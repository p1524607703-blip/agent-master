// 详情页渲染等待：出现「促销编号」字样即视为已加载完成。
(function () {
  try {
    var ok = /促销编号/.test(document.body.innerText || '');
    return JSON.stringify({ ok: ok });
  } catch (e) { return JSON.stringify({ ok: false }); }
})();
