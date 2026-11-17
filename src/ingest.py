"""Load each customer export through its mapping config into one alert schema.

Adding a source system means adding a JSON file to config/sources/, not code.
Every row is either loaded, dropped as a duplicate or closed alert, or rejected
with a reason, and the counts reconcile back to the rows read.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "config" / "sources"
EXPORTS = ROOT / "data" / "customer_exports"


class Rejected(Exception):
    """A row that cannot be loaded; the message becomes the data quality reason."""


def read_rows(config: dict, folder: Path) -> list[dict]:
    path = folder / config["file"]
    if config["format"] == "csv":
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    if config["format"] == "delimited":
        with open(path, newline="") as f:
            return list(csv.DictReader(f, delimiter=config["delimiter"]))
    if config["format"] == "json":
        data = json.loads(path.read_text())
        for key in config["records_path"].split("."):
            data = data[key]
        return data
    raise ValueError(f"Unknown format {config['format']}")


def get(row: dict, spec: dict, index: int):
    """Read one field as the config describes: a column, a JSON path, a constant or a template."""
    if "value" in spec:
        return spec["value"]
    if "template" in spec:
        return spec["template"].format(row=index + 1)
    if "column" in spec:
        return row.get(spec["column"])
    value = row
    for key in spec["path"].split("."):
        value = value.get(key) if isinstance(value, dict) else None
    return value


def parse_date(text, formats):
    if not text:
        raise Rejected("missing date")
    for fmt in formats:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    raise Rejected(f"unreadable date {text!r}")


def parse_money(text):
    """'12,345.67', '$12,345', '5200' and '$4.2k' all become dollars; blank becomes None."""
    if text is None or str(text).strip() == "":
        return None
    s = str(text).strip().replace("$", "").replace(",", "").lower()
    scale = 1000 if s.endswith("k") else 1
    try:
        return round(float(s.rstrip("k")) * scale, 2)
    except ValueError:
        raise Rejected(f"unreadable amount {text!r}")


def normalize_name(text, order="first_last"):
    """'Anderson, Luis E.' and 'LUIS E ANDERSON' both become 'luis e anderson'."""
    if not text:
        return ""
    text = text.strip()
    if order == "last_first" and "," in text:
        last, rest = [p.strip() for p in text.split(",", 1)]
        text = f"{rest} {last}"
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", text.lower())).strip()


def load_source(config: dict, folder: Path = EXPORTS) -> tuple[list[dict], dict]:
    fields = config["fields"]
    rows = read_rows(config, folder)
    loaded, seen, rejects = [], set(), Counter()
    report = {"source": config["source"], "label": config["label"], "file": config["file"], "rows_read": len(rows),
              "duplicates": 0, "closed": 0, "missing_amount": 0}
    for i, row in enumerate(rows):
        try:
            status = str(get(row, fields["status"], i) or "").strip()
            if "open_values" in fields["status"] and status not in fields["status"]["open_values"]:
                report["closed"] += 1
                continue
            alert_id = str(get(row, fields["alert_id"], i)).strip()
            key = tuple(str(get(row, fields[k], i)) for k in config["dedupe_on"])
            if key in seen:
                report["duplicates"] += 1
                continue
            seen.add(key)
            raw_scenario = get(row, fields["scenario"], i)
            scenario = fields["scenario"].get("map", {}).get(raw_scenario, raw_scenario)
            if not scenario:
                raise Rejected("missing scenario")
            ref = get(row, fields["customer_ref"], i)
            ref = str(ref).strip() if ref else None
            if ref and fields["customer_ref"].get("pad_left"):
                ref = ref.zfill(fields["customer_ref"]["pad_left"])
            amount = parse_money(get(row, fields["amount"], i))
            report["missing_amount"] += amount is None
            loaded.append({
                "alert_id": alert_id,
                "source": config["source"],
                "ref_type": fields["customer_ref"]["ref_type"] if ref else None,
                "customer_ref": ref,
                "name": normalize_name(get(row, fields["name"], i), fields["name"].get("name_order", "first_last")),
                "dob": get(row, fields["dob"], i) if "dob" in fields else None,
                "scenario": scenario,
                "detail": get(row, {"path": fields["scenario"]["detail_path"]}, i) if "detail_path" in fields["scenario"] else None,
                "alert_date": parse_date(get(row, fields["alert_date"], i), fields["alert_date"]["date_formats"]).isoformat(),
                "amount": amount,
            })
        except Rejected as reason:
            rejects[str(reason).split(" '")[0]] += 1
    report["rejected"] = dict(rejects)
    report["loaded"] = len(loaded)
    assert report["loaded"] + report["duplicates"] + report["closed"] + sum(rejects.values()) == report["rows_read"]
    return loaded, report


def load_all(folder: Path = EXPORTS, configs: Path = CONFIGS) -> tuple[list[dict], list[dict], list[dict]]:
    alerts, reports, mappings = [], [], []
    for path in sorted(configs.glob("*.json")):
        config = json.loads(path.read_text())
        rows, report = load_source(config, folder)
        alerts += rows
        reports.append(report)
        mappings.append(config)
    return alerts, reports, mappings


def load_customers(folder: Path = EXPORTS) -> tuple[list[dict], dict]:
    with open(folder / "core_customers.csv", newline="") as f:
        customers = [{**r, "name": normalize_name(r["FULL_NAME"]), "accounts": r["ACCOUNTS"].split(";")}
                     for r in csv.DictReader(f)]
    with open(folder / "party_crosswalk.csv", newline="") as f:
        crosswalk = {r["PARTY_KEY"]: r["CIF"] for r in csv.DictReader(f)}
    return customers, crosswalk
