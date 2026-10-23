"""Deterministic NorthPeak Outfitters world (seed=42). Writes data/world.json and data/policies.json."""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
TODAY = date(2026, 10, 23)

FIRST = ["Anna", "Ben", "Chloe", "David", "Elena", "Felix", "Grace", "Hugo", "Ines", "Jonas",
         "Kira", "Liam", "Mila", "Noah", "Olga", "Paul", "Rosa", "Sam", "Tara", "Umar", "Vera", "Will"]
LAST = ["Schmidt", "Novak", "Rossi", "Kim", "Silva", "Berg", "Moreau", "Hansen", "Costa", "Weber"]
CITIES = ["Austin", "Denver", "Seattle", "Boston", "Portland", "Chicago"]

PRODUCTS = [
    ("SKU-TENT-02", "Ridgeline 2P Tent", 189.0, True),
    ("SKU-JKT-05", "Summit Shell Jacket", 129.0, False),
    ("SKU-STOVE-03", "Trailblaze Stove", 79.0, False),
    ("SKU-BOOT-01", "Granite Hiking Boot", 149.0, False),
    ("SKU-PACK-04", "Alpine 45L Pack", 159.0, False),
    ("SKU-BAG-06", "Glacier Sleeping Bag", 139.0, True),
    ("SKU-LAMP-07", "Lumen Headlamp", 39.0, False),
    ("SKU-POLE-08", "Carbon Trek Poles", 89.0, False),
    ("SKU-MAT-09", "Cloudrest Sleeping Pad", 99.0, False),
    ("SKU-FILT-10", "PureFlow Water Filter", 49.0, True),
    ("SKU-GLOV-11", "Ridge Gloves", 35.0, False),
    ("SKU-HAT-12", "Sunpeak Hat", 29.0, False),
    ("SKU-COOK-13", "Basecamp Cook Set", 69.0, False),
    ("SKU-CHAIR-14", "Fold Camp Chair", 59.0, False),
    ("SKU-GPS-15", "TrailMark GPS", 249.0, True),
    ("SKU-SOCK-16", "Merino Socks 3-Pack", 25.0, False),
]

POLICIES = [
    {"doc_id": "POL-REFUND", "version": "v1", "effective_from": "2024-01-01", "superseded_by": "v2",
     "text": "Refunds within 60 days of delivery.", "window_days": 60, "final_sale_excluded": False},
    {"doc_id": "POL-REFUND", "version": "v2", "effective_from": "2026-06-01", "superseded_by": None,
     "text": "Refunds within 30 days of delivery; final-sale items are excluded.", "window_days": 30,
     "final_sale_excluded": True},
    {"doc_id": "POL-DELAY", "version": "v1", "effective_from": "2025-01-01", "superseded_by": None,
     "text": "If a shipment is delayed more than 5 days, the customer gets a $10 credit.", "credit_usd": 10,
     "threshold_days": 5},
    {"doc_id": "POL-ESCALATION", "version": "v1", "effective_from": "2025-01-01", "superseded_by": None,
     "text": "Escalate to a human when a required system is unavailable."},
]


def build_world() -> dict:
    """Build the seeded world: customers, products, orders, shipments."""
    rng = random.Random(42)
    customers = []
    for i in range(1, 25):
        cid = f"C-{i:03d}"
        if cid == "C-019":
            name, city = "Maria Lopez", "Austin"
        elif cid == "C-004":
            name, city = "Jonas Weber", "Seattle"
        else:
            name, city = f"{rng.choice(FIRST)} {rng.choice(LAST)}", rng.choice(CITIES)
        customers.append({"id": cid, "name": name, "city": city,
                          "email": f"{name.lower().replace(' ', '.')}.{i}@example.com"})
    customers.append({"id": "C-031", "name": "Maria Lopez", "city": "Denver",
                      "email": "maria.lopez.31@example.com"})

    products = [{"sku": s, "name": n, "price": p, "final_sale": f} for s, n, p, f in PRODUCTS]
    orders, shipments = [], []
    for i in range(1001, 1041):
        cust = rng.choice(customers[:24])
        prod = rng.choice(products)
        delivered = TODAY - timedelta(days=rng.randint(3, 80))
        oid = f"ORD-{i}"
        orders.append({"id": oid, "customer_id": cust["id"], "sku": prod["sku"],
                       "delivered_at": delivered.isoformat(), "status": "delivered"})
        shipments.append({"order_id": oid, "delay_days": rng.randint(0, 9), "status": "delivered"})
    fixed = [
        ("ORD-1042", "C-004", "SKU-TENT-02", "2026-09-02", "delivered", 0),
        ("ORD-1043", "C-007", "SKU-JKT-05", "2026-10-12", "delivered", 1),
        ("ORD-1107", "C-012", "SKU-STOVE-03", None, "in_transit", 7),
        ("ORD-1150", "C-019", "SKU-BOOT-01", "2026-10-10", "delivered", 0),
        ("ORD-1188", "C-031", "SKU-PACK-04", None, "in_transit", 2),
    ]
    for oid, cid, sku, d, st, delay in fixed:
        orders.append({"id": oid, "customer_id": cid, "sku": sku, "delivered_at": d, "status": st})
        shipments.append({"order_id": oid, "delay_days": delay, "status": st})
    return {"today": TODAY.isoformat(), "customers": customers, "products": products,
            "orders": orders, "shipments": shipments}


def write() -> dict:
    """Write world.json and policies.json; return the world."""
    DATA.mkdir(exist_ok=True)
    world = build_world()
    (DATA / "world.json").write_text(json.dumps(world, indent=2), encoding="utf-8")
    (DATA / "policies.json").write_text(json.dumps(POLICIES, indent=2), encoding="utf-8")
    return world


if __name__ == "__main__":
    write()
