// Combat effects: spark streaks, glints, dust, shock rings, blade trails, dash afterimages, the crescent wave.
import * as THREE from 'three';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';

const V3 = THREE.Vector3;
const rnd = (a, b) => a + Math.random() * (b - a);

function canvasTex(size, draw) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  draw(c.getContext('2d'), size);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
const TEX = {};
function textures() {
  if (TEX.dot) return TEX;
  TEX.dot = canvasTex(64, (g, s) => {
    const r = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
    r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.3, 'rgba(255,255,255,0.55)'); r.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = r; g.fillRect(0, 0, s, s);
  });
  TEX.star = canvasTex(256, (g, s) => {
    g.fillStyle = '#000'; g.fillRect(0, 0, s, s);
    g.globalCompositeOperation = 'lighter';
    const r = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s * 0.42);
    r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.12, 'rgba(255,255,255,0.5)'); r.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = r; g.fillRect(0, 0, s, s);
    for (const [ang, len, w] of [[0, 0.5, 5], [Math.PI / 2, 0.5, 5], [Math.PI / 4, 0.26, 3], [-Math.PI / 4, 0.26, 3]]) {
      g.save(); g.translate(s / 2, s / 2); g.rotate(ang);
      const l = g.createLinearGradient(-s * len, 0, s * len, 0);
      l.addColorStop(0, 'rgba(255,255,255,0)'); l.addColorStop(0.5, 'rgba(255,255,255,1)'); l.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = l; g.fillRect(-s * len, -w / 2, s * len * 2, w);
      g.restore();
    }
  });
  TEX.smoke = canvasTex(128, (g, s) => {
    for (let i = 0; i < 26; i++) {
      const x = rnd(0.3, 0.7) * s, y = rnd(0.3, 0.7) * s, rr = rnd(0.12, 0.3) * s;
      const r = g.createRadialGradient(x, y, 0, x, y, rr);
      r.addColorStop(0, 'rgba(255,255,255,0.16)'); r.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = r; g.fillRect(0, 0, s, s);
    }
  });
  return TEX;
}

class Streaks {
  constructor(scene, n = 900) {
    this.n = n; this.i = 0;
    this.p = new Float32Array(n * 3); this.v = new Float32Array(n * 3); this.life = new Float32Array(n); this.max = new Float32Array(n);
    this.col = new Float32Array(n * 3); this.grav = new Float32Array(n); this.len = new Float32Array(n);
    const g = new THREE.BufferGeometry();
    this.pos = new THREE.BufferAttribute(new Float32Array(n * 6), 3);
    this.c = new THREE.BufferAttribute(new Float32Array(n * 6), 3);
    g.setAttribute('position', this.pos); g.setAttribute('color', this.c);
    this.mesh = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ vertexColors: true, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, toneMapped: false }));
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
  }
  add(p, v, life, color, grav = 9, len = 0.035) {
    const i = this.i; this.i = (i + 1) % this.n;
    this.p.set([p.x, p.y, p.z], i * 3); this.v.set([v.x, v.y, v.z], i * 3);
    this.life[i] = this.max[i] = life; this.col.set([color.r, color.g, color.b], i * 3); this.grav[i] = grav; this.len[i] = len;
  }
  update(dt) {
    const { p, v, life, pos, c, col } = this;
    for (let i = 0; i < this.n; i++) {
      const j = i * 3, k = i * 6;
      if (life[i] <= 0) { if (c.array[k] !== 0 || c.array[k + 3] !== 0) { c.array.fill(0, k, k + 6); pos.array.fill(0, k, k + 6); } continue; }
      life[i] -= dt;
      v[j + 1] -= this.grav[i] * dt;
      p[j] += v[j] * dt; p[j + 1] += v[j + 1] * dt; p[j + 2] += v[j + 2] * dt;
      if (p[j + 1] < 0.02) { p[j + 1] = 0.02; v[j + 1] *= -0.35; v[j] *= 0.6; v[j + 2] *= 0.6; }
      const a = Math.max(0, life[i] / this.max[i]), L = this.len[i];
      pos.array[k] = p[j]; pos.array[k + 1] = p[j + 1]; pos.array[k + 2] = p[j + 2];
      pos.array[k + 3] = p[j] - v[j] * L; pos.array[k + 4] = p[j + 1] - v[j + 1] * L; pos.array[k + 5] = p[j + 2] - v[j + 2] * L;
      c.array[k] = col[j] * a; c.array[k + 1] = col[j + 1] * a; c.array[k + 2] = col[j + 2] * a;
      c.array[k + 3] = 0; c.array[k + 4] = 0; c.array[k + 5] = 0;
    }
    pos.needsUpdate = true; c.needsUpdate = true;
  }
}

class SpritePool {
  constructor(scene, n, tex, blending) {
    this.items = [];
    for (let i = 0; i < n; i++) {
      const m = new THREE.SpriteMaterial({ map: tex, blending, depthWrite: false, transparent: true, opacity: 0, toneMapped: blending !== THREE.AdditiveBlending });
      const s = new THREE.Sprite(m);
      s.visible = false; s.renderOrder = 5;
      scene.add(s);
      this.items.push({ s, life: 0, max: 1, v: new V3(), s0: 1, s1: 1, a: 1, follow: null, rot: 0 });
    }
    this.i = 0;
  }
  add(p, { color = 0xffffff, s0 = 0.3, s1 = 1, life = 0.3, a = 1, v = null, follow = null, rot = 0 } = {}) {
    const it = this.items[this.i]; this.i = (this.i + 1) % this.items.length;
    it.s.position.copy(p); it.s.material.color.set(color); it.s.material.rotation = Math.random() * 6.28;
    it.life = it.max = life; it.s0 = s0; it.s1 = s1; it.a = a; it.follow = follow; it.rot = rot;
    if (v) it.v.copy(v); else it.v.set(0, 0, 0);
    it.s.visible = true;
    return it;
  }
  update(dt) {
    for (const it of this.items) {
      if (it.life <= 0) continue;
      it.life -= dt;
      if (it.life <= 0) { it.s.visible = false; continue; }
      const k = 1 - it.life / it.max;
      if (it.follow) it.follow(it.s.position); else it.s.position.addScaledVector(it.v, dt);
      const sc = it.s0 + (it.s1 - it.s0) * (1 - (1 - k) * (1 - k));
      it.s.scale.set(sc, sc, 1);
      it.s.material.rotation += it.rot * dt;
      it.s.material.opacity = it.a * Math.sin(Math.min(1, k * 6) * Math.PI / 2) * (1 - k) ** 1.2;
    }
  }
}

export class Trail {
  constructor(scene, color = 0xbfe4ff, n = 40, life = 0.2) {
    this.n = n; this.life = life; this.samples = [];
    const g = new THREE.BufferGeometry();
    this.pos = new THREE.BufferAttribute(new Float32Array(n * 6), 3);
    this.uv = new THREE.BufferAttribute(new Float32Array(n * 4), 2);
    g.setAttribute('position', this.pos); g.setAttribute('uv', this.uv);
    const idx = [];
    for (let i = 0; i < n - 1; i++) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
    g.setIndex(idx);
    this.mat = new THREE.ShaderMaterial({
      uniforms: { color: { value: new THREE.Color(color) }, gain: { value: 1 } },
      vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: `uniform vec3 color; uniform float gain; varying vec2 vUv;
        void main(){ float a = vUv.x; float w = smoothstep(0.0, 0.75, vUv.y) * (0.35 + 0.65 * smoothstep(0.55, 1.0, vUv.y));
          float core = smoothstep(0.90, 1.0, vUv.y);
          gl_FragColor = vec4((color * w + vec3(1.0) * core * 0.8) * a * a * gain, 1.0); }`,
      blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, side: THREE.DoubleSide, toneMapped: false,
    });
    this.mesh = new THREE.Mesh(g, this.mat);
    this.mesh.frustumCulled = false; this.mesh.renderOrder = 4;
    scene.add(this.mesh);
    this.on = false;
  }
  setColor(c) { this.mat.uniforms.color.value.set(c); }
  /** Call every frame with the blade's base and tip; `on` adds to the ribbon. */
  update(dt, base, tip, on) {
    for (const s of this.samples) s.age += dt;
    while (this.samples.length && this.samples[this.samples.length - 1].age > this.life) this.samples.pop();
    if (on) {
      const last = this.samples[0];
      if (last && this.wasOn) {                 // subdivide fast swings so the arc stays round
        const d = last.tip.distanceTo(tip), k = Math.min(10, Math.floor(d / 0.11));
        if (k > 0) {
          const d0 = new V3().subVectors(last.tip, last.base), d1 = new V3().subVectors(tip, base), l0 = d0.length(), l1 = d1.length();
          const q = new THREE.Quaternion().setFromUnitVectors(d0.clone().normalize(), d1.clone().normalize()), qi = new THREE.Quaternion(), ID = new THREE.Quaternion();
          for (let i = 1; i <= k; i++) {          // swing the blade direction round its own base: a true arc, not a chord
            const f = i / (k + 1), b = last.base.clone().lerp(base, f);
            qi.copy(ID).slerp(q, f);
            const t = d0.clone().normalize().applyQuaternion(qi).multiplyScalar(l0 + (l1 - l0) * f).add(b);
            this.samples.unshift({ base: b, tip: t, age: last.age * (1 - f) });
          }
        }
      }
      this.samples.unshift({ base: base.clone(), tip: tip.clone(), age: 0 });
      if (this.samples.length > this.n) this.samples.length = this.n;
    }
    this.wasOn = on;
    const P = this.pos.array, U = this.uv.array, m = this.samples.length;
    for (let i = 0; i < this.n; i++) {
      const s = this.samples[Math.min(i, m - 1)];
      if (!s) { P.fill(0, i * 6, i * 6 + 6); U.fill(0, i * 4, i * 4 + 4); continue; }
      const a = i < m ? Math.max(0, 1 - s.age / this.life) : 0;
      P[i * 6] = s.base.x; P[i * 6 + 1] = s.base.y; P[i * 6 + 2] = s.base.z;
      P[i * 6 + 3] = s.tip.x; P[i * 6 + 4] = s.tip.y; P[i * 6 + 5] = s.tip.z;
      U[i * 4] = a; U[i * 4 + 1] = 0; U[i * 4 + 2] = a; U[i * 4 + 3] = 1;
    }
    this.pos.needsUpdate = true; this.uv.needsUpdate = true;
    this.mesh.visible = m > 1;
  }
}

/** Translucent afterimages of an actor (pose snapshots), used for the hero's dash and the boss's dash-slash. */
export class Ghosts {
  constructor(scene, actor, n = 4, color = 0x7fc8ff) {
    this.src = actor; this.items = []; this.i = 0;
    this.mat = new THREE.ShaderMaterial({
      uniforms: { color: { value: new THREE.Color(color) }, alpha: { value: 0 } },
      vertexShader: `#include <common>\n#include <skinning_pars_vertex>\nvarying vec3 vN; varying vec3 vV;
        void main(){\n#include <skinbase_vertex>\n#include <beginnormal_vertex>\n#include <skinnormal_vertex>\n#include <begin_vertex>\n#include <skinning_vertex>\n
          vec4 mv = modelViewMatrix * vec4(transformed, 1.0); vN = normalize(normalMatrix * objectNormal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform vec3 color; uniform float alpha; varying vec3 vN; varying vec3 vV;
        void main(){ float f = pow(clamp(1.0 - abs(dot(normalize(vN + 1e-5), normalize(vV + 1e-5))), 0.0, 1.0), 1.6); gl_FragColor = vec4(color * (0.25 + 1.6 * f) * alpha, 1.0); }`,
      blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, toneMapped: false,
    });
    for (let k = 0; k < n; k++) {
      const root = SkeletonUtils.clone(actor.model);
      const mat = this.mat.clone();
      const bones = {};
      root.traverse((o) => {
        if (o.isBone) bones[o.name] = o;
        if (o.isMesh) { o.material = mat; o.castShadow = false; o.receiveShadow = false; o.frustumCulled = false; o.renderOrder = 3; }
      });
      const g = new THREE.Group();
      g.add(root); g.visible = false;
      scene.add(g);
      this.items.push({ g, bones, mat, life: 0, max: 1 });
    }
  }
  spawn(life = 0.35, alpha = 0.8, color = null) {
    const it = this.items[this.i]; this.i = (this.i + 1) % this.items.length;
    it.g.position.copy(this.src.root.position); it.g.rotation.copy(this.src.root.rotation);
    for (const [n, b] of Object.entries(it.bones)) {
      const s = this.src.bones[n];
      if (s) { b.position.copy(s.position); b.quaternion.copy(s.quaternion); b.scale.copy(s.scale); }
    }
    if (color !== null) it.mat.uniforms.color.value.set(color);
    it.life = it.max = life; it.a = alpha; it.g.visible = true;
  }
  update(dt) {
    for (const it of this.items) {
      if (it.life <= 0) continue;
      it.life -= dt;
      it.mat.uniforms.alpha.value = it.a * Math.max(0, it.life / it.max);
      if (it.life <= 0) it.g.visible = false;
    }
  }
}

export class FX {
  constructor(scene) {
    const T = textures();
    this.scene = scene;
    this.streaks = new Streaks(scene);
    this.glints = new SpritePool(scene, 24, T.star, THREE.AdditiveBlending);
    this.glows = new SpritePool(scene, 40, T.dot, THREE.AdditiveBlending);
    this.smoke = new SpritePool(scene, 48, T.smoke, THREE.NormalBlending);
    this.rings = [];
    const rg = new THREE.RingGeometry(0.86, 1.0, 64);
    rg.rotateX(-Math.PI / 2);
    for (let i = 0; i < 6; i++) {
      const m = new THREE.Mesh(rg, new THREE.MeshBasicMaterial({ color: 0xffffff, blending: THREE.AdditiveBlending, transparent: true, opacity: 0, depthWrite: false, toneMapped: false, side: THREE.DoubleSide }));
      m.visible = false; m.renderOrder = 2;
      scene.add(m);
      this.rings.push({ m, life: 0, max: 1, r0: 1, r1: 4 });
    }
    this.ri = 0;
    this._c = new THREE.Color();
  }

  sparks(p, n = 24, { color = 0xffc070, speed = 7, spread = 1, dir = null, life = 0.45, grav = 12, up = 1.5 } = {}) {
    const c = this._c.set(color), v = new V3();
    for (let i = 0; i < n; i++) {
      v.set(rnd(-1, 1), rnd(-0.6, 1), rnd(-1, 1)).normalize().multiplyScalar(spread);
      if (dir) v.addScaledVector(dir, 1.2);
      v.normalize().multiplyScalar(speed * rnd(0.25, 1));
      v.y += up * Math.random();
      this.streaks.add(p, v, life * rnd(0.5, 1), c, grav, rnd(0.02, 0.05));
    }
  }

  glint(p, { color = 0xffffff, size = 1.6, life = 0.4, follow = null } = {}) {
    this.glints.add(p, { color, s0: size * 0.15, s1: size, life, a: 1, follow, rot: 2.5 });
    this.glows.add(p, { color, s0: size * 0.4, s1: size * 1.3, life: life * 0.9, a: 0.55, follow });
  }

  glow(p, { color = 0xffffff, size = 1, life = 0.25, a = 0.8, v = null } = {}) { this.glows.add(p, { color, s0: size * 0.5, s1: size, life, a, v }); }

  dust(p, n = 6, { color = 0x8f98a8, size = 1.2, speed = 1.2, life = 0.9, a = 0.22 } = {}) {
    const v = new V3(), q = new V3();
    for (let i = 0; i < n; i++) {
      v.set(rnd(-1, 1), rnd(0.1, 0.7), rnd(-1, 1)).multiplyScalar(speed);
      q.copy(p).add(new V3(rnd(-0.3, 0.3), rnd(0, 0.2), rnd(-0.3, 0.3)));
      this.smoke.add(q, { color, s0: size * 0.4, s1: size * rnd(1, 1.8), life: life * rnd(0.6, 1), a, v, rot: rnd(-1, 1) });
    }
  }

  ring(p, { color = 0xffe0b0, r0 = 0.4, r1 = 5, life = 0.5, y = 0.06 } = {}) {
    const it = this.rings[this.ri]; this.ri = (this.ri + 1) % this.rings.length;
    it.m.position.set(p.x, y, p.z); it.m.material.color.set(color);
    it.life = it.max = life; it.r0 = r0; it.r1 = r1; it.m.visible = true;
  }

  /** The burst when steel meets steel. */
  clash(p, big = false, color = 0xffd9a0) {
    this.sparks(p, big ? 70 : 26, { color, speed: big ? 11 : 7, life: big ? 0.6 : 0.4 });
    this.glint(p, { color: big ? 0xffffff : color, size: big ? 3.2 : 1.5, life: big ? 0.32 : 0.22 });
  }

  /** A cut landing on armour or cloth. */
  slash(p, dir, { color = 0xfff0e0, crit = false } = {}) {
    this.sparks(p, crit ? 40 : 16, { color: crit ? 0xffb060 : 0xffd0a0, speed: crit ? 9 : 6, dir, spread: 0.7, life: 0.35 });
    this.glow(p, { color, size: crit ? 2.2 : 1.2, life: 0.16, a: 0.9 });
    this.dust(p, 2, { color: 0xb0b6c0, size: 0.7, speed: 0.8, life: 0.5, a: 0.18 });
  }

  update(dt) {
    this.streaks.update(dt); this.glints.update(dt); this.glows.update(dt); this.smoke.update(dt);
    for (const it of this.rings) {
      if (it.life <= 0) continue;
      it.life -= dt;
      if (it.life <= 0) { it.m.visible = false; continue; }
      const k = 1 - it.life / it.max, r = it.r0 + (it.r1 - it.r0) * (1 - (1 - k) ** 3);
      it.m.scale.set(r, 1, r);
      it.m.material.opacity = (1 - k) ** 1.5;
    }
  }
}

/** The boss's crescent wave: a tall blade of fire that runs along the ground. */
export class Wave {
  constructor(scene) {
    const N = 24, pos = [], uv = [], idx = [];
    for (let i = 0; i <= N; i++) {
      const a = i / N * 2 - 1;
      const x = a * 1.7, z = -a * a * 1.1, h = 2.6 * (1 - 0.75 * a * a);
      pos.push(x, 0.03, z, x * 0.92, h, z - 0.25 * (1 - a * a));
      uv.push(i / N, 0, i / N, 1);
      if (i < N) { const k = i * 2; idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(idx);
    this.mat = new THREE.ShaderMaterial({
      uniforms: { t: { value: 0 }, alpha: { value: 0 } },
      vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: `uniform float t; uniform float alpha; varying vec2 vUv;
        float h(vec2 p){ return fract(sin(dot(p, vec2(41.3, 289.1))) * 43758.5); }
        float n(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
          return mix(mix(h(i), h(i + vec2(1, 0)), f.x), mix(h(i + vec2(0, 1)), h(i + vec2(1, 1)), f.x), f.y); }
        void main(){ float e = 1.0 - abs(vUv.x * 2.0 - 1.0);
          float f = n(vec2(vUv.x * 9.0, vUv.y * 5.0 - t * 7.0)) * 0.6 + n(vec2(vUv.x * 21.0, vUv.y * 11.0 - t * 12.0)) * 0.4;
          float body = smoothstep(0.0, 0.25, e) * (1.0 - vUv.y) * (0.45 + f);
          float rim = pow(1.0 - vUv.y, 6.0) * 2.0 + smoothstep(0.82, 1.0, f * (1.0 - vUv.y * 0.6)) * 1.5;
          vec3 c = vec3(1.0, 0.16, 0.05) * body * 2.2 + vec3(1.0, 0.75, 0.4) * rim * smoothstep(0.0, 0.2, e);
          gl_FragColor = vec4(c * alpha, 1.0); }`,
      blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, side: THREE.DoubleSide, toneMapped: false,
    });
    this.mesh = new THREE.Mesh(g, this.mat);
    this.mesh.visible = false; this.mesh.frustumCulled = false; this.mesh.renderOrder = 4;
    this.light = new THREE.PointLight(0xff4a1a, 0, 9, 1.8);
    this.mesh.add(this.light); this.light.position.set(0, 1, 0);
    scene.add(this.mesh);
    this.active = false; this.dir = new V3(); this.travel = 0; this.hit = false; this.time = 0;
  }
  launch(p, yaw) {
    this.mesh.position.set(p.x, 0, p.z); this.mesh.rotation.y = yaw;
    this.dir.set(Math.sin(yaw), 0, Math.cos(yaw));
    this.active = true; this.travel = 0; this.hit = false; this.mesh.visible = true; this.time = 0;
  }
  update(dt, speed = 15, range = 24) {
    if (!this.active) return;
    this.time += dt;
    this.mesh.position.addScaledVector(this.dir, speed * dt);
    this.travel += speed * dt;
    const a = Math.min(1, this.time * 8) * Math.max(0, Math.min(1, (range - this.travel) / 4));
    this.mat.uniforms.t.value = this.time; this.mat.uniforms.alpha.value = a;
    this.light.intensity = 60 * a;
    if (this.travel > range) { this.active = false; this.mesh.visible = false; this.light.intensity = 0; }
  }
}

/** Ghost-light material for summoned arms (works on skinned and static meshes). */
export function spiritMaterial(color = 0x6fd0ff) {
  return new THREE.ShaderMaterial({
    uniforms: { color: { value: new THREE.Color(color) }, alpha: { value: 1 }, time: { value: 0 } },
    vertexShader: [
      '#include <common>', '#include <skinning_pars_vertex>', 'varying vec3 vN; varying vec3 vV; varying vec3 vP;', 'void main(){',
      '#include <skinbase_vertex>', '#include <beginnormal_vertex>', '#include <skinnormal_vertex>', '#include <begin_vertex>', '#include <skinning_vertex>',
      'vec4 mv = modelViewMatrix * vec4(transformed, 1.0); vN = normalMatrix * objectNormal; vV = -mv.xyz; vP = (modelMatrix * vec4(transformed, 1.0)).xyz; gl_Position = projectionMatrix * mv; }',
    ].join('\n'),
    fragmentShader: `uniform vec3 color; uniform float alpha; uniform float time; varying vec3 vN; varying vec3 vV; varying vec3 vP;
      void main(){ float f = pow(clamp(1.0 - abs(dot(normalize(vN + 1e-5), normalize(vV + 1e-5))), 0.0, 1.0), 1.4);
        float band = 0.6 + 0.4 * sin(vP.y * 38.0 - time * 9.0);
        gl_FragColor = vec4((color * (0.55 + 2.4 * f) + vec3(1.0) * f * f * 0.9) * band * alpha, 1.0); }`,
    blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, toneMapped: false, side: THREE.DoubleSide,
  });
}

/** Thrown spirit blades: fly at the target, lightly homing. */
export class Daggers {
  constructor(scene, proto, n = 6) {
    this.items = [];
    this.mat = spiritMaterial(0x8fe0ff);
    for (let i = 0; i < n; i++) {
      let o;
      if (proto) { o = proto.clone(); o.traverse((c) => { if (c.isMesh) { c.material = this.mat; c.castShadow = false; c.frustumCulled = false; } }); }
      else { const g = new THREE.ConeGeometry(0.035, 0.34, 6); g.rotateX(Math.PI / 2); o = new THREE.Mesh(g, this.mat); }
      const grp = new THREE.Group();
      grp.add(o); grp.scale.setScalar(1.6); grp.visible = false;
      scene.add(grp);
      this.items.push({ g: grp, v: new V3(), life: 0 });
    }
    this.i = 0;
  }
  throw(from, dir) {
    const it = this.items[this.i]; this.i = (this.i + 1) % this.items.length;
    it.g.position.copy(from); it.v.copy(dir).normalize().multiplyScalar(30); it.life = 1.3; it.g.visible = true;
  }
  /** target: Vector3 (boss chest). onHit(position) when a blade arrives. onFly(position) every frame for sparkle. */
  update(dt, target, radius, onHit, onFly) {
    this.mat.uniforms.time.value += dt;
    const d = new V3();
    for (const it of this.items) {
      if (it.life <= 0) continue;
      it.life -= dt;
      d.subVectors(target, it.g.position);
      const dist = d.length();
      it.v.lerp(d.normalize().multiplyScalar(30), Math.min(1, dt * 9));
      it.g.position.addScaledVector(it.v, dt);
      it.g.lookAt(d.copy(it.g.position).add(it.v));
      if (onFly) onFly(it.g.position);
      if (dist < radius + it.v.length() * dt) { it.life = 0; it.g.visible = false; onHit(it.g.position.clone()); }
      else if (it.life <= 0) it.g.visible = false;
    }
  }
}
