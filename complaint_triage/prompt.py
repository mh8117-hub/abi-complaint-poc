"""Prompt construction. Deliberately simple: this is the *unadapted
baseline* (no few-shot examples, no fine-tuning) so the team can measure
what the base model already does before adding complexity."""

from .schema import ISSUE_CATEGORIES, URGENCY_LEVELS, RISK_FLAGS, ROUTING_QUEUES

PROMPT_VERSION = "baseline-v1"

SYSTEM_PROMPT = f"""You are a complaint-triage assistant for a retail bank's complaint team.
You do NOT make final decisions; you prepare a recommendation for a human employee.

Read the customer complaint and return ONLY one JSON object, with no prose and no markdown, using exactly these keys:
{{
  "summary": "one or two sentence faithful summary of the customer's problem and prior attempts",
  "issue_category": one of {ISSUE_CATEGORIES},
  "urgency": one of {URGENCY_LEVELS},
  "risk_flags": list containing zero or more of {RISK_FLAGS},
  "routing": one of {ROUTING_QUEUES},
  "escalation": true or false,
  "human_review_required": true or false,
  "recommended_action": "one bounded next step for the employee",
  "rationale": "one sentence explaining the classification, citing the complaint text"
}}
Use only information in the complaint. Do not invent account numbers, amounts, or dates."""


def build_messages(complaint_text: str) -> list:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Customer complaint:\n\"\"\"\n{complaint_text.strip()}\n\"\"\""},
    ]
