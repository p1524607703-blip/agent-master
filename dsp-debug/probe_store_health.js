JSON.stringify((function () {
  var res = performance.getEntriesByType('resource').map(function (e) { return e.name; });

  var ver = {};
  res.forEach(function (u) {
    var m = u.match(/versionID=(\d+)/);
    if (!m) return;
    var host = (u.match(/^https?:\/\/([^\/]+)/) || [])[1];
    var f = u.split('?')[0].split('/').pop();
    var k = host + ' @ ' + m[1];
    (ver[k] = ver[k] || []).push(f);
  });

  var localeChunks = res.filter(function (u) { return /countrySelector--|CloseButton--/.test(u); });
  var unversionedCdn = res.filter(function (u) {
    return /\.js$/.test(u.split('?')[0]) && u.indexOf('versionID=') < 0 && /cloudfront\.net/.test(u);
  });

  function deepFind(sel) {
    var hit = null;
    function walk(root, depth) {
      if (hit || depth > 6 || !root) return;
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
  var csInner = null, csText = null;
  if (cs) {
    csInner = (cs.innerHTML || '').replace(/\s+/g, ' ').slice(0, 260);
    csText = (cs.innerText || '').replace(/\s+/g, ' ').slice(0, 200);
  }

  var errText = null;
  try {
    var body = document.body ? (document.body.innerText || '') : '';
    var m = body.match(/Cannot read properties of undefined[^\n]{0,60}/);
    if (m) errText = m[0];
  } catch (e) {}

  return {
    url: location.href,
    htmlLang: document.documentElement.lang,
    navLang: navigator.language,
    navLangs: (navigator.languages || []).join(','),
    totalResources: res.length,
    versionGroups: ver,
    localeChunks: localeChunks,
    unversionedCdnJs: unversionedCdn,
    countrySelectorFound: !!cs,
    countrySelectorInner: csInner,
    countrySelectorText: csText,
    pageErrorText: errText,
    hasWebpackJsonp: typeof window.webpackJsonp !== 'undefined'
  };
})())
