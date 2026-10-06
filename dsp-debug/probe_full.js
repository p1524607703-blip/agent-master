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
      if (lines.length >= 2) return { name: lines[0].slice(0, 60), desc: lines.slice(1).join(' ').slice(0, 120) };
      if (lines.length === 1 && t.length < 70) return { name: lines[0], desc: '' };
    }
    return { name: clean(el.parentElement ? el.parentElement.innerText : '').slice(0, 50), desc: '' };
  }

  var SLOTS = ['DSP_CAMPAIGN_GENERAL_SECTION_MFE', 'DSP_CAMPAIGN_LEVEL_MEDIA_TYPE', 'DSP_CAMPAIGN_MGMT_ORDER_OPTIMIZATION_MFE',
    'DSP_CAMPAIGN_MGMT_DELIVERY_CAP_MFE', 'DSP_CAMPAIGN_ORDER_AGENCY_FEES', 'DSP_CAMPAIGN_CONVERSION_TRACKING_PRODUCTS',
    'FM_ORDER_FREQUENCY_SETTINGS', 'FREQUENCY_GROUPS_ASSOCIATION', 'CAMPAIGN_COMMITMENT_ASSOCIATION',
    'AD_CONVERSION_DEFINITION_TRACKING', 'AD_SKAD_NETWORK_TRACKING', 'PG_DEAL_SYNC_CAMPAIGN'];

  var out = { url: location.href, steps: [] };

  var chain = Promise.resolve();
  // 1) 展开「显示可选设置」
  chain = chain.then(function () {
    var btn = document.querySelector('[data-takt-id="section.campaign.optional_settings.expand"]');
    if (btn && btn.getAttribute('aria-expanded') !== 'true') { fire(btn); out.steps.push('expanded optional settings'); return sleep(1800); }
    out.steps.push('optional settings already expanded');
  });
  // 2) 打开国家下拉并读取选项
  chain = chain.then(function () {
    var c = document.getElementById('DSP_CAMPAIGN_GENERAL_SECTION_MFE_container');
    var btns = deepAll(c, 'button', []);
    var target = null;
    for (var i = 0; i < btns.length; i++) { if (/美国|United States/.test(clean(btns[i].innerText))) { target = btns[i]; break; } }
    if (!target) { out.countries = 'BTN_NOT_FOUND'; return; }
    fire(target);
    return sleep(1500).then(function () {
      var opts = [];
      var cands = deepAll(document.body, '[role="option"],[role="menuitem"],li', []);
      for (var j = 0; j < cands.length; j++) {
        var t = clean(cands[j].innerText);
        if (t && t.length > 1 && t.length < 30 && cands[j].children.length <= 1) opts.push(t);
      }
      out.countries = opts.filter(function (v, i2, a) { return a.indexOf(v) === i2; }).slice(0, 60);
      try { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); } catch (e) {}
      return sleep(800);
    });
  });
  // 3) 全槽位文本 + 结构化清单
  chain = chain.then(function () {
    out.slots = {};
    out.inventory = {};
    for (var i = 0; i < SLOTS.length; i++) {
      var c = document.getElementById(SLOTS[i] + '_container');
      if (!c) { out.slots[SLOTS[i]] = null; continue; }
      out.slots[SLOTS[i]] = clean(c.textContent).slice(0, 1200);
      var inv = [];
      deepAll(c, 'input,select,textarea,button[role="switch"],button', []).forEach(function (e) {
        var tg = e.tagName.toLowerCase();
        var tp = e.getAttribute('type') || '';
        if (tg === 'button' && e.getAttribute('role') !== 'switch' && !e.getAttribute('data-takt-id') && e.children.length > 2) return;
        var L = labelOf(e);
        inv.push({
          t: tg, type: tp, role: e.getAttribute('role') || '',
          state: e.checked === true ? 'checked' : (e.getAttribute('aria-checked') || ''),
          name: L.name, desc: L.desc,
          id: e.id || '', takt: e.getAttribute('data-takt-id') || '',
          val: (e.value === undefined ? '' : (e.value + '')).slice(0, 40)
        });
      });
      out.inventory[SLOTS[i]] = inv.filter(function (x) { return x.name && x.name !== '?'; }).slice(0, 40);
    }
    return null;
  });
  // 4) 全页搜「完播 / 视频」相关字眼
  chain = chain.then(function () {
    var t = clean(document.body.textContent);
    var hits = {};
    ['完播', '视频完播', 'VCR', '可见', 'viewab'].forEach(function (k) {
      var idx = t.indexOf(k);
      hits[k] = idx < 0 ? null : t.slice(Math.max(0, idx - 40), idx + 60);
    });
    out.keywordHits = hits;
    return null;
  });
  chain = chain.then(function () { return JSON.stringify(out); });
  return chain;
})()
