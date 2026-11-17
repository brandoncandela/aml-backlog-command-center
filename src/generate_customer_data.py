"""Generate the fictional customer's raw exports, the way a bank would hand them over.

Candela Bank (fictional) runs three alert sources that disagree on IDs, formats
and quality. This script writes those exports to data/customer_exports/ plus a
hidden answer key in data/eval/ used only to measure entity resolution accuracy.
Everything is synthetic and deterministic (fixed seed).
"""
from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "data" / "customer_exports"
EVAL = ROOT / "data" / "eval"
RNG = random.Random(20261117)

FIRST = ["James", "Maria", "Robert", "Ana", "Michael", "Luis", "David", "Sofia", "Daniel", "Carmen", "Kevin", "Elena",
         "Jason", "Rosa", "Brian", "Isabel", "Anthony", "Lucia", "Mark", "Paula", "Steven", "Diana", "Eric", "Gloria",
         "Andrew", "Teresa", "Joseph", "Patricia", "Thomas", "Linda", "Carlos", "Angela", "Victor", "Monica", "Raymond",
         "Julia", "Samuel", "Laura", "Henry", "Nadia"]
LAST = ["Smith", "Garcia", "Johnson", "Rodriguez", "Williams", "Martinez", "Brown", "Hernandez", "Jones", "Lopez",
        "Miller", "Gonzalez", "Davis", "Perez", "Wilson", "Sanchez", "Anderson", "Ramirez", "Taylor", "Torres", "Moore",
        "Rivera", "Jackson", "Flores", "Martin", "Gomez", "Lee", "Diaz", "Walker", "Reyes", "Hall", "Cruz", "Allen",
        "Morales", "Young", "Ortiz", "King", "Gutierrez", "Wright", "Chavez", "Scott", "Ramos", "Green", "Vargas"]
NICKNAMES = {"Robert": "Bob", "Michael": "Mike", "Daniel": "Dan", "Anthony": "Tony", "Joseph": "Joe",
             "Thomas": "Tom", "Steven": "Steve", "Andrew": "Andy", "Patricia": "Pat", "Samuel": "Sam"}
ZIPS = ["33101", "33131", "33139", "33156", "32801", "32803", "32819", "10001", "10016", "10023", "11201", "07302"]
SEGMENTS = [("retail", 0.62), ("small_business", 0.22), ("private_banking", 0.09), ("msb", 0.07)]

ACTIMIZE_SCENARIOS = ["STRUCT_CASH", "RAPID_MVMT", "HR_GEO_WIRE", "LARGE_CASH", "P2P_VELOCITY", "DORMANT_REACT"]
LEGACY_RULES = ["Cash deposits over 10k in 3 days", "Wires to high risk jurisdiction", "Round dollar wires",
                "Funnel account deposits", "Check kiting pattern"]
FRAUD_REASONS = ["Account takeover", "Check fraud", "Elder exploitation", "Synthetic identity", "Mule activity"]

START = date(2026, 3, 1)
END = date(2026, 10, 31)


def pick_weighted(options):
    roll, total = RNG.random(), 0.0
    for value, weight in options:
        total += weight
        if roll <= total:
            return value
    return options[-1][0]


def make_customers(n=1400):
    customers, used = [], set()
    for i in range(n):
        first, last = RNG.choice(FIRST), RNG.choice(LAST)
        middle = RNG.choice("ABCDEFGHJKLMNPRSTW")
        dob = date(1945, 1, 1) + timedelta(days=RNG.randint(0, 365 * 58))
        segment = pick_weighted(SEGMENTS)
        risk = pick_weighted([("H", 0.10), ("M", 0.30), ("L", 0.60)] if segment != "msb" else [("H", 0.6), ("M", 0.4)])
        cif = f"{RNG.randint(10000, 999999):08d}"
        while cif in used:
            cif = f"{RNG.randint(10000, 999999):08d}"
        used.add(cif)
        accounts = [f"{RNG.randint(10**9, 10**10 - 1)}" for _ in range(RNG.choice([1, 1, 2, 3]))]
        customers.append({"cif": cif, "first": first, "middle": middle, "last": last, "dob": dob.isoformat(),
                          "zip": RNG.choice(ZIPS), "risk_rating": risk, "segment": segment, "accounts": accounts})
    return customers


def name_variant(c, style):
    first = NICKNAMES.get(c["first"], c["first"]) if RNG.random() < 0.25 else c["first"]
    if style == "upper":
        return f"{first} {c['middle']} {c['last']}".upper() if RNG.random() < 0.5 else f"{first} {c['last']}".upper()
    if style == "last_first":
        return f"{c['last']}, {first}" + (f" {c['middle']}." if RNG.random() < 0.3 else "")
    return f"{first} {c['last']}" + (" " if RNG.random() < 0.1 else "")


def alert_day():
    return START + timedelta(days=RNG.randint(0, (END - START).days))


def main():
    EXPORTS.mkdir(parents=True, exist_ok=True)
    EVAL.mkdir(parents=True, exist_ok=True)
    customers = make_customers()
    # A minority of customers generate most alerts, as in real monitoring programs.
    weights = [min(RNG.paretovariate(1.6), 12) for _ in customers]
    truth = []  # (source, source_record_id, true_cif)

    with open(EXPORTS / "core_customers.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["CIF", "FULL_NAME", "DOB", "ZIP", "RISK_RATING", "SEGMENT", "ACCOUNTS"])
        for c in customers:
            w.writerow([c["cif"], f"{c['first']} {c['middle']} {c['last']}", c["dob"], c["zip"],
                        c["risk_rating"], c["segment"], ";".join(c["accounts"])])

    # Actimize-style export: its own party keys; the crosswalk only covers most of them.
    keys = RNG.sample(range(100000, 999999), len(customers))
    party_key = {c["cif"]: f"P{k}" for c, k in zip(customers, keys)}
    with open(EXPORTS / "party_crosswalk.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["PARTY_KEY", "CIF"])
        for c in customers:
            if RNG.random() < 0.88:
                w.writerow([party_key[c["cif"]], c["cif"]])

    rows = []
    for i in range(3300):
        c = RNG.choices(customers, weights)[0]
        d = alert_day()
        amount = round(RNG.lognormvariate(8.8, 1.1), 2)
        status = "CLOSED" if RNG.random() < 0.06 else "OPEN"
        row = [f"ACT-{260000 + i}", party_key[c["cif"]], name_variant(c, "upper"), RNG.choice(ACTIMIZE_SCENARIOS),
               d.strftime("%m/%d/%Y"), f"{amount:,.2f}", status, RNG.choice(["MIA01", "MIA02", "ORL01", "NYC03"])]
        if RNG.random() < 0.01:
            row[4] = "00/00/0000"  # bad date from a failed batch
        rows.append(row)
        truth.append(("actimize", row[0], c["cif"]))
    rows += [list(r) for r in RNG.sample(rows, 60)]  # duplicate rows from a re-run extract
    RNG.shuffle(rows)
    with open(EXPORTS / "actimize_alert_export.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ALERT_ID", "PARTY_KEY", "PARTY_NM", "SCENARIO_CD", "ALERT_DT", "TXN_AMT", "ALERT_STATUS", "BRANCH"])
        w.writerows(rows)

    # Legacy SQL rules: pipe delimited, CIF often missing leading zeros, mixed date formats.
    with open(EXPORTS / "legacy_rules_export.txt", "w") as f:
        f.write("rule_name|cust_no|customer|created|amount|state\n")
        for i in range(1900):
            c = RNG.choices(customers, weights)[0]
            d = alert_day()
            cust_no = c["cif"].lstrip("0") if RNG.random() < 0.5 else c["cif"]
            created = d.isoformat() if RNG.random() < 0.7 else d.strftime("%Y/%m/%d")
            amount = "" if RNG.random() < 0.03 else f"${RNG.lognormvariate(9.2, 0.9):,.0f}"
            state = "closed" if RNG.random() < 0.05 else "open"
            if RNG.random() < 0.02:
                cust_no = str(RNG.randint(10**6, 10**7))  # customer not in core: a migration orphan
                truth.append(("legacy", f"LEG-{i + 1:05d}", None))
            else:
                truth.append(("legacy", f"LEG-{i + 1:05d}", c["cif"]))
            f.write(f"{RNG.choice(LEGACY_RULES)}|{cust_no}|{name_variant(c, 'last_first')}|{created}|{amount}|{state}\n")

    # Fraud referrals: no customer ID at all, sometimes only a masked account and no DOB.
    referrals = []
    for i in range(450):
        c = RNG.choices(customers, weights)[0]
        acct = RNG.choice(c["accounts"])
        acct_field = acct if RNG.random() < 0.65 else ("****" + acct[-4:] if RNG.random() < 0.7 else None)
        exposure = RNG.lognormvariate(8.3, 1.0)
        referrals.append({
            "ref": f"FR-{4400 + i}",
            "subject": {"name": name_variant(c, "plain"), "dob": c["dob"] if RNG.random() < 0.8 else None,
                        "account": acct_field},
            "reason": RNG.choice(FRAUD_REASONS),
            "opened": f"{alert_day().isoformat()}T{RNG.randint(8, 18):02d}:{RNG.randint(0, 59):02d}:00",
            "exposure": f"${exposure / 1000:.1f}k" if RNG.random() < 0.5 else f"{exposure:.0f}",
        })
        truth.append(("fraud", f"FR-{4400 + i}", c["cif"]))
    (EXPORTS / "fraud_referrals.json").write_text(json.dumps({"exported_at": "2026-11-01T06:00:00", "referrals": referrals}, indent=1))

    with open(EVAL / "entity_answer_key.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "source_record_id", "true_cif"])
        w.writerows([(s, r, cif or "") for s, r, cif in truth])
    print(f"{len(customers)} customers, {len(rows)} Actimize rows, 1900 legacy rows, {len(referrals)} fraud referrals")


if __name__ == "__main__":
    main()
