// 探测: 多种方式尝试给 kat-date-picker 注入日期, 验证哪种能被组件接受(不点应用)
(function () {
  try {
    var out = { steps: [] };
    function ki(p) { return p.shadowRoot ? p.shadowRoot.querySelector('kat-input') : null; }
    function realInput(k) {
      if (!k) return null;
      if (k.shadowRoot) return k.shadowRoot.querySelector('input') || k;
      return k.tagName.toLowerCase() === 'input' ? k : k.querySelector('input');
    }
    var ps = document.querySelectorAll('kat-date-picker');
    out.pickerCount = ps.length;
    if (ps.length < 2) return JSON.stringify({ status: 'ERR', msg: 'picker<2' });

    var host = ps[0], k = ki(host), inp = realInput(k);
    out.katInputTag = k ? k.tagName.toLowerCase() : 'none';
    out.katInputHasShadow = k ? !!k.shadowRoot : false;
    out.realInputTag = inp ? inp.tagName.toLowerCase() : 'none';
    out.realInputCls = inp ? (inp.className || '').toString().slice(0, 120) : '';
    out.before = { hostValue: host.getAttribute('value'), katValue: k ? k.getAttribute('value') : '', inputValue: inp ? inp.value : '' };

    var TARGET = '2026/09/06';

    // 方式 A: 仅 setAttribute + change
    try {
      host.setAttribute('value', TARGET);
      host.dispatchEvent(new Event('change', { bubbles: true }));
      out.steps.push({ m: 'A_setAttribute_host', kat: k.getAttribute('value'), inp: inp.value, host: host.getAttribute('value') });
    } catch (e) { out.steps.push({ m: 'A', err: String(e) }); }

    // 方式 B: kat-input setAttribute
    try {
      k.setAttribute('value', TARGET);
      k.dispatchEvent(new Event('change', { bubbles: true }));
      out.steps.push({ m: 'B_setAttribute_katinput', kat: k.getAttribute('value'), inp: inp.value });
    } catch (e) { out.steps.push({ m: 'B', err: String(e) }); }

    // 方式 C: native setter on real input + input + change
    try {
      var proto = inp.tagName.toLowerCase() === 'input' ? window.HTMLInputElement.prototype : window.HTMLElement.prototype;
      var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
      setter.call(inp, TARGET);
      inp.dispatchEvent(new Event('input', { bubbles: true }));
      inp.dispatchEvent(new Event('change', { bubbles: true }));
      out.steps.push({ m: 'C_nativeSetter', kat: k.getAttribute('value'), inp: inp.value, host: host.getAttribute('value') });
    } catch (e) { out.steps.push({ m: 'C', err: String(e) }); }

    // 方式 D: 组件实例方法探测
    out.hostMethods = Object.keys(host).filter(function (x) { return typeof host[x] === 'function'; }).slice(0, 30);
    out.hostProtoMethods = (function () {
      var m = [], n = Object.getPrototypeOf(host);
      while (n && m.length < 40) { Object.getOwnPropertyNames(n).forEach(function (x) { if (m.indexOf(x) < 0) m.push(x); }); n = Object.getPrototypeOf(n); }
      return m.slice(0, 60);
    })();

    // 方式 E: 键盘模拟(先清空再逐字输入)
    try {
      inp.focus();
      inp.select && inp.select();
      document.execCommand && document.execCommand('selectAll', false, null);
      out.steps.push({ m: 'E_focus', active: document.activeElement ? document.activeElement.tagName.toLowerCase() : '' });
    } catch (e) { out.steps.push({ m: 'E', err: String(e) }); }

    // 方式 F: 若 kat-input 暴露 setValue/value 属性
    try {
      if (typeof k.setValue === 'function') { k.setValue(TARGET); out.steps.push({ m: 'F_setValue', kat: k.getAttribute('value'), inp: inp.value }); }
      else out.steps.push({ m: 'F_no_setValue' });
    } catch (e) { out.steps.push({ m: 'F', err: String(e) }); }

    out.after = { hostValue: host.getAttribute('value'), katValue: k.getAttribute('value'), inputValue: inp ? inp.value : '' };
    return JSON.stringify({ status: 'OK', data: out });
  } catch (e) {
    return JSON.stringify({ status: 'ERR', msg: String(e) });
  }
})();
