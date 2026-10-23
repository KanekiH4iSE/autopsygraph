"""Accuracy of stored diagnoses against the injected labels. Writes data/metrics.json.

Labels are read here only; the engine and the judge never see them.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from graph.db import read

OUT = Path(__file__).resolve().parent / "data" / "metrics.json"


def main() -> dict:
    rows = read("""
        MATCH (r:ReasoningTrace {success: false})
        OPTIONAL MATCH (r)-[:HAS_DIAGNOSIS]->(d:Diagnosis)
        RETURN r.id AS run, r.injected_pattern AS label_pattern, r.label_root_step AS label_step,
               d.pattern_code AS pattern, d.root_step_idx AS step, d.source AS source ORDER BY run""")
    per: dict[str, dict] = {}
    for r in rows:
        p = per.setdefault(r["label_pattern"], {"n": 0, "step": 0, "pattern": 0})
        p["n"] += 1
        p["step"] += int(r["step"] == r["label_step"])
        p["pattern"] += int(r["pattern"] == r["label_pattern"])
    n = len(rows)
    m = {"n": n,
         "root_step_acc": round(sum(p["step"] for p in per.values()) / n, 3) if n else 0,
         "pattern_acc": round(sum(p["pattern"] for p in per.values()) / n, 3) if n else 0,
         "per_pattern": {k: {"n": v["n"], "root_step_acc": round(v["step"] / v["n"], 3),
                             "pattern_acc": round(v["pattern"] / v["n"], 3)} for k, v in sorted(per.items())},
         "sources": sorted({r["source"] for r in rows if r["source"]}),
         "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M")}
    OUT.write_text(json.dumps(m, indent=2), encoding="utf-8")
    print(f"root-step accuracy {m['root_step_acc']:.0%}, pattern accuracy {m['pattern_acc']:.0%} on {n} failed runs")
    for k, v in m["per_pattern"].items():
        print(f"  {k}: n={v['n']} step={v['root_step_acc']:.0%} pattern={v['pattern_acc']:.0%}")
    for r in rows:
        if r["step"] != r["label_step"] or r["pattern"] != r["label_pattern"]:
            print(f"  MISS {r['run']}: label {r['label_pattern']}@{r['label_step']}, got {r['pattern']}@{r['step']}")
    return m


if __name__ == "__main__":
    main()
