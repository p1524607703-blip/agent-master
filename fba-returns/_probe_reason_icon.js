(function(){
  try{
    var table = document.querySelector('table');
    if(!table) return JSON.stringify({status:'NO_TABLE'});
    var trs = Array.from(table.querySelectorAll('tbody tr')).filter(function(r){ return r.querySelectorAll('td').length >= 5; });
    var out = { totalRows: trs.length, withComment: 0, withSvg: 0, withImg: 0, commentContexts: [], iconClasses: {}, reasonHasIcon: 0 };
    trs.forEach(function(r, idx){
      var td = r.querySelectorAll('td')[4]; // Return Reason
      if(!td) return;
      var html = td.outerHTML || '';
      if(td.querySelectorAll('svg').length) out.withSvg++;
      if(td.querySelectorAll('img').length) out.withImg++;
      var lc = html.toLowerCase();
      if(lc.indexOf('comment') >= 0){
        out.withComment++;
        if(out.commentContexts.length < 8){
          var i = lc.indexOf('comment');
          out.commentContexts.push({ row: idx+1, ctx: html.slice(Math.max(0, i-160), i+180).replace(/\s+/g,' ') });
        }
      }
      var iconEls = td.querySelectorAll('[class*="icon"]');
      if(iconEls.length) out.reasonHasIcon++;
      Array.from(iconEls).forEach(function(e){
        ((e.getAttribute('class')||'').split(/\s+/)).forEach(function(t){ if(/icon/i.test(t)) out.iconClasses[t] = (out.iconClasses[t]||0)+1; });
      });
    });
    return JSON.stringify({status:'OK', out:out});
  }catch(e){ return JSON.stringify({status:'ERR', msg:String(e)}); }
})();
