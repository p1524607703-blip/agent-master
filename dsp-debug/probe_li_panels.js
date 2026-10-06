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
  function deepText(root, out) {
    out = out || [];
    if (!root) return out;
    var k = root.children || [];
    for (var i = 0; i < k.length; i++) {
      var e = k[i];
      if (e.children.length === 0) { var t = clean(e.innerText); if (t && t.length < 90) out.push(t); }
      if (e.shadowRoot) deepText(e.shadowRoot, out);
      deepText(e, out);
    }
    return out;
  }
  function uniq(a) { return a.filter(function (v, i) { return a.indexOf(v) === i; }); }
  var PAGE_CANCEL = 'dspcreate_lineitem_save_cancel_button_trigger';

  function getTrigger(takt) {
    var els = deepAll(document, '[data-takt-id="' + takt + '"]', []);
    var b = null;
    els.forEach(function (e) { if (e.tagName.toLowerCase() === 'button' && clean(e.innerText) === '更改') b = e; });
    if (b) return b;
    els.forEach(function (e) { if (e.tagName.toLowerCase() === 'button' && b === null) b = e; });
    return b || els[0] || null;
  }
  function closePanel(takt) {
    var same = deepAll(document, '[data-takt-id="' + takt + '"]', []).filter(function (e) { return clean(e.innerText) === '取消' && e.offsetParent !== null; });
    if (same.length) { try { same[0].click(); return 'same-takt'; } catch (e) {} }
    var cands = deepAll(document, 'button,a,[role="button"]', []).filter(function (e) {
      if (clean(e.innerText) !== '取消') return false;
      if (e.getAttribute('data-takt-id') === PAGE_CANCEL) return false;   // 🔴 绝不点页面级取消
      if (e.offsetParent === null) return false;
      return true;
    });
    if (cands.length) { try { cands[0].click(); return 'generic'; } catch (e) {} }
    try { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, composed: true })); } catch (e) {}
    return 'escape';
  }

  var TARGETS = [
    { n: '媒体-设备', t: 'dspcreate_lineitem_mobile_os_list_targeting_button_trigger' },
    { n: '媒体-移动环境', t: 'dspcreate_lineitem_mobile_app_device_type_targeting_button_trigger' },
    { n: '媒体-移动应用', t: 'dspcreate_lineitem_mobile_app_targeting_button_trigger' },
    { n: '产品和服务-类别', t: 'button.product_categories_card_change.edit' },
    { n: '交易(Deals)', t: 'button.deals_card_change.edit' },
    { n: '供应包', t: 'button.supply_packages_card_change.edit' },
    { n: '定向策略-地域', t: 'tenrec_lineitem_geo_targeting_button_trigger' },
    { n: '定向策略-受众', t: 'adsppricing_lineitem_audience_targeting_card_section_view_button_trigger' },
    { n: '定向策略-预竞价', t: 'SQ_LINEITEM_PREBID_TARGETING_button_trigger' },
    { n: '显示可选设置', t: 'section.ad_group.optional_settings.expand' }
  ];

  var out = { url: location.href, panels: [] };
  var chain = Promise.resolve();
  TARGETS.forEach(function (tg) {
    chain = chain.then(function () {
      var el = getTrigger(tg.t);
      if (!el) { out.panels.push({ name: tg.n, error: 'trigger not found' }); return null; }
      var pre = uniq(deepText(document.body, []));
      var isToggle = (tg.t === 'section.ad_group.optional_settings.expand');
      if (isToggle) { el.click(); return sleep(1800).then(function () { var post = uniq(deepText(document.body, [])); var s = {}; pre.forEach(function (x) { s[x] = 1; }); out.panels.push({ name: tg.n, kind: 'toggle', added: post.filter(function (x) { return !s[x]; }).slice(0, 60) }); }); }
      try { el.click(); } catch (e) {}
      return sleep(2400).then(function () {
        var post = uniq(deepText(document.body, []));
        var s = {}; pre.forEach(function (x) { s[x] = 1; });
        var added = post.filter(function (x) { return !s[x]; });
        var rec = { name: tg.n, addedCount: added.length, added: added.slice(0, 70) };
        var closeHow = closePanel(tg.t);
        rec.close = closeHow;
        return sleep(1500).then(function () {
          var now = uniq(deepText(document.body, []));
          var st = {}; added.forEach(function (x) { st[x] = 1; });
          var stillThere = now.filter(function (x) { return st[x]; });
          rec.closedClean = stillThere.length < 6;
          rec.stillCount = stillThere.length;
          out.panels.push(rec);
        });
      });
    });
  });
  chain = chain.then(function () {
    // 折叠回可选设置
    var el = getTrigger('section.ad_group.optional_settings.expand');
    if (el && el.getAttribute && el.getAttribute('aria-expanded') === 'true') { try { el.click(); } catch (e) {} }
    return sleep(1200);
  }).then(function () { return JSON.stringify(out); });
  return chain;
})()
