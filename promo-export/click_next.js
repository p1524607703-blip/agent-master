// 点击 ag-Grid 的「下一页」按钮（.ag-icon-next，位于 light DOM，可点击）。
// 返回点击前是否 disabled（disabled 表示已是最后一页）。
(function () {
  try {
    var next = document.querySelector('.ag-icon-next');
    if (!next) return JSON.stringify({ status: 'NO_NEXT' });
    var wrap = next.closest('.ag-paging-button') || next.parentElement;
    var disabled = next.classList.contains('ag-disabled') || (wrap && wrap.classList.contains('ag-disabled'));
    next.click();
    return JSON.stringify({ status: 'CLICKED', disabledBefore: disabled });
  } catch (e) { return JSON.stringify({ err: String(e) }); }
})();
