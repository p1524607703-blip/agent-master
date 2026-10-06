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
    return (w.id || '').replace(/^.*tree-/, '');
  }

  var out = { url: location.href, rounds: [] };
  var clicked = {}, round = 0;

  function step() {
    round++;
    if (round > 40) { out.rounds.push({ round: round, stop: 'max' }); return Promise.resolve(); }
    var todo = deepAll(document, 'i[data-test-id^="option-expander-"]', []).filter(function (e) {
      if (e.offsetParent === null) return false;
      var key = e.getAttribute('data-test-id') || '';
      return !clicked[key];
    });
    if (!todo.length) { out.rounds.push({ round: round, clicked: 0, stop: 'all expanded' }); return Promise.resolve(); }
    todo.forEach(function (e) { clicked[e.getAttribute('data-test-id') || ('?')] = 1; try { e.click(); } catch (x) {} });
    return sleep(1800).then(function () {
      out.rounds.push({ round: round, clicked: todo.length, nodes: wrappers().length });
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
        lv: levelOf(w), id: nodeId(w),
        name: (w.getAttribute('data-test-id') || '').replace('option-wrapper-', ''),
        group: /option-parent/.test(cls), sel: cb !== null, ck: cb
      };
    });
    // 顺带试取中文翻译表
    return fetch('https://d2ybzpzm1pr0am.cloudfront.net/translations/translation-zh.json')
      .then(function (r) { return r.text(); })
      .then(function (t) {
        out.zhLen = t.length;
        var probes = ['Automotive', 'Beauty & Fashion', 'Shopping', 'Pets', 'Real Estate'];
        out.zhHits = probes.map(function (k) {
          var i = t.indexOf('"' + k + '"');
          return { k: k, idx: i, ctx: i < 0 ? null : t.slice(i, i + 160) };
        });
        return JSON.stringify(out);
      })
      .catch(function (e) {
        out.zhErr = String(e && e.message || e);
        return JSON.stringify(out);
      });
  });
})()
