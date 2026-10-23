"""Counterfactual replay: with the user's approval, re-run the scripted agent on the same request with the
recommended guardrail applied, load the replay into the graph as a separate run linked to the original
((:ReasoningTrace)-[:REPLAY_OF]->(:ReasoningTrace)), and re-check it with the same detectors.
The original run is never modified. Replays are excluded from run lists and fleet statistics.
"""
from __future__ import annotations

import json
from pathlib import Path

from datagen import patterns as P
from datagen.tasks import compute_outcome
from datagen.tools import Tools
from datagen.world import build_world
from forensics.claims import claim_verdicts
from forensics.detectors import run_all
from graph.db import database, get_driver, read, write
from graph.loader import _load_tx, _run_params

DATA = Path(__file__).resolve().parent.parent / "data"

GUARDRAILS = {
    "FP01": "Make the eligibility tool mandatory before any refund answer.",
    "FP03": "When a lookup returns more than one match, ask which one the user means before continuing.",
    "FP04": "Retry a failed tool once; if it still fails, escalate. Block write tools without a successful check.",
    "FP05": "Only assert facts that are backed by a tool result — look up the policy first.",
    "FP07": "Filter superseded policy versions out of search results.",
}


def replay_id(run_id: str) -> str:
    return f"{run_id}_fix"


def apply_fix(run_id: str, pattern: str) -> dict:
    """Re-run the agent with the guardrail for `pattern`, store it as `<run>_fix`, and re-check it."""
    if pattern not in GUARDRAILS:
        raise ValueError(f"No automatic guardrail for {pattern}")
    row = read("""
        MATCH (r:ReasoningTrace {id: $id})-[:FOR_TASK]->(t:Task)
        OPTIONAL MATCH (r)-[:STARTED_BY]->(u:UserRequest)
        RETURN t.id AS task, u.text AS request""", id=run_id)[0]
    task = {t["task_id"]: t for t in json.loads((DATA / "tasks.json").read_text())}[row["task"]]
    rid = replay_id(run_id)
    # The guardrailed agent follows the correct plan. For an ignored tool error the guardrail is
    # "retry once", so the replay keeps the original timeout and shows the successful retry.
    kwargs = {"timeout_then_retry": True} if pattern == "FP04" and task["template"] in ("T07", "T08", "T24") else {}
    trace = P.success_run(rid, task, row["request"], Tools(build_world()), **kwargs)
    ok, reasons = compute_outcome(trace, task)
    with get_driver().session(database=database()) as session:
        session.execute_write(_load_tx, _run_params(trace, task))
    write("""
        MATCH (fix:ReasoningTrace {id: $rid}), (orig:ReasoningTrace {id: $oid})
        SET fix.replay_of = $oid, fix.guardrail = $g
        MERGE (fix)-[:REPLAY_OF]->(orig)""", rid=rid, oid=run_id, g=GUARDRAILS[pattern])
    hits = run_all(rid)
    return {"run": rid, "replay_of": run_id, "pattern": pattern, "guardrail": GUARDRAILS[pattern],
            "success": ok, "reasons": reasons, "claims": claim_verdicts(rid),
            "decisive_hits": [h.as_dict() for h in hits if h.severity == 3]}
