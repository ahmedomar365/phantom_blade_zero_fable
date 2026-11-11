// Marshal Yan: two-phase glaive master. Telegraphed combos (gold = can be parried, red = must be dodged),
// a guard-and-counter answer to greedy combos, a posture meter that opens him to a finisher.
import * as THREE from 'three';
import { Actor, turnTo, yawTo, dist2, bladeTouches } from './actor.js';
import { T, rndIn } from './tuning.js';

const V3 = THREE.Vector3;
const rnd = (a, b) => a + Math.random() * (b - a);

export const BOSS_ATK = {
  Sweep: { dmg: [15, 15, 24], knock: [0, 0, 1], cost: 22, track: 3.4, reach: 2.2, post: 15 },
  Thrust: { dmg: [24], knock: [1], cost: 34, track: 4.0, reach: 2.7, post: 24 },
  Whirl: { dmg: [16, 16, 16, 16], knock: [1, 1, 1, 1], red: true, track: 1.6, reach: 2.2 },
  Leap: { dmg: [32], knock: [1], red: true, aoe: 3.3, track: 5 },
  Flurry: { dmg: [10, 10, 10, 10, 24], knock: [0, 0, 0, 0, 1], cost: 14, track: 4.2, reach: 2.3, post: 10 },
  DashSlash: { dmg: [28], knock: [1], red: true, track: 5 },
  Wave: { dmg: [20], knock: [1], red: true, track: 4 },
  Counter: { dmg: [15], knock: [0], cost: 24, track: 7, reach: 2.3, post: 20 },
};

export class Boss {
  constructor(G, gltf, meta) {
    this.G = G;
    this.a = new Actor(gltf, meta, { springCfg: { stiff: 0.008, damp: 0.972, grav: 9 } });
    this.pos = this.a.pos;
    this.radius = 0.9; this.maxHp = 2200;
    this.eye = this.a.mats.find((m) => m.name === 'b_eye');
    this.edge = this.a.mats.find((m) => m.name === 'b_blade_edge');
    for (const m of [this.eye, this.edge]) if (m) m.userData.noFlash = true;
    if (this.edge) this.edge.emissive.setRGB(1.0, 0.24, 0.04);
    this._s1 = new V3(); this._s0 = new V3();
    this._b0 = new V3(); this._t0 = new V3(); this._b1 = new V3(); this._t1 = new V3();
    this.from = new V3(); this.to = new V3(); this.dir = new V3();
    this.has = (c) => !!this.a.act[c];
    this.reset();
  }

  reset(phase = 1) {
    this.maxHp = T.bossHp;
    this.phase = phase; this.hp = phase === 2 ? this.maxHp * 0.5 : this.maxHp;
    this.posture = 0; this.postT = 0; this.chain = 0; this.chainT = 0; this.guardAt = T.guardP1[0];
    this.state = 'idle'; this.stateT = 0; this.think = 1.2; this.atk = null; this.last = null; this.pendingEnrage = false;
    this.hitDone = []; this.trail = false; this.kneelT = 0; this.eyeFlash = 0;
    this.a.play('Idle', { fade: 0 });
    this.a.resetSprings();
    this.setMood(phase === 2 ? 1 : 0, true);
  }

  setMood(k, instant = false) { this.mood = k; if (instant) this.moodNow = k; }

  set(state, clip, opts) { this.state = state; this.stateT = 0; if (clip) this.a.play(clip, opts); }
  get busy() { return ['cine', 'enrage', 'dying', 'dead', 'executed'].includes(this.state); }
  canExecute(hero) { return (this.state === 'kneel' || (this.state === 'break' && this.a.t > 0.5)) && dist2(hero.pos, this.pos) < 3.6; }

  /** Info for the bot and HUD: the strike about to land. */
  threat() {
    if (this.state !== 'attack') return null;
    const spec = BOSS_ATK[this.atk], hits = this.a.hits();
    let next = null;
    for (let i = 0; i < hits.length; i++) if (!this.hitDone[i] && hits[i] >= this.a.t - 0.02) { next = hits[i]; break; }
    return { name: this.atk, red: !!spec.red, eta: next === null ? null : (next - this.a.t) / this.a.speed };
  }

  startAttack(name) {
    const G = this.G, spec = BOSS_ATK[name], d = dist2(this.pos, G.hero.pos);
    this.set('attack', name, { fade: 0.12 });
    // on Master his tempo varies from swing to swing, so the rhythm cannot be memorised
    this.a.speed = 1 + (Math.random() * 2 - 0.7) * T.speedVar * (this.phase === 2 ? 1 : 0.6);
    this.atk = name; this.last = name; this.hitDone = []; this.told = false; this.leaping = false; this.dashing = false; this.dragging = false;
    const adv = this.a.meta.clips[name].adv;
    if (adv && spec.reach) {
      const total = adv[adv.length - 1][0];
      this.a.motionScale = total > 0.2 ? Math.max(0.3, Math.min(1.5, (d - spec.reach) / total)) : 1;
    }
  }

  choose(d) {
    const p2 = this.phase === 2, opts = [];
    const add = (n, w) => { if (this.has(n) && n !== this.last) opts.push([n, w]); };
    if (d < 4.0) { add('Sweep', 3); add('Whirl', 2); if (p2) { add('Flurry', 3.5); add('Wave', 1); } add('Thrust', 1); }
    else if (d < 7.5) { add('Thrust', 3); add('Leap', 2); if (p2) { add('DashSlash', 2.5); add('Wave', 2.5); } }
    else { add('Leap', 3); if (p2) { add('DashSlash', 3); add('Wave', 2); } else add('walk', 3); }
    if (!opts.length) return 'Sweep';
    let r = Math.random() * opts.reduce((s, o) => s + o[1], 0);
    for (const [n, w] of opts) { r -= w; if (r <= 0) return n; }
    return opts[0][0];
  }

  addPosture(v) {
    if (this.busy || this.state === 'kneel' || this.state === 'break') return;
    this.posture = Math.min(100, this.posture + v); this.postT = T.postDelay;
    if (this.posture >= 100) this.breakPosture();
  }

  breakPosture() {
    this.set('break', 'Break', { fade: 0.08 });
    this.a.motionScale = 1; this.kneelT = 5.5; this.trail = false; this.chain = 0;
    this.G.onBossBreak();
  }

  /** A hero strike has reached him. */
  receive({ dmg, post, heavy, crit, kick, spirit, point, from }) {
    const G = this.G;
    if (this.busy) return 'ignored';
    const open = this.state === 'kneel' || this.state === 'break';
    if (this.state === 'guard') {
      if (kick) { this.chain = 0; post += 14; this.set('flinch', 'Flinch', { fade: 0.05 }); G.onGuardBreak(point); }      // a kick knocks his guard aside
      else if (!spirit && this.a.t < 0.45) { G.onBossGuard(point); return 'guard'; }
    }
    if (!open && ['idle', 'walk', 'flinch'].includes(this.state)) {
      this.chain++; this.chainT = 1.5;
      if (this.chain >= this.guardAt && this.has('Guard') && !crit && !kick && !spirit) {
        this.chain = 0; const gr = this.phase === 2 ? T.guardP2 : T.guardP1; this.guardAt = gr[0] + Math.floor(Math.random() * (gr[1] - gr[0] + 1));
        this.a.yaw = yawTo(this.pos, from);
        this.set('guard', 'Guard', { fade: 0.04 });
        G.onBossGuard(point);
        return 'guard';
      }
    }
    if (open) dmg *= 1.35;
    this.hp -= dmg; G.stats.dealt += dmg;
    G.onBossHurt(point, from, heavy, crit);
    if (this.hp <= 0) { this.die(); return 'hit'; }
    if (this.phase === 1 && this.hp <= this.maxHp * 0.5) this.pendingEnrage = true;
    if (!open) {
      const armored = this.state === 'attack' || this.state === 'guard' || this.state === 'rise';
      this.addPosture(post * (armored ? 0.7 : 1));
      if (this.state === 'kneel' || this.state === 'break') return 'hit';
      if (!armored && this.has('Flinch')) { this.set('flinch', 'Flinch', { fade: 0.05 }); this.a.yaw = turnTo(this.a.yaw, yawTo(this.pos, from), 0.5); }
    }
    return 'hit';
  }

  die() {
    this.hp = 0; this.trail = false;
    this.set('dying', 'Death', { fade: 0.15 });
    this.a.motionScale = 1;
    this.G.onBossDead();
  }

  enrage() {
    this.pendingEnrage = false; this.posture = 0;
    this.set('enrage', 'Enrage', { fade: 0.25 });
    this.G.onEnrageStart();
  }

  strike(i, point) {
    const G = this.G, spec = BOSS_ATK[this.atk];
    this.hitDone[i] = true;
    const res = G.hero.takeHit({ dmg: spec.dmg[Math.min(i, spec.dmg.length - 1)] * T.bossDmg, red: !!spec.red, knock: !!spec.knock[Math.min(i, spec.knock.length - 1)], cost: spec.cost || 30, point, from: this.pos });
    G.onBossStrike(res, point, spec);
    if (res === 'parried') this.addPosture((spec.post || 20) * T.parryPost);
    else if (res === 'blocked') this.addPosture(3);
    return res;
  }

  update(dt) {
    const G = this.G, a = this.a, hero = G.hero;
    this.stateT += dt;
    const toHero = yawTo(this.pos, hero.pos), d = dist2(this.pos, hero.pos), p2 = this.phase === 2;
    this.chainT -= dt; if (this.chainT <= 0) this.chain = 0;
    this.postT -= dt;
    if (this.postT <= 0 && !['kneel', 'break'].includes(this.state)) this.posture = Math.max(0, this.posture - T.postDecay * dt);
    const nextIdle = (t) => { this.set('idle', 'Idle', { fade: 0.2 }); this.think = t; this.trail = false; };

    switch (this.state) {
      case 'idle': case 'walk': {
        a.yaw = turnTo(a.yaw, toHero, (p2 ? 4.6 : 3.2) * dt);
        if (!hero.alive) { if (this.state !== 'idle') this.set('idle', 'Idle', { fade: 0.3 }); break; }
        if (this.pendingEnrage) { this.enrage(); break; }
        this.think -= dt;
        if (T.punishHeal && hero.state === 'heal' && d < 9) this.think = Math.min(this.think, 0.05);      // he does not let you drink in his face
        const far = d > 3.3;
        if (far && this.has('Walk')) {
          if (this.state !== 'walk') this.set('walk', 'Walk', { fade: 0.25 });
          const sp = p2 ? 2.7 : 1.9;
          a.speed = sp / 1.33;
          this.pos.x += Math.sin(a.yaw) * sp * dt; this.pos.z += Math.cos(a.yaw) * sp * dt;
          if (a.ev('stepL') || a.ev('stepR')) { G.audio.step(true); G.env.ripple(this.pos.x, this.pos.z, 1.2); G.shake(0.05); }
        } else if (this.state !== 'idle') this.set('idle', 'Idle', { fade: 0.25 });
        if (this.think <= 0) {
          const pick = this.choose(d);
          if (pick === 'walk') this.think = 0.6; else this.startAttack(pick);
        }
        break;
      }
      case 'attack': this.updateAttack(dt, toHero, d); break;
      case 'guard':
        if (a.done || a.t > 0.5) { if (this.has('Counter')) this.startAttack('Counter'); else nextIdle(0.4); }
        break;
      case 'flinch':
        if (a.done) nextIdle(Math.min(this.think, rndIn(p2 ? T.thinkP2 : T.thinkP1) * 0.6));
        break;
      case 'break':
        if (a.done) this.set('kneel', 'Kneel', { fade: 0.15 });
        break;
      case 'kneel':
        this.kneelT -= dt;
        if (this.kneelT <= 0) { this.posture = 0; this.set('rise', 'Rise', { fade: 0.15 }); }
        break;
      case 'rise':
        if (a.done) { if (this.pendingEnrage) this.enrage(); else nextIdle(rndIn(T.thinkP2)); }
        break;
      case 'executed':
        if (a.done) { this.posture = 0; if (this.pendingEnrage) this.enrage(); else nextIdle(0.7); G.onExecuteEnd(); }
        break;
      case 'enrage':
        if (a.ev('slam')) G.onEnrageSlam();
        if (a.ev('roar')) { this.phase = 2; this.setMood(1); G.onEnrageRoar(); }
        if (a.done) { this.phase = 2; nextIdle(0.5); G.onEnrageEnd(); }
        break;
      case 'dying':
        if (a.ev('knees')) { G.audio.thud(0.9); G.shake(0.3); G.env.ripple(this.pos.x, this.pos.z, 2); }
        if (a.done) this.state = 'dead';
        break;
      default: break;
    }

    a.update(dt);
    const r = Math.hypot(this.pos.x, this.pos.z), R = G.env.radius - 1.0;
    if (r > R) { this.pos.x *= R / r; this.pos.z *= R / r; }
    a.root.updateMatrixWorld(true);
    a.updateSprings(dt);
    this._b0.copy(this._b1); this._t0.copy(this._t1); this._s0.copy(this._s1);
    a.at('blade.base', this._b1); a.at('blade.tip', this._t1); a.at('butt', this._s1);

    this.moodNow += (this.mood - this.moodNow) * Math.min(1, dt * 1.5);
    this.eyeFlash = Math.max(0, this.eyeFlash - dt * 2.5);
    if (this.eye) {
      this.eye.emissive.setRGB(1, 0.62 - 0.52 * this.moodNow, 0.12 - 0.08 * this.moodNow).lerp(RED, Math.min(1, this.eyeFlash));
      this.eye.emissiveIntensity = (this.state === 'dead' ? 0.1 : 2.2 + 2.5 * this.moodNow + 5 * this.eyeFlash) * (this.state === 'dying' ? Math.max(0.05, 1 - a.t / 2.5) : 1);
    }
    if (this.edge) this.edge.emissiveIntensity = (this.state === 'dying' || this.state === 'dead') ? Math.max(0, this.edge.emissiveIntensity - dt * 2) : this.moodNow * 3.0 + this.eyeFlash * 2;
  }

  updateAttack(dt, toHero, d) {
    const G = this.G, a = this.a, hero = G.hero, spec = BOSS_ATK[this.atk], hits = a.hits(), t = a.t;
    const tell = a.evTime('tell');
    if (!this.told && (tell === null || t >= tell)) { this.told = true; this.eyeFlash = spec.red ? 1 : 0.35; G.onTelegraph(!!spec.red); }
    let nearHit = false, anyLeft = false, on = false;
    for (let i = 0; i < hits.length; i++) {
      if (t > hits[i] - 0.14 && t < hits[i] + 0.22) nearHit = true;
      if (t < hits[i]) anyLeft = true;
      if (t > hits[i] - 0.24 && t < hits[i] + 0.14) on = true;
    }
    this.trail = on;
    if (a.ev('tell') || hits.some((h) => a.prevT < h - 0.2 && t >= h - 0.2)) G.audio.whoosh(true);

    if (this.atk === 'Leap') {
      const tj = a.evTime('jump') ?? 0.6, tl = a.evTime('land') ?? hits[0];
      if (t < tj) a.yaw = turnTo(a.yaw, toHero, spec.track * dt);
      if (a.ev('jump')) {
        this.leaping = true; this.from.copy(this.pos);
        this.dir.set(Math.sin(toHero), 0, Math.cos(toHero));
        this.to.copy(hero.pos).addScaledVector(this.dir, -2.2);
        if (dist2(this.to, this.pos) < 0.5) this.to.copy(this.pos);
        a.yaw = toHero; G.audio.whoosh(true); G.env.ripple(this.pos.x, this.pos.z, 1.5);
      }
      if (this.leaping && t <= tl) {
        const k = Math.min(1, (t - tj) / Math.max(0.05, tl - tj - 0.04)), e = k * k * (3 - 2 * k);
        this.pos.x = this.from.x + (this.to.x - this.from.x) * e; this.pos.z = this.from.z + (this.to.z - this.from.z) * e;
      }
      this.trail = this.leaping && t <= tl + 0.1;
      if (a.ev('land') || (!this.hitDone[0] && t >= tl)) {
        this.leaping = false; this.hitDone[0] = true;
        const ip = this.to.copy(this.pos).add(a.fwd(this.dir).multiplyScalar(2.3));
        G.onSlam(ip);
        if (dist2(ip, hero.pos) < spec.aoe) { const res = hero.takeHit({ dmg: spec.dmg[0] * T.bossDmg, red: true, knock: true, point: ip.clone().setY(1), from: this.pos }); G.onBossStrike(res, ip.clone().setY(1), spec); }
      }
    } else if (this.atk === 'DashSlash') {
      const t0 = a.evTime('dash') ?? hits[0] - 0.1, t1 = a.evTime('dashEnd') ?? hits[0] + 0.15;
      if (t < t0) a.yaw = turnTo(a.yaw, toHero, spec.track * dt);
      if (a.ev('dash') || (!this.dashing && t >= t0 && t < t1)) {
        this.dashing = true; this.from.copy(this.pos); a.fwd(this.dir);
        let len = Math.max(6, Math.min(11, d + 3.5));
        this.to.copy(this.pos).addScaledVector(this.dir, len);
        const R = G.env.radius - 1.2, rr = Math.hypot(this.to.x, this.to.z);
        if (rr > R) { this.to.x *= R / rr; this.to.z *= R / rr; }
        this.ghostT = 0; G.audio.dash(); G.audio.whoosh(true);
      }
      if (this.dashing) {
        const k = Math.min(1, (t - t0) / Math.max(0.03, t1 - t0)), px = this.pos.x, pz = this.pos.z;
        this.pos.x = this.from.x + (this.to.x - this.from.x) * k; this.pos.z = this.from.z + (this.to.z - this.from.z) * k;
        this.ghostT -= dt;
        if (this.ghostT <= 0) { G.bossGhosts.spawn(0.4, 0.5); this.ghostT = 0.03; G.env.ripple(this.pos.x, this.pos.z, 1.5); }
        if (!this.hitDone[0]) {
          for (let i = 0; i <= 6; i++) {
            const x = px + (this.pos.x - px) * i / 6, z = pz + (this.pos.z - pz) * i / 6;
            if (Math.hypot(x - hero.pos.x, z - hero.pos.z) < 1.9) { this.strike(0, hero.pos.clone().setY(1.1)); break; }
          }
        }
        if (k >= 1) { this.dashing = false; this.hitDone[0] = true; }
      }
      this.trail = this.dashing || (t > t0 - 0.1 && t < t1 + 0.2);
    } else if (this.atk === 'Wave') {
      const tl = a.evTime('launch') ?? 0.9;
      if (t < tl - 0.1) a.yaw = turnTo(a.yaw, toHero, spec.track * dt);
      if (a.ev('drag')) this.dragging = true;
      if (this.dragging && t < tl) { G.fx.sparks(this._t1.clone().setY(0.08), 3, { color: 0xff9040, speed: 4, life: 0.35, up: 2 }); }
      this.trail = t > tl - 0.2 && t < tl + 0.15;
      if (a.ev('launch')) { this.dragging = false; this.hitDone[0] = true; G.onWaveLaunch(); }
    } else {
      // blade attacks: keep turning toward the hero between strikes, never during one
      if (!nearHit && anyLeft) a.yaw = turnTo(a.yaw, toHero, spec.track * dt);
      if (this.atk === 'Whirl') {
        const s0 = a.evTime('start') ?? hits[0] - 0.2, s1 = a.evTime('end') ?? hits[hits.length - 1] + 0.1;
        if (t > s0 && t < s1) { this.trail = true; if (d > 1.8) { this.pos.x += Math.sin(toHero) * 2.0 * dt; this.pos.z += Math.cos(toHero) * 2.0 * dt; } a.yaw = turnTo(a.yaw, toHero, 1.2 * dt); }
      }
      for (let i = 0; i < hits.length; i++) {
        if (this.hitDone[i]) continue;
        if (t > hits[i] + 0.07) { this.hitDone[i] = true; continue; }
        if (t < hits[i] - 0.09) continue;
        const p = bladeTouches(this._s0, this._t0, this._s1, this._t1, hero.pos, 0.55, 1.85, 0.15);      // the whole polearm, butt to tip
        if (p) { this.strike(i, p.clone()); if (this.state !== 'attack') return; }
      }
    }
    if (a.done) { this.set('idle', 'Idle', { fade: 0.2 }); this.trail = false; this.think = rndIn(this.phase === 2 ? T.thinkP2 : T.thinkP1); }
  }
}
const RED = new THREE.Color(1, 0.05, 0.02);
