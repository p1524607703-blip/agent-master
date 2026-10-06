// 探测: kat-date-picker / kat-button 的 shadow DOM 内部结构
(function () {
  try {
    var out = { url: location.href, pickers: [], buttons: [] };

    Array.prototype.forEach.call(document.querySelectorAll('kat-date-picker'), function (p, idx) {
      var rec = { idx: idx, value: p.getAttribute('value'), hasShadow: !!p.shadowRoot, attrs: {} };
      Array.prototype.forEach.call(p.attributes, function (a) { rec.attrs[a.name] = String(a.value).slice(0, 60); });
      if (p.shadowRoot) {
        var ins = [];
        Array.prototype.forEach.call(p.shadowRoot.querySelectorAll('input,select,button,[role=button]'), function (i) {
          ins.push({
            tag: i.tagName.toLowerCase(),
            type: i.getAttribute('type') || '',
            cls: (i.className || '').toString().slice(0, 120),
            id: i.id || '',
            name: i.getAttribute('name') || '',
            value: i.value != null ? String(i.value).slice(0, 40) : '',
            ph: i.getAttribute('placeholder') || '',
            aria: i.getAttribute('aria-label') || ''
          });
        });
        rec.shadowInputs = ins;
        rec.shadowHtmlHead = p.shadowRoot.innerHTML.slice(0, 300);
      } else {
        rec.lightHtmlHead = p.innerHTML.slice(0, 200);
      }
      out.pickers.push(rec);
    });

    Array.prototype.forEach.call(document.querySelectorAll('kat-button'), function (b) {
      var rec = { label: b.getAttribute('label'), variant: b.getAttribute('variant'), hasShadow: !!b.shadowRoot };
      if (b.shadowRoot) {
        var inner = b.shadowRoot.querySelector('button');
        rec.innerTag = inner ? inner.tagName.toLowerCase() : '';
        rec.innerCls = inner ? (inner.className || '').toString().slice(0, 120) : '';
        rec.innerText = inner ? (inner.innerText || '').trim().slice(0, 40) : '';
        rec.disabled = inner ? !!inner.disabled : null;
      }
      out.buttons.push(rec);
    });

    // kat-dropdown(日期预设 / 每页行数)
    var dds = [];
    Array.prototype.forEach.call(document.querySelectorAll('kat-dropdown'), function (d) {
      var rec = { label: d.getAttribute('label') || '', value: d.getAttribute('value') || '', hasShadow: !!d.shadowRoot };
      if (d.shadowRoot) {
        var s = d.shadowRoot.querySelector('select');
        if (s) {
          rec.options = Array.prototype.map.call(s.options, function (o) { return String(o.value).slice(0, 40) + '|' + (o.text || '').slice(0, 30); }).slice(0, 20);
          rec.selected = s.value;
        }
      }
      dds.push(rec);
    });
    out.dropdowns = dds;

    return JSON.stringify({ status: 'OK', data: out });
  } catch (e) {
    return JSON.stringify({ status: 'ERR', msg: String(e) });
  }
})();
