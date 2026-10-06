JSON.stringify((function () {
  var SLOTS = [
    'DSP_CAMPAIGN_GENERAL_SECTION_MFE',
    'DSP_CAMPAIGN_LEVEL_MEDIA_TYPE',
    'DSP_CAMPAIGN_MGMT_ORDER_OPTIMIZATION_MFE',
    'DSP_CAMPAIGN_MGMT_DELIVERY_CAP_MFE',
    'DSP_CAMPAIGN_ORDER_AGENCY_FEES',
    'FM_ORDER_FREQUENCY_SETTINGS',
    'FREQUENCY_GROUPS_ASSOCIATION',
    'CAMPAIGN_COMMITMENT_ASSOCIATION'
  ];
  var CAP = 220;

  function cls(e) {
    var c = e.className;
    if (c && c.baseVal !== undefined) c = c.baseVal;
    return (c + '').split(' ').filter(Boolean).slice(0, 1).join('');
  }
  function collect(root, depth, out) {
    if (!root || out.length > CAP) return;
    var kids = root.children || [];
    for (var i = 0; i < kids.length; i++) {
      if (out.length > CAP) return;
      var e = kids[i];
      var t = e.tagName ? e.tagName.toLowerCase() : '?';
      var own = '';
      for (var j = 0; j < e.childNodes.length; j++) if (e.childNodes[j].nodeType === 3) own += e.childNodes[j].nodeValue;
      own = own.replace(/\s+/g, ' ').trim();
      var role = e.getAttribute ? (e.getAttribute('role') || '') : '';
      var isCtl = ['input', 'select', 'textarea', 'button', 'a'].indexOf(t) >= 0 || !!role;
      if (isCtl || own) {
        out.push({
          d: depth, tag: t, cls: cls(e), role: role,
          aria: (e.getAttribute && (e.getAttribute('aria-label') || '')) || '',
          txt: own.slice(0, 60),
          sel: (e.getAttribute && ((e.getAttribute('aria-checked') || '') + (e.getAttribute('aria-selected') || '') + (e.getAttribute('aria-expanded') || ''))) || '',
          chk: e.checked === true ? 'Y' : '',
          id: e.id || ''
        });
      }
      if (e.shadowRoot) collect(e.shadowRoot, depth + 1, out);
      collect(e, depth + 1, out);
    }
  }

  var res = {};
  for (var s = 0; s < SLOTS.length; s++) {
    var id = SLOTS[s];
    var host = document.getElementById(id + '_container');
    if (!host) { res[id] = 'NOT_FOUND'; continue; }
    var out = [];
    collect(host, 0, out);
    res[id] = { count: out.length, nodes: out };
  }
  return { url: location.href, res: res };
})())
