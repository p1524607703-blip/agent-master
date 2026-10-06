// 点击详情页商品表格的「下一页」（.ag-icon-next，light DOM 可点）
// 返回点击前是否 disabled 与点击后所在页码/总页数
(function () {
  try {
    var nx = document.querySelector('.ag-icon-next');
    if (!nx) return JSON.stringify({ clicked: false, reason: 'no-next' });
    var wrap = nx.closest('.ag-paging-button') || nx.parentElement;
    var disabledBefore = nx.classList.contains('ag-disabled') || (wrap && wrap.classList.contains('ag-disabled'));
    nx.click();
    var panel = document.querySelector('.ag-paging-panel, [class*="paging"]');
    var page = null, pages = null;
    if (panel) {
      var t = (panel.innerText || '').replace(/\s+/g, ' ');
      var pm = t.match(/页面\s*(\d+)\s*\/\s*(\d+)/);
      if (pm) { page = +pm[1]; pages = +pm[2]; }
    }
    return JSON.stringify({ clicked: true, disabledBefore: disabledBefore, page: page, pages: pages });
  } catch (e) { return JSON.stringify({ err: String(e) }); }
})();