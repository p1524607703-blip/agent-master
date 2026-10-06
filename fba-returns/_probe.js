(function(){
  try{
    var out={};
    out.url = location.href;
    var sels = Array.from(document.querySelectorAll('select'));
    out.selects = sels.map(function(s){return {value:s.value, n:s.options.length, opts:Array.from(s.options).map(function(o){return o.value;}).slice(0,12)};});
    var tables = Array.from(document.querySelectorAll('table'));
    out.tableCount = tables.length;
    out.tables = tables.map(function(t){return {rows: t.querySelectorAll('tbody tr').length, head:(t.querySelector('thead')?t.querySelector('thead').innerText:'').replace(/\s+/g,' ').trim().slice(0,140)};});
    var bt = document.body.innerText;
    out.pagMatch = (bt.match(/\d+\s*-\s*\d+\s*of\s*[\d,]+/i)||[])[0] || null;
    out.resultsMatch = (bt.match(/[\d,]+\s*(results|items|returns)/i)||[])[0] || null;
    var btns = Array.from(document.querySelectorAll('button,a')).map(function(b){return {t:(b.innerText||b.getAttribute('aria-label')||b.title||'').trim().slice(0,25), dis:!!b.disabled};}).filter(function(x){return /next|prev|page|[›»]|>|<|^\d+$/i.test(x.t);});
    out.pageBtns = btns.slice(0,14);
    return JSON.stringify({status:'OK', out:out});
  }catch(e){return JSON.stringify({status:'ERR', msg:String(e)});}
})();
