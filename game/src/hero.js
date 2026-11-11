// The Wanderer: player-controlled swordsman.
// Two main weapons (sabre, greatsword) with their own combo graphs on light / heavy / kick, summoned arms that
// spend qi, a dash with i-frames, guard and timed parry. Qi pays for heavy moves, summons and blocked hits.
import * as THREE from 'three';
import { Actor, turnTo, yawTo, dist2, angDiff, bladeTouches } from './actor.js';
import { T } from './tuning.js';

const V3 = THREE.Vector3;
// dmg / post (posture damage) are per hit. qi = cost. gain = qi returned per landed hit.
export const MOVES = {
  A1: { dmg: [16], post: [3], gain: 5 },
  A2: { dmg: [16], post: [3], gain: 5 },
  A3: { dmg: [22], post: [4], gain: 5 },
  A4: { dmg: [34], post: [8], gain: 6, heavy: true },
  Heavy: { dmg: [46], post: [10], qi: 25, heavy: true },
  S_Twin: { dmg: [15, 21], post: [3, 5], gain: 4 },
  S_Rise: { dmg: [22, 34], post: [5, 9], qi: 15, heavy: true },
  S_DashCut: { dmg: [27], post: [6], gain: 6 },
  Kick: { dmg: [8], post: [9], kick: true, gain: 3 },
  G1: { dmg: [32], post: [8], gain: 7, heavy: true, armor: true },
  G2: { dmg: [36], post: [9], gain: 7, heavy: true, armor: true },
  G3: { dmg: [28, 50], post: [7, 14], gain: 6, heavy: true, armor: true, slam: [0, 1] },
  G_Heavy: { dmg: [86], post: [24], qi: 35, heavy: true, armor: true, slam: [1] },
  G_Launch: { dmg: [50], post: [12], qi: 15, heavy: true, armor: true },
  SA_Hammer: { dmg: [130], post: [34], qi: 50, heavy: true, armor: true, slam: [1], spirit: 'hammer' },
  SA_Daggers: { dmg: [30], post: [6], qi: 35, spirit: 'daggers' },
};
// what each button leads to: from neutral (start), out of a dash, and after each move
export const CHAIN = {
  sabre: {
    start: { L: 'A1', H: 'Heavy', K: 'Kick' }, dash: { L: 'S_DashCut', H: 'Heavy', K: 'Kick' },
    A1: { L: 'A2', H: 'S_Twin', K: 'Kick' }, A2: { L: 'A3', H: 'S_Rise', K: 'Kick' }, A3: { L: 'A4', H: 'Heavy', K: 'Kick' },
    S_Twin: { L: 'A3', H: 'S_Rise', K: 'Kick' }, S_DashCut: { L: 'A2', H: 'S_Twin', K: 'Kick' }, Kick: { L: 'A2', H: 'Heavy' },
  },
  great: {
    start: { L: 'G1', H: 'G_Heavy', K: 'Kick' }, dash: { L: 'G2', H: 'G_Launch', K: 'Kick' },
    G1: { L: 'G2', H: 'G_Launch', K: 'Kick' }, G2: { L: 'G3', H: 'G_Heavy', K: 'Kick' }, G_Launch: { L: 'G3', H: 'G_Heavy' }, Kick: { L: 'G2', H: 'G_Heavy' },
  },
};
export const WEAPONS = { sabre: 'Rainsplitter', great: 'Mountain-Cleaver' };
export const SPIRITS = [{ id: 'SA_Hammer', name: 'Thunder Maul' }, { id: 'SA_Daggers', name: 'Swallow Darts' }];
const RUN_SPEED = 4.6, DASH_T = 0.40, SWAP_REFILL = 10;
const BTN_ACTION = { L: 'light', H: 'heavy', K: 'kick' };
const toBoss0 = (h, boss) => yawTo(h.pos, boss.pos);

export class Hero {
  constructor(G, gltf, meta) {
    this.G = G;
    this.a = new Actor(gltf, meta, { springCfg: { stiff: 0.010, damp: 0.968, grav: 9 } });
    this.pos = this.a.pos;
    this.maxHp = 100; this.maxQi = 100;
    this.edge = this.a.mats.find((m) => m.name === 'h_blade_edge');
    if (this.edge) { this.edge.userData.noFlash = true; this.edge.emissive.setRGB(0.45, 0.75, 1.0); this.edge.emissiveIntensity = 0; }
    this.part = {};
    for (const n of ['sword', 'tassel', 'great', 'great_back', 'sword_hip', 'hammer']) this.part[n] = this.a.model.getObjectByName(n) || null;
    this.dagger = this.a.model.getObjectByName('dagger') || null;
    if (this.dagger) this.dagger.removeFromParent();
    this.hasGreat = !!this.part.great && this.has('G1');
    this.spirits = SPIRITS.filter((s) => this.has(s.id));
    this._b0 = new V3(); this._t0 = new V3(); this._b1 = new V3(); this._t1 = new V3();
    this.dashDir = new V3();
    this.weapon = 'sabre'; this.spiritIdx = 0;
    this.reset();
  }

  has(c) { return !!this.a.act[c]; }

  reset() {
    this.hp = this.maxHp; this.qi = this.maxQi; this.heals = T.heals;
    this.state = 'idle'; this.inv = 0; this.counter = 0; this.qiDelay = 0; this.dashCd = 0; this.swapCd = 0;
    this.flashGuard = 0; this.atkSerial = 0;
    this.buffer = null; this.bufferT = 0; this.hitDone = []; this.crit = false; this.weak = false; this.stateT = 0; this.summoned = null; this.noQiT = 0;
    this.a.play('Idle', { fade: 0 });
    this.a.resetSprings();
    this.applyWeapon();
  }

  get alive() { return this.state !== 'dead'; }
  get iframes() { return this.state === 'dash' && this.stateT >= T.iframe[0] && this.stateT <= T.iframe[1]; }
  get guarding() { return (this.G.input.block || this.flashGuard > 0) && ['idle', 'run', 'block', 'blockhit', 'parry'].includes(this.state); }
  get spirit() { return this.spirits[this.spiritIdx] || null; }

  applyWeapon() {
    const p = this.part, s = this.summoned === 'hammer';
    if (p.sword) p.sword.visible = this.weapon === 'sabre' && !s;
    if (p.tassel) p.tassel.visible = this.weapon === 'sabre' && !s;
    if (p.great) p.great.visible = this.weapon === 'great' && !s;
    if (p.great_back) p.great_back.visible = this.hasGreat && this.weapon === 'sabre';
    if (p.sword_hip) p.sword_hip.visible = this.weapon === 'great';
    if (p.hammer) p.hammer.visible = s;
    const g = this.weapon === 'great' && this.a.mark['great.tip'];
    this.tipMark = s && this.a.mark['hammer.head'] ? 'hammer.head' : g ? 'great.tip' : 'blade.tip';
    this.baseMark = g && !s ? 'great.base' : 'blade.base';
  }

  set(state, clip, opts) {
    if (this.summoned && state !== 'attack') { this.summoned = null; this.applyWeapon(); this.G.onVanish(); }
    this.state = state; this.stateT = 0;
    if (clip) this.a.play(clip, opts);
  }

  spend(v) { this.qi = Math.max(0, this.qi - v); this.qiDelay = 1.2; }
  gain(v) { this.qi = Math.min(this.maxQi, this.qi + v); }

  /** Next move for a button from a node of the combo graph (null if nothing follows). */
  next(btn, from) {
    const n = (CHAIN[this.weapon][from] || {})[btn];
    return n && this.has(n) ? n : null;
  }

  startAttack(name, opts = {}) {
    const G = this.G, boss = G.boss, spec = MOVES[name];
    this.set('attack', name, { fade: 0.07, at: opts.at || 0 });
    this.atk = name; this.hitDone = []; this.buffer = null; this.atkSerial++;
    this.crit = !spec.spirit && (this.counter > 0 || !!opts.crit);
    if (this.crit) this.counter = 0;
    this.weak = false;
    if (spec.qi && !this.crit) { if (this.qi >= spec.qi) this.spend(spec.qi); else { this.weak = true; this.spend(this.qi); } }
    const d = dist2(this.pos, boss.pos), adv = this.a.meta.clips[name].adv;
    const total = adv ? adv[adv.length - 1][0] - (this.a.advAt(opts.at || 0) || [0])[0] : 0;
    const stop = spec.kick ? 1.9 : this.weapon === 'great' || spec.spirit ? 2.7 : 2.25;
    this.a.motionScale = spec.spirit === 'daggers' ? 1 : total > 0.05 ? Math.max(0, Math.min(total > 1 ? 2.0 : 2.8, (d - stop) / total)) : 1;
    G.audio.cloth();
  }

  startSpirit() {
    const G = this.G, s = this.spirit;
    if (!s) return false;
    if (this.qi < MOVES[s.id].qi) {
      if (this.noQiT <= 0) { G.hud.popup('NOT ENOUGH QI', 'red'); this.noQiT = 1.0; }
      return false;
    }
    this.startAttack(s.id);
    return true;
  }

  startSwap() {
    if (!this.hasGreat) return false;
    if (this.has('Swap')) { this.set('swap', 'Swap', { fade: 0.06 }); this.swapped = false; } else this.doSwap();
    return true;
  }

  doSwap() {
    this.weapon = this.weapon === 'sabre' ? 'great' : 'sabre';
    this.applyWeapon();
    const refill = this.swapCd <= 0;
    if (refill) { this.qi = this.maxQi; this.swapCd = SWAP_REFILL; }
    this.G.onSwap(refill);
  }

  startDash(side = false) {
    const G = this.G, I = G.input;
    if (side) { this.a.left(this.dashDir); if (Math.random() < 0.5) this.dashDir.multiplyScalar(-1); }       // timed evade: slip past his flank
    else if (Math.hypot(I.mx, I.mz) > 0.2) this.dashDir.set(I.mx, 0, I.mz).normalize();
    else this.a.fwd(this.dashDir).multiplyScalar(-1);
    this.set('dash', 'Dash', { fade: 0.05, speed: 1.0 });
    this.dodged = false; this.ghostT = 0;
    G.audio.dash();
    G.env.ripple(this.pos.x, this.pos.z, 0.8);
  }

  /** Called by the boss when one of his strikes reaches the hero. */
  takeHit({ dmg, red = false, knock = false, cost = 30, point = null, from = null }) {
    const G = this.G;
    if (!this.alive || this.state === 'execute' || this.state === 'cine' || this.inv > 0 || G.god) {
      if (this.iframes) return this.perfectDodge();
      return 'ignored';
    }
    if (this.iframes) return this.perfectDodge();
    const facing = from ? Math.abs(angDiff(this.a.yaw, yawTo(this.pos, from))) < 1.9 : true;
    if (this.guarding && !red && facing) {
      if (G.time - G.input.blockAt <= T.parry || this.flashGuard > 0) {
        this.flashGuard = 0;
        this.set('parry', 'Parry', { fade: 0.04 });
        this.gain(18); this.counter = 1.4;
        G.stats.parries++;
        return 'parried';
      }
      const broke = this.qi < cost * T.blockCost;
      this.spend(cost * T.blockCost);
      this.hp -= dmg * T.chip; G.stats.taken += dmg * T.chip;
      if (broke) {
        this.qiDelay = 2.2;
        G.hud.popup('GUARD BROKEN', 'red');
        this.hurt(dmg * T.breakDmg, true, from);
        return 'broken';
      }
      this.set('blockhit', 'BlockHit', { fade: 0.03 });
      if (this.hp <= 0) this.die();
      return 'blocked';
    }
    // heavy weapons shrug off light blows mid-swing
    if (this.state === 'attack' && MOVES[this.atk].armor && !knock && !red) {
      this.hp -= dmg * 0.7; G.stats.taken += dmg * 0.7; this.inv = 0.25;
      if (this.hp <= 0) this.die();
      return 'armored';
    }
    this.hurt(dmg, knock || red, from);
    return 'hit';
  }

  perfectDodge() {
    if (this.dodged) return 'dodged';
    this.dodged = true; this.counter = 1.6; this.gain(20); this.G.stats.dodges++;
    this.G.onPerfectDodge();
    return 'dodged';
  }

  hurt(dmg, knock, from) {
    const G = this.G;
    this.hp -= dmg; G.stats.taken += dmg;
    this.inv = knock ? 1.0 : T.hitInv;
    if (from) this.a.yaw = yawTo(this.pos, from);
    if (this.hp <= 0) { this.die(); return; }
    this.set(knock ? 'knock' : 'hit', knock ? 'Knock' : 'Hit', { fade: 0.05 });
    this.a.motionScale = 1;
  }

  die() {
    this.hp = 0;
    this.set('dead', 'Death', { fade: 0.08 });
    this.G.onHeroDead();
  }

  update(dt) {
    const G = this.G, I = G.input, a = this.a, boss = G.boss;
    this.stateT += dt;
    this.inv = Math.max(0, this.inv - dt); this.counter = Math.max(0, this.counter - dt);
    this.dashCd = Math.max(0, this.dashCd - dt); this.swapCd = Math.max(0, this.swapCd - dt); this.noQiT -= dt;
    this.qiDelay -= dt;
    if (this.qiDelay <= 0 && !I.block) this.qi = Math.min(this.maxQi, this.qi + T.qiRegen * dt);
    const toBoss = yawTo(this.pos, boss.pos), d = dist2(this.pos, boss.pos);
    const stick = Math.hypot(I.mx, I.mz), moving = stick > 0.2;
    const wL = I.take('light'), wH = I.take('heavy'), wS = I.take('spirit'), wSwap = I.take('swapW');
    let wK = I.take('kick');
    this.flashGuard = Math.max(0, this.flashGuard - dt);
    // the kick button inside the closing ring answers the strike instead: parry a gold one, slip a red one
    if (wK && ['idle', 'run', 'block', 'blockhit', 'parry', 'attack', 'recoil', 'swap', 'dash'].includes(this.state)) {
      const ans = G.timedAnswer();
      if (ans === 'dodge') { wK = false; if (!this.iframes) this.startDash(true); }
      else if (ans === 'parry') { wK = false; this.flashGuard = T.circle + 0.05; this.a.yaw = toBoss0(this, boss); this.set('block', 'Block', { fade: 0.04 }); }
      if (ans) G.stats.timed = (G.stats.timed || 0) + 1;
    }
    const wantDash = I.take('dodge') && this.dashCd <= 0, wantHeal = I.take('heal'), wantExec = I.take('exec');
    if (I.take('swapS') && this.spirits.length > 1) { this.spiritIdx = (this.spiritIdx + 1) % this.spirits.length; G.onSpiritSwitch(); }
    const btn = wL ? 'L' : wH ? 'H' : wK ? 'K' : null;
    const free = () => { const e = a.evTime('free'); return e === null || a.t >= e; };
    const tryExec = () => { if (boss.canExecute(this)) { G.startExecute(); return true; } return false; };
    const counterMove = () => (this.weapon === 'great' ? (this.has('G_Launch') ? ['G_Launch', {}] : null) : ['Heavy', { at: 0.34 }]);
    const act = (from = 'start') => {             // actions available from a neutral state
      if ((wantExec || btn) && tryExec()) return true;
      if (wantDash) { this.startDash(); return true; }
      if (wS && this.startSpirit()) return true;
      if (wSwap && this.startSwap()) return true;
      if (btn) {
        const cm = this.counter > 0 && btn !== 'K' ? counterMove() : null;
        if (cm) { this.startAttack(cm[0], Object.assign({ crit: true }, cm[1])); return true; }
        const n = this.next(btn, from) || this.next(btn, 'start');
        if (n) { this.startAttack(n); return true; }
      }
      if (wantHeal && this.heals > 0 && this.hp < this.maxHp) { this.set('heal', 'Heal', { fade: 0.1 }); return true; }
      return false;
    };

    const st0 = this.state, serial0 = this.atkSerial;
    switch (this.state) {
      case 'idle': case 'run':
        if (act()) break;
        if (I.block) { this.set('block', 'Block', { fade: 0.07 }); break; }
        if (moving) {
          a.yaw = turnTo(a.yaw, Math.atan2(I.mx, I.mz), 14 * dt);
          this.pos.x += I.mx * RUN_SPEED * dt; this.pos.z += I.mz * RUN_SPEED * dt;      // analogue: a light tilt walks
          if (this.state !== 'run') this.set('run', 'Run', { fade: 0.12 });
          a.speed = Math.max(0.5, Math.min(1, stick));
          if (a.ev('stepL') || a.ev('stepR')) { G.env.ripple(this.pos.x, this.pos.z, 0.5); G.audio.step(); }
        } else {
          a.yaw = turnTo(a.yaw, toBoss, 9 * dt);
          if (this.state !== 'idle') this.set('idle', 'Idle', { fade: 0.16 });
        }
        break;
      case 'block':
        a.yaw = turnTo(a.yaw, toBoss, 12 * dt);
        if (act()) break;
        if (!I.block && this.flashGuard <= 0) this.set('idle', 'Idle', { fade: 0.12 });
        break;
      case 'blockhit': case 'parry':
        a.yaw = turnTo(a.yaw, toBoss, 12 * dt);
        if ((this.state === 'parry' ? free() : a.t > 0.2) && act()) break;
        if (a.done || (this.state === 'parry' && free() && !I.block && moving)) {
          if (I.block) this.set('block', 'Block', { fade: 0.08 }); else this.set('idle', 'Idle', { fade: 0.12 });
        }
        break;
      case 'attack': this.updateAttack(dt, { btn, wS, wSwap, wantDash, wantHeal, moving, toBoss, d, act, free }); break;
      case 'swap':
        a.yaw = turnTo(a.yaw, toBoss, 10 * dt);
        if (!this.swapped && (a.ev('swap') || a.done || (a.evTime('swap') === null && a.t > 0.15))) { this.doSwap(); this.swapped = true; }
        if (wantDash) { if (!this.swapped) this.doSwap(); this.startDash(); break; }
        if (this.swapped && free()) { if (act()) break; } else if (btn) I.keep(BTN_ACTION[btn]);
        if (a.done) this.set(I.block ? 'block' : 'idle', I.block ? 'Block' : 'Idle', { fade: 0.1 });
        break;
      case 'recoil':
        if (a.t > 0.13 && act()) break;
        if (a.done) this.set('idle', 'Idle', { fade: 0.1 });
        break;
      case 'dash': {
        const k = Math.min(1, this.stateT / DASH_T), sp = 12.5 * (1 - k) * (1 - k) + 1.2;
        this.pos.x += this.dashDir.x * sp * dt; this.pos.z += this.dashDir.z * sp * dt;
        a.yaw = turnTo(a.yaw, toBoss, 14 * dt);
        this.ghostT -= dt;
        if (this.ghostT <= 0 && this.stateT < 0.26) { G.heroGhosts.spawn(0.32, 0.5); this.ghostT = 0.045; }
        if (this.stateT > 0.2) {
          if ((btn || wS || wSwap) && act('dash')) { this.dashCd = 0.1; break; }
          if (wantDash && this.stateT > 0.32) { this.startDash(); break; }
        } else if (btn) I.keep(BTN_ACTION[btn]);
        if (this.stateT >= DASH_T) { this.dashCd = 0.08; if (I.block) this.set('block', 'Block', { fade: 0.1 }); else this.set(moving ? 'run' : 'idle', moving ? 'Run' : 'Idle', { fade: 0.12 }); }
        break;
      }
      case 'hit': case 'knock':
        if (free()) { if (act()) break; if (I.block) { this.set('block', 'Block', { fade: 0.1 }); break; } }
        if (a.done) this.set('idle', 'Idle', { fade: 0.12 });
        break;
      case 'heal':
        if (a.ev('glow')) { G.audio.heal(); }
        if (a.ev('done')) { this.heals--; this.hp = Math.min(this.maxHp, this.hp + T.healAmt); G.onHeal(); }
        if (wantDash) { this.startDash(); break; }
        if (free() && act()) break;
        if (a.done) this.set('idle', 'Idle', { fade: 0.12 });
        break;
      default: break;                           // execute, cine, dead: driven by the game
    }
    // a press that this state could not use yet stays buffered for the next frames
    if (this.state === st0 && this.atkSerial === serial0 && st0 !== 'attack') {
      if (btn) I.untake(BTN_ACTION[btn]);
      if (wS) I.untake('spirit');
      if (wSwap) I.untake('swapW');
    }
    if (this.state !== 'attack' && this.state !== 'execute') this.trail = false;

    a.update(dt);
    // keep inside the ring
    const r = Math.hypot(this.pos.x, this.pos.z), R = G.env.radius - 0.5;
    if (r > R) { this.pos.x *= R / r; this.pos.z *= R / r; }
    a.root.updateMatrixWorld(true);
    a.updateSprings(dt);
    this._b0.copy(this._b1); this._t0.copy(this._t1);
    a.at(this.baseMark, this._b1); a.at(this.tipMark, this._t1);
    if (this.edge) {
      const want = this.counter > 0 ? 3.2 : (this.state === 'execute' ? 2.0 : this.state === 'attack' && MOVES[this.atk].qi && !this.weak ? 1.6 : 0);
      this.edge.emissiveIntensity += (want - this.edge.emissiveIntensity) * Math.min(1, dt * 12);
    }
  }

  updateAttack(dt, { btn, wS, wSwap, wantDash, wantHeal, moving, toBoss, d, act, free }) {
    const G = this.G, I = G.input, a = this.a, boss = G.boss, spec = MOVES[this.atk], hits = a.hits(), t = a.t;
    const combo = a.evTime('combo'), lastHit = hits.length ? hits[hits.length - 1] : 0;
    if (!hits.length || t < lastHit) a.yaw = turnTo(a.yaw, toBoss, (hits.some((h) => Math.abs(t - h) < 0.08) ? 2 : 10) * dt);
    if (btn) { this.buffer = btn; this.bufferT = 0.45; }
    this.bufferT -= dt;
    for (const s of ['swing', 'swing2', 'swing3']) if (a.ev(s)) G.audio.whoosh(!!spec.heavy);
    if (a.ev('charge')) G.audio.cloth();
    // summoned arms appear and vanish on the clip's cues
    if (spec.spirit) {
      if (a.ev('summon')) { this.summoned = spec.spirit; this.applyWeapon(); G.onSummon(spec.spirit); }
      if (a.ev('vanish')) { this.summoned = null; this.applyWeapon(); G.onVanish(); }
      for (let i = 1; i <= 3; i++) if (a.ev('throw' + i)) G.throwDagger(i - 2, spec);
    }
    this.trail = hits.some((h) => t > h - 0.16 && t < h + 0.12);
    const mult = (this.crit ? 1.6 : 1) * (this.weak ? 0.55 : 1), pm = (this.crit ? 2 : 1) * (this.weak ? 0.5 : 1);
    for (let i = 0; i < hits.length; i++) {
      if (this.hitDone[i] || t < hits[i] - 0.07) continue;
      if (t > hits[i] + 0.08) { this.hitDone[i] = true; continue; }
      let p = null;
      const slam = spec.slam && spec.slam[Math.min(i, spec.slam.length - 1)];
      if (spec.kick) {
        if (t >= hits[i]) { this.hitDone[i] = true; if (d < boss.radius + 1.9) p = boss.a.at('chest').clone().lerp(a.at('chest'), 0.4).setY(1.2); }
      } else if (slam) {
        if (t >= hits[i]) {
          this.hitDone[i] = true;
          const ip = a.fwd().multiplyScalar(spec.spirit ? 2.1 : 1.9).add(this.pos);
          G.onHeroSlam(ip, !!spec.spirit || this.atk === 'G_Heavy');
          if (dist2(ip, boss.pos) < boss.radius + 1.9) p = boss.a.at('chest').clone().setY(1.3);
        }
      } else {
        p = bladeTouches(this._b0, this._t0, this._b1, this._t1, boss.pos, boss.radius + 0.35, 2.6, 0.35);
        if (p) { p = p.clone(); this.hitDone[i] = true; }
      }
      if (p) {
        const k = Math.min(i, spec.dmg.length - 1);
        const res = boss.receive({ dmg: spec.dmg[k] * mult, post: spec.post[k] * pm, heavy: !!spec.heavy, crit: this.crit, kick: !!spec.kick, spirit: !!spec.spirit, point: p, from: this.pos });
        if (res === 'hit' && spec.gain) this.gain(spec.gain);
        if (res === 'guard') { this.set('recoil', 'BlockHit', { fade: 0.03 }); return; }
      }
    }
    if (wantDash) { this.startDash(); return; }
    if (combo !== null && t >= combo) {
      if (wSwap && this.startSwap()) return;
      if (wS && this.startSpirit()) return;
      if (this.buffer && this.bufferT > 0) {
        if (boss.canExecute(this)) { G.startExecute(); return; }
        const nx = this.next(this.buffer, this.atk);
        if (nx) { this.startAttack(nx); return; }
      }
    } else { if (wS) I.keep('spirit'); if (wSwap) I.keep('swapW'); }
    if (free()) {
      if (I.block) { this.set('block', 'Block', { fade: 0.1 }); return; }
      // a held stick only walks out of a swing late, so combos still chain while moving (pads and touch keep the stick tilted)
      if (moving && t > (a.evTime('free') || 0) + 0.17 && !(this.buffer && this.bufferT > 0)) { this.set('run', 'Run', { fade: 0.14 }); return; }
      if (this.buffer && this.bufferT > 0 && !this.next(this.buffer, this.atk)) {      // chain exhausted: start over
        const n = this.next(this.buffer, 'start');
        if (n && t > (a.evTime('free') || 0) + 0.04) { this.startAttack(n); return; }
      }
      if (wantHeal && act()) return;
    }
    if (a.done) this.set('idle', 'Idle', { fade: 0.1 });
  }
}
