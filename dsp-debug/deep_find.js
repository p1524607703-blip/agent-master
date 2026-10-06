(() => {
  // 深度遍历 light DOM + 所有 shadow root，把命中元素引用挂在 window.__DBG 上供后续点击
  const NEEDLE_A = 'Cannot read properties of undefined';
  const NEEDLE_B = '显示可选设置';
  const NEEDLE_C = '国家/地区';

  window.__DBG = window.__DBG || [];
  window.__DBG.length = 0;
  const flat = [];
  const walk = (root, depth) => {
    let els;
    try { els = root.querySelectorAll('*'); } catch (e) { return; }
    for (const el of els) {
      flat.push({ el, depth });
      if (el.shadowRoot) walk(el.shadowRoot, depth + 1);
    }
  };
  walk(document, 0);
  // 顺带把 document 自身也算进去
  flat.push({ el: document.documentElement, depth: 0 });

  const txt = e => {
    try { return (e.innerText || e.textContent || e.value || '').trim(); } catch (err) { return ''; }
  };
  const desc = e => {
    const r = e.getBoundingClientRect ? e.getBoundingClientRect() : { x: 0, y: 0, width: 0, height: 0 };
    return {
      tag: e.tagName, id: e.id || '',
      cls: String(e.className && e.className.baseVal !== undefined ? e.className.baseVal : (e.className || '')).slice(0, 70),
      role: e.getAttribute && (e.getAttribute('role') || ''),
      ariaExpanded: e.getAttribute && e.getAttribute('aria-expanded'),
      testid: e.getAttribute && (e.getAttribute('data-testid') || ''),
      text: txt(e).slice(0, 60),
      rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }
    };
  };

  const hitA = [], hitB = [], hitC = [];
  for (const { el, depth } of flat) {
    const t = txt(el);
    if (!t) continue;
    if (t.includes(NEEDLE_A)) hitA.push({ el, depth });
    if (t === NEEDLE_B || (t.length < 12 && t.includes(NEEDLE_B))) hitB.push({ el, depth });
    if (t === NEEDLE_C) hitC.push({ el, depth });
  }

  const pick = arr => {
    // 取最深的（最具体的）若干个
    const sorted = arr.slice().sort((a, b) => b.depth - a.depth);
    return sorted.slice(0, 5).map(({ el, depth }) => {
      const idx = window.__DBG.push(el) - 1;
      const rec = { idx, depth, ...desc(el) };
      rec.outerHTML = (el.outerHTML || '').slice(0, 1200);
      rec.ancestors = [];
      let p = el.parentElement || (el.getRootNode && el.getRootNode().host);
      let i = 0;
      while (p && i < 6) { rec.ancestors.push(desc(p)); p = p.parentElement || (p.getRootNode && p.getRootNode().host); i++; }
      const par = el.parentElement;
      if (par) {
        rec.parentChildren = [...par.children].map(c => ({
          tag: c.tagName, id: c.id || '', cls: String(c.className || '').slice(0, 60), text: txt(c).slice(0, 60),
          html: (c.outerHTML || '').slice(0, 500)
        })).slice(0, 12);
      }
      return rec;
    });
  };

  return JSON.stringify({
    url: location.href,
    shadowRoots: (() => { let n = 0; const walk2 = r => { try { r.querySelectorAll('*').forEach(e => { if (e.shadowRoot) { n++; walk2(e.shadowRoot); } }); } catch (e) {} }; walk2(document); return n; })(),
    counts: { errText: hitA.length, toggleText: hitB.length, countryLabel: hitC.length },
    errorEls: pick(hitA),
    toggleEls: pick(hitB),
    countryEls: pick(hitC)
  }, null, 1);
})()
