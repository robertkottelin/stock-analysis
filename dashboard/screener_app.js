"use strict";
/* Universe screener dashboard app logic. Depends on screener_data.js (window.SCREENER_DATA)
 * and the helpers/state defined inline in screener.html (esc, fmt*, scoreBar, tierChip,
 * sectorGroup, DATA). Kept as a separate file so the markup and the logic can be read
 * and edited independently. */

var FNONE = {type:"none"};
var FTEXT = {type:"text"};
var FNUM  = {type:"range", scale:1};
var FPCT  = {type:"range", scale:100};

var COLUMNS = [
  {key:"rank",   label:"#",           group:"core", numeric:true,  align:"num", filter:FNONE,
   title:"Rank by Overall score (non-duplicate rows only)",
   render:function(r){ return r.rank ? "#"+r.rank : "—"; },
   sortval:function(r){ return r.rank==null ? 1e9 : r.rank; }},
  {key:"name",   label:"Company",     group:"core", numeric:false, align:"namecell", filter:FNONE,
   title:"Company, ticker, exchange and sector", special:"name"},
  {key:"overall",     label:"Overall",      group:"core", numeric:true, align:"num", filter:FNUM,
   title:"0.65×Fundamentals + 0.35×AI-leverage",
   render:function(r){ return scoreBar(r.overall); }, sortval:function(r){ return r.overall; }},
  {key:"fund_score",  label:"Fundamentals", group:"core", numeric:true, align:"num", filter:FNUM,
   title:"Percentile composite: Quality 35% / Growth 20% / Balance sheet 15% / Valuation 30%",
   render:function(r){ return scoreBar(r.fund_score); }, sortval:function(r){ return r.fund_score; }},
  {key:"ai_score",    label:"AI leverage",  group:"core", numeric:true, align:"num", filter:FNUM,
   title:"Structural heuristic: industry base-rate + labor intensity + margin leverage (see row detail)",
   render:function(r){ return scoreBar(r.ai_score); }, sortval:function(r){ return r.ai_score; }},
  {key:"mcap_eur_m",  label:"Mkt cap",      group:"core", numeric:true, align:"num", filter:FNUM,
   title:"Market capitalisation, converted to EUR — min/max filter is in €M",
   render:function(r){ return fmtMoneyM(r.mcap_eur_m); }, sortval:function(r){ return r.mcap_eur_m; }},

  {key:"pe_ttm",  label:"P/E (ttm)", group:"valuation", numeric:true, align:"num", filter:FNUM, title:"Trailing price/earnings",
   render:function(r){ return fmtMult(r.pe_ttm); }, sortval:function(r){ return r.pe_ttm; }},
  {key:"ev_ebitda", label:"EV/EBITDA", group:"valuation", numeric:true, align:"num", filter:FNUM, title:"Enterprise value / EBITDA",
   render:function(r){ return fmtX(r.ev_ebitda); }, sortval:function(r){ return r.ev_ebitda; }},
  {key:"fcf_yield", label:"FCF yield", group:"valuation", numeric:true, align:"num", filter:FPCT, title:"Free cash flow / market cap — filter in %",
   render:function(r){ return fmtPct(r.fcf_yield); }, sortval:function(r){ return r.fcf_yield; }},
  {key:"div_yield", label:"Div yield", group:"valuation", numeric:true, align:"num", filter:FPCT, title:"Trailing dividend yield — filter in %",
   render:function(r){ return fmtPct(r.div_yield); }, sortval:function(r){ return r.div_yield; }},
  {key:"analyst_upside", label:"Analyst upside", group:"valuation", numeric:true, align:"num", filter:FPCT,
   title:"Mean analyst target price vs current price — filter in %",
   render:function(r){ return fmtPctSigned(r.analyst_upside); }, sortval:function(r){ return r.analyst_upside; }},

  {key:"roe", label:"ROE", group:"quality", numeric:true, align:"num", filter:FPCT, title:"Return on equity — filter in %",
   render:function(r){ return fmtPct(r.roe); }, sortval:function(r){ return r.roe; }},
  {key:"gm",  label:"Gross margin", group:"quality", numeric:true, align:"num", filter:FPCT, title:"Filter in %",
   render:function(r){ return fmtPct(r.gm); }, sortval:function(r){ return r.gm; }},
  {key:"om",  label:"Op margin", group:"quality", numeric:true, align:"num", filter:FPCT, title:"Filter in %",
   render:function(r){ return fmtPct(r.om); }, sortval:function(r){ return r.om; }},
  {key:"nm",  label:"Net margin", group:"quality", numeric:true, align:"num", filter:FPCT, title:"Filter in %",
   render:function(r){ return fmtPct(r.nm); }, sortval:function(r){ return r.nm; }},

  {key:"rev_growth", label:"Rev growth", group:"growth", numeric:true, align:"num", filter:FPCT, title:"YoY revenue growth — filter in %",
   render:function(r){ return fmtPctSigned(r.rev_growth); }, sortval:function(r){ return r.rev_growth; }},
  {key:"eps_growth", label:"EPS growth", group:"growth", numeric:true, align:"num", filter:FPCT, title:"YoY earnings growth — filter in %",
   render:function(r){ return fmtPctSigned(r.eps_growth); }, sortval:function(r){ return r.eps_growth; }},

  {key:"nd_ebitda", label:"Net debt/EBITDA", group:"balance", numeric:true, align:"num", filter:FNUM,
   title:"Negative = net cash position",
   render:function(r){ return fmtXSigned(r.nd_ebitda); }, sortval:function(r){ return r.nd_ebitda; }},
  {key:"debt_equity", label:"Debt/Equity", group:"balance", numeric:true, align:"num", filter:FNUM,
   render:function(r){ return fmtX(r.debt_equity); }, sortval:function(r){ return r.debt_equity; }},
  {key:"current_ratio", label:"Current ratio", group:"balance", numeric:true, align:"num", filter:FNUM,
   render:function(r){ return fmtX(r.current_ratio); }, sortval:function(r){ return r.current_ratio; }},
  {key:"net_cash_eur_m", label:"Net cash", group:"balance", numeric:true, align:"num", filter:FNUM,
   title:"Cash minus debt, EUR (negative = net debt)",
   render:function(r){ return fmtMoneyMSigned(r.net_cash_eur_m); }, sortval:function(r){ return r.net_cash_eur_m; }},

  {key:"ai_note", label:"AI rationale", group:"ai", numeric:false, align:"aicell", filter:FTEXT,
   title:"Why this industry scores the way it does — full text on hover / row detail",
   render:function(r){ return '<span title="'+esc(r.ai_note||"")+'">'+esc(truncate(r.ai_note,64))+'</span>'; },
   sortval:function(r){ return (r.ai_note||"").toLowerCase(); }},
  {key:"rev_emp_keur", label:"Revenue/employee", group:"ai", numeric:true, align:"num", filter:FNUM,
   title:"Lower often means more headcount-automation upside",
   render:function(r){ return fmtKEur(r.rev_emp_keur); }, sortval:function(r){ return r.rev_emp_keur; }},
  {key:"employees", label:"Employees", group:"ai", numeric:true, align:"num", filter:FNUM,
   render:function(r){ return fmtInt(r.employees); }, sortval:function(r){ return r.employees; }},

  {key:"country", label:"Country", group:"meta", numeric:false, align:"", filter:FTEXT,
   render:function(r){ return fmtText(r.country); }, sortval:function(r){ return (r.country||"").toLowerCase(); }},
  {key:"industry", label:"Industry (full)", group:"meta", numeric:false, align:"", filter:FTEXT,
   render:function(r){ return fmtText(r.industry); }, sortval:function(r){ return (r.industry||"").toLowerCase(); }},
  {key:"pe_fwd", label:"P/E (fwd)", group:"meta", numeric:true, align:"num", filter:FNUM,
   render:function(r){ return fmtMult(r.pe_fwd); }, sortval:function(r){ return r.pe_fwd; }},
  {key:"pb", label:"P/B", group:"meta", numeric:true, align:"num", filter:FNUM,
   render:function(r){ return fmtMult(r.pb); }, sortval:function(r){ return r.pb; }},
  {key:"ps", label:"P/S", group:"meta", numeric:true, align:"num", filter:FNUM,
   render:function(r){ return fmtMult(r.ps); }, sortval:function(r){ return r.ps; }},
  {key:"beta", label:"Beta", group:"meta", numeric:true, align:"num", filter:FNUM,
   render:function(r){ return fmtNum2(r.beta); }, sortval:function(r){ return r.beta; }},
  {key:"w52_change", label:"52w change", group:"meta", numeric:true, align:"num", filter:FPCT, title:"Filter in %",
   render:function(r){ return fmtPctSigned(r.w52_change); }, sortval:function(r){ return r.w52_change; }},
  {key:"coverage", label:"Data coverage", group:"meta", numeric:true, align:"num", filter:FPCT,
   title:"Share of scoring inputs available for this name — filter in %",
   render:function(r){ return fmtPct(r.coverage); }, sortval:function(r){ return r.coverage; }},
  {key:"adv_eur_k", label:"Avg $vol/day", group:"meta", numeric:true, align:"num", filter:FNUM,
   title:"3-month average daily traded value, EUR thousands",
   render:function(r){ return fmtKEur(r.adv_eur_k); }, sortval:function(r){ return r.adv_eur_k; }},
];

var GROUP_LABELS = {valuation:"Valuation", quality:"Quality", growth:"Growth", balance:"Balance sheet", ai:"AI detail", meta:"More"};
var CORE_COLS = COLUMNS.filter(function(c){ return c.group==="core"; });
var COLUMN_BY_KEY = {};
COLUMNS.forEach(function(c){ COLUMN_BY_KEY[c.key] = c; });

var state = {
  q:"", exch:"ALL", sectors:new Set(), showAll:false,
  colFilters:{}, /* key -> {min,max} for range columns, {text} for text columns */
  sortKey:"overall", sortDir:-1,
  groups:{valuation:true, quality:true, growth:true, balance:false, ai:false, meta:false},
  colorMode:"exch", expanded:new Set(), lastRows:[], scrollTo:null,
};

function prepData(){
  (DATA.rows||[]).forEach(function(r){
    r._sectorGroup = sectorGroup(r.sector);
    r._hay = (r.name+" "+r.symbol+" "+(r.industry||"")+" "+(r.sector||"")).toLowerCase();
  });
}

function visibleColumns(){
  return COLUMNS.filter(function(c){ return c.group==="core" || state.groups[c.group]; });
}

function populateFilterControls(){
  var sectors = Array.from(new Set((DATA.rows||[]).map(function(r){ return r.sector || "Unknown"; }))).sort();
  var sel = document.getElementById("sectorSel");
  sel.innerHTML = sectors.map(function(s){ return '<option value="'+esc(s)+'">'+esc(s)+'</option>'; }).join("");
  sel.size = Math.min(6, Math.max(3, sectors.length));

  var chipsWrap = document.getElementById("groupChips");
  chipsWrap.innerHTML = Object.keys(GROUP_LABELS).map(function(g){
    return '<button class="gchip'+(state.groups[g]?" active":"")+'" data-g="'+g+'">'+GROUP_LABELS[g]+"</button>";
  }).join("");
  chipsWrap.querySelectorAll(".gchip").forEach(function(btn){
    btn.addEventListener("click", function(){
      var g = btn.getAttribute("data-g");
      state.groups[g] = !state.groups[g];
      btn.classList.toggle("active", state.groups[g]);
      renderTableHead();
      renderAll();
    });
  });
}

function matchesFilters(r){
  if(!state.showAll && (r.dup_class || (r.coverage!=null && r.coverage<0.5))) return false;
  if(state.exch!=="ALL" && r.exch!==state.exch) return false;
  if(state.sectors.size){
    var s = r.sector || "Unknown";
    if(!state.sectors.has(s)) return false;
  }
  if(state.q && r._hay.indexOf(state.q)<0) return false;
  for(var key in state.colFilters){
    var f = state.colFilters[key], col = COLUMN_BY_KEY[key];
    if(!col) continue;
    if(col.filter.type==="text"){
      if(String(r[key]==null ? "" : r[key]).toLowerCase().indexOf(f.text)<0) return false;
    } else {
      var scale = col.filter.scale || 1, v = r[key];
      if(f.min!=null && !(v!=null && v>=f.min/scale)) return false;
      if(f.max!=null && !(v!=null && v<=f.max/scale)) return false;
    }
  }
  return true;
}

function cmpRows(a,b,col,dir){
  var av = col.sortval(a), bv = col.sortval(b);
  var an = (av==null || (typeof av==="number" && isNaN(av)));
  var bn = (bv==null || (typeof bv==="number" && isNaN(bv)));
  if(an && bn) return 0;
  if(an) return 1;
  if(bn) return -1;
  if(typeof av==="string") return av.localeCompare(bv)*dir;
  return (av-bv)*dir;
}

function computeFilteredSorted(){
  var col = COLUMNS.filter(function(c){ return c.key===state.sortKey; })[0] || COLUMNS[0];
  var rows = (DATA.rows||[]).filter(matchesFilters);
  rows.sort(function(a,b){ return cmpRows(a,b,col,state.sortDir); });
  return rows;
}

/* ---------- KPIs ---------- */
function renderKpis(rows){
  var n = rows.length;
  var hel = rows.filter(function(r){ return r.exch==="HEL"; }).length;
  var sto = rows.filter(function(r){ return r.exch==="STO"; }).length;
  var us = rows.filter(function(r){ return r.exch==="US"; }).length;
  var sweet = rows.filter(function(r){ return r.fund_score>=60 && r.ai_score>=70; }).length;
  var withScore = rows.filter(function(r){ return r.overall!=null; }).map(function(r){ return r.overall; }).sort(function(a,b){return a-b;});
  var med = withScore.length ? withScore[Math.floor(withScore.length/2)] : null;
  var cov = rows.length ? rows.reduce(function(s,r){ return s+(r.coverage||0); },0)/rows.length : 0;
  var errNote = (DATA.meta && DATA.meta.errors) ? '<small>'+DATA.meta.errors+' fetch errors</small>' : "";
  var tiles = [
    ["Shown", n.toLocaleString("en-US"), ""],
    ["Helsinki", hel.toLocaleString("en-US"), ""],
    ["Stockholm", sto.toLocaleString("en-US"), ""],
    ["USA", us.toLocaleString("en-US"), ""],
    ["Sweet spot", sweet.toLocaleString("en-US"), "<small>fund≥60 &amp; AI≥70</small>"],
    ["Median overall", med!=null ? med.toFixed(0) : "—", ""],
    ["Data coverage", (cov*100).toFixed(0)+"%", errNote],
  ];
  document.getElementById("kpis").innerHTML = tiles.map(function(t){
    return '<div class="kpi"><div class="l">'+t[0]+'</div><div class="v">'+t[1]+" "+t[2]+"</div></div>";
  }).join("");
}

/* ---------- Chart ---------- */
var CHART_W=920, CHART_H=520, PAD_L=48, PAD_R=18, PAD_T=18, PAD_B=42;
var PLOT_W = CHART_W-PAD_L-PAD_R, PLOT_H = CHART_H-PAD_T-PAD_B;

function plotX(v){ return PAD_L + (Math.max(0,Math.min(100,v))/100)*PLOT_W; }
function plotY(v){ return PAD_T + (1-Math.max(0,Math.min(100,v))/100)*PLOT_H; }
function radiusFor(mcap){
  var cap = Math.min(Math.max(mcap||1,1), 250000);
  return 4 + 13*Math.sqrt(cap/250000);
}

var LEGENDS = {
  exch:   [{k:"HEL",label:"Helsinki (HEL)",color:"var(--cat-1)"},
           {k:"STO",label:"Stockholm (STO)",color:"var(--cat-2)"},
           {k:"US",label:"USA (S&amp;P 500)",color:"var(--cat-3)"}],
  sector: [{k:"tc",label:"Tech &amp; Communications",color:"var(--cat-1)"},
           {k:"fr",label:"Financials &amp; Real Estate",color:"var(--cat-2)"},
           {k:"ime",label:"Industrials, Materials &amp; Energy",color:"var(--cat-3)"},
           {k:"hc",label:"Healthcare &amp; Consumer",color:"var(--cat-4)"},
           {k:"other",label:"Other / unclassified",color:"var(--faint)"}],
};

function colorForRow(r){
  if(state.colorMode==="sector"){
    var m = {tc:"var(--cat-1)", fr:"var(--cat-2)", ime:"var(--cat-3)", hc:"var(--cat-4)", other:"var(--faint)"};
    return m[r._sectorGroup] || "var(--faint)";
  }
  var em = {HEL:"var(--cat-1)", STO:"var(--cat-2)", US:"var(--cat-3)"};
  return em[r.exch] || "var(--faint)";
}

function initChartChrome(){
  var svg = document.getElementById("scatter");
  var ticks = [0,25,50,75,100];
  var gl = ticks.map(function(t){
    var x=plotX(t), y=plotY(t);
    return '<line class="gridline'+(t===50?" mid":"")+'" x1="'+x+'" y1="'+PAD_T+'" x2="'+x+'" y2="'+(PAD_T+PLOT_H)+'"></line>'+
           '<line class="gridline'+(t===50?" mid":"")+'" x1="'+PAD_L+'" y1="'+y+'" x2="'+(PAD_L+PLOT_W)+'" y2="'+y+'"></line>'+
           '<text class="tick" x="'+x+'" y="'+(PAD_T+PLOT_H+14)+'" text-anchor="middle">'+t+'</text>'+
           '<text class="tick" x="'+(PAD_L-8)+'" y="'+(y+3)+'" text-anchor="end">'+t+'</text>';
  }).join("");
  var axisLabels =
    '<text class="axislabel" x="'+(PAD_L+PLOT_W/2)+'" y="'+(CHART_H-6)+'" text-anchor="middle">Fundamentals score →</text>'+
    '<text class="axislabel" x="'+(-(PAD_T+PLOT_H/2))+'" y="14" text-anchor="middle" transform="rotate(-90)">AI-leverage score →</text>';
  var quadW = PLOT_W/2, quadH = PLOT_H/2;
  var quads =
    '<text class="quadlabel" x="'+(PAD_L+quadW+quadW-8)+'" y="'+(PAD_T+14)+'" text-anchor="end">Prime candidates</text>'+
    '<text class="quadlabel" x="'+(PAD_L+8)+'" y="'+(PAD_T+14)+'" text-anchor="start">AI-ready, fundamentals lag</text>'+
    '<text class="quadlabel" x="'+(PAD_L+quadW+quadW-8)+'" y="'+(PAD_T+PLOT_H-8)+'" text-anchor="end">Solid business, low AI leverage</text>'+
    '<text class="quadlabel" x="'+(PAD_L+8)+'" y="'+(PAD_T+PLOT_H-8)+'" text-anchor="start">Screen out</text>';
  svg.innerHTML = '<g class="axes">'+gl+axisLabels+quads+'</g><g class="dots" id="dotsG"></g>';

  var tt = document.getElementById("tooltip");
  svg.addEventListener("pointermove", function(e){
    var g = e.target.closest(".dot");
    if(!g){ tt.style.display="none"; return; }
    var sym = g.getAttribute("data-sym");
    var r = (DATA.rows||[]).filter(function(x){ return x.symbol===sym; })[0];
    if(!r) return;
    tt.innerHTML =
      '<div class="tt-name">'+esc(r.name)+' <span style="color:var(--faint);font-weight:400">('+esc(r.symbol)+')</span></div>'+
      '<div class="tt-row"><span>'+esc(r.sector||"Unknown sector")+'</span></div>'+
      '<div class="tt-row"><span>Mkt cap</span><b>'+fmtMoneyM(r.mcap_eur_m)+'</b></div>'+
      '<div class="tt-row"><span>Fundamentals</span><b>'+(r.fund_score!=null?r.fund_score.toFixed(0):"—")+'</b></div>'+
      '<div class="tt-row"><span>AI leverage</span><b>'+(r.ai_score!=null?r.ai_score.toFixed(0):"—")+'</b></div>'+
      '<div class="tt-row"><span>Overall</span><b>'+(r.overall!=null?r.overall.toFixed(0):"—")+'</b></div>';
    tt.style.display="block";
    var pad=16;
    tt.style.left = Math.min(e.clientX+pad, window.innerWidth-270)+"px";
    tt.style.top = Math.min(e.clientY+pad, window.innerHeight-140)+"px";
  });
  svg.addEventListener("pointerleave", function(){ tt.style.display="none"; });
  svg.addEventListener("click", function(e){
    var g = e.target.closest(".dot");
    if(!g) return;
    var sym = g.getAttribute("data-sym");
    state.expanded.add(sym);
    state.scrollTo = sym;
    renderAll();
  });
}

function renderChart(rows){
  var plotted = rows.filter(function(r){ return r.fund_score!=null && r.ai_score!=null; });
  document.getElementById("chartSub").textContent = " — "+plotted.length+" of "+rows.length+" shown names plotted (need both scores)";
  var html = plotted.map(function(r){
    var x=plotX(r.fund_score), y=plotY(r.ai_score), rad=radiusFor(r.mcap_eur_m), color=colorForRow(r);
    return '<g class="dot" data-sym="'+esc(r.symbol)+'">'+
           '<circle class="hit" r="'+Math.max(12,rad+6)+'" cx="'+x+'" cy="'+y+'" fill="transparent"></circle>'+
           '<circle class="mark" r="'+rad+'" cx="'+x+'" cy="'+y+'" fill="'+color+'" fill-opacity="0.8" stroke="var(--surface)" stroke-width="1.5"></circle>'+
           "</g>";
  }).join("");
  document.getElementById("dotsG").innerHTML = html;

  var legend = LEGENDS[state.colorMode];
  document.getElementById("legend").innerHTML = legend.map(function(l){
    return '<span class="li"><span class="sw" style="background:'+l.color+'"></span>'+l.label+"</span>";
  }).join("");
}

/* ---------- Table ---------- */
function sortHeaderHtml(c){
  var arrow = c.key===state.sortKey ? (state.sortDir===1?"↑":"↓") : "↕";
  var sorted = c.key===state.sortKey ? " sorted" : "";
  var title = c.title ? ' title="'+esc(c.title)+'"' : "";
  return '<th data-key="'+c.key+'" class="'+sorted+'"'+title+'>'+esc(c.label)+' <span class="arrow">'+arrow+'</span></th>';
}

function filterCellHtml(c){
  var cur = state.colFilters[c.key];
  var active = cur ? " active" : "";
  if(c.filter.type==="none") return '<td class="ffcell"></td>';
  if(c.filter.type==="text"){
    var t = cur ? esc(cur.text) : "";
    return '<td class="ffcell'+active+'"><input type="text" class="ff-text" data-key="'+c.key+'" placeholder="contains…" value="'+t+'"></td>';
  }
  var mn = (cur && cur.min!=null) ? cur.min : "";
  var mx = (cur && cur.max!=null) ? cur.max : "";
  return '<td class="ffcell'+active+'"><div class="ffrange">'+
    '<input type="number" step="any" class="ff-min" data-key="'+c.key+'" placeholder="min" value="'+mn+'">'+
    '<input type="number" step="any" class="ff-max" data-key="'+c.key+'" placeholder="max" value="'+mx+'">'+
    '</div></td>';
}

function renderTableHead(){
  var cols = visibleColumns();
  document.getElementById("theadRow").innerHTML = cols.map(sortHeaderHtml).join("");
  document.getElementById("filterHeadRow").innerHTML = cols.map(filterCellHtml).join("");
  updateClearFiltersButton();
}

function updateSortIndicators(){
  document.querySelectorAll("#theadRow th[data-key]").forEach(function(th){
    var k = th.getAttribute("data-key");
    var isSorted = k===state.sortKey;
    th.classList.toggle("sorted", isSorted);
    th.querySelector(".arrow").textContent = isSorted ? (state.sortDir===1?"↑":"↓") : "↕";
  });
}

function updateClearFiltersButton(){
  var n = Object.keys(state.colFilters).length;
  var btn = document.getElementById("btnClearColFilters");
  btn.classList.toggle("hidden", n===0);
  btn.textContent = "Clear column filters ("+n+")";
}

var _colFilterTimers = {};
function initColumnFilters(){
  document.getElementById("filterHeadRow").addEventListener("input", function(e){
    var el = e.target;
    if(!el.matches(".ff-min,.ff-max,.ff-text")) return;
    var key = el.getAttribute("data-key");
    var timerKey = key+":"+(el.classList.contains("ff-text")?"text":(el.classList.contains("ff-min")?"min":"max"));
    clearTimeout(_colFilterTimers[timerKey]);
    _colFilterTimers[timerKey] = setTimeout(function(){
      if(el.classList.contains("ff-text")){
        var t = el.value.trim().toLowerCase();
        if(t) state.colFilters[key] = {text:t}; else delete state.colFilters[key];
      } else {
        var cur = state.colFilters[key] || {};
        var num = el.value==="" ? null : parseFloat(el.value);
        if(el.classList.contains("ff-min")) cur.min = (num==null||isNaN(num)) ? null : num;
        else cur.max = (num==null||isNaN(num)) ? null : num;
        if(cur.min==null && cur.max==null) delete state.colFilters[key];
        else state.colFilters[key] = cur;
      }
      el.closest(".ffcell").classList.toggle("active", !!state.colFilters[key]);
      updateClearFiltersButton();
      renderAll();
    }, 220);
  });
  document.getElementById("btnClearColFilters").addEventListener("click", function(){
    state.colFilters = {};
    renderTableHead();
    renderAll();
  });
}

function rowDetailHtml(r, colspan){
  var rev = r.rev_eur_m!=null ? fmtMoneyM(r.rev_eur_m) : "—";
  var web = r.website ? ' · <a href="'+esc(ensureUrl(r.website))+'" target="_blank" rel="noopener">Website ↗</a>' : "";
  return '<tr class="detailrow'+(state.expanded.has(r.symbol)?"":" hidden")+'" data-detail-for="'+esc(r.symbol)+'">'+
    '<td colspan="'+colspan+'"><div class="detail">'+
    '<p class="desc">'+esc(r.desc||"No business summary available from Yahoo Finance for this name.")+'</p>'+
    '<div class="pillars">'+
      '<div class="pillarrow"><span>Quality</span>'+scoreBar(r.pillar_quality)+'</div>'+
      '<div class="pillarrow"><span>Growth</span>'+scoreBar(r.pillar_growth)+'</div>'+
      '<div class="pillarrow"><span>Balance sheet</span>'+scoreBar(r.pillar_balance)+'</div>'+
      '<div class="pillarrow"><span>Valuation</span>'+scoreBar(r.pillar_valuation)+'</div>'+
    '</div>'+
    '<p class="airationale"><b>AI-fit rationale:</b> '+esc(r.ai_note||"—")+' — industry base '+esc(r.ai_base)+
      ', +'+esc(r.ai_labor_pts)+' labor-intensity, +'+esc(r.ai_margin_pts)+' margin leverage → '+esc(r.ai_score)+'/100.</p>'+
    '<p class="meta2">Employees: '+fmtInt(r.employees)+' · Revenue: '+rev+' · Country: '+esc(r.country||"—")+
      web+' · <a href="'+yahooUrl(r.symbol)+'" target="_blank" rel="noopener">Yahoo Finance ↗</a></p>'+
    '</div></td></tr>';
}

function renderTable(rows){
  var cols = visibleColumns();
  var colspan = cols.length;
  if(!rows.length){
    document.getElementById("tbody").innerHTML =
      '<tr><td colspan="'+colspan+'"><div class="empty">No names match the current filters — try Reset filters, '+
      'or check "show duplicate classes &amp; thin-data names".</div></td></tr>';
    return;
  }
  var parts = [];
  rows.forEach(function(r){
    var tds = cols.map(function(c){
      if(c.special==="name"){
        var caret = state.expanded.has(r.symbol) ? "▾" : "▸";
        return '<td class="namecell"><button class="caret" data-sym="'+esc(r.symbol)+'">'+caret+'</button>'+
          '<div class="namewrap"><div class="nametop"><a class="rlink" href="'+yahooUrl(r.symbol)+
          '" target="_blank" rel="noopener">'+esc(r.name)+'</a>'+tierChip(r.overall)+'</div>'+
          '<div class="tkr">'+esc(r.symbol)+" · "+esc(r.exch_name||r.exch)+(r.dup_class?" · dup class":"")+'</div>'+
          '<div class="secline">'+esc(r.sector||"Unknown sector")+(r.industry?" › "+esc(r.industry):"")+'</div>'+
          '</div></td>';
      }
      var cls = c.align==="num" ? ' class="num"' : (c.align ? ' class="'+c.align+'"' : "");
      return "<td"+cls+">"+c.render(r)+"</td>";
    }).join("");
    parts.push('<tr data-sym="'+esc(r.symbol)+'">'+tds+"</tr>");
    parts.push(rowDetailHtml(r, colspan));
  });
  document.getElementById("tbody").innerHTML = parts.join("");
}

/* ---------- Orchestration ---------- */
function renderAll(){
  var rows = computeFilteredSorted();
  state.lastRows = rows;
  renderKpis(rows);
  renderChart(rows);
  renderTable(rows);
  var total = (DATA.rows||[]).length;
  document.getElementById("rowCount").textContent =
    "Showing "+rows.length.toLocaleString("en-US")+" of "+total.toLocaleString("en-US")+" listings";

  if(state.scrollTo){
    var sym = state.scrollTo; state.scrollTo = null;
    requestAnimationFrame(function(){
      var el = document.querySelector('tr[data-sym="'+CSS.escape(sym)+'"]');
      if(el){
        el.scrollIntoView({behavior:"smooth", block:"center"});
        el.classList.add("flash");
        setTimeout(function(){ el.classList.remove("flash"); }, 1700);
      }
    });
  }
}

function bindStaticEvents(){
  document.getElementById("q").addEventListener("input", debounce(function(e){
    state.q = e.target.value.trim().toLowerCase(); renderAll();
  }, 150));

  document.getElementById("exchSeg").addEventListener("click", function(e){
    var b = e.target.closest("button"); if(!b) return;
    state.exch = b.getAttribute("data-v");
    this.querySelectorAll("button").forEach(function(x){ x.classList.toggle("active", x===b); });
    renderAll();
  });

  document.getElementById("sectorSel").addEventListener("change", function(e){
    state.sectors = new Set(Array.from(e.target.selectedOptions).map(function(o){ return o.value; }));
    renderAll();
  });

  document.getElementById("chkAll").addEventListener("change", function(e){ state.showAll = e.target.checked; renderAll(); });

  document.getElementById("btnReset").addEventListener("click", function(){
    state.q=""; state.exch="ALL"; state.sectors=new Set(); state.showAll=false; state.colFilters={};
    document.getElementById("q").value="";
    document.getElementById("exchSeg").querySelectorAll("button").forEach(function(x){ x.classList.toggle("active", x.getAttribute("data-v")==="ALL"); });
    document.getElementById("sectorSel").querySelectorAll("option").forEach(function(o){ o.selected=false; });
    document.getElementById("chkAll").checked=false;
    renderTableHead();
    renderAll();
  });

  document.getElementById("colorSeg").addEventListener("click", function(e){
    var b = e.target.closest("button"); if(!b) return;
    state.colorMode = b.getAttribute("data-v");
    this.querySelectorAll("button").forEach(function(x){ x.classList.toggle("active", x===b); });
    renderChart(state.lastRows);
  });

  document.getElementById("stab").addEventListener("click", function(e){
    var th = e.target.closest("th[data-key]");
    if(th){
      var k = th.getAttribute("data-key");
      if(state.sortKey===k) state.sortDir *= -1;
      else { state.sortKey = k; var col = COLUMN_BY_KEY[k];
             state.sortDir = (col && !col.numeric) ? 1 : -1; }
      updateSortIndicators(); renderAll();
      return;
    }
    var caret = e.target.closest(".caret");
    if(caret){
      var sym = caret.getAttribute("data-sym");
      if(state.expanded.has(sym)) state.expanded.delete(sym); else state.expanded.add(sym);
      renderAll();
    }
  });

  document.getElementById("btnExport").addEventListener("click", exportCsv);
}

function csvEscape(v){
  var s = v==null ? "" : String(v);
  return /[",\n]/.test(s) ? '"'+s.replace(/"/g,'""')+'"' : s;
}
function exportCsv(){
  var cols = visibleColumns().filter(function(c){ return c.key!=="name"; });
  var header = ["symbol","name","exch","sector","industry"].concat(cols.map(function(c){ return c.label; }));
  var lines = [header.map(csvEscape).join(",")];
  state.lastRows.forEach(function(r){
    var row = [r.symbol, r.name, r.exch, r.sector||"", r.industry||""].concat(cols.map(function(c){ return r[c.key]; }));
    lines.push(row.map(csvEscape).join(","));
  });
  var blob = new Blob([lines.join("\n")], {type:"text/csv"});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "universe-screener-shortlist-"+new Date().toISOString().slice(0,10)+".csv";
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(a.href);
}

/* ---------- Refresh / status / reload ---------- */
var isServed = location.protocol.indexOf("http")===0;
var pollTimer = null;

function setStatusText(t){ document.getElementById("rbStatusText").textContent = t; }
function setDot(cls){
  var d = document.getElementById("rbDot");
  d.className = "rb-dot"+(cls?" "+cls:"");
}
function setNote(msg, isErr){
  var n = document.getElementById("rbNote");
  n.textContent = msg;
  n.className = "rb-note show"+(isErr?" err":"");
}
function clearNote(){ document.getElementById("rbNote").className = "rb-note"; }
function showProgress(){ document.getElementById("rbProgress").className = "rb-progress show"; }
function hideProgress(){ document.getElementById("rbProgress").className = "rb-progress"; }

function initialStatusText(){
  var meta = DATA.meta || {};
  var n = (DATA.rows||[]).length;
  if(!n){ setStatusText("No data yet — run the fetch script, then reload this page."); return; }
  setStatusText("Loaded "+n.toLocaleString("en-US")+" names · as of "+(meta.generated||"—")+
    " · coverage "+(meta.n_full!=null?meta.n_full:"—")+"/"+(meta.n!=null?meta.n:n)+
    (meta.errors ? " · "+meta.errors+" fetch errors" : ""));
}

function updateProgressUI(st){
  var total = st.total||0, done = st.done||0;
  var pct = total ? Math.round(100*done/total) : (st.phase==="universe" ? 8 : 0);
  document.getElementById("rbBarFill").style.width = pct+"%";
  var txt;
  if(st.phase==="universe") txt = "Enumerating exchange listings…";
  else if(st.phase==="fundamentals") txt = "Fetching fundamentals "+done+"/"+total+(st.errors?" ("+st.errors+" errors)":"")+"…";
  else if(st.phase==="compute") txt = "Scoring & ranking…";
  else if(st.phase==="done") txt = "Done.";
  else if(st.phase==="failed") txt = "Failed: "+(st.error||"unknown error");
  else txt = st.phase || "Working…";
  document.getElementById("rbProgressText").textContent = txt;
}

function pollStatus(){
  clearInterval(pollTimer);
  pollTimer = setInterval(function(){
    fetch("/api/status", {cache:"no-store"}).then(function(r){ return r.json(); }).then(function(st){
      updateProgressUI(st);
      setDot(st.running ? "busy" : (st.ok===false ? "err" : ""));
      if(!st.running){
        clearInterval(pollTimer); pollTimer=null;
        document.getElementById("btnRefresh").disabled = false;
        hideProgress();
        if(st.stalled) setNote("The refresh process seems to have stopped unexpectedly. Check data/screener_refresh.log, then try again.", true);
        else if(st.ok===false) setNote("Refresh failed: "+(st.error||"unknown error")+". Check data/screener_refresh.log.", true);
        else { clearNote(); reloadFromDisk(true); }
      }
    }).catch(function(e){
      clearInterval(pollTimer); pollTimer=null;
      document.getElementById("btnRefresh").disabled = false;
      hideProgress();
      setDot("err");
      setNote("Lost contact with the refresh API ("+e.message+").", true);
    });
  }, 1200);
}

function startRefresh(){
  var btn = document.getElementById("btnRefresh");
  btn.disabled = true;
  clearNote(); showProgress(); setDot("busy");
  updateProgressUI({phase:"starting"});
  var clear = document.getElementById("chkClear").checked;
  fetch("/api/refresh"+(clear?"?clear=1":""), {method:"POST"}).then(function(res){
    if(res.status===409){ setNote("A refresh is already running — polling for progress…"); return pollStatus(); }
    if(!res.ok) throw new Error("HTTP "+res.status);
    pollStatus();
  }).catch(function(e){
    btn.disabled = false; hideProgress(); setDot("err");
    setNote("Could not reach the local refresh API ("+e.message+"). Start this page via: python utils/screener_server.py", true);
  });
}

function reloadFromDisk(afterRefresh){
  return fetch("screener_data.json?_="+Date.now(), {cache:"no-store"}).then(function(r){
    if(!r.ok) throw new Error("HTTP "+r.status);
    return r.json();
  }).then(function(j){
    DATA.meta = j.meta; DATA.rows = j.rows;
    prepData();
    populateFilterControls();
    renderTableHead();
    renderAll();
    initialStatusText();
    setDot("");
    if(afterRefresh) setNote("Refreshed just now.", false);
    setTimeout(clearNote, 4000);
  }).catch(function(e){
    setDot("err");
    setNote("Could not reload data from disk ("+e.message+"). "+
      (isServed ? "Try again in a moment." :
       "Open this page via python utils/screener_server.py to enable one-click reload, or re-run python utils/universe_screener.py and refresh the browser page."), true);
  });
}

function initRefreshControls(){
  document.getElementById("btnReload").addEventListener("click", function(){ reloadFromDisk(false); });
  document.getElementById("btnRefresh").addEventListener("click", startRefresh);
  if(!isServed){
    var btn = document.getElementById("btnRefresh");
    btn.disabled = true;
    btn.title = "Needs the local server: python utils/screener_server.py";
  }
}

/* ---------- Init ---------- */
prepData();
populateFilterControls();
renderTableHead();
initColumnFilters();
initChartChrome();
initialStatusText();
initRefreshControls();
bindStaticEvents();
renderAll();

if(isServed){
  fetch("/api/status", {cache:"no-store"}).then(function(r){return r.json();}).then(function(st){
    if(st && st.running){ setDot("busy"); showProgress(); updateProgressUI(st); document.getElementById("btnRefresh").disabled=true; pollStatus(); }
  }).catch(function(){});
}
