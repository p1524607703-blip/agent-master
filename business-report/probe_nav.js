// 探测: 业务报告页左侧导航 + 日期控件 + 表格容器
// 输出 JSON: { url, links:[{text, href}], navTexts:[], dateInputs:[], tableContainers:[], bodyHead }
(function () {
  try {
    var out = { url: location.href, title: document.title };
    var links = [];
    Array.prototype.forEach.call(document.querySelectorAll('a'), function (a) {
      var t = (a.innerText || a.textContent || '').trim().replace(/\s+/g, ' ');
      if (!t) return;
      links.push({ text: t.slice(0, 80), href: (a.getAttribute('href') || '').slice(0, 200) });
    });
    out.links = links.slice(0, 120);
    out.linkCount = links.length;

    // 可能是自定义元素的导航项(非 a 标签)
    var navTexts = [];
    var sels = ['nav', '[class*=nav]', '[class*=Nav]', '[class*=menu]', '[class*=Menu]', '[class*=side]', '[class*=Side]', 'aside'];
    for (var i = 0; i < sels.length; i++) {
      try {
        Array.prototype.forEach.call(document.querySelectorAll(sels[i]), function (n) {
          var t = (n.innerText || '').trim().replace(/\s+/g, ' ');
          if (t && t.length < 600) navTexts.push({ sel: sels[i], text: t.slice(0, 400) });
        });
      } catch (e) {}
    }
    out.navTexts = navTexts.slice(0, 12);

    // 日期/输入类控件
    var inputs = [];
    Array.prototype.forEach.call(document.querySelectorAll('input,select,[class*=date],[class*=Date],[class*=picker]'), function (el) {
      var tag = el.tagName.toLowerCase();
      inputs.push({
        tag: tag,
        type: el.getAttribute('type') || '',
        cls: (el.className || '').toString().slice(0, 100),
        id: el.id || '',
        ph: el.getAttribute('placeholder') || '',
        aria: el.getAttribute('aria-label') || ''
      });
    });
    out.inputs = inputs.slice(0, 60);
    out.inputCount = inputs.length;

    // 表格容器
    var tbls = [];
    Array.prototype.forEach.call(document.querySelectorAll('table,[class*=grid],[class*=Grid],[role=grid],[role=table]'), function (t) {
      tbls.push({ tag: t.tagName.toLowerCase(), cls: (t.className || '').toString().slice(0, 120), rows: t.querySelectorAll('tr,[role=row]').length });
    });
    out.tables = tbls.slice(0, 20);

    out.bodyHead = (document.body.innerText || '').trim().slice(0, 2500);
    return JSON.stringify({ status: 'OK', data: out });
  } catch (e) {
    return JSON.stringify({ status: 'ERR', msg: String(e) });
  }
})();
