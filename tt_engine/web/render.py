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
  --ink:oklch(0.945 0.006 82); --mut:oklch(0.685 0.01 82); --faint:oklch(0.56 0.008 82);
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
nav a.on { background:var(--acc-soft); color:var(--acc); font-weight:600; }
nav a:focus-visible { outline:2px solid var(--acc); outline-offset:-2px; }
.navgroup { display:flex; gap:2px; align-items:center; }
.navsep { width:1px; height:17px; background:var(--line); margin:0 9px; flex:0 0 auto;
          border-radius:1px; }
@media (max-width:760px) { .navsep { display:none; }
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
pre { padding:13px 15px; overflow-x:auto; }
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
                   background:var(--elev); border:1px solid var(--line);
                   border-radius:9px; color:var(--ink); font-size:14px; }
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
    for i, (_, items) in enumerate(_NAV_GROUPS):
        links = "".join(
            f'<a href="{href}"{" class=on" if href == active else ""}>{esc(label)}</a>'
            for label, href in items
        )
        sep = "<span class=navsep aria-hidden=true></span>" if i else ""
        groups.append(f"{sep}<span class=navgroup>{links}</span>")
    nav = "".join(groups)
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)} · ENGINE</title><style>{_CSS}</style></head><body>"
            f"<nav><span class=brand>◈ ENGINE</span>{nav}</nav>"
            f"<main>{body}</main></body></html>")


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
