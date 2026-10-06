JSON.stringify((function () {
  var res = performance.getEntriesByType('resource');
  var urls = res.map(function (e) { return e.name; });

  var hostCount = {};
  urls.forEach(function (u) {
    var h = (u.match(/^https?:\/\/([^\/]+)/) || [])[1] || 'other';
    hostCount[h] = (hostCount[h] || 0) + 1;
  });

  var ver = {};
  urls.forEach(function (u) {
    var m = u.match(/versionID=(\d+)/);
    if (!m) return;
    var h = (u.match(/^https?:\/\/([^\/]+)/) || [])[1];
    var f = u.split('?')[0].split('/').pop();
    var k = h + '@' + m[1];
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
  var csInfo = null;
  if (cs) {
    var trig = cs.querySelector('button,[role="button"]');
    csInfo = {
      text: (cs.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 100),
      hasTrigger: !!trig,
      emptySlot: !!cs.querySelector('[class*="fifgRP"]'),
      innerLen: (cs.innerHTML || '').length
    };
  }

  var body = document.body ? (document.body.innerText || '') : '';
  var errs = body.match(/Cannot read properties of undefined[^\n]{0,50}/g);

  return {
    url: location.href,
    docLang: document.documentElement.lang,
    navLang: navigator.language,
    navLangs: (navigator.languages || []).join(','),
    resTotal: urls.length,
    hostCount: hostCount,
    verGroups: ver,
    localeChunks: urls.filter(function (u) { return /countrySelector--/.test(u); }).map(function (u) { return u.split('/').pop(); }),
    standaloneChunks: urls.filter(function (u) { return /standalone-cacheable/.test(u); }).length,
    hasA3cLoader: urls.some(function (u) { return /a3c-loader/.test(u); }),
    cs: csInfo,
    errs: errs,
    hasWebpackJsonp: typeof window.webpackJsonp !== 'undefined'
  };
})())
