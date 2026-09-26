"""Build the representative DEVELOPMENT sample for the billing-dispute scope.

    py scripts/make_dev_sample.py --csv "<path>/ABI_Bank_Complaints_Development_8000.csv"

Scope (Group 1, Team Exercise 3): product = Credit card, issue = Billing
disputes -> 653 development cases, routed to Card Billing Disputes or
Card Fraud & Security.

Sample = ALL 27 "rule-error" dev cases (fraud_indicator = Yes but true
owner = Card Billing Disputes; the reference rule is wrong on every one by
construction, plan item P3) + a seeded random 8 clean billing + 8 fraud
cases for context.

Only the narrative is ever sent to the model (data-dictionary leakage rule).
Labels are stored as `expected` for scoring only. The course CSV and the
generated sample stay out of Git (see .gitignore); only record IDs are
committed, in cases/dev_billing_sample_ids.txt.
The held-out file is never read here (plan item P7: one frozen run only).
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", default=str(ROOT / "data" / "dev_billing_sample.jsonl"))
    ap.add_argument("--n-clean", type=int, default=8)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    if "heldout" in pathlib.Path(a.csv).name.lower():
        raise SystemExit("Refusing to sample the held-out evaluation file (plan item P7).")

    with open(a.csv, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if r["product"] == "Credit card" and r["issue"] == "Billing disputes"]
    assert all(r["course_record_id"].startswith("DEV-") for r in rows), "non-development rows found"

    rule_err = [r for r in rows if r["fraud_indicator"] == "Yes" and r["routing_destination"] == "Card Billing Disputes"]
    clean_bill = [r for r in rows if r["fraud_indicator"] == "No" and r["routing_destination"] == "Card Billing Disputes"]
    fraud = [r for r in rows if r["routing_destination"] == "Card Fraud & Security"]
    rng = random.Random(a.seed)
    picked = ([("rule_error", r) for r in rule_err]
              + [("clean_billing", r) for r in rng.sample(clean_bill, a.n_clean)]
              + [("fraud_security", r) for r in rng.sample(fraud, a.n_clean)])

    out = pathlib.Path(a.out)
    out.parent.mkdir(exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for group, r in picked:
            f.write(json.dumps({
                "id": r["course_record_id"],
                "type": group,
                "text": r["consumer_complaint_narrative"],
                "word_count": int(r["word_count"]),
                "label_status": r["label_status"],
                "reference_rule_routing": "Card Fraud & Security" if r["fraud_indicator"] == "Yes" else "Card Billing Disputes",
                "expected": {
                    "routing": r["routing_destination"],
                    "human_review_required": r["human_review_required"] == "Yes",
                    "fraud_concern": r["fraud_indicator"] == "Yes",
                    "regulatory_concern": r["regulatory_indicator"] == "Potential",
                },
            }, ensure_ascii=False) + "\n")
    ids = ROOT / "cases" / "dev_billing_sample_ids.txt"
    ids.parent.mkdir(exist_ok=True)
    ids.write_text("\n".join(f"{g}\t{r['course_record_id']}" for g, r in picked) + "\n", encoding="utf-8")
    print(f"scope rows={len(rows)} rule_error={len(rule_err)} sample={len(picked)} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
