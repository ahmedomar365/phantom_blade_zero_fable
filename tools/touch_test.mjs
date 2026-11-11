// Drives the game as a phone in landscape (touch events, multi-touch) and prints what the hero does.
// node tools/touch_test.mjs   (server on PORT, default 5260; BASE overrides the origin)
import { chromium } from 'playwright-core';
import fs from 'node:fs';
const BASE = process.env.BASE || `http://localhost:${process.env.PORT || 5260}`;
fs.mkdirSync('build/shots', { recursive: true });
const UA = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36';
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-angle=d3d11', '--ignore-gpu-blocklist', '--enable-gpu', '--mute-audio'] });
const ctx = await browser.newContext({ viewport: { width: 915, height: 412 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, userAgent: UA });
const page = await ctx.newPage();
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.goto(`${BASE}/?god=1`);
await page.waitForFunction(() => window.gameReady, null, { timeout: 120000 });
const cdp = await ctx.newCDPSession(page);
const st = async (label) => console.log(label.padEnd(34), JSON.stringify(await page.evaluate(() => { const g = game, h = g.hero; return { game: g.state, paused: !!g.paused, dev: g.input.device, q: g.q, hero: h.state, clip: h.a.clip, weapon: h.weapon, arm: h.spirit && h.spirit.name, z: +h.pos.z.toFixed(1), pads: document.getElementById('touch').classList.contains('on'), fps: Math.round(g.fpsAvg) }; })));
const mid = (sel) => page.evaluate((s) => { const r = document.querySelector(s).getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }, sel);
let pts = [];
const send = (type) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: pts.map((p) => ({ x: p.x, y: p.y, id: p.id, radiusX: 8, radiusY: 8, force: 1 })) });
const down = async (id, p) => { pts.push({ id, x: p.x, y: p.y }); await send('touchStart'); };
const move = async (id, p) => { const t = pts.find((q) => q.id === id); t.x = p.x; t.y = p.y; await send('touchMove'); };
// lifting one finger while others stay down is sent as a move with the remaining points (CDP's touchEnd must be empty)
const up = async (id) => { pts = pts.filter((q) => q.id !== id); await send(pts.length ? 'touchMove' : 'touchEnd'); };
const tap = async (sel, hold = 70, id = 9) => { const p = await mid(sel); await down(id, p); await page.waitForTimeout(hold); await up(id); };

await st('title (phone, landscape)');
await page.screenshot({ path: 'build/shots/touch_title.png' });
await tap('#ovTag'); await page.waitForTimeout(250);
console.log('difficulty after tapping the tag:', await page.evaluate(() => document.getElementById('ovTag').textContent));
await tap('#ovTag'); await page.waitForTimeout(200);
await tap('#ovGo'); await page.waitForTimeout(1700); await st('tap "Draw your sword"');
await down(5, { x: 600, y: 200 }); await page.waitForTimeout(60); await up(5); await page.waitForTimeout(1000); await st('tap the scene (skips intro)');
await down(1, { x: 160, y: 300 }); await move(1, { x: 160, y: 262 }); await move(1, { x: 160, y: 225 }); await page.waitForTimeout(900); await st('left thumb pushed up 0.9 s');
await tap('#tAtk'); await page.waitForTimeout(140); await st('ATTACK while still moving');
await tap('#tAtk'); await page.waitForTimeout(330); await st('ATTACK again (combo)');
await up(1);
await tap('#tHeavy'); await page.waitForTimeout(330); await st('HEAVY (chain)');
await page.waitForTimeout(1300);
await page.screenshot({ path: 'build/shots/touch_fight.png' });
await tap('#tKick'); await page.waitForTimeout(150); await st('KICK');
await page.waitForTimeout(800);
{ const p = await mid('#tGuard'); await down(2, p); await page.waitForTimeout(220); await st('GUARD held'); await up(2); }
await page.waitForTimeout(250);
await tap('#tDodge'); await page.waitForTimeout(110); await st('DODGE');
await page.waitForTimeout(600);
await tap('#armW'); await page.waitForTimeout(550); await st('tap weapon panel');
await tap('#armS'); await page.waitForTimeout(200); await st('tap arm panel');
await tap('#tArm'); await page.waitForTimeout(400); await st('ARM (summon)');
await page.waitForTimeout(1500);
await tap('#tPause'); await page.waitForTimeout(300); await st('pause button');
await page.screenshot({ path: 'build/shots/touch_pause.png' });
await tap('#ovGo'); await page.waitForTimeout(300); await st('tap Resume');
await ctx.close();
// portrait: the rotate notice must cover the game
const c2 = await browser.newContext({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, userAgent: UA });
const p2 = await c2.newPage();
await p2.goto(`${BASE}/?q=0`);
await p2.waitForTimeout(1500);
console.log('portrait: rotate notice shown =', await p2.evaluate(() => getComputedStyle(document.getElementById('rotate')).display !== 'none'));
await p2.screenshot({ path: 'build/shots/touch_portrait.png' });
await browser.close();
