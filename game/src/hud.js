const $ = (id) => document.getElementById(id);

export class Hud {
  constructor() {
    this.el = { hud: $('hud'), boss: $('boss'), bossFill: $('bossFill'), bossLag: $('bossLag'), post: $('post'), postFill: $('postFill'),
      heroFill: $('heroFill'), heroLag: $('heroLag'), guard: $('guard'), guardFill: $('guardFill'), heals: [...$('heals').querySelectorAll('b')],
      prompt: $('prompt'), pops: $('pops'), danger: $('danger'), card: $('card'), word: $('fightWord'), keys: $('keys'),
      ov: $('overlay'), ovHan: $('ovHan'), ovTitle: $('ovTitle'), ovTag: $('ovTag'), ovBody: $('ovBody'), ovKeys: $('ovKeys'), ovStats: $('ovStats'),
      ovGo: $('ovGo'), ovBar: $('ovBar'), ovBarWrap: $('ovBarWrap') };
    this._prompt = null;
  }
  show(on) { this.el.hud.classList.toggle('on', on); }
  bossShow(on) { this.el.boss.classList.toggle('on', on); }
  hero(hp, guard) {
    const s = `scaleX(${Math.max(0, hp)})`;
    this.el.heroFill.style.transform = s; this.el.heroLag.style.transform = s;
    this.el.guardFill.style.transform = `scaleX(${Math.max(0, guard)})`;
    this.el.guard.classList.toggle('low', guard < 0.3);
  }
  arms({ wGlyph, wName, refill, sGlyph, sName, sReady }) {
    const key = [wGlyph, wName, refill, sGlyph, sName, sReady].join('|');
    if (key === this._arms) return;
    this._arms = key;
    const w = document.getElementById('armW'), s = document.getElementById('armS');
    w.children[0].textContent = wGlyph; w.children[1].textContent = wName; w.children[2].textContent = refill ? '+QI' : '';
    s.style.display = sName ? 'flex' : 'none';
    s.children[0].textContent = sGlyph; s.children[1].textContent = sName || ''; s.classList.toggle('off', !sReady);
  }
  keys(rows) { this.el.keys.innerHTML = rows.map((r) => r.map(([label, g]) => `${label} <b>${g}</b>`).join(' &middot; ')).join('<br>'); }
  qiFlash() { const g = this.el.guard; g.classList.add('flash'); setTimeout(() => g.classList.remove('flash'), 400); }
  /** Closing ring round the hero: k = 1 far .. 0 at the hit; now = inside the answer window. */
  ring(x, y, k, red, now, label) {
    const r = this._ring || (this._ring = document.getElementById('ring'));
    if (k === null) { if (this._ringOn) { r.style.opacity = 0; this._ringOn = false; } return; }
    this._ringOn = true;
    r.style.opacity = 1; r.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
    r.children[1].style.transform = `scale(${(1 + k * 2.6).toFixed(3)})`;
    r.classList.toggle('red', red); r.classList.toggle('now', now);
    if (label !== this._ringLabel) { this._ringLabel = label; r.children[2].innerHTML = label; }
  }
  caption(title, sub) {
    const c = document.getElementById('demoCap');
    if (!title) { c.classList.remove('on'); return; }
    document.getElementById('demoTitle').textContent = title; document.getElementById('demoSub').innerHTML = sub || '';
    c.classList.add('on');
  }
  demoTag(on) { document.getElementById('demoTag').classList.toggle('on', on); }
  heals(n) { this.el.heals.forEach((b, i) => b.classList.toggle('used', i >= n)); }
  boss(hp, posture) {
    const s = `scaleX(${Math.max(0, hp)})`;
    this.el.bossFill.style.transform = s; this.el.bossLag.style.transform = s;
    this.el.postFill.style.transform = `scaleX(${Math.min(1, Math.max(0, posture))})`;
    this.el.post.classList.toggle('full', posture >= 1);
  }
  prompt(html) {
    if (html === this._prompt) return;
    this._prompt = html;
    this.el.prompt.classList.toggle('on', !!html);
    if (html) this.el.prompt.innerHTML = html;
  }
  popup(text, cls = 'gold') {
    const d = document.createElement('div');
    d.className = 'pop ' + cls; d.textContent = text;
    this.el.pops.replaceChildren(d);
    setTimeout(() => d.remove(), 1150);
  }
  danger(v) { this.el.danger.style.opacity = v; }
  card(on) { this.el.card.classList.toggle('on', on); }
  word(ch) { const w = this.el.word; w.textContent = ch; w.classList.remove('go'); void w.offsetWidth; w.classList.add('go'); }
  keysDim(on) { this.el.keys.classList.toggle('dim', on); }
  progress(p) { this.el.ovBar.style.width = Math.round(p * 100) + '%'; }
  overlay({ show = true, han = '朱門', title = 'Vermilion Gate', tag = '', body = '', keys = null, stats = null, go = null, onGo = null, go2 = null, onGo2 = null, bar = false } = {}) {
    const e = this.el;
    e.ov.classList.toggle('hide', !show);
    if (!show) return;
    e.ovHan.textContent = han; e.ovTitle.textContent = title; e.ovTag.textContent = tag; e.ovBody.innerHTML = body;
    e.ovKeys.innerHTML = keys ? keys.map(([k, v]) => `<div><b>${k}</b>${v}</div>`).join('') : '';
    e.ovStats.innerHTML = stats ? stats.map(([k, v]) => `<div><strong>${v}</strong>${k}</div>`).join('') : '';
    e.ovGo.style.display = go ? 'inline-block' : 'none';
    e.ovBarWrap.style.display = bar ? 'block' : 'none';
    if (go) { e.ovGo.textContent = go; e.ovGo.onclick = onGo; }
    const b2 = document.getElementById('ovGo2');
    b2.style.display = go2 ? 'inline-block' : 'none';
    if (go2) { b2.textContent = go2; b2.onclick = onGo2; }
  }
}
