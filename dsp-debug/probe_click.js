(function () {
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function clean(s) { return ((s || '') + '').replace(/\s+/g, ' ').trim(); }
  function deepAll(root, sel, out) {
    out = out || [];
    if (!root) return out;
    try { var h = root.querySelectorAll(sel); for (var i = 0; i < h.length; i++) out.push(h[i]); } catch (e) {}
    try { var all = root.querySelectorAll('*'); for (var j = 0; j < all.length; j++) { if (all[j].shadowRoot) deepAll(all[j].shadowRoot, sel, out); } } catch (e) {}
    return out;
  }
  function labelOf(el) {
    var cands = [];
    if (el.tagName && el.tagName.toLowerCase() !== 'input') cands.push(el);
    var p = el.parentElement;
    for (var k = 0; k < 3 && p; k++) { cands.push(p); p = p.parentElement; }
    for (var i = 0; i < cands.length; i++) {
      var t = ((cands[i].innerText || '') + '').trim();
      if (!t || t.length > 240) continue;
      var lines = t.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
      if (lines.length >= 2) return lines[0].slice(0, 60);
      if (lines.length === 1 && t.length < 70) return lines[0];
    }
    return '?';
  }
  var MT = 'DSP_CAMPAIGN_LEVEL_MEDIA_TYPE_container';
  function inputs() { return deepAll(document.getElementById(MT), 'input[type="checkbox"]', []); }
  function state() { return inputs().map(function (e) { return labelOf(e) + '=' + (e.checked === true); }); }
  function findInput(name) { var a = inputs(); for (var i = 0; i < a.length; i++) if (labelOf(a[i]) === name) return a[i]; return null; }
  function composed(o) { var d = { bubbles: true, cancelable: true, composed: true, view: window, button: 0 }; for (var k in (o || {})) d[k] = o[k]; return d; }
  function seq(el, opts) {
    try {
      el.dispatchEvent(new PointerEvent('pointerdown', composed(opts)));
      el.dispatchEvent(new MouseEvent('mousedown', composed(opts)));
      el.dispatchEvent(new PointerEvent('pointerup', composed(opts)));
      el.dispatchEvent(new MouseEvent('mouseup', composed(opts)));
      el.dispatchEvent(new MouseEvent('click', composed(opts)));
    } catch (e) {}
  }

  var out = { url: location.href, chain: [], trials: [] };
  var el = findInput('在线视频');
  if (!el) { out.error = 'input not found'; return JSON.stringify(out); }

  // 记录祖先链
  var p = el, lvl = 0;
  while (p && lvl < 6) {
    var cs = null;
    try { cs = window.getComputedStyle(p); } catch (e) {}
    out.chain.push({
      lvl: lvl, tag: p.tagName ? p.tagName.toLowerCase() : '?',
      cls: ((p.className || '') + '').slice(0, 40),
      role: p.getAttribute ? (p.getAttribute('role') || '') : '',
      pe: cs ? cs.pointerEvents : '', dis: p.disabled === true,
      outer: (p.outerHTML || '').slice(0, 110)
    });
    p = p.parentElement; lvl++;
  }

  // 依次尝试不同层级 / 不同事件序列，看哪一个能真正切换状态
  var levels = [];
  var q = el;
  for (var i = 0; i < 5 && q; i++) { levels.push(q); q = q.parentElement; }
  var strats = [
    { name: 'input.click()', run: function (t) { try { t.click(); } catch (e) {} } },
    { name: 'input seq(composed)', run: function (t) { seq(t, {}); } },
    { name: 'closest label → click', run: function (t) { var l = t.closest ? t.closest('label') : null; if (l) l.click(); else try { t.click(); } catch (e) {} } }
  ];

  var chain = Promise.resolve();
  strats.forEach(function (st) {
    levels.forEach(function (tgt, idx) {
      chain = chain.then(function () {
        if (findInput('在线视频').checked === true) { out.trials.push({ strat: st.name, lvl: idx, skip: 'already selected' }); return null; }
        st.run(tgt);
        return sleep(1300).then(function () {
          var st2 = state();
          out.trials.push({ strat: st.name, lvl: idx, tag: tgt.tagName.toLowerCase(), cls: ((tgt.className || '') + '').slice(0, 24), after: st2, worked: /在线视频=true/.test(st2.join(',')) });
        });
      });
    });
  });
  chain = chain.then(function () {
    // 恢复
    var cur = state().join(',');
    var box = findInput('展示');
    if (box && box.checked !== true) { seq(box, {}); return sleep(1400); }
  }).then(function () { out.final = state(); return JSON.stringify(out); });
  return chain;
})()
