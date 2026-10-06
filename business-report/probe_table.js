// 探测: 报告表格 DOM 结构 + 导出/下载入口 + 分页
(function () {
  try {
    var out = { url: location.href };

    // 1) 找表头 "（父）ASIN" 所在容器
    var headEl = null;
    Array.prototype.forEach.call(document.querySelectorAll('*'), function (el) {
      if (headEl) return;
      if (el.children.length === 0) {
        var t = (el.innerText || el.textContent || '').trim();
        if (t === '（父）ASIN' || t === '(Parent) ASIN') headEl = el;
      }
    });
    var info = { found: !!headEl };
    if (headEl) {
      var node = headEl, chain = [], i = 0;
      // 向上找到包含多行的容器
      while (node && i < 12) {
        chain.push({
          tag: node.tagName.toLowerCase(),
          cls: (node.className || '').toString().slice(0, 100),
          role: node.getAttribute('role') || '',
          children: node.children.length,
          rows: node.querySelectorAll('[role=row],tr').length,
          depth: i
        });
        node = node.parentElement; i++;
      }
      info.chain = chain;
      // 容器文本(表头区)
      var c = headEl;
      for (var k = 0; k < 6 && c.parentElement; k++) { c = c.parentElement; if (c.querySelectorAll('[role=row],tr').length > 5) break; }
      info.containerTag = c.tagName.toLowerCase();
      info.containerCls = (c.className || '').toString().slice(0, 120);
      info.containerRows = c.querySelectorAll('[role=row],tr').length;
      var sample = [];
      Array.prototype.forEach.call(c.querySelectorAll('[role=row],tr'), function (r, idx) {
        if (idx < 3) sample.push((r.innerText || '').trim().replace(/\s+/g, ' | ').slice(0, 300));
      });
      info.sampleRows = sample;
      info.rowTag = (function () { var r = c.querySelector('[role=row],tr'); return r ? r.tagName.toLowerCase() + ' ' + (r.className || '').toString().slice(0, 80) : ''; })();
    }
    out.table = info;

    // 2) kat-button 全量(含 shadow-less 文本)
    var kb = [];
    Array.prototype.forEach.call(document.querySelectorAll('kat-button'), function (b) {
      kb.push({
        text: (b.innerText || b.textContent || '').trim().slice(0, 40),
        label: b.getAttribute('label') || b.getAttribute('aria-label') || '',
        value: b.getAttribute('value') || '',
        variant: b.getAttribute('variant') || '',
        cls: (b.className || '').toString().slice(0, 60)
      });
    });
    out.katButtons = kb;

    // 3) kat-icon name(下载/导出图标)
    var icons = [];
    Array.prototype.forEach.call(document.querySelectorAll('kat-icon'), function (ic) {
      var n = ic.getAttribute('name') || ic.getAttribute('icon') || '';
      if (n) icons.push(n);
    });
    out.iconNames = icons;

    // 4) 含"下载/导出/下载报告"文本的元素
    var dl = [];
    Array.prototype.forEach.call(document.querySelectorAll('*'), function (el) {
      if (el.children.length > 2) return;
      var t = (el.innerText || el.textContent || '').trim();
      if (t && t.length < 30 && /下载|导出|Download|Export|CSV/.test(t)) {
        dl.push({ tag: el.tagName.toLowerCase(), text: t, cls: (el.className || '').toString().slice(0, 60), href: el.getAttribute('href') || '' });
      }
    });
    out.downloadish = dl.slice(0, 20);

    // 5) 分页信息
    var pg = [];
    Array.prototype.forEach.call(document.querySelectorAll('*'), function (el) {
      if (el.children.length > 3) return;
      var t = (el.innerText || el.textContent || '').trim();
      if (t && t.length < 60 && /(共|第\s*\d+\s*[-–]\s*\d+|of\s+\d+|显示全部|每页|Rows per page|显示)/.test(t)) {
        pg.push(t);
      }
    });
    out.pagination = pg.slice(0, 15);

    // 6) 表格区域尾部文本(找下载/分页)
    var bt = (document.body.innerText || '');
    out.bodyTail = bt.slice(Math.max(0, bt.length - 1200));
    out.textLen = bt.length;
    return JSON.stringify({ status: 'OK', data: out });
  } catch (e) {
    return JSON.stringify({ status: 'ERR', msg: String(e) });
  }
})();
