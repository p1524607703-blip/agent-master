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
  function flat() {
    return wrappers().map(function (w) {
      var cls = (w.className || '') + '';
      var id = null; try { id = JSON.parse(w.getAttribute('data-takt-value') || '{}').value; } catch (e) {}
      return {
        name: (w.getAttribute('data-test-id') || '').replace('option-wrapper-', ''),
        id: id,
        group: /option-parent/.test(cls),
        collapsed: /option-collapsed/.test(cls),
        sel: !!w.querySelector('input[type="checkbox"]')
      };
    });
  }

  var out = { url: location.href, map: {}, order: [] };
  var baseline = flat();
  out.baselineCount = baseline.length;

  var groupsCollapsed = [];
  wrappers().forEach(function (w) {
    var cls = (w.className || '') + '';
    if (/option-parent/.test(cls) && /option-collapsed/.test(cls)) {
      groupsCollapsed.push((w.getAttribute('data-test-id') || '').replace('option-wrapper-', ''));
    }
  });
  out.collapsedGroups = groupsCollapsed;

  var prevNames = baseline.map(function (x) { return x.name; });

  function step(i) {
    if (i >= groupsCollapsed.length) return Promise.resolve();
    var gname = groupsCollapsed[i];
    var w = null;
    wrappers().forEach(function (x) { if ((x.getAttribute('data-test-id') || '') === 'option-wrapper-' + gname) w = x; });
    if (!w) { out.map[gname] = { error: 'wrapper not found' }; return step(i + 1); }
    var e = w.querySelector('i[data-test-id^="option-expander-"]');
    if (!e) { out.map[gname] = { error: 'no expander' }; return step(i + 1); }
    try { e.click(); } catch (x) {}
    return sleep(1500).then(function () {
      var now = flat().map(function (x) { return x.name; });
      var added = now.filter(function (n) { return prevNames.indexOf(n) < 0; });
      out.map[gname] = { added: added };
      prevNames = now;
      return step(i + 1);
    });
  }

  return step(0).then(function () {
    out.finalFlat = flat();
    out.finalCount = out.finalFlat.length;
    return JSON.stringify(out);
  });
})()
