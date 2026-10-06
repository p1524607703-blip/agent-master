(() => {
  const NEEDLE = 'Cannot read properties of undefined';
  const desc = e => {
    if (!e || !e.getAttribute) return null;
    const attrs = {};
    for (const a of e.attributes) attrs[a.name] = String(a.value).slice(0, 120);
    return {
      tag: e.tagName,
      attrs,
      rect: (r => ({ x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }))(e.getBoundingClientRect())
    };
  };

  const hits = [...document.querySelectorAll('*')].filter(e => e.textContent && e.textContent.includes(NEEDLE));
  const deepest = hits.filter(e => ![...e.children].some(c => c.textContent && c.textContent.includes(NEEDLE)));

  const out = { url: location.href, hitCount: hits.length, deepestCount: deepest.length, targets: [] };

  deepest.slice(0, 4).forEach(el => {
    const rec = { self: desc(el) };
    // 自身 outerHTML
    rec.selfHTML = (el.outerHTML || '').slice(0, 1500);
    // 祖先链
    rec.ancestors = [];
    let p = el.parentElement, i = 0;
    while (p && i < 7) { rec.ancestors.push(desc(p)); p = p.parentElement; i++; }
    // 父节点全部子元素（看本该渲染成 select 的位置有什么）
    const par = el.parentElement;
    if (par) {
      rec.parentChildren = [...par.children].map(c => ({
        tag: c.tagName, id: c.id || '', cls: String(c.className || '').slice(0, 80),
        text: (c.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 80),
        html: (c.outerHTML || '').slice(0, 600)
      }));
    }
    out.targets.push(rec);
  });

  // 找「显示可选设置」开关
  const toggleCands = [...document.querySelectorAll('*')].filter(e => {
    const t = (e.innerText || '').trim();
    return t === '显示可选设置' || t === '显示可选设置 ' || /^(显示|隐藏)可选设置$/.test(t);
  });
  out.toggle = toggleCands.slice(0, 6).map(e => ({
    ...desc(e),
    text: (e.innerText || '').trim(),
    ariaExpanded: e.getAttribute('aria-expanded'),
    // 往上找可点击祖先
    clickableAncestors: (() => {
      const a = []; let p = e; let i = 0;
      while (p && i < 5) { a.push(desc(p)); p = p.parentElement; i++; }
      return a;
    })()
  }));

  // 国家/地区 那一行结构
  const rowLabel = [...document.querySelectorAll('*')].find(e => (e.innerText || '').trim() === '国家/地区');
  if (rowLabel) {
    out.countryRow = {
      label: desc(rowLabel),
      up: (() => { const a = []; let p = rowLabel, i = 0; while (p && i < 5) { a.push(desc(p)); p = p.parentElement; i++; } return a; })(),
      rowHTML: (() => { let p = rowLabel; for (let i = 0; i < 3 && p.parentElement; i++) p = p.parentElement; return (p.outerHTML || '').slice(0, 2500); })()
    };
  }

  return JSON.stringify(out, null, 1);
})()
