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
  var OP = 'DSP_CAMPAIGN_MGMT_ORDER_OPTIMIZATION_MFE_container';
  function mediaInputs() { return deepAll(document.getElementById(MT), 'input[type="checkbox"]', []); }
  function mediaInfo() { return mediaInputs().map(function (e) { return { id: e.id, name: e.name, label: labelOf(e), on: e.checked === true }; }); }
  function objBtns() { return deepAll(document.getElementById(OP), 'button[role="switch"]', []); }
  function objInfo() { return objBtns().map(function (e) { return { n: labelOf(e), on: e.getAttribute('aria-checked') === 'true' }; }); }
  function setMedia(ids) {
    mediaInputs().forEach(function (e) { var want = ids.indexOf(e.id) >= 0; if ((e.checked === true) !== want) { try { e.click(); } catch (x) {} } });
  }
  function setObj(name) { objBtns().forEach(function (e) { if (labelOf(e) === name && e.getAttribute('aria-checked') !== 'true') { try { e.click(); } catch (x) {} } }); }

  var info = mediaInfo();
  var ids = info.map(function (x) { return x.id; });
  var byLabel = {};
  info.forEach(function (x) { byLabel[x.label] = x.id; });

  var COMBOS = [
    { n: '展示', ids: [byLabel['展示']] },
    { n: '在线视频', ids: [byLabel['在线视频']] },
    { n: '流媒体电视', ids: [byLabel['流媒体电视']] },
    { n: '音频', ids: [byLabel['音频']] },
    { n: '在线视频+流媒体电视', ids: [byLabel['在线视频'], byLabel['流媒体电视']] }
  ];
  var OBJS = ['认知度', '购买意向', '转化量'];

  var out = { url: location.href, mediaOptions: info, matrix: [] };
  var chain = Promise.resolve();
  COMBOS.forEach(function (c) {
    OBJS.forEach(function (o) {
      chain = chain.then(function () { setMedia(c.ids); return sleep(1200); })
        .then(function () { setObj(o); return sleep(1500); })
        .then(function () {
          var oi = objInfo();
          out.matrix.push({
            media: c.n, objective: o,
            mediaActual: mediaInfo().filter(function (x) { return x.on; }).map(function (x) { return x.label; }),
            objOn: oi.filter(function (x) { return x.on; }).map(function (x) { return x.n; }),
            kpis: oi.filter(function (x) { return !/^(认知度|购买意向|转化量)$/.test(x.n); }).map(function (x) { return x.n; }),
            optText: uniq(deepText(document.getElementById(OP), [])).join(' | ').slice(0, 800)
          });
        });
    });
  });
  chain = chain.then(function () { setMedia([byLabel['展示']]); return sleep(1200); })
    .then(function () { setObj('购买意向'); return sleep(1200); })
    .then(function () {
      var dt = uniq(deepText(document.body, [])).join(' ').slice(0, 400000);
      out.vcr = [];
      var idx = 0;
      while ((idx = dt.indexOf('Video completion', idx)) >= 0 && out.vcr.length < 3) { out.vcr.push(dt.slice(Math.max(0, idx - 80), idx + 120)); idx += 10; }
      out.restored = { media: mediaInfo().filter(function (x) { return x.on; }).map(function (x) { return x.label; }), objOn: objInfo().filter(function (x) { return x.on; }).map(function (x) { return x.n; }) };
      return JSON.stringify(out);
    });
  return chain;
})()
