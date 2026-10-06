JSON.stringify((function () {
  var res = performance.getEntriesByType('resource').map(function (e) { return e.name; });
  var ver = {};
  res.forEach(function (u) {
    var m = u.match(/versionID=(\d+)/);
    if (!m) return;
    var host = (u.match(/^https?:\/\/([^\/]+)/) || [])[1];
    var f = u.split('?')[0].split('/').pop();
    var k = host + '@' + m[1];
    (ver[k] = ver[k] || []).push(f);
  });
  function deepFind(sel) {
    var hit = null;
    function walk(root, depth) {
      if (hit || depth > 8 || !root) return;
      try {
        var el = root.querySelector(sel);
        if (el) { hit = el; return; }
        var all = root.querySelectorAll('*');
        for (var i = 0; i < all.length; i++) {
          if (all[i].shadowRoot) walk(all[i].shadowRoot, depth + 1);
          if (hit) return;
        }
      } catch (e) {}
    }
    walk(document, 0);
    return hit;
  }
  var cs = deepFind('#country-selector');
  var body = document.body ? (document.body.innerText || '') : '';
  var err = body.match(/Cannot read properties of undefined[^\n]{0,40}/);
  var out = {
    url: location.href,
    langHtml: document.documentElement.lang,
    navLang: navigator.language,
    verGroups: Object.keys(ver).map(function (k) { return k + ' x' + ver[k].length; }),
    localeChunks: res.filter(function (u) { return /countrySelector--/.test(u); }).map(function (u) { return u.split('/').pop(); }),
    csFound: !!cs,
    csEmpty: cs ? (cs.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120) : null,
    csHasTrigger: cs ? !!cs.querySelector('button,[role="button"],input') : null,
    err: err ? err[0] : null
  };
  return out;
})())
