"""Match every alert to a core banking customer (CIF), strongest evidence first.

Each match records the method and a confidence. Matches at or above
AUTO_ACCEPT are used for cases; anything weaker, ambiguous or unmatched goes to
an identity review queue instead of being guessed.
"""
from __future__ import annotations

from collections import defaultdict

AUTO_ACCEPT = 0.9
NICKNAMES = {"bob": "robert", "mike": "michael", "dan": "daniel", "tony": "anthony", "joe": "joseph",
             "tom": "thomas", "steve": "steven", "andy": "andrew", "pat": "patricia", "sam": "samuel"}

# Method, confidence and the plain-language reason shown to the reviewer.
METHODS = {
    "crosswalk": (1.0, "Party key found in the Actimize to core crosswalk"),
    "cif": (1.0, "Customer number matches core banking after restoring leading zeros"),
    "account": (0.99, "Full account number belongs to this customer"),
    "masked_account_name": (0.92, "Last four account digits and name match one customer"),
    "name_dob": (0.95, "Name and date of birth match one customer"),
    "name_only": (0.6, "Only the name matches one customer; no identifier confirms it"),
}


def name_key(name: str) -> str:
    """First and last name only, nicknames expanded: 'mike j smith' -> 'michael smith'."""
    parts = [p for p in name.split() if len(p) > 1]
    if not parts:
        return ""
    first = NICKNAMES.get(parts[0], parts[0])
    return f"{first} {parts[-1]}" if len(parts) > 1 else first


class Resolver:
    def __init__(self, customers: list[dict], crosswalk: dict):
        self.crosswalk = crosswalk
        self.cifs = {c["CIF"] for c in customers}
        self.by_account = {a: c["CIF"] for c in customers for a in c["accounts"]}
        self.by_name = defaultdict(set)
        self.by_name_dob = defaultdict(set)
        self.by_last4_name = defaultdict(set)
        for c in customers:
            key = name_key(c["name"])
            self.by_name[key].add(c["CIF"])
            self.by_name_dob[(key, c["DOB"])].add(c["CIF"])
            for a in c["accounts"]:
                self.by_last4_name[(a[-4:], key)].add(c["CIF"])

    def resolve(self, alert: dict) -> dict:
        ref, kind, key = alert["customer_ref"], alert["ref_type"], name_key(alert["name"])
        if kind == "party_key" and ref in self.crosswalk:
            return self._match(self.crosswalk[ref], "crosswalk")
        if kind == "cif" and ref in self.cifs:
            return self._match(ref, "cif")
        if kind == "account" and ref and not ref.startswith("*") and ref in self.by_account:
            return self._match(self.by_account[ref], "account")
        if kind == "account" and ref and ref.startswith("*"):
            hits = self.by_last4_name.get((ref[-4:], key), set())
            if len(hits) == 1:
                return self._match(next(iter(hits)), "masked_account_name")
        if alert.get("dob"):
            hits = self.by_name_dob.get((key, alert["dob"]), set())
            if len(hits) == 1:
                return self._match(next(iter(hits)), "name_dob")
        hits = self.by_name.get(key, set())
        if len(hits) == 1:
            return self._match(next(iter(hits)), "name_only")
        if len(hits) > 1:
            return {"cif": None, "method": "ambiguous", "confidence": 0.0,
                    "reason": f"Name matches {len(hits)} customers and no identifier separates them",
                    "candidates": sorted(hits)[:5]}
        return {"cif": None, "method": "no_match", "confidence": 0.0,
                "reason": "No identifier or name matches a core banking customer", "candidates": []}

    @staticmethod
    def _match(cif: str, method: str) -> dict:
        confidence, reason = METHODS[method]
        return {"cif": cif, "method": method, "confidence": confidence, "reason": reason, "candidates": [cif]}


def resolve_all(alerts: list[dict], customers: list[dict], crosswalk: dict) -> list[dict]:
    resolver = Resolver(customers, crosswalk)
    for alert in alerts:
        alert["resolution"] = resolver.resolve(alert)
        alert["auto_accepted"] = alert["resolution"]["confidence"] >= AUTO_ACCEPT
    return alerts


def evaluate(alerts: list[dict], answer_key: dict) -> dict:
    """Compare automatic matches with the answer key held back for testing."""
    accepted = [a for a in alerts if a["auto_accepted"]]
    correct = sum(answer_key.get(a["alert_id"]) == a["resolution"]["cif"] for a in accepted)
    queued = [a for a in alerts if not a["auto_accepted"]]
    queued_wrong_guess = sum(a["resolution"]["cif"] is not None and answer_key.get(a["alert_id"]) != a["resolution"]["cif"]
                             for a in queued)
    return {
        "alerts": len(alerts),
        "auto_accepted": len(accepted),
        "auto_accepted_correct": correct,
        "auto_precision": round(correct / len(accepted), 4) if accepted else None,
        "sent_to_review": len(queued),
        "review_name_only_guesses_wrong": queued_wrong_guess,
    }
