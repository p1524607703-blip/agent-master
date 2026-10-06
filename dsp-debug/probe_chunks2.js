(function () {
  var B = 'https://ddwxeg2ktxtzx.cloudfront.net/';
  function hash(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h * 16777619) >>> 0; }
    return h.toString(16);
  }
  function grab(name) {
    return fetch(B + name, { cache: 'reload' })
      .then(function (r) {
        return r.text().then(function (t) {
          return { name: name.replace('storm-ui-country-selector--countrySelector--', ''), status: r.status, len: t.length, hash: hash(t), modId: (t.match(/\{(\d{3}):function/) || [])[1] || null };
        });
      })
      .catch(function (e) { return { name: name.replace('storm-ui-country-selector--countrySelector--', ''), err: String(e && e.message || e) }; });
  }
  return Promise.all([
    grab('storm-ui-country-selector--countrySelector--zh-CN.chunk.js'),
    grab('storm-ui-country-selector--countrySelector--en-GB.chunk.js'),
    grab('storm-ui-country-selector--countrySelector--en-US.chunk.js')
  ]).then(function (r) { return JSON.stringify(r); });
})()
