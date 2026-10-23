# Decisions

- Pre-event work is limited to data prep and plumbing (datagen, schema, loader). Detectors, judge and UI are built at the event.
- Python 3.13 venv (3.14 is the system default but has thinner wheel coverage).
- No `make` on Windows: `run.ps1` provides the same targets.
- No Docker installed: the local Neo4j fallback is unavailable; Aura Free only. Phone hotspot if venue wifi fails.
- FastAPI dropped: Streamlit calls `forensics.engine` directly (one less layer for a ~3 h build).
- Hero runs live in `datagen/generate.py` (`plan()` rows) instead of a separate `hero.py`.
- Task ids are per instance (`T08_refund_request__ORD-1042`), so ground truth differs per order.
- Evidence ids are `{run}-e{step idx}` so run_017's stale policy evidence is `run_017-e3`, as in the spec.
- Successful timeout case = retry once then success; no "escalate" success run (an escalation answer has no
  `refund_eligible` claim and would count as MISSING under the outcome rule).
- FP03 alternates Denver/Austin: an Austin request picks C-031, a Denver request picks C-019.
- FP05 root step = the answer step; FP05 on T15 has no tool calls at all (root = step 1).
- Run ids are a seeded sample from 1..120 so hero ids (003, 017, 066, 087) sit among them.
