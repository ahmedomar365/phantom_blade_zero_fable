// node tools/shot.mjs "<query>" <name> [wait,wait,...] [evalJs]   (env: PAGE=envtest.html|index.html, PORT, W, H, DPR)
// Opens the page in headless Chrome (real GPU), waits for window.envReady (or window.game.ready), then for each
// wait (ms) saves build/shots/<name>_<i>.png and prints fps + whatever window.debugState() returns.
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const [, , query = '', name = 'shot', waits = '1500', evalJs = ''] = process.argv;
const PORT = process.env.PORT || 5260, PAGE = process.env.PAGE || 'envtest.html';
fs.mkdirSync('build/shots', { recursive: true });
const browser = await chromium.launch({
  channel: 'chrome', headless: true,
  args: ['--use-angle=d3d11', '--ignore-gpu-blocklist', '--enable-gpu', '--mute-audio', '--disable-frame-rate-limit', '--disable-gpu-vsync'],
});
const page = await browser.newPage({ viewport: { width: Number(process.env.W || 1600), height: Number(process.env.H || 900) }, deviceScaleFactor: Number(process.env.DPR || 1) });
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) console.log('[console]', m.type(), m.text().slice(0, 500)); });
page.on('response', (r) => { if (r.status() >= 400) console.log('[http]', r.status(), r.url()); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message, (e.stack || '').split('\n').slice(0, 4).join(' | ')));
await page.goto(`http://localhost:${PORT}/${PAGE}?${query}`);
try {
  await page.waitForFunction(() => window.envReady || (window.game && window.game.ready), null, { timeout: 90000 });
} catch (e) { console.log('LOAD TIMEOUT'); }
if (evalJs) console.log('eval:', JSON.stringify(await page.evaluate(evalJs)));
let i = 0;
for (const w of waits.split(',')) {
  await page.waitForTimeout(Number(w));
  const info = await page.evaluate(() => ({ fps: window.envFps, state: window.debugState ? window.debugState() : null }));
  const f = `build/shots/${name}_${i++}.png`;
  await page.screenshot({ path: f });
  console.log(f, JSON.stringify(info));
}
await browser.close();
