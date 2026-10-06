// 探测: 报告页(按父商品)的日期控件 / 表格 / 分页 / 导出按钮
(function () {
  try {
    var out = { url: location.href, title: document.title };

    // 1) 所有 kat-* / 自定义元素统计
    var tags = {};
    Array.prototype.forEach.call(document.querySelectorAll('*'), function (el) {
      var t = el.tagName.toLowerCase();
      if (t.indexOf('-') > 0) tags[t] = (tags[t] || 0) + 1;
    });
    out.customTags = tags;

    // 2) 日期/区间相关元素(含 kat-* 的 label 文本)
    var dateish = [];
    Array.prototype.forEach.call(document.querySelectorAll('*'), function (el) {
      var t = el.tagName.toLowerCase();
      if (!/date|calendar|range|period|picker/.test(t + ' ' + (el.className || '') + ' ' + (el.id || ''))) return;
      var txt = (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 120);
      dateish.push({
        tag: t, cls: (el.className || '').toString().slice(0, 100), id: el.id || '',
        label: el.getAttribute('label') || el.getAttribute('aria-label') || '',
        value: el.getAttribute('value') || '',
        text: txt
      });
    });
    out.dateish = dateish.slice(0, 30);

    // 3) button / kat-button 文本
    var btns = [];
    Array.prototype.forEach.call(document.querySelectorAll('button,kat-button,[role=button],a[class*=button]'), function (b) {
      var t = (b.innerText || b.textContent || '').trim().replace(/\s+/g, ' ');
      if (!t || t.length > 40) return;
      btns.push({ tag: b.tagName.toLowerCase(), text: t, cls: (b.className || '').toString().slice(0, 80), id: b.id || '' });
    });
    out.buttons = btns.slice(0, 60);

    // 4) 表格 / 网格行
    var gridInfo = { roleGrid: 0, rows: 0, sampleRows: [], headerText: '' };
    var g = document.querySelector('[role=grid],[role=table],table,.ag-root');
    if (g) {
      gridInfo.cls = (g.className || '').toString().slice(0, 120);
      var rows = g.querySelectorAll('[role=row],tr');
      gridInfo.rows = rows.length;
      for (var i = 0; i < Math.min(3, rows.length); i++) {
        gridInfo.sampleRows.push((rows[i].innerText || '').trim().replace(/\s+/g, ' | ').slice(0, 400));
      }
    }
    out.grid = gridInfo;

    // 5) ag-grid 行宿主 row-id
    var rowIds = [];
    Array.prototype.forEach.call(document.querySelectorAll('[row-id]'), function (r) {
      rowIds.push(r.getAttribute('row-id'));
    });
    out.agRowCount = rowIds.length;
    out.agRowSample = rowIds.slice(0, 5);

    out.bodyHead = (document.body.innerText || '').trim().slice(0, 2000);
    return JSON.stringify({ status: 'OK', data: out });
  } catch (e) {
    return JSON.stringify({ status: 'ERR', msg: String(e) });
  }
})();
