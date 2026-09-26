"""Structured-output parser and validator.

Turns raw model text into a validated triage record, or a documented
failure. Never raises on bad model output: every outcome is returned as a
ParseResult so it can be logged as evidence.

Pipeline:
  1. extract   - locate a JSON object in the raw text (handles ```json fences,
                 leading/trailing prose, and a trailing comma)
  2. normalize - forgive harmless drift (case, "true"/"yes" strings,
                 routing label in a different case)
  3. validate  - required keys, types, enum membership
  4. rules     - deterministic controls applied AFTER the model
                 (the model recommends; rules can only make handling stricter)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .schema import BOOL_FIELDS, ENUMS, REQUIRED_FIELDS


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
    for key in BOOL_FIELDS:
        if key in out:
            out[key], changed = _to_bool(out[key])
            if changed:
                repairs.append(f"{key}: coerced string to bool")
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
    extra = set(obj) - set(REQUIRED_FIELDS)
    if extra:
        errors.append(f"unexpected fields: {sorted(extra)}")
    return errors


def apply_rules(rec: dict, overrides: list) -> dict:
    """Deterministic controls (team plan P4: non-bypassable review rule).
    They can only tighten handling, never relax it; routing is left to the
    model because routing is what the PoC is testing."""
    if rec.get("regulatory_concern") and not rec.get("human_review_required"):
        rec["human_review_required"] = True
        overrides.append("R1: regulatory_concern -> human_review_required=true")
    if rec.get("fraud_concern") and not rec.get("human_review_required"):
        rec["human_review_required"] = True
        overrides.append("R2: fraud_concern -> human_review_required=true")
    if rec.get("routing") == "Card Fraud & Security" and not rec.get("human_review_required"):
        rec["human_review_required"] = True
        overrides.append("R3: fraud routing -> human_review_required=true")
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
