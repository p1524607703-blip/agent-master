(() => {
  const out = { url: location.href };

  const res = performance.getEntriesByType('resource').map(e => e.name);
  const ver = {};
  for (const u of res) {
    const m = u.match(/versionID=(\d+)/);
    if (!m) continue;
    const host = (u.match(/^https?:\/\/([^/]+)/) || [])[1] || '?';
    const f = u.split('?')[0].split('/').pop();
    (ver[host + ' @ ' + m[1]] = ver[host + ' @ ' + m[1]] || []).push(f);
  }
  out.totalResources = res.length;
  out.versionGroups = Object.keys(ver).sort().map(k => ({ group: k, count: ver[k].length, files: ver[k].slice(0, 10) }));
  out.orderMfeAssets = res.filter(u => /ddwxeg2ktxtzx|d1a6ad4gq10kca|d2uvmb4xqforyj/i.test(u)).slice(0, 40);

  out.slots = [...document.querySelectorAll('mfe-slot')].map(s => {
    let sc = null;
    try { sc = JSON.parse(s.getAttribute('data-slot-view-model')).slotConfig; } catch (e) {}
    return sc ? { id: s.id, name: sc.name, endpoint: sc.endpoint, serviceName: sc.serviceName, integrity: sc.integrity, authProtocol: sc.authProtocol } : { id: s.id, parse: 'fail' };
  });

  const flat = [];
  const walk = r => { try { r.querySelectorAll('*').forEach(e => { flat.push(e); if (e.shadowRoot) walk(e.shadowRoot); }); } catch (e) {} };
  walk(document);
  const t = e => { try { return (e.innerText || e.textContent || '').trim(); } catch (x) { return ''; } };
  const err = flat.find(e => t(e).includes("reading 'call'"));
  out.countryErrorNow = err ? { present: true, text: t(err).slice(0, 140) } : { present: false };
  const cs = flat.find(e => e.id === 'country-selector');
  out.countrySelectorHtml = cs ? (cs.outerHTML || '').slice(0, 600) : null;
  const mfe = flat.find(e => e.id === 'DSP_CAMPAIGN_GENERAL_SECTION_MFE');
  out.mfeState = mfe ? { childCount: mfe.children.length, h: Math.round(mfe.getBoundingClientRect().height) } : null;
  const nameInput = flat.find(e => e.tagName === 'INPUT' && /campaign.*name|order.*name/i.test(e.id || ''));
  out.nameVal = nameInput ? nameInput.value : null;

  return JSON.stringify(out, null, 1);
})()
