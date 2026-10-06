(function () {
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function clean(s) { return ((s || '') + '').replace(/\s+/g, ' ').trim(); }
  function deepAll(root, sel, out) {
    out = out || [];
    if (!root) return out;
    try { var h = root.querySelectorAll(sel); for (var i = 0; i < h.length; i++) out.push(h[i]); } catch (e) {}
    try { var a = root.querySelectorAll('*'); for (var j = 0; j < a.length; j++) { if (a[j].shadowRoot) deepAll(a[j].shadowRoot, sel, out); } } catch (e) {}
    return out;
  }
  function vis(e) { return e && e.offsetParent !== null; }
  function findRowContainer() {
    var inputs = deepAll(document, 'input', []).filter(function (i) { return /搜索类别/.test(i.placeholder || ''); });
    if (!inputs.length) return null;
    var node = inputs[0], best = null;
    for (var k = 0; k < 8 && node; k++) {
      var t = node.textContent || '';
      if (t.indexOf('Automotive') >= 0 && t.length < 60000) best = node;
      node = node.parentElement;
    }
    return best;
  }
  var out = { url: location.href, rounds: [], items: [], sample: null };
  var chain = Promise.resolve();

  chain = chain.then(function () {
    var els = deepAll(document, '[data-takt-id="button.product_categories_card_change.edit"]', []);
    var t = null;
    els.forEach(function (e) { if (e.tagName.toLowerCase() === 'button') t = e; });
    t = t || els[0];
    if (!t) { out.error = 'trigger not found'; return null; }
    try { t.click(); } catch (e) {}
    return sleep(2600);
  });

  chain = chain.then(function () {
    var panel = findRowContainer();
    if (!panel) { out.error = 'panel not found'; return null; }
    out.panelTag = panel.tagName.toLowerCase() + '.' + ((panel.className || '') + '').split(' ')[0];
    out.panelTextLen = (panel.textContent || '').length;

    var expandAll = function (round) {
      if (round > 9) return Promise.resolve();
      var exps = deepAll(panel, '[aria-expanded="false"], [aria-expanded=false]', []).filter(vis);
      var before = (panel.textContent || '').length;
      if (!exps.length) { out.rounds.push({ round: round, expanded: 0, note: 'no collapsed nodes left', len: before }); return Promise.resolve(); }
      var n = 0;
      for (var i = 0; i < exps.length && i < 40; i++) {
        if (exps[i].tagName === 'INPUT' || exps[i].tagName === 'A') continue;
        try { exps[i].click(); n++; } catch (e) {}
      }
      out.rounds.push({ round: round, expanded: n, lenBefore: before });
      return sleep(1700).then(function () {
        var after = (panel.textContent || '').length;
        out.rounds[out.rounds.length - 1].lenAfter = after;
        if (after === before && n === 0) return null;
        return expandAll(round + 1);
      });
    };
    return expandAll(1).then(function () {
      // 结构采样
      var nodes = [];
      (function walk(root, depth) {
        if (depth > 14 || nodes.length > 34) return;
        var kids = root.children || [];
        for (var i = 0; i < kids.length && nodes.length < 34; i++) {
          var e = kids[i];
          var t = clean(e.innerText);
          nodes.push({
            d: depth, tag: e.tagName.toLowerCase(),
            cls: ((e.className || '') + '').split(' ')[0],
            role: e.getAttribute('role') || '',
            level: e.getAttribute('aria-level') || '',
            exp: e.getAttribute('aria-expanded'),
            txt: t.slice(0, 40)
          });
          if (e.shadowRoot) walk(e.shadowRoot, depth + 1);
          walk(e, depth + 1);
        }
      })(panel, 0);
      out.sample = nodes;

      // 全量行（带层级推断）
      var rows = deepAll(panel, '[role="treeitem"], li, [aria-level]', []);
      if (rows.length < 5) rows = deepAll(panel, 'div', []).filter(function (e) { return e.getAttribute('aria-expanded') !== null; });
      var uniq = [];
      rows.forEach(function (r) { if (uniq.indexOf(r) < 0 && vis(r)) uniq.push(r); });
      out.rowCount = uniq.length;
      out.items = uniq.map(function (r) {
        var exp = r.getAttribute('aria-expanded');
        var cb = null;
        try { var c = r.querySelector('input[type="checkbox"]'); if (c) cb = c.checked; } catch (e) {}
        return {
          level: r.getAttribute('aria-level') || '',
          role: r.getAttribute('role') || '',
          exp: exp === null ? '' : exp,
          checked: cb,
          txt: clean(r.innerText).slice(0, 60)
        };
      }).slice(0, 400);
      return null;
    });
  });

  chain = chain.then(function () {
    var panel = findRowContainer();
    if (panel) {
      var c = deepAll(panel, 'button,a,[role="button"]', []).filter(function (e) { return clean(e.innerText) === '取消' && vis(e); });
      if (c.length) { try { c[0].click(); } catch (e) {} out.close = 'panel-cancel'; }
      else { out.close = 'not-closed'; }
    }
    return sleep(1500);
  }).then(function () { return JSON.stringify(out); });
  return chain;
})()
