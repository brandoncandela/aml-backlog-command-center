"""Group resolved alerts into one case per customer and rank the cases.

Priority is a sum of named points so an analyst or examiner can see exactly why
a case sits where it does. Weights are starting values agreed with the customer
in discovery and are meant to be tuned.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

AS_OF = date(2026, 11, 17)
SLA_DAYS = 60  # bank policy: alert to decision

RISK_POINTS = {"H": 30, "M": 15, "L": 0}
TYPOLOGY_POINTS = {"structuring": 25, "fraud_referral": 25, "high_risk_geography": 20, "funnel_account": 20,
                   "rapid_movement": 18, "check_kiting": 15, "round_dollar_wires": 12, "large_cash": 10,
                   "p2p_velocity": 10, "dormant_reactivation": 8}
TIERS = [("P1", 85), ("P2", 60), ("P3", 0)]


def score(case: dict) -> list[tuple[str, int]]:
    """The points that make up a case's priority, in display order."""
    alerts = case["alerts"]
    total = sum(a["amount"] or 0 for a in alerts)
    overdue = max(0, case["oldest_age_days"] - SLA_DAYS)
    return [
        ("Customer risk rating " + case["risk_rating"], RISK_POINTS[case["risk_rating"]]),
        ("Most severe typology: " + case["top_typology"].replace("_", " "), TYPOLOGY_POINTS.get(case["top_typology"], 5)),
        ("Flagged by more than one system", 10 if len(case["sources"]) > 1 else 0),
        (f"{len(alerts)} alerts on this customer", min(15, 3 * (len(alerts) - 1))),
        (f"${total:,.0f} total flagged", min(15, round(3 * math.log10(total))) if total > 1 else 0),
        (f"{overdue} days past the {SLA_DAYS} day SLA", min(20, round(overdue / 6))),
    ]


def build_cases(alerts: list[dict], customers: list[dict]) -> list[dict]:
    by_cif = {c["CIF"]: c for c in customers}
    grouped = defaultdict(list)
    for alert in alerts:
        if alert["auto_accepted"]:
            grouped[alert["resolution"]["cif"]].append(alert)
    cases = []
    for cif, items in grouped.items():
        customer = by_cif[cif]
        items.sort(key=lambda a: a["alert_date"])
        oldest = date.fromisoformat(items[0]["alert_date"])
        case = {
            "cif": cif,
            "customer": customer["FULL_NAME"],
            "segment": customer["SEGMENT"],
            "risk_rating": customer["RISK_RATING"],
            "alerts": items,
            "sources": sorted({a["source"] for a in items}),
            "typologies": sorted({a["scenario"] for a in items}),
            "top_typology": max((a["scenario"] for a in items), key=lambda t: TYPOLOGY_POINTS.get(t, 5)),
            "oldest_alert": oldest.isoformat(),
            "oldest_age_days": (AS_OF - oldest).days,
            "total_amount": round(sum(a["amount"] or 0 for a in items), 2),
            "has_fraud_referral": any(a["scenario"] == "fraud_referral" for a in items),
        }
        case["score_parts"] = score(case)
        case["priority_score"] = sum(points for _, points in case["score_parts"])
        case["tier"] = next(name for name, floor in TIERS if case["priority_score"] >= floor)
        case["sla_breached"] = case["oldest_age_days"] > SLA_DAYS
        cases.append(case)
    cases.sort(key=lambda c: (-c["priority_score"], c["oldest_alert"], c["cif"]))
    for i, case in enumerate(cases, 1):
        case["case_id"] = f"CASE-{i:04d}"
    return cases
