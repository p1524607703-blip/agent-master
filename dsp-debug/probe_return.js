(() => {
  const hid = {};
  document.querySelectorAll('input[type=hidden]').forEach(i => { if (i.name && !(i.name in hid)) hid[i.name] = i.value; });
  const b64 = s => { try { return decodeURIComponent(escape(atob(s))); } catch (e) { return '<decode-fail>'; } };
  const out = {
    url: location.href,
    title: document.title,
    formAction: (document.querySelector('form') || {}).action || null,
    returnToRaw: hid['openid.return_to'] || null,
    returnToDecoded: hid['openid.return_to'] ? b64(String(hid['openid.return_to']).replace(/^ape:/, '')) : null,
    claimedId: hid['openid.claimed_id'] ? b64(String(hid['openid.claimed_id']).replace(/^ape:/, '')) : null,
    prevRID: hid['prevRID'] ? b64(String(hid['prevRID']).replace(/^ape:/, '')) : null,
    hasEmailInput: !!document.querySelector('#ap_email, input[name=email]'),
    cookiesHere: document.cookie.split(';').map(c => c.trim().split('=')[0]).slice(0, 40),
    aLinks: [...document.querySelectorAll('a[href]')].map(a => ({ t: (a.innerText || '').trim().slice(0, 30), h: a.href })).slice(0, 25)
  };
  return JSON.stringify(out, null, 1);
})()
