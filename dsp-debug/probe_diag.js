JSON.stringify((function () {
  function diag(el) {
    if (!el) return null;
    var sr = el.shadowRoot;
    return {
      tag: el.tagName ? el.tagName.toLowerCase() : '?',
      id: el.id || '',
      hasSR: !!sr,
      srChildren: sr ? (sr.children ? sr.children.length : -1) : -1,
      srHtmlLen: sr ? ((sr.innerHTML || '').length) : -1,
      lightChildren: el.children ? el.children.length : -1,
      lightHtmlLen: (el.innerHTML || '').length
    };
  }
  var out = { url: location.href };
  ['DSP_CAMPAIGN_GENERAL_SECTION_MFE', 'DSP_CAMPAIGN_LEVEL_MEDIA_TYPE', 'DSP_CAMPAIGN_MGMT_ORDER_OPTIMIZATION_MFE'].forEach(function (id) {
    var byId = document.getElementById(id + '_container');
    var bySel = document.querySelector('mfe-slot#' + id + '_container');
    out[id] = { byId: diag(byId), bySel: diag(bySel) };
  });

  var srs = [];
  (function walk(root, d) {
    if (!root || d > 12) return;
    var all = root.querySelectorAll ? root.querySelectorAll('*') : [];
    for (var i = 0; i < all.length; i++) {
      if (all[i].shadowRoot) { srs.push(d + ':' + all[i].tagName.toLowerCase() + (all[i].id ? '#' + all[i].id : '')); walk(all[i].shadowRoot, d + 1); }
    }
  })(document, 0);
  out.shadowRootCount = srs.length;
  out.shadowRoots = srs.slice(0, 40);

  out.mfeSlots = [];
  document.querySelectorAll('mfe-slot').forEach(function (s) {
    out.mfeSlots.push({ id: s.id, name: s.getAttribute('name'), hasSR: !!s.shadowRoot, kids: s.shadowRoot ? s.shadowRoot.children.length : -1, htmlLen: (s.innerHTML || '').length });
  });
  return out;
})())
