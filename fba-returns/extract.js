(function(){
  try{
    var table = document.querySelector('table');
    if(!table) return JSON.stringify({status:'NO_TABLE'});
    var trs = Array.from(table.querySelectorAll('tbody tr'));
    var rows = trs.filter(function(r){ return r.querySelectorAll('td').length >= 5; });
    var data = rows.map(function(r){
      return Array.from(r.querySelectorAll('td')).map(function(td){
        return (td.innerText || td.textContent || '').replace(/\s+/g,' ').trim();
      });
    });
    return JSON.stringify({status:'OK', rowCount: data.length, sample: data.slice(0,2), totalTds: trs.length});
  }catch(e){ return JSON.stringify({status:'ERR', msg: String(e)}); }
})();
