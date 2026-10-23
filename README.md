# 🩻 AutopsyGraph

**Every failed agent run leaves evidence. We follow it.**

AutopsyGraph records the *observable* behaviour of a tool-using AI agent — requests, tool calls, arguments, outputs,
evidence and final claims — as a **Neo4j graph**. For every failed run it finds the **first decisive mistake**, classifies
it, cites the evidence, explains what the agent should have done, and counts how often the same failure recurs across all
runs.

> *"check_refund_eligibility timed out in 8 runs — and the agent silently ignored it in 7."*

Built at **Graphs Gone Wild** (NODES 2026 pop-up, Berlin).

## How it works

```
agent runs (JSON) → Neo4j Aura graph → 9 Cypher detectors → first divergence → rules verdict (+ LLM judge) → :Diagnosis
```

- **Graph-native forensics:** the cause of a wrong answer is a path (error → stale evidence → claim → answer); missing
  behaviour ("no retry after an error") is a `NOT EXISTS` query; shared Tool/Entity nodes make fleet patterns one query.
- **Rules narrow, the LLM decides and explains:** the LLM must choose among graph-proven candidates; evidence, symptoms
  and fixes stay deterministic; rules-only fallback when no LLM is available.
- **Measured:** on 24 labelled synthetic failures the injected root-cause step and pattern are found 24/24 — an upper
  bound on clean synthetic data.

## Quick start

```powershell
pip install -r requirements.txt          # Python 3.11+
copy .env.example .env                    # fill in Neo4j Aura credentials (LLM optional)
.\run.ps1 all                             # gen → reset → load → detect → validate
.\run.ps1 ui                              # http://localhost:8501
```

📖 **Full explanation, demo script and Q&A:** [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) · team plan: [`TEAM_PLAN.md`](TEAM_PLAN.md)

## Honesty

We analyse observable agent behaviour only — we never claim to read hidden chain of thought; "rationale" fields are text
the agent emitted. Diagnoses are root-cause candidates with a confidence score. Accuracy is measured on synthetic runs
with injected labels; real-world performance will be lower. All customer data is synthetic.
