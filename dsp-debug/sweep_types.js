(function () {
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function clean(s) { return (s || '').replace(/\s+/g, ' ').trim(); }

  var SLOTS = [
    'DSP_CAMPAIGN_GENERAL_SECTION_MFE',
    'DSP_CAMPAIGN_LEVEL_MEDIA_TYPE',
    'DSP_CAMPAIGN_MGMT_ORDER_OPTIMIZATION_MFE',
    'DSP_CAMPAIGN_MGMT_DELIVERY_CAP_MFE',
    'DSP_CAMPAIGN_ORDER_AGENCY_FEES',
    'FM_ORDER_FREQUENCY_SETTINGS',
    'FREQUENCY_GROUPS_ASSOCIATION'
  ];

  function snap() {
    var o = {};
    for (var i = 0; i < SLOTS.length; i++) {
      var e = document.getElementById(SLOTS[i] + '_container');
      o[SLOTS[i]] = e ? clean(e.innerText).slice(0, 900) : null;
    }
    return o;
  }
  function fire(el) {
    try {
      var opts = { bubbles: true, cancelable: true, view: window, button: 0 };
      el.dispatchEvent(new PointerEvent('pointerdown', opts));
      el.dispatchEvent(new MouseEvent('mousedown', opts));
      el.dispatchEvent(new PointerEvent('pointerup', opts));
      el.dispatchEvent(new MouseEvent('mouseup', opts));
      el.dispatchEvent(new MouseEvent('click', opts));
    } catch (e) {}
    try { el.click(); } catch (e) {}
  }
  function mediaRadios() {
    var c = document.getElementById('DSP_CAMPAIGN_LEVEL_MEDIA_TYPE_container');
    if (!c) return [];
    var rs = c.querySelectorAll('input[type="radio"]');
    var out = [];
    for (var i = 0; i < rs.length; i++) {
      var lab = '';
      var p = rs[i].parentElement;
      for (var k = 0; k < 4 && p && !lab; k++) {
        var t = clean(p.innerText);
        if (t && t.length > 1) lab = t.split(' ').slice(0, 3).join(' ');
        p = p.parentElement;
      }
      out.push({ idx: i, label: lab, checked: rs[i].checked === true, el: rs[i] });
    }
    return out;
  }

  var rs = mediaRadios();
  if (!rs.length) return JSON.stringify({ error: 'no media radios found' });

  var results = [{ step: 'as-is', label: '(初始)', snapshot: snap() }];
  var chain = Promise.resolve();
  for (var i = 0; i < rs.length; i++) {
    (function (r) {
      chain = chain.then(function () {
        fire(r.el);
        return sleep(1500);
      }).then(function () {
        results.push({ step: 'click-' + r.idx, label: r.label, snapshot: snap() });
      });
    })(rs[i]);
  }
  return chain.then(function () {
    var finalTypes = mediaRadios().map(function (x) { return x.label + '=' + x.checked; });
    return JSON.stringify({ url: location.href, mediaOptions: finalTypes, results: results });
  });
})()
