// 探测: 业务报告左侧菜单项的可点击元素结构(按父商品)
(function () {
  try {
    var out = { url: location.href, hits: [] };
    // 1) 收集所有可能含 "site-metrics" 的 href
    var hrefs = [];
    Array.prototype.forEach.call(document.querySelectorAll('a'), function (a) {
      var h = a.getAttribute('href') || '';
      if (/site-metrics|report/i.test(h)) hrefs.push({ text: (a.innerText || '').trim().slice(0, 60), href: h.slice(0, 300) });
    });
    out.reportHrefs = hrefs.slice(0, 40);

    // 2) 找文本含 "按父商品" / "父商品" 的元素链
    function chain(el) {
      var c = [], n = el, i = 0;
      while (n && n !== document.body && i < 8) {
        c.push({
          tag: n.tagName.toLowerCase(),
          cls: (n.className || '').toString().slice(0, 120),
          id: n.id || '',
          role: n.getAttribute && n.getAttribute('role') || '',
          href: n.getAttribute && (n.getAttribute('href') || '') || '',
          data: JSON.stringify(n.dataset || {}).slice(0, 300),
          childCount: n.children ? n.children.length : 0
        });
        n = n.parentElement; i++;
      }
      return c;
    }
    var all = document.querySelectorAll('*');
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      if (el.children && el.children.length > 6) continue;
      var t = (el.innerText || el.textContent || '').trim();
      if (t && t.length < 40 && /按父商品|父商品|Parent/.test(t)) {
        out.hits.push({ text: t, chain: chain(el) });
        if (out.hits.length >= 6) break;
      }
    }

    // 3) 报告菜单容器内的所有叶子项文本 + 元素信息
    var menuItems = [];
    Array.prototype.forEach.call(document.querySelectorAll('[class*=report-menu],[class*=ReportMenu],[class*=sidebar],[class*=SideBar],[class*=side-nav]'), function (c) {
      Array.prototype.forEach.call(c.querySelectorAll('li,a,div,span'), function (it) {
        var t = (it.innerText || '').trim().replace(/\s+/g, ' ');
        if (!t || t.length > 60 || it.children.length > 0) return;
        if (/业务报告|控制面板|销售和流量|卖家绩效|各月|ASIN/.test(t)) {
          menuItems.push({
            text: t,
            tag: it.tagName.toLowerCase(),
            cls: (it.className || '').toString().slice(0, 100),
            href: it.getAttribute && (it.getAttribute('href') || '') || '',
            onclick: (it.getAttribute && it.getAttribute('onclick') || '').slice(0, 200)
          });
        }
      });
    });
    out.menuItems = menuItems.slice(0, 60);
    return JSON.stringify({ status: 'OK', data: out });
  } catch (e) {
    return JSON.stringify({ status: 'ERR', msg: String(e) });
  }
})();
