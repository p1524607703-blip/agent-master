(function(){
  try{
    var cands = Array.from(document.querySelectorAll('button,a'));
    var next = cands.find(function(b){
      var t=(b.innerText||b.getAttribute('aria-label')||b.title||'').trim();
      if(b.offsetParent===null) return false;
      if(b.disabled) return false;
      if(/disabled/i.test(String(b.className||''))) return false;
      return /^next$/i.test(t) || /next page/i.test(t);
    });
    if(!next) return JSON.stringify({status:'NO_NEXT'});
    next.click();
    return JSON.stringify({status:'OK', clicked:(next.innerText||next.getAttribute('aria-label')||'').trim().slice(0,20)});
  }catch(e){return JSON.stringify({status:'ERR',msg:String(e)});}
})();
