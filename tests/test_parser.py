"""Offline tests for the parser using canned model outputs that imitate
the kinds of drift small instruction models produce."""

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from complaint_triage import parse_model_output  # noqa: E402

GOOD = {
    "summary": "Customer disputes a timeshare charge after the merchant misrepresented terms; merchant refused a refund.",
    "customer_request": "Reverse the charge",
    "disputed_amount": "not stated",
    "prior_contact_attempted": True,
    "routing": "Card Billing Disputes",
    "fraud_concern": False,
    "regulatory_concern": False,
    "human_review_required": False,
    "rationale": "Customer authorized the purchase but says 'we were told' false terms.",
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
        bad = dict(GOOD, prior_contact_attempted="true", routing="card billing disputes")
        raw = json.dumps(bad)[:-1] + ",}"
        r = parse_model_output(raw)
        self.assertEqual(r.status, "valid", r.errors)
        self.assertIs(r.record["prior_contact_attempted"], True)
        self.assertEqual(r.record["routing"], "Card Billing Disputes")

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

    def test_rule_regulatory_forces_review(self):
        r = parse_model_output(json.dumps(dict(GOOD, regulatory_concern=True)))
        self.assertEqual(r.status, "valid")
        self.assertTrue(r.record["human_review_required"])
        self.assertTrue(any(o.startswith("R1") for o in r.rule_overrides))

    def test_rule_fraud_routing_forces_review(self):
        r = parse_model_output(json.dumps(dict(GOOD, routing="Card Fraud & Security")))
        self.assertTrue(r.record["human_review_required"])
        self.assertTrue(any(o.startswith("R3") for o in r.rule_overrides))

    def test_rules_never_relax(self):
        r = parse_model_output(json.dumps(dict(GOOD, human_review_required=True)))
        self.assertTrue(r.record["human_review_required"])
        self.assertEqual(r.rule_overrides, [])


if __name__ == "__main__":
    unittest.main()
