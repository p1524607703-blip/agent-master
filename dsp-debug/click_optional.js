(() => {
  const SEARCH = 'section.campaign.optional_settings.expand';
  const txt = e => { try { return (e.innerText || e.textContent || '').trim(); } catch (x) { return ''; } };

  const flat = [];
  const walk = r => { try { r.querySelectorAll('*').forEach(e => { flat.push(e); if (e.shadowRoot) walk(e.shadowRoot); }); } catch (e) {} };
  walk(document);

  const btns = flat.filter(e => e.tagName === 'BUTTON' && e.getAttribute && e.getAttribute('data-takt-id') === SEARCH);
  const rec = { found: btns.length, ctxHasDbg: typeof window.__DBG !== 'undefined', before: null, after: null, clicked: false };

  if (!btns.length) return JSON.stringify(rec);

  const btn = btns[0];
  rec.before = { text: txt(btn), ariaExpanded: btn.getAttribute('aria-expanded'), rect: (r => ({ x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }))(btn.getBoundingClientRect()) };

  // 记录 extender 区域点击前状态
  const ext = flat.find(e => e.id === 'general-section-extender');
  const extW = flat.find(e => e.id === 'general-section-extender-wrapper');
  rec.beforeExtender = ext ? { display: getComputedStyle(ext).display, h: Math.round(ext.getBoundingClientRect().height), text: txt(ext).slice(0, 120) } : null;
  rec.beforeWrapper = extW ? { h: Math.round(extW.getBoundingClientRect().height), overflow: getComputedStyle(extW).overflow } : null;

  // 真实点击序列
  const opts = { bubbles: true, cancelable: true, view: window, button: 0 };
  try { btn.dispatchEvent(new PointerEvent('pointerdown', opts)); } catch (e) {}
  btn.dispatchEvent(new MouseEvent('mousedown', opts));
  try { btn.dispatchEvent(new PointerEvent('pointerup', opts)); } catch (e) {}
  btn.dispatchEvent(new MouseEvent('mouseup', opts));
  btn.dispatchEvent(new MouseEvent('click', opts));
  rec.clicked = true;

  rec.after = { text: txt(btn), ariaExpanded: btn.getAttribute('aria-expanded') };
  if (ext) rec.afterExtender = { display: getComputedStyle(ext).display, h: Math.round(ext.getBoundingClientRect().height), text: txt(ext).slice(0, 300) };
  if (extW) rec.afterWrapper = { h: Math.round(extW.getBoundingClientRect().height) };

  return JSON.stringify(rec, null, 1);
})()
