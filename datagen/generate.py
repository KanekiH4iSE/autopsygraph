"""Generate the 36-run labelled dataset (12 success, 24 failing) deterministically.

Hero runs (run_003, run_017, run_066, run_087) are fixed here instead of a separate hero.py.
Usage: python -m datagen.generate
"""
from __future__ import annotations

import json
import random
from datetime import date

from datagen import patterns as P
from datagen.tasks import compute_outcome, make_task, request_text
from datagen.tools import TOOL_SCHEMAS, Tools
from datagen.world import DATA, write
from graph.models import Trace

HERO_IDS = {"run_003", "run_017", "run_066", "run_087"}


def _pools(tl: Tools) -> dict:
    """Order pools computed from the world."""
    today = date.fromisoformat(tl.w["today"])
    inelig, elig, delayed, ontime = [], [], [], []
    for o in tl.w["orders"]:
        if o["delivered_at"] and o["id"] not in ("ORD-1042", "ORD-1043", "ORD-1150"):
            res = tl.check_refund_eligibility(o["id"], o["sku"])
            (elig if res["refund_eligible"] == "true" else inelig).append(o["id"])
        s = tl.get_shipment(o["id"])
        if o["id"] not in ("ORD-1107", "ORD-1150", "ORD-1188"):
            (delayed if s["delay_days"] > 5 else ontime).append(o["id"])
    assert today and inelig and elig and delayed and ontime
    return {"inelig": inelig, "elig": elig, "delayed": delayed, "ontime": ontime}


def plan(tl: Tools) -> list[tuple]:
    """(run_id or None, builder name, template, params, kwargs, variant). None ids get assigned later."""
    pool = _pools(tl)
    ine, eli, dly, ont = pool["inelig"], pool["elig"], pool["delayed"], pool["ontime"]
    rows = [
        # heroes
        ("run_003", "success", "T07", {"order": "ORD-1042"}, {"with_product": True}, 0),
        ("run_017", "fp04", "T08", {"order": "ORD-1042"}, {"stale": True}, 0),
        ("run_066", "fp05", "T12", {"order": "ORD-1107"}, {}, 0),
        ("run_087", "fp03", "T02", {"city": "Denver"}, {}, 0),
        # 11 more successes
        (None, "success", "T07", {"order": eli[0]}, {}, 1),
        (None, "success", "T24", {"order": "ORD-1043"}, {}, 0),
        (None, "success", "T08", {"order": eli[1]}, {}, 1),
        (None, "success", "T08", {"order": ine[0]}, {}, 2),
        (None, "success", "T12", {"order": dly[0]}, {}, 1),
        (None, "success", "T12", {"order": ont[0]}, {}, 2),
        (None, "success", "T15", {}, {}, 0),
        (None, "success", "T18", {"order": "ORD-1188"}, {}, 0),
        (None, "success", "T21", {"sku": "SKU-JKT-05"}, {}, 0),
        (None, "success", "T02", {"city": "Austin"}, {}, 1),
        (None, "success", "T07", {"order": ine[1]}, {"timeout_then_retry": True}, 2),
        # FP04 x6 more (2 stale + 4 current policy)
        (None, "fp04", "T08", {"order": ine[2]}, {"stale": True}, 1),
        (None, "fp04", "T07", {"order": ine[3]}, {"stale": True}, 1),
        (None, "fp04", "T08", {"order": ine[4]}, {"stale": False}, 2),
        (None, "fp04", "T07", {"order": ine[5]}, {"stale": False}, 2),
        (None, "fp04", "T08", {"order": ine[0]}, {"stale": False}, 3),
        (None, "fp04", "T07", {"order": "ORD-1042"}, {"stale": False}, 3),
        # FP03 x5 more
        (None, "fp03", "T02", {"city": "Austin"}, {}, 0),
        (None, "fp03", "T02", {"city": "Denver"}, {}, 1),
        (None, "fp03", "T02", {"city": "Austin"}, {}, 2),
        (None, "fp03", "T02", {"city": "Denver"}, {}, 2),
        (None, "fp03", "T02", {"city": "Austin"}, {}, 3),
        # FP05 x4 more
        (None, "fp05", "T12", {"order": dly[0]}, {}, 2),
        (None, "fp05", "T12", {"order": dly[-1]}, {}, 3),
        (None, "fp05", "T15", {}, {}, 1),
        (None, "fp05", "T15", {}, {}, 2),
        # FP07 x3
        (None, "fp07", "T15", {}, {}, 1),
        (None, "fp07", "T15", {}, {}, 2),
        (None, "fp07", "T15", {}, {}, 3),
        # FP01 x3
        (None, "fp01", "T07", {"order": "ORD-1042"}, {}, 1),
        (None, "fp01", "T07", {"order": ine[2]}, {}, 2),
        (None, "fp01", "T07", {"order": ine[4]}, {}, 3),
    ]
    rng = random.Random(7)
    free = [n for n in range(1, 121) if f"run_{n:03d}" not in HERO_IDS]
    ids = sorted(rng.sample(free, sum(1 for r in rows if r[0] is None)))
    out, k = [], 0
    for r in rows:
        if r[0] is None:
            r = (f"run_{ids[k]:03d}",) + r[1:]
            k += 1
        out.append(r)
    return out


BUILDERS = {"success": P.success_run, "fp04": P.fp04_ignored_error, "fp03": P.fp03_wrong_entity,
            "fp05": P.fp05_hallucination, "fp07": P.fp07_stale_context, "fp01": P.fp01_wrong_tool}


def generate() -> list[dict]:
    """Build, validate and write all traces plus tasks.json and tools.json."""
    world = write()
    tl = Tools(world)
    traces_dir = DATA / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    for old in traces_dir.glob("*.json"):
        old.unlink()
    tasks: dict[str, dict] = {}
    traces = []
    for run_id, kind, template, params, kwargs, variant in plan(tl):
        task = make_task(template, tl, **params)
        req = request_text(template, variant, tl, params)
        trace = BUILDERS[kind](run_id, task, req, tl, **kwargs)
        Trace.model_validate(trace)
        ok, reasons = compute_outcome(trace, task)
        if ok != (kind == "success"):
            raise AssertionError(f"{run_id} ({kind}) outcome={ok} reasons={reasons}")
        tasks[task["task_id"]] = task
        traces.append(trace)
        (traces_dir / f"{run_id}.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
    (DATA / "tasks.json").write_text(json.dumps(sorted(tasks.values(), key=lambda t: t["task_id"]), indent=2),
                                     encoding="utf-8")
    (DATA / "tools.json").write_text(json.dumps(TOOL_SCHEMAS, indent=2), encoding="utf-8")
    return traces


if __name__ == "__main__":
    ts = generate()
    fails = [t for t in ts if t["label"]["injected_pattern"]]
    print(f"{len(ts)} runs, {len(fails)} failing")
