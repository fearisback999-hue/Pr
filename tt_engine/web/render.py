"""HTML rendering for the local dashboard. Stdlib only, zero external assets —
everything inlines so the page works on an offline desk server."""

from __future__ import annotations

import html
import re

esc = html.escape

_CSS = """
:root {
  --bg:oklch(0.165 0.006 72); --panel:oklch(0.207 0.008 72);
  --elev:oklch(0.247 0.009 72); --line:oklch(0.315 0.008 72);
  --line-soft:oklch(0.27 0.007 72);
  /* --mut / --faint bumped for WCAG AA (≥4.5:1 on --panel): secondary text and
     table headers were failing contrast at the old lightness. */
  --ink:oklch(0.945 0.006 82); --mut:oklch(0.74 0.01 82); --faint:oklch(0.655 0.01 82);
  --acc:oklch(0.76 0.128 279); --acc-soft:oklch(0.76 0.128 279 / 0.15);
  --acc-line:oklch(0.76 0.128 279 / 0.30); --acc-ink:oklch(0.20 0.03 279);
  --good:oklch(0.76 0.15 156); --warn:oklch(0.81 0.13 82); --bad:oklch(0.665 0.17 26);
  --shadow:0 1px 2px oklch(0 0 0 / 0.35), 0 8px 24px -16px oklch(0 0 0 / 0.5);
}
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:14.5px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
       font-variant-numeric:tabular-nums; }
::selection { background:var(--acc-soft); }
a { color:var(--acc); text-decoration:none; transition:color .15s ease; }
a:hover { text-decoration:underline; text-underline-offset:2px; }

nav { display:flex; gap:3px; align-items:center; padding:11px 22px; background:var(--panel);
      border-bottom:1px solid var(--line-soft); position:sticky; top:0; z-index:20;
      flex-wrap:wrap; box-shadow:0 1px 0 oklch(0 0 0 / 0.25); }
nav .brand { font-weight:700; letter-spacing:-0.01em; margin-right:16px; font-size:15px;
             color:var(--ink); }
nav a { padding:6px 12px; border-radius:8px; color:var(--mut); font-size:13.5px;
        font-weight:500; transition:background-color .15s ease, color .15s ease; }
nav a:hover { background:var(--elev); color:var(--ink); text-decoration:none; }
/* Active page: brighter text + a solid underline bar, not just a faint fill —
   the old subtle tint was easy to miss among 16 links. */
nav a.on { background:var(--acc-soft); color:var(--acc); font-weight:700; }
nav a.on::after { content:""; position:absolute; left:10px; right:10px; bottom:-11px;
                  height:2px; background:var(--acc); border-radius:2px 2px 0 0; }
nav a { position:relative; }
nav a:focus-visible { outline:2px solid var(--acc); outline-offset:-2px; }
/* Grouping by visual containment, not text labels — a subtle inset pill around each
   cluster reads as a group without the width a label row would cost (which forced the
   nav to wrap to two rows). The group's name is exposed to assistive tech via title. */
.navgroup { display:flex; gap:1px; align-items:center; padding:2px; border-radius:10px;
            background:oklch(0.24 0.008 72 / 0.5); }
.navsep { display:none; }
nav a { padding:6px 11px; }
@media (max-width:820px) { .navgroup { background:none; padding:0; }
                           nav { gap:2px; padding:9px 14px; } }

main { max-width:1120px; margin:0 auto; padding:26px 22px 96px; }
main p, main li { max-width:76ch; }
h1 { font-size:27px; line-height:1.15; letter-spacing:-0.022em; font-weight:700;
     margin:20px 0 12px; }
h2 { font-size:18px; letter-spacing:-0.012em; font-weight:650; margin:30px 0 10px; }
h3 { font-size:11.5px; text-transform:uppercase; letter-spacing:0.09em; font-weight:700;
     color:var(--faint); margin:18px 0 6px; }

.panel { background:var(--panel); border:1px solid var(--line-soft); border-radius:14px;
         padding:18px 20px; margin:14px 0; overflow-x:auto; box-shadow:var(--shadow); }
.panel > h2:first-child, .panel > h3:first-child { margin-top:0; }

table { border-collapse:collapse; width:100%; font-size:13.5px; }
th, td { text-align:left; padding:9px 12px; border-bottom:1px solid var(--line-soft);
         vertical-align:top; }
th { color:var(--faint); font-weight:600; font-size:11px; text-transform:uppercase;
     letter-spacing:0.06em; white-space:nowrap; }
th.num { text-align:right; }
tbody tr { transition:background-color .12s ease; }
tbody tr:hover { background:var(--elev); }
tr:last-child td { border-bottom:none; }
.num { text-align:right; font-variant-numeric:tabular-nums; }

.chip { display:inline-block; padding:2.5px 11px; border-radius:999px; font-size:11.5px;
        font-weight:650; letter-spacing:0.01em; line-height:1.5; white-space:nowrap; }
.chip.TEST { background:oklch(0.76 0.15 156 / 0.16); color:var(--good);
             box-shadow:inset 0 0 0 1px oklch(0.76 0.15 156 / 0.22); }
.chip.WATCH { background:oklch(0.81 0.13 82 / 0.15); color:var(--warn);
              box-shadow:inset 0 0 0 1px oklch(0.81 0.13 82 / 0.22); }
.chip.KILL { background:oklch(0.665 0.17 26 / 0.16); color:var(--bad);
             box-shadow:inset 0 0 0 1px oklch(0.665 0.17 26 / 0.24); }
.chip.info { background:var(--elev); color:var(--mut);
             box-shadow:inset 0 0 0 1px var(--line); }

.kpis { display:flex; gap:12px; flex-wrap:wrap; margin:16px 0; }
.kpi { background:var(--panel); border:1px solid var(--line-soft); border-radius:12px;
       padding:14px 18px; min-width:154px; flex:1 1 154px; box-shadow:var(--shadow); }
.kpi b { display:block; font-size:25px; font-weight:680; letter-spacing:-0.02em;
         line-height:1.1; }
.kpi span { color:var(--faint); font-size:11px; text-transform:uppercase;
            letter-spacing:0.06em; margin-top:5px; display:block; }

code, pre { background:oklch(0.14 0.006 72); border:1px solid var(--line-soft);
            border-radius:7px; font:13px/1.55 ui-monospace,"SF Mono",Menlo,Consolas,monospace; }
code { padding:1.5px 6px; color:oklch(0.86 0.03 279); }
/* Wrap long prose lines (the month-one bullet notes overflowed their panel and
   clipped behind a scrollbar). Short aligned number columns stay on one line at
   panel width; only genuinely long lines wrap. */
pre { padding:13px 15px; overflow-x:auto; white-space:pre-wrap; overflow-wrap:anywhere; }
pre code { background:none; border:none; padding:0; color:inherit; }

blockquote { margin:12px 0; padding:13px 16px; color:var(--mut); background:var(--acc-soft);
             border:1px solid var(--acc-line); border-radius:12px; }
blockquote b { color:var(--ink); }

form.calc { display:flex; gap:12px; flex-wrap:wrap; align-items:flex-end; }
form.calc label { display:flex; flex-direction:column; font-size:11px; color:var(--faint);
                  text-transform:uppercase; letter-spacing:0.05em; font-weight:600; }
form.calc input { margin-top:6px; padding:8px 11px; width:140px; background:var(--elev);
                  border:1px solid var(--line); border-radius:9px; color:var(--ink);
                  font-size:14px; transition:border-color .15s ease, box-shadow .15s ease; }
form.calc input:focus, form.calc select:focus { outline:none; border-color:var(--acc);
                        box-shadow:0 0 0 3px var(--acc-soft); }
/* Selects and file inputs default to their own intrinsic heights, which breaks the
   row baseline next to text inputs. Match them explicitly. */
form.calc select { margin-top:6px; padding:8px 11px; width:160px; height:37px;
                   max-width:100%; background:var(--elev); border:1px solid var(--line);
                   border-radius:9px; color:var(--ink); font-size:14px; }
/* Wider fields for forms whose values are phrases, not numbers (e.g. Restyle). */
form.calc.wide select { width:230px; }
form.calc.wide input { width:230px; }
form.calc.wide input::placeholder { color:var(--faint); }
form.calc input[type=file] { width:210px; padding:7px 10px; font-size:12.5px;
                             color:var(--mut); }
form.calc input[type=file]::file-selector-button {
    background:var(--elev); color:var(--ink); border:1px solid var(--line);
    border-radius:7px; padding:4px 10px; margin-right:9px; cursor:pointer;
    font-size:12.5px; font-weight:600; }
form.calc input[type=file]::file-selector-button:hover { border-color:var(--acc); }
form.calc label.check { flex-direction:row; align-items:center; gap:8px;
                        text-transform:none; letter-spacing:0; font-size:13.5px;
                        color:var(--ink); font-weight:500; height:37px; }
form.calc label.check input { width:auto; margin:0; accent-color:var(--acc); }
form.calc button { padding:9px 20px; border-radius:9px; border:none; background:var(--acc);
                   color:var(--acc-ink); font-weight:650; font-size:14px; cursor:pointer;
                   transition:transform .16s cubic-bezier(.22,1,.36,1), filter .16s ease; }
form.calc button:hover { filter:brightness(1.07); transform:translateY(-1px); }
form.calc button:active { transform:translateY(0); }
form.calc button:focus-visible { outline:2px solid var(--acc); outline-offset:2px; }

.step { padding:11px 0; border-bottom:1px solid var(--line-soft); }
.step:last-child { border-bottom:none; }
.step .cmd { margin-top:4px; }
.mut { color:var(--mut); } .good { color:var(--good); } .warn { color:var(--warn); }
.bad { color:var(--bad); }
ul { margin:8px 0; padding-left:22px; } li { margin:3px 0; }
hr { border:none; border-top:1px solid var(--line-soft); margin:18px 0; }

.bar { height:7px; border-radius:99px; background:var(--elev); overflow:hidden;
       margin:7px 0 2px; box-shadow:inset 0 0 0 1px var(--line-soft); }
.bar > i { display:block; height:100%; background:var(--good); border-radius:99px;
           transition:width .5s cubic-bezier(.22,1,.36,1); }

.pbstep { display:flex; gap:11px; padding:11px 0; border-bottom:1px solid var(--line-soft);
          align-items:flex-start; }
.pbstep:last-child { border-bottom:none; }
.pbstep.done { opacity:.5; }
.pbstep .box { flex:0 0 auto; }
.pbstep .box a { display:block; width:19px; height:19px; border-radius:6px;
                  border:1px solid var(--line); text-align:center; line-height:17px;
                  font-size:13px; color:var(--good); text-decoration:none;
                  transition:border-color .15s ease, background-color .15s ease; }
.pbstep .box a:hover { border-color:var(--good); background:oklch(0.76 0.15 156 / 0.12); }
.pbstep .body b { display:inline-block; }
.pbstep .src { font-size:11px; color:var(--faint); margin-left:6px; }
.pbstep .cmd { margin-top:4px; }
.phasehead { display:flex; justify-content:space-between; align-items:baseline;
             margin:26px 0 4px; }

/* ── odds bars (shots on goal) ─────────────────────────────────────────────── */
.oddsrow { display:grid; grid-template-columns:5.5rem 1fr 3rem; gap:12px;
           align-items:center; padding:5px 0; }
.oddsn { font-size:12.5px; color:var(--mut); white-space:nowrap; }
.oddsp { font-size:13px; font-weight:650; text-align:right;
         font-variant-numeric:tabular-nums; }
.oddsrow .bar { margin:0; }
.bar > i.good { background:var(--good); }
.bar > i.warn { background:var(--warn); }
.bar > i.bad  { background:var(--bad); }

/* ── auditor findings ──────────────────────────────────────────────────────── */
.finding { padding:14px 0; border-bottom:1px solid var(--line-soft); }
.finding:first-child { padding-top:2px; }
.finding:last-child { border-bottom:none; padding-bottom:2px; }
.finding p { margin:0 0 5px; }
.finding p:last-child { margin-bottom:0; }
.finding .cost { color:var(--warn); font-size:13px; }
.finding .fix { font-size:13px; }
.finding .cost b, .finding .fix b { font-size:10.5px; text-transform:uppercase;
                                    letter-spacing:0.07em; color:var(--faint);
                                    margin-right:5px; font-weight:700; }
/* The judgment is prose, not output — the `code, pre` shorthand would otherwise
   set it in mono, which reads as a machine dump rather than a considered opinion. */
pre.judgment { background:none; border:none; padding:0; white-space:pre-wrap;
               font-family:inherit; font-size:14.5px; line-height:1.62;
               color:var(--ink); max-width:74ch; margin:0; }

/* Section label above a panel's content. */
.label { font-size:11px; text-transform:uppercase; letter-spacing:0.075em;
         font-weight:700; color:var(--faint); margin:0 0 11px; }

/* ── how-to instructions, disclosed on demand ─────────────────────────────── */
details.how { margin-top:8px; }
details.how > summary { cursor:pointer; display:inline-flex; align-items:center;
                        gap:6px; font-size:11.5px; font-weight:650; color:var(--acc);
                        text-transform:uppercase; letter-spacing:0.06em;
                        list-style:none; padding:3px 0; }
details.how > summary::-webkit-details-marker { display:none; }
details.how > summary::before { content:"›"; display:inline-block; font-size:15px;
                                transition:transform .18s cubic-bezier(.22,1,.36,1); }
details.how[open] > summary::before { transform:rotate(90deg); }
details.how > summary:hover { filter:brightness(1.15); }
details.how > summary:focus-visible { outline:2px solid var(--acc); outline-offset:3px;
                                      border-radius:4px; }
.how-body { margin:8px 0 4px; padding:14px 16px; background:var(--elev);
            border:1px solid var(--line-soft); border-radius:11px; }
.how-body ol { margin:0; padding-left:20px; }
.how-body ol li { margin:0 0 7px; font-size:13.5px; color:var(--mut); }
.how-body ol li:last-child { margin-bottom:0; }
.how-body ol li::marker { color:var(--acc); font-weight:650; }
.how-done { margin:11px 0 0; padding-top:10px; border-top:1px solid var(--line-soft);
            font-size:12.5px; color:var(--good); }
.how-done b { font-size:10.5px; text-transform:uppercase; letter-spacing:0.07em;
              color:var(--faint); margin-right:5px; font-weight:700; }
.phasehead .n { color:var(--faint); font-size:12px; font-variant-numeric:tabular-nums; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:14px;
        margin:14px 0; }
.card { background:var(--panel); border:1px solid var(--line-soft); border-radius:14px;
        padding:16px 18px; box-shadow:var(--shadow);
        transition:border-color .15s ease, transform .16s cubic-bezier(.22,1,.36,1); }
.card:hover { border-color:var(--acc-line); transform:translateY(-2px); }
.card.on { border-color:var(--acc); }
.card h3 { margin-top:0; }
.card .nm { font-size:17px; font-weight:650; letter-spacing:-0.01em; }
.avatar { width:44px; height:44px; border-radius:50%; display:inline-flex;
          align-items:center; justify-content:center; font-weight:700; font-size:18px;
          background:var(--acc-soft); color:var(--acc); flex:0 0 auto; }
.crow { display:flex; gap:12px; align-items:center; margin-bottom:10px; }

/* ── copy button on code blocks ───────────────────────────────────────────── */
.codewrap { position:relative; }
.copybtn { position:absolute; top:7px; right:7px; z-index:2; font:600 10.5px/1
           ui-monospace,Menlo,monospace; letter-spacing:0.05em; text-transform:uppercase;
           color:var(--mut); background:var(--panel); border:1px solid var(--line);
           border-radius:6px; padding:4px 8px; cursor:pointer; opacity:0; transition:
           opacity .14s ease, color .14s ease, border-color .14s ease; }
.codewrap:hover .copybtn, .copybtn:focus-visible { opacity:1; }
.copybtn:hover { color:var(--acc); border-color:var(--acc-line); }
.copybtn.ok { color:var(--good); border-color:var(--good); opacity:1; }
code.cmdline { display:block; padding-right:60px; }

/* ── sortable table headers ───────────────────────────────────────────────── */
th.sortable { cursor:pointer; user-select:none; white-space:nowrap; }
th.sortable:hover { color:var(--ink); }
th.sortable::after { content:"⇅"; opacity:0.35; margin-left:5px; font-size:10px; }
th.sortable.asc::after { content:"↑"; opacity:1; color:var(--acc); }
th.sortable.desc::after { content:"↓"; opacity:1; color:var(--acc); }

/* ── severity: a colored left rail on the whole card, scannable at a glance ── */
.sev { border-left:3px solid var(--line); }
.sev-critical { border-left-color:var(--bad);
                box-shadow:var(--shadow), inset 3px 0 0 -1px var(--bad); }
.sev-warning  { border-left-color:var(--warn); }
.sev-good     { border-left-color:var(--good); }
.sev-info     { border-left-color:var(--acc-line); }

/* ── empty states: icon + copy + action, not a bare sentence ──────────────── */
.empty { text-align:center; padding:34px 20px; color:var(--mut); }
.empty .ico { font-size:30px; opacity:0.5; display:block; margin-bottom:10px; }
.empty .act { margin-top:14px; }
.btn { display:inline-block; padding:8px 16px; border-radius:9px; background:var(--acc);
       color:var(--acc-ink); font-weight:650; font-size:13.5px; border:none;
       cursor:pointer; text-decoration:none; }
.btn:hover { filter:brightness(1.07); text-decoration:none; }
.btn.ghost { background:transparent; color:var(--acc); border:1px solid var(--acc-line); }

/* ── sticky in-page section jump (long pages) ─────────────────────────────── */
.toc { position:sticky; top:49px; z-index:10; display:flex; gap:6px; flex-wrap:wrap;
       padding:10px 0; margin:6px 0 4px; background:var(--bg);
       border-bottom:1px solid var(--line-soft); }
.toc a { font-size:12px; padding:4px 10px; border-radius:7px; background:var(--elev);
         color:var(--mut); border:1px solid var(--line-soft); white-space:nowrap; }
.toc a:hover { color:var(--ink); text-decoration:none; border-color:var(--acc-line); }

/* ── loading state + toast ────────────────────────────────────────────────── */
button[aria-busy="true"] { opacity:0.6; pointer-events:none; }
button[aria-busy="true"]::after { content:" …"; }
#toptop { position:fixed; right:20px; bottom:20px; z-index:30; width:40px; height:40px;
          border-radius:50%; background:var(--panel); border:1px solid var(--line);
          color:var(--ink); font-size:17px; cursor:pointer; opacity:0; transition:
          opacity .2s ease; box-shadow:var(--shadow); }
#toptop.show { opacity:0.85; } #toptop:hover { opacity:1; border-color:var(--acc-line); }
#toast { position:fixed; left:50%; bottom:26px; transform:translateX(-50%) translateY(20px);
         z-index:40; background:var(--elev); color:var(--ink); border:1px solid var(--line);
         border-radius:10px; padding:11px 18px; font-size:13.5px; box-shadow:var(--shadow);
         opacity:0; pointer-events:none; transition:opacity .2s ease, transform .2s ease; }
#toast.show { opacity:1; transform:translateX(-50%) translateY(0); }
@media (prefers-reduced-motion:reduce) { * { transition:none !important; } }
"""

# One shared, dependency-free enhancement layer. Everything here is PROGRESSIVE —
# the pages work with JS off (forms are real GET forms, chips are real links, code
# is selectable); this just makes them nicer. Inlined so the offline server needs
# no static assets.
_JS = r"""
(function(){
  function toast(msg){
    var t=document.getElementById('toast'); if(!t){t=document.createElement('div');
      t.id='toast'; document.body.appendChild(t);} t.textContent=msg; t.classList.add('show');
    clearTimeout(t._h); t._h=setTimeout(function(){t.classList.remove('show');},1900);
  }
  // Copy buttons on every code block.
  function addCopy(el, text){
    var w=el.closest('.codewrap'); if(w) return;
    w=document.createElement('span'); w.className='codewrap';
    el.parentNode.insertBefore(w, el); w.appendChild(el);
    var b=document.createElement('button'); b.className='copybtn'; b.type='button';
    b.textContent='copy'; b.setAttribute('aria-label','Copy to clipboard');
    b.addEventListener('click', function(e){ e.preventDefault(); e.stopPropagation();
      var t=text(); navigator.clipboard && navigator.clipboard.writeText(t).then(function(){
        b.textContent='copied'; b.classList.add('ok'); toast('Copied to clipboard');
        setTimeout(function(){b.textContent='copy'; b.classList.remove('ok');},1400);
      }, function(){ toast('Copy failed — select and press Ctrl+C'); });
    });
    w.appendChild(b);
  }
  document.querySelectorAll('pre').forEach(function(p){ addCopy(p, function(){return p.innerText;}); });
  document.querySelectorAll('.cmd > code, .fix code, .cmdline').forEach(function(c){
    addCopy(c, function(){return c.innerText;});
  });
  // Suggestion chips: fill the page's first text input and submit (progressive).
  document.querySelectorAll('.suggest a').forEach(function(a){
    a.addEventListener('click', function(e){
      var form=document.querySelector('form.calc'); var inp=form && form.querySelector('input[type=text],input:not([type])');
      if(form && inp){ e.preventDefault(); inp.value=a.getAttribute('data-q')||a.textContent;
        inp.focus(); form.requestSubmit ? form.requestSubmit() : form.submit(); }
    });
  });
  // Selects: mirror the chosen option into a title tooltip so a truncated value
  // is always inspectable on hover.
  document.querySelectorAll('select').forEach(function(s){
    function t(){ var o=s.options[s.selectedIndex]; s.title=o?o.text:''; }
    t(); s.addEventListener('change', t);
  });
  // Loading state on any form submit.
  document.querySelectorAll('form').forEach(function(f){
    f.addEventListener('submit', function(){
      var b=f.querySelector('button'); if(b){ b.setAttribute('aria-busy','true'); }
    });
  });
  // Sortable tables (opt-in via data-sortable on <table>, or any table with a
  // numeric column — we mark headers and sort client-side).
  document.querySelectorAll('table').forEach(function(tbl){
    var head=tbl.tHead; if(!head) return; var body=tbl.tBodies[0]; if(!body||body.rows.length<3) return;
    Array.prototype.forEach.call(head.rows[0].cells, function(th, idx){
      th.classList.add('sortable'); th.tabIndex=0;
      var dir=0;
      function sort(){
        dir = dir===1 ? -1 : 1;
        Array.prototype.forEach.call(head.rows[0].cells,function(o){o.classList.remove('asc','desc');});
        th.classList.add(dir===1?'asc':'desc');
        var rows=Array.prototype.slice.call(body.rows);
        rows.sort(function(a,b){
          var x=(a.cells[idx]||{}).innerText||'', y=(b.cells[idx]||{}).innerText||'';
          var nx=parseFloat(x.replace(/[^0-9.\-]/g,'')), ny=parseFloat(y.replace(/[^0-9.\-]/g,''));
          var bothNum=!isNaN(nx)&&!isNaN(ny)&&x.match(/\d/)&&y.match(/\d/);
          if(bothNum) return (nx-ny)*dir;
          return x.localeCompare(y)*dir;
        });
        rows.forEach(function(r){body.appendChild(r);});
      }
      th.addEventListener('click', sort);
      th.addEventListener('keydown', function(e){ if(e.key==='Enter'||e.key===' '){e.preventDefault();sort();} });
    });
  });
  // Back-to-top.
  var top=document.createElement('button'); top.id='toptop'; top.type='button';
  top.textContent='↑'; top.setAttribute('aria-label','Back to top');
  top.addEventListener('click', function(){ window.scrollTo({top:0,behavior:'smooth'}); });
  document.body.appendChild(top);
  window.addEventListener('scroll', function(){ top.classList.toggle('show', window.scrollY>400); });
})();
"""

# Nav in three groups: what you DO daily, what you BUILD, what you LEARN FROM.
# Fourteen undifferentiated links is a wall; grouped, it reads as a workspace.
_NAV_GROUPS = [
    ("operate", [("Overview", "/"), ("Audit", "/audit"), ("Launch", "/launch"),
                 ("Playbook", "/playbook")]),
    ("build",   [("Catalog", "/catalog"), ("Restyle", "/restyle"), ("Ideas", "/ideas"),
                 ("Search", "/search"), ("Actors", "/actors"),
                 ("Styles", "/styles"), ("Creators", "/creators")]),
    # Labels are kept short deliberately: fifteen full-width links wrap to a second
    # row, and a two-row nav pushes every page's content below the fold.
    ("learn",   [("Ask", "/assistant"), ("Organic", "/organic"),
                 ("Ads", "/advertising"), ("Budget", "/budget"),
                 ("Profit", "/profit")]),   # /million still routes; Profit is the goal page now
]

# Flat view, kept because callers and tests reason about "is this page in the nav".
_NAV = [item for _, items in _NAV_GROUPS for item in items]


def sparkline(values: list[float], width: int = 220, height: int = 44,
              stroke: str = "oklch(0.76 0.128 279)") -> str:
    """Inline SVG sparkline — no JS, no external assets. A soft area fill under the
    line grounds it; the last point gets a dot so the current value reads at a glance."""
    pts = [v for v in values if v is not None]
    if len(pts) < 2:
        return "<span class=mut>not enough data to chart</span>"
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    step = width / (len(pts) - 1)
    xy = [(i * step, height - 4 - (v - lo) / span * (height - 8))
          for i, v in enumerate(pts)]
    coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    area = f"0,{height} " + coords + f" {width},{height}"
    lx, ly = xy[-1]
    return (f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' "
            f"role='img' aria-label='trend' style='display:block'>"
            f"<polygon points='{area}' fill='{stroke}' fill-opacity='0.10'/>"
            f"<polyline points='{coords}' fill='none' stroke='{stroke}' "
            f"stroke-width='2' stroke-linejoin='round' stroke-linecap='round'/>"
            f"<circle cx='{lx:.1f}' cy='{ly:.1f}' r='2.6' fill='{stroke}'/></svg>")


_STAGE_CLASS = {"early_trend": "TEST", "growing": "TEST", "brand_new": "info",
                "peaking": "WATCH", "oversaturated": "KILL", "dead": "KILL"}


def stage_chip(stage: str) -> str:
    cls = _STAGE_CLASS.get(stage, "info")
    return f'<span class="chip {cls}">{esc(stage.replace("_", " "))}</span>'


def meter(fraction: float, label: str) -> str:
    pct = int(max(0.0, min(1.0, fraction)) * 100)
    color = "var(--good)" if pct >= 80 else ("var(--warn)" if pct >= 55 else "var(--bad)")
    return (f"<div class=bar title='{esc(label)}'>"
            f"<i style='width:{pct}%;background:{color}'></i></div>")


def page(title: str, body: str, active: str = "/") -> str:
    groups = []
    for i, (label_name, items) in enumerate(_NAV_GROUPS):
        links = "".join(
            f'<a href="{href}"{" class=on" if href == active else ""}>{esc(label)}</a>'
            for label, href in items
        )
        groups.append(f"<span class=navgroup title='{esc(label_name)}' "
                      f"aria-label='{esc(label_name)}'>{links}</span>")
    nav = "".join(groups)
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)} · ENGINE</title><style>{_CSS}</style></head><body>"
            f"<nav><span class=brand>◈ ENGINE</span>{nav}</nav>"
            f"<main>{body}</main><div id=toast></div>"
            f"<script>{_JS}</script></body></html>")


def toc(sections: list[tuple[str, str]]) -> str:
    """Sticky in-page jump list for long pages. sections = [(anchor_id, label)]."""
    if len(sections) < 3:
        return ""
    links = "".join(f"<a href='#{esc(a)}'>{esc(l)}</a>" for a, l in sections)
    return f"<nav class=toc aria-label='On this page'>{links}</nav>"


def empty_state(icon: str, text: str, action_html: str = "") -> str:
    """A consistent empty state: icon + copy + optional action button."""
    act = f"<div class=act>{action_html}</div>" if action_html else ""
    return (f"<div class=empty><span class=ico aria-hidden=true>{esc(icon)}</span>"
            f"<div>{text}</div>{act}</div>")


def cmd_code(command: str) -> str:
    """A shell command styled for the one-click copy button the JS attaches."""
    return f"<code class=cmdline>{esc(command)}</code>"


def chip(verdict: str) -> str:
    cls = verdict if verdict in ("TEST", "WATCH", "KILL") else "info"
    return f'<span class="chip {cls}">{esc(verdict)}</span>'


def kpi(value: str, label: str) -> str:
    return f'<div class=kpi><b>{esc(value)}</b><span>{esc(label)}</span></div>'


def table(headers: list[str], rows: list[list[str]], num_cols: set[int] = frozenset()) -> str:
    """rows contain PRE-RENDERED html cells; headers are escaped here."""
    # Header alignment must follow the cells beneath it — a left-aligned header over a
    # right-aligned column of figures reads as a misrendered table.
    head = "".join(
        f'<th{" class=num" if i in num_cols else ""}>{esc(h)}</th>'
        for i, h in enumerate(headers)
    )
    body = "".join(
        "<tr>" + "".join(
            f'<td{" class=num" if i in num_cols else ""}>{cell}</td>'
            for i, cell in enumerate(r)
        ) + "</tr>"
        for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


# ── minimal markdown → HTML (enough for the scorecard / monthly report) ─────────
_INLINE = [(re.compile(r"\*\*(.+?)\*\*"), r"<b>\1</b>"),
           (re.compile(r"`([^`]+)`"), r"<code>\1</code>")]


def _inline(s: str) -> str:
    s = esc(s)
    for pat, rep in _INLINE:
        s = pat.sub(rep, s)
    return s


def md_to_html(md: str) -> str:
    out: list[str] = []
    lines = md.splitlines()
    i = 0
    in_list = in_code = False
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            out.append("<pre>" if not in_code else "</pre>")
            in_code = not in_code
            i += 1
            continue
        if in_code:
            out.append(esc(ln))
            i += 1
            continue
        if in_list and not ln.lstrip().startswith("- "):
            out.append("</ul>")
            in_list = False
        # tables: a header row followed by a |---| separator
        if ln.strip().startswith("|") and i + 1 < len(lines) and \
                re.fullmatch(r"\s*\|[\s\-:|]+\|\s*", lines[i + 1] or ""):
            headers = [c.strip() for c in ln.strip().strip("|").split("|")]
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([_inline(c.strip())
                             for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append(table(headers, rows))
            continue
        if ln.startswith("### "):
            out.append(f"<h3>{_inline(ln[4:])}</h3>")
        elif ln.startswith("## "):
            out.append(f"<h2>{_inline(ln[3:])}</h2>")
        elif ln.startswith("# "):
            out.append(f"<h1>{_inline(ln[2:])}</h1>")
        elif ln.lstrip().startswith("> "):
            out.append(f"<blockquote>{_inline(ln.lstrip()[2:])}</blockquote>")
        elif ln.lstrip().startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(ln.lstrip()[2:])}</li>")
        elif ln.strip():
            out.append(f"<p>{_inline(ln)}</p>")
        i += 1
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</pre>")
    return "\n".join(out)
