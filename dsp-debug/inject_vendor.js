(() => {
  window.__VENDORTEST = { phase: 'started', t: Date.now() };
  const s = document.createElement('script');
  s.charset = 'utf-8';
  s.src = 'https://ddwxeg2ktxtzx.cloudfront.net/orderMFEWebsiteVendors.chunk.js?versionID=1790601009000';
  s.onload = () => { window.__VENDORTEST.phase = 'LOAD_OK'; window.__VENDORTEST.t2 = Date.now(); };
  s.onerror = () => { window.__VENDORTEST.phase = 'LOAD_FAIL_404_or_blocked'; window.__VENDORTEST.t2 = Date.now(); };
  document.head.appendChild(s);
  window.__VENDORTEST.src = s.src;
  return JSON.stringify(window.__VENDORTEST);
})()
