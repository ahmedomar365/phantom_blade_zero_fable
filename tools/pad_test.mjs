// Drives the game through a simulated DualSense (standard-mapping Gamepad API object) and prints what the hero does.
// node tools/pad_test.mjs   (server on PORT, default 5260)
import { chromium } from 'playwright-core';
const PORT = process.env.PORT || 5260;
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-angle=d3d11', '--ignore-gpu-blocklist', '--enable-gpu', '--mute-audio'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.addInitScript(() => {
  const pad = { id: 'DualSense Wireless Controller (STANDARD GAMEPAD Vendor: 054c Product: 0ce6)', index: 0, connected: true, mapping: 'standard', timestamp: 0,
    axes: [0, 0, 0, 0], buttons: Array.from({ length: 17 }, () => ({ pressed: false, touched: false, value: 0 })),
    vibrationActuator: { playEffect: (type, o) => { window.__rumbles.push([type, o.strongMagnitude, o.weakMagnitude, o.duration]); return Promise.resolve('complete'); } } };
  window.__pad = pad; window.__rumbles = [];
  navigator.getGamepads = () => [pad, null, null, null];
});
await page.goto(`${process.env.BASE || `http://localhost:${PORT}`}/?god=1&q=0`);
await page.waitForFunction(() => window.gameReady, null, { timeout: 90000 });
const btn = (i, v) => page.evaluate(([i, v]) => { const b = window.__pad.buttons[i]; b.pressed = v; b.value = v ? 1 : 0; }, [i, v]);
const tap = async (i, ms = 70) => { await btn(i, true); await page.waitForTimeout(ms); await btn(i, false); };
const axes = (a) => page.evaluate((a) => { window.__pad.axes = a; }, a);
const st = async (label) => console.log(label.padEnd(30), JSON.stringify(await page.evaluate(() => { const g = game, h = g.hero; return { game: g.state, paused: !!g.paused, dev: g.input.device, hero: h.state, clip: h.a.clip, weapon: h.weapon, arm: h.spirit && h.spirit.name, qi: Math.round(h.qi), z: +h.pos.z.toFixed(1), rumbles: window.__rumbles.length }; })));
const B = { cross: 0, circle: 1, square: 2, triangle: 3, l1: 4, r1: 5, l2: 6, r2: 7, options: 9, up: 12, left: 14, right: 15 };

await st('title');
await tap(B.cross); await page.waitForTimeout(1600); await st('Cross on title (starts intro)');
await tap(B.cross); await page.waitForTimeout(900); await st('Cross again (skips intro)');
console.log('hint panel:', await page.evaluate(() => document.getElementById('keys').innerText.replace(/\n/g, ' | ')));
await axes([0, -1, 0, 0]); await page.waitForTimeout(900); await st('left stick up 0.9 s'); await axes([0, 0, 0, 0]);
await axes([0, -0.5, 0, 0]); await page.waitForTimeout(300); await st('half tilt (walk speed ' + await page.evaluate(() => game.hero.a.speed.toFixed(2)) + ')'); await axes([0, 0, 0, 0]);
await tap(B.square); await page.waitForTimeout(130); await st('Square');
await tap(B.square); await page.waitForTimeout(330); await st('Square (combo 2)');
await tap(B.triangle); await page.waitForTimeout(330); await st('Triangle (chain)');
await page.waitForTimeout(1400);
await tap(B.circle); await page.waitForTimeout(150); await st('Circle (kick)');
await page.waitForTimeout(900);
await btn(B.l1, true); await page.waitForTimeout(220); await st('L1 held'); await btn(B.l1, false);
await page.waitForTimeout(250);
await tap(B.r1); await page.waitForTimeout(110); await st('R1 (dodge)');
await page.waitForTimeout(600);
await tap(B.left); await page.waitForTimeout(500); await st('D-pad left (weapon)');
await tap(B.square); await page.waitForTimeout(250); await st('Square with 2nd weapon');
await page.waitForTimeout(1300);
await tap(B.right); await page.waitForTimeout(200); await st('D-pad right (arm)');
await tap(B.r2); await page.waitForTimeout(400); await st('R2 (summon)');
await page.waitForTimeout(1800);
await tap(B.options); await page.waitForTimeout(300); await st('Options (pause)');
await tap(B.cross); await page.waitForTimeout(300); await st('Cross (resume)');
await axes([0, 0, 1, 0]); await page.waitForTimeout(500); console.log('right stick camera yaw:', await page.evaluate(() => game.camYaw.toFixed(2))); await axes([0, 0, 0, 0]);
await browser.close();
