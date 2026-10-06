(() => {
  const b = document.body ? document.body.innerText : '';
  return JSON.stringify({
    url: location.href, title: document.title, ready: document.readyState,
    bodyLen: b.length, bodyHead: b.slice(0, 900).replace(/\n{2,}/g, '\n'),
    iframes: [...document.querySelectorAll('iframe')].map(f => f.src).slice(0, 10),
    appRoots: [...document.querySelectorAll('[id]')].map(e => e.id).filter(x => /app|root|content|main/i.test(x)).slice(0, 20)
  }, null, 1);
})()
