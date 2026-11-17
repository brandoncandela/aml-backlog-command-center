"""Estimate analyst hours and the backlog clear date, alert by alert versus by case.

The effort numbers are planning assumptions, the kind agreed with an operations
manager in week one of a pilot and then replaced with measured handle times.
They live here as named constants so they can be challenged and changed.
"""
from __future__ import annotations

from datetime import date, timedelta

START = date(2026, 11, 30)
DEADLINE = date(2027, 3, 31)  # date in the fictional regulatory agreement
HOLIDAYS = {date(2026, 12, 25), date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15)}
PRODUCTIVE_MINUTES_PER_DAY = 6 * 60

ASSUMPTIONS = {
    "alert_minutes": 40,             # review one alert on its own, including customer research
    "case_base_minutes": 50,         # first alert in a case: full customer research
    "case_extra_alert_minutes": 12,  # each further alert reuses that research
    "fraud_referral_minutes": 20,    # extra review of fraud team evidence (per alert or once per case)
    "high_risk_edd_minutes": 25,     # enhanced due diligence refresh for high risk customers
    "identity_review_minutes": 8,    # resolve one alert in the identity review queue
    "sar_minutes": 120,              # draft and file a SAR for an escalated customer
    "qa_minutes": 20,                # QA review of one decision
    "qa_sample_rate": 0.10,          # random QA sample of non escalated decisions
}
ESCALATION_RATE = {"P1": 0.35, "P2": 0.12, "P3": 0.04}  # share of customers expected to need a SAR


def working_days(start: date, count: int) -> list[date]:
    days, d = [], start
    while len(days) < count:
        if d.weekday() < 5 and d not in HOLIDAYS:
            days.append(d)
        d += timedelta(days=1)
    return days


def effort(cases: list[dict], review_queue: int, a: dict = ASSUMPTIONS) -> dict:
    """Total analyst minutes for each approach. SAR and QA work is the same per customer either way."""
    alert_level = case_level = 0.0
    for case in cases:
        n = len(case["alerts"])
        frauds = sum(al["scenario"] == "fraud_referral" for al in case["alerts"])
        edd = a["high_risk_edd_minutes"] if case["risk_rating"] == "H" else 0
        alert_level += n * a["alert_minutes"] + frauds * a["fraud_referral_minutes"] + n * edd
        case_level += (a["case_base_minutes"] + (n - 1) * a["case_extra_alert_minutes"]
                       + (a["fraud_referral_minutes"] if frauds else 0) + edd)
        escalation = ESCALATION_RATE[case["tier"]]
        shared = escalation * (a["sar_minutes"] + a["qa_minutes"]) + (1 - escalation) * a["qa_sample_rate"] * a["qa_minutes"]
        alert_level += shared
        case_level += shared
    review = review_queue * a["identity_review_minutes"]
    return {"alert_level_minutes": round(alert_level + review), "case_level_minutes": round(case_level + review),
            "identity_review_minutes": review, "expected_sars": round(sum(ESCALATION_RATE[c["tier"]] for c in cases))}


def clear_date(total_minutes: float, analysts: int) -> date:
    days_needed = -(-total_minutes // (analysts * PRODUCTIVE_MINUTES_PER_DAY))  # ceiling
    return working_days(START, int(days_needed))[-1]


def analysts_needed(total_minutes: float) -> int:
    available = len([d for d in working_days(START, 400) if d <= DEADLINE])
    return int(-(-total_minutes // (available * PRODUCTIVE_MINUTES_PER_DAY)))


def plan(cases: list[dict], review_queue: int) -> dict:
    e = effort(cases, review_queue)
    scenarios = []
    for n in range(4, 31):
        scenarios.append({"analysts": n,
                          "alert_level_clear": clear_date(e["alert_level_minutes"], n).isoformat(),
                          "case_level_clear": clear_date(e["case_level_minutes"], n).isoformat()})
    return {
        **e,
        "start": START.isoformat(),
        "deadline": DEADLINE.isoformat(),
        "productive_minutes_per_day": PRODUCTIVE_MINUTES_PER_DAY,
        "assumptions": ASSUMPTIONS,
        "escalation_rate": ESCALATION_RATE,
        "analysts_needed_alert_level": analysts_needed(e["alert_level_minutes"]),
        "analysts_needed_case_level": analysts_needed(e["case_level_minutes"]),
        "working_days": [d.isoformat() for d in working_days(START, 400)],
        "scenarios": scenarios,
    }
