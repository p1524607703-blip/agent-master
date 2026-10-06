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
      if (e.children.length === 0) { var t = clean(e.innerText); if (t) out.push(t); }
      if (e.shadowRoot) deepText(e.shadowRoot, out);
      deepText(e, out);
    }
    return out;
  }
  function uniq(a) { return a.filter(function (v, i) { return v && a.indexOf(v) === i; }); }
  function lines(el) { return ((el.innerText || '') + '').split('\n').map(function (s) { return s.trim(); }).filter(Boolean); }
  function lab2(el) {
    var L = lines(el);
    if (L.length >= 2) return { n: L[0].slice(0, 60), d: L.slice(1).join(' ').slice(0, 160) };
    if (L.length === 1) return { n: L[0].slice(0, 60), d: '' };
    var p = el.parentElement;
    if (p) { var L2 = lines(p); if (L2.length) return { n: L2[0].slice(0, 60), d: L2.slice(1).join(' ').slice(0, 160) }; }
    return { n: '?', d: '' };
  }
  var MT = 'DSP_CAMPAIGN_LEVEL_MEDIA_TYPE_container';
  var OP = 'DSP_CAMPAIGN_MGMT_ORDER_OPTIMIZATION_MFE_container';
  function mediaInputs() { return deepAll(document.getElementById(MT), 'input[type="checkbox"]', []); }
  function objBtns() { return deepAll(document.getElementById(OP), 'button[role="switch"]', []); }
  function setMedia(ids) { mediaInputs().forEach(function (e) { var w = ids.indexOf(e.id) >= 0; if ((e.checked === true) !== w) { try { e.click(); } catch (x) {} } }); }
  function setObj(name) { objBtns().forEach(function (e) { if (lab2(e).n === name && e.getAttribute('aria-checked') !== 'true') { try { e.click(); } catch (x) {} } }); }

  var out = { url: location.href };
  var chain = Promise.resolve();

  // A. 三个目标下的 KPI 明细（类型 = 展示+在线视频，最全）
  out.kpiDetail = {};
  ['认知度', '购买意向', '转化量'].forEach(function (o) {
    chain = chain.then(function () { setMedia(['DISPLAY', 'VIDEO_OLV']); return sleep(1200); })
      .then(function () { setObj(o); return sleep(1500); })
      .then(function () {
        out.kpiDetail[o] = objBtns().map(function (e) { var L = lab2(e); return { n: L.n, d: L.d, on: e.getAttribute('aria-checked') === 'true' }; })
          .filter(function (x) { return !/^(认知度|购买意向|转化量)$/.test(x.n); });
      });
  });

  // B. 国家/地区下拉
  chain = chain.then(function () {
    var g = document.getElementById('DSP_CAMPAIGN_GENERAL_SECTION_MFE_container');
    var btns = deepAll(g, 'button', []);
    var tgt = null;
    for (var i = 0; i < btns.length; i++) { var t = clean(btns[i].innerText); if (t === '美国' || /United States/.test(t)) { tgt = btns[i]; break; } }
    if (!tgt) { out.countries = 'BTN_NOT_FOUND'; return; }
    try { tgt.click(); } catch (e) {}
    return sleep(1600).then(function () {
      var opts = deepAll(document.body, '[role="option"]', []).map(function (e) { return clean(e.innerText); }).filter(Boolean);
      out.countries = uniq(opts).slice(0, 80);
      out.countriesRaw = deepAll(document.body, '[role="listbox"]', []).map(function (e) { return clean(e.innerText).slice(0, 400); });
      try { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, composed: true })); } catch (e) {}
      return sleep(700);
    });
  });

  // C. 所有原生 select 的选项 + 全槽位文本
  chain = chain.then(function () {
    out.selects = deepAll(document.body, 'select', []).map(function (s) {
      return { id: s.id, name: s.name, opts: (s.options ? Array.prototype.map.call(s.options, function (o) { return clean(o.text); }) : []).slice(0, 40), val: s.value };
    }).filter(function (x) { return x.opts.length; });
    var SLOTS = ['DSP_CAMPAIGN_GENERAL_SECTION_MFE', 'DSP_CAMPAIGN_LEVEL_MEDIA_TYPE', 'DSP_CAMPAIGN_MGMT_ORDER_OPTIMIZATION_MFE',
      'DSP_CAMPAIGN_MGMT_DELIVERY_CAP_MFE', 'DSP_CAMPAIGN_ORDER_AGENCY_FEES', 'FM_ORDER_FREQUENCY_SETTINGS',
      'FREQUENCY_GROUPS_ASSOCIATION', 'AD_CONVERSION_DEFINITION_TRACKING', 'AD_SKAD_NETWORK_TRACKING'];
    out.slots = {};
    SLOTS.forEach(function (id) {
      var c = document.getElementById(id + '_container');
      out.slots[id] = c ? uniq(deepText(c, [])).join(' | ').slice(0, 1500) : null;
    });
    return null;
  });

  // D. 还原：类型=展示+在线视频，目标=购买意向
  chain = chain.then(function () { setMedia(['DISPLAY', 'VIDEO_OLV']); return sleep(1200); })
    .then(function () { setObj('购买意向'); return sleep(1200); })
    .then(function () {
      out.restored = { media: mediaInputs().filter(function (e) { return e.checked === true; }).map(function (e) { return e.id; }), objOn: objBtns().filter(function (e) { return e.getAttribute('aria-checked') === 'true'; }).map(function (e) { return lab2(e).n; }) };
      return JSON.stringify(out);
    });
  return chain;
})()
