// 收集当前 dashboard 页所有促销 UUID（来自 [row-id] 属性，light DOM 可读）。
// ag-Grid 行内容在 shadow DOM 里读不到，但 row-id 宿主属性可读，足够驱动详情页抓取。
(function () {
  try {
    var ids = Array.from(document.querySelectorAll('[row-id]')).map(function (e) {
      return e.getAttribute('row-id');
    }).filter(function (x) { return x && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(x); });
    var uniq = Array.from(new Set(ids));
    return JSON.stringify({ ids: uniq });
  } catch (e) { return JSON.stringify({ err: String(e), ids: [] }); }
})();
