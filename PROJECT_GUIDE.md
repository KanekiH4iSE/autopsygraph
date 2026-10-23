# AutopsyGraph — the complete guide (A to Z)

> **Every failed agent run leaves evidence. We follow it.**
>
> Read this once and you will be able to explain, run, demo and defend the whole project.
> Built at **Graphs Gone Wild** (NODES 2026 pop-up, CODE University Berlin, 23 Oct 2026).

---

## Contents

1. [The 30-second version](#1-the-30-second-version)
2. [The problem we solve](#2-the-problem-we-solve)
3. [What AutopsyGraph does](#3-what-autopsygraph-does)
4. [The demo story: run_017, the $189 refund](#4-the-demo-story-run_017-the-189-refund)
5. [How it works, end to end](#5-how-it-works-end-to-end)
6. [The data: a fake shop and a scripted agent](#6-the-data-a-fake-shop-and-a-scripted-agent)
7. [The graph: what is stored in Neo4j](#7-the-graph-what-is-stored-in-neo4j)
8. [The detectors: how we spot mistakes](#8-the-detectors-how-we-spot-mistakes)
9. [Finding the root cause](#9-finding-the-root-cause)
10. [The judge: rules + LLM](#10-the-judge-rules--llm)
11. [The UI, page by page](#11-the-ui-page-by-page)
12. [The numbers we can quote](#12-the-numbers-we-can-quote)
13. [Why a graph and not logs](#13-why-a-graph-and-not-logs)
14. [The judging criteria and our answers](#14-the-judging-criteria-and-our-answers)
15. [Tough questions and honest answers](#15-tough-questions-and-honest-answers)
16. [What we do NOT claim](#16-what-we-do-not-claim)
17. [How to run everything](#17-how-to-run-everything)
18. [The 2-minute pitch script](#18-the-2-minute-pitch-script)
19. [If something breaks on stage](#19-if-something-breaks-on-stage)
20. [Where to take it next](#20-where-to-take-it-next)
21. [File map](#21-file-map)
22. [Glossary](#22-glossary)

---

## 1. The 30-second version

AI agents (chatbots that call tools — look up orders, issue refunds, search policies) **fail quietly**. Every API call
returns "200 OK", the final answer sounds confident, and nobody notices that the customer just got a refund they were
never entitled to.

**AutopsyGraph** records every step of every agent run as a **graph in Neo4j**: the request, each tool call, its
arguments, what the tool returned, which evidence the agent relied on, and the claims in its final answer. For every
failed run it then:

1. finds the **first decisive mistake** (not the last visible symptom),
2. **proves** it by following edges in the graph,
3. explains **what the agent should have done**, and suggests a **fix**,
4. counts **how often the same mistake happens across all runs**.

Headline result in our demo: *the eligibility tool timed out in 8 runs, and the agent silently ignored the error in 7
of them.* One guardrail fixes the whole class.

---

## 2. The problem we solve

Companies now put tool-using agents into customer support, finance and operations. When these agents fail:

- **Monitoring says everything is fine.** Latency normal, error rate low, every request answered. The failure is in the
  *meaning* of the answer, not in the infrastructure.
- **The visible symptom is not the cause.** In our hero example the visible damage is a refund at step 4, but the real
  mistake happened at step 2 (a timeout the agent ignored). Fixing step 4 doesn't fix anything.
- **Engineers read traces one at a time.** They cannot tell whether failure #12 has the same root cause as failure #4,
  so they cannot prioritise.
- **LLMs alone are bad at this.** Research benchmarks show frontier models find the failing step in raw agent traces
  only **11%** (TRAIL benchmark) to **14.2%** (Who&When benchmark) of the time.

**Who it is for:** an AI engineer on a small team shipping an agent, who just learned their agent fails ~30% of the
time and needs to know *what to fix first*.

---

## 3. What AutopsyGraph does

| Step | What happens | Where in the code |
|---|---|---|
| Record | Each agent run is written to Neo4j as connected nodes (run → steps → tool calls → arguments → observations → evidence → claims) | `graph/loader.py` |
| Judge the outcome | The answer's claims are compared with ground-truth facts; forbidden actions are checked | `datagen/tasks.py`, `forensics/claims.py` |
| Detect | 9 graph checks (Cypher queries) flag suspicious steps | `forensics/detectors.py` |
| Find the root | The earliest decisive flagged step is the root cause; later flags are symptoms | `forensics/divergence.py` |
| Explain | A rules verdict is always built; an LLM can choose among the rule candidates and write the narrative | `forensics/judge.py` |
| Store | The verdict is saved back into the graph as a `:Diagnosis` node linked to the root step, the pattern and the evidence | `forensics/engine.py` |
| Zoom out | Fleet queries count patterns, failing tools and ignored errors across all runs | `forensics/engine.py` |
| Show | Streamlit app: Runs, Run detail (timeline graph + Investigate), Fleet | `ui/app.py` |

---

## 4. The demo story: run_017, the $189 refund

This is the run we show on stage. Learn it by heart.

**The customer asks:** *"I want my money back for the Ridgeline 2P Tent on ORD-1042, please process it."*

**What the agent did:**

| Step | Tool | Result |
|---|---|---|
| 1 | `get_order(ORD-1042)` | OK — tent, $189, delivered 2 Sep 2026 |
| 2 | `check_refund_eligibility(ORD-1042, SKU-TENT-02)` | **TIMEOUT** (`UPSTREAM_TIMEOUT`, retryable) |
| 3 | `search_policy("refund window")` | OK — but returns **v1** of the refund policy ("60 days"), which was **superseded** on 1 June 2026 |
| 4 | `issue_refund(ORD-1042, $189)` | OK — refund RF-5521 issued |
| 5 | Answer: *"Done! I've refunded $189."* | — |

**The truth:** the tent is a **final-sale item**. The current policy (v2) says 30 days and **final-sale items are excluded**.
The correct answer was *not eligible*, and `issue_refund` should never have been called.

**What AutopsyGraph says after clicking Investigate:**

- **Root cause: step 2, pattern FP04 "Ignored tool error", confidence 0.90.**
  The eligibility check timed out; the agent neither retried nor escalated and the answer never mentioned it.
- **Symptoms after the root:** FP07 at step 3 (relied on stale policy), FP06 and FP12 at step 4 (refund without a
  successful check; forbidden action).
- **Cited evidence:** `run_017-e3` — "POL-REFUND v1: Refunds within 60 days of delivery" — marked **STALE**.
- **What it should have done:** retry the check once; if it still fails, tell the user and escalate to a human.
- **Fix:** "Retry once, then escalate. Add a guard blocking write tools without a successful eligibility result."
- **Across the fleet:** *check_refund_eligibility errored in 8 runs; the agent ignored it in 7.*

**Why this is the money shot:** the obvious culprit (the refund at step 4) is a *symptom*. The graph traces it back to
the real cause (the ignored timeout at step 2). And the fleet number turns one bug into a pattern worth fixing.

**Second example, run_087 (wrong customer):** *"This is Maria Lopez from Denver. Where is my latest order?"* There are
two Maria Lopez customers (C-019 in Austin, C-031 in Denver). The agent picked the Austin one. **Every claim in the
answer is backed by evidence**, so a simple "is it grounded?" check passes. Only by following the argument edge
`list_orders → customer:C-019` and comparing it with the expected entity `customer:C-031` does the mistake appear.
That's a failure you can only see in a graph.

---

## 5. How it works, end to end

```
 (before the event)                      (live, in Aura)
 datagen/generate.py ──► data/traces/*.json ──► graph/loader.py ──► Neo4j Aura graph
   world + tools + tasks      36 runs (JSON)        MERGE, idempotent        ~1,000 nodes
   + buggy policies
                                                                              │
                         ┌────────────────────────────────────────────────────┘
                         ▼
   forensics/detectors.py   9 Cypher checks per run  ──►  Hits (pattern, step, severity)
   forensics/divergence.py  earliest decisive hit    ──►  root step + symptoms
   forensics/claims.py      claims vs ground truth   ──►  match / MISMATCH / MISSING
   forensics/judge.py       rules verdict (+ LLM)    ──►  verdict JSON
   forensics/engine.py      write :Diagnosis back into the graph + fleet queries
                         │
                         ▼
   ui/app.py (Streamlit)    Runs · Run detail (graph + Investigate) · Fleet
   validate.py              accuracy vs injected labels → data/metrics.json
```

Tech stack: **Python 3.13, Neo4j Aura Free (Neo4j 5.27), official neo4j Python driver, Pydantic, Streamlit,
OpenAI-compatible LLM (gpt-4o-mini via the GraphAcademy workshop proxy)**.

---

## 6. The data: a fake shop and a scripted agent

We built a small, fully controlled world so we **know the right answer** for every run. That is what lets us measure
accuracy.

**The shop: "NorthPeak Outfitters" (outdoor gear, customer support).** Generated with a fixed random seed (42), so it is
identical every time.

- 25 customers, including **two "Maria Lopez"** (C-019 Austin, C-031 Denver) — a deliberate name collision.
- 16 products; 4 are **final-sale** (no refunds), e.g. the Ridgeline 2P Tent ($189).
- 45 orders and shipments; some shipments are delayed (e.g. ORD-1107, 7 days late).
- Policies:
  - `POL-REFUND v1` — 60 days, **superseded** on 2026-06-01.
  - `POL-REFUND v2` — 30 days, final-sale items excluded (current).
  - `POL-DELAY` — delay > 5 days → $10 credit.
  - `POL-ESCALATION` — escalate when a required system is unavailable.

**The tools** the agent can call (pure functions over the world): `find_customer`, `get_order`, `list_orders`,
`get_shipment`, `get_product`, `search_policy`, `check_refund_eligibility`, `issue_refund`, `escalate_to_human`.
Each has a JSON schema (e.g. `order_id` must match `ORD-\d{4}`).

**The tasks** (8 templates), each with ground truth **computed by code, never by an LLM**: expected tools, required
tools, forbidden tools, expected facts (e.g. `refund_eligible=false`) and expected entities (e.g. `customer:C-031`).

| Template | Customer asks about |
|---|---|
| T02 | Order status with an ambiguous name (Maria Lopez) |
| T07 | Refund eligibility |
| T08 | Process a refund |
| T12 | Delay compensation |
| T15 | Refund window policy |
| T18 | Order status |
| T21 | Product price |
| T24 | Returning a jacket (eligible case) |

**The agent ("ShopBot")** is **scripted** — not an LLM. For each task there is a *correct* script and *buggy* scripts,
one per failure pattern. This gives exact, reproducible labels.

**The dataset: 36 runs — 12 successful, 24 failed.**

| Pattern | Name | Runs | What the buggy script does |
|---|---|---|---|
| FP04 | Ignored tool error | 7 | Eligibility check times out; agent doesn't retry/escalate, falls back to policy search (stale v1 in 3 runs), refunds or says "eligible" |
| FP03 | Wrong entity | 6 | Two Maria Lopez; agent picks the wrong one without asking |
| FP05 | Hallucinated conclusion | 5 | Answers without looking up the policy ("25% refund and free express shipping") |
| FP07 | Stale context | 3 | Policy search returns superseded v1; agent says "60 days" |
| FP01 | Wrong tool | 3 | Never calls the eligibility tool; decides from policy text instead |

Every failed run carries a hidden **label**: the injected pattern and the true root step. The label is used **only** by
`validate.py` to measure accuracy. The detectors and the LLM **never see it**.

A run is marked failed by plain rules (`compute_outcome`): an expected fact is missing or wrong, a forbidden tool was
called, or the run hit the step limit.

---

## 7. The graph: what is stored in Neo4j

The schema deliberately mirrors **Neo4j Agent Memory's reasoning-trace model** (ReasoningTrace → ReasoningStep →
ToolCall → Tool), extended with evidence, claims, ground truth and diagnoses.

**Main path of one run:**

```
(Session)-[:HAS_RUN]->(ReasoningTrace)-[:FOR_TASK]->(Task)-[:HAS_GROUND_TRUTH]->(GroundTruth)
(ReasoningTrace)-[:STARTED_BY]->(UserRequest)
(ReasoningTrace)-[:HAS_STEP]->(ReasoningStep)-[:NEXT]->(ReasoningStep)
(ReasoningStep)-[:USES_TOOL]->(ToolCall)-[:INSTANCE_OF]->(Tool)
(ToolCall)-[:HAS_ARG]->(Argument)-[:REFERS_TO]->(Entity)
(ToolCall)-[:RETURNED]->(Observation)-[:RAISED]->(Error)
(Observation)-[:YIELDED]->(Evidence)-[:ABOUT]->(Entity)
(ReasoningStep)-[:CITES]->(Evidence)
(ReasoningTrace)-[:PRODUCED]->(Answer)-[:ASSERTS]->(Claim)-[:SUPPORTED_BY]->(Evidence)
(GroundTruth)-[:EXPECTS_FACT]->(Fact)
(GroundTruth)-[:EXPECTS_ENTITY]->(Entity)
(ReasoningTrace)-[:HAS_DIAGNOSIS]->(Diagnosis)-[:ROOT_CAUSE]->(ReasoningStep)
(Diagnosis)-[:CLASSIFIED_AS]->(FailurePattern)
(Diagnosis)-[:CITES_EVIDENCE]->(Evidence)
```

**Key ideas:**

- **Shared hubs.** Every `ToolCall` points to one `Tool` node, every argument to one `Entity` node. That's why
  cross-run questions ("which tool fails most?") are one query.
- **Provenance edges.** A `Claim` is linked to the exact `Evidence` it rests on, and evidence to the entities it is
  about. "Is this claim supported, and by what?" is a path, not a guess.
- **Ground truth in the graph.** Expected facts and entities are nodes, so "what the agent said vs what was true" is a
  join.
- **Diagnoses are nodes.** Verdicts are stored and linked, so they can be counted, compared and reused.

**Size:** 36 runs, 116 steps, 80 tool calls, 72 evidence nodes, 29 entities, 14 failure patterns, 24 diagnoses —
about 1,000 nodes. Loading is **idempotent** (MERGE everywhere): loading twice changes nothing.

---

## 8. The detectors: how we spot mistakes

Each detector is **one parameterised Cypher query** for one run. It returns hits with a pattern, a step, a severity
(1 low … 3 decisive) and a human-readable detail.

| Detector | Pattern | Severity | The graph signal |
|---|---|---|---|
| `ignored_error` | FP04 | 3 | A tool returned an `Error`, no later step retried it successfully or escalated, and the answer doesn't acknowledge it (`NOT EXISTS {…}`) |
| `invalid_args` | FP02 | 3 | An `Argument` with `valid=false` (schema violation) |
| `wrong_entity` | FP03 | 3 | An argument `REFERS_TO` an entity of the expected type but not the expected one |
| `wrong_tool_plan` | FP01 | 3 | A required tool was **never called** and an unplanned tool was used instead |
| `unsupported_claim` | FP05 | 3 | A `Claim` with **no** `SUPPORTED_BY` edge (root = the answer step) |
| `stale_evidence` | FP07 | 3 if a claim rests on it, else 2 | A step `CITES` evidence with `stale=true` |
| `retry_loop` | FP10 | 2 | 3+ calls with the same tool and identical argument hash |
| `missing_required_step` | FP06 / FP11 | 2 / 1 | A write tool before a successful required check / required tools never called |
| `forbidden_tool` | FP12 | 2 | A tool listed in the ground truth's `forbidden_tools` was called |

Example — the "ignored error" check, the heart of the demo:

```cypher
MATCH (r:ReasoningTrace {id: $run_id})-[:HAS_STEP]->(st)-[:USES_TOOL]->(tc)
      -[:RETURNED]->(:Observation)-[:RAISED]->(err:Error)
MATCH (r)-[:PRODUCED]->(ans:Answer)
WHERE NOT EXISTS {
  MATCH (r)-[:HAS_STEP]->(later)-[:USES_TOOL]->(tc2)
  WHERE later.idx > st.idx AND ((tc2.tool_name = tc.tool_name AND tc2.status = 'ok')
        OR tc2.tool_name = 'escalate_to_human') }
  AND coalesce(ans.acknowledges_limitation, false) = false
RETURN st.idx AS step, tc.tool_name AS tool, err.code AS error
```

All 9 detectors run **in parallel** (each is one round trip to Aura), so a full investigation takes ~1–2 seconds.

---

## 9. Finding the root cause

Many steps get flagged in a failed run. The question is **which one, if fixed, would have prevented the failure** — the
definition used by the Who&When research benchmark.

Rules (`forensics/divergence.py`):

1. If there is an **ignored error** (FP04), the error step is the root. Anything the agent did afterwards (stale policy,
   unsafe refund) is a consequence.
2. Otherwise the root is the **earliest decisive hit** (severity 3; wrong entity always counts as decisive).
3. If several patterns hit the same step, a fixed priority decides
   (FP04 > FP02 > FP03 > FP01 > FP07 > FP05 > …).
4. Everything flagged later is listed as **symptoms** ("contributing").

**Confidence:** 0.9 when two or more detectors agree on the root step, 0.7 when one does, 0.4 otherwise.

---

## 10. The judge: rules + LLM

**Principle: rules narrow the field, the LLM decides and explains.** (The same idea Microsoft's AgentRx research uses:
constraint checks first, LLM judgement second — it improved step localisation by 23.6 points over pure prompting.)

1. **Rules verdict — always computed.** Built from the detector hits: root step, pattern, confidence, an explanation
   template filled with the step, tool, error and evidence, the counterfactual, and the fix from the pattern's
   `fix_template`. Works with no LLM at all.
2. **LLM judge — optional.** gpt-4o-mini (via the GraphAcademy workshop proxy) receives a compact timeline, the detector
   hits, the claim verdicts and the rules candidate. Strict guardrails:
   - it sees **observable records only** — never the injected label;
   - trace text is wrapped in `<trace_data>` and declared **untrusted** (prompt-injection defence);
   - `pattern_code` must be one of the detected candidates, `root_step_idx` must be a real step — otherwise its answer is
     **discarded** and the rules verdict is used;
   - if it disagrees with the rules on the root step, its confidence is capped at 0.6 and the disagreement is flagged.
3. **What the LLM is allowed to change:** the root choice (among candidates) and the **narrative explanation**.
   Everything checkable stays deterministic: symptoms, cited evidence IDs, the counterfactual and the fix always come
   from the rules.
4. **Cache.** LLM verdicts are cached in `data/judge_cache/{run}.json` (committed to git), so demos are instant, stable
   and don't depend on the network. The verdict card shows `source: llm+rules` or `source: rules`.

---

## 11. The UI, page by page

Start it with `.\run.ps1 ui` → http://localhost:8501

**Runs** — headline numbers (36 runs, 24 failed, 24 diagnosed), a table of runs with 🟢/🔴 status, the customer request
and why it failed (e.g. `MISMATCH:refund_eligible;FORBIDDEN:issue_refund`). Pick a run → "Open in Run detail".

**Run detail** — the main demo page.
- **Left: the timeline graph.** One box per step, left to right.
  Colours: grey = normal step · amber = symptom · **red = root cause** · blue notes = evidence (dark blue = cited by the
  verdict, `[STALE]` marked) · purple = ground truth · green/red edge from the answer = matches / contradicts the truth ·
  **dashed box = what the agent should have done**.
- **Right:** user request, final answer, claims-vs-ground-truth table, and the **🔍 Investigate** button.
- After Investigate: the verdict card — pattern, root step, confidence, source; *what happened / why*; *what it should
  have done*; *fix*; symptoms; cited evidence; and the cross-fleet line.

**Apply fix & re-run (human-in-the-loop)** — after a verdict, the **🛠 Apply fix & re-run** button opens a confirmation
dialog that shows the guardrail (e.g. *"Retry a failed tool once; if it still fails, escalate"*). Nothing happens until
the user clicks **Approve**. Then the agent is re-run on the same customer request with the guardrail, the replay is
written to Neo4j as a separate run (`run_017_fix`) linked by `(:ReasoningTrace)-[:REPLAY_OF]->(:ReasoningTrace)`, and the
same 9 detectors re-check it. Result for run_017, run_087 and run_066: **the replay passes — all facts match, 0 decisive
hits.** The original run is never modified, and replays are excluded from run lists and fleet statistics.

**Fleet** — the big number (*check_refund_eligibility · UPSTREAM_TIMEOUT — ignored in 7 of 8 runs*), accuracy
(100% / 100% on labelled synthetic runs), failures by pattern (bar chart), a tools table (calls, failed calls, error %,
failed runs), and an ignored-errors table.

Footer on every page: *"We analyse observable agent behaviour only. Diagnoses are root-cause candidates, measured on
synthetic labelled runs."*

---

## 12. The numbers we can quote

| Number | Value | How to say it |
|---|---|---|
| Runs recorded | 36 (12 ✓, 24 ✗) | "36 recorded agent runs, 24 failed" |
| Graph size | ~1,000 nodes; 116 steps, 80 tool calls | "Every step, call and claim is a node" |
| Headline pattern | 8 timeouts → 7 ignored | "This tool timed out in 8 runs and the agent ignored it in 7" |
| Root-step accuracy | 24 / 24 (100%) | "On our labelled synthetic runs we find the injected root step every time" |
| Pattern accuracy | 24 / 24 (100%) | — |
| Speed | ~1–2 s per investigation; ~11 s for all 24 | "Investigate is live against Aura" |
| Research baseline | 11% (TRAIL), 14.2% (Who&When) | "LLMs alone on raw traces find the failing step 11–14% of the time" |

⚠️ **Always pair 100% with the caveat:** it is an **upper bound on synthetic data we generated ourselves**.

---

## 13. Why a graph and not logs

1. **Causality is a path.** Wrong refund ← claim ← stale evidence ← policy search ← ignored timeout. In Neo4j that is a
   chain of edges you can query and draw.
2. **Absence is queryable.** "No retry after an error", "no eligibility check before a refund", "a claim with no
   supporting evidence" are each one `NOT EXISTS { … }` pattern. In logs, absence is invisible.
3. **Shared hubs make cross-run questions trivial.** All calls point to the same `Tool` node, all arguments to the same
   `Entity` nodes → "which tool fails most, in which runs was it ignored?" is one query.
4. **Hidden mistakes become visible.** run_087's answer is fully "grounded" — only the `REFERS_TO` edge to the wrong
   Maria Lopez reveals the error.
5. **Diagnoses become reusable knowledge.** They are nodes linked to patterns and evidence, so new failures can be
   matched against past ones.

---

## 14. The judging criteria and our answers

**1. Business impact** — Agents are entering support, finance and ops, and they fail silently: our demo agent refunded
**$189 on a final-sale item** while every dashboard was green. Engineers today read traces one by one. AutopsyGraph
gives the first decisive mistake, the proof, how often it recurs and the fix — *"one guardrail removes 7 failures"* —
turning hours of log reading into a prioritised fix list.

**2. Innovative use of graphs and Gen AI** — The cause of a wrong answer is literally a path in the graph, and missing
behaviour ("no retry") is a `NOT EXISTS` query. Shared tool and entity nodes make fleet patterns one query, and the
wrong-customer bug is only visible by following an argument edge. GenAI is used where it is strong: the graph narrows
the candidates, the LLM picks among them and explains — because LLMs alone find the failing step only 11–14% of the time.

**3. Solution scalability** — The schema mirrors Neo4j Agent Memory's reasoning traces and maps onto OpenTelemetry GenAI
spans (`invoke_agent` → run, `execute_tool` → ToolCall), so any agent framework can feed it. Detectors are plain
parameterised Cypher: a new failure pattern = one new query. Loading is idempotent; diagnoses are stored for reuse; Aura
handles storage growth.

**4. Demo functionality** — Everything is live on Neo4j Aura: 36 runs, 24 diagnosed, Investigate in ~1–2 seconds with
evidence, fix and fleet context, and 24/24 root-cause accuracy on labelled synthetic runs.

---

## 15. Tough questions and honest answers

**"Isn't this just LangSmith / Langfuse / Phoenix?"**
They are great trace stores, and LangSmith even advertises automatic root-cause detection. What we add is provenance as
a graph (claim ↔ evidence ↔ tool call ↔ entity), comparison with ground truth, and Cypher queries across all runs. We
would ingest from them, not replace them.

**"100% accuracy? That's suspicious."**
Yes — and we say so. We generated the failures ourselves, so it's an upper bound on clean synthetic data. Published
methods on real, long traces score far lower (11–14%), which is exactly why we use graph checks to narrow the search
instead of asking an LLM to read raw logs.

**"Does it work without ground truth?"**
Partly. Ignored errors, unsupported claims, stale evidence, retry loops and unsafe writes need no ground truth. Wrong
facts and wrong entities need a reference (expected facts or entities).

**"Can you see what the model was thinking?"**
No. We analyse observable behaviour only. "Rationale" fields are text the agent emitted, not its hidden reasoning. Every
verdict cites tool outputs.

**"Is the agent real?"**
It's a scripted agent so that we have exact labels. Plugging in a real agent means emitting the same trace JSON (or
mapping OpenTelemetry spans) — the detectors don't care who produced the trace.

**"What does the LLM actually do?"**
It chooses the root among graph-proven candidates and writes the explanation. It can't invent a pattern or a step, and
evidence, symptoms and fixes stay deterministic. If it fails or misbehaves, the rules verdict is used.

**"How does it scale to millions of runs?"**
Detectors are per-run indexed queries (constraints on ids, indexes on `(run_id, idx)`, `success`, `status`); fleet queries
are aggregations over shared hubs. Next steps would be batching detectors and streaming ingestion from OpenTelemetry.

**"Why Neo4j specifically?"**
Variable-length paths, `NOT EXISTS` subqueries, shared nodes and Aura's managed service make "follow the evidence" both
natural to write and fast to run. And the schema extends Neo4j's own Agent Memory model.

---

## 16. What we do NOT claim

- ❌ "Reads the model's mind" / "understands intent" — we analyse **observable** behaviour.
- ❌ "Proves causality" — diagnoses are **root-cause candidates** with a confidence score.
- ❌ "Works on any agent out of the box" — today it reads our trace format; real-world ingestion is the next step.
- ❌ "100% accurate" without the caveat — always add **"on labelled synthetic runs"**.
- All customer data is synthetic.

---

## 17. How to run everything

Everything lives in `C:\Users\User\projects\autopsygraph` (GitHub: `KanekiH4iSE/autopsygraph`, private).

```powershell
cd C:\Users\User\projects\autopsygraph
.\run.ps1 ping        # check Aura connection → prints "5.27-aura"
.\run.ps1 test        # 9 tests
.\run.ps1 ui          # start the app → http://localhost:8501
```

| Command | What it does | Time |
|---|---|---|
| `.\run.ps1 gen` | Regenerate the 36 traces (deterministic) | 1 s |
| `.\run.ps1 reset` | Wipe the graph and apply the schema | ~10 s |
| `.\run.ps1 load` | Load traces into Aura (idempotent) | ~1 min |
| `.\run.ps1 detect` | Investigate all failed runs, write Diagnoses | ~11 s |
| `.\run.ps1 validate` | Accuracy vs labels → `data/metrics.json` | ~2 s |
| `.\run.ps1 all` | gen → reset → load → detect → validate | ~2 min |

**Configuration (`.env`, never shown on screen, never committed):** `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`,
`NEO4J_DATABASE`, `OPENAI_API_KEY` + `OPENAI_BASE_URL` (workshop proxy), `LLM_ENABLED`.
With `LLM_ENABLED=false` everything still works (rules-only verdicts).

**Workshop LLM gotcha:** the GraphAcademy proxy goes **idle** and returns 403 unless a lesson of the course is open in
the browser. The demo doesn't depend on it — all 24 LLM verdicts are cached.

---

## 18. The 2-minute pitch script

| Time | Screen | Say |
|---|---|---|
| 0:00–0:15 | Slide 1 | "Agents fail quietly. Every call returned 200, the answer sounded confident — and the customer got a refund they were never entitled to." |
| 0:15–0:30 | Runs | "We record every run of a support agent in Neo4j as a graph: request, tool calls, arguments, outputs, evidence, claims. 36 runs, 24 failed." |
| 0:30–1:10 | run_017 → Investigate | "The agent refunded $189 for a final-sale tent. Where did it go wrong? Not at step 4, the refund. The root cause is step 2: the eligibility check timed out, the agent neither retried nor escalated, and fell back to a superseded 60-day policy. The refund is just the symptom — and every conclusion points to a node in the graph." |
| 1:10–1:35 | Fleet | "Across all runs, one query: this tool timed out in 8 runs, and in 7 the agent silently ignored it. That's a missing rule, not bad luck. Three fixes: a prompt rule, a code guardrail, filtering superseded policies." |
| 1:35–2:00 | Slide 3 | "On labelled synthetic runs we find the root-cause step 24 out of 24 times — an upper bound, since LLMs alone manage 11–14% on real traces. We analyse what the agent did, not what it thought." |

**Before going on stage:** click Investigate once on run_017 and run_087 (warms the app cache), open the Fleet page once,
zoom the browser (Ctrl +).

---

## 19. If something breaks on stage

| Problem | Do this |
|---|---|
| Aura not responding | console.neo4j.io → Instance01 → Resume; wait 1–2 min; `.\run.ps1 ping` |
| Graph data looks wrong | `.\run.ps1 reset` then `.\run.ps1 load` then `.\run.ps1 detect` |
| Streamlit frozen | Ctrl+C in its terminal, `.\run.ps1 ui` again |
| Wifi down | Phone hotspot |
| Nothing works | Play the backup video, or show the 4 saved Cypher queries in Aura Query (see `TEAM_PLAN.md` §6) |

---

## 20. Where to take it next

- **Real agents in:** a `@record_tool` decorator for Python agents; OpenTelemetry GenAI / OpenAI Agents SDK / LangSmith
  importers (`invoke_agent` → run, `execute_tool` → ToolCall).
- **Agents out (MCP):** expose `list_failed_runs`, `get_run_timeline`, `diagnose_run`, `ignored_errors` as an MCP server,
  or use `mcp-neo4j-cypher --read-only`, so Claude Code / Codex / Cursor can ask the graph "why did run X fail?".
- **More patterns:** contradictions between sources, prompt injection via tool output, ignored user constraints.
- **Similarity:** embed diagnoses and match new failures to past ones (Agent Memory's `get_similar_traces` idea).
- **Counterfactual replay:** re-run the agent with the fix applied and prove the failure disappears.

---

## 21. File map

| Path | What it is |
|---|---|
| `PROJECT_GUIDE.md` | This document |
| `TEAM_PLAN.md` | Roles, timeline, demo script, fallback Cypher queries |
| `CLAUDE.md` | Build spec for the coding agent |
| `DECISIONS.md` | One line per non-obvious decision |
| `run.ps1` | Command runner (Makefile replacement) |
| `codex-workshop.ps1` | Starts Codex CLI on the workshop model |
| `datagen/world.py` | Seeded shop: customers, products, orders, shipments, policies |
| `datagen/tools.py` | Mock tools + JSON schemas + argument validation |
| `datagen/tasks.py` | Task templates, paraphrases, ground truth, outcome rule |
| `datagen/patterns.py` | Correct and buggy agent scripts (trace builder) |
| `datagen/generate.py` | Builds the 36 runs, incl. hero runs 003 / 017 / 066 / 087 |
| `graph/models.py` | Pydantic models of the trace JSON |
| `graph/schema.cypher` | Constraints and indexes |
| `graph/loader.py` | Idempotent JSON → Neo4j loader, 14 failure patterns |
| `graph/db.py` | Driver + read/write helpers; `python -m graph.db` pings Aura |
| `forensics/detectors.py` | The 9 Cypher detectors |
| `forensics/divergence.py` | Root-cause selection |
| `forensics/claims.py` | Claims vs ground truth, run lists |
| `forensics/judge.py` | Rules verdict + LLM judge with guardrails and cache |
| `forensics/engine.py` | Investigation pipeline, Diagnosis write-back, fleet queries |
| `ui/app.py` | Streamlit app |
| `validate.py` | Accuracy vs injected labels |
| `tests/` | Dataset and detector tests |
| `data/` | Generated world, tasks, traces, metrics, judge cache |

---

## 22. Glossary

| Term | Meaning |
|---|---|
| **Agent** | An LLM-driven program that calls tools to complete a task |
| **Run / trace** | One complete attempt by the agent to handle one request |
| **Step** | One action in a run: a tool call or the final answer |
| **Tool call** | The agent invoking a function (e.g. `get_order`) with arguments |
| **Observation** | What the tool returned (or the error it raised) |
| **Evidence** | A fact taken from an observation that the agent can rely on |
| **Claim** | A statement in the final answer (e.g. `refund_eligible=true`) |
| **Ground truth** | The correct facts, entities and allowed tools for a task, computed by code |
| **Stale evidence** | Evidence from a superseded document version (policy v1) |
| **Root cause** | The earliest step that, if corrected, would have prevented the failure |
| **Symptom / contributing** | A flagged step after the root cause, caused by it |
| **Failure pattern (FPxx)** | A named type of mistake, from a taxonomy of 14 |
| **Diagnosis** | The stored verdict for a failed run |
| **Fleet** | All runs together, for cross-run patterns |
| **Cypher** | Neo4j's graph query language |
| **Aura** | Neo4j's managed cloud database |
| **MCP** | Model Context Protocol — a standard way for AI agents to call external tools |
| **Idempotent** | Running it twice gives the same result |
