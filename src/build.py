"""Run the pipeline end to end and write the command center data to dist/data/.

ingest -> resolve identities -> group into cases -> forecast capacity.
The answer key in data/eval/ is used only to report matching accuracy.
"""
from __future__ import annotations

import csv
import json
import random
from collections import Counter
from pathlib import Path

import cases as case_builder
import forecast
import ingest
import resolve

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "data"


def answer_key() -> dict:
    with open(ROOT / "data" / "eval" / "entity_answer_key.csv", newline="") as f:
        return {r["source_record_id"]: r["true_cif"] or None for r in csv.DictReader(f)}


def qa_sample(cases: list[dict], rate: float, seed: int = 7) -> list[str]:
    """Random QA sample drawn with a fixed seed so the selection can be reproduced for examiners."""
    rng = random.Random(seed)
    return sorted(c["case_id"] for c in cases if rng.random() < rate)


def build() -> dict:
    alerts, reports, mappings = ingest.load_all()
    customers, crosswalk = ingest.load_customers()
    resolve.resolve_all(alerts, customers, crosswalk)
    accuracy = resolve.evaluate(alerts, answer_key())
    cases = case_builder.build_cases(alerts, customers)
    review = [a for a in alerts if not a["auto_accepted"]]
    plan = forecast.plan(cases, len(review))
    sample = set(qa_sample(cases, forecast.ASSUMPTIONS["qa_sample_rate"]))

    def slim_alert(a):
        return {k: a[k] for k in ("alert_id", "source", "scenario", "detail", "alert_date", "amount")} | {
            "method": a["resolution"]["method"], "confidence": a["resolution"]["confidence"]}

    return {
        "as_of": case_builder.AS_OF.isoformat(),
        "bank": "Larkspur Bank (fictional)",
        "summary": {
            "alerts": len(alerts),
            "cases": len(cases),
            "alerts_per_case": round(sum(len(c["alerts"]) for c in cases) / len(cases), 1),
            "sla_breached_cases": sum(c["sla_breached"] for c in cases),
            "multi_source_cases": sum(len(c["sources"]) > 1 for c in cases),
            "tiers": dict(Counter(c["tier"] for c in cases)),
            "identity_review": len(review),
        },
        "sources": reports,
        "mappings": mappings,
        "resolution": {
            "auto_accept_threshold": resolve.AUTO_ACCEPT,
            "methods": dict(Counter(a["resolution"]["method"] for a in alerts)),
            "method_notes": {k: {"confidence": v[0], "reason": v[1]} for k, v in resolve.METHODS.items()},
            "accuracy": accuracy,
        },
        "review_queue": [slim_alert(a) | {"name": a["name"], "customer_ref": a["customer_ref"],
                                          "reason": a["resolution"]["reason"], "candidates": a["resolution"]["candidates"]}
                         for a in review],
        "cases": [{k: c[k] for k in ("case_id", "cif", "customer", "segment", "risk_rating", "sources", "typologies",
                                     "oldest_alert", "oldest_age_days", "total_amount", "priority_score", "tier",
                                     "sla_breached", "score_parts")}
                  | {"alerts": [slim_alert(a) for a in c["alerts"]], "qa_sampled": c["case_id"] in sample}
                  for c in cases],
        "forecast": plan,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = build()
    (OUT / "command_center.json").write_text(json.dumps(data, separators=(",", ":")) + "\n")
    s, f = data["summary"], data["forecast"]
    print(f"{s['alerts']} alerts -> {s['cases']} cases ({s['alerts_per_case']} per case), "
          f"{s['identity_review']} to identity review, auto match precision {data['resolution']['accuracy']['auto_precision']}")
    print(f"Analysts to meet {f['deadline']}: alert level {f['analysts_needed_alert_level']}, case level {f['analysts_needed_case_level']}")


if __name__ == "__main__":
    main()
