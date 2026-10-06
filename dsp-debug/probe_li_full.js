JSON.stringify((function () {
  function clean(s) { return ((s || '') + '').replace(/\s+/g, ' ').trim(); }
  function deepAll(root, sel, out) {
    out = out || [];
    if (!root) return out;
    try { var h = root.querySelectorAll(sel); for (var i = 0; i < h.length; i++) out.push(h[i]); } catch (e) {}
    try { var a = root.querySelectorAll('*'); for (var j = 0; j < a.length; j++) { if (a[j].shadowRoot) deepAll(a[j].shadowRoot, sel, out); } } catch (e) {}
    return out;
  }
  function deepText(root, out) {
    out = out || [];
    if (!root) return out;
    var k = root.children || [];
    for (var i = 0; i < k.length; i++) {
      var e = k[i];
      if (e.children.length === 0) { var t = clean(e.innerText); if (t && t.length < 90) out.push(t); }
      if (e.shadowRoot) deepText(e.shadowRoot, out);
      deepText(e, out);
    }
    return out;
  }
  function uniq(a) { return a.filter(function (v, i) { return v && a.indexOf(v) === i; }); }

  var out = { url: location.href };

  // 1) 主内容区（h1 之后）
  var main = document.querySelector('main') || document.body;
  out.mainText = uniq(deepText(main, [])).slice(0, 400);

  // 2) 按 h4 分节
  var h4s = deepAll(document, 'h4', []);
  out.sections = [];
  for (var i = 0; i < h4s.length; i++) {
    var title = clean(h4s[i].innerText);
    if (!title) continue;
    var node = h4s[i].parentElement, text = [];
    for (var step = 0; step < 6 && node && text.length < 6; step++) {
      text = uniq(deepText(node, []));
      if (text.length > 6) break;
      node = node.parentElement;
    }
    out.sections.push({ title: title, texts: text.slice(0, 90) });
  }

  // 3) 单选/复选组
  var groups = {};
  deepAll(document, 'input[type="radio"],input[type="checkbox"]', []).forEach(function (e) {
    var key = e.name || e.getAttribute('data-group') || e.id || '(no-name)';
    var lab = '';
    try { if (e.id) { var l = document.querySelector('label[for="' + e.id + '"]'); if (l) lab = clean(l.innerText); } } catch (x) {}
    if (!lab && e.parentElement) lab = clean(e.parentElement.innerText).slice(0, 70);
    (groups[key] = groups[key] || []).push((e.checked ? '[✓] ' : '[ ] ') + lab + '  (val=' + (e.value || '') + ')');
  });
  out.groups = groups;

  // 4) 下拉触发器
  out.dropdowns = uniq(deepAll(document, 'button,[role="button"],[role="combobox"]', []).map(function (e) {
    var t = clean(e.innerText);
    return (e.getAttribute('aria-haspopup') ? '[popup] ' : '') + t.slice(0, 40);
  })).slice(0, 60);

  // 5) 表格
  out.tables = deepAll(document, 'table,[role="grid"]', []).slice(0, 6).map(function (tb) {
    var txt = clean(tb.innerText).slice(0, 900);
    return txt;
  });

  // 6) 文本域 / 输入
  out.inputs = deepAll(document, 'input[type="text"],input[type="number"],input[type="search"],textarea,select', []).map(function (e) {
    return { id: e.id || '', type: e.type || e.tagName.toLowerCase(), val: (e.value || '').slice(0, 40), ph: e.placeholder || '' };
  }).filter(function (x) { return x.id || x.val || x.ph; }).slice(0, 40);

  return out;
})())
