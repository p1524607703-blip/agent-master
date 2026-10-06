(function () {
  var B = 'https://ddwxeg2ktxtzx.cloudfront.net/';
  function grab(name) {
    return fetch(B + name)
      .then(function (r) { return r.text().then(function (t) { return { name: name, status: r.status, len: t.length, head: t.slice(0, 150) }; }); })
      .catch(function (e) { return { name: name, err: String(e && e.message || e) }; });
  }
  return Promise.all([
    grab('storm-ui-country-selector--countrySelector--zh-CN.chunk.js'),
    grab('storm-ui-country-selector--countrySelector--en-GB.chunk.js'),
    grab('storm-ui-country-selector--countrySelector--en-US.chunk.js')
  ]).then(function (r) { return JSON.stringify(r); });
})()
