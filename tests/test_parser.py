"""Offline tests for the parser using canned model outputs that imitate
the kinds of drift small instruction models produce."""

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from complaint_triage import parse_model_output  # noqa: E402

GOOD = {
    "summary": "Customer reports an unauthorized card transaction and two unsuccessful disputes.",
    "issue_category": "Fraud or unauthorized transaction",
    "urgency": "High",
    "risk_flags": ["fraud"],
    "routing": "Card Fraud and Security",
    "escalation": True,
    "human_review_required": True,
    "recommended_action": "Route for fraud investigation.",
    "rationale": "Customer says 'I never made this purchase'.",
}


class ParserTests(unittest.TestCase):
    def test_clean_json(self):
        r = parse_model_output(json.dumps(GOOD))
        self.assertEqual(r.status, "valid")
        self.assertEqual(r.repairs, [])

    def test_code_fence_and_prose(self):
        raw = "Here is the JSON:\n```json\n" + json.dumps(GOOD) + "\n```\nLet me know!"
        r = parse_model_output(raw)
        self.assertEqual(r.status, "valid")
        self.assertIn("stripped markdown code fence", r.repairs)

    def test_trailing_comma_and_string_bool(self):
        bad = dict(GOOD, escalation="true", urgency="high")
        raw = json.dumps(bad)[:-1] + ",}"
        r = parse_model_output(raw)
        self.assertEqual(r.status, "valid", r.errors)
        self.assertIs(r.record["escalation"], True)
        self.assertEqual(r.record["urgency"], "High")

    def test_invalid_enum_is_reported_not_guessed(self):
        r = parse_model_output(json.dumps(dict(GOOD, routing="Fraud Department")))
        self.assertEqual(r.status, "invalid")
        self.assertTrue(any("routing" in e for e in r.errors))

    def test_missing_field(self):
        d = dict(GOOD); d.pop("rationale")
        r = parse_model_output(json.dumps(d))
        self.assertEqual(r.status, "invalid")

    def test_unparseable(self):
        r = parse_model_output("I'm sorry, I can't help with that.")
        self.assertEqual(r.status, "unparseable")

    def test_rule_forces_human_review_on_fraud(self):
        r = parse_model_output(json.dumps(dict(GOOD, human_review_required=False)))
        self.assertEqual(r.status, "valid")
        self.assertTrue(r.record["human_review_required"])
        self.assertTrue(r.rule_overrides)

    def test_risk_flags_none_string(self):
        r = parse_model_output(json.dumps(dict(GOOD, risk_flags="none", urgency="Low", escalation=False,
                                               human_review_required=False)))
        self.assertEqual(r.status, "valid", r.errors)
        self.assertEqual(r.record["risk_flags"], [])


if __name__ == "__main__":
    unittest.main()
