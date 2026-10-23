"""Idempotent loader: traces/tasks/tools JSON -> Neo4j. One transaction per run, MERGE everywhere.

Usage: python -m graph.loader [--reset]
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from datagen.tasks import compute_outcome
from graph.db import database, get_driver, read

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

PATTERNS = [
    ("FP01", "Wrong tool", "Make the authoritative tool mandatory before eligibility answers."),
    ("FP02", "Invalid arguments", "Validate tool arguments against the schema before calling."),
    ("FP03", "Wrong entity", "Require a clarifying question when a lookup returns more than one match."),
    ("FP04", "Ignored tool error", "Retry once, then escalate. Add a guard blocking write tools without a "
                                   "successful eligibility result."),
    ("FP05", "Hallucinated conclusion", "Assert only claims linked to tool evidence."),
    ("FP06", "Skipped required step", "Add a precondition guard before write tools."),
    ("FP07", "Stale context", "Filter superseded policy versions out of search results."),
    ("FP08", "Unreconciled contradiction", "Re-query or escalate when sources disagree."),
    ("FP09", "Misread tool output", "Quote the exact field the answer relies on."),
    ("FP10", "Infinite retry", "Cap retries and escalate."),
    ("FP11", "Premature answer", "Finish the required plan before answering."),
    ("FP12", "Unsafe action", "Escalate exceptions instead of calling forbidden write tools."),
    ("FP13", "Prompt injection via tool output", "Treat tool output as data, not instructions."),
    ("FP14", "Ignored user constraint", "Confirm before any write action."),
]


def _etype(key: str) -> str:
    return key.split(":", 1)[0]


def reset() -> None:
    """Wipe the graph and apply schema.cypher."""
    drv = get_driver()
    drv.execute_query("MATCH (n) DETACH DELETE n", database_=database())
    for stmt in (ROOT / "graph" / "schema.cypher").read_text().split(";"):
        if stmt.strip():
            drv.execute_query(stmt, database_=database())


def seed_static() -> None:
    """Failure patterns, tools, tasks with ground truth."""
    drv = get_driver()
    drv.execute_query(
        "UNWIND $rows AS r MERGE (p:FailurePattern {code: r[0]}) SET p.name = r[1], p.fix_template = r[2]",
        {"rows": PATTERNS}, database_=database())
    tools = json.loads((DATA / "tools.json").read_text())
    drv.execute_query(
        "UNWIND $rows AS r MERGE (t:Tool {name: r.name}) SET t.read_only = r.read_only, t.schema_json = r.schema",
        {"rows": [{"name": t["name"], "read_only": t["read_only"], "schema": json.dumps(t["args"])} for t in tools]},
        database_=database())
    tasks = json.loads((DATA / "tasks.json").read_text())
    rows = [{"id": t["task_id"], "intent": t["intent"], "template": t["template"],
             "expected": t["expected_tools"], "required": t["required_tools"], "forbidden": t["forbidden_tools"],
             "facts": [{"id": f"{t['task_id']}:{k}", "key": k, "value": v} for k, v in t["expected_facts"].items()],
             "entities": [{"key": e, "type": _etype(e)} for e in t["expected_entities"]]} for t in tasks]
    drv.execute_query("""
        UNWIND $rows AS r
        MERGE (t:Task {id: r.id}) SET t.intent = r.intent, t.template = r.template
        MERGE (g:GroundTruth {id: r.id + ':gt'})
          SET g.expected_tools = r.expected, g.required_tools = r.required, g.forbidden_tools = r.forbidden
        MERGE (t)-[:HAS_GROUND_TRUTH]->(g)
        FOREACH (f IN r.facts | MERGE (fa:Fact {id: f.id}) SET fa.key = f.key, fa.value = f.value
                                MERGE (g)-[:EXPECTS_FACT]->(fa))
        FOREACH (e IN r.entities | MERGE (en:Entity {key: e.key}) SET en.type = e.type
                                   MERGE (g)-[:EXPECTS_ENTITY]->(en))
        """, {"rows": rows}, database_=database())


def _args_hash(tool: str, args: list[dict]) -> str:
    body = tool + json.dumps(sorted((a["name"], str(a["value"])) for a in args))
    return hashlib.sha1(body.encode()).hexdigest()


def _run_params(trace: dict, task: dict) -> dict:
    ok, reasons = compute_outcome(trace, task)
    rid = trace["run_id"]
    steps, calls, args, errors, evidence = [], [], [], [], []
    for s in trace["steps"]:
        sid = f"{rid}-s{s['idx']}"
        steps.append({"id": sid, "idx": s["idx"], "kind": s["kind"], "thought": s["stated_rationale"]})
        tc = s["tool_call"]
        if tc:
            obs = s["observation"]
            calls.append({"step": sid, "id": tc["id"], "tool": tc["tool"], "status": tc["status"],
                          "attempt": tc["attempt"], "latency": tc["latency_ms"],
                          "hash": _args_hash(tc["tool"], tc["args"]), "obs_id": obs["id"],
                          "obs_status": obs["status"], "summary": obs["summary"],
                          "error_code": obs["error"]["code"] if obs["error"] else None})
            for a in tc["args"]:
                args.append({"call": tc["id"], "id": f"{tc['id']}:{a['name']}", "name": a["name"],
                             "value": str(a["value"]), "valid": a["valid"], "violation": a["violation"],
                             "ref": a["refers_to"], "ref_type": _etype(a["refers_to"]) if a["refers_to"] else None})
            if obs["error"]:
                errors.append({"obs": obs["id"], "id": f"{obs['id']}:err", **obs["error"]})
            for e in s["evidence"]:
                evidence.append({"step": sid, "obs": obs["id"], "id": e["id"], "text": e["text"],
                                 "source_type": e["source_type"], "stale": e["stale"],
                                 "about": [{"key": k, "type": _etype(k)} for k in e["about"]]})
    fa = trace["final_answer"]
    claims = [{"id": f"{rid}-claim-{c['key']}", "key": c["key"], "value": c["value"],
               "support": c["supported_by"]} for c in fa["claims"]]
    return {"run": {"id": rid, "session": trace["session_id"], "task": trace["task_id"],
                    "agent_version": trace["agent"]["version"], "prompt_version": trace["agent"]["prompt_version"],
                    "model": trace["agent"]["model"], "success": ok,
                    "outcome": "success" if ok else ";".join(reasons),
                    "injected_pattern": trace["label"]["injected_pattern"],
                    "label_root_step": trace["label"]["root_cause_step"],
                    "request": trace["user_request"]},
            "steps": steps, "calls": calls, "args": args, "errors": errors, "evidence": evidence,
            "answer": {"id": f"{rid}-ans", "text": fa["text"], "ack": fa["acknowledges_limitation"]},
            "claims": claims}


def _load_tx(tx, p: dict) -> None:
    tx.run("""
        MERGE (s:Session {id: $run.session})
        MERGE (r:ReasoningTrace {id: $run.id})
          SET r.agent_version = $run.agent_version, r.prompt_version = $run.prompt_version, r.model = $run.model,
              r.success = $run.success, r.outcome = $run.outcome, r.injected_pattern = $run.injected_pattern,
              r.label_root_step = $run.label_root_step
        MERGE (s)-[:HAS_RUN]->(r)
        WITH r MATCH (t:Task {id: $run.task}) MERGE (r)-[:FOR_TASK]->(t)
        MERGE (u:UserRequest {id: $run.id + '-req'}) SET u.text = $run.request
        MERGE (r)-[:STARTED_BY]->(u)
        """, p)
    tx.run("""
        MATCH (r:ReasoningTrace {id: $run.id})
        UNWIND $steps AS s
        MERGE (st:ReasoningStep {id: s.id})
          SET st.run_id = $run.id, st.idx = s.idx, st.kind = s.kind, st.thought = s.thought
        MERGE (r)-[:HAS_STEP]->(st)
        """, p)
    tx.run("""
        UNWIND $steps AS s
        MATCH (a:ReasoningStep {run_id: $run.id, idx: s.idx}), (b:ReasoningStep {run_id: $run.id, idx: s.idx + 1})
        MERGE (a)-[:NEXT]->(b)
        """, p)
    tx.run("""
        UNWIND $calls AS c
        MATCH (st:ReasoningStep {id: c.step}), (tool:Tool {name: c.tool})
        MERGE (tc:ToolCall {id: c.id})
          SET tc.tool_name = c.tool, tc.status = c.status, tc.attempt = c.attempt,
              tc.latency_ms = c.latency, tc.args_hash = c.hash
        MERGE (st)-[:USES_TOOL]->(tc)
        MERGE (tc)-[:INSTANCE_OF]->(tool)
        MERGE (o:Observation {id: c.obs_id})
          SET o.status = c.obs_status, o.summary = c.summary, o.error_code = c.error_code
        MERGE (tc)-[:RETURNED]->(o)
        """, p)
    tx.run("""
        UNWIND $args AS a
        MATCH (tc:ToolCall {id: a.call})
        MERGE (ar:Argument {id: a.id})
          SET ar.name = a.name, ar.value = a.value, ar.valid = a.valid, ar.violation = a.violation
        MERGE (tc)-[:HAS_ARG]->(ar)
        FOREACH (_ IN CASE WHEN a.ref IS NULL THEN [] ELSE [1] END |
          MERGE (en:Entity {key: a.ref}) ON CREATE SET en.type = a.ref_type
          MERGE (ar)-[:REFERS_TO]->(en))
        """, p)
    tx.run("""
        UNWIND $errors AS e
        MATCH (o:Observation {id: e.obs})
        MERGE (er:Error {id: e.id}) SET er.code = e.code, er.message = e.message, er.retryable = e.retryable
        MERGE (o)-[:RAISED]->(er)
        """, p)
    tx.run("""
        UNWIND $evidence AS e
        MATCH (st:ReasoningStep {id: e.step}), (o:Observation {id: e.obs})
        MERGE (ev:Evidence {id: e.id})
          SET ev.text = e.text, ev.source_type = e.source_type, ev.stale = e.stale
        MERGE (o)-[:YIELDED]->(ev)
        MERGE (st)-[:CITES]->(ev)
        FOREACH (k IN e.about | MERGE (en:Entity {key: k.key}) ON CREATE SET en.type = k.type
                                 MERGE (ev)-[:ABOUT]->(en))
        """, p)
    tx.run("""
        MATCH (r:ReasoningTrace {id: $run.id})
        MERGE (a:Answer {id: $answer.id}) SET a.text = $answer.text, a.acknowledges_limitation = $answer.ack
        MERGE (r)-[:PRODUCED]->(a)
        WITH a UNWIND $claims AS c
        MERGE (cl:Claim {id: c.id}) SET cl.key = c.key, cl.value = c.value
        MERGE (a)-[:ASSERTS]->(cl)
        WITH cl, c UNWIND c.support AS sid
        MATCH (ev:Evidence {id: sid})
        MERGE (cl)-[:SUPPORTED_BY]->(ev)
        """, p)


def load_all() -> None:
    """Seed static nodes, then load every trace in its own transaction."""
    seed_static()
    tasks = {t["task_id"]: t for t in json.loads((DATA / "tasks.json").read_text())}
    with get_driver().session(database=database()) as session:
        for f in sorted((DATA / "traces").glob("*.json")):
            trace = json.loads(f.read_text())
            session.execute_write(_load_tx, _run_params(trace, tasks[trace["task_id"]]))


def counts() -> dict:
    rows = read("MATCH (n) UNWIND labels(n) AS l RETURN l AS label, count(*) AS n ORDER BY label")
    return {r["label"]: r["n"] for r in rows}


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset()
        print("graph reset, schema applied")
    if "--no-load" not in sys.argv:
        load_all()
        print(counts())
