(() => {
  const flat=[];
  const walk=r=>{try{r.querySelectorAll('*').forEach(e=>{flat.push(e); if(e.shadowRoot) walk(e.shadowRoot);});}catch(e){}};
  walk(document);
  const t=e=>{try{return (e.innerText||e.textContent||'').trim();}catch(x){return '';}};
  const cs=flat.find(e=>e.id==='country-selector');
  const err=flat.find(e=>t(e).includes("reading 'call'"));
  return JSON.stringify({
    vendorTest: window.__VENDORTEST || null,
    countrySelector: cs ? (cs.outerHTML||'').slice(0,800) : null,
    errPresent: !!err,
    errText: err ? t(err).slice(0,150) : null,
    mfeChildCount: (()=>{const m=flat.find(e=>e.id==='DSP_CAMPAIGN_GENERAL_SECTION_MFE'); return m?m.children.length:null;})()
  }, null, 1);
})()
