"""Cypher detectors. Each runs one parameterised read query for a single run and returns Hits."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field

from graph.db import read


@dataclass
class Hit:
    pattern: str
    step_idx: int
    severity: int  # 1 low .. 3 decisive
    detector: str
    evidence_ids: list[str] = field(default_factory=list)
    detail: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def ignored_error(run_id: str) -> list[Hit]:
    """FP04: a tool error with no later successful retry or escalation, and an answer that stays silent."""
    rows = read("""
        MATCH (r:ReasoningTrace {id: $run_id})-[:HAS_STEP]->(st:ReasoningStep)-[:USES_TOOL]->(tc:ToolCall)
              -[:RETURNED]->(o:Observation)-[:RAISED]->(err:Error)
        MATCH (r)-[:PRODUCED]->(ans:Answer)
        WHERE NOT EXISTS {
          MATCH (r)-[:HAS_STEP]->(later:ReasoningStep)-[:USES_TOOL]->(tc2:ToolCall)
          WHERE later.idx > st.idx AND ((tc2.tool_name = tc.tool_name AND tc2.status = 'ok')
                OR tc2.tool_name = 'escalate_to_human') }
          AND coalesce(ans.acknowledges_limitation, false) = false
        RETURN st.idx AS step, tc.tool_name AS tool, err.code AS error, err.retryable AS retryable, o.id AS obs
        ORDER BY step""", run_id=run_id)
    return [Hit("FP04", r["step"], 3, "ignored_error", [],
                f"{r['tool']} returned {r['error']}{' (retryable)' if r['retryable'] else ''}; the agent neither "
                f"retried nor escalated, and the answer does not mention it") for r in rows]


def invalid_args(run_id: str) -> list[Hit]:
    """FP02: an argument that violates the tool schema."""
    rows = read("""
        MATCH (:ReasoningTrace {id: $run_id})-[:HAS_STEP]->(st:ReasoningStep)-[:USES_TOOL]->(tc:ToolCall)
              -[:HAS_ARG]->(a:Argument {valid: false})
        RETURN st.idx AS step, tc.tool_name AS tool, a.name AS arg, a.value AS value, a.violation AS violation
        ORDER BY step""", run_id=run_id)
    return [Hit("FP02", r["step"], 3, "invalid_args", [],
                f"{r['tool']}({r['arg']}={r['value']}) {r['violation']}") for r in rows]


def retry_loop(run_id: str) -> list[Hit]:
    """FP10: three or more calls with the same tool and identical arguments."""
    rows = read("""
        MATCH (:ReasoningTrace {id: $run_id})-[:HAS_STEP]->(st:ReasoningStep)-[:USES_TOOL]->(tc:ToolCall)
        WITH tc.tool_name AS tool, tc.args_hash AS h, st.idx AS idx ORDER BY idx
        WITH tool, h, collect(idx) AS idxs WHERE size(idxs) >= 3
        RETURN tool, idxs""", run_id=run_id)
    return [Hit("FP10", r["idxs"][0], 2, "retry_loop", [],
                f"{r['tool']} called {len(r['idxs'])} times with identical arguments") for r in rows]


def unsupported_claim(run_id: str) -> list[Hit]:
    """FP05: a claim in the final answer with no SUPPORTED_BY evidence. Root step = the answer step."""
    rows = read("""
        MATCH (r:ReasoningTrace {id: $run_id})-[:PRODUCED]->(:Answer)-[:ASSERTS]->(c:Claim)
        WHERE NOT (c)-[:SUPPORTED_BY]->(:Evidence)
        MATCH (r)-[:HAS_STEP]->(st:ReasoningStep {kind: 'answer'})
        RETURN st.idx AS step, c.key AS claim, c.value AS value""", run_id=run_id)
    return [Hit("FP05", r["step"], 3, "unsupported_claim", [],
                f"claim {r['claim']}={r['value']} has no supporting evidence") for r in rows]


def stale_evidence(run_id: str) -> list[Hit]:
    """FP07: a step cites superseded evidence. Decisive when a final claim rests on it."""
    rows = read("""
        MATCH (r:ReasoningTrace {id: $run_id})-[:HAS_STEP]->(st:ReasoningStep)-[:CITES]->(ev:Evidence {stale: true})
        OPTIONAL MATCH (r)-[:PRODUCED]->(:Answer)-[:ASSERTS]->(c:Claim)-[:SUPPORTED_BY]->(ev)
        RETURN st.idx AS step, ev.id AS ev_id, ev.text AS text, collect(c.key) AS relying
        ORDER BY step""", run_id=run_id)
    return [Hit("FP07", r["step"], 3 if r["relying"] else 2, "stale_evidence", [r["ev_id"]],
                f"cites superseded evidence '{r['text']}'"
                + (f"; claim(s) {', '.join(r['relying'])} rest on it" if r["relying"] else "")) for r in rows]


def wrong_entity(run_id: str) -> list[Hit]:
    """FP03: an argument refers to an entity of the expected type but not the expected one."""
    rows = read("""
        MATCH (r:ReasoningTrace {id: $run_id})-[:FOR_TASK]->(:Task)-[:HAS_GROUND_TRUTH]->(:GroundTruth)
              -[:EXPECTS_ENTITY]->(want:Entity)
        MATCH (r)-[:HAS_STEP]->(st:ReasoningStep)-[:USES_TOOL]->(tc:ToolCall)-[:HAS_ARG]->(:Argument)
              -[:REFERS_TO]->(got:Entity)
        WHERE got.type = want.type AND got.key <> want.key
        RETURN st.idx AS step, tc.tool_name AS tool, got.key AS used, want.key AS expected
        ORDER BY step LIMIT 1""", run_id=run_id)
    return [Hit("FP03", r["step"], 3, "wrong_entity", [],
                f"{r['tool']} used {r['used']} but the task is about {r['expected']}") for r in rows]


def forbidden_tool(run_id: str) -> list[Hit]:
    """FP12: a tool the ground truth forbids was called."""
    rows = read("""
        MATCH (r:ReasoningTrace {id: $run_id})-[:FOR_TASK]->(:Task)-[:HAS_GROUND_TRUTH]->(gt:GroundTruth)
        MATCH (r)-[:HAS_STEP]->(st:ReasoningStep)-[:USES_TOOL]->(tc:ToolCall)
        WHERE tc.tool_name IN gt.forbidden_tools
        RETURN st.idx AS step, tc.tool_name AS tool ORDER BY step""", run_id=run_id)
    return [Hit("FP12", r["step"], 2, "forbidden_tool", [], f"forbidden tool {r['tool']} was called") for r in rows]


def missing_required_step(run_id: str) -> list[Hit]:
    """FP06: a write tool before a successful required check. FP11: required tools never called."""
    hits = []
    for r in read("""
        MATCH (r:ReasoningTrace {id: $run_id})-[:FOR_TASK]->(:Task)-[:HAS_GROUND_TRUTH]->(gt:GroundTruth)
        MATCH (r)-[:HAS_STEP]->(st:ReasoningStep)-[:USES_TOOL]->(tc:ToolCall)-[:INSTANCE_OF]->(:Tool {read_only: false})
        WHERE tc.tool_name <> 'escalate_to_human'
          AND any(rt IN gt.required_tools WHERE NOT EXISTS {
                MATCH (r)-[:HAS_STEP]->(p:ReasoningStep)-[:USES_TOOL]->(pc:ToolCall {tool_name: rt, status: 'ok'})
                WHERE p.idx < st.idx })
        RETURN st.idx AS step, tc.tool_name AS tool ORDER BY step""", run_id=run_id):
        hits.append(Hit("FP06", r["step"], 2, "missing_required_step", [],
                        f"{r['tool']} called without a prior successful required check"))
    for r in read("""
        MATCH (r:ReasoningTrace {id: $run_id})-[:FOR_TASK]->(:Task)-[:HAS_GROUND_TRUTH]->(gt:GroundTruth)
        MATCH (r)-[:HAS_STEP]->(ans:ReasoningStep {kind: 'answer'})
        WITH r, ans, [rt IN gt.required_tools WHERE NOT EXISTS {
               MATCH (r)-[:HAS_STEP]->(:ReasoningStep)-[:USES_TOOL]->(:ToolCall {tool_name: rt}) }] AS missing
        WHERE size(missing) > 0
        RETURN ans.idx AS step, missing""", run_id=run_id):
        hits.append(Hit("FP11", r["step"], 1, "missing_required_step", [],
                        f"answered without calling required tool(s): {', '.join(r['missing'])}"))
    return hits


def wrong_tool_plan(run_id: str) -> list[Hit]:
    """FP01: a required tool was never called and the agent used an unplanned tool in its place.
    (A required tool that was called but errored is FP04, not FP01.)"""
    rows = read("""
        MATCH (r:ReasoningTrace {id: $run_id})-[:FOR_TASK]->(:Task)-[:HAS_GROUND_TRUTH]->(gt:GroundTruth)
        WITH r, gt, [rt IN gt.required_tools WHERE NOT EXISTS {
               MATCH (r)-[:HAS_STEP]->(:ReasoningStep)-[:USES_TOOL]->(:ToolCall {tool_name: rt}) }] AS unmet
        WHERE size(unmet) > 0
        MATCH (r)-[:HAS_STEP]->(st:ReasoningStep)-[:USES_TOOL]->(tc:ToolCall)
        WHERE NOT tc.tool_name IN gt.expected_tools
        RETURN st.idx AS step, tc.tool_name AS tool, unmet ORDER BY step LIMIT 1""", run_id=run_id)
    return [Hit("FP01", r["step"], 3, "wrong_tool_plan", [],
                f"used {r['tool']} instead of required {', '.join(r['unmet'])}") for r in rows]


DETECTORS = [ignored_error, invalid_args, retry_loop, unsupported_claim, stale_evidence, wrong_entity,
             forbidden_tool, missing_required_step, wrong_tool_plan]


def run_all(run_id: str) -> list[Hit]:
    """Run every detector for one run (in parallel: each is one round trip to Aura), ordered by step then severity."""
    with ThreadPoolExecutor(max_workers=len(DETECTORS)) as pool:
        hits = [h for result in pool.map(lambda d: d(run_id), DETECTORS) for h in result]
    return sorted(hits, key=lambda h: (h.step_idx, -h.severity))
