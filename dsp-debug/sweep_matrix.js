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
  function labelOf(el) {
    var cands = [];
    if (el.tagName && el.tagName.toLowerCase() !== 'input') cands.push(el);
    var p = el.parentElement;
    for (var k = 0; k < 3 && p; k++) { cands.push(p); p = p.parentElement; }
    for (var i = 0; i < cands.length; i++) {
      var t = ((cands[i].innerText || '') + '').trim();
      if (!t || t.length > 220) continue;
      var lines = t.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
      if (lines.length >= 2) return { name: lines[0].slice(0, 50), desc: lines.slice(1).join(' ').slice(0, 100) };
      if (lines.length === 1 && t.length < 60) return { name: lines[0], desc: '' };
    }
    return { name: '?', desc: '' };
  }
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
  function mediaEls() { return deepAll(document.getElementById('DSP_CAMPAIGN_LEVEL_MEDIA_TYPE_container'), 'input[type="checkbox"]', []); }
  function objEls() { return deepAll(document.getElementById('DSP_CAMPAIGN_MGMT_ORDER_OPTIMIZATION_MFE_container'), 'button[role="switch"]', []); }

  function readMedia() {
    return mediaEls().map(function (e) { var L = labelOf(e); return { name: L.name, on: e.checked === true || e.getAttribute('aria-checked') === 'true' }; });
  }
  function readObjs() {
    return objEls().map(function (e) { var L = labelOf(e); return { name: L.name, desc: L.desc, on: e.getAttribute('aria-checked') === 'true' }; });
  }
  function setMedia(name) {
    var els = mediaEls();
    for (var i = 0; i < els.length; i++) { if (labelOf(els[i]).name === name) { if (!(els[i].checked === true)) fire(els[i]); return true; } }
    return false;
  }
  function setObj(name) {
    var els = objEls();
    for (var i = 0; i < els.length; i++) { if (labelOf(els[i]).name === name) { if (els[i].getAttribute('aria-checked') !== 'true') fire(els[i]); return true; } }
    return false;
  }
  function objNames() { return objEls().map(function (e) { return labelOf(e).name; }).filter(function (n, i, a) { return a.indexOf(n) === i && n !== 'KPI' && n !== '?'; }); }

  var objs = objNames();
  var mediaOrder = readMedia().map(function (m) { return m.name; });

  var matrix = [];
  var chain = Promise.resolve();
  for (var mi = 0; mi < mediaOrder.length; mi++) {
    (function (mName) {
      for (var oi = 0; oi < objs.length; oi++) {
        (function (oName) {
          chain = chain.then(function () { setMedia(mName); return sleep(1200); })
            .then(function () { setObj(oName); return sleep(1400); })
            .then(function () {
              var items = readObjs();
              matrix.push({ media: mName, objective: oName, kpi: items.filter(function (x) { return x.name.indexOf('(') >= 0; }).map(function (x) { return (x.on ? '[选中] ' : '') + x.name + ' — ' + x.desc; }) });
            });
        })(objs[oi]);
      }
    })(mediaOrder[mi]);
  }
  chain = chain.then(function () { setMedia('展示'); return sleep(1200); })
    .then(function () { setObj('购买意向'); return sleep(1200); })
    .then(function () { return JSON.stringify({ url: location.href, mediaOrder: mediaOrder, objs: objs, matrix: matrix, restored: { media: readMedia(), objs: readObjs().map(function (o) { return o.name + '=' + o.on; }) } }); });
  return chain;
})()
