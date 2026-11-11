// Keyboard + mouse and gamepad (DualSense / DualShock / Xbox, standard mapping) behind one set of actions.
// Pad layout follows the usual wuxia-action scheme: Square light, Triangle heavy, Circle kick, L1 guard/parry,
// R1 dodge, R2 summoned arm, D-pad left/right switch weapon / summoned arm, D-pad up or L2 heal, Cross finisher.
import { T } from './tuning.js';

const now = () => performance.now() / 1000;

const KEY_ACTION = {
  KeyJ: 'light', KeyK: 'heavy', KeyE: 'kick', KeyI: 'kick', Space: 'dodge', KeyF: 'spirit', KeyR: 'heal', ArrowUp: 'heal',
  ArrowLeft: 'swapW', Tab: 'swapW', ArrowRight: 'swapS', KeyV: 'exec', Escape: 'pause', KeyP: 'pause', Enter: 'confirm',
};
const BLOCK_KEYS = ['ShiftLeft', 'ShiftRight', 'KeyQ'];
const PAD_ACTION = { 2: 'light', 3: 'heavy', 1: 'kick', 5: 'dodge', 7: 'spirit', 6: 'heal', 12: 'heal', 14: 'swapW', 15: 'swapS', 0: 'exec', 9: 'pause', 11: 'camReset' };
const GLYPH = {
  kbm: { light: 'Left click', heavy: 'Right click', kick: 'E', block: 'Shift', dodge: 'Space', spirit: 'F', heal: 'R', swapW: '←', swapS: '→', exec: 'V', pause: 'Esc', move: 'W A S D', confirm: 'Enter' },
  ps: { light: '□', heavy: '△', kick: '○', block: 'L1', dodge: 'R1', spirit: 'R2', heal: 'L2', swapW: 'D-pad ←', swapS: 'D-pad →', exec: '✕', pause: 'Options', move: 'L stick', confirm: '✕' },
  xbox: { light: 'X', heavy: 'Y', kick: 'B', block: 'LB', dodge: 'RB', spirit: 'RT', heal: 'LT', swapW: 'D-pad ←', swapS: 'D-pad →', exec: 'A', pause: 'Menu', move: 'L stick', confirm: 'A' },
};

export class Input {
  constructor({ onAny = () => {}, onDevice = () => {} } = {}) {
    this.onAny = onAny; this.onDevice = onDevice;
    this.keys = new Set(); this.pressed = {}; this.taken = {}; this.mx = 0; this.mz = 0; this.block = false; this.blockAt = -9;
    this.camX = 0; this.device = 'kbm'; this.pad = []; this.padBlock = false; this.padName = '';
    addEventListener('keydown', (e) => {
      if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Tab'].includes(e.code)) e.preventDefault();
      if (e.repeat) return;
      this.keys.add(e.code);
      this.setDevice('kbm');
      if (KEY_ACTION[e.code]) this.press(KEY_ACTION[e.code]);
      if (e.code === 'Space') this.press('confirm');
      if (BLOCK_KEYS.includes(e.code)) this.tapBlock();
      this.onAny();
    });
    addEventListener('keyup', (e) => this.keys.delete(e.code));
    addEventListener('blur', () => this.keys.clear());
    const c = document.getElementById('c');
    c.addEventListener('mousedown', (e) => {
      this.setDevice('kbm');
      if (e.button === 0) this.press('light'); if (e.button === 2) this.press('heavy'); if (e.button === 1) this.press('spirit');
      this.onAny();
    });
    addEventListener('contextmenu', (e) => e.preventDefault());
    addEventListener('gamepadconnected', (e) => { this.padName = e.gamepad.id; this.setDevice(this.kind(e.gamepad)); });
  }

  /** A guard press opens the parry window, unless the button is being mashed. */
  tapBlock() { const t = now(); if (t - (this.lastTap || -9) >= T.mash) this.blockAt = t; else this.blockAt = -9; this.lastTap = t; }

  kind(gp) { return /054c|dualsense|dualshock|playstation|wireless controller/i.test(gp.id) ? 'ps' : 'xbox'; }
  setDevice(d) { if (d !== this.device) { this.device = d; this.onDevice(d); } }
  glyph(action) { return GLYPH[this.device][action] || action; }
  press(n) { this.pressed[n] = now(); }
  take(n) { if (this.pressed[n] !== undefined && now() - this.pressed[n] < 0.32) { this.taken[n] = this.pressed[n]; delete this.pressed[n]; return true; } return false; }
  /** Put back a press that could not be used this frame (it keeps its original time, so it still expires). */
  untake(n) { if (this.taken[n] !== undefined) this.pressed[n] = this.taken[n]; }
  keep(n) { this.pressed[n] = now(); }
  clear() { this.pressed = {}; }
  getPad() { const l = navigator.getGamepads ? navigator.getGamepads() : []; for (const g of l) if (g && g.connected) return g; return null; }

  /** Controller vibration: strong = low-frequency motor, weak = high-frequency motor (0..1), ms duration. */
  rumble(strong, weak, ms = 120) {
    const gp = this.device === 'kbm' ? null : this.getPad();
    const v = gp && gp.vibrationActuator;
    if (!v || !v.playEffect) return;
    try { v.playEffect('dual-rumble', { startDelay: 0, duration: ms, strongMagnitude: Math.min(1, strong), weakMagnitude: Math.min(1, weak) }).catch(() => {}); } catch (e) { /* unsupported */ }
  }

  update(fwd, dt) {
    const k = this.keys;
    let x = (k.has('KeyD') ? 1 : 0) - (k.has('KeyA') ? 1 : 0), y = (k.has('KeyW') ? 1 : 0) - (k.has('KeyS') ? 1 : 0);
    let block = BLOCK_KEYS.some((c) => k.has(c));
    this.camX = 0;
    const gp = this.getPad();
    if (gp) {
      const b = (i) => { const o = gp.buttons[i]; return !!o && (o.pressed || o.value > 0.5); };
      let any = false;
      for (const [i, act] of Object.entries(PAD_ACTION)) {
        const down = b(i);
        if (down && !this.pad[i]) { this.press(act); if (i === '0') this.press('confirm'); any = true; }
        this.pad[i] = down;
      }
      const lb = b(4);
      if (lb && !this.padBlock) { this.tapBlock(); any = true; }
      this.padBlock = lb; block = block || lb;
      // sticks: radial dead zone, rescaled so the edge of the dead zone is zero
      const stick = (ax, ay) => { const m = Math.hypot(ax, ay), dz = 0.2; if (m < dz) return [0, 0]; const s = Math.min(1, (m - dz) / (1 - dz)) / m; return [ax * s, ay * s]; };
      const [lx, ly] = stick(gp.axes[0] || 0, gp.axes[1] || 0), [rx] = stick(gp.axes[2] || 0, gp.axes[3] || 0);
      if (lx || ly) { x = lx; y = -ly; any = true; }
      this.camX = rx;
      if (rx) any = true;
      if (any) { this.setDevice(this.kind(gp)); this.onAny(); }
    }
    const l = Math.hypot(x, y);
    if (l > 1) { x /= l; y /= l; }
    this.mx = fwd.x * y - fwd.z * x; this.mz = fwd.z * y + fwd.x * x;
    this.block = block;
  }
}
