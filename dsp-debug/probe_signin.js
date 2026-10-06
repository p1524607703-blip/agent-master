(() => {
  const txt = (document.body && document.body.innerText) ? document.body.innerText.replace(/\n{2,}/g, '\n').slice(0, 2000) : '';
  const inputs = [...document.querySelectorAll('input')].map(i => ({
    type: i.type, id: i.id, name: i.name, ph: i.placeholder, val: i.type === 'password' ? '***' : (i.value || '').slice(0, 40)
  }));
  const btns = [...document.querySelectorAll('button, input[type=submit], a[role=button]')].map(b => ({
    t: (b.innerText || b.value || b.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 40), id: b.id
  })).filter(b => b.t);
  return JSON.stringify({ url: location.href, title: document.title, body: txt, inputs, btns: btns.slice(0, 20) }, null, 1);
})()
