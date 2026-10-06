(function () {
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function clean(s) { return ((s || '') + '').replace(/\s+/g, ' ').trim(); }
  function deepAll(root, sel, out) {
    out = out || [];
    try { var h = root.querySelectorAll(sel); for (var i = 0; i < h.length; i++) out.push(h[i]); } catch (e) {}
    try { var all = root.querySelectorAll('*'); for (var j = 0; j < all.length; j++) { if (all[j].shadowRoot) deepAll(all[j].shadowRoot, sel, out); } } catch (e) {}
    return out;
  }
  function labelOf(el) {
    var p = el.parentElement;
    for (var k = 0; k < 3 && p; k++) {
      var lines = ((p.innerText || '')).split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
      if (lines.length >= 2) return { name: lines[0], desc: lines.slice(1).join(' ').slice(0, 90) };
      p = p.parentElement;
    }
    return { name: clean(el.parentElement ? el.parentElement.innerText : '').slice(0, 40), desc: '' };
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
  function group(id, sel) {
    var c = document.getElementById(id + '_container');
    if (!c) return [];
    return deepAll(c, sel, []).map(function (el) {
      var L = labelOf(el);
      return {
        name: L.name, desc: L.desc,
        on: el.getAttribute('aria-checked') === 'true' || el.checked === true
      };
    });
  }
  function snap() {
    return {
      media: group('DSP_CAMPAIGN_LEVEL_MEDIA_TYPE', 'input[type="checkbox"]'),
      objectives: group('DSP_CAMPAIGN_MGMT_ORDER_OPTIMIZATION_MFE', 'button[role="switch"]'),
      delivery: clean((document.getElementById('DSP_CAMPAIGN_MGMT_DELIVERY_CAP_MFE_container') || {}).innerText || '').slice(0, 220),
      freq: clean((document.getElementById('FM_ORDER_FREQUENCY_SETTINGS_container') || {}).innerText || '').slice(0, 220)
    };
  }

  var mediaEls = deepAll(document.getElementById('DSP_CAMPAIGN_LEVEL_MEDIA_TYPE_container'), 'input[type="checkbox"]', []);
  if (!mediaEls.length) return JSON.stringify({ error: 'no media checkboxes' });
  var labels = mediaEls.map(function (e) { return labelOf(e).name; });

  var results = [];
  var chain = Promise.resolve();
  for (var i = 0; i < mediaEls.length; i++) {
    (function (idx) {
      chain = chain.then(function () { fire(mediaEls[idx]); return sleep(1800); })
        .then(function () { results.push({ clicked: labels[idx], state: snap() }); });
    })(i);
  }
  chain = chain.then(function () {
    fire(mediaEls[0]); return sleep(1500);
  }).then(function () {
    return JSON.stringify({ url: location.href, labels: labels, results: results, restored: snap() });
  });
  return chain;
})()
