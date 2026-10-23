"""Scripted ShopBot policies: one correct policy per task plus one buggy policy per failure pattern.

Every function returns a trace dict (graph.models.Trace shape) with its injected label.
"""
from __future__ import annotations

from datagen.tools import Tools, validate_arg

REFERS = {"order_id": "order", "sku": "product", "customer_id": "customer"}


class TraceBuilder:
    """Accumulates steps for one run. Evidence ids are {run}-e{step idx}[_{k}]."""

    def __init__(self, run_id: str, task: dict, request: str):
        self.run_id, self.task, self.request = run_id, task, request
        self.steps: list[dict] = []

    @property
    def next_idx(self) -> int:
        return len(self.steps) + 1

    def call(self, tool: str, args: dict, *, rationale: str | None = None, status: str = "ok",
             error: dict | None = None, summary: str = "", evidence: list[tuple] = (),
             attempt: int = 1, latency_ms: int = 120) -> list[str]:
        """Record a tool step. evidence = [(text, about_keys, stale)]. Returns evidence ids."""
        idx = self.next_idx
        arg_list = []
        for name, value in args.items():
            valid, violation = validate_arg(tool, name, value)
            ref = f"{REFERS[name]}:{value}" if name in REFERS and valid else None
            arg_list.append({"name": name, "value": value, "valid": valid, "violation": violation, "refers_to": ref})
        ev_ids, evs = [], []
        for k, (text, about, stale) in enumerate(evidence):
            eid = f"{self.run_id}-e{idx}" + (f"_{k}" if k else "")
            ev_ids.append(eid)
            evs.append({"id": eid, "text": text, "source_type": "tool", "stale": stale, "about": list(about)})
        obs = {"id": f"{self.run_id}-o{idx}", "status": "error" if error else "ok", "summary": summary, "error": error}
        self.steps.append({"idx": idx, "kind": "tool", "stated_rationale": rationale,
                           "tool_call": {"id": f"{self.run_id}-c{idx}", "tool": tool, "attempt": attempt,
                                         "status": status, "latency_ms": latency_ms, "args": arg_list},
                           "observation": obs, "evidence": evs})
        return ev_ids

    def build(self, text: str, claims: list[tuple], *, ack: bool = False, pattern: str | None = None,
              root: int | None = None, contributing: list[str] = ()) -> dict:
        """Close the run with an answer step. claims = [(key, value, [evidence ids])]."""
        self.steps.append({"idx": self.next_idx, "kind": "answer", "stated_rationale": None,
                           "tool_call": None, "observation": None, "evidence": []})
        num = self.run_id.split("_")[1]
        return {"run_id": self.run_id, "session_id": f"sess_{num}", "task_id": self.task["task_id"],
                "agent": {"version": "1.3.0", "prompt_version": "p4", "model": "scripted"},
                "user_request": self.request, "steps": self.steps,
                "final_answer": {"text": text, "acknowledges_limitation": ack,
                                 "claims": [{"key": k, "value": v, "supported_by": list(s)} for k, v, s in claims]},
                "label": {"injected_pattern": pattern, "root_cause_step": root, "contributing": list(contributing)}}


# ---------- reusable observed steps ----------

def s_get_order(tb: TraceBuilder, tl: Tools, oid: str) -> list[str]:
    o = tl.get_order(oid)
    p = tl.get_product(o["sku"])
    when = f"delivered {o['delivered_at']}" if o["delivered_at"] else "in transit"
    text = f"{oid} has {o['sku']} ${p['price']:.0f}, {when}"
    return tb.call("get_order", {"order_id": oid}, rationale="Look up the order.", summary=text,
                   evidence=[(text, [f"order:{oid}", f"product:{o['sku']}"], False)])


def s_get_product(tb: TraceBuilder, tl: Tools, sku: str) -> list[str]:
    p = tl.get_product(sku)
    text = f"{sku} {p['name']} ${p['price']:.2f}" + (" is final sale" if p["final_sale"] else "")
    return tb.call("get_product", {"sku": sku}, rationale="Check the product.", summary=text,
                   evidence=[(text, [f"product:{sku}"], False)])


def s_check(tb: TraceBuilder, tl: Tools, oid: str, attempt: int = 1) -> tuple[list[str], dict]:
    sku = tl.get_order(oid)["sku"]
    res = tl.check_refund_eligibility(oid, sku)
    text = ("Eligible: " if res["refund_eligible"] == "true" else "Not eligible: ") + res["reason"]
    ids = tb.call("check_refund_eligibility", {"order_id": oid, "sku": sku}, rationale="Verify eligibility.",
                  summary=text, attempt=attempt, evidence=[(text, [f"order:{oid}", f"product:{sku}"], False)])
    return ids, res


def s_check_timeout(tb: TraceBuilder, tl: Tools, oid: str) -> None:
    sku = tl.get_order(oid)["sku"]
    tb.call("check_refund_eligibility", {"order_id": oid, "sku": sku}, rationale="Verify eligibility.",
            status="timeout", latency_ms=30000, summary="UPSTREAM_TIMEOUT",
            error={"code": "UPSTREAM_TIMEOUT", "message": "Eligibility service did not respond in 30s",
                   "retryable": True})


def s_policy(tb: TraceBuilder, tl: Tools, query: str, version: str | None = None,
             rationale: str = "Check the policy.") -> list[str]:
    hits = tl.search_policy(query, version)
    p = hits[0]
    stale = p["superseded_by"] is not None
    text = f"{p['doc_id']} {p['version']}: {p['text']}"
    return tb.call("search_policy", {"query": query}, rationale=rationale, summary=text,
                   evidence=[(text, [f"policy:{p['doc_id']}@{p['version']}"], stale)])


def s_shipment(tb: TraceBuilder, tl: Tools, oid: str) -> list[str]:
    s = tl.get_shipment(oid)
    o = tl.get_order(oid)
    if s["status"] == "delivered":
        text = f"{oid} delivered {o['delivered_at']}" + (f", {s['delay_days']} days late" if s["delay_days"] else "")
    else:
        text = f"{oid} in transit, delayed {s['delay_days']} days"
    return tb.call("get_shipment", {"order_id": oid}, rationale="Check the shipment.", summary=text,
                   evidence=[(text, [f"order:{oid}"], False)])


def s_find_maria(tb: TraceBuilder, tl: Tools) -> list[str]:
    hits = tl.find_customer(name="Maria Lopez")
    text = "Two Maria Lopez: " + ", ".join(f"{c['id']} {c['city']}" for c in hits)
    return tb.call("find_customer", {"name": "Maria Lopez"}, rationale="Find the customer.", summary=text,
                   evidence=[(text, [f"customer:{c['id']}" for c in hits], False)])


def s_list_orders(tb: TraceBuilder, tl: Tools, cid: str) -> tuple[list[str], str]:
    latest = sorted(tl.list_orders(cid), key=lambda o: o["id"])[-1]["id"]
    text = f"{cid} latest order {latest}"
    ids = tb.call("list_orders", {"customer_id": cid}, rationale="List the customer's orders.", summary=text,
                  evidence=[(text, [f"customer:{cid}", f"order:{latest}"], False)])
    return ids, latest


# ---------- correct policies ----------

def success_run(run_id: str, task: dict, request: str, tl: Tools, *, with_product: bool = False,
                timeout_then_retry: bool = False) -> dict:
    """The correct plan for each task template."""
    tb, t, p = TraceBuilder(run_id, task, request), task["template"], task["params"]
    if t in ("T07", "T24", "T08"):
        oid = p["order"]
        s_get_order(tb, tl, oid)
        if with_product:
            s_get_product(tb, tl, tl.get_order(oid)["sku"])
        if timeout_then_retry:
            s_check_timeout(tb, tl, oid)
            ev, res = s_check(tb, tl, oid, attempt=2)
        else:
            ev, res = s_check(tb, tl, oid)
        ok = res["refund_eligible"] == "true"
        if t == "T08" and ok:
            o = tl.get_order(oid)
            price = tl.get_product(o["sku"])["price"]
            tb.call("issue_refund", {"order_id": oid, "sku": o["sku"], "amount": price},
                    rationale="Eligible, so process the refund.", summary=f"Refund issued for ${price:.0f}",
                    evidence=[(f"Refund issued for ${price:.0f}", [f"order:{oid}"], False)])
            text = f"Done - your refund of ${price:.0f} is on its way."
        elif ok:
            text = "Yes, that item is still within the 30-day refund window."
        else:
            text = f"Sorry, that item isn't refundable ({res['reason'].replace('_', ' ')})."
        return tb.build(text, [("refund_eligible", res["refund_eligible"], ev)])
    if t == "T12":
        e1 = s_shipment(tb, tl, p["order"])
        e2 = s_policy(tb, tl, "delay compensation")
        credit = task["expected_facts"]["credit_usd"]
        text = ("Sorry for the delay - you get a $10 credit." if credit == "10"
                else "Your order is within the normal window, so no credit applies yet.")
        return tb.build(text, [("credit_usd", credit, e1 + e2)])
    if t == "T15":
        e = s_policy(tb, tl, "refund window")
        return tb.build("You can request a refund within 30 days of delivery (final-sale items excluded).",
                        [("window_days", "30", e)])
    if t == "T18":
        e = s_get_order(tb, tl, p["order"])
        st = tl.get_order(p["order"])["status"]
        return tb.build(f"Order {p['order']} is {st.replace('_', ' ')}.", [("order_status", st, e)])
    if t == "T21":
        e = s_get_product(tb, tl, p["sku"])
        price = tl.get_product(p["sku"])["price"]
        return tb.build(f"It costs ${price:.2f}.", [("price", f"{price:.2f}", e)])
    if t == "T02":
        s_find_maria(tb, tl)
        cid = task["expected_entities"][0].split(":")[1]
        e2, latest = s_list_orders(tb, tl, cid)
        e3 = s_shipment(tb, tl, latest)
        st = tl.get_shipment(latest)["status"]
        return tb.build(f"Your latest order {latest} is {st.replace('_', ' ')}.",
                        [("latest_order", latest, e2), ("shipment_status", st, e3)])
    raise ValueError(t)


# ---------- buggy policies ----------

def fp04_ignored_error(run_id: str, task: dict, request: str, tl: Tools, *, stale: bool) -> dict:
    """Eligibility check times out; agent neither retries nor escalates and falls back to policy search."""
    tb, oid = TraceBuilder(run_id, task, request), task["params"]["order"]
    s_get_order(tb, tl, oid)
    root = tb.next_idx
    s_check_timeout(tb, tl, oid)
    pol_idx = tb.next_idx
    ev = s_policy(tb, tl, "refund window", "v1" if stale else None,
                  rationale="Check timed out; I'll use the policy instead.")
    contributing = [f"FP07@{pol_idx}"] if stale else []
    if task["template"] == "T08":
        o = tl.get_order(oid)
        price = tl.get_product(o["sku"])["price"]
        ref_idx = tb.next_idx
        refund_id = "RF-5521" if run_id == "run_017" else f"RF-{5600 + int(run_id.split('_')[1])}"
        tb.call("issue_refund", {"order_id": oid, "sku": o["sku"], "amount": price},
                rationale="Within the window, so refund." if stale else "Policy allows refunds, so refund.",
                summary=f"Refund {refund_id} issued for ${price:.0f}",
                evidence=[(f"Refund {refund_id} issued for ${price:.0f}", [f"order:{oid}"], False)])
        contributing += [f"FP06@{ref_idx}", f"FP12@{ref_idx}"]
        text = f"Done! I've refunded ${price:.0f} (refund {refund_id})."
    else:
        text = "Yes, you can get a refund for that."
    return tb.build(text, [("refund_eligible", "true", ev)], pattern="FP04", root=root, contributing=contributing)


def fp03_wrong_entity(run_id: str, task: dict, request: str, tl: Tools) -> dict:
    """find_customer returns two matches; agent picks the other Maria Lopez without asking."""
    tb = TraceBuilder(run_id, task, request)
    s_find_maria(tb, tl)
    right = task["expected_entities"][0].split(":")[1]
    wrong = "C-019" if right == "C-031" else "C-031"
    root = tb.next_idx
    e2, latest = s_list_orders(tb, tl, wrong)
    e3 = s_shipment(tb, tl, latest)
    st = tl.get_shipment(latest)["status"]
    o = tl.get_order(latest)
    text = (f"Your latest order {latest} was delivered on {o['delivered_at']}." if st == "delivered"
            else f"Your latest order {latest} is {st.replace('_', ' ')}.")
    return tb.build(text, [("latest_order", latest, e2), ("shipment_status", st, e3)],
                    pattern="FP03", root=root)


def fp05_hallucination(run_id: str, task: dict, request: str, tl: Tools) -> dict:
    """Agent answers without consulting the policy; claims have no supporting evidence."""
    tb = TraceBuilder(run_id, task, request)
    if task["template"] == "T12":
        s_shipment(tb, tl, task["params"]["order"])
        root = tb.next_idx
        return tb.build("You're entitled to a 25% refund and free express shipping next time.",
                        [("compensation_due", "true", []), ("credit_usd", "25%_refund", [])],
                        pattern="FP05", root=root, contributing=[f"FP11@{root}"])
    root = tb.next_idx
    return tb.build("You have 90 days to return anything, no questions asked.",
                    [("window_days", "90", [])], pattern="FP05", root=root, contributing=[f"FP11@{root}"])


def fp07_stale_context(run_id: str, task: dict, request: str, tl: Tools) -> dict:
    """search_policy serves superseded v1 (60 days) and the agent relies on it."""
    tb = TraceBuilder(run_id, task, request)
    root = tb.next_idx
    ev = s_policy(tb, tl, "refund window", "v1")
    return tb.build("You can request a refund within 60 days of delivery.", [("window_days", "60", ev)],
                    pattern="FP07", root=root)


def fp01_wrong_tool(run_id: str, task: dict, request: str, tl: Tools) -> dict:
    """Eligibility tool is not used; agent decides from the policy text and answers eligible."""
    tb, oid = TraceBuilder(run_id, task, request), task["params"]["order"]
    e1 = s_get_order(tb, tl, oid)
    root = tb.next_idx
    e2 = s_policy(tb, tl, "refund window", rationale="Search policy to decide eligibility.")
    return tb.build("Yes! It's within our refund window, so it's refundable.",
                    [("refund_eligible", "true", e1 + e2)], pattern="FP01", root=root,
                    contributing=[f"FP09@{root + 1}"])
