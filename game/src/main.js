// Vermilion Gate: a third-person sword duel against Marshal Yan.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { Env } from './env.js';
import { Hud } from './hud.js';
import { Audio } from './audio.js';
import { FX, Trail, Ghosts, Wave, Daggers, spiritMaterial } from './fx.js';
import { Input } from './input.js';
import { Hero, MOVES, WEAPONS } from './hero.js';
import { Demo } from './demo.js';
import { T, DIFFS, setDiff } from './tuning.js';
import { Boss } from './boss.js';
import { dist2, yawTo, turnTo } from './actor.js';

const V3 = THREE.Vector3;
const params = new URLSearchParams(location.search);
const num = (k, d) => (params.has(k) ? Number(params.get(k)) : d);
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const sm = (t) => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
const now = () => performance.now() / 1000;

class Game {
  constructor() {
    setDiff(params.get('diff') || localStorage.getItem('vg-diff') || 'master');
    this.hud = new Hud(); this.audio = new Audio();
    this.q = num('q', 2); this.god = params.has('god'); this.auto = params.has('auto'); this.botSkill = num('bot', 0.75);
    this.state = 'load'; this.time = now(); this.gt = 0; this.stopT = 0; this.slowT = 0; this.slowScale = 1; this.scale = 1;
    this.trauma = 0; this.camPos = new V3(0, 2.4, 12); this.camLook = new V3(0, 1.6, 0); this.camFov = 50; this.camDir = new V3(0, 0, 1);
    this.cine = null; this.seq = []; this.phaseK = 0; this.phaseTarget = 0; this.danger = 0; this.bars = 0;
    this.stats = { parries: 0, dodges: 0, taken: 0, dealt: 0, t0: 0 };
    this.fpsAvg = 60;
  }

  async init() {
    const hud = this.hud;
    hud.overlay({ tag: 'Loading', bar: true });
    this.env = new Env(document.getElementById('c'), { quality: this.q });
    const loader = new GLTFLoader();
    let pe = 0, pa = 0;
    const prog = () => hud.progress(pe * 0.6 + pa * 0.4);
    const j = (u) => fetch(u).then((r) => r.json());
    const [, hg, hm, bg, bm] = await Promise.all([
      this.env.load((p) => { pe = p; prog(); }),
      loader.loadAsync('/assets/hero.glb').then((g) => { pa += 0.5; prog(); return g; }), j('/assets/hero_meta.json'),
      loader.loadAsync('/assets/boss.glb').then((g) => { pa += 0.5; prog(); return g; }), j('/assets/boss_meta.json'),
    ]);
    const scene = this.env.scene;
    this.input = new Input({ onAny: () => this.anyKey(), onDevice: () => this.refreshKeys() });
    if (['ps', 'xbox', 'kbm'].includes(params.get('glyphs'))) this.input.setDevice(params.get('glyphs'));          // force button hints: glyphs=ps | xbox | kbm
    this.hero = new Hero(this, hg, hm); this.boss = new Boss(this, bg, bm);
    scene.add(this.hero.a.root, this.boss.a.root);
    this.fx = new FX(scene);
    this.heroTrail = new Trail(scene, 0xbfe4ff, 96, 0.2);
    this.bossTrail = new Trail(scene, 0xffe2b0, 150, 0.26);
    this.heroGhosts = new Ghosts(scene, this.hero.a, 5, 0x7fc8ff);
    this.bossGhosts = new Ghosts(scene, this.boss.a, 6, 0xff5030);
    this.wave = new Wave(scene);
    this.spiritMat = spiritMaterial();
    if (this.hero.part.hammer) this.hero.part.hammer.traverse((o) => { if (o.isMesh) { o.material = this.spiritMat; o.castShadow = false; } });
    this.daggers = new Daggers(scene, this.hero.dagger);
    this.spiritLight = new THREE.PointLight(0x6fd0ff, 0, 8, 1.8);
    scene.add(this.spiritLight);
    this.focus = new V3();
    this.place();
    this.env.camera.fov = 50;
    addEventListener('resize', () => this.env.resize());
    this.last = now();
    requestAnimationFrame(() => this.frame());
    // warm up shaders with everything visible once
    this.env.update(0.016, this.focus); this.env.render();
    this.state = 'title';
    this.showTitle();
    window.gameReady = true;
    if (params.has('demo')) { this.demoMode = true; this.begin(); } else if (this.auto || params.has('skip')) this.begin();
  }

  /** Overlay with an optional button that Cross / A / Enter also presses. */
  menu(opts) { const on = opts.show !== false; this.menuGo = on ? (opts.onGo || null) : null; this.menuGo2 = on ? (opts.onGo2 || null) : null; this.hud.overlay(opts); }

  controls() {
    const g = (a) => this.input.glyph(a);
    return [[g('move'), 'Move'], [g('light'), 'Light attack'], [g('heavy'), 'Heavy attack (qi)'], [g('kick'), 'Kick: breaks his guard'],
      [g('block'), 'Guard · tap to parry'], [g('dodge'), 'Dodge'], [g('spirit'), 'Summoned arm (qi)'], [g('heal'), 'Focus (heal)'],
      [g('swapW'), 'Switch weapon'], [g('swapS'), 'Switch summoned arm'], [g('exec'), 'Finisher'], [g('pause'), 'Pause']];
  }

  showTitle() {
    this.overlayKind = 'title';
    this.menu({
      tag: `Difficulty: ${T.label}  ·  ${this.input.glyph('kick')} to change`, body: 'Marshal Yan has held the Vermilion Gate for thirty winters. No one has passed.<br>Read his blade: <span style="color:#ffe2a0">gold glints can be parried</span>, <span style="color:#ff7a5a">red glints must be dodged</span>. Break his posture, then finish it.',
      keys: this.controls(), go: `Draw your sword  (${this.input.glyph('confirm')})`, onGo: () => { this.demoMode = false; this.begin(); },
      go2: `Watch the showcase  (${this.input.glyph('heavy')})`, onGo2: () => { this.demoMode = true; this.begin(); },
    });
  }

  togglePause() {
    if (this.state !== 'fight' && !this.paused) return;
    this.paused = !this.paused;
    if (this.audio.ctx) this.audio.ctx[this.paused ? 'suspend' : 'resume']();
    if (this.paused) { this.overlayKind = 'pause'; this.menu({ han: '止', title: 'Paused', tag: 'Controls', keys: this.controls(), go: `Resume  (${this.input.glyph('confirm')})`, onGo: () => this.togglePause() }); }
    else { this.overlayKind = null; this.menu({ show: false }); this.input.clear(); this.last = now(); }
  }

  /** The hint panel and menus follow whichever device was used last. */
  refreshKeys() {
    if (!this.input) return;
    const g = (a) => this.input.glyph(a);
    this.hud.keys([[['Move', g('move')]], [['Light', g('light')], ['Heavy', g('heavy')], ['Kick', g('kick')]], [['Guard / parry', g('block')], ['Dodge', g('dodge')]],
      [['Summon', g('spirit')], ['Heal', g('heal')]], [['Weapon', g('swapW')], ['Arm', g('swapS')]]]);
    if (this.overlayKind === 'title' && this.state === 'title') this.showTitle();
    if (this.overlayKind === 'pause' && this.paused) { this.paused = false; this.togglePause(); }
  }

  place() {
    const h = this.hero, b = this.boss;
    h.pos.set(0, 0, 6.5); h.a.yaw = Math.PI; b.pos.set(0, 0, -5.5); b.a.yaw = 0;
    h.a.root.rotation.y = h.a.yaw; b.a.root.rotation.y = b.a.yaw;
    h.a.resetSprings(); b.a.resetSprings();
  }

  anyKey() {
    if (this.state === 'intro' && this.introT > 1.2) this.skipIntro = true;
    if (this.audio.ctx && this.audio.ctx.state === 'suspended' && !this.paused) this.audio.ctx.resume();
  }

  begin(retry = false) {
    const phase = retry && this.reached2 && T.retryP2 ? 2 : num('phase', 1);
    if (!phase || phase === 1) this.reached2 = false;
    this.audio.start();
    this.overlayKind = null; this.menu({ show: false }); this.input.clear(); this.camYaw = 0; this.camIdle = 0;
    this.hero.reset(); this.boss.reset(phase); this.place();
    if (params.has('hp')) this.boss.hp = this.boss.maxHp * num('hp', 1);
    this.demo = this.demoMode ? new Demo(this) : null;
    this.hud.demoTag(!!this.demo); this.hud.caption(null);
    this.phaseTarget = phase === 2 ? 1 : 0; this.phaseK = this.phaseTarget;
    this.stats = { parries: 0, dodges: 0, taken: 0, dealt: 0, t0: now() };
    this.seq = []; this.cine = null; this.wave.active = false; this.wave.mesh.visible = false;
    this.stopT = 0; this.slowT = 0;
    if ((retry && !this.demo) || params.has('skip') || this.auto) this.startFight();
    else this.startIntro();
  }

  // ------------------------------------------------------------------ flow
  after(t, fn) { this.seq.push({ t: this.gt + t, fn }); }

  startIntro() {
    const h = this.hero, b = this.boss, hud = this.hud;
    this.state = 'intro'; this.introT = 0; this.skipIntro = false; this.bars = 1;
    hud.show(false); hud.bossShow(false);
    h.state = 'cine'; b.state = 'cine';
    h.a.play('Ready', { fade: 0, speed: 0 });
    const intro = b.has('Intro');
    b.a.play(intro ? 'Intro' : 'Idle', { fade: 0, speed: 0 });
    const bp = b.pos, hp = h.pos;
    this.shots = [
      { dur: 3.2, start: () => { this.audio.gong(); }, cam: (k) => { this.camPos.set(1.7 - 0.6 * k, 0.75 + 0.5 * k, hp.z + 4.2 - 1.6 * k); this.camLook.set(0, 2.2 + 0.3 * k, bp.z); this.camFov = 46; } },
      { dur: intro ? b.a.meta.clips.Intro.dur + 0.5 : 3.0, start: () => { b.a.speed = 1; hud.card(true); this.audio.thud(0.7); },
        cam: (k) => { const a = -0.55 + 1.0 * sm(k); this.camPos.set(bp.x + Math.sin(a) * 4.4, 1.0 + 0.7 * k, bp.z + Math.cos(a) * 4.4); this.camLook.set(bp.x, 2.25, bp.z); this.camFov = 40; },
        tick: () => { if (b.a.ev('whirl')) this.audio.whoosh(true); if (b.a.ev('stance')) { this.audio.thud(0.8); this.shake(0.4); this.env.ripple(bp.x, bp.z, 2); } } },
      { dur: 2.6, start: () => { hud.card(false); h.a.play('Ready', { fade: 0, at: 0.75 }); },
        cam: (k) => { this.camPos.set(hp.x + 1.25 - 0.35 * k, 1.0 + 0.25 * k, hp.z + 2.9 - 0.5 * k); this.camLook.set(hp.x - 0.5, 1.55, hp.z - 3); this.camFov = 40; },
        tick: () => { if (h.a.ev('stance')) { this.audio.cloth(); this.audio.whoosh(); } } },
    ];
    this.shotI = -1; this.shotT = 0;
  }

  updateIntro(dt) {
    this.introT += dt;
    let s = this.shots[this.shotI];
    if (!s || this.shotT >= s.dur) {
      this.shotI++; this.shotT = 0; s = this.shots[this.shotI];
      if (s && s.start) s.start();
    }
    if (!s || this.skipIntro) { this.hud.card(false); this.startFight(); return; }
    this.shotT += dt;
    s.cam(this.shotT / s.dur);
    if (s.tick) s.tick();
    this.camSnap = true;
  }

  startFight() {
    const h = this.hero, b = this.boss, hud = this.hud;
    this.state = 'fight'; this.bars = this.demo ? 0.45 : 0; this.cine = null;
    h.set('idle', 'Idle', { fade: 0.25 }); b.set('idle', 'Idle', { fade: 0.3 }); b.think = 1.4;
    hud.show(true); hud.bossShow(true); hud.word('決'); this.refreshKeys(); hud.keysDim(false);
    this.audio.thud(0.9);
    this.after(14, () => hud.keysDim(true));
  }

  startExecute() {
    const h = this.hero, b = this.boss;
    b.a.yaw = yawTo(b.pos, h.pos);
    const f = b.a.fwd();
    h.pos.set(b.pos.x + f.x * 1.9, 0, b.pos.z + f.z * 1.9); h.a.yaw = b.a.yaw + Math.PI;
    h.set('execute', 'Execute', { fade: 0.1 }); h.a.motionScale = 1; h.execDone = [];
    b.set('executed', b.has('Executed') ? 'Executed' : 'Kneel', { fade: 0.1 }); b.a.motionScale = 1;
    this.hud.prompt(null); this.bars = 1;
    const mid = new V3().addVectors(h.pos, b.pos).multiplyScalar(0.5), side = new V3(f.z, 0, -f.x), a0 = Math.random() < 0.5 ? 1 : -1;
    this.cine = {
      t: 0, dur: 99, update: (t) => {
        const ang = a0 * (0.9 - 0.5 * sm(t / 2.6)), dd = 3.6 - 0.5 * sm(t / 1.8);
        mid.addVectors(h.pos, b.pos).multiplyScalar(0.5);
        this.camPos.set(mid.x + (side.x * Math.cos(ang) + f.x * Math.sin(ang)) * dd, 1.25 + 0.25 * t / 2.6, mid.z + (side.z * Math.cos(ang) + f.z * Math.sin(ang)) * dd);
        this.camLook.set(mid.x, 1.3, mid.z); this.camFov = 40;
      },
    };
    this.audio.whoosh(true);
  }

  updateExecute() {
    const h = this.hero, b = this.boss, a = h.a, hits = a.hits();
    for (const s of ['s1', 's2', 's3']) if (a.ev(s)) this.audio.whoosh(true);
    h.trail = hits.some((t) => a.t > t - 0.22 && a.t < t + 0.12);
    hits.forEach((t, i) => {
      if (h.execDone[i] || a.t < t) return;
      h.execDone[i] = true;
      const last = i === hits.length - 1, p = b.a.at('chest').clone();
      b.hp -= 120; this.stats.dealt += 120;
      if (!last) b.hp = Math.max(1, b.hp);
      this.fx.slash(p, null, { crit: true }); this.fx.clash(p, last); this.audio.hit(true); this.audio.clang(last);
      this.input.rumble(last ? 1 : 0.7, 0.8, last ? 320 : 150);
      b.a.hitFlash(1); this.shake(last ? 1 : 0.6); this.hitstop(last ? 0.14 : 0.09); this.env.post.flash = last ? 0.5 : 0.25;
      if (last) { this.slowmo(0.25, 0.7); this.fx.ring(b.pos, { color: 0xffe0b0, r1: 6, life: 0.6 }); this.env.gust(1.5); }
      if (b.phase === 1 && b.hp <= b.maxHp * 0.5) b.pendingEnrage = true;
      if (last && b.hp <= 0) b.die();
    });
    if (a.done) { h.set('idle', 'Idle', { fade: 0.15 }); if (this.cine && this.state === 'fight' && this.boss.state !== 'enrage') { this.cine = null; this.bars = this.demo ? 0.45 : 0; } }
  }

  onExecuteEnd() { if (this.hero.state !== 'execute' && this.boss.state !== 'enrage') { this.cine = null; this.bars = this.demo ? 0.45 : 0; } }

  // ------------------------------------------------------------------ combat callbacks
  hitstop(s) { this.stopT = Math.max(this.stopT, s); }
  slowmo(scale, s) { this.slowScale = scale; this.slowT = s; this.slowDur = s; }
  shake(v) { this.trauma = Math.min(1.2, this.trauma + v); }

  onPerfectDodge() {
    this.input.rumble(0.1, 0.7, 140);
    this.slowmo(0.2, 0.6); this.hud.popup('PERFECT DODGE', 'blue'); this.audio.perfect();
    this.env.post.flash = 0.22; this.heroGhosts.spawn(0.7, 1.0);
  }

  onBossStrike(res, point, spec) {
    const fx = this.fx, au = this.audio, p = point || this.hero.a.at('chest');
    if (res === 'parried') {
      fx.clash(p, true); au.clang(true); this.hitstop(0.1); this.shake(0.55); this.hud.popup('PARRY', 'gold'); this.env.post.flash = 0.3;
      this.env.ripple(this.hero.pos.x, this.hero.pos.z, 1.5); this.input.rumble(0.25, 1, 110); this.hud.qiFlash();
    } else if (res === 'blocked') {
      fx.clash(p, false); au.clang(false); this.hitstop(0.045); this.shake(0.3); this.input.rumble(0.55, 0.3, 100);
    } else if (res === 'armored') {
      fx.slash(p, null, { color: 0xffe0c0 }); au.hurt(); this.shake(0.35); this.env.post.damage = 0.5; this.input.rumble(0.6, 0.4, 140);
    } else if (res === 'broken' || res === 'hit') {
      fx.slash(p, null, { color: spec.red ? 0xff5030 : 0xffe0c0, crit: true }); au.hurt(); if (res === 'broken') au.clang(false);
      this.hitstop(0.09); this.shake(0.8); this.env.post.damage = 1; this.input.rumble(1, 0.8, 300);
    }
  }

  onBossHurt(point, from, heavy, crit) {
    const dir = new V3().subVectors(this.boss.pos, from).setY(0.3).normalize();
    this.fx.slash(point, dir, { crit }); this.audio.hit(heavy || crit);
    this.hitstop(crit ? 0.11 : heavy ? 0.075 : 0.05); this.shake(crit ? 0.6 : heavy ? 0.4 : 0.22);
    this.boss.a.hitFlash(crit ? 1 : 0.6);
    this.input.rumble(heavy || crit ? 0.6 : 0.15, heavy || crit ? 0.6 : 0.45, heavy || crit ? 130 : 60);
    if (crit) this.hud.popup('COUNTER', 'blue');
  }

  onBossGuard(point) { this.fx.clash(point, false, 0xfff0c0); this.audio.clang(false); this.shake(0.3); this.hitstop(0.05); this.boss.eyeFlash = 0.5; }

  onGuardBreak(point) { this.fx.clash(point, true, 0xfff0c0); this.audio.clang(false); this.audio.thud(0.6); this.hud.popup('GUARD BROKEN', 'gold'); this.shake(0.4); this.input.rumble(0.7, 0.5, 160); }

  // ---- summoned arms, weapon swaps, heavy-weapon slams
  onSummon(kind) {
    const h = this.hero;
    this.audio.perfect(); this.env.post.flash = Math.max(this.env.post.flash, 0.12); this.input.rumble(0.2, 0.6, 180);
    const mark = kind === 'hammer' && h.a.mark['hammer.head'] ? 'hammer.head' : 'handL';
    this.fx.glint(h.a.at(mark), { color: 0x8fe0ff, size: 2.6, life: 0.45, follow: (p) => h.a.at(mark, p) });
    this.fx.ring(h.pos, { color: 0x6fd0ff, r0: 0.3, r1: 2.4, life: 0.45 });
  }
  onVanish() { const h = this.hero; this.fx.sparks(h.a.at(h.tipMark), 26, { color: 0x8fe0ff, speed: 4, grav: 2, life: 0.6, up: 2 }); }
  throwDagger(i, spec) {
    const h = this.hero, b = this.boss, from = h.a.at(h.a.mark.throw ? 'throw' : 'handL').clone(), to = b.a.at('chest');
    const dir = new V3().subVectors(to, from).normalize(), a = i * 0.24;
    dir.set(dir.x * Math.cos(a) + dir.z * Math.sin(a), dir.y + 0.06, dir.z * Math.cos(a) - dir.x * Math.sin(a));
    this.daggers.throw(from, dir); this.audio.whoosh(false); this.fx.glow(from, { color: 0x8fe0ff, size: 0.9, life: 0.2 });
  }
  onHeroSlam(ip, big) {
    this.fx.ring(ip, { color: big ? 0x9fe0ff : 0xffe0b0, r1: big ? 6 : 4, life: 0.5 }); this.fx.dust(ip, big ? 12 : 7, { size: big ? 2 : 1.4, speed: 2.4, a: 0.28 });
    this.fx.sparks(new V3(ip.x, 0.1, ip.z), big ? 50 : 24, { color: big ? 0x9fe0ff : 0xffc080, speed: 9, up: 5 });
    this.audio.thud(big ? 1 : 0.7); this.shake(big ? 0.9 : 0.5); this.hitstop(big ? 0.07 : 0.04); this.env.ripple(ip.x, ip.z, big ? 4 : 2.5); this.input.rumble(big ? 1 : 0.6, big ? 0.9 : 0.4, big ? 280 : 160);
  }
  onSwap(refill) {
    const h = this.hero;
    this.audio.cloth(); this.audio.whoosh(false); this.fx.glint(h.a.at(h.tipMark), { color: 0xffe9b0, size: 1.5, life: 0.3 });
    if (refill) { this.audio.heal(); this.hud.qiFlash(); this.fx.ring(h.pos, { color: 0x9fd8ff, r0: 0.3, r1: 2, life: 0.4 }); }
    this.hud.popup(WEAPONS[h.weapon].toUpperCase(), 'gold'); this.input.rumble(0.2, 0.3, 80);
  }
  onSpiritSwitch() { this.audio.tell(false); this.hud.popup(this.hero.spirit.name.toUpperCase(), 'blue'); }

  onBossBreak() {
    this.input.rumble(0.7, 1, 260);
    this.audio.brk(); this.slowmo(0.3, 0.7); this.hud.popup('POSTURE BROKEN', 'gold'); this.shake(0.7); this.env.post.flash = 0.4;
    this.fx.ring(this.boss.pos, { color: 0xffd98a, r1: 5, life: 0.6 }); this.fx.clash(this.boss.a.at('chest'), true);
  }

  onTelegraph(red) {
    const b = this.boss;
    this.fx.glint(b.a.at('blade.tip'), { color: red ? 0xff2408 : 0xffe9b0, size: red ? 3.6 : 2.3, life: red ? 0.6 : 0.42, follow: (p) => b.a.at('blade.tip', p) });
    this.audio.tell(red);
    if (red) this.danger = 1;
  }

  onSlam(ip) {
    this.input.rumble(1, 1, 320);
    this.fx.ring(ip, { color: 0xffc890, r1: 6.5, life: 0.6 }); this.fx.dust(ip, 14, { size: 2.2, speed: 3, a: 0.3 });
    this.fx.sparks(new V3(ip.x, 0.1, ip.z), 60, { color: 0xffb060, speed: 10, up: 5 });
    this.audio.thud(1); this.audio.clang(false); this.shake(1); this.hitstop(0.06); this.env.ripple(ip.x, ip.z, 4);
  }

  onWaveLaunch() {
    const b = this.boss, f = b.a.fwd();
    this.wave.launch(new V3(b.pos.x + f.x * 1.8, 0, b.pos.z + f.z * 1.8), b.a.yaw);
    this.audio.whoosh(true); this.audio.thud(0.6); this.shake(0.4);
  }

  onEnrageStart() {
    const b = this.boss;
    this.bars = 1; this.hud.prompt(null);
    const f = b.a.fwd(), s = new V3(f.z, 0, -f.x);
    this.cine = {
      t: 0, dur: 99, update: (t) => {
        const k = sm(t / 3.0);
        this.camPos.set(b.pos.x + f.x * (5.2 - 1.4 * k) + s.x * (1.4 - 0.8 * k), 0.8 + 0.3 * k, b.pos.z + f.z * (5.2 - 1.4 * k) + s.z * (1.4 - 0.8 * k));
        this.camLook.set(b.pos.x, 2.3, b.pos.z); this.camFov = 44;
      },
    };
  }
  onEnrageSlam() { this.audio.thud(1); this.shake(0.8); this.fx.ring(this.boss.pos, { color: 0xff7040, r1: 5, life: 0.5 }); this.env.ripple(this.boss.pos.x, this.boss.pos.z, 3); }
  onEnrageRoar() {
    const b = this.boss, h = this.hero;
    this.reached2 = true; this.phaseTarget = 1; this.input.rumble(0.9, 0.9, 1400);
    this.audio.roar(2.2); this.audio.gong(); this.roarT = 1.6; this.env.gust(2.5); this.hud.word('怒');
    this.fx.ring(b.pos, { color: 0xff3010, r1: 11, life: 0.9 }); this.env.post.flash = 0.35;
    if (h.alive && dist2(h.pos, b.pos) < 7 && h.state !== 'execute') { h.a.yaw = yawTo(h.pos, b.pos); h.set('knock', 'Knock', { fade: 0.06 }); h.inv = 1.4; }
  }
  onEnrageEnd() { this.cine = null; this.bars = this.demo ? 0.45 : 0; }

  onHeal() { this.fx.ring(this.hero.pos, { color: 0x9fffd0, r0: 0.3, r1: 2.2, life: 0.6 }); this.fx.glow(this.hero.a.at('chest'), { color: 0x9fffd0, size: 2.4, life: 0.5 }); }

  onBossDead() {
    const b = this.boss, h = this.hero;
    this.state = 'bossdead'; this.slowmo(0.2, 1.6); this.audio.gong(); this.shake(0.8); this.env.post.flash = 0.6;
    this.hud.prompt(null); this.hud.bossShow(false); this.bars = 1; this.wave.active = false; this.wave.mesh.visible = false;
    const a0 = Math.atan2(h.pos.x - b.pos.x, h.pos.z - b.pos.z) + 0.6;
    this.cine = { t: 0, dur: 99, update: (t) => { const a = a0 + t * 0.12; this.camPos.set(b.pos.x + Math.sin(a) * 4.6, 1.1 + t * 0.08, b.pos.z + Math.cos(a) * 4.6); this.camLook.set(b.pos.x, 1.5, b.pos.z); this.camFov = 40; } };
    this.after(4.2, () => {
      if (h.state !== 'dead') { h.set('cine', 'Victory', { fade: 0.25 }); }
      const f = h.a.fwd();
      this.cine = { t: 0, dur: 99, update: (t) => { const k = 3.9 - 0.1 * t; this.camPos.set(h.pos.x - f.x * k + f.z * 1.7, 1.25 + 0.04 * t, h.pos.z - f.z * k - f.x * 1.7); this.camLook.set(h.pos.x + f.x * 2.5, 1.45, h.pos.z + f.z * 2.5); this.camFov = 40; } };
    });
    this.after(8.2, () => {
      const s = this.stats, sec = Math.round(now() - s.t0), rank = s.taken < 40 ? '天' : s.taken < 110 ? '地' : '人';
      this.state = 'victory'; this.hud.show(false);
      this.menu({ han: rank, title: 'The Gate Is Open', tag: 'Marshal Yan has fallen',
        stats: [['Time', `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`], ['Parries', s.parries], ['Perfect dodges', s.dodges], ['Damage taken', Math.round(s.taken)]],
        go: this.demo ? `Play it yourself  (${this.input.glyph('confirm')})` : `Duel again  (${this.input.glyph('confirm')})`, onGo: () => { this.reached2 = false; this.demoMode = false; this.begin(true); },
        go2: this.demo ? `Watch again  (${this.input.glyph('heavy')})` : null, onGo2: () => { this.reached2 = false; this.demoMode = true; this.begin(); } });
    });
  }

  onHeroDead() {
    this.state = 'herodead'; this.slowmo(0.3, 1.2); this.hud.prompt(null);
    this.after(2.8, () => {
      this.menu({ han: '敗', title: 'You Fell', tag: this.reached2 && T.retryP2 ? 'The Marshal\'s wrath remains' : 'The gate stays shut · the duel begins again', go: `Rise again  (${this.input.glyph('confirm')})`, onGo: () => this.begin(true) });
      if (this.auto) this.after(1.5, () => this.begin(true));
    });
  }

  /** The strike about to land on the hero (boss blade, slam, dash or the fire wave), or null. */
  threat() {
    if (this.state !== 'fight') return null;
    const th = this.boss.threat();
    if (th && th.eta !== null && th.eta >= -0.03) return th;
    const w = this.wave, h = this.hero;
    if (w.active && !w.hit) {
      const rx = h.pos.x - w.mesh.position.x, rz = h.pos.z - w.mesh.position.z, f = rx * w.dir.x + rz * w.dir.z;
      if (f > -0.5 && Math.abs(rx * w.dir.z - rz * w.dir.x) < 2.4) return { name: 'Wave', red: true, eta: Math.max(0, f) / 15 };
    }
    return null;
  }

  /** What pressing the kick button does right now: null (it is a kick), or the answer to an incoming strike. */
  timedAnswer() { const th = this.threat(); return th && th.eta <= T.circle ? (th.red ? 'dodge' : 'parry') : null; }

  // ------------------------------------------------------------------ test bot
  bot() { this.autoFight(this.botSkill); }

  autoFight(skill) {
    const I = this.input, h = this.hero, b = this.boss, d = dist2(h.pos, b.pos), th = b.threat();
    const to = new V3().subVectors(b.pos, h.pos).setY(0).normalize();
    I.mx = 0; I.mz = 0; I.block = false;
    if (this.state !== 'fight' || !h.alive) return;
    if (this.wave.active) {
      const w = this.wave, rel = new V3().subVectors(h.pos, w.mesh.position), f = rel.dot(w.dir);
      if (f > 0 && f < 3.2 && Math.abs(rel.x * w.dir.z - rel.z * w.dir.x) < 2.2 && h.state !== 'dash') { I.mx = to.z; I.mz = -to.x; I.press('dodge'); return; }
    }
    if (b.canExecute(h)) { I.press('exec'); I.mx = to.x; I.mz = to.z; return; }
    if (b.state === 'kneel' || b.state === 'break') { I.mx = to.x; I.mz = to.z; return; }
    if (th && th.eta !== null) {
      if (th.red) {
        if (th.eta < Math.min(0.17, T.iframe[1] - 0.05) && h.state !== 'dash') { I.mx = to.z; I.mz = -to.x; I.press('dodge'); }
        else if (th.name === 'Whirl' && d < 5) { I.mx = -to.x; I.mz = -to.z; }
      } else if (th.eta < 0.6) {
        I.block = true;
        if (th.eta < Math.min(0.12, T.parry - 0.03) && Math.random() < skill && now() - I.blockAt > 0.2) { I.blockAt = now(); }
      }
      return;
    }
    if (h.hp < 45 && h.heals > 0 && d > 4 && b.state !== 'attack') { I.press('heal'); return; }
    if (b.state === 'enrage') { if (d < 7) { I.mx = -to.x; I.mz = -to.z; } return; }
    if (d > 2.7) { I.mx = to.x; I.mz = to.z; }
    else if (b.state === 'guard') I.press('kick');
    else if (['idle', 'run', 'attack', 'swap'].includes(h.state)) {
      const r = Math.random();
      if (r < 0.16) I.press('light'); else if (r < 0.2) I.press('heavy'); else if (r < 0.206) I.press('kick');
      else if (r < 0.214 && h.qi > 60) I.press('spirit'); else if (r < 0.2165) I.press('swapW'); else if (r < 0.2175) I.press('swapS');
    }
  }

  // ------------------------------------------------------------------ frame
  frame() {
    requestAnimationFrame(() => this.frame());
    const t = now(), real = Math.min(0.05, t - this.last);
    this.last = t; this.time = t;
    this.fpsAvg += (1 / Math.max(real, 1e-3) - this.fpsAvg) * 0.05;
    // drop a quality level if the machine cannot hold 40 fps for a few seconds
    if (this.state === 'fight' && !params.has('q') && this.q > 0) {
      this.lowT = this.fpsAvg < 40 ? (this.lowT || 0) + real : 0;
      if (this.lowT > 4) { this.q--; this.env.setQuality(this.q); this.lowT = -6; }
    }
    let scale = 1;
    if (this.stopT > 0) { this.stopT -= real; scale = 0.02; }
    else if (this.slowT > 0) { this.slowT -= real; scale = this.slowScale + (1 - this.slowScale) * (1 - sm(this.slowT / Math.min(0.25, this.slowDur))); }
    this.scale = scale;
    const dt = real * scale;
    this.gt += dt;
    const h = this.hero, b = this.boss, env = this.env, cam = env.camera;

    for (let i = this.seq.length - 1; i >= 0; i--) if (this.gt >= this.seq[i].t) { const s = this.seq.splice(i, 1)[0]; s.fn(); }

    // input, camera-relative
    const fwd = new V3().subVectors(this.camLook, this.camPos).setY(0).normalize();
    this.input.update(fwd, real);
    if (this.menuGo && this.input.take('confirm')) { const go = this.menuGo; this.menuGo = null; go(); }
    if (this.input.take('pause')) this.togglePause();
    if (this.overlayKind === 'title' && this.state === 'title' && this.input.take('kick')) {      // difficulty toggle on the title screen
      const names = Object.keys(DIFFS);
      setDiff(names[(names.indexOf(T.name) + 1) % names.length]);
      try { localStorage.setItem('vg-diff', T.name); } catch (e) { /* private mode */ }
      this.hero.reset(); this.boss.reset(); this.place(); this.showTitle();
    }
    if (this.menuGo2 && this.input.take('heavy')) { const go = this.menuGo2; this.menuGo2 = null; this.menuGo = null; go(); }
    if (this.paused) { env.render(); return; }
    if (this.demo) this.demo.update(dt); else if (this.auto) this.bot();
    if (this.state === 'intro') this.updateIntro(dt);
    if (this.state !== 'fight' && this.state !== 'bossdead') { this.input.mx = this.input.mz = 0; this.input.block = false; }

    if (this.state !== 'load' && this.state !== 'title') {
      h.update(dt); b.update(dt);
      if (h.state === 'execute') this.updateExecute();
      // bodies do not overlap (dashes pass through)
      const d = dist2(h.pos, b.pos), min = b.radius + 0.42;
      if (d < min && h.state !== 'dash' && h.state !== 'execute' && !b.leaping && !b.dashing && b.state !== 'cine') {
        const nx = d > 1e-3 ? (h.pos.x - b.pos.x) / d : 0, nz = d > 1e-3 ? (h.pos.z - b.pos.z) / d : 1;
        h.pos.x = b.pos.x + nx * min; h.pos.z = b.pos.z + nz * min;
      }
      // the crescent wave
      const w = this.wave;
      if (w.active) {
        w.update(dt);
        w.rip = (w.rip || 0) - dt;
        if (w.rip <= 0) { w.rip = 0.07; env.ripple(w.mesh.position.x, w.mesh.position.z, 1.5); this.fx.sparks(new V3(w.mesh.position.x, 0.1, w.mesh.position.z), 6, { color: 0xff7030, speed: 5, up: 3, life: 0.4 }); }
        const rel = new V3().subVectors(h.pos, w.mesh.position), f = rel.dot(w.dir), l = Math.abs(rel.x * w.dir.z - rel.z * w.dir.x);
        if (!w.hit && Math.abs(f) < 0.9 && l < 1.9) {
          const res = h.takeHit({ dmg: 20, red: true, knock: true, from: w.mesh.position });
          if (res !== 'ignored') { w.hit = true; this.onBossStrike(res, h.a.at('chest').clone(), { red: true }); }
        }
      }
      // thrown spirit blades
      const chest = b.a.at('chest');
      this.daggers.update(dt, chest, 0.8, (p) => {
        const res = b.receive({ dmg: MOVES.SA_Daggers.dmg[0], post: MOVES.SA_Daggers.post[0], spirit: true, point: p, from: h.pos });
        if (res === 'ignored') this.fx.sparks(p, 8, { color: 0x8fe0ff, speed: 4 });
      }, (p) => { if (Math.random() < 0.5) this.fx.glow(p, { color: 0x8fe0ff, size: 0.5, life: 0.18, a: 0.6 }); });
      this.spiritMat.uniforms.time.value += dt;
      const sOn = h.summoned === 'hammer';
      this.spiritLight.intensity += ((sOn ? 40 : 0) - this.spiritLight.intensity) * Math.min(1, dt * 14);
      if (sOn) this.spiritLight.position.copy(h._t1);
      this.heroTrail.setColor(h.summoned ? 0x6fd0ff : h.counter > 0 || h.crit ? 0x9fd8ff : 0xdfeeff);
      this.heroTrail.update(dt, h._b1, h._t1, !!h.trail);
      this.bossTrail.setColor(b.atk && this.bossRed() ? 0xff3a18 : (b.phase === 2 ? 0xffa050 : 0xffe2b0));
      this.bossTrail.update(dt, b._b1, b._t1, !!b.trail);
    }
    this.fx.update(dt); this.heroGhosts.update(dt); this.bossGhosts.update(dt);

    // HUD
    if (this.state === 'fight') {
      this.hud.hero(h.hp / h.maxHp, h.qi / h.maxQi); this.hud.heals(h.heals);
      const I = this.input, sp = h.spirit;
      this.hud.arms({ wGlyph: I.glyph('swapW'), wName: WEAPONS[h.weapon], refill: h.hasGreat && h.swapCd <= 0, sGlyph: I.glyph('spirit'), sName: sp ? sp.name : '', sReady: !!sp && h.qi >= MOVES[sp.id].qi });
      this.hud.boss(b.hp / b.maxHp, b.posture / 100);
      this.hud.prompt(b.canExecute(h) && h.state !== 'execute' ? `FINISHER &nbsp;<kbd>${this.input.glyph('exec')}</kbd> or <kbd>${this.input.glyph('light')}</kbd>` : null);
    }
    // the closing ring: when to answer the strike that is coming
    const th = h && h.alive && !this.cine ? this.threat() : null;
    if (th && th.eta < 0.8 && h.state !== 'execute') {
      const sp = h.a.at('chest').clone().project(cam), g = (a) => `<kbd>${this.input.glyph(a)}</kbd>`;
      this.hud.ring((sp.x * 0.5 + 0.5) * innerWidth, (-sp.y * 0.5 + 0.5) * innerHeight, Math.min(1, th.eta / 0.8), th.red, th.eta <= T.circle, (th.red ? g('dodge') : g('block')) + ' ' + g('kick'));
    } else this.hud.ring(0, 0, null);
    // a browser tab keeps sound off until a click or key press (pad buttons do not count): say so
    if (this.state === 'fight' && this.audio.ctx && this.audio.ctx.state === 'suspended') {
      this.sndT = (this.sndT || 0) - real;
      if (this.sndT <= 0) { this.hud.popup('CLICK OR PRESS A KEY ONCE FOR SOUND', 'blue'); this.sndT = 10; }
    }
    this.danger = Math.max(0, this.danger - real * 1.6);
    this.hud.danger(this.danger * 0.8);

    // camera
    this.focus.addVectors(h.pos, b.pos).multiplyScalar(0.5);
    if (this.cine) { this.cine.t += dt; this.cine.update(this.cine.t); this.camSnap = true; }
    else if (this.demo && this.state === 'fight') { this.camFov += (this.demo.camera(real, this.camPos, this.camLook) - this.camFov) * (1 - Math.exp(-real * 6)); }
    else if (this.state !== 'intro' && this.state !== 'title' && this.state !== 'load') {
      const d = dist2(h.pos, b.pos);
      if (d > 0.9) this.camDir.set(h.pos.x - b.pos.x, 0, h.pos.z - b.pos.z).normalize();
      const I = this.input;
      if (I.take('camReset')) this.camYaw = 0;
      if (I.camX) { this.camYaw = clamp((this.camYaw || 0) + I.camX * 2.2 * real, -1.5, 1.5); this.camIdle = 0; }
      else { this.camIdle = (this.camIdle || 0) + real; if (this.camIdle > 2) this.camYaw = (this.camYaw || 0) * Math.exp(-real * 1.5); }
      const cy = Math.cos(this.camYaw || 0), sy = Math.sin(this.camYaw || 0);
      const dir = new V3(this.camDir.x * cy + this.camDir.z * sy, 0, this.camDir.z * cy - this.camDir.x * sy), back = 4.2 + d * 0.22, up = 2.6 + d * 0.08, sd = 1.35;
      const want = new V3(h.pos.x + dir.x * back + dir.z * sd, up, h.pos.z + dir.z * back - dir.x * sd);
      const R = 13.2, r = Math.hypot(want.x, want.z);
      if (r > R) { want.x *= R / r; want.z *= R / r; want.y += (r - R) * 0.35; }
      const look = new V3(h.pos.x + (b.pos.x - h.pos.x) * 0.55, 1.35, h.pos.z + (b.pos.z - h.pos.z) * 0.55);
      const kp = this.camSnap ? 1 - Math.exp(-real * 3) : 1 - Math.exp(-real * 5.5), kl = 1 - Math.exp(-real * 8);
      this.camPos.lerp(want, kp); this.camLook.lerp(look, kl); this.camFov += (50 - this.camFov) * (1 - Math.exp(-real * 4));
      if (this.camSnap && this.camPos.distanceTo(want) < 0.4) this.camSnap = false;
    } else if (this.state === 'title') {
      const a = t * 0.05;
      this.camPos.set(Math.sin(a) * 3 + 2.2, 1.25, 11.5); this.camLook.set(0, 2.1, -4); this.camFov = 44;
    }
    this.trauma = Math.max(0, this.trauma - real * 1.9);
    if (this.roarT > 0) { this.roarT -= real; this.trauma = Math.max(this.trauma, 0.55); }
    const sh = this.trauma * this.trauma * 0.28;
    cam.position.set(this.camPos.x + Math.sin(t * 61) * sh, this.camPos.y + Math.sin(t * 73 + 1) * sh, this.camPos.z + Math.sin(t * 67 + 2) * sh);
    cam.lookAt(this.camLook);
    cam.rotation.z += Math.sin(t * 53) * sh * 0.06;
    if (Math.abs(cam.fov - this.camFov) > 0.01) { cam.fov = this.camFov; cam.updateProjectionMatrix(); }

    // world mood and screen effects
    this.phaseK += (this.phaseTarget - this.phaseK) * Math.min(1, real * 0.9);
    env.setPhase(this.phaseK);
    const P = env.post, slow = scale < 0.95 && this.stopT <= 0 ? 1 : 0;
    P.desat += (slow * 0.55 - P.desat) * Math.min(1, real * 8);
    P.blur += (slow * 0.6 - P.blur) * Math.min(1, real * 8);
    P.flash = Math.max(0, P.flash - real * 2.6); P.damage = Math.max(h.hp < 30 && h.alive ? 0.35 : 0, P.damage - real * 1.5);
    P.bars += (this.bars - P.bars) * Math.min(1, real * 4);
    const wind = 1.2 + Math.sin(t * 0.7) * 0.8;
    h.a.springCfg.wind.set(wind, 0, wind * 0.4); b.a.springCfg.wind.set(wind, 0, wind * 0.4);
    this.audio.update(this.state === 'fight' ? (b.phase === 2 ? 1 : 0.5) : this.state === 'intro' ? 0.2 : 0);
    env.update(dt, this.focus);
    env.render();
  }

  bossRed() { const th = this.boss.threat(); return !!(th && th.red); }
}

const game = new Game();
window.game = game;
game.init().catch((e) => { document.getElementById('err').textContent += (e.stack || e) + '\n'; console.error(e); });
