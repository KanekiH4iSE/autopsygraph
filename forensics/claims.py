"""Compare a run's final claims against ground-truth facts in the graph."""
from __future__ import annotations

from graph.db import read


def claim_verdicts(run_id: str) -> list[dict]:
    """One row per expected fact: match, MISMATCH (supported but wrong, or unsupported) or MISSING."""
    return read("""
        MATCH (r:ReasoningTrace {id: $run_id})-[:FOR_TASK]->(:Task)-[:HAS_GROUND_TRUTH]->(:GroundTruth)
              -[:EXPECTS_FACT]->(f:Fact)
        OPTIONAL MATCH (r)-[:PRODUCED]->(:Answer)-[:ASSERTS]->(c:Claim {key: f.key})
        OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(ev:Evidence)
        WITH f, c, collect(ev) AS evs
        RETURN f.key AS fact, f.value AS expected, c.value AS asserted,
               CASE WHEN c IS NULL THEN 'MISSING' WHEN c.value = f.value THEN 'match' ELSE 'MISMATCH' END AS verdict,
               [e IN evs | e.text][0..2] AS evidence, [e IN evs | e.id] AS evidence_ids,
               any(e IN evs WHERE e.stale) AS stale
        ORDER BY fact""", run_id=run_id)


def failed_runs() -> list[str]:
    """Ids of runs whose outcome is a failure."""
    return [r["id"] for r in read(
        "MATCH (r:ReasoningTrace {success: false}) WHERE r.replay_of IS NULL RETURN r.id AS id ORDER BY id")]


def all_runs() -> list[dict]:
    """Run list for the UI (labels omitted)."""
    return read("""
        MATCH (r:ReasoningTrace)-[:FOR_TASK]->(t:Task) WHERE r.replay_of IS NULL
        OPTIONAL MATCH (r)-[:STARTED_BY]->(u:UserRequest)
        OPTIONAL MATCH (r)-[:HAS_DIAGNOSIS]->(d:Diagnosis)
        RETURN r.id AS run, t.intent AS intent, r.success AS success, r.outcome AS outcome, u.text AS request,
               d.pattern_code AS diagnosed_pattern, d.root_step_idx AS diagnosed_step
        ORDER BY run""")
