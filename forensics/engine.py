"""Forensic engine: detectors -> first divergence -> claims -> rules verdict -> judge -> :Diagnosis write-back.

Read-only on trace data except `flags`/`severity` on flagged steps and the Diagnosis nodes it owns.
Usage: python -m forensics.engine            (investigate all failed runs)
"""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from forensics.claims import claim_verdicts, failed_runs
from forensics.detectors import run_all
from forensics.divergence import find_root
from forensics.judge import judge, rules_verdict
from graph.db import read, write

ROOT = Path(__file__).resolve().parent.parent


def timeline(run_id: str) -> list[dict]:
    """Ordered steps with tool, args, status, error, evidence and stored flags."""
    return read("""
        MATCH (:ReasoningTrace {id: $run_id})-[:HAS_STEP]->(st:ReasoningStep)
        OPTIONAL MATCH (st)-[:USES_TOOL]->(tc:ToolCall)
        OPTIONAL MATCH (tc)-[:RETURNED]->(o:Observation)
        OPTIONAL MATCH (o)-[:RAISED]->(err:Error)
        CALL (tc) { OPTIONAL MATCH (tc)-[:HAS_ARG]->(a:Argument)
                    RETURN collect(CASE WHEN a IS NULL THEN NULL
                                   ELSE {name: a.name, value: a.value, valid: a.valid} END) AS args }
        CALL (st) { OPTIONAL MATCH (st)-[:CITES]->(ev:Evidence)
                    RETURN collect(CASE WHEN ev IS NULL THEN NULL
                                   ELSE {id: ev.id, text: ev.text, stale: ev.stale} END) AS evidence }
        RETURN st.idx AS idx, st.kind AS kind, st.thought AS thought, tc.tool_name AS tool, tc.status AS status,
               tc.attempt AS attempt, tc.latency_ms AS latency_ms, o.summary AS summary, err.code AS error,
               err.retryable AS retryable, args, evidence, coalesce(st.flags, []) AS flags, st.severity AS severity
        ORDER BY idx""", run_id=run_id)


def run_header(run_id: str) -> dict:
    """Request, answer, outcome and task for one run (label excluded)."""
    rows = read("""
        MATCH (r:ReasoningTrace {id: $run_id})-[:FOR_TASK]->(t:Task)
        OPTIONAL MATCH (r)-[:STARTED_BY]->(u:UserRequest)
        OPTIONAL MATCH (r)-[:PRODUCED]->(a:Answer)
        RETURN r.id AS run, t.id AS task, t.intent AS intent, r.success AS success, r.outcome AS outcome,
               u.text AS request, a.text AS answer, a.acknowledges_limitation AS ack""", run_id=run_id)
    return rows[0] if rows else {}


def _fixes() -> dict[str, str]:
    return {r["code"]: r["fix"] for r in read("MATCH (p:FailurePattern) RETURN p.code AS code, p.fix_template AS fix")}


def fleet_context(pattern: str | None, tool: str | None) -> str:
    """One line of cross-run context for a verdict."""
    if pattern == "FP04" and tool:
        rows = read("""
            MATCH (r:ReasoningTrace)-[:HAS_STEP]->(st)-[:USES_TOOL]->(tc:ToolCall {tool_name: $tool})
                  -[:RETURNED]->(:Observation)-[:RAISED]->(:Error)
            WHERE r.replay_of IS NULL
            MATCH (r)-[:PRODUCED]->(ans:Answer)
            WITH r, st, tc, ans,
                 EXISTS { MATCH (r)-[:HAS_STEP]->(l)-[:USES_TOOL]->(tc2)
                          WHERE l.idx > st.idx AND ((tc2.tool_name = tc.tool_name AND tc2.status = 'ok')
                                OR tc2.tool_name = 'escalate_to_human') }
                 OR coalesce(ans.acknowledges_limitation, false) AS handled
            RETURN count(DISTINCT r) AS failed_in, count(DISTINCT CASE WHEN NOT handled THEN r END) AS ignored_in""",
                    tool=tool)
        if rows:
            return f"{tool} errored in {rows[0]['failed_in']} runs; the agent ignored it in {rows[0]['ignored_in']}."
    if pattern:
        rows = read("""
            MATCH (d:Diagnosis {pattern_code: $p}) RETURN count(d) AS n""", p=pattern)
        n = rows[0]["n"] if rows else 0
        return f"{n} diagnosed runs share pattern {pattern}."
    return ""


_WRITE_LOCK = threading.Lock()


def _write_diagnosis(run_id: str, v, hits) -> None:
    # Reads run in parallel; writes are serialised so concurrent runs never deadlock on shared FailurePattern nodes.
    with _WRITE_LOCK:
        _write_diagnosis_locked(run_id, v, hits)


def _write_diagnosis_locked(run_id: str, v, hits) -> None:
    write("MATCH (:ReasoningTrace {id: $run_id})-[:HAS_STEP]->(st:ReasoningStep) REMOVE st.flags, st.severity",
          run_id=run_id)
    flags: dict[int, dict] = {}
    for h in hits:
        f = flags.setdefault(h.step_idx, {"idx": h.step_idx, "flags": [], "severity": 0})
        f["flags"].append(h.pattern)
        f["severity"] = max(f["severity"], h.severity)
    write("""
        UNWIND $rows AS f
        MATCH (st:ReasoningStep {run_id: $run_id, idx: f.idx})
        SET st.flags = f.flags, st.severity = f.severity""", run_id=run_id, rows=list(flags.values()))
    write("""
        MATCH (r:ReasoningTrace {id: $run_id})
        OPTIONAL MATCH (r)-[:HAS_DIAGNOSIS]->(old:Diagnosis) DETACH DELETE old
        WITH r
        MERGE (d:Diagnosis {id: 'dx_' + $run_id})
        SET d.pattern_code = $v.pattern_code, d.root_step_idx = $v.root_step_idx, d.confidence = $v.confidence,
            d.explanation = $v.explanation, d.counterfactual = $v.counterfactual,
            d.recommendation = $v.recommendation, d.source = $v.source, d.contributing = $v.contributing,
            d.disagrees_with_rules = $v.disagrees_with_rules
        MERGE (r)-[:HAS_DIAGNOSIS]->(d)
        WITH r, d
        MATCH (r)-[:HAS_STEP]->(st:ReasoningStep {idx: $v.root_step_idx})
        MERGE (d)-[:ROOT_CAUSE]->(st)
        WITH d
        OPTIONAL MATCH (p:FailurePattern {code: $v.pattern_code})
        FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (d)-[:CLASSIFIED_AS]->(p))
        WITH d
        UNWIND (CASE WHEN size($v.evidence_ids) = 0 THEN [null] ELSE $v.evidence_ids END) AS eid
        OPTIONAL MATCH (ev:Evidence {id: eid})
        FOREACH (_ IN CASE WHEN ev IS NULL THEN [] ELSE [1] END | MERGE (d)-[:CITES_EVIDENCE]->(ev))""",
          run_id=run_id, v=v.model_dump())


def investigate(run_id: str, use_cache: bool = True, fixes: dict | None = None) -> dict:
    """Full investigation of one run; writes the Diagnosis and returns verdict + context for the UI."""
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_tl, f_head = pool.submit(timeline, run_id), pool.submit(run_header, run_id)
        f_hits, f_claims = pool.submit(run_all, run_id), pool.submit(claim_verdicts, run_id)
        tl, header, hits, claims = f_tl.result(), f_head.result(), f_hits.result(), f_claims.result()
    root = find_root(hits)
    rules = rules_verdict(tl, root, claims, fixes or _fixes())
    if rules is None:
        return {"run": run_id, "verdict": None, "hits": [], "claims": claims, "fleet": ""}
    verdict = judge(run_id, tl, header.get("answer") or "", hits, claims, rules, use_cache=use_cache)
    _write_diagnosis(run_id, verdict, hits)
    root_tool = next((s["tool"] for s in tl if s["idx"] == verdict.root_step_idx), None)
    return {"run": run_id, "verdict": verdict.model_dump(), "rules": rules.model_dump(),
            "hits": [h.as_dict() for h in hits], "claims": claims,
            "fleet": fleet_context(verdict.pattern_code, root_tool)}


def investigate_all(use_cache: bool = True) -> list[dict]:
    fixes = _fixes()
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(lambda r: investigate(r, use_cache=use_cache, fixes=fixes), failed_runs()))


# ---------- fleet queries ----------

def fleet_patterns() -> list[dict]:
    return read("""
        MATCH (d:Diagnosis)-[:CLASSIFIED_AS]->(p:FailurePattern)
        RETURN p.code AS code, p.name AS name, count(d) AS runs ORDER BY runs DESC, code""")


def fleet_tools() -> list[dict]:
    return read("""
        MATCH (r:ReasoningTrace)-[:HAS_STEP]->()-[:USES_TOOL]->(tc:ToolCall)-[:INSTANCE_OF]->(t:Tool)
        WHERE r.replay_of IS NULL
        WITH t, count(tc) AS calls,
             sum(CASE WHEN tc.status IN ['error', 'timeout'] THEN 1 ELSE 0 END) AS failed_calls,
             count(DISTINCT CASE WHEN r.success = false THEN r END) AS failed_runs
        RETURN t.name AS tool, calls, failed_calls, round(100.0 * failed_calls / calls, 1) AS error_pct, failed_runs
        ORDER BY error_pct DESC, failed_runs DESC""")


def fleet_ignored_errors() -> list[dict]:
    return read("""
        MATCH (r:ReasoningTrace)-[:HAS_STEP]->(st)-[:USES_TOOL]->(tc)-[:RETURNED]->(:Observation)-[:RAISED]->(err:Error)
        WHERE r.replay_of IS NULL
        MATCH (r)-[:PRODUCED]->(ans:Answer)
        WITH tc.tool_name AS tool, err.code AS error, r,
             NOT (EXISTS { MATCH (r)-[:HAS_STEP]->(l)-[:USES_TOOL]->(tc2)
                           WHERE l.idx > st.idx AND ((tc2.tool_name = tc.tool_name AND tc2.status = 'ok')
                                 OR tc2.tool_name = 'escalate_to_human') }
                  OR coalesce(ans.acknowledges_limitation, false)) AS ignored
        RETURN tool, error, count(DISTINCT r) AS runs_with_error,
               count(DISTINCT CASE WHEN ignored THEN r END) AS runs_ignoring_it
        ORDER BY runs_ignoring_it DESC""")


def metrics() -> dict:
    f = ROOT / "data" / "metrics.json"
    return json.loads(f.read_text()) if f.exists() else {}


if __name__ == "__main__":
    results = investigate_all()
    by = {}
    for r in results:
        v = r["verdict"]
        key = (v["pattern_code"], v["source"]) if v else ("none", "-")
        by[key] = by.get(key, 0) + 1
    print(f"diagnosed {len(results)} failed runs:", by)
