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
  function levelOf(w) {
    var n = 0, p = w.parentElement;
    while (p) { var t = p.getAttribute ? (p.getAttribute('data-test-id') || '') : ''; if (t.indexOf('option-wrapper-') === 0) n++; p = p.parentElement; }
    return n;
  }
  function nodeId(w) {
    var v = w.getAttribute('data-takt-value') || '';
    try { var o = JSON.parse(v); if (o && o.value !== undefined) return String(o.value); } catch (e) {}
    return (w.id || '') ? (w.id || '').replace(/^.*tree-/, '') : '';
  }
  var out = { url: location.href, rounds: [] };
  var stable = 0, last = 0, round = 0;

  function step() {
    round++;
    if (round > 40) { out.rounds.push({ round: round, stop: 'max rounds' }); return Promise.resolve(); }
    var ex = deepAll(document, 'i[data-test-id^="option-expander-"]', []).filter(function (e) { return e.offsetParent !== null; });
    for (var i = 0; i < ex.length; i++) { try { ex[i].click(); } catch (e) {} }
    return sleep(2000).then(function () {
      var n = wrappers().length;
      var grew = (n !== last);
      stable = grew ? 0 : stable + 1;
      out.rounds.push({ round: round, clicked: ex.length, nodes: n, grew: grew });
      last = n;
      if (stable >= 3) return null;
      return step();
    });
  }

  return step().then(function () {
    var ws = wrappers();
    out.total = ws.length;
    out.nodes = ws.map(function (w) {
      var cls = (w.className || '') + '';
      var cb = null; try { var c = w.querySelector('input[type="checkbox"]'); if (c) cb = c.checked === true; } catch (e) {}
      return {
        lv: levelOf(w),
        id: nodeId(w),
        name: (w.getAttribute('data-test-id') || '').replace('option-wrapper-', ''),
        group: /option-parent/.test(cls),
        sel: cb !== null,
        ck: cb
      };
    });
    return JSON.stringify(out);
  });
})()
