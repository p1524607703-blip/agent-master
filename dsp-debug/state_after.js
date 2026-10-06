(() => {
  const flat = [];
  const walk = r => { try { r.querySelectorAll('*').forEach(e => { flat.push(e); if (e.shadowRoot) walk(e.shadowRoot); }); } catch (e) {} };
  walk(document);
  const txt = e => { try { return (e.innerText || e.textContent || '').trim(); } catch (x) { return ''; } };
  const box = e => (r => ({ x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }))(e.getBoundingClientRect());
  const byId = id => flat.find(e => e.id === id);

  const ids = ['d16g-rodeo-order-page-general-section-container', 'general-section-extender-wrapper', 'general-section-extender', 'country-selector', 'DSP_CAMPAIGN_GENERAL_SECTION_MFE', 'DSP_CAMPAIGN_GENERAL_SECTION_MFE_container'];
  const out = { url: location.href, blocks: {}, errPresent: false, errSample: null, mediaBox: null };

  ids.forEach(id => {
    const e = byId(id);
    if (!e) { out.blocks[id] = null; return; }
    out.blocks[id] = {
      box: box(e),
      display: getComputedStyle(e).display,
      visibility: getComputedStyle(e).visibility,
      opacity: getComputedStyle(e).opacity,
      overflow: getComputedStyle(e).overflow,
      childCount: e.children.length,
      text: txt(e).slice(0, 200),
      html: (e.outerHTML || '').slice(0, 900)
    };
  });

  const errEl = flat.find(e => txt(e).includes('Cannot read properties of undefined'));
  out.errPresent = !!errEl;
  if (errEl) out.errSample = txt(errEl).slice(0, 160);

  const media = flat.find(e => txt(e) === 'MEDIA');
  if (media) out.mediaBox = box(media);

  const nameInput = flat.find(e => e.id && /name/i.test(e.id) && e.tagName === 'INPUT');
  out.nameInput = nameInput ? { id: nameInput.id, val: nameInput.value, box: box(nameInput) } : null;

  return JSON.stringify(out, null, 1);
})()
