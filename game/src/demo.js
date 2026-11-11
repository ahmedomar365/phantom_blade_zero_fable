// Showcase: the game plays itself like a practised player, one feature at a time, through the real input layer
// (it presses the same actions a pad would), with captions and cut-together camera angles.
import * as THREE from 'three';
import { dist2 } from './actor.js';
import { T } from './tuning.js';

const V3 = THREE.Vector3;
const now = () => performance.now() / 1000;

export class Demo {
  constructor(G) {
    this.G = G; this.i = -1; this.t = 0; this.q = []; this.fedSerial = -1; this.fedAt = 0; this.defend = 'auto'; this.bossFloor = 0.56;
    this.rig = 0; this.rigT = 0; this.side = 1; this.circleAt = 0; this.flag = {};
    this.steps = this.script();
  }

  // ---------------------------------------------------------------- helpers
  get h() { return this.G.hero; }
  get b() { return this.G.boss; }
  get I() { return this.G.input; }
  get d() { return dist2(this.h.pos, this.b.pos); }
  get neutral() { return ['idle', 'run', 'block'].includes(this.h.state); }
  g(a) { return `<kbd>${this.I.glyph(a)}</kbd>`; }
  toBoss() { return new V3().subVectors(this.b.pos, this.h.pos).setY(0).normalize(); }
  approach(dist = 2.7) { const to = this.toBoss(); if (this.d > dist) { this.I.mx = to.x; this.I.mz = to.z; return false; } return true; }
  retreat(dist = 6) { const to = this.toBoss(); if (this.d < dist) { this.I.mx = -to.x; this.I.mz = -to.z; return false; } return true; }
  /** Feed a button string ("LLH") into the combo windows, one press per move. */
  feed() {
    const h = this.h, a = h.a;
    if (!this.q.length) return true;
    const t = now();
    if (h.state === 'attack') {
      const c = a.evTime('combo');
      if (c !== null && a.t >= c - 0.14 && this.fedSerial !== h.atkSerial) { this.press(this.q.shift()); this.fedSerial = h.atkSerial; this.fedAt = t; }
    } else if ((this.neutral || h.state === 'dash') && t - this.fedAt > 0.3 && this.approach(h.weapon === 'great' ? 3.0 : 2.6)) {
      this.press(this.q.shift()); this.fedSerial = h.atkSerial; this.fedAt = t;
    }
    return false;
  }
  press(k) { this.I.press({ L: 'light', H: 'heavy', K: 'kick', S: 'spirit', W: 'swapW', A: 'swapS', D: 'dodge', X: 'exec', F: 'heal' }[k]); }
  /** Make the boss use one attack as soon as he is free and in range. */
  force(name, range = 4.5) {
    const b = this.b;
    if ((b.state === 'idle' || b.state === 'walk') && !b.pendingEnrage && this.d < range && b.has(name)) { b.startAttack(name); return true; }
    return false;
  }
  attacking(name) { return this.b.state === 'attack' && (!name || this.b.atk === name); }

  /** Answer whatever he throws, in the way this step is showing off. */
  guard() {
    const G = this.G, I = this.I, h = this.h, th = G.threat(), t = now(), to = this.toBoss();      // eslint-disable-line no-unused-vars
    if (!th) return;
    const mode = this.defend === 'auto' ? (th.red ? 'dodge' : 'parry') : this.defend;
    if (mode === 'none') return;
    if (mode === 'circle') { if (th.eta < Math.min(0.24, T.circle - 0.03) && t - this.circleAt > 0.5) { I.press('kick'); this.circleAt = t; } return; }
    if (th.red || mode === 'dodge') {
      if (th.eta < Math.min(0.17, T.iframe[1] - 0.05) && h.state !== 'dash') { I.mx = to.z * this.side; I.mz = -to.x * this.side; I.press('dodge'); }
      else if (th.name === 'Whirl' && this.d < 5.5 && th.eta > 0.3) { I.mx = -to.x; I.mz = -to.z; }
      return;
    }
    if (th.eta < 0.55) { I.block = true; if (th.eta < Math.min(0.115, T.parry - 0.03) && t - I.blockAt > 0.2) I.blockAt = t; }
  }

  // ---------------------------------------------------------------- the script
  script() {
    const S = (cap, sub, o) => Object.assign({ cap, sub, max: 14, hold: 0.6 }, o);
    return [
      S('Light combo', () => `${this.g('light')} ${this.g('light')} ${this.g('light')} ${this.g('light')}`,
        { start: () => { this.q = ['L', 'L', 'L', 'L']; this.b.guardAt = 99; }, tick: () => this.feed() && this.neutral }),
      S('Parry', () => `tap ${this.g('block')} as the gold strike lands · then ${this.g('light')} to counter`,
        { start: () => { this.defend = 'parry'; this.flag = {}; },
          tick: () => {
            if (!this.flag.on) { this.approach(3.2); if (this.force('Sweep')) this.flag.on = true; return false; }
            if (this.attacking('Sweep')) return false;
            if (!this.flag.c && this.h.counter > 0) { this.press('L'); this.flag.c = true; }
            return this.neutral && this.t > 3;
          } }),
      S('Kick breaks his guard', () => `${this.g('light')} ${this.g('light')} · he guards · ${this.g('kick')}`,
        { start: () => { this.q = ['L', 'L', 'L']; this.b.guardAt = 2; this.b.chain = 0; this.flag = {}; },
          tick: () => {
            if (this.b.state === 'guard' && !this.flag.k) { this.q = []; this.press('K'); this.flag.k = true; this.flag.t = this.t; }
            if (!this.flag.k) { this.feed(); return false; }
            if (!this.flag.f && this.t > this.flag.t + 0.35) { this.b.guardAt = 99; this.q = ['L', 'H']; this.flag.f = true; }
            return this.flag.f && this.feed() && this.neutral;
          } }),
      S('Heavy chains spend qi', () => `${this.g('light')} ${this.g('heavy')} twin cut · ${this.g('heavy')} rising cut`,
        { start: () => { this.q = ['L', 'H', 'H']; this.b.guardAt = 99; }, tick: () => this.feed() && this.neutral }),
      S('Dash attack', () => `${this.g('dodge')} then ${this.g('light')}: a running draw-cut`,
        { start: () => { this.flag = {}; }, max: 9,
          tick: () => {
            const h = this.h, to = this.toBoss();
            if (!this.flag.r) { if (this.retreat(5.2)) this.flag.r = true; return false; }
            if (!this.flag.d) { if (this.neutral) { this.I.mx = to.x; this.I.mz = to.z; this.press('D'); this.flag.d = true; } return false; }
            if (h.state === 'dash') { this.I.mx = to.x; this.I.mz = to.z; if (!this.flag.c && h.stateT > 0.21) { this.press('L'); this.flag.c = true; } return false; }
            return this.neutral;
          } }),
      S('Perfect dodge', () => `${this.g('dodge')} through a red strike slows time · ${this.g('light')} out of the dash`,
        { start: () => { this.defend = 'dodge'; this.flag = {}; },
          tick: () => {
            if (!this.flag.on) { if (this.retreat(4.5) && this.force('Leap', 9)) this.flag.on = true; return false; }
            if (this.h.state === 'dash' && !this.flag.c && this.h.stateT > 0.21) { this.press('L'); this.flag.c = true; }
            return !this.attacking() && this.neutral && this.t > 3.5;
          } }),
      S('Timed answer', () => `${this.g('kick')} inside the closing ring parries gold and slips red`,
        { start: () => { this.defend = 'circle'; this.flag = {}; }, max: 16,
          tick: () => {
            if (!this.flag.a) { this.approach(3.6); if (this.force('Thrust', 5.5)) this.flag.a = true; return false; }
            if (this.attacking('Thrust')) return false;
            if (!this.flag.c && this.h.counter > 0) { this.press('L'); this.flag.c = true; return false; }
            if (!this.flag.b) { if (this.neutral && this.force('Whirl', 5)) this.flag.b = true; else this.approach(3.4); return false; }
            return !this.attacking() && this.neutral;
          } }),
      S('Switch weapon', () => `${this.g('swapW')} Mountain-Cleaver · refills qi · ${this.g('light')} ${this.g('light')} ${this.g('light')}`,
        { start: () => { this.defend = 'auto'; this.flag = {}; this.q = []; }, max: 16,
          tick: () => {
            if (!this.flag.s) { if (this.neutral) { this.h.swapCd = 0; if (this.h.weapon !== 'great') this.press('W'); this.flag.s = true; this.flag.t = this.t; } return false; }
            if (!this.flag.q && this.t > this.flag.t + 0.6) { this.q = ['L', 'L', 'L']; this.flag.q = true; }
            if (!this.flag.q) return false;
            if (!this.feed()) return false;
            if (!this.flag.h && this.neutral) { this.q = ['H']; this.flag.h = true; return false; }
            return this.flag.h && this.neutral;
          } }),
      S('Summoned arms', () => `${this.g('spirit')} Thunder Maul · ${this.g('swapS')} then ${this.g('spirit')} Swallow Darts`,
        { start: () => { this.flag = {}; this.q = []; }, max: 16,
          tick: () => {
            const h = this.h;
            if (!this.flag.a) { if (this.neutral && this.approach(3.0)) { h.qi = h.maxQi; this.press('S'); this.flag.a = true; this.flag.t = this.t; } return false; }
            if (this.t < this.flag.t + 1.9 || h.state === 'attack') return false;
            if (!this.flag.sw) { if (h.spirits.length > 1) this.press('A'); this.flag.sw = true; this.flag.t = this.t; return false; }
            if (!this.flag.b) { if (this.retreat(6.5) || this.t > this.flag.t + 2.2) { h.qi = h.maxQi; this.press('S'); this.flag.b = true; this.flag.t = this.t; } return false; }
            return this.t > this.flag.t + 1.6 && this.neutral;
          } }),
      S('Break his posture, then finish', () => `parries fill the gold bar · ${this.g('exec')}`,
        { breaks: true, start: () => { this.defend = 'parry'; this.flag = {}; if (this.h.weapon !== 'sabre') { this.h.swapCd = 0; this.press('W'); } this.b.posture = Math.max(this.b.posture, 74); this.b.postT = 30; }, max: 22,
          tick: () => {
            const b = this.b, h = this.h;
            if (h.state === 'execute') { this.flag.x = true; return false; }
            if (this.flag.x) return this.neutral;
            if (b.canExecute(h)) { this.press('X'); return false; }
            if (b.state === 'kneel' || b.state === 'break') { this.approach(2.4); return false; }
            b.postT = 30;
            this.approach(3.2); this.force('Sweep');
            return false;
          } }),
      S('Focus', () => `${this.g('heal')} restores health, three uses`,
        { start: () => { this.flag = {}; this.h.hp = Math.min(this.h.hp, 48); }, max: 8,
          tick: () => { if (!this.flag.a) { if (this.neutral) { this.press('F'); this.flag.a = true; this.flag.t = this.t; } return false; } return this.t > this.flag.t + 1.3; } }),
      S('Phase two', () => 'the Marshal\'s wrath: faster, with a flurry, a dash-slash and a wave of fire',
        { start: () => { this.defend = 'auto'; this.flag = {}; this.bossFloor = 0.2; const b = this.b; b.hp = Math.min(b.hp, b.maxHp * 0.5); b.pendingEnrage = true; }, max: 40, free: true, breaks: true,
          tick: () => {
            const b = this.b, h = this.h;
            if (b.phase !== 2 || b.state === 'enrage') { if (this.d < 6.5) this.retreat(7); return false; }
            if (!this.flag.t0) this.flag.t0 = this.t;
            this.G.autoFight(1);
            return this.t > this.flag.t0 + 26 && !this.attacking() && h.state !== 'execute';
          } }),
      S('The final blow', () => `${this.g('exec')}`,
        { start: () => { this.defend = 'auto'; this.flag = {}; this.bossFloor = 0; const b = this.b; b.hp = Math.min(b.hp, b.maxHp * 0.05); }, max: 30, free: true, hold: 0, breaks: true,
          tick: () => {
            const b = this.b, h = this.h;
            if (this.G.state !== 'fight') return true;
            if (h.state === 'execute') return false;
            if (!this.attacking() && !b.busy && !this.flag.p) { b.addPosture(100); this.flag.p = true; }
            this.G.autoFight(1);
            return false;
          } }),
    ];
  }

  // ---------------------------------------------------------------- per frame (replaces the player's input)
  update(dt) {
    const G = this.G, I = this.I, h = this.h, b = this.b;
    I.mx = 0; I.mz = 0; I.block = false;
    if (G.state !== 'fight') { if (G.state !== 'intro') G.hud.caption(null); return; }
    if (!h.alive) return;
    let s = this.steps[this.i];
    if (!s) { this.next(); s = this.steps[this.i]; if (!s) return; }
    this.t += dt;
    if (!s.free) b.think = Math.max(b.think, 2);                 // he waits for his cue
    if (b.state !== 'dying' && b.state !== 'dead') { h.hp = Math.max(h.hp, 30); b.hp = Math.max(b.hp, b.maxHp * this.bossFloor); }
    if (this.bossFloor > 0.5) b.pendingEnrage = false;          // phase two waits for its cue
    if (!s.breaks && !['kneel', 'break'].includes(b.state)) b.posture = Math.min(b.posture, 58);
    if (!s.free) this.guard();
    const done = s.tick() || this.t > s.max;
    if (done) { this.doneT = (this.doneT || 0) + dt; if (this.doneT >= s.hold) this.next(); } else this.doneT = 0;
  }

  next() {
    this.i++; this.t = 0; this.doneT = 0; this.q = [];
    const s = this.steps[this.i];
    if (!s) { this.G.hud.caption(null); return; }
    this.side = -this.side;
    this.G.hud.caption(s.cap, s.sub());
    if (s.start) s.start();
    this.cut();
  }

  // ---------------------------------------------------------------- camera: a handful of rigs, hard cuts between them
  cut() { this.rig = (this.rig + 1 + Math.floor(Math.random() * 2)) % 5; this.rigT = 0; this.snap = true; }

  camera(real, camPos, camLook) {
    const h = this.h, b = this.b, d = this.d;
    this.rigT += real;
    if (this.rigT > 5.5 && this.G.scale > 0.9 && h.state !== 'execute') this.cut();
    const dir = new V3(h.pos.x - b.pos.x, 0, h.pos.z - b.pos.z);
    if (dir.lengthSq() < 0.2) dir.set(0, 0, 1);
    dir.normalize();
    const s = new V3(dir.z, 0, -dir.x), mid = new V3().addVectors(h.pos, b.pos).multiplyScalar(0.5);
    const want = new V3(), look = new V3();
    let fov = 46;
    const sgn = (p) => (Math.hypot(p.x + s.x * 6, p.z + s.z * 6) < Math.hypot(p.x - s.x * 6, p.z - s.z * 6) ? 1 : -1);   // stay on the roomier side
    switch (this.rig) {
      case 0: want.copy(h.pos).addScaledVector(dir, 4.0 + d * 0.2).addScaledVector(s, 1.3).setY(2.5 + d * 0.07); look.copy(mid).setY(1.35); fov = 50; break;
      case 1: { const k = sgn(mid); want.copy(mid).addScaledVector(s, k * (5.4 + d * 0.35)).setY(0.9); look.copy(mid).setY(1.45); fov = 38; break; }
      case 2: { const k = sgn(b.pos); want.copy(b.pos).addScaledVector(dir, -3.6).addScaledVector(s, k * 3.4).setY(3.3); look.copy(mid).setY(1.1); fov = 46; break; }
      case 3: { const k = sgn(mid); want.copy(mid).addScaledVector(s, k * 4.2).addScaledVector(dir, 4.6 + d * 0.3).setY(5.2); look.copy(mid).setY(0.9); fov = 40; break; }
      default: want.copy(h.pos).addScaledVector(dir, 2.7).addScaledVector(s, -1.25).setY(0.85); look.copy(b.pos).setY(1.9); fov = 46;
    }
    const R = 14.2, r = Math.hypot(want.x, want.z);
    if (r > R) { want.x *= R / r; want.z *= R / r; want.y += (r - R) * 0.3; }
    if (this.snap) { camPos.copy(want); camLook.copy(look); this.snap = false; }
    else { camPos.lerp(want, 1 - Math.exp(-real * 3.2)); camLook.lerp(look, 1 - Math.exp(-real * 6)); }
    return fov;
  }
}
