(() => {
  const out = { url: location.href, title: document.title, ready: document.readyState };
  const links = [...document.querySelectorAll('a[href]')].map(a => ({
    t: (a.innerText || a.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 40),
    h: a.href
  }));
  out.dspLinks = links.filter(l => /dsp/i.test(l.h) || /dsp/i.test(l.t)).slice(0, 30);
  out.createLinks = links.filter(l => /campaign|order|line.?item|create|new/i.test(l.h) || /创建|新建/.test(l.t)).slice(0, 30);
  out.totalLinks = links.length;
  out.sample = links.slice(0, 50);
  out.avatar = (document.body ? document.body.innerText : '').slice(0, 1200);
  return JSON.stringify(out, null, 1);
})()
