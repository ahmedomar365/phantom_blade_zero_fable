// node tools/play.mjs "<query>" <name> <wait,wait,...> [evalJs]
// Opens the game in headless Chrome (real GPU), waits each interval (ms), saves build/shots/<name>_<i>.png
// and prints the fight state. Query flags: auto=1 (bot plays), skip=1 (no intro), god=1, phase=2, hp=0.55, q=0..2, bot=0..1.
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const [, , query = '', name = 'play', waits = '3000', evalJs = ''] = process.argv;
const PORT = process.env.PORT || 5260;
fs.mkdirSync('build/shots', { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-angle=d3d11', '--ignore-gpu-blocklist', '--enable-gpu', '--mute-audio', '--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage({ viewport: { width: Number(process.env.W || 1600), height: Number(process.env.H || 900) }, deviceScaleFactor: Number(process.env.DPR || 1) });
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) console.log('[console]', m.type(), m.text().slice(0, 300)); });
page.on('response', (r) => { if (r.status() >= 400) console.log('[http]', r.status(), r.url()); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message, (e.stack || '').split('\n').slice(0, 4).join(' | ')));
await page.goto(`${process.env.BASE || `http://localhost:${PORT}`}/?${query}`);
try { await page.waitForFunction(() => window.gameReady, null, { timeout: 90000 }); } catch (e) { console.log('LOAD TIMEOUT', await page.evaluate(() => document.getElementById('err').textContent)); }
if (process.env.CLICK) await page.click('#ovGo').catch(() => {});
if (evalJs) console.log('eval:', JSON.stringify(await page.evaluate(evalJs)));
let i = 0;
for (const w of waits.split(',')) {
  await page.waitForTimeout(Number(w));
  const info = await page.evaluate(() => { const g = window.game; return { state: g.state, fps: Math.round(g.fpsAvg), hero: g.hero && [g.hero.state, Math.round(g.hero.hp), g.hero.a.clip], boss: g.boss && [g.boss.state, g.boss.atk, Math.round(g.boss.hp), Math.round(g.boss.posture), 'p' + g.boss.phase], stats: g.stats && [g.stats.parries, g.stats.dodges, Math.round(g.stats.taken)], demo: g.demo ? [g.demo.i, g.demo.steps[g.demo.i] && g.demo.steps[g.demo.i].cap, +g.demo.t.toFixed(1)] : undefined, w: g.hero && g.hero.weapon, qi: g.hero && Math.round(g.hero.qi), err: document.getElementById('err').textContent.slice(0, 400) }; });
  const f = `build/shots/${name}_${i++}.png`;
  await page.screenshot({ path: f });
  console.log(f, JSON.stringify(info));
}
await browser.close();
