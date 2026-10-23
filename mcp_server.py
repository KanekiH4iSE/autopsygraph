"""AutopsyGraph MCP server (stdio). Lets any MCP client — Claude Code, Codex, OpenCode, Antigravity, Cursor —
ask the forensic graph why an agent run failed, how often it recurs, and (with explicit approval) apply the fix.

Run: <project>/.venv/Scripts/python.exe <project>/mcp_server.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

from forensics import engine  # noqa: E402
from forensics.claims import all_runs, claim_verdicts  # noqa: E402
from forensics.replay import GUARDRAILS, apply_fix as _apply_fix  # noqa: E402
from graph.db import read  # noqa: E402

server = MCPServer(
    name="autopsygraph",
    title="AutopsyGraph — AI agent failure forensics on Neo4j",
    instructions=(
        "AutopsyGraph stores AI-agent runs as a Neo4j evidence graph and diagnoses failed runs: the first decisive "
        "mistake, the evidence that proves it, the fix, and how often it recurs. Start with list_failed_runs or "
        "fleet_report, then diagnose_run(run_id). Only call apply_fix after the user explicitly approves it. "
        "Diagnoses describe observable behaviour only and are root-cause candidates with a confidence score."),
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


@server.tool(annotations=READ_ONLY)
def list_failed_runs() -> list[dict]:
    """List failed agent runs with the task, the customer request, why it failed and the stored diagnosis."""
    return [{"run": r["run"], "task": r["intent"], "request": r["request"], "why_failed": r["outcome"],
             "diagnosis": r["diagnosed_pattern"], "root_step": r["diagnosed_step"]}
            for r in all_runs() if not r["success"]]


@server.tool(annotations=READ_ONLY)
def get_run(run_id: str) -> dict:
    """Full observable record of one run: request, answer, step-by-step timeline (tool, args, status, errors,
    evidence incl. stale flags) and claims compared with ground truth."""
    return {"header": engine.run_header(run_id), "timeline": engine.timeline(run_id),
            "claims_vs_ground_truth": claim_verdicts(run_id)}


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True,
                                         openWorldHint=False))
def diagnose_run(run_id: str) -> dict:
    """Investigate a failed run: 9 Cypher detectors + first-divergence + judge. Returns the root-cause step,
    failure pattern, confidence, evidence trail, what the agent should have done, the fix, symptoms, cited
    evidence and cross-run context. Stores the verdict as a :Diagnosis node (idempotent)."""
    r = engine.investigate(run_id)
    v, rules = r["verdict"], r.get("rules") or {}
    if not v:
        return {"run": run_id, "verdict": None, "note": "No decisive failure found (the run may have succeeded)."}
    return {"run": run_id, "pattern": v["pattern_code"], "root_cause_step": v["root_step_idx"],
            "confidence": v["confidence"], "evidence_trail": rules.get("explanation"), "summary": v["explanation"],
            "should_have": v["counterfactual"], "fix": v["recommendation"], "symptoms": v["contributing"],
            "cited_evidence": v["evidence_ids"], "fleet_context": r["fleet"], "source": v["source"],
            "auto_fix_available": v["pattern_code"] in GUARDRAILS}


@server.tool(annotations=READ_ONLY)
def fleet_report() -> dict:
    """Cross-run view: ignored tool errors (e.g. 'timed out in 8 runs, ignored in 7'), failures by pattern,
    failing tools and measured accuracy on labelled synthetic runs."""
    return {"ignored_errors": engine.fleet_ignored_errors(), "failures_by_pattern": engine.fleet_patterns(),
            "tools": engine.fleet_tools(), "accuracy": engine.metrics()}


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True,
                                         openWorldHint=False))
def apply_fix(run_id: str, pattern: str, approve: bool = False) -> dict:
    """Re-run the agent on the same request with the recommended guardrail, store the replay as '<run>_fix'
    (linked by REPLAY_OF; the original run is never modified) and re-check it with the same detectors.
    REQUIRES the user's explicit approval: ask the user first, then call with approve=true."""
    if not approve:
        return {"status": "approval_required", "guardrail": GUARDRAILS.get(pattern),
                "message": "Ask the user to approve this guardrail, then call apply_fix again with approve=true."}
    return _apply_fix(run_id, pattern)


@server.tool(annotations=READ_ONLY)
def query_graph(cypher: str, limit: int = 50) -> list[dict]:
    """Run a READ-ONLY Cypher query against the AutopsyGraph database (writes are rejected by the server in read
    mode). Main labels: ReasoningTrace, ReasoningStep, ToolCall, Tool, Argument, Entity, Observation, Error,
    Evidence, Answer, Claim, Task, GroundTruth, Fact, Diagnosis, FailurePattern."""
    return read(cypher)[: max(1, min(limit, 500))]


if __name__ == "__main__":
    server.run("stdio")
