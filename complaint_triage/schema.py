"""Output contract for the complaint-triage structured output.

Field set mirrors the employee-facing example in the course briefing
("What You Are Building", p.1): summary, issue, urgency, routing,
escalation, human review, recommended action -- plus risk flags and a
short rationale so an employee can inspect *why*.
"""

ISSUE_CATEGORIES = [
    "Fraud or unauthorized transaction",
    "Billing, fees, or charges dispute",
    "Account access or login",
    "Loan or mortgage servicing",
    "Credit reporting",
    "Customer service conduct",
    "Other",
]

URGENCY_LEVELS = ["Low", "Medium", "High"]

RISK_FLAGS = ["fraud", "regulatory", "privacy", "vulnerable_customer"]

ROUTING_QUEUES = [
    "Card Fraud and Security",
    "Billing and Disputes",
    "Digital Banking Support",
    "Mortgage and Lending Servicing",
    "Credit Reporting Disputes",
    "General Customer Care",
]

# field -> expected python type after normalization
REQUIRED_FIELDS = {
    "summary": str,
    "issue_category": str,
    "urgency": str,
    "risk_flags": list,
    "routing": str,
    "escalation": bool,
    "human_review_required": bool,
    "recommended_action": str,
    "rationale": str,
}

ENUMS = {
    "issue_category": ISSUE_CATEGORIES,
    "urgency": URGENCY_LEVELS,
    "routing": ROUTING_QUEUES,
}
