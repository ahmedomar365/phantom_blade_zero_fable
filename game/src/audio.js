// All sound is synthesised with WebAudio: steel, cloth, impacts, the boss's voice, rain and war drums.
export class Audio {
  constructor() { this.ctx = null; this.intensity = 0; this.muted = false; }

  start() {
    if (this.ctx) { this.ctx.resume(); return; }
    const C = window.AudioContext || window.webkitAudioContext;
    if (!C) return;
    const ctx = this.ctx = new C();
    this.master = ctx.createGain(); this.master.gain.value = 0.9;
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -14; comp.ratio.value = 5;
    this.master.connect(comp); comp.connect(ctx.destination);
    this.sfx = ctx.createGain(); this.sfx.gain.value = 1; this.sfx.connect(this.master);
    this.mus = ctx.createGain(); this.mus.gain.value = 0.0; this.mus.connect(this.master);
    // reverb: a generated tail for the courtyard
    const len = ctx.sampleRate * 2.2, ir = ctx.createBuffer(2, len, ctx.sampleRate);
    for (let c = 0; c < 2; c++) { const d = ir.getChannelData(c); for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.6); }
    this.rev = ctx.createConvolver(); this.rev.buffer = ir;
    const rg = ctx.createGain(); rg.gain.value = 0.22;
    this.rev.connect(rg); rg.connect(this.master);
    this.sfx.connect(this.rev);
    const nl = ctx.sampleRate * 2;
    this.noise = ctx.createBuffer(1, nl, ctx.sampleRate);
    const nd = this.noise.getChannelData(0);
    for (let i = 0; i < nl; i++) nd[i] = Math.random() * 2 - 1;
    this.rain();
    this.nextBeat = ctx.currentTime + 0.2; this.beat = 0;
  }

  get t() { return this.ctx.currentTime; }

  nz(dur, { f = 1000, q = 1, type = 'bandpass', g = 0.5, f1 = null, a = 0.005, when = 0, rate = 1 } = {}) {
    if (!this.ctx) return;
    const ctx = this.ctx, t = this.t + when;
    const s = ctx.createBufferSource(); s.buffer = this.noise; s.loop = true; s.playbackRate.value = rate;
    const fl = ctx.createBiquadFilter(); fl.type = type; fl.frequency.setValueAtTime(f, t); fl.Q.value = q;
    if (f1) fl.frequency.exponentialRampToValueAtTime(f1, t + dur);
    const gn = ctx.createGain();
    gn.gain.setValueAtTime(0, t); gn.gain.linearRampToValueAtTime(g, t + a); gn.gain.exponentialRampToValueAtTime(0.0008, t + dur);
    s.connect(fl); fl.connect(gn); gn.connect(this.sfx);
    s.start(t, Math.random()); s.stop(t + dur + 0.05);
  }

  tone(f, dur, { type = 'sine', g = 0.3, f1 = null, a = 0.003, when = 0, dest = null } = {}) {
    if (!this.ctx) return;
    const ctx = this.ctx, t = this.t + when;
    const o = ctx.createOscillator(); o.type = type; o.frequency.setValueAtTime(f, t);
    if (f1) o.frequency.exponentialRampToValueAtTime(f1, t + dur);
    const gn = ctx.createGain();
    gn.gain.setValueAtTime(0, t); gn.gain.linearRampToValueAtTime(g, t + a); gn.gain.exponentialRampToValueAtTime(0.0008, t + dur);
    o.connect(gn); gn.connect(dest || this.sfx);
    o.start(t); o.stop(t + dur + 0.05);
  }

  whoosh(heavy = false) { this.nz(heavy ? 0.42 : 0.22, { f: heavy ? 500 : 1400, f1: heavy ? 2200 : 4200, q: 1.4, g: heavy ? 0.5 : 0.28, a: heavy ? 0.12 : 0.05 }); }
  cloth() { this.nz(0.18, { f: 700, f1: 300, q: 0.7, g: 0.16, a: 0.03 }); }

  /** Steel on steel. bright = a clean parry. */
  clang(bright = false) {
    const base = bright ? 2100 : 1300;
    for (const [m, g, d] of [[1, 0.26, 0.5], [1.48, 0.2, 0.42], [2.09, 0.16, 0.35], [2.94, 0.11, 0.28], [4.1, 0.07, 0.2]])
      this.tone(base * m * (0.97 + Math.random() * 0.06), d * (bright ? 1.7 : 1), { type: 'triangle', g: g * (bright ? 1.2 : 1) });
    this.nz(0.09, { f: 5200, q: 0.8, g: 0.5, type: 'highpass' });
    if (bright) this.tone(3400, 0.9, { g: 0.1 });
  }

  hit(heavy = false) {
    this.nz(0.14, { f: heavy ? 900 : 1600, f1: 200, q: 0.8, g: 0.6 });
    this.tone(heavy ? 90 : 140, 0.2, { g: 0.6, f1: 40 });
    this.tone(1500, 0.12, { type: 'triangle', g: 0.12 });
  }
  hurt() { this.nz(0.2, { f: 500, f1: 120, q: 0.7, g: 0.7 }); this.tone(70, 0.3, { g: 0.7, f1: 35 }); }
  thud(g = 0.8) { this.tone(62, 0.5, { g, f1: 28 }); this.nz(0.35, { f: 180, f1: 60, q: 0.6, g: g * 0.7, type: 'lowpass' }); }
  step(heavy = false) { this.nz(0.09, { f: heavy ? 260 : 900, q: 0.8, g: heavy ? 0.4 : 0.08, type: 'lowpass' }); if (heavy) this.tone(50, 0.22, { g: 0.45, f1: 30 }); }
  dash() { this.nz(0.3, { f: 2600, f1: 500, q: 0.9, g: 0.34, a: 0.02 }); }
  tell(red = false) {
    if (red) { this.tone(196, 0.7, { type: 'sawtooth', g: 0.16, f1: 185 }); this.tone(277, 0.7, { type: 'sawtooth', g: 0.12, f1: 262 }); this.tone(880, 0.5, { g: 0.12 }); }
    else { this.tone(2640, 0.35, { g: 0.1 }); this.tone(3960, 0.3, { g: 0.06 }); }
  }
  perfect() { for (const [f, w] of [[1320, 0], [1980, 0.05], [2640, 0.1]]) this.tone(f, 0.8, { g: 0.1, when: w }); this.nz(0.8, { f: 300, f1: 2400, q: 2, g: 0.2, a: 0.3 }); }
  heal() { for (const [f, w] of [[392, 0], [523, 0.1], [659, 0.2], [784, 0.3]]) this.tone(f, 0.9, { g: 0.1, when: w }); }
  brk() { this.clang(true); this.thud(1); this.tone(110, 1.2, { type: 'sawtooth', g: 0.14, f1: 55 }); }
  gong() { for (const [m, g] of [[1, 0.5], [1.52, 0.3], [2.4, 0.2], [3.1, 0.12], [4.3, 0.08]]) this.tone(92 * m, 4.5, { g: g * 0.6, type: 'sine', a: 0.01 }); this.nz(1.2, { f: 400, f1: 150, q: 0.5, g: 0.3 }); }
  roar(dur = 2.0) {
    if (!this.ctx) return;
    const ctx = this.ctx, t = this.t;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.5, t + 0.25); g.gain.setValueAtTime(0.5, t + dur * 0.6); g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    const fm = ctx.createBiquadFilter(); fm.type = 'bandpass'; fm.Q.value = 2.5;
    fm.frequency.setValueAtTime(380, t); fm.frequency.linearRampToValueAtTime(760, t + 0.4); fm.frequency.linearRampToValueAtTime(520, t + dur);
    for (const f of [58, 87, 116.5]) {
      const o = ctx.createOscillator(); o.type = 'sawtooth'; o.frequency.setValueAtTime(f * 0.8, t); o.frequency.linearRampToValueAtTime(f * 1.15, t + 0.35); o.frequency.linearRampToValueAtTime(f * 0.9, t + dur);
      const lfo = ctx.createOscillator(); lfo.frequency.value = 27 + Math.random() * 9;
      const lg = ctx.createGain(); lg.gain.value = f * 0.12;
      lfo.connect(lg); lg.connect(o.frequency);
      o.connect(fm); o.start(t); o.stop(t + dur); lfo.start(t); lfo.stop(t + dur);
    }
    fm.connect(g); g.connect(this.sfx);
    this.nz(dur, { f: 700, f1: 420, q: 1.2, g: 0.35, a: 0.2 });
  }

  rain() {
    const ctx = this.ctx;
    const s = ctx.createBufferSource(); s.buffer = this.noise; s.loop = true;
    const hp = ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 1800;
    const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 7500;
    const g = ctx.createGain(); g.gain.value = 0.045;
    s.connect(hp); hp.connect(lp); lp.connect(g); g.connect(this.master); s.start();
    const s2 = ctx.createBufferSource(); s2.buffer = this.noise; s2.loop = true; s2.playbackRate.value = 0.5;
    const lp2 = ctx.createBiquadFilter(); lp2.type = 'lowpass'; lp2.frequency.value = 220;
    const g2 = ctx.createGain(); g2.gain.value = 0.10;
    s2.connect(lp2); lp2.connect(g2); g2.connect(this.master); s2.start();
  }

  drum(when, g = 0.7, f = 78) { this.tone(f, 0.55, { g, f1: f * 0.45, when, dest: this.mus }); }
  rim(when, g = 0.2) { this.tone(820, 0.06, { type: 'square', g, when, dest: this.mus }); }

  /** Call every frame: schedules war drums; intensity 0..1 thickens the pattern. */
  update(mood) {
    if (!this.ctx) return;
    this.intensity += (mood - this.intensity) * 0.02;
    this.mus.gain.value += ((mood > 0.01 ? 0.75 : 0) - this.mus.gain.value) * 0.03;
    const bpm = 84 + 44 * this.intensity, step = 60 / bpm / 2;
    while (this.nextBeat < this.t + 0.15) {
      const b = this.beat % 16, w = this.nextBeat - this.t, I = this.intensity;
      if (b % 8 === 0) this.drum(w, 0.9, 66);
      if (b === 6 || b === 14) this.drum(w, 0.6, 88);
      if (I > 0.35 && (b === 3 || b === 11)) this.drum(w, 0.5, 100);
      if (I > 0.6 && b % 2 === 1) this.rim(w, 0.10);
      if (I > 0.8 && (b === 12 || b === 13 || b === 15)) this.drum(w, 0.55, 120);
      if (b === 0 && this.beat % 32 === 0) { this.tone(55, step * 30, { type: 'sawtooth', g: 0.05 + 0.04 * I, a: 1.5, when: w, dest: this.mus }); this.tone(82.4, step * 30, { type: 'sine', g: 0.07, a: 1.5, when: w, dest: this.mus }); }
      this.nextBeat += step; this.beat++;
    }
  }
}
