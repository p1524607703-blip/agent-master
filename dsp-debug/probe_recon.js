JSON.stringify((function () {
  var CAP = 300;
  function deepAll(sel, cap) {
    var out = [];
    var seen = [];
    function walk(root, depth) {
      if (!root || depth > 12 || out.length > (cap || CAP)) return;
      try {
        var hit = root.querySelectorAll(sel);
        for (var i = 0; i < hit.length; i++) { if (seen.indexOf(hit[i]) < 0) { seen.push(hit[i]); out.push(hit[i]); } }
      } catch (e) {}
      try {
        var all = root.querySelectorAll('*');
        for (var j = 0; j < all.length; j++) { if (all[j].shadowRoot) walk(all[j].shadowRoot, depth + 1); if (out.length > (cap || CAP)) return; }
      } catch (e) {}
    }
    walk(document, 0);
    return out;
  }
  function txt(e) { try { return ((e.innerText || e.textContent || '') + '').replace(/\s+/g, ' ').trim().slice(0, 90); } catch (x) { return ''; } }
  function own(e) {
    var s = '';
    for (var i = 0; i < e.childNodes.length; i++) if (e.childNodes[i].nodeType === 3) s += e.childNodes[i].nodeValue;
    return s.replace(/\s+/g, ' ').trim().slice(0, 70);
  }

  var slots = deepAll('mfe-slot', 60).map(function (e) { return { id: e.id, name: e.getAttribute('name') }; });

  var takt = deepAll('[data-takt-id]', 260).map(function (e) {
    return {
      t: e.getAttribute('data-takt-id'),
      tag: e.tagName.toLowerCase(),
      role: e.getAttribute('role') || '',
      txt: txt(e).slice(0, 60),
      exp: e.getAttribute('aria-expanded'),
      chk: e.getAttribute('aria-checked') || e.getAttribute('aria-selected'),
      dis: e.disabled === true
    };
  });

  var fields = deepAll('input,select,textarea', 120).map(function (e) {
    var lab = '';
    try {
      if (e.id) { var l = document.querySelector('label[for="' + e.id + '"]'); if (l) lab = txt(l); }
      if (!lab && e.closest) { var pc = e.closest('label'); if (pc) lab = txt(pc); }
    } catch (x) {}
    return { tag: e.tagName.toLowerCase(), type: e.type || '', id: e.id || '', aria: e.getAttribute('aria-label') || '', label: lab, val: (e.value || '').slice(0, 60), ph: e.placeholder || '', dis: e.disabled === true };
  });

  var heads = deepAll('h1,h2,h3,h4,h5,h6,legend', 80).map(function (e) { return e.tagName.toLowerCase() + ': ' + txt(e); }).filter(function (s) { return s.length > 4; });

  return { url: location.href, slotCount: slots.length, slots: slots, taktCount: takt.length, takt: takt, fieldCount: fields.length, fields: fields, heads: heads };
})())
