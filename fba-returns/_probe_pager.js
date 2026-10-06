(function(){
  try{
    var t = document.querySelector('table');
    var trs = t ? Array.from(t.querySelectorAll('tbody tr')).filter(function(r){ return r.querySelectorAll('td').length >= 5; }) : [];
    // 每页条数 select
    var sel = Array.from(document.querySelectorAll('select')).find(function(s){
      return /results per page|per page|每页/i.test(Array.from(s.options).map(function(o){ return o.text || ''; }).join('|'));
    });
    // 所有 select 概览
    var sels = Array.from(document.querySelectorAll('select')).map(function(s){
      return { value: s.value, opts: Array.from(s.options).map(function(o){ return o.text; }).slice(0,12) };
    });
    // 分页控件候选
    var cand = Array.from(document.querySelectorAll('div,section,nav,footer,span')).filter(function(e){
      var tx = e.innerText || '';
      return /of\s*\d|Next|Prev|下一页/.test(tx) && tx.length < 600;
    });
    cand.sort(function(a,b){ return (a.innerText||'').length - (b.innerText||'').length; });
    var pagerText = cand.length ? cand[0].innerText.replace(/\s+/g,' ').trim().slice(0,300) : null;
    // Next 按钮实况
    var btns = Array.from(document.querySelectorAll('button,a')).filter(function(b){ return b.offsetParent !== null; });
    var nexts = btns.filter(function(b){
      var tx = (b.innerText||b.getAttribute('aria-label')||b.title||'').trim();
      return /next|›|»/i.test(tx);
    }).map(function(b){
      return { text:(b.innerText||'').trim().slice(0,30), aria:(b.getAttribute('aria-label')||'').slice(0,40),
               disabled: !!b.disabled, cls: (b.className||'').toString().slice(0,60) };
    });
    // 行数文本候选(如 "1-1000 of 9000")
    var countTxt = null;
    var cc = Array.from(document.querySelectorAll('div,span,td')).filter(function(e){
      var tx = (e.innerText||'').trim();
      return /^\s*[\d,]+\s*[-–]\s*[\d,]+\s*(of|共)/i.test(tx) && tx.length < 80;
    });
    if (cc.length) countTxt = cc.map(function(e){ return e.innerText.replace(/\s+/g,' ').trim(); }).slice(0,5);
    // 当前页码高亮
    var active = Array.from(document.querySelectorAll('[aria-current="page"],[class*="active"],[class*="selected"]')).filter(function(e){
      var tx=(e.innerText||'').trim(); return /^\d+$/.test(tx) && tx.length<4;
    }).map(function(e){ return e.innerText.trim(); }).slice(0,5);
    return JSON.stringify({ status:'OK', url: location.href, rowCount: trs.length,
      selectValue: sel ? sel.value : null, sels: sels.slice(0,4), pagerText: pagerText,
      nextButtons: nexts, rangeText: countTxt, activePage: active });
  }catch(e){ return JSON.stringify({ status:'ERR', msg:String(e) }); }
})();
