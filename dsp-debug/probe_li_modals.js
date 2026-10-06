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
      if (e.children.length === 0) { var t = clean(e.innerText); if (t && t.length < 60) out.push(t); }
      if (e.shadowRoot) deepText(e.shadowRoot, out);
      deepText(e, out);
    }
    return out;
  }
  function uniq(a) { return a.filter(function (v, i) { return v && a.indexOf(v) === i; }); }
  function btn(takt) {
    var els = deepAll(document, '[data-takt-id="' + takt + '"]', []);
    for (var i = 0; i < els.length; i++) if (els[i].tagName.toLowerCase() === 'button') return els[i];
    return els[0] || null;
  }
  function openDialog() {
    var dlg = deepAll(document, '[role="dialog"],[role="alertdialog"]', []);
    var vis = dlg.filter(function (d) {
      if (d.offsetParent === null) return false;
      var t = clean(d.innerText);
      if (/查看消息|忽略/.test(t) && t.length < 20) return false;
      return t.length > 0;
    });
    vis.sort(function (a, b) { return (b.innerText || '').length - (a.innerText || '').length; });
    return vis[0] || null;
  }
  // ⚠️ 只在弹窗内部找关闭按钮；绝不点页面级的「取消」（那是返回列表页的链接）
  function closeDialog(dlg) {
    if (dlg) {
      var cands = deepAll(dlg, 'button,a,[role="button"]', []);
      var want = /^(取消|关闭|完成|Cancel|Close|Done)$/;
      for (var i = 0; i < cands.length; i++) {
        var t = clean(cands[i].innerText);
        if (want.test(t) && cands[i].offsetParent !== null) { try { cands[i].click(); return 'clicked:' + t; } catch (e) {} }
      }
      var x = deepAll(dlg, '[aria-label="关闭"],[aria-label="Close"],button[class*="close"]', []);
      for (var j = 0; j < x.length; j++) { try { x[j].click(); return 'clicked-x'; } catch (e) {} }
    }
    try { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, composed: true })); } catch (e) {}
    return 'escape';
  }

  var TARGETS = [
    { n: '设备（电脑端/移动端）', t: 'dspcreate_lineitem_mobile_os_list_targeting_button_trigger' },
    { n: '移动环境（网页/应用）', t: 'dspcreate_lineitem_mobile_app_device_type_targeting_button_trigger' },
    { n: '移动应用', t: 'dspcreate_lineitem_mobile_app_targeting_button_trigger' },
    { n: '产品和服务-类别', t: 'button.product_categories_card_change.edit' },
    { n: '交易/Deals', t: 'button.deals_card_change.edit' },
    { n: '供应包', t: 'button.supply_packages_card_change.edit' },
    { n: '地域定向', t: 'tenrec_lineitem_geo_targeting_button_trigger' },
    { n: '受众定向', t: 'adsppricing_lineitem_audience_targeting_card_section_view_button_trigger' },
    { n: '预竞价定向', t: 'SQ_LINEITEM_PREBID_TARGETING_button_trigger' },
    { n: '订单指标（预测）', t: 'adpt_adsp_ifs_forecast_components_dropdown' }
  ];

  var out = { url: location.href, modals: [] };
  var chain = Promise.resolve();
  TARGETS.forEach(function (tg) {
    chain = chain.then(function () {
      var el = btn(tg.t);
      if (!el) { out.modals.push({ name: tg.n, error: 'trigger not found' }); return null; }
      try { el.click(); } catch (e) {}
      return sleep(2200).then(function () {
        var dlg = openDialog();
        var rec = { name: tg.n, hasDialog: !!dlg };
        if (dlg) {
          var texts = uniq(deepText(dlg, []));
          rec.texts = texts.slice(0, 140);
          rec.textLen = texts.length;
          rec.controls = deepAll(dlg, 'input,select,button,label,[role="option"],[role="checkbox"],[role="radio"]', []).map(function (e) {
            var t = clean(e.innerText);
            if (!t) { var p = e.parentElement; if (p) t = clean(p.innerText).slice(0, 70); }
            return { tag: e.tagName.toLowerCase(), type: e.getAttribute('type') || '', role: e.getAttribute('role') || '', txt: t.slice(0, 70), chk: e.checked === undefined ? null : e.checked, id: e.id || '' };
          }).slice(0, 120);
        } else {
          rec.pageAdds = uniq(deepText(document.body, [])).slice(0, 60);
        }
        out.modals.push(rec);
        rec.close = closeDialog(dlg);
        return sleep(1200);
      });
    });
  });
  chain = chain.then(function () { return JSON.stringify(out); });
  return chain;
})()
