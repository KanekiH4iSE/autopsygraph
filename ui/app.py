"""AutopsyGraph UI: Runs, Run detail (timeline graph + Investigate), Fleet.  Run: streamlit run ui/app.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from forensics import engine  # noqa: E402
from forensics.claims import all_runs, claim_verdicts  # noqa: E402

st.set_page_config(page_title="AutopsyGraph", page_icon="🩻", layout="wide")
FOOTER = ("We analyse observable agent behaviour only. Diagnoses are root-cause candidates, "
          "measured on synthetic labelled runs.")


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


def _esc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace('"', "'")


def dot(tl: list[dict], cl: list[dict], verdict: dict | None) -> str:
    """Left-to-right timeline. Grey = normal, amber = flagged, red = root cause, blue = evidence,
    green/purple = answer vs ground truth, dashed = what the agent should have done."""
    root = verdict["root_step_idx"] if verdict else None
    flagged = {int(c.split("@")[1]) for c in (verdict or {}).get("contributing", [])
               if "@" in c and c.split("@")[1].isdigit()}
    cited = set((verdict or {}).get("evidence_ids", []))
    out = ['digraph G { rankdir=LR; bgcolor="transparent"; nodesep=0.35; ranksep=0.45;',
           'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#666666"];',
           'edge [color="#888888", fontname="Helvetica", fontsize=9];']
    for s in tl:
        if s["kind"] == "answer":
            ok = all(c["verdict"] == "match" for c in cl) if cl else True
            out.append(f'S{s["idx"]} [label="{s["idx"]} · ANSWER", fillcolor="{"#c8e6c9" if ok else "#ffcdd2"}"];')
            continue
        status = (s.get("error") or s.get("status") or "").upper()
        label = f'{s["idx"]} · {s["tool"]}\\n→ {status}'
        args = ", ".join(f'{a["name"]}={a["value"]}' for a in s.get("args") or [])
        if args:
            label += f'\\n{_esc(args)[:46]}'
        if s["idx"] == root:
            fill, pen = "#ef5350", 3
        elif s["idx"] in flagged:
            fill, pen = "#ffcc80", 1.5
        else:
            fill, pen = "#eeeeee", 1
        out.append(f'S{s["idx"]} [label="{label}", fillcolor="{fill}", penwidth={pen}];')
        for e in s.get("evidence") or []:
            txt = _esc(e["text"])[:44] + (" [STALE]" if e["stale"] else "")
            col = "#1565c0" if e["id"] in cited else "#90caf9"
            out.append(f'"{e["id"]}" [label="{txt}", shape=note, fillcolor="#e3f2fd", color="{col}", fontsize=9];')
            out.append(f'S{s["idx"]} -> "{e["id"]}" [style=dotted, arrowhead=none];')
    for a, b in zip(tl, tl[1:]):
        out.append(f'S{a["idx"]} -> S{b["idx"]} [penwidth=2];')
    ans = next((s["idx"] for s in tl if s["kind"] == "answer"), None)
    for i, c in enumerate(cl):
        out.append(f'GT{i} [label="ground truth\\n{c["fact"]} = {c["expected"]}", fillcolor="#e1bee7"];')
        if ans:
            lab = f'said {c["asserted"]}' if c["asserted"] is not None else "missing"
            col = "#2e7d32" if c["verdict"] == "match" else "#c62828"
            out.append(f'S{ans} -> GT{i} [label="{_esc(lab)}", color="{col}"];')
    if verdict and root:
        out.append(f'GHOST [label="expected:\\n{_esc(verdict["counterfactual"])[:60]}", style="dashed,rounded", '
                   f'fillcolor="white", fontcolor="#555555"];')
        out.append(f'S{root} -> GHOST [style=dashed, color="#c62828"];')
    out.append("}")
    return "\n".join(out)


def page_runs() -> None:
    st.title("Runs")
    df = runs()
    if df.empty:
        st.warning("No runs in the graph. Run `.\\run.ps1 load`.")
        return
    total, failed = len(df), int((~df["success"]).sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Runs recorded", total)
    c2.metric("Failed", failed)
    c3.metric("Diagnosed", int(df["diagnosed_pattern"].notna().sum()))
    only_failed = st.toggle("Failed runs only", value=True)
    view = df[~df["success"]] if only_failed else df
    view = view.assign(status=view["success"].map({True: "🟢 success", False: "🔴 failed"}))
    st.dataframe(view[["run", "status", "intent", "request", "outcome"]], hide_index=True, use_container_width=True)
    ids = view["run"].tolist()
    pick = st.selectbox("Open run", ids, index=ids.index("run_017") if "run_017" in ids else 0)
    if st.button("Open in Run detail", type="primary"):
        st.session_state["run"] = pick
        st.session_state["nav"] = "Run detail"
        st.rerun()


def page_detail() -> None:
    df = runs()
    ids = df["run"].tolist()
    cur = st.session_state.get("run", "run_017")
    run_id = st.selectbox("Run", ids, index=ids.index(cur) if cur in ids else 0)
    st.session_state["run"] = run_id
    h, tl, cl = header(run_id), timeline(run_id), claims(run_id)
    verdict_key = f"verdict_{run_id}"
    result = st.session_state.get(verdict_key)
    verdict = result["verdict"] if result else None

    st.title(f"{run_id} · {'🟢 success' if h.get('success') else '🔴 failed'}")
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Timeline")
        st.graphviz_chart(dot(tl, cl, verdict), use_container_width=True)
        st.caption("grey = step · amber = contributing · red = root cause · blue = evidence (dark = cited) · "
                   "purple = ground truth · dashed = what should have happened")
    with right:
        st.markdown(f"**User request**  \n> {h.get('request')}")
        st.markdown(f"**Final answer**  \n> {h.get('answer')}")
        st.markdown("**Claims vs ground truth**")
        st.dataframe(pd.DataFrame([{"fact": c["fact"], "expected": c["expected"], "agent said": c["asserted"],
                                    "verdict": c["verdict"], "stale evidence": c["stale"]} for c in cl]),
                     hide_index=True, use_container_width=True)
        if not h.get("success"):
            if st.button("🔍 Investigate", type="primary", use_container_width=True):
                with st.spinner("Running graph detectors and the judge…"):
                    st.session_state[verdict_key] = investigate(run_id)
                st.rerun()
        if verdict:
            st.error(f"**{verdict['pattern_code']} · root cause at step {verdict['root_step_idx']}** · "
                     f"confidence {verdict['confidence']:.2f} · source: {verdict['source']}")
            st.markdown(f"**What happened / why**  \n{verdict['explanation']}")
            st.markdown(f"**What it should have done**  \n{verdict['counterfactual']}")
            st.markdown(f"**Fix**  \n{verdict['recommendation']}")
            if verdict.get("contributing"):
                st.markdown("**Symptoms after the root:** " + ", ".join(verdict["contributing"]))
            ev = {e["id"]: e for s in tl for e in (s.get("evidence") or [])}
            cited = [ev[i] for i in verdict.get("evidence_ids", []) if i in ev]
            if cited:
                st.markdown("**Cited evidence**")
                for e in cited:
                    st.markdown(f"- `{e['id']}` {e['text']}" + (" — **STALE**" if e["stale"] else ""))
            if result.get("fleet"):
                st.info(f"Across the fleet: {result['fleet']}")
        elif h.get("success"):
            st.success("Run succeeded: all expected facts match.")


def page_fleet() -> None:
    st.title("Fleet")
    ign = engine.fleet_ignored_errors()
    if ign:
        top = ign[0]
        st.metric(f"{top['tool']} · {top['error']}",
                  f"ignored in {top['runs_ignoring_it']} of {top['runs_with_error']} runs")
    m = engine.metrics()
    if m:
        c1, c2 = st.columns(2)
        c1.metric("Root-step accuracy (synthetic, labelled)", f"{m['root_step_acc']:.0%}", f"{m['n']} failed runs",
                  delta_color="off")
        c2.metric("Pattern accuracy", f"{m['pattern_acc']:.0%}", delta_color="off")
    left, right = st.columns(2)
    with left:
        st.subheader("Failures by pattern")
        pats = pd.DataFrame(engine.fleet_patterns())
        if not pats.empty:
            st.bar_chart(pats.assign(pattern=pats["code"] + " " + pats["name"]).set_index("pattern")["runs"])
        else:
            st.caption("No diagnoses yet — run `.\\run.ps1 detect`.")
    with right:
        st.subheader("Tools")
        st.dataframe(pd.DataFrame(engine.fleet_tools()), hide_index=True, use_container_width=True)
        st.subheader("Ignored errors")
        st.dataframe(pd.DataFrame(ign), hide_index=True, use_container_width=True)
    if m:
        with st.expander("Accuracy per pattern"):
            st.dataframe(pd.DataFrame(m["per_pattern"]).T, use_container_width=True)


PAGES = {"Runs": page_runs, "Run detail": page_detail, "Fleet": page_fleet}
if "nav" in st.session_state:
    st.session_state["page"] = st.session_state.pop("nav")
st.sidebar.title("🩻 AutopsyGraph")
st.sidebar.caption("Every failed agent run leaves evidence. We follow it.")
page = st.sidebar.radio("Page", list(PAGES), key="page")
PAGES[page]()
st.divider()
st.caption(FOOTER)
