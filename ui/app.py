"""AutopsyGraph UI: Runs, Run detail (timeline graph + Investigate), Fleet.  Run: streamlit run ui/app.py"""
from __future__ import annotations

import html
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from forensics import engine  # noqa: E402
from forensics.claims import all_runs, claim_verdicts  # noqa: E402
from forensics.replay import GUARDRAILS, apply_fix  # noqa: E402

st.set_page_config(page_title="AutopsyGraph", page_icon="🩻", layout="wide", initial_sidebar_state="expanded")

FOOTER = ("We analyse observable agent behaviour only — never hidden chain of thought. Diagnoses are root-cause "
          "candidates with a confidence score, measured on synthetic labelled runs.")

PATTERNS = {
    "FP01": ("Wrong tool", "#0090FF"),
    "FP02": ("Invalid arguments", "#5B5BD6"),
    "FP03": ("Wrong entity", "#8E4EC6"),
    "FP04": ("Ignored tool error", "#E5484D"),
    "FP05": ("Hallucinated conclusion", "#F76B15"),
    "FP06": ("Skipped required step", "#AD7F58"),
    "FP07": ("Stale context", "#D6A300"),
    "FP10": ("Infinite retry", "#12A594"),
    "FP11": ("Premature answer", "#8B8D98"),
    "FP12": ("Unsafe action", "#CE2C31"),
}
INTENTS = {"order_status_ambiguous": "Order status (ambiguous name)", "refund_eligibility": "Refund eligibility",
           "refund_request": "Refund request", "delay_compensation": "Delay compensation",
           "policy_question": "Policy question", "order_status": "Order status", "product_info": "Product info",
           "return_jacket": "Return a jacket"}

CSS = """
<style>
#MainMenu, footer, [data-testid="stMainMenu"], [data-testid="stAppDeployButton"], [data-testid="stStatusWidget"] {
  display: none !important;}
header[data-testid="stHeader"] {background: rgba(255,255,255,.94); border-bottom: 1px solid rgba(22,24,29,.08);
  box-shadow: 0 1px 8px rgba(16,24,40,.04);}
.block-container {padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1500px;}
h1, h2, h3 {letter-spacing: -0.02em;}
.ag-brand {font-size: 1.45rem; font-weight: 800; letter-spacing: -0.03em; margin-bottom: 0.1rem;}
.ag-brand span {background: linear-gradient(90deg,#E5484D,#8E4EC6); -webkit-background-clip: text; color: transparent;}
.ag-tag {color: #5B6170; font-size: 0.86rem; margin-bottom: 1rem;}
.ag-live {display:inline-flex; align-items:center; gap:.45rem; font-size:.8rem; color:#1F7A3F; background:#E9F7EE;
          border:1px solid #BFE6CC; padding:.2rem .6rem; border-radius:999px;}
.ag-live i {width:.5rem; height:.5rem; border-radius:50%; background:#2EAA5C; display:inline-block;}
.ag-title {font-size: 2.1rem; font-weight: 800; letter-spacing: -0.03em; margin: 0 0 .2rem 0;}
.ag-sub {color:#5B6170; margin-bottom: 1.2rem;}
.ag-kpis {display:grid; grid-template-columns: repeat(4, 1fr); gap: .9rem; margin: .4rem 0 1.2rem 0;}
.ag-kpi {background:#fff; border:1px solid #E6E9F0; border-radius:16px; padding:1rem 1.1rem;
         box-shadow: 0 1px 2px rgba(16,24,40,.04);}
.ag-kpi .l {color:#5B6170; font-size:.8rem; text-transform:uppercase; letter-spacing:.06em;}
.ag-kpi .v {font-size:2rem; font-weight:800; letter-spacing:-0.03em; line-height:1.15;}
.ag-kpi .s {color:#8B8D98; font-size:.78rem;}
.ag-pill {display:inline-block; padding:.18rem .65rem; border-radius:999px; font-size:.78rem; font-weight:600;}
.ag-ok {background:#E9F7EE; color:#1F7A3F;} .ag-bad {background:#FDECEC; color:#B4232A;}
.ag-badge {display:inline-block; padding:.22rem .7rem; border-radius:8px; font-weight:700; font-size:.85rem; color:#fff;}
.ag-card {background:#fff; border:1px solid #E6E9F0; border-radius:16px; padding:1rem 1.15rem; margin-bottom:.8rem;}
.ag-card .h {color:#5B6170; font-size:.74rem; text-transform:uppercase; letter-spacing:.07em; margin-bottom:.35rem;}
.ag-quote {font-size:1.02rem; line-height:1.45;}
.ag-verdict {border:1px solid #F3C4C6; border-left:6px solid #E5484D; background:linear-gradient(180deg,#FFF7F7,#FFFFFF);
             border-radius:16px; padding:1.1rem 1.25rem; margin:.6rem 0 .8rem 0;}
.ag-verdict .top {display:flex; flex-wrap:wrap; align-items:center; gap:.6rem; margin-bottom:.7rem;}
.ag-verdict .root {font-size:1.25rem; font-weight:800; letter-spacing:-0.02em;}
.ag-sec {margin-top:.75rem;}
.ag-sec .h {color:#5B6170; font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; margin-bottom:.2rem;}
.ag-sec .b {line-height:1.5;}
.ag-conf {height:8px; background:#F1F2F6; border-radius:99px; overflow:hidden; width:140px; display:inline-block;
          vertical-align:middle;}
.ag-conf i {display:block; height:100%; background:linear-gradient(90deg,#F76B15,#E5484D);}
.ag-chip {display:inline-block; font-size:.8rem; padding:.18rem .55rem; border-radius:8px; margin:.15rem .3rem .15rem 0;
          background:#F4F6FA; border:1px solid #E6E9F0;}
.ag-ev {display:block; background:#F4F8FF; border:1px solid #D5E6FF; border-radius:10px; padding:.45rem .65rem;
        margin:.3rem 0; font-size:.9rem;}
.ag-ev code {background:transparent; color:#0060C7; font-size:.8rem;}
.ag-stale {background:#FDECEC; color:#B4232A; border-radius:6px; padding:.05rem .4rem; font-size:.72rem; font-weight:700;
           margin-left:.35rem;}
.ag-fleet {background:linear-gradient(135deg,#16181D,#2A2D36); color:#fff; border-radius:18px; padding:1.3rem 1.5rem;
           margin:.4rem 0 1.2rem 0;}
.ag-fleet .big {font-size:3.2rem; font-weight:800; letter-spacing:-0.04em; line-height:1;}
.ag-fleet .big span {color:#FF6369;}
.ag-fleet .l {color:#B9BDC8; margin-top:.35rem;}
.ag-callout {background:#F3E8FF; border:1px solid #E1CCF7; color:#4E2A84; border-radius:12px; padding:.6rem .8rem;
             margin-top:.8rem; font-size:.92rem;}
.ag-ai {background:#F8F9FB; border:1px dashed #D3D7E1; border-radius:12px; padding:.6rem .8rem; margin-top:.8rem;
        color:#4A4F5C; font-size:.9rem;}
.ag-legend span {display:inline-flex; align-items:center; gap:.3rem; margin-right:.9rem; font-size:.78rem; color:#5B6170;}
.ag-legend i {width:.75rem; height:.75rem; border-radius:3px; display:inline-block; border:1px solid rgba(0,0,0,.15);}
.ag-foot {color:#8B8D98; font-size:.78rem; border-top:1px solid #EEF0F4; padding-top:.7rem; margin-top:1.6rem;}
div.stButton > button[kind="primary"] {border-radius:12px; font-weight:700; padding:.6rem 1rem; min-height:44px;
  box-shadow: 0 1px 2px rgba(229,72,77,.25), 0 4px 12px rgba(229,72,77,.18);
  transition-property: transform, box-shadow, background-color; transition-duration: 150ms;
  transition-timing-function: ease-out;}
div.stButton > button[kind="primary"]:hover {box-shadow: 0 2px 4px rgba(229,72,77,.3), 0 8px 20px rgba(229,72,77,.22);}
div.stButton > button[kind="primary"]:active {transform: scale(0.97);}
/* polish: smoothing, balanced headings, pretty body text, tabular numbers */
html, body, [class*="st-"] {-webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;}
.ag-title, .ag-verdict .root, .ag-brand {text-wrap: balance;}
.ag-sub, .ag-quote, .ag-sec .b, .ag-fleet .l, .ag-callout, .ag-ai, .ag-ev {text-wrap: pretty;}
.ag-kpi .v, .ag-fleet .big, .ag-chip b {font-variant-numeric: tabular-nums;}
/* depth: layered, transparent shadows; outer radius = inner radius + padding */
.ag-kpi, .ag-card {box-shadow: 0 1px 1px rgba(16,24,40,.03), 0 2px 6px rgba(16,24,40,.04);
  transition-property: transform, box-shadow; transition-duration: 160ms; transition-timing-function: ease-out;}
.ag-kpi:hover {transform: translateY(-1px); box-shadow: 0 2px 4px rgba(16,24,40,.05), 0 10px 24px rgba(16,24,40,.07);}
.ag-verdict {box-shadow: 0 1px 2px rgba(229,72,77,.06), 0 12px 32px rgba(229,72,77,.08);
  animation: ag-enter 280ms var(--ease-out) both;}
.ag-fleet {box-shadow: 0 2px 6px rgba(16,24,40,.12), 0 18px 40px rgba(16,24,40,.18);
  animation: ag-enter 320ms var(--ease-out) both;}
@keyframes ag-enter {from {opacity: 0; transform: translateY(8px); filter: blur(2px);}
                     to {opacity: 1; transform: none; filter: none;}}
/* timeline motion: steps cascade in, arrows draw, the root cause glows, the fix appears last */
.ag-step {opacity: 0; animation: ag-pop 420ms var(--ease-out) forwards;}
.ag-draw {stroke-dasharray: 80; stroke-dashoffset: 80; animation: ag-draw-line 360ms ease-out forwards;}
.ag-ghost {opacity: 0; animation: ag-enter 460ms var(--ease-out) forwards;}
.ag-root {animation: ag-glow 1.6s ease-in-out 600ms 3;}
@keyframes ag-pop {from {opacity: 0; transform: translateY(10px) scale(.97);} to {opacity: 1; transform: none;}}
@keyframes ag-draw-line {to {stroke-dashoffset: 0;}}
@keyframes ag-glow {0%, 100% {filter: drop-shadow(0 0 0 rgba(229,72,77,0));}
                    50% {filter: drop-shadow(0 0 10px rgba(229,72,77,.55));}}
.ag-step, .ag-ghost {transform-box: fill-box; transform-origin: center;}
/* page-level motion */
.ag-kpi {animation: ag-enter 380ms var(--ease-out) both;}
.ag-kpi:nth-child(2) {animation-delay: 60ms;} .ag-kpi:nth-child(3) {animation-delay: 120ms;}
.ag-kpi:nth-child(4) {animation-delay: 180ms;}
.ag-title {animation: ag-enter 300ms ease-out both;}
.ag-fleet .big span {display: inline-block; animation: ag-bounce 700ms cubic-bezier(.34,1.56,.64,1) 200ms both;}
@keyframes ag-bounce {from {opacity: 0; transform: scale(.4);} to {opacity: 1; transform: scale(1);}}
.ag-fixed {border: 1px solid #BFE6CC; border-left: 6px solid #2EAA5C; background: linear-gradient(180deg,#F2FBF5,#fff);
  border-radius: 16px; padding: 1rem 1.2rem; margin: .8rem 0; animation: ag-enter 360ms var(--ease-out) both;
  box-shadow: 0 1px 2px rgba(46,170,92,.08), 0 12px 32px rgba(46,170,92,.10);}
.ag-fixed .t {font-size: 1.2rem; font-weight: 800; color: #1F7A3F;}
.ag-fixed .s {color: #3D6B4D;}
.ag-fixed-bad {border-color: #F3C4C6; border-left-color: #E5484D; background: #FFF7F7;}
.ag-fixed-bad .t {color: #B4232A;}
/* ===== colour + motion layer (Emil Kowalski tokens) ===== */
:root {--ease-out: cubic-bezier(0.23, 1, 0.32, 1); --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);}
.stApp {background:
  radial-gradient(1200px 600px at -10% -10%, rgba(229,72,77,.10), transparent 60%),
  radial-gradient(1000px 600px at 110% 0%, rgba(142,78,198,.12), transparent 60%),
  radial-gradient(900px 700px at 50% 120%, rgba(0,144,255,.08), transparent 60%), #F7F8FC;}
.stApp::before {content:""; position:fixed; inset:-20%; pointer-events:none; z-index:0;
  background: conic-gradient(from 0deg at 50% 50%, rgba(229,72,77,.06), rgba(142,78,198,.06), rgba(0,144,255,.05),
  rgba(229,72,77,.06)); filter: blur(60px); animation: ag-spin 40s linear infinite;}
@keyframes ag-spin {to {transform: rotate(360deg);}}
.block-container {position: relative; z-index: 1; padding-top: 5.2rem !important;}
.ag-hero {display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:1.1rem 1.4rem;
  border-radius:20px; margin:.2rem 0 1.4rem 0; color:#fff; position:relative; overflow:hidden;
  background: linear-gradient(120deg,#16181D 0%,#2B1B3D 45%,#4A1622 100%); background-size: 200% 200%;
  box-shadow: 0 2px 6px rgba(16,24,40,.18), 0 20px 50px rgba(74,22,34,.25);
  animation: ag-enter 240ms var(--ease-out) both, ag-shift 14s ease-in-out infinite alternate;}
.ag-hero::after {content:""; position:absolute; inset:0; pointer-events:none;
  background: linear-gradient(105deg, transparent 40%, rgba(255,255,255,.10) 50%, transparent 60%);
  transform: translateX(-100%); animation: ag-sheen 5s var(--ease-in-out) 1s infinite;}
@keyframes ag-shift {from {background-position: 0% 50%;} to {background-position: 100% 50%;}}
@keyframes ag-sheen {0% {transform: translateX(-100%);} 35%, 100% {transform: translateX(100%);}}
.ag-hero .ag-brand {color:#fff; margin:0;} .ag-hero .ag-tag {color:#C9CCD6; margin:0;}
.ag-hero .ag-brand span {background: linear-gradient(90deg,#FF6369,#C084FC,#60A5FA,#FF6369); background-size:300% 100%;
  -webkit-background-clip:text; color:transparent; animation: ag-shift 6s linear infinite alternate;}
.ag-hero-r {display:flex; gap:.6rem; align-items:center; flex-wrap:wrap;}
.ag-event {font-size:.78rem; color:#E7E9F0; border:1px solid rgba(255,255,255,.18); padding:.2rem .6rem; border-radius:999px;
  background: rgba(255,255,255,.06);}
.ag-live i {animation: ag-ping 1.8s var(--ease-out) infinite;}
@keyframes ag-ping {0% {box-shadow: 0 0 0 0 rgba(46,170,92,.6);} 80%, 100% {box-shadow: 0 0 0 8px rgba(46,170,92,0);}}
/* coloured accents on cards */
.ag-kpi {position:relative; overflow:hidden;}
.ag-kpi::before {content:""; position:absolute; left:0; top:0; right:0; height:4px;
  background: linear-gradient(90deg,#E5484D,#8E4EC6,#0090FF); transform-origin:left; transform: scaleX(0);
  animation: ag-bar 600ms var(--ease-out) 200ms forwards;}
.ag-kpi:nth-child(2)::before {animation-delay: 260ms;} .ag-kpi:nth-child(3)::before {animation-delay: 320ms;}
.ag-kpi:nth-child(4)::before {animation-delay: 380ms;}
@keyframes ag-bar {to {transform: scaleX(1);}}
.ag-card {border-top: 3px solid #E6E9F0;}
.ag-card:nth-of-type(1) {border-top-color:#0090FF;}
.ag-chip {transition-property: transform, background-color, border-color; transition-duration: 160ms;
  transition-timing-function: var(--ease-out);}
.ag-ev {transition-property: transform, box-shadow; transition-duration: 180ms; transition-timing-function: var(--ease-out);}
.ag-ev, .ag-chip {animation: ag-enter 260ms var(--ease-out) both;}
.ag-ev:nth-child(2) {animation-delay: 40ms;} .ag-ev:nth-child(3) {animation-delay: 80ms;}
.ag-chip:nth-child(2) {animation-delay: 40ms;} .ag-chip:nth-child(3) {animation-delay: 80ms;}
.ag-chip:nth-child(4) {animation-delay: 120ms;}
.ag-sec {animation: ag-enter 260ms var(--ease-out) both;}
.ag-sec:nth-of-type(2) {animation-delay: 60ms;} .ag-sec:nth-of-type(3) {animation-delay: 120ms;}
.ag-sec:nth-of-type(4) {animation-delay: 180ms;} .ag-sec:nth-of-type(5) {animation-delay: 240ms;}
.ag-conf i {transform-origin: left; animation: ag-bar 700ms var(--ease-out) 150ms both;}
.ag-badge {animation: ag-pop 240ms var(--ease-out) both;}
.ag-stale {animation: ag-flash 1.4s ease-in-out 400ms 2;}
@keyframes ag-flash {50% {box-shadow: 0 0 0 4px rgba(229,72,77,.25);}}
.ag-callout {animation: ag-enter 280ms var(--ease-out) 260ms both;}
.ag-step rect, .ag-ghost rect {transition-property: transform; transition-duration: 180ms;
  transition-timing-function: var(--ease-out); transform-box: fill-box; transform-origin: center;}
@media (hover: hover) and (pointer: fine) {
  .ag-card:hover {transform: translateY(-2px); box-shadow: 0 2px 4px rgba(16,24,40,.05), 0 14px 30px rgba(16,24,40,.08);}
  .ag-chip:hover {transform: translateY(-1px); background:#EEF1F7; border-color:#D3D7E1;}
  .ag-ev:hover {transform: translateX(3px); box-shadow: 0 6px 16px rgba(0,96,199,.10);}
  .ag-step:hover rect {transform: scale(1.03);}
  .ag-verdict:hover {box-shadow: 0 2px 4px rgba(229,72,77,.08), 0 18px 40px rgba(229,72,77,.12);}
}
@media (prefers-reduced-motion: reduce) {
  .stApp::before, .ag-hero, .ag-hero::after, .ag-hero .ag-brand span, .ag-live i, .ag-kpi::before, .ag-ev, .ag-chip,
  .ag-sec, .ag-conf i, .ag-badge, .ag-stale, .ag-callout {animation: none !important;}
  .ag-kpi::before, .ag-conf i {transform: none;}
  .ag-verdict, .ag-fleet, .ag-kpi, .ag-title, .ag-fixed, .ag-fleet .big span, .ag-root {animation: none;}
  .ag-step, .ag-ghost {animation: none; opacity: 1;} .ag-draw {animation: none; stroke-dashoffset: 0;}
  .ag-kpi:hover {transform: none;}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------- data (cached) ----------

@st.cache_data(ttl=120, show_spinner=False)
def runs() -> pd.DataFrame:
    return pd.DataFrame(all_runs())


@st.cache_data(ttl=600, show_spinner=False)
def timeline(run_id: str) -> list[dict]:
    return engine.timeline(run_id)


@st.cache_data(ttl=600, show_spinner=False)
def header(run_id: str) -> dict:
    return engine.run_header(run_id)


@st.cache_data(ttl=600, show_spinner=False)
def claims(run_id: str) -> list[dict]:
    return claim_verdicts(run_id)


@st.cache_data(ttl=3600, show_spinner=False)
def investigate(run_id: str) -> dict:
    return engine.investigate(run_id)


@st.cache_data(ttl=120, show_spinner=False)
def fleet() -> dict:
    return {"ignored": engine.fleet_ignored_errors(), "patterns": engine.fleet_patterns(),
            "tools": engine.fleet_tools(), "metrics": engine.metrics()}


@st.cache_data(ttl=300, show_spinner=False)
def aura_ok() -> bool:
    try:
        engine.read("RETURN 1 AS ok")
        return True
    except Exception:
        return False


# ---------- helpers ----------

def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def badge(code: str | None) -> str:
    if not code:
        return ""
    name, color = PATTERNS.get(code, (code, "#8B8D98"))
    return f'<span class="ag-badge" style="background:{color}">{esc(code)} · {esc(name)}</span>'


def humanize_outcome(outcome: str | None) -> str:
    if not outcome or outcome == "success":
        return "—"
    parts = []
    for p in outcome.split(";"):
        kind, _, what = p.partition(":")
        parts.append({"MISMATCH": f"wrong {what}", "MISSING": f"missing {what}",
                      "FORBIDDEN": f"called forbidden {what}", "MAX_STEPS": "hit step limit"}.get(kind, p))
    return ", ".join(parts)


def _dot_text(s: str, width: int) -> str:
    return "\\n".join(textwrap.wrap(str(s).replace("\\", "/").replace('"', "'"), width)) or " "


def dot(tl: list[dict], cl: list[dict], verdict: dict | None) -> str:
    """Left-to-right timeline. Red = root cause, amber = symptom, blue = evidence (red border = stale),
    purple = ground truth, green dashed = what the agent should have done."""
    root = verdict["root_step_idx"] if verdict else None
    flagged = {int(c.split("@")[1]) for c in (verdict or {}).get("contributing", [])
               if "@" in c and c.split("@")[1].isdigit()}
    cited = set((verdict or {}).get("evidence_ids", []))
    out = ['digraph G { rankdir=LR; bgcolor="transparent"; pad=0.25; nodesep=0.3; ranksep=0.55; splines=true;',
           'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=12, margin="0.18,0.1", '
           'color="#C7CDD9", fillcolor="#F4F6FA", fontcolor="#16181D"];',
           'edge [color="#9AA3B2", fontname="Helvetica", fontsize=10, fontcolor="#5B6170", arrowsize=0.7];']
    for s in tl:
        sid = f'S{s["idx"]}'
        if s["kind"] == "answer":
            ok = all(c["verdict"] == "match" for c in cl) if cl else True
            fill, col = ("#E9F7EE", "#2EAA5C") if ok else ("#FDECEC", "#E5484D")
            out.append(f'{sid} [label="{s["idx"]} · FINAL ANSWER", fillcolor="{fill}", color="{col}", penwidth=2, '
                       f'fontname="Helvetica-Bold"];')
            continue
        status = (s.get("error") or s.get("status") or "").upper()
        args = ", ".join(f'{a["name"]}={a["value"]}' for a in s.get("args") or [])
        label = f'{s["idx"]} · {s["tool"]}\\n{status}' + (f'\\n{_dot_text(args, 34)}' if args else "")
        if s["idx"] == root:
            style = 'fillcolor="#FDECEC", color="#E5484D", penwidth=3, fontcolor="#B4232A", fontname="Helvetica-Bold"'
        elif s["idx"] in flagged:
            style = 'fillcolor="#FFF4E0", color="#F5A524", penwidth=2'
        else:
            style = 'fillcolor="#F4F6FA", color="#C7CDD9", penwidth=1.2'
        out.append(f'{sid} [label="{label}", {style}];')
        for e in s.get("evidence") or []:
            txt = ("STALE · " if e["stale"] else "") + e["text"]
            border = "#E5484D" if e["stale"] else ("#0090FF" if e["id"] in cited else "#9CC8F5")
            fill = "#FFF5F5" if e["stale"] else "#EEF6FF"
            out.append(f'"{e["id"]}" [label="{_dot_text(txt, 30)}", shape=note, fillcolor="{fill}", color="{border}", '
                       f'fontsize=10, penwidth={2 if e["id"] in cited else 1}];')
            out.append(f'{sid} -> "{e["id"]}" [style=dotted, arrowhead=none, color="#9CC8F5"];')
    for a, b in zip(tl, tl[1:]):
        out.append(f'S{a["idx"]} -> S{b["idx"]} [penwidth=2.2, color="#5B6170"];')
    ans = next((s["idx"] for s in tl if s["kind"] == "answer"), None)
    for i, c in enumerate(cl):
        out.append(f'GT{i} [label="ground truth\\n{_dot_text(c["fact"] + " = " + str(c["expected"]), 26)}", '
                   f'fillcolor="#F3E8FF", color="#8E4EC6", fontcolor="#4E2A84"];')
        if ans:
            said = f'said {c["asserted"]}' if c["asserted"] is not None else "missing"
            col = "#2EAA5C" if c["verdict"] == "match" else "#E5484D"
            out.append(f'S{ans} -> GT{i} [label="{_dot_text(said, 18)}", color="{col}", fontcolor="{col}", penwidth=2];')
    if verdict and root:
        out.append(f'GHOST [label="should have:\\n{_dot_text(verdict["counterfactual"], 30)}", '
                   f'style="dashed,rounded,filled", fillcolor="#F2FBF5", color="#2EAA5C", fontcolor="#1F7A3F", '
                   f'fontsize=10];')
        out.append(f'S{root} -> GHOST [style=dashed, color="#2EAA5C"];')
    out.append("}")
    return "\n".join(out)


def _wrap_ident(name: str, width: int) -> list[str]:
    """Wrap snake_case identifiers at underscores, never mid-word."""
    lines, cur = [], ""
    for part in str(name).split("_"):
        piece = part if not cur else "_" + part
        if cur and len(cur) + len(piece) > width:
            lines.append(cur + "_")
            cur = part
        else:
            cur += piece
    return lines + [cur]


def _wrap(s, width: int, max_lines: int = 4) -> list[str]:
    lines = textwrap.wrap(str(s), width) or [""]
    return lines[:max_lines - 1] + [textwrap.shorten(" ".join(lines[max_lines - 1:]), width, placeholder="…")] \
        if len(lines) > max_lines else lines


def _texts(x: float, y: float, lines: list[tuple[str, int, str, str]]) -> tuple[str, float]:
    """lines = [(text, size, color, weight)] stacked from y; returns svg and the y after the block."""
    out = []
    for text, size, color, weight in lines:
        y += size + 4
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}">{esc(text)}</text>')
    return "".join(out), y


def svg_timeline(tl: list[dict], cl: list[dict], verdict: dict | None) -> str:
    """Server-rendered SVG timeline (no client-side graph engine): steps left to right, evidence below each step,
    ground truth right of the answer, and a green dashed 'should have done' box above the root cause."""
    root = verdict["root_step_idx"] if verdict else None
    flagged = {int(c.split("@")[1]) for c in (verdict or {}).get("contributing", [])
               if "@" in c and c.split("@")[1].isdigit()}
    cited = set((verdict or {}).get("evidence_ids", []))
    W, GAP, X0 = 178, 40, 14
    Y_STEP = 128 if verdict else 22
    parts, step_box = [], {}
    # steps
    for i, s in enumerate(tl):
        x = X0 + i * (W + GAP)
        if s["kind"] == "answer":
            ok = all(c["verdict"] == "match" for c in cl) if cl else True
            fill, stroke, tc = ("#E9F7EE", "#2EAA5C", "#1F7A3F") if ok else ("#FDECEC", "#E5484D", "#B4232A")
            body, yb = _texts(x + 14, Y_STEP + 8, [(f"STEP {s['idx']}", 11, "#8B8D98", "600"),
                                                   ("FINAL ANSWER", 15, tc, "800"),
                                                   ("matches truth" if ok else "contradicts truth", 12, tc, "600")])
        else:
            status = (s.get("error") or s.get("status") or "").upper()
            st_col = "#1F7A3F" if status == "OK" else "#B4232A"
            args = ", ".join(f'{a["name"]}={a["value"]}' for a in s.get("args") or [])
            lines = [(f"STEP {s['idx']}", 11, "#8B8D98", "600")]
            lines += [(t, 15, "#16181D", "700") for t in _wrap_ident(s["tool"], 17)]
            lines += [(("● " if status == "OK" else "▲ ") + status, 13, st_col, "700")]
            lines += [(t, 11.5, "#5B6170", "400") for t in _wrap(args, 26, 2)] if args else []
            body, yb = _texts(x + 14, Y_STEP + 8, lines)
            if s["idx"] == root:
                fill, stroke = "#FDECEC", "#E5484D"
            elif s["idx"] in flagged:
                fill, stroke = "#FFF4E0", "#F5A524"
            else:
                fill, stroke = "#FFFFFF", "#C7CDD9"
        h = max(96, yb - Y_STEP + 14)
        sw = 3 if s["idx"] == root else 2 if s["idx"] in flagged else 1.3
        step_box[s["idx"]] = (x, h)
        delay = i * 110
        cls = ' class="ag-root"' if s["idx"] == root else ""
        badge_svg = (f'<rect x="{x + W - 92}" y="{Y_STEP - 11}" width="84" height="22" rx="11" fill="#E5484D"/>'
                     f'<text x="{x + W - 50}" y="{Y_STEP + 4}" font-size="11" fill="#fff" font-weight="800" '
                     f'text-anchor="middle">ROOT CAUSE</text>') if s["idx"] == root else ""
        parts.append(f'<g class="ag-step" style="animation-delay:{delay}ms"><rect{cls} x="{x}" y="{Y_STEP}" '
                     f'width="{W}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
                     f'{body}{badge_svg}</g>')
    max_h = max(h for _, h in step_box.values())
    # arrows between steps
    for i, (a, b) in enumerate(zip(tl, tl[1:])):
        xa, _ = step_box[a["idx"]]
        xb, _ = step_box[b["idx"]]
        y = Y_STEP + 40
        parts.append(f'<line class="ag-draw" style="animation-delay:{i * 110 + 80}ms" x1="{xa + W + 4}" y1="{y}" '
                     f'x2="{xb - 6}" y2="{y}" stroke="#5B6170" stroke-width="2.2" marker-end="url(#ag-arrow)"/>')
    # evidence below steps
    y_ev0, bottom = Y_STEP + max_h + 26, Y_STEP + max_h
    for i, s in enumerate(tl):
        x, h = step_box[s["idx"]]
        y = y_ev0
        parts.append(f'<g class="ag-step" style="animation-delay:{i * 110 + 260}ms">')
        for e in s.get("evidence") or []:
            lines = ([("STALE · superseded", 10, "#B4232A", "800")] if e["stale"] else []) + \
                    [(t, 12, "#16181D", "400") for t in _wrap(e["text"], 25, 4)]
            body, yb = _texts(x + 12, y + 4, lines)
            eh = yb - y + 12
            stroke = "#E5484D" if e["stale"] else ("#0090FF" if e["id"] in cited else "#9CC8F5")
            fill = "#FFF5F5" if e["stale"] else "#EEF6FF"
            parts.append(f'<line x1="{x + W / 2}" y1="{Y_STEP + h}" x2="{x + W / 2}" y2="{y}" stroke="#9CC8F5" '
                         f'stroke-dasharray="3 3"/>')
            parts.append(f'<rect x="{x}" y="{y}" width="{W}" height="{eh}" rx="10" fill="{fill}" stroke="{stroke}" '
                         f'stroke-width="{2 if e["id"] in cited else 1}"/>' + body)
            if e["id"] in cited:
                parts.append(f'<text x="{x + W - 10}" y="{y + 14}" font-size="9" fill="#0060C7" font-weight="700" '
                             f'text-anchor="end">CITED</text>')
            y += eh + 10
        parts.append("</g>")
        bottom = max(bottom, y)
    # ground truth right of the answer
    ans = next((s["idx"] for s in tl if s["kind"] == "answer"), None)
    x_gt = X0 + len(tl) * (W + GAP) + 44
    y = Y_STEP
    parts.append(f'<g class="ag-step" style="animation-delay:{len(tl) * 110 + 120}ms">')
    for c in cl:
        lines = [("GROUND TRUTH", 11, "#6E56CF", "800")] + \
                [(t, 14, "#4E2A84", "700") for t in _wrap_ident(c["fact"], 17)] + \
                [(f'= {c["expected"]}', 15, "#4E2A84", "800")]
        body, yb = _texts(x_gt + 12, y + 4, lines)
        gh = yb - y + 14
        parts.append(f'<rect x="{x_gt}" y="{y}" width="{W}" height="{gh}" rx="14" fill="#F3E8FF" stroke="#8E4EC6" '
                     f'stroke-width="1.5"/>' + body)
        if ans is not None:
            xa, ha = step_box[ans]
            ok = c["verdict"] == "match"
            col = "#2EAA5C" if ok else "#E5484D"
            said = f'said {c["asserted"]}' if c["asserted"] is not None else "missing"
            y_to = y + gh / 2
            y_from = min(y_to, Y_STEP + ha - 14)  # leave from the answer box, elbow down to lower truths
            x_mid = xa + W + 22
            parts.append(f'<path d="M{xa + W + 2} {y_from} H{x_mid} V{y_to} H{x_gt - 6}" fill="none" stroke="{col}" '
                         f'stroke-width="2.2" marker-end="url(#ag-arrow-{"g" if ok else "r"})"/>'
                         f'<text x="{(x_mid + x_gt) / 2 + 2}" y="{y_to - 7}" font-size="11" fill="{col}" '
                         f'font-weight="700" text-anchor="middle">{esc(said)}</text>')
        y += gh + 12
        bottom = max(bottom, y)
    parts.append("</g>")
    # "should have done" above the root
    if verdict and root in step_box:
        x, _ = step_box[root]
        cf = _wrap(verdict["counterfactual"], 64, 3)
        gw = min(W * 2 + GAP + 60, 470)
        body, _ = _texts(x + 12, 6, [("SHOULD HAVE", 10, "#1F7A3F", "800")] + [(t, 11, "#1F7A3F", "500") for t in cf])
        parts.append(f'<g class="ag-ghost" style="animation-delay:{len(tl) * 110 + 300}ms">'
                     f'<rect x="{x}" y="8" width="{gw}" height="{14 + 15 * (len(cf) + 1)}" rx="12" fill="#F2FBF5" '
                     f'stroke="#2EAA5C" stroke-width="1.5" stroke-dasharray="6 4"/>{body}'
                     f'<line x1="{x + 30}" y1="{22 + 15 * (len(cf) + 1)}" x2="{x + 30}" y2="{Y_STEP - 4}" '
                     f'stroke="#2EAA5C" stroke-width="1.6" stroke-dasharray="4 3" marker-end="url(#ag-arrow-g)"/></g>')
    width = x_gt + W + X0
    defs = ('<defs>'
            '<marker id="ag-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#5B6170"/></marker>'
            '<marker id="ag-arrow-g" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#2EAA5C"/></marker>'
            '<marker id="ag-arrow-r" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#E5484D"/></marker></defs>')
    return (f'<div style="overflow-x:auto;border:1px solid #E6E9F0;border-radius:16px;background:#FBFCFE;padding:6px">'
            f'<svg viewBox="0 0 {width} {bottom + 16}" width="100%" style="min-width:{min(width, 1000)}px" '
            f'font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif" role="img" '
            f'aria-label="Run timeline">{defs}{"".join(parts)}</svg></div>')


def kpis(items: list[tuple[str, str, str]]) -> None:
    cells = "".join(f'<div class="ag-kpi"><div class="l">{esc(l)}</div><div class="v">{esc(v)}</div>'
                    f'<div class="s">{esc(s)}</div></div>' for l, v, s in items)
    st.markdown(f'<div class="ag-kpis">{cells}</div>', unsafe_allow_html=True)


# ---------- pages ----------

def page_runs() -> None:
    st.markdown('<div class="ag-title">Agent runs</div>'
                '<div class="ag-sub">Every request, tool call, argument, output and claim — stored as a graph in '
                'Neo4j Aura.</div>', unsafe_allow_html=True)
    df = runs()
    if df.empty:
        st.warning("No runs in the graph yet. Run `.\\run.ps1 load`.")
        return
    m = fleet()["metrics"]
    total, failed = len(df), int((~df["success"]).sum())
    kpis([("Runs recorded", str(total), "support agent · NorthPeak Outfitters"),
          ("Failed", str(failed), f"{failed / total:.0%} of runs"),
          ("Diagnosed", str(int(df["diagnosed_pattern"].notna().sum())), "root cause + evidence + fix"),
          ("Root-cause accuracy", f"{m.get('root_step_acc', 0):.0%}" if m else "—", "on labelled synthetic runs")])
    only_failed = st.toggle("Show failed runs only", value=True)
    view = df[~df["success"]] if only_failed else df
    view = view.assign(
        status=view["success"].map({True: "🟢 success", False: "🔴 failed"}),
        task=view["intent"].map(lambda i: INTENTS.get(i, i)),
        why=view["outcome"].map(humanize_outcome),
        diagnosis=view["diagnosed_pattern"].map(
            lambda c: f"{c} · {PATTERNS.get(c, (c, ''))[0]}" if isinstance(c, str) else "—"))
    st.dataframe(
        view[["run", "status", "task", "request", "why", "diagnosis"]], hide_index=True, width="stretch", height=420,
        column_config={"run": st.column_config.TextColumn("Run", width="small"),
                       "status": st.column_config.TextColumn("Status", width="small"),
                       "task": st.column_config.TextColumn("Task"),
                       "request": st.column_config.TextColumn("Customer request", width="large"),
                       "why": st.column_config.TextColumn("Why it failed"),
                       "diagnosis": st.column_config.TextColumn("Diagnosis")})
    ids = view["run"].tolist()
    c1, c2 = st.columns([3, 1])
    pick = c1.selectbox("Open a run", ids, index=ids.index("run_017") if "run_017" in ids else 0,
                        label_visibility="collapsed")
    if c2.button("Open run →", type="primary", width="stretch"):
        st.session_state["run"] = pick
        st.switch_page(DETAIL_PAGE)


def verdict_card(result: dict, tl: list[dict]) -> None:
    v, rules = result["verdict"], result.get("rules") or result["verdict"]
    step = next((s for s in tl if s["idx"] == v["root_step_idx"]), {})
    where = step.get("tool") or "final answer"
    conf = max(0.0, min(1.0, float(v["confidence"])))
    ev = {e["id"]: e for s in tl for e in (s.get("evidence") or [])}
    cited = "".join(
        f'<span class="ag-ev"><code>{esc(i)}</code> {esc(ev[i]["text"])}'
        + ('<span class="ag-stale">STALE</span>' if ev[i]["stale"] else "") + "</span>"
        for i in v.get("evidence_ids", []) if i in ev)
    symptoms = "".join(f'<span class="ag-chip">{esc(c.split("@")[0])} · {esc(PATTERNS.get(c.split("@")[0], ("", ""))[0])}'
                       f' @ step {esc(c.split("@")[1])}</span>' for c in v.get("contributing", []) if "@" in c)
    ai = ""
    if v.get("source") == "llm+rules" and v.get("explanation") and v["explanation"] != rules.get("explanation"):
        ai = (f'<div class="ag-ai"><b>AI summary</b> (gpt-4o-mini, constrained to graph-proven candidates)<br>'
              f'{esc(v["explanation"])}</div>')
    fleet_line = f'<div class="ag-callout">🌐 <b>Across the fleet:</b> {esc(result["fleet"])}</div>' \
        if result.get("fleet") else ""
    st.markdown(f"""
<div class="ag-verdict">
  <div class="top">{badge(v["pattern_code"])}
    <span class="ag-chip">confidence <b>{conf:.2f}</b> <span class="ag-conf"><i style="width:{conf * 100:.0f}%"></i></span></span>
    <span class="ag-chip">source: {esc(v["source"])}</span></div>
  <div class="root">Root cause → step {esc(v["root_step_idx"])} · {esc(where)}</div>
  <div class="ag-sec"><div class="h">Evidence trail (from graph queries)</div><div class="b">{esc(rules["explanation"])}</div></div>
  <div class="ag-sec"><div class="h">What it should have done</div><div class="b">✅ {esc(v["counterfactual"])}</div></div>
  <div class="ag-sec"><div class="h">Fix</div><div class="b">🛠 {esc(v["recommendation"])}</div></div>
  {'<div class="ag-sec"><div class="h">Symptoms after the root</div>' + symptoms + '</div>' if symptoms else ''}
  {'<div class="ag-sec"><div class="h">Cited evidence</div>' + cited + '</div>' if cited else ''}
  {fleet_line}{ai}
</div>""", unsafe_allow_html=True)


@st.dialog("Apply the fix?", width="large")
def confirm_fix(run_id: str, pattern: str) -> None:
    """Human-in-the-loop: nothing is changed until the user approves."""
    st.markdown(f'{badge(pattern)}', unsafe_allow_html=True)
    st.markdown(f"**Guardrail to apply:** {GUARDRAILS[pattern]}")
    st.markdown("AutopsyGraph will **re-run the agent on the same customer request with this guardrail**, write the "
                "replay to Neo4j as a separate run linked to the original (`REPLAY_OF`), and re-check it with the "
                "same 9 detectors. **The original run is not modified.**")
    c1, c2 = st.columns(2)
    if c1.button("✅ Approve & re-run", type="primary", width="stretch"):
        with st.spinner("Re-running the agent with the guardrail and re-checking it…"):
            st.session_state[f"replay_{run_id}"] = apply_fix(run_id, pattern)
        st.rerun()
    if c2.button("Cancel", width="stretch"):
        st.rerun()


def replay_card(fixed: dict) -> None:
    ok = fixed["success"] and not fixed["decisive_hits"]
    facts = "".join(f'<span class="ag-chip">{"✅" if c["verdict"] == "match" else "❌"} <code>{esc(c["fact"])}</code> = '
                    f'{esc(c["asserted"])}</span>' for c in fixed["claims"])
    head = ("✅ Fixed — the replay passes" if ok else "⚠️ The replay still fails")
    sub = ("All expected facts match, no forbidden actions, 0 decisive detector hits." if ok else
           "; ".join(fixed["reasons"]) or "Detectors still flag decisive steps.")
    st.markdown(f'<div class="ag-fixed {"" if ok else "ag-fixed-bad"}"><div class="t">{head}</div>'
                f'<div class="s">{esc(sub)}</div><div class="ag-sec"><div class="h">Guardrail applied</div>'
                f'<div class="b">🛠 {esc(fixed["guardrail"])}</div></div>'
                f'<div class="ag-sec"><div class="h">Replay run <code>{esc(fixed["run"])}</code> · claims</div>{facts}'
                f'</div></div>', unsafe_allow_html=True)
    st.markdown(svg_timeline(timeline(fixed["run"]), claims(fixed["run"]), None), unsafe_allow_html=True)


def page_detail() -> None:
    df = runs()
    ids = df["run"].tolist()
    cur = st.session_state.get("run", "run_017")
    top_l, top_r = st.columns([3, 1])
    run_id = top_r.selectbox("Run", ids, index=ids.index(cur) if cur in ids else 0)
    st.session_state["run"] = run_id
    h, tl, cl = header(run_id), timeline(run_id), claims(run_id)
    pill = '<span class="ag-pill ag-ok">● success</span>' if h.get("success") else \
        '<span class="ag-pill ag-bad">● failed</span>'
    top_l.markdown(f'<div class="ag-title">{esc(run_id)} {pill}</div>'
                   f'<div class="ag-sub">{esc(INTENTS.get(h.get("intent"), h.get("intent")))} · '
                   f'{len([s for s in tl if s["kind"] == "tool"])} tool calls</div>', unsafe_allow_html=True)
    key = f"verdict_{run_id}"
    result = st.session_state.get(key)
    verdict = result["verdict"] if result else None

    st.markdown(svg_timeline(tl, cl, verdict), unsafe_allow_html=True)
    left, right = st.columns([5, 7], gap="large")
    with left:
        st.markdown('<div class="ag-legend" style="margin:.5rem 0 1rem 0">'
                    '<span><i style="background:#FDECEC;border-color:#E5484D"></i>root cause</span>'
                    '<span><i style="background:#FFF4E0;border-color:#F5A524"></i>symptom</span>'
                    '<span><i style="background:#EEF6FF;border-color:#0090FF"></i>evidence</span>'
                    '<span><i style="background:#FFF5F5;border-color:#E5484D"></i>stale evidence</span>'
                    '<span><i style="background:#F3E8FF;border-color:#8E4EC6"></i>ground truth</span>'
                    '<span><i style="background:#F2FBF5;border-color:#2EAA5C"></i>should have done</span>'
                    '</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ag-card"><div class="h">Customer asked</div>'
                    f'<div class="ag-quote">“{esc(h.get("request"))}”</div></div>'
                    f'<div class="ag-card"><div class="h">Agent answered</div>'
                    f'<div class="ag-quote">“{esc(h.get("answer"))}”</div></div>', unsafe_allow_html=True)
        rows = "".join(
            f'<tr><td><code>{esc(c["fact"])}</code></td><td>{esc(c["expected"])}</td>'
            f'<td>{esc(c["asserted"] if c["asserted"] is not None else "—")}</td>'
            f'<td>{"✅" if c["verdict"] == "match" else "❌ " + esc(c["verdict"])}'
            f'{" <span class=ag-stale>STALE</span>" if c["stale"] else ""}</td></tr>' for c in cl)
        st.markdown(f'<div class="ag-card"><div class="h">Claims vs ground truth</div>'
                    f'<table style="width:100%;font-size:.9rem"><tr style="color:#5B6170"><td>fact</td><td>truth</td>'
                    f'<td>agent said</td><td></td></tr>{rows}</table></div>', unsafe_allow_html=True)
    with right:
        if not h.get("success"):
            if st.button("🔍  Investigate this run", type="primary", width="stretch"):
                with st.spinner("Running 9 graph detectors, first-divergence and the judge…"):
                    st.session_state[key] = investigate(run_id)
                st.rerun()
            if result:
                verdict_card(result, tl)
                pattern = result["verdict"]["pattern_code"]
                fixed = st.session_state.get(f"replay_{run_id}")
                if pattern in GUARDRAILS and not fixed:
                    if st.button("🛠  Apply fix & re-run", width="stretch"):
                        confirm_fix(run_id, pattern)
                if fixed:
                    replay_card(fixed)
        else:
            st.success("This run succeeded — every expected fact matches the ground truth.")


def page_fleet() -> None:
    st.markdown('<div class="ag-title">Fleet</div>'
                '<div class="ag-sub">Recurring failures across every run — one Cypher query each.</div>',
                unsafe_allow_html=True)
    f = fleet()
    ign, m = f["ignored"], f["metrics"]
    if ign:
        t = ign[0]
        st.markdown(f'<div class="ag-fleet"><div class="big"><span>{t["runs_ignoring_it"]}</span> of '
                    f'{t["runs_with_error"]}</div><div class="l"><b>{esc(t["tool"])}</b> returned '
                    f'<b>{esc(t["error"])}</b> in {t["runs_with_error"]} runs — the agent silently ignored it in '
                    f'{t["runs_ignoring_it"]}. One guardrail removes the whole class.</div></div>',
                    unsafe_allow_html=True)
    if m:
        kpis([("Root-step accuracy", f"{m['root_step_acc']:.0%}", f"{m['n']} labelled synthetic failures"),
              ("Pattern accuracy", f"{m['pattern_acc']:.0%}", "injected pattern recovered"),
              ("Patterns diagnosed", str(len(f["patterns"])), "of 14 in the taxonomy"),
              ("LLM role", "narrow", "picks among graph-proven candidates")])
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Failures by pattern")
        pats = pd.DataFrame(f["patterns"])
        if not pats.empty:
            pats["pattern"] = pats["code"] + " · " + pats["name"]
            st.bar_chart(pats.set_index("pattern")["runs"], color="#E5484D", horizontal=True, height=260)
        else:
            st.caption("No diagnoses yet — run `.\\run.ps1 detect`.")
        if m:
            st.subheader("Accuracy per pattern")
            acc = pd.DataFrame(m["per_pattern"]).T.reset_index().rename(columns={"index": "pattern"})
            acc["pattern"] = acc["pattern"].map(lambda c: f"{c} · {PATTERNS.get(c, (c, ''))[0]}")
            st.dataframe(acc, hide_index=True, width="stretch",
                         column_config={"root_step_acc": st.column_config.ProgressColumn(
                                            "root step", min_value=0, max_value=1, format="percent"),
                                        "pattern_acc": st.column_config.ProgressColumn(
                                            "pattern", min_value=0, max_value=1, format="percent")})
    with right:
        st.subheader("Tools")
        tools = pd.DataFrame(f["tools"])
        if not tools.empty:
            st.dataframe(tools, hide_index=True, width="stretch",
                         column_config={"error_pct": st.column_config.ProgressColumn(
                             "error %", min_value=0, max_value=100, format="%.0f%%")})
        st.subheader("Ignored errors")
        st.dataframe(pd.DataFrame(ign), hide_index=True, width="stretch")


# ---------- layout ----------

RUNS_PAGE = st.Page(page_runs, title="Runs", icon="📋", default=True)
DETAIL_PAGE = st.Page(page_detail, title="Run detail", icon="🔍", url_path="run")
FLEET_PAGE = st.Page(page_fleet, title="Fleet", icon="🌐", url_path="fleet")
nav = st.navigation([RUNS_PAGE, DETAIL_PAGE, FLEET_PAGE], position="top")
live = ('<span class="ag-live"><i></i>Live on Neo4j Aura</span>' if aura_ok() else
        '<span class="ag-pill ag-bad">● Aura unreachable</span>')
st.markdown(f'<div class="ag-hero"><div class="ag-hero-in"><div class="ag-brand">🩻 <span>AutopsyGraph</span></div>'
            f'<div class="ag-tag">Every failed agent run leaves evidence. We follow it.</div></div>'
            f'<div class="ag-hero-r">{live}<span class="ag-event">Graphs Gone Wild · NODES 2026</span></div></div>',
            unsafe_allow_html=True)
nav.run()
st.markdown(f'<div class="ag-foot">{esc(FOOTER)}</div>', unsafe_allow_html=True)
