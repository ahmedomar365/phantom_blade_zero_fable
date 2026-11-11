// Captures the showcase frame by frame on a virtual clock (every frame is rendered, nothing is dropped) into
// build/frames/f_00001.jpg ...; tools/encode_video.py then turns them into an MP4 with Blender's encoder.
// node tools/capture.mjs [maxFrames]     env: PORT (5260), W, H (1920x1080), FPS (30), QUERY
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const PORT = process.env.PORT || 5260, W = Number(process.env.W || 1920), H = Number(process.env.H || 1080), FPS = Number(process.env.FPS || 30);
const MAX = Number(process.argv[2] || 6000), QUERY = process.env.QUERY || 'demo=1&q=2&glyphs=ps';
fs.rmSync('build/frames', { recursive: true, force: true });
fs.mkdirSync('build/frames', { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-angle=d3d11', '--ignore-gpu-blocklist', '--enable-gpu', '--mute-audio'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.addInitScript(() => {
  // the page's clock, animation frames and timers all run on a virtual time that only __step() advances
  let t = 0, id = 1;
  const timers = [], st = window.setTimeout.bind(window);
  performance.now = () => t;
  window.requestAnimationFrame = (cb) => { (window.__rafs = window.__rafs || []).push(cb); return id++; };
  window.cancelAnimationFrame = () => {};
  window.setTimeout = (fn, ms = 0, ...a) => { if (ms < 5) return st(fn, ms, ...a); timers.push({ due: t + ms, fn, a }); return id++; };
  window.__step = (ms) => {
    t += ms;
    for (let i = timers.length - 1; i >= 0; i--) if (timers[i].due <= t) { const x = timers.splice(i, 1)[0]; x.fn(...x.a); }
    const r = window.__rafs || []; window.__rafs = [];
    for (const cb of r) cb(t);
    return window.game ? window.game.state : 'boot';
  };
});
await page.goto(`http://localhost:${PORT}/?${QUERY}`);
const cdp = await page.context().newCDPSession(page);
await cdp.send('Animation.enable');
const step = () => page.evaluate((ms) => window.__step(ms), 1000 / FPS);
// loading: keep the virtual clock ticking until the fight scene exists
for (let i = 0; i < 4000; i++) { const s = await step(); if (s !== 'boot' && s !== 'load') break; await page.waitForTimeout(20); }
console.log('loaded, capturing at', W + 'x' + H, FPS, 'fps');
let n = 0, tail = -1, t0 = Date.now(), rate = 0.3;
await cdp.send('Animation.setPlaybackRate', { playbackRate: rate });
while (n < MAX) {
  const state = await step();
  const shot = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 93, optimizeForSpeed: true });
  n++;
  fs.writeFileSync(`build/frames/f_${String(n).padStart(5, '0')}.jpg`, Buffer.from(shot.data, 'base64'));
  if (n % 60 === 0) {                              // keep CSS animations in step with the virtual clock
    const per = (Date.now() - t0) / n;
    rate = Math.min(1, (1000 / FPS) / per);
    await cdp.send('Animation.setPlaybackRate', { playbackRate: rate });
    if (n % 300 === 0) console.log(n, 'frames', state, per.toFixed(0) + ' ms/frame');
  }
  if (state === 'victory' && tail < 0) tail = n + FPS * 5;      // hold the result screen for five seconds
  if (tail > 0 && n >= tail) break;
}
console.log('done', n, 'frames', ((Date.now() - t0) / 1000).toFixed(0) + ' s', 'err:', await page.evaluate(() => document.getElementById('err').textContent.slice(0, 300)));
await browser.close();
