(async () => {
  const out = { url: location.href };

  // 1) 所有带 versionID 的资源，按 versionID 分组
  const res = performance.getEntriesByType('resource').map(e => e.name);
  const ver = {};
  for (const u of res) {
    const m = u.match(/versionID=(\d+)/);
    if (!m) continue;
    const host = (u.match(/^https?:\/\/([^/]+)/) || [])[1] || '?';
    const f = u.split('?')[0].split('/').pop();
    (ver[host + ' @ ' + m[1]] = ver[host + ' @ ' + m[1]] || []).push(f);
  }
  out.versionGroups = Object.keys(ver).sort().map(k => ({ group: k, count: ver[k].length, files: ver[k].slice(0, 12) }));
  out.totalResources = res.length;

  // 2) MFE slot 的 config 端点
  const slots = [...document.querySelectorAll('mfe-slot')].map(s => {
    let cfg = null;
    try { cfg = JSON.parse(s.getAttribute('data-slot-view-model')); } catch (e) {}
    const sc = cfg && cfg.slotConfig ? cfg.slotConfig : null;
    return {
      id: s.id,
      name: sc && sc.name,
      endpoint: sc && sc.endpoint,
      serviceName: sc && sc.serviceName,
      integrity: sc && sc.integrity,
      authProtocol: sc && sc.authProtocol
    };
  });
  out.slots = slots;

  // 3) 试着 fetch 一次 config（同源策略允许则能拿到）
  const ep = slots.find(s => s.endpoint);
  out.configFetch = null;
  if (ep) {
    try {
      const r = await fetch(ep.endpoint, { credentials: 'include' });
      const t = await r.text();
      out.configFetch = { endpoint: ep.endpoint, status: r.status, len: t.length, head: t.slice(0, 1800) };
    } catch (e) {
      out.configFetch = { endpoint: ep.endpoint, error: String(e && e.message || e) };
    }
  }

  // 4) 当前 国家/地区 区域是否又崩了
  const flat = [];
  const walk = r => { try { r.querySelectorAll('*').forEach(e => { flat.push(e); if (e.shadowRoot) walk(e.shadowRoot); }); } catch (e) {} };
  walk(document);
  const t = e => { try { return (e.innerText || e.textContent || '').trim(); } catch (x) { return ''; } };
  const err = flat.find(e => t(e).includes("reading 'call'"));
  out.countryErrorNow = err ? { present: true, text: t(err).slice(0, 120), box: (r => ({ y: Math.round(r.y), h: Math.round(r.height) }))(err.getBoundingClientRect()) } : { present: false };
  const cs = flat.find(e => e.id === 'country-selector');
  out.countrySelector = cs ? { childCount: cs.children.length, html: (cs.outerHTML || '').slice(0, 700) } : null;
  const mfe = flat.find(e => e.id === 'DSP_CAMPAIGN_GENERAL_SECTION_MFE');
  out.mfeState = mfe ? { childCount: mfe.children.length, box: (r => ({ w: Math.round(r.width), h: Math.round(r.height) }))(mfe.getBoundingClientRect()) } : null;

  return JSON.stringify(out, null, 1);
})()
