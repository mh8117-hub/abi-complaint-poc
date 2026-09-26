"""Structured-output parser and validator.

Turns raw model text into a validated triage record, or a documented
failure. Never raises on bad model output: every outcome is returned as a
ParseResult so it can be logged as evidence.

Pipeline:
  1. extract   - locate a JSON object in the raw text (handles ```json fences,
                 leading/trailing prose, and a trailing comma)
  2. normalize - forgive harmless drift (case, "true"/"yes" strings,
                 risk_flags given as a string or containing "none")
  3. validate  - required keys, types, enum membership
  4. rules     - deterministic controls applied AFTER the model
                 (the model recommends; rules can only make handling stricter)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .schema import ENUMS, REQUIRED_FIELDS, RISK_FLAGS


@dataclass
class ParseResult:
    status: str                      # "valid" | "invalid" | "unparseable"
    record: dict | None = None
    errors: list = field(default_factory=list)
    repairs: list = field(default_factory=list)   # normalizations applied
    rule_overrides: list = field(default_factory=list)

    def to_dict(self):
        return {
            "status": self.status,
            "record": self.record,
            "errors": self.errors,
            "repairs": self.repairs,
            "rule_overrides": self.rule_overrides,
        }


_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def extract_json(raw: str, repairs: list) -> dict | None:
    if raw is None:
        return None
    text = raw.strip()
    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()
        repairs.append("stripped markdown code fence")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    if start > 0 or end < len(text) - 1:
        repairs.append("trimmed prose outside JSON object")
    candidate = text[start:end + 1]
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError:
        fixed = _TRAILING_COMMA.sub(r"\1", candidate)
        try:
            obj = json.loads(fixed)
            repairs.append("removed trailing comma")
        except json.JSONDecodeError:
            return None
    return obj if isinstance(obj, dict) else None


def _to_bool(v):
    if isinstance(v, bool):
        return v, False
    if isinstance(v, str) and v.strip().lower() in ("true", "yes", "y", "required"):
        return True, True
    if isinstance(v, str) and v.strip().lower() in ("false", "no", "n", "not required"):
        return False, True
    return v, False


def normalize(obj: dict, repairs: list) -> dict:
    out = dict(obj)
    # enums: case-insensitive match to canonical label
    for key, allowed in ENUMS.items():
        v = out.get(key)
        if isinstance(v, str) and v not in allowed:
            match = [a for a in allowed if a.lower() == v.strip().lower()]
            if match:
                out[key] = match[0]
                repairs.append(f"{key}: case-normalized '{v}'")
    for key in ("escalation", "human_review_required"):
        if key in out:
            out[key], changed = _to_bool(out[key])
            if changed:
                repairs.append(f"{key}: coerced string to bool")
    rf = out.get("risk_flags")
    if isinstance(rf, str):
        rf = [s.strip() for s in rf.split(",") if s.strip()]
        repairs.append("risk_flags: split string into list")
    if isinstance(rf, list):
        cleaned = [str(x).strip().lower().replace(" ", "_") for x in rf]
        cleaned = [x for x in cleaned if x not in ("none", "", "n/a")]
        if cleaned != rf:
            repairs.append("risk_flags: normalized values")
        out["risk_flags"] = cleaned
    return out


def validate(obj: dict) -> list:
    errors = []
    for key, typ in REQUIRED_FIELDS.items():
        if key not in obj:
            errors.append(f"missing field: {key}")
        elif not isinstance(obj[key], typ):
            errors.append(f"{key}: expected {typ.__name__}, got {type(obj[key]).__name__}")
    for key, allowed in ENUMS.items():
        if isinstance(obj.get(key), str) and obj[key] not in allowed:
            errors.append(f"{key}: '{obj[key]}' not in allowed values")
    for flag in obj.get("risk_flags", []) if isinstance(obj.get("risk_flags"), list) else []:
        if flag not in RISK_FLAGS:
            errors.append(f"risk_flags: unknown flag '{flag}'")
    extra = set(obj) - set(REQUIRED_FIELDS)
    if extra:
        errors.append(f"unexpected fields: {sorted(extra)}")
    return errors


def apply_rules(rec: dict, overrides: list) -> dict:
    """Deterministic controls. They can only tighten handling, never relax it."""
    flags = set(rec.get("risk_flags", []))
    if flags & {"fraud", "regulatory", "vulnerable_customer"} and not rec.get("human_review_required"):
        rec["human_review_required"] = True
        overrides.append("R1: fraud/regulatory/vulnerable flag -> human_review_required=true")
    if rec.get("urgency") == "High" and not rec.get("escalation"):
        rec["escalation"] = True
        overrides.append("R2: urgency High -> escalation=true")
    return rec


def parse_model_output(raw: str) -> ParseResult:
    repairs: list = []
    obj = extract_json(raw, repairs)
    if obj is None:
        return ParseResult(status="unparseable", errors=["no JSON object could be extracted"], repairs=repairs)
    obj = normalize(obj, repairs)
    errors = validate(obj)
    if errors:
        return ParseResult(status="invalid", record=obj, errors=errors, repairs=repairs)
    overrides: list = []
    rec = apply_rules(obj, overrides)
    return ParseResult(status="valid", record=rec, repairs=repairs, rule_overrides=overrides)
