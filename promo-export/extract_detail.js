// 详情页提取（v2）：促销级字段 + 当前页商品表 SKU + 分页信息
// 关键修正：SKU 限定在商品 ag-Grid 容器内抓取，避免与表头「SKU」字段混淆；
// 表格可能异步渲染，故本脚本只返回「当前可见状态」，由 Node 侧轮询/翻页累加。
(function () {
  try {
    function grab(txt, re) { var m = txt.match(re); return m ? m[1].trim() : null; }
    var body = (document.body && document.body.innerText || '').replace(/\s+/g, ' ');
    var promo = grab(body, /促销编号\s*([0-9a-fA-F-]{36})/);
    var type = grab(body, /类型\s*([^\s]+)/);
    // 注意：月份是 3~4 字母（九月是 "Sept" 不是 "Sep"），用 {2,8} 兼容缩写与全称，
    // 否则九月及全称月份会整条匹配失败 → 日期静默变空（曾导致 1 Sept 2026 被判空）。
    var start = grab(body, /开始日期\s*(\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4},\s*\d{1,2}:\d{2})/);
    var end = grab(body, /结束日期\s*(\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4},\s*\d{1,2}:\d{2})/);
    var mkt = grab(body, /亚马逊商城\s*([^\s]+)/) || grab(body, /商城\s*([^\s]+)/);
    var fee = grab(body, /费用\s*([^\n]+?)(?=\s*下载当前商品)/);
    var status = null;
    var sm = body.match(/已结束|已取消|已暂停|待开始|进行中|已过期/);
    if (sm) status = sm[0];

    // SKU：优先商品表格（grid 内），回退正文
    function gridSkus() {
      var grid = document.querySelector('.ag-grid-container') || document.querySelector('.ag-root-wrapper');
      if (!grid) return [];
      var gtxt = (grid.innerText || '').replace(/\s+/g, ' ');
      return (gtxt.match(/SKU\s*[:：]\s*([^\s]+)/g) || []).map(function (s) { return s.replace(/SKU\s*[:：]\s*/, '').trim(); });
    }
    var skus = gridSkus();
    var source = skus.length ? 'grid' : 'body';
    if (!skus.length) {
      skus = (body.match(/SKU\s*[:：]\s*([^\s]+)/g) || []).map(function (s) { return s.replace(/SKU\s*[:：]\s*/, '').trim(); });
    }

    // 分页信息（商品表分页面板）
    var panel = document.querySelector('.ag-paging-panel, [class*="paging"]');
    var pager = null;
    if (panel) {
      var t = (panel.innerText || '').replace(/\s+/g, ' ');
      var pm = t.match(/页面\s*(\d+)\s*\/\s*(\d+)/);
      pager = { page: pm ? +pm[1] : 1, pages: pm ? +pm[2] : 1, text: t.slice(0, 80) };
    }
    return JSON.stringify({ promo: promo, type: type, status: status, start: start, end: end, mkt: mkt, fee: fee, skus: skus, skuSource: source, pager: pager });
  } catch (e) { return JSON.stringify({ err: String(e), promo: null }); }
})();