(() => {
  const b = document.body ? document.body.innerText.replace(/\n{2,}/g, '\n') : '';
  const out = {
    url: location.href,
    title: document.title,
    ready: document.readyState,
    bodyLen: b.length,
    bodyHead: b.slice(0, 1100),
    signIn: /Amazon Sign-In|Sign in with the email/i.test(document.title + b),
    notFound: /Page not found|does not exist/i.test(b),
    dspLinks: [...document.querySelectorAll('a[href]')].map(a => a.href).filter(h => /\/dsp\//i.test(h)).slice(0, 20)
  };
  return JSON.stringify(out, null, 1);
})()
