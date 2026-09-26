"""Output contract, aligned with Group 1's Gate 2 scope (Team Exercise 3).

Bounded capability: employee-facing intake support for credit-card
billing disputes. From the complaint narrative alone, produce a
structured case record, a routing recommendation between two
destinations, and a human-review flag. The employee decides.

History: commit 55c0d88 used a broader 9-field, 6-queue schema on 8
synthetic cases (schema/prompt "baseline-v1"). It was replaced here once the
team's scope and the course dataset were available.
"""

SCHEMA_VERSION = "billing-v1"

ROUTING_QUEUES = [
    "Card Billing Disputes",
    "Card Fraud & Security",
]

# field -> expected python type after normalization
REQUIRED_FIELDS = {
    "summary": str,                  # structured case record ...
    "customer_request": str,
    "disputed_amount": str,          # "not stated" allowed; never invented
    "prior_contact_attempted": bool,
    "routing": str,                  # recommendation only
    "fraud_concern": bool,
    "regulatory_concern": bool,
    "human_review_required": bool,
    "rationale": str,
}

BOOL_FIELDS = [k for k, t in REQUIRED_FIELDS.items() if t is bool]

ENUMS = {
    "routing": ROUTING_QUEUES,
}
