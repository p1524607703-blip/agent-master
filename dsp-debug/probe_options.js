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
  function deepText(root, out) {
    out = out || [];
    if (!root) return out;
    var kids = root.children || [];
    for (var i = 0; i < kids.length; i++) {
      var e = kids[i];
      if (e.children.length === 0) { var t = clean(e.innerText); if (t && t.length < 40) out.push(t); }
      if (e.shadowRoot) deepText(e.shadowRoot, out);
      deepText(e, out);
    }
    return out;
  }
  function uniq(a) { return a.filter(function (v, i) { return a.indexOf(v) === i; }); }
  var out = { url: location.href, dropdowns: [] };
  var base = null;

  function diff(before, after) {
    var s = {}; before.forEach(function (x) { s[x] = 1; });
    return after.filter(function (x) { return !s[x]; });
  }
  function esc() { try { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, composed: true })); } catch (e) {} }

  var chain = Promise.resolve();
  chain = chain.then(function () { base = uniq(deepText(document.body, [])); return null; });

  function probeTrigger(name, finder) {
    chain = chain.then(function () {
      var el = finder();
      if (!el) { out.dropdowns.push({ name: name, error: 'trigger not found' }); return null; }
      var pre = uniq(deepText(document.body, []));
      try { el.click(); } catch (e) {}
      return sleep(1600).then(function () {
        var post = uniq(deepText(document.body, []));
        out.dropdowns.push({ name: name, trigger: clean(el.innerText).slice(0, 30), items: diff(pre, post) });
        esc();
        return sleep(700);
      });
    });
  }

  var G = 'DSP_CAMPAIGN_GENERAL_SECTION_MFE_container';
  var DC = 'DSP_CAMPAIGN_MGMT_DELIVERY_CAP_MFE_container';
  var FQ = 'FM_ORDER_FREQUENCY_SETTINGS_container';

  probeTrigger('国家/地区', function () {
    var b = deepAll(document.getElementById(G), 'button', []);
    for (var i = 0; i < b.length; i++) { var t = clean(b[i].innerText); if (t === '美国' || /美国/.test(t) && t.length < 6) return b[i]; }
    return null;
  });
  probeTrigger('预算上限-周期', function () {
    var b = deepAll(document.getElementById(DC), 'button', []);
    for (var i = 0; i < b.length; i++) { if (/每日|每月/.test(clean(b[i].innerText))) return b[i]; }
    return null;
  });
  probeTrigger('频率-单位', function () {
    var b = deepAll(document.getElementById(FQ), 'button', []);
    for (var i = 0; i < b.length; i++) { if (/用户|设备/.test(clean(b[i].innerText))) return b[i]; }
    return null;
  });
  probeTrigger('广告主域名', function () {
    var b = deepAll(document.getElementById(G), 'button', []);
    for (var i = 0; i < b.length; i++) { var t = clean(b[i].innerText); if (/New|新增|广告主域名/.test(t) && t.length < 40) return b[i]; }
    return null;
  });

  chain = chain.then(function () { return JSON.stringify(out); });
  return chain;
})()
