// A rigged fighter: clip playback with crossfades, root motion from the baked `adv` curves,
// event/hit queries, bone markers and verlet spring chains (scarf, coat, cape, plume).
import * as THREE from 'three';

const V3 = THREE.Vector3;
const san = (n) => n.replace(/\./g, '');
const _a = new V3(), _b = new V3(), _c = new V3(), _q = new THREE.Quaternion();

export class Actor {
  constructor(gltf, meta, { springCfg = {} } = {}) {
    this.root = new THREE.Group();
    this.model = gltf.scene;
    this.root.add(this.model);
    this.meta = meta;
    this.bones = {};
    this.mats = [];
    this.meshes = [];
    this.model.traverse((o) => {
      if (o.isBone) this.bones[o.name] = o;
      if (o.isMesh) {
        o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false;
        this.meshes.push(o);
        for (const m of [].concat(o.material)) {
          if (this.mats.includes(m)) continue;
          this.mats.push(m);
          const t = m.userData && m.userData.tint;
          if (t && m.map) m.color.setRGB(t[0], t[1], t[2]);
          m.envMapIntensity = 0.9;
          if (Array.isArray(m.userData.glow)) m.emissive.setRGB(...m.userData.glow);      // the exporter drops emission at strength 0
          m.userData.baseEmissive = m.emissive.clone();
          m.userData.baseEI = m.emissiveIntensity;
        }
      }
    });
    const skip = new Set(meta.springs.flat().map(san).concat('root'));
    this.mixer = new THREE.AnimationMixer(this.model);
    this.act = {};
    for (const clip of gltf.animations) {
      if (!meta.clips[clip.name]) continue;
      clip.tracks = clip.tracks.filter((t) => !skip.has(t.name.split('.')[0]));
      const a = this.mixer.clipAction(clip);
      if (!meta.clips[clip.name].loop) { a.setLoop(THREE.LoopOnce, 1); a.clampWhenFinished = true; }
      this.act[clip.name] = a;
    }
    this.mark = {};
    for (const [name, m] of Object.entries(meta.markers)) {
      const o = new THREE.Object3D();
      o.position.fromArray(m.off);
      this.bone(m.bone).add(o);
      this.mark[name] = o;
    }
    this.springs = meta.springs.map((chain) => chain.map((b) => {
      const off = new V3().fromArray(meta.markers[b].off);
      const k = /^(coat|tas|tabard)/.test(chain[0]) ? 5 : /^(sash|tassel)/.test(chain[0]) ? 2 : 1;      // armour and coat skirts are stiffer than scarves
      return { bone: this.bone(b), off, len: off.length(), dir: off.clone().normalize(), p: new V3(), prev: new V3(), init: false, k, cape: /^cape/.test(chain[0]) };
    }));
    this.springCfg = Object.assign({ stiff: 0.012, damp: 0.965, grav: 9.0, wind: new V3() }, springCfg);
    this.caps = ['thigh.L', 'shin.L', 'foot.L', 'thigh.R', 'shin.R', 'foot.R'].map((n) => ({ b: this.bone(n), p: new V3() }));
    this.capR = 0.105 * (this.bone('hips').position.y || 1);
    this.acc = 0;
    this.clip = null; this.t = 0; this.prevT = 0; this.speed = 1; this.motionScale = 1; this.yaw = 0;
    this.pos = this.root.position;
    this.flash = 0;
  }

  bone(n) { return this.bones[san(n)]; }
  get dur() { return this.meta.clips[this.clip].dur; }
  get done() { return !this.meta.clips[this.clip].loop && this.t >= this.dur - 1e-4; }
  fwd(out = new V3()) { return out.set(Math.sin(this.yaw), 0, Math.cos(this.yaw)); }
  left(out = new V3()) { return out.set(Math.cos(this.yaw), 0, -Math.sin(this.yaw)); }
  at(name, out = new V3()) { return this.mark[name].getWorldPosition(out); }

  play(name, { fade = 0.1, speed = 1, at = 0, force = false } = {}) {
    if (this.clip === name && !force && this.meta.clips[name].loop) { this.speed = speed; return; }
    const next = this.act[name];
    if (!next) { console.warn('missing clip', name); return; }
    const prev = this.clip && this.act[this.clip];
    next.reset(); next.time = at; next.setEffectiveTimeScale(1); next.setEffectiveWeight(1);
    if (prev && prev !== next && fade > 0) { next.play(); prev.crossFadeTo(next, fade, false); }
    else { if (prev && prev !== next) prev.stop(); next.play(); }
    this.clip = name; this.t = at; this.prevT = at; this.speed = speed; this.motionScale = 1;
  }

  advAt(t) {
    const adv = this.meta.clips[this.clip].adv;
    if (!adv) return null;
    const x = Math.min(Math.max(t * 60, 0), adv.length - 1), i = Math.min(Math.floor(x), adv.length - 2), f = x - i;
    return [adv[i][0] + (adv[i + 1][0] - adv[i][0]) * f, adv[i][1] + (adv[i + 1][1] - adv[i][1]) * f];
  }

  /** True on the frame the clip time crosses the named event. */
  ev(name) {
    const e = this.meta.clips[this.clip].events;
    if (!e || e[name] === undefined) return false;
    if (this.prevT <= this.t) return this.prevT < e[name] && this.t >= e[name];
    return e[name] > this.prevT || e[name] <= this.t;          // a looping clip wrapped this frame
  }
  evTime(name, clip = this.clip) { const e = this.meta.clips[clip].events; return e && e[name] !== undefined ? e[name] : null; }
  hits(clip = this.clip) { return this.meta.clips[clip].hits || []; }

  update(dt) {
    const meta = this.meta.clips[this.clip];
    this.prevT = this.t;
    const step = dt * this.speed;
    const a = this.act[this.clip];
    a.setEffectiveTimeScale(this.speed);
    this.mixer.update(dt);
    this.t = meta.loop ? a.time : Math.min(this.t + step, meta.dur);
    if (meta.adv && !meta.loop) {
      const p0 = this.advAt(this.prevT), p1 = this.advAt(this.t);
      const df = (p1[0] - p0[0]) * this.motionScale, dl = (p1[1] - p0[1]) * this.motionScale;
      this.pos.x += Math.sin(this.yaw) * df + Math.cos(this.yaw) * dl;
      this.pos.z += Math.cos(this.yaw) * df - Math.sin(this.yaw) * dl;
    }
    this.root.rotation.y = this.yaw;
    if (this.flash > 0 || this._flashOn) {
      this.flash = Math.max(0, this.flash - dt * 6);
      this._flashOn = this.flash > 0;
      for (const m of this.mats) {
        if (m.userData.noFlash) continue;
        m.emissive.copy(m.userData.baseEmissive).lerp(this.flashColor || WHITE, Math.min(1, this.flash));
        m.emissiveIntensity = m.userData.baseEI + this.flash * 1.4;
      }
    }
  }

  hitFlash(v = 1, color = WHITE) { this.flash = v; this.flashColor = color; this._flashOn = true; }

  /** Push a cloth point out of the leg capsules (hip-knee and knee-ankle on each side). */
  collide(p) {
    const R = this.capR + 0.035, C = this.caps;
    for (const i of [0, 1, 3, 4]) {
      const a = C[i].p, b = C[i + 1].p;
      const bx = b.x - a.x, by = b.y - a.y, bz = b.z - a.z, l2 = bx * bx + by * by + bz * bz || 1;
      const u = Math.max(0, Math.min(1, ((p.x - a.x) * bx + (p.y - a.y) * by + (p.z - a.z) * bz) / l2));
      const dx = p.x - (a.x + bx * u), dy = p.y - (a.y + by * u), dz = p.z - (a.z + bz * u), dd = Math.hypot(dx, dy, dz);
      if (dd < R && dd > 1e-4) { const k = (R - dd) / dd; p.x += dx * k; p.y += dy * k * 0.3; p.z += dz * k; }
    }
  }

  resetSprings() { this.springs.flat().forEach((s) => { s.init = false; }); }

  updateSprings(dt) {
    const { stiff, damp, grav, wind } = this.springCfg;
    this.acc = Math.min(this.acc + dt, 0.05);
    const steps = Math.floor(this.acc / (1 / 120));
    this.acc -= steps / 120;
    this.root.updateMatrixWorld(true);
    const head = _a, rest = _b, d = _c, pq = _q;
    for (const c of this.caps) c.p.setFromMatrixPosition(c.b.matrixWorld);
    for (const chain of this.springs) {
      for (const s of chain) {
        const b = s.bone;
        b.quaternion.identity();
        b.updateWorldMatrix(true, false);
        head.setFromMatrixPosition(b.matrixWorld);
        rest.copy(s.off).applyMatrix4(b.matrixWorld);
        if (!s.init) { s.p.copy(rest); s.prev.copy(rest); s.init = true; }
        for (let i = 0; i < steps; i++) {
          d.subVectors(s.p, s.prev).multiplyScalar(damp);
          s.prev.copy(s.p);
          s.p.add(d); s.p.y -= grav / 14400;
          s.p.x += wind.x / 14400; s.p.z += wind.z / 14400;
          s.p.lerp(rest, Math.min(0.5, stiff * s.k));
          d.subVectors(s.p, head).setLength(s.len);
          s.p.addVectors(head, d);
          if (s.p.y < 0.04) s.p.y = 0.04;
          if (s.k > 1 || s.cape) this.collide(s.p);
        }
        d.subVectors(s.p, head).normalize();
        b.parent.getWorldQuaternion(pq).invert();
        b.quaternion.setFromUnitVectors(s.dir, d.applyQuaternion(pq));
        b.updateWorldMatrix(false, true);
      }
    }
  }
}
const WHITE = new THREE.Color(1, 1, 1);

/** Shortest signed angle from a to b. */
export function angDiff(a, b) { let d = (b - a) % (Math.PI * 2); if (d > Math.PI) d -= Math.PI * 2; if (d < -Math.PI) d += Math.PI * 2; return d; }
export function turnTo(cur, target, maxStep) { const d = angDiff(cur, target); return cur + Math.max(-maxStep, Math.min(maxStep, d)); }
export function yawTo(from, to) { return Math.atan2(to.x - from.x, to.z - from.z); }
export function dist2(a, b) { return Math.hypot(a.x - b.x, a.z - b.z); }

/** Does a blade (base->tip, swept from its previous position) pass within `radius` of a standing target? */
export function bladeTouches(b0, t0, b1, t1, target, radius, height, ext = 0.25) {
  for (let i = 0; i <= 4; i++) {
    const k = i / 4;
    const bx = b0.x + (b1.x - b0.x) * k, by = b0.y + (b1.y - b0.y) * k, bz = b0.z + (b1.z - b0.z) * k;
    let tx = t0.x + (t1.x - t0.x) * k, ty = t0.y + (t1.y - t0.y) * k, tz = t0.z + (t1.z - t0.z) * k;
    let dx = tx - bx, dy = ty - by, dz = tz - bz;
    const L = Math.hypot(dx, dy, dz) || 1;
    tx += dx / L * ext; ty += dy / L * ext; tz += dz / L * ext;
    dx = tx - bx; dy = ty - by; dz = tz - bz;
    const l2 = dx * dx + dz * dz;
    let u = l2 > 1e-6 ? ((target.x - bx) * dx + (target.z - bz) * dz) / l2 : 0;
    u = Math.max(0, Math.min(1, u));
    const px = bx + dx * u, py = by + dy * u, pz = bz + dz * u;
    if (Math.hypot(px - target.x, pz - target.z) < radius && py > -0.3 && py < height + 0.3) return _hitPoint.set(px, Math.min(Math.max(py, 0.4), height), pz);
  }
  return null;
}
const _hitPoint = new V3();
