"""Deterministic mock tools over the world, plus their JSON schemas."""
from __future__ import annotations

import re
from datetime import date

from datagen.world import POLICIES

TOOL_SCHEMAS: list[dict] = [
    {"name": "find_customer", "read_only": True, "args": {"name": {"type": "string"}, "email": {"type": "string"}}},
    {"name": "get_order", "read_only": True, "args": {"order_id": {"type": "string", "pattern": r"^ORD-\d{4}$"}}},
    {"name": "list_orders", "read_only": True, "args": {"customer_id": {"type": "string", "pattern": r"^C-\d{3}$"}}},
    {"name": "get_shipment", "read_only": True, "args": {"order_id": {"type": "string", "pattern": r"^ORD-\d{4}$"}}},
    {"name": "get_product", "read_only": True, "args": {"sku": {"type": "string", "pattern": r"^SKU-[A-Z]+-\d{2}$"}}},
    {"name": "search_policy", "read_only": True, "args": {"query": {"type": "string"}}},
    {"name": "check_refund_eligibility", "read_only": True,
     "args": {"order_id": {"type": "string", "pattern": r"^ORD-\d{4}$"},
              "sku": {"type": "string", "pattern": r"^SKU-[A-Z]+-\d{2}$"}}},
    {"name": "issue_refund", "read_only": False,
     "args": {"order_id": {"type": "string", "pattern": r"^ORD-\d{4}$"},
              "sku": {"type": "string", "pattern": r"^SKU-[A-Z]+-\d{2}$"}, "amount": {"type": "number"}}},
    {"name": "escalate_to_human", "read_only": False, "args": {"reason": {"type": "string"}}},
]
SCHEMA_BY_NAME = {s["name"]: s for s in TOOL_SCHEMAS}


def validate_arg(tool: str, name: str, value) -> tuple[bool, str | None]:
    """Check one argument against the tool schema; return (valid, violation)."""
    spec = SCHEMA_BY_NAME[tool]["args"].get(name)
    if spec is None:
        return False, f"unknown argument {name}"
    if spec["type"] == "number" and not isinstance(value, (int, float)):
        return False, "expected number"
    if spec["type"] == "string" and not isinstance(value, str):
        return False, "expected string"
    if "pattern" in spec and not re.match(spec["pattern"], str(value)):
        return False, f"does not match {spec['pattern']}"
    return True, None


class Tools:
    """Pure functions over a world dict. Each returns a payload dict."""

    def __init__(self, world: dict):
        self.w = world
        self.orders = {o["id"]: o for o in world["orders"]}
        self.products = {p["sku"]: p for p in world["products"]}
        self.ships = {s["order_id"]: s for s in world["shipments"]}
        self.today = date.fromisoformat(world["today"])

    def find_customer(self, name: str | None = None, email: str | None = None) -> list[dict]:
        return [c for c in self.w["customers"] if (name and c["name"] == name) or (email and c["email"] == email)]

    def get_order(self, order_id: str) -> dict | None:
        return self.orders.get(order_id)

    def list_orders(self, customer_id: str) -> list[dict]:
        return [o for o in self.w["orders"] if o["customer_id"] == customer_id]

    def get_shipment(self, order_id: str) -> dict | None:
        return self.ships.get(order_id)

    def get_product(self, sku: str) -> dict | None:
        return self.products.get(sku)

    def search_policy(self, query: str, version: str | None = None) -> list[dict]:
        q = query.lower()
        doc = "POL-DELAY" if ("delay" in q or "late" in q) else "POL-REFUND"
        hits = [p for p in POLICIES if p["doc_id"] == doc]
        if version:
            hits = [p for p in hits if p["version"] == version]
        else:
            hits = [p for p in hits if p["superseded_by"] is None]
        return hits

    def check_refund_eligibility(self, order_id: str, sku: str) -> dict:
        order, prod = self.orders[order_id], self.products[sku]
        if prod["final_sale"]:
            return {"refund_eligible": "false", "reason": "final_sale"}
        if order["delivered_at"] is None:
            return {"refund_eligible": "false", "reason": "not_delivered"}
        days = (self.today - date.fromisoformat(order["delivered_at"])).days
        if days > 30:
            return {"refund_eligible": "false", "reason": "window_expired"}
        return {"refund_eligible": "true", "reason": "within_window"}
