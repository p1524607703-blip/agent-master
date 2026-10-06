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
  function wrappers() { return deepAll(document, '[data-test-id^="option-wrapper-"]', []); }
  function expandersCollapsed() {
    var out = [];
    wrappers().forEach(function (w) {
      var cls = (w.className || '') + '';
      if (/option-collapsed/.test(cls)) {
        var i = w.querySelector('i[data-test-id^="option-expander-"]');
        if (i && i.offsetParent !== null) out.push(i);
      }
    });
    return out;
  }
  function levelOf(w) {
    var n = 0, p = w.parentElement;
    while (p) { if (p.getAttribute && (p.getAttribute('data-test-id') || '').indexOf('option-wrapper-') === 0) n++; p = p.parentElement; }
    return n;
  }
  function dump() {
    var ws = wrappers();
    return ws.map(function (w) {
      var name = (w.getAttribute('data-test-id') || '').replace('option-wrapper-', '');
      var id = (w.id || '').replace('d16g-rodeo-line-item--product-categories-options-tree-', '');
      var cls = (w.className || '') + '';
      var cb = null;
      try { var c = w.querySelector('input[type="checkbox"]'); if (c) cb = c.checked === true; } catch (e) {}
      return {
        level: levelOf(w),
        id: id,
        name: name,
        kind: /option-parent/.test(cls) ? 'parent' : (/option-leaf/.test(cls) ? 'leaf' : '?'),
        collapsed: /option-collapsed/.test(cls),
        checked: cb
      };
    });
  }

  var out = { url: location.href, rounds: [] };
  var chain = Promise.resolve();
  var round = function (n) {
    if (n > 12) return Promise.resolve();
    var ex = expandersCollapsed();
    if (!ex.length) { out.rounds.push({ round: n, expanded: 0, note: 'done' }); return Promise.resolve(); }
    var before = wrappers().length;
    for (var i = 0; i < ex.length; i++) { try { ex[i].click(); } catch (e) {} }
    return sleep(1500).then(function () {
      var after = wrappers().length;
      out.rounds.push({ round: n, expanded: ex.length, before: before, after: after });
      return round(n + 1);
    });
  };
  chain = chain.then(function () { return round(1); });
  chain = chain.then(function () {
    out.total = wrappers().length;
    out.nodes = dump();
    return JSON.stringify(out);
  });
  return chain;
})()
