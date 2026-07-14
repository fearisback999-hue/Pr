"""HTML rendering for the local dashboard. Stdlib only, zero external assets —
everything inlines so the page works on an offline desk server."""

from __future__ import annotations

import html
import re

esc = html.escape

_CSS = """
:root { --bg:#0e1116; --panel:#161b23; --line:#252c38; --ink:#dbe2ec; --mut:#8b95a5;
        --acc:#4da3ff; --good:#3fbf7f; --warn:#e0a63c; --bad:#e05c5c; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:15px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
a { color:var(--acc); text-decoration:none; } a:hover { text-decoration:underline; }
nav { display:flex; gap:4px; align-items:center; padding:10px 20px; background:var(--panel);
      border-bottom:1px solid var(--line); position:sticky; top:0; flex-wrap:wrap; }
nav .brand { font-weight:700; margin-right:14px; }
nav a { padding:6px 12px; border-radius:8px; color:var(--ink); }
nav a.on, nav a:hover { background:var(--line); text-decoration:none; }
main { max-width:1080px; margin:0 auto; padding:24px 20px 80px; }
h1 { font-size:22px; margin:18px 0 10px; } h2 { font-size:17px; margin:22px 0 8px; }
h3 { font-size:15px; margin:16px 0 6px; color:var(--mut); }
.panel { background:var(--panel); border:1px solid var(--line); border-radius:12px;
         padding:16px 18px; margin:14px 0; overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:14px; }
th, td { text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); }
th { color:var(--mut); font-weight:600; white-space:nowrap; }
tr:last-child td { border-bottom:none; }
.num { text-align:right; font-variant-numeric:tabular-nums; }
.chip { display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px;
        font-weight:700; }
.chip.TEST { background:#12351f; color:var(--good); }
.chip.WATCH { background:#332a12; color:var(--warn); }
.chip.KILL { background:#361616; color:var(--bad); }
.chip.info { background:var(--line); color:var(--mut); }
.kpis { display:flex; gap:12px; flex-wrap:wrap; margin:14px 0; }
.kpi { background:var(--panel); border:1px solid var(--line); border-radius:12px;
       padding:12px 18px; min-width:150px; }
.kpi b { display:block; font-size:22px; } .kpi span { color:var(--mut); font-size:12px; }
code, pre { background:#0a0d12; border:1px solid var(--line); border-radius:6px;
            font:13px/1.5 ui-monospace,Menlo,Consolas,monospace; }
code { padding:1px 6px; } pre { padding:12px 14px; overflow-x:auto; }
blockquote { border-left:3px solid var(--acc); margin:10px 0; padding:4px 14px;
             color:var(--mut); background:var(--panel); border-radius:0 8px 8px 0; }
form.calc { display:flex; gap:10px; flex-wrap:wrap; align-items:flex-end; }
form.calc label { display:flex; flex-direction:column; font-size:12px; color:var(--mut); }
form.calc input { margin-top:4px; padding:7px 9px; width:130px; background:#0a0d12;
                  border:1px solid var(--line); border-radius:8px; color:var(--ink); }
form.calc button { padding:8px 18px; border-radius:8px; border:none; background:var(--acc);
                   color:#04121f; font-weight:700; cursor:pointer; }
.step { padding:9px 0; border-bottom:1px solid var(--line); }
.step:last-child { border-bottom:none; }
.step .cmd { margin-top:3px; }
.mut { color:var(--mut); } .good { color:var(--good); } .warn { color:var(--warn); }
.bad { color:var(--bad); }
ul { margin:6px 0; padding-left:22px; }
.bar { height:6px; border-radius:99px; background:var(--line); overflow:hidden; margin:6px 0 2px; }
.bar > i { display:block; height:100%; background:var(--good); }
.pbstep { display:flex; gap:10px; padding:9px 0; border-bottom:1px solid var(--line);
          align-items:flex-start; }
.pbstep:last-child { border-bottom:none; }
.pbstep.done { opacity:.55; }
.pbstep .box { flex:0 0 auto; }
.pbstep .box a { display:block; width:18px; height:18px; border-radius:5px;
                  border:1px solid var(--line); text-align:center; line-height:16px;
                  font-size:13px; color:var(--good); text-decoration:none; }
.pbstep .box a:hover { border-color:var(--good); }
.pbstep .body b { display:inline-block; }
.pbstep .src { font-size:11px; color:var(--mut); margin-left:6px; }
.pbstep .cmd { margin-top:3px; }
.phasehead { display:flex; justify-content:space-between; align-items:baseline;
             margin:22px 0 4px; }
.phasehead .n { color:var(--mut); font-size:13px; }
"""

_NAV = [("Overview", "/"), ("Assistant", "/assistant"), ("Search", "/search"),
        ("Playbook", "/playbook"), ("Advertising", "/advertising"), ("Budget", "/budget"),
        ("Creators", "/creators"), ("Road to $1M", "/million")]


def sparkline(values: list[float], width: int = 220, height: int = 44,
              stroke: str = "#4da3ff") -> str:
    """Inline SVG sparkline — no JS, no external assets."""
    pts = [v for v in values if v is not None]
    if len(pts) < 2:
        return "<span class=mut>not enough data to chart</span>"
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    step = width / (len(pts) - 1)
    coords = " ".join(
        f"{i * step:.1f},{height - 4 - (v - lo) / span * (height - 8):.1f}"
        for i, v in enumerate(pts)
    )
    return (f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' "
            f"role='img' aria-label='trend'>"
            f"<polyline points='{coords}' fill='none' stroke='{stroke}' "
            f"stroke-width='2' stroke-linejoin='round' stroke-linecap='round'/></svg>")


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
    nav = "".join(
        f'<a href="{href}"{" class=on" if href == active else ""}>{esc(label)}</a>'
        for label, href in _NAV
    )
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)} · ENGINE</title><style>{_CSS}</style></head><body>"
            f"<nav><span class=brand>⚙ ENGINE</span>{nav}</nav>"
            f"<main>{body}</main></body></html>")


def chip(verdict: str) -> str:
    cls = verdict if verdict in ("TEST", "WATCH", "KILL") else "info"
    return f'<span class="chip {cls}">{esc(verdict)}</span>'


def kpi(value: str, label: str) -> str:
    return f'<div class=kpi><b>{esc(value)}</b><span>{esc(label)}</span></div>'


def table(headers: list[str], rows: list[list[str]], num_cols: set[int] = frozenset()) -> str:
    """rows contain PRE-RENDERED html cells; headers are escaped here."""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
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
