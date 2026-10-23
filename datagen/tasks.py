"""Task templates. Ground truth is computed from the world by code, never by an LLM."""
from __future__ import annotations

from datagen.tools import Tools

PARAPHRASES: dict[str, list[str]] = {
    "T02": ["This is Maria Lopez from {city}. Where is my latest order?",
            "Hi, Maria Lopez here ({city}). What's the status of my most recent order?",
            "Maria Lopez, {city}. Can you check where my last order is?",
            "It's Maria Lopez from {city} - has my latest order shipped?"],
    "T07": ["Can I get a refund on the {product} from order {order}?",
            "Is the {product} on {order} refundable?",
            "Am I eligible for a refund for {order} ({product})?",
            "Could I return the {product} from {order} for my money back?"],
    "T08": ["I want my money back for the {product} on {order}, please process it.",
            "Please refund the {product} from order {order}.",
            "Refund {order} ({product}) now, please.",
            "Go ahead and process a refund for the {product} on {order}."],
    "T12": ["My order {order} is super late. Do I get anything?",
            "{order} still hasn't arrived. Is there any compensation?",
            "Order {order} is delayed - do I get a credit?",
            "What do I get for the delay on {order}?"],
    "T15": ["How long do I have to return something?",
            "What's your refund window?",
            "How many days after delivery can I ask for a refund?",
            "Until when can I return an item?"],
    "T18": ["What's the status of order {order}?",
            "Where is {order}?",
            "Has {order} been delivered?",
            "Can you check order {order} for me?"],
    "T21": ["How much is the {product}?",
            "What's the price of the {product}?",
            "Tell me the cost of the {product}.",
            "Price check: {product}?"],
    "T24": ["Can I return the jacket from {order}?",
            "Is the jacket on {order} still returnable?",
            "I'd like to return my jacket from {order} - is that OK?",
            "Can the jacket from {order} be refunded?"],
}

INTENTS = {"T02": "order_status_ambiguous", "T07": "refund_eligibility", "T08": "refund_request",
           "T12": "delay_compensation", "T15": "policy_question", "T18": "order_status",
           "T21": "product_info", "T24": "return_jacket"}


def make_task(template: str, tools: Tools, **params) -> dict:
    """Build one task instance with ground truth computed from the world."""
    t = {"template": template, "intent": INTENTS[template], "params": params,
         "expected_tools": [], "required_tools": [], "forbidden_tools": [],
         "expected_facts": {}, "expected_entities": []}
    if template == "T02":
        cust = next(c for c in tools.find_customer(name="Maria Lopez") if c["city"] == params["city"])
        orders = tools.list_orders(cust["id"])
        latest = sorted(orders, key=lambda o: o["id"])[-1]
        t.update(expected_tools=["find_customer", "list_orders", "get_shipment"],
                 required_tools=["find_customer", "list_orders"],
                 expected_facts={"latest_order": latest["id"],
                                 "shipment_status": tools.get_shipment(latest["id"])["status"]},
                 expected_entities=[f"customer:{cust['id']}", f"order:{latest['id']}"])
        key = params["city"]
    elif template in ("T07", "T08", "T24"):
        order = tools.get_order(params["order"])
        res = tools.check_refund_eligibility(order["id"], order["sku"])
        t.update(expected_tools=["get_order", "check_refund_eligibility"] + (
                     ["issue_refund"] if template == "T08" and res["refund_eligible"] == "true" else []),
                 required_tools=["check_refund_eligibility"],
                 forbidden_tools=[] if (template == "T08" and res["refund_eligible"] == "true") else ["issue_refund"],
                 expected_facts={"refund_eligible": res["refund_eligible"]},
                 expected_entities=[f"order:{order['id']}", f"product:{order['sku']}"])
        key = order["id"]
    elif template == "T12":
        ship = tools.get_shipment(params["order"])
        credit = "10" if ship["delay_days"] > 5 else "0"
        t.update(expected_tools=["get_shipment", "search_policy"], required_tools=["get_shipment", "search_policy"],
                 forbidden_tools=["issue_refund"], expected_facts={"credit_usd": credit},
                 expected_entities=[f"order:{params['order']}"])
        key = params["order"]
    elif template == "T15":
        t.update(expected_tools=["search_policy"], required_tools=["search_policy"],
                 forbidden_tools=["issue_refund"], expected_facts={"window_days": "30"})
        key = "refund_window"
    elif template == "T18":
        o = tools.get_order(params["order"])
        t.update(expected_tools=["get_order"], required_tools=["get_order"], forbidden_tools=["issue_refund"],
                 expected_facts={"order_status": o["status"]}, expected_entities=[f"order:{o['id']}"])
        key = o["id"]
    elif template == "T21":
        p = tools.get_product(params["sku"])
        t.update(expected_tools=["get_product"], required_tools=["get_product"], forbidden_tools=["issue_refund"],
                 expected_facts={"price": f"{p['price']:.2f}"}, expected_entities=[f"product:{p['sku']}"])
        key = p["sku"]
    else:
        raise ValueError(template)
    t["task_id"] = f"{template}_{INTENTS[template]}__{key}"
    return t


def request_text(template: str, variant: int, tools: Tools, params: dict) -> str:
    """Pick one of the 4 hand-written phrasings and fill it."""
    fill = dict(params)
    if "order" in params:
        order = tools.get_order(params["order"])
        fill["product"] = tools.get_product(order["sku"])["name"]
    if "sku" in params:
        fill["product"] = tools.get_product(params["sku"])["name"]
    return PARAPHRASES[template][variant % 4].format(**fill)


def compute_outcome(trace: dict, task: dict, max_steps: int = 8) -> tuple[bool, list[str]]:
    """Fail on a missing/mismatched fact, a forbidden tool call, or hitting max_steps."""
    reasons = []
    claims = {c["key"]: c["value"] for c in trace["final_answer"]["claims"]}
    for k, v in task["expected_facts"].items():
        if k not in claims:
            reasons.append(f"MISSING:{k}")
        elif claims[k] != v:
            reasons.append(f"MISMATCH:{k}")
    called = [s["tool_call"]["tool"] for s in trace["steps"] if s["kind"] == "tool"]
    for f in task["forbidden_tools"]:
        if f in called:
            reasons.append(f"FORBIDDEN:{f}")
    if len(trace["steps"]) >= max_steps:
        reasons.append("MAX_STEPS")
    return not reasons, reasons
