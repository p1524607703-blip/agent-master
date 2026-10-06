(() => {
  const vis = el => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const T = el => (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim().replace(/\s+/g, ' ').slice(0, 70);
  const tid = el => el.getAttribute('data-testid') || el.getAttribute('id') || '';

  const out = { url: location.href, title: document.title, ready: document.readyState };

  out.headings = [...document.querySelectorAll('h1,h2,h3,h4,h5,legend,[role=heading]')]
    .filter(vis).map(e => ({ tag: e.tagName, t: T(e) })).slice(0, 60);

  out.buttons = [...document.querySelectorAll('button,[role=button],input[type=submit],input[type=button],summary')]
    .filter(vis).map(e => ({ t: T(e), id: tid(e), disabled: e.disabled === true || e.getAttribute('aria-disabled') === 'true' }))
    .filter(b => b.t).slice(0, 90);

  out.links = [...document.querySelectorAll('a[href]')].filter(vis)
    .map(a => ({ t: T(a), h: a.getAttribute('href') })).filter(x => x.t).slice(0, 40);

  out.fields = [...document.querySelectorAll('input,select,textarea,[role=combobox],[role=textbox]')]
    .filter(vis).map(e => ({
      tag: e.tagName, type: e.type || '', id: e.id || '', name: e.name || '',
      testid: e.getAttribute('data-testid') || '',
      label: (e.labels && e.labels[0]) ? T(e.labels[0]) : (e.getAttribute('aria-label') || ''),
      ph: e.placeholder || '', req: !!(e.required || e.getAttribute('aria-required') === 'true'),
      val: e.type === 'password' ? '***' : String(e.value || '').slice(0, 30)
    })).slice(0, 90);

  const acc = [...document.querySelectorAll('*')].filter(e => {
    const t = T(e);
    return t && /可选|设置|高级|更多|折叠|展开|optional|advanced|settings/i.test(t) && vis(e) &&
      e.children.length <= 4 && (e.tagName === 'BUTTON' || e.tagName === 'SUMMARY' || e.tagName === 'A' || e.tagName === 'SPAN' || e.tagName === 'DIV' || e.tagName === 'LABEL');
  }).slice(0, 40).map(e => ({ tag: e.tagName, t: T(e), testid: e.getAttribute('data-testid') || '', id: e.id || '', cls: String(e.className || '').slice(0, 60) }));

  out.optionalish = acc;

  const bodyTxt = document.body ? document.body.innerText : '';
  out.errLines = bodyTxt.split('\n').map(s => s.trim()).filter(s => /error|错误|失败|cannot read|undefined|必填|required|无法/i.test(s)).slice(0, 30);

  return JSON.stringify(out, null, 1);
})()
