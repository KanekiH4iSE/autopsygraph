# AutopsyGraph — two-person team plan

**Hackathon:** Graphs Gone Wild (NODES 2026 pop-up), CODE University, Donaustraße 44, Berlin, 23 Oct 2026
**Hacking:** 16:30–18:30 and 19:00–20:00 · **Pizza:** 18:30–19:00 · **Pitches:** 20:00–20:30 (~2 minutes per team)
**Project:** `C:\Users\User\projects\autopsygraph` · **Database:** [console.neo4j.io](https://console.neo4j.io) → project FiranAI → Instance01

> The idea in one sentence: *AutopsyGraph turns every AI-agent run into an evidence graph, and for every failed run
> it finds the first decisive mistake, proves it, and counts how often it recurs.*

---

## 0. Already done (before the start)

- Dataset: 36 runs (12 successful, 24 failed), tests green.
- Graph schema and loader; the data is **already in Aura** (36 runs, 116 steps, 80 tool calls).
- `.env` with Aura access. `LLM_ENABLED=false` — no Anthropic key, so the judge runs on rules only.
- The headline number for the pitch is already verified: **`check_refund_eligibility` timed out in 8 runs, and the agent ignored the error in 7 of them.**
- Still to build: detectors → judge → UI (milestones 4–8 in `CLAUDE.md`).

---

## 1. Roles

| | **A — Builder** | **B — Demo & Graph** |
|---|---|---|
| Main job | Get the code to a working demo | Make sure the judges understand and remember it |
| Sits at | The laptop running Claude Code | The second laptop with Aura and the slides |
| Decides | What gets cut from the code | What gets said and shown |
| During the pitch | Clicks through the demo | Talks |

**Shared rules**
- Sync every 30 minutes, 2 minutes max: what's done, what's stuck, what we cut.
- Stuck for more than 10 minutes → take the fallback (section 5), stop fixing.
- After 18:30, no new features — only polish and stability.
- No password or key ever goes into chat, onto a slide, or on screen during the demo.

---

## 2. A — Builder: responsibilities

### Setup (16:15–16:30, during the intro talk)
- [ ] Open a terminal in `C:\Users\User\projects\autopsygraph`.
- [ ] Check the database: `.\run.ps1 ping` → should print version `5.27-aura`.
- [ ] Check the tests: `.\run.ps1 test` → `3 passed`.
- [ ] Start Claude Code in this folder.

### Milestone 4 (16:30–17:15): detectors
Tell Claude Code: **"Start from milestone 4 in CLAUDE.md. Milestones 1–3 are done and the data is in Aura."**
- [ ] `forensics/detectors.py`, `divergence.py`, `claims.py` exist.
- [ ] `.\.venv\Scripts\python.exe -m pytest -q tests\test_detectors.py` is green.
- [ ] Verified: run_017 → root at step 2, FP04; run_087 → step 2, FP03; run_066 → step 2, FP05; run_003 → no high-severity hits.
- [ ] Commit.

### Milestone 5 (17:15–17:40): judge and Diagnosis
- [ ] `forensics/judge.py` works with `LLM_ENABLED=false` (rules only).
- [ ] `.\run.ps1 detect` → `Diagnosis` nodes written for all 24 failed runs.
- [ ] Commit.

### Milestone 6 (17:40–18:00): accuracy
- [ ] `.\run.ps1 validate` prints root-step and pattern accuracy and writes `data/metrics.json`.
- [ ] **Give B the accuracy number** (needed for the pitch).
- [ ] Accuracy below 85% → fix the detectors first, UI comes later.
- [ ] Commit.

### Milestone 8a (18:00–18:30): Run detail page
- [ ] `.\run.ps1 ui` → Streamlit opens.
- [ ] Runs list, select run_017, timeline graph (graphviz), **Investigate** button → verdict card.
- [ ] Send B the page URL for testing.
- [ ] Commit.

### 18:30–19:00 — pizza + sync with B
- [ ] Go through B's bug list: fix only what shows up in the demo.

### Milestone 8b (19:00–19:40): Fleet page
- [ ] Bar chart of failures by pattern, failing-tools table, big number "8 timeouts → 7 ignored".
- [ ] Accuracy from `data/metrics.json`.
- [ ] Footer on every page: *"We analyse observable agent behaviour only…"*.
- [ ] Commit.

### 19:40–20:00 — code freeze
- [ ] `.\run.ps1 all` passes from scratch with no errors.
- [ ] Final commit. **No more code changes.**
- [ ] Pre-open the tabs: Runs → run_017, Fleet. Increase browser zoom (Ctrl +).
- [ ] Two full demo run-throughs with B.

### If there is time left (only after 19:40 and only if everything is green)
- Hook `mcp-neo4j-cypher --read-only` into Claude Code and ask the graph a question live. If it doesn't work within 10 minutes, drop it.

---

## 3. B — Demo & Graph: responsibilities

### Setup (15:00–16:30)
- [ ] At check-in, ask the organisers (Zaid Zaim):
  - may we bring pre-written code and data (our data generator and loader are ready);
  - how do we submit the project and how many minutes is the pitch;
  - which new tools or partners will be announced.
- [ ] During the intro, note anything we could plug in quickly (e.g. Aura Agents) and tell A.
- [ ] Log in to [console.neo4j.io](https://console.neo4j.io) → FiranAI → Instance01 → **Query**.

### 16:30–17:30 — fallback Cypher queries
Save the four queries from section 6 in Aura Query (favourites) and run each one:
- [ ] Q1 run_017 graph
- [ ] Q2 the wrong Maria Lopez (run_087)
- [ ] Q3 the pitch number (8 → 7)
- [ ] Q4 agent answer vs ground truth (run_017)
- [ ] Take screenshots of the results into `screenshots/` (fallback if the wifi dies).

### 17:30–18:00 — slides (3 max)
- [ ] **Slide 1 — the problem:** "Agents fail quietly: every call returns 200 and the answer sounds confident."
- [ ] **Slide 2 — how it works:** run → graph (step → tool call → observation → evidence → claim → ground truth) → Cypher checks → verdict.
- [ ] **Slide 3 — the numbers:** "8 timeouts, 7 ignored" + accuracy from A + an honest note that the data is synthetic.

### 18:00–18:30 — UI testing
- [ ] Walk through the demo script (section 4) in A's UI.
- [ ] Log bugs as one line each: what I clicked → what I expected → what I saw. Hand them to A in a batch at the sync, don't interrupt every 2 minutes.

### 19:00–19:40 — final pitch
- [ ] Put the accuracy number into slide 3 and the script.
- [ ] Read the pitch out loud with a timer: exactly 2:00.
- [ ] Prepare answers to the questions (section 7).

### 19:40–20:00 — backup video and rehearsal
- [ ] Screen-record A walking through the demo (OBS, Xbox Game Bar `Win+G`, or a phone). 1.5–2 minutes.
- [ ] Two full rehearsals with A.

### 20:00 — pitch
- [ ] B talks, A clicks. If the demo freezes, B switches to the video or screenshots without pausing.

---

## 4. Demo flow and pitch script (2 minutes)

| Time | Screen (A clicks) | Script (B says) |
|---|---|---|
| 0:00–0:15 | Slide 1 | "Agents fail quietly. Every call returned 200, the answer sounded confident — and the customer got a refund they were never entitled to." |
| 0:15–0:30 | Runs page | "We record every run of a support agent in Neo4j as a graph: the request, tool calls, arguments, outputs, evidence and final claims. 36 runs, 24 failed." |
| 0:30–1:10 | run_017 → **Investigate** | "The agent refunded $189 for a final-sale tent. Where did it go wrong? Not at step 4, the refund. The root cause is step 2: the eligibility check timed out, the agent neither retried nor escalated, and fell back to a superseded 60-day policy. The refund is just the symptom. Every conclusion points to a node in the graph." |
| 1:10–1:35 | Fleet | "Now across all runs, in one query: this tool timed out in 8 runs, and in 7 the agent silently ignored the error. That's not bad luck, that's a missing rule. Three fixes: a prompt rule, a code guardrail, and filtering out superseded policies." |
| 1:35–2:00 | Slide 3 | "On labelled synthetic runs we find the root-cause step X% of the time. We analyse what the agent did, not what it thought." |

---

## 5. If something breaks

| Problem | What we do | Who |
|---|---|---|
| Aura not responding / paused | Open console.neo4j.io → Instance01 → Resume, wait 1–2 minutes, `.\run.ps1 ping` | A |
| Graph data corrupted | `.\run.ps1 reset` then `.\run.ps1 load` (~1 minute) | A |
| Wifi down | Phone hotspot | B |
| A detector won't work in Cypher | Do the check in Python over the JSON; keep Cypher only for the demo queries | A |
| Accuracy below 85% at 18:00 | Fix the detectors; cut the UI down to one page | A |
| Streamlit not working by 19:30 | Demo via Aura Query (queries Q1–Q4) + slides | B |
| Demo freezes on stage | Switch straight to the backup video or screenshots | B |

**Cut in this order:** MCP stretch goal → neo4j-viz tab → Fleet page polish → extra patterns (FP01, FP03).
**Never cut:** the run_017 verdict, the timeline graph, the "8 → 7" number.

---

## 6. Fallback Cypher queries (for B, paste into Aura → Query)

**Q1 — run_017 graph (the demo picture)**
```cypher
MATCH (r:ReasoningTrace {id: 'run_017'})-[:HAS_STEP]->(s:ReasoningStep)
OPTIONAL MATCH p1 = (s)-[:USES_TOOL]->(:ToolCall)-[:RETURNED]->(:Observation)-[:RAISED|YIELDED]->()
OPTIONAL MATCH p2 = (r)-[:PRODUCED]->(:Answer)-[:ASSERTS]->(:Claim)-[:SUPPORTED_BY]->(:Evidence)
RETURN r, s, p1, p2
```

**Q2 — the wrong Maria Lopez (run_087)**
```cypher
MATCH (r:ReasoningTrace {id: 'run_087'})-[:FOR_TASK]->(:Task)-[:HAS_GROUND_TRUTH]->(:GroundTruth)
      -[:EXPECTS_ENTITY]->(want:Entity {type: 'customer'})
MATCH (r)-[:HAS_STEP]->(st:ReasoningStep)-[:USES_TOOL]->(tc:ToolCall)-[:HAS_ARG]->(:Argument)
      -[:REFERS_TO]->(got:Entity {type: 'customer'})
RETURN st.idx AS step, tc.tool_name AS tool, got.key AS used, want.key AS expected
```

**Q3 — the headline number (verified: 7)**
```cypher
MATCH (r:ReasoningTrace)-[:HAS_STEP]->(st)-[:USES_TOOL]->(tc)-[:RETURNED]->(:Observation)-[:RAISED]->(err:Error)
MATCH (r)-[:PRODUCED]->(ans:Answer)
WHERE NOT EXISTS {
  MATCH (r)-[:HAS_STEP]->(l)-[:USES_TOOL]->(tc2)
  WHERE l.idx > st.idx AND ((tc2.tool_name = tc.tool_name AND tc2.status = 'ok')
        OR tc2.tool_name = 'escalate_to_human') }
  AND coalesce(ans.acknowledges_limitation, false) = false
RETURN tc.tool_name AS tool, err.code AS error, count(DISTINCT r) AS runs_ignoring_it
```

**Q4 — agent answer vs ground truth (run_017)**
```cypher
MATCH (r:ReasoningTrace {id: 'run_017'})-[:FOR_TASK]->(:Task)-[:HAS_GROUND_TRUTH]->(:GroundTruth)
      -[:EXPECTS_FACT]->(f:Fact)
OPTIONAL MATCH (r)-[:PRODUCED]->(:Answer)-[:ASSERTS]->(c:Claim {key: f.key})
OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(ev:Evidence)
RETURN f.key AS fact, f.value AS expected, c.value AS agent_said,
       collect({text: ev.text, stale: ev.stale}) AS evidence
```

---

## 7. Judge questions and answers (for B)

- **"Isn't this just LangSmith / Langfuse?"** — Those are great trace stores. What we add is provenance as a graph (claim ↔ evidence ↔ tool call ↔ entity), comparison against ground truth, and Cypher queries across all runs at once.
- **"How do you know the diagnosis is right?"** — We injected the failures ourselves, so we know the right answer and can measure accuracy. It's an upper bound: published results on real, longer traces are much lower (11% on TRAIL, 14.2% on Who&When).
- **"Does it work without ground truth?"** — Ignored errors, unsupported claims, stale evidence and unsafe actions are found without it. Wrong facts and wrong entities need a reference.
- **"Can you see what the model was thinking?"** — No. Only observable behaviour, and every verdict cites tool outputs.
- **"Why a graph and not logs?"** — The cause is a path in the graph: error → stale evidence → claim → answer. And "no retry after an error" is a single `NOT EXISTS` query.

---

## 8. Where everything is

| What | Where |
|---|---|
| Project | `C:\Users\User\projects\autopsygraph` |
| Instructions for Claude Code | `CLAUDE.md` |
| Decisions log | `DECISIONS.md` |
| Aura access | `.env` (never show on screen) |
| Aura password file | `C:\Users\User\Downloads\Neo4j-40d861fc-Created-2026-10-23.txt` |
| Commands | `.\run.ps1 ping / test / reset / load / detect / validate / ui / all` |
| Plan (document) | https://claude.ai/artifact/3phKEEuFTW1CmbDcBfSrdk |
