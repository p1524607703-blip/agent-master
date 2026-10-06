// 读取报告页当前状态: 日期控件值 / 按钮列表 / 是否有数据 / 提示文本
(function () {
  try {
    var ps = document.querySelectorAll('kat-date-picker');
    var vals = [];
    for (var i = 0; i < ps.length; i++) {
      var p = ps[i], k = p.shadowRoot ? p.shadowRoot.querySelector('kat-input') : null;
      var inp = k ? (k.shadowRoot ? k.shadowRoot.querySelector('input') : k) : null;
      vals.push(inp && inp.value ? inp.value : p.getAttribute('value'));
    }
    var labels = [];
    Array.prototype.forEach.call(document.querySelectorAll('kat-button'), function (b) { labels.push(b.getAttribute('label') || ''); });
    var txt = document.body.innerText || '';
    var m = txt.match(/可能尚未完全提供自[^\n]*/);
    var usd = (txt.match(/US\$/g) || []).length;
    // 表格区域的真实行数: 找到表头「（父）ASIN」之后的内容片段
    var tail = '';
    var idx = txt.indexOf('订单商品总数 - B2B');
    if (idx >= 0) tail = txt.slice(idx + 10, idx + 400).replace(/\s+/g, ' ');
    return JSON.stringify({
      status: 'OK', url: location.href, pickers: vals, katButtons: labels,
      hint: m ? m[0].slice(0, 120) : '', usdCount: usd, textLen: txt.length,
      loading: /加载|Loading|正在加载/.test(txt),
      tableTail: tail,
      reportText: (function () {
        var i = txt.indexOf('业务报告 |');
        return i >= 0 ? txt.slice(i, i + 900).replace(/\s+/g, ' ') : '(未找到报告区)';
      })()
    });
  } catch (e) { return JSON.stringify({ status: 'ERR', msg: String(e) }); }
})();
