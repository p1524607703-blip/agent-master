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
  function fire(el) {
    try {
      var o = { bubbles: true, cancelable: true, view: window, button: 0 };
      el.dispatchEvent(new PointerEvent('pointerdown', o));
      el.dispatchEvent(new MouseEvent('mousedown', o));
      el.dispatchEvent(new PointerEvent('pointerup', o));
      el.dispatchEvent(new MouseEvent('mouseup', o));
      el.dispatchEvent(new MouseEvent('click', o));
    } catch (e) {}
    try { el.click(); } catch (e) {}
  }
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
    return clean(el.parentElement ? el.parentElement.innerText : '').slice(0, 50);
  }
  var MT = 'DSP_CAMPAIGN_LEVEL_MEDIA_TYPE_container';
  var OP = 'DSP_CAMPAIGN_MGMT_ORDER_OPTIMIZATION_MFE_container';
  function mediaState() {
    return deepAll(document.getElementById(MT), 'input[type="checkbox"]', []).map(function (e) { return labelOf(e) + '=' + (e.checked === true); });
  }
  function switches() {
    return deepAll(document.getElementById(OP), 'button[role="switch"]', []).map(function (e) { return { n: labelOf(e), on: e.getAttribute('aria-checked') === 'true' }; });
  }
  function optText() { return uniq(deepText(document.getElementById(OP), [])).join(' | ').slice(0, 1500); }
  function setMedia(name) { var a = deepAll(document.getElementById(MT), 'input[type="checkbox"]', []); for (var i = 0; i < a.length; i++) if (labelOf(a[i]) === name) { if (a[i].checked !== true) fire(a[i]); return; } }
  function setObj(name) { var a = deepAll(document.getElementById(OP), 'button[role="switch"]', []); for (var i = 0; i < a.length; i++) if (labelOf(a[i]) === name) { if (a[i].getAttribute('aria-checked') !== 'true') fire(a[i]); return; } }

  var out = { url: location.href, tests: [], matrix: [] };
  var chain = Promise.resolve();

  // 测试 1：类型是多选还是单选
  chain = chain.then(function () {
    setMedia('在线视频'); return sleep(1600);
  }).then(function () {
    out.tests.push({ name: '多选测试：点击「在线视频」后的类型状态', media: mediaState() });
    setMedia('展示'); return sleep(1400);
  });

  // 测试 2：逐个组合
  var MEDIA = ['展示', '在线视频', '流媒体电视', '音频'];
  var OBJS = ['认知度', '购买意向', '转化量'];
  for (var mi = 0; mi < MEDIA.length; mi++) {
    (function (m) {
      for (var oi = 0; oi < OBJS.length; oi++) {
        (function (o) {
          chain = chain.then(function () { setMedia(m); return sleep(1300); })
            .then(function () { setObj(o); return sleep(1500); })
            .then(function () {
              var sw = switches();
              out.matrix.push({
                media: m, objective: o,
                mediaActual: mediaState(),
                objOn: sw.filter(function (x) { return x.on; }).map(function (x) { return x.n; }),
                kpis: sw.filter(function (x) { return !/^(认知度|购买意向|转化量)$/.test(x.n); }).map(function (x) { return x.n; }),
                text: optText()
              });
            });
        })(OBJS[oi]);
      }
    })(MEDIA[mi]);
  }
  chain = chain.then(function () { setMedia('展示'); return sleep(1300); })
    .then(function () { setObj('购买意向'); return sleep(1300); })
    .then(function () {
      var deep = uniq(deepText(document.body, [])).join(' ');
      out.vcrHits = [];
      ['完播', 'Video completion', 'VCR', '可见率', 'viewable'].forEach(function (k) {
        var i = deep.indexOf(k);
        if (i >= 0) out.vcrHits.push(k + ' → ' + deep.slice(Math.max(0, i - 60), i + 90));
      });
      out.restored = { media: mediaState(), objOn: switches().filter(function (x) { return x.on; }).map(function (x) { return x.n; }) };
      return JSON.stringify(out);
    });
  return chain;
})()
