# Complaint triage: model call + structured-output parser (candidate contribution)

ABI Week 4, Assignment 4. This is a bounded candidate component for Group 1's baseline scaffold. It answers one question: **what can an unadapted, locally hosted model already do?**

**Scope (Group 1 Gate 2 plan, TW3):** credit-card billing disputes. From the narrative alone the component produces a structured case record, a routing recommendation between `Card Billing Disputes` and `Card Fraud & Security`, and a human-review flag. The employee decides.

```
narrative -> prompt (billing-v1, zero-shot) -> Open WebUI on DGX Spark (Llama-3.1-8B-Instruct)
              -> parser: extract -> normalize -> validate -> deterministic rules
              -> evidence/run_<ts>.jsonl  (raw output + parsed record + errors + latency)
```

## Files
| Path | Purpose |
|---|---|
| `complaint_triage/schema.py` | Output contract: 9-field case record, 2 routing destinations |
| `complaint_triage/prompt.py` | Baseline system prompt (zero-shot, no examples) |
| `complaint_triage/client.py` | Open WebUI client, standard library only |
| `complaint_triage/parser.py` | Parses raw model text into a validated record or a logged failure; applies review rules R1–R3 |
| `scripts/make_dev_sample.py` | Builds the 43-case DEVELOPMENT sample (all 27 rule-error cases + 8 clean billing + 8 fraud, seed 7) from the course CSV; refuses the held-out file |
| `cases/dev_billing_sample_ids.txt` | The exact course_record_ids used (the course data itself is not committed) |
| `run_cases.py` | Runs the cases and writes evidence |
| `tests/test_parser.py` | Offline parser tests (no network) |

## Requirements
Python 3.8 or later. No third-party packages. You need the NYU VPN ("NYU-NET Traffic Only") to reach the DGX Spark Open WebUI.

## Reproduce
```bash
git clone <repo> && cd abi-complaint-poc && git checkout candidate/mh8117-structured-parser
python -m unittest discover -s tests -v          # offline check (Windows: use `py` if `python` opens the Microsoft Store)

# Windows PowerShell
$env:OPENWEBUI_BASE_URL="http://<open-webui-host>"   # the address you open in the browser
py login_helper.py                                 # signs in and stores the token (password is not echoed)
$env:OPENWEBUI_API_KEY=[Environment]::GetEnvironmentVariable("OPENWEBUI_API_KEY","User")
# macOS/Linux: export OPENWEBUI_BASE_URL=...; export OPENWEBUI_API_KEY=...

py scripts/make_dev_sample.py --csv "<path>\ABI_Bank_Complaints_Development_8000.csv"
py run_cases.py --list-models                    # copy the exact model id
py run_cases.py --model "llama-3.1-8b-instruct"
```

## Verified API facts
Open WebUI's chat endpoint is `POST /api/chat/completions`, not the OpenAI-style `/v1/chat/completions`. Authentication uses `Authorization: Bearer <key>`. Models are listed with `GET /api/models`. Source: https://docs.openwebui.com/getting-started/api-endpoints/. The docs do not document `response_format` JSON mode, so this component does not rely on it. JSON is requested in the prompt and enforced by the parser.

## Blocker and workaround (course DGX)
On the course Open WebUI (v0.11.3 at 172.22.42.174:8080), API keys are disabled by the admin: Settings > Account shows no API Keys section. The documented alternative is the user's JWT. To get it, open the site while logged in, press F12, and in the Console type `localStorage.token`. Put the value in `OPENWEBUI_API_KEY`. The JWT expires and is tied to a personal login, so it is fine for a PoC but not for a shared service. The team should ask the course admin for a service API key.

## Deterministic rules (run after the model; they can only make handling stricter)
- **R1** (plan P4, non-bypassable): `regulatory_concern` sets `human_review_required=true`.
- **R2**: `fraud_concern` sets `human_review_required=true`.
- **R3**: routing to `Card Fraud & Security` sets `human_review_required=true`.
Routing itself is left to the model, because routing is what the PoC tests.

## Data handling
- Only `consumer_complaint_narrative` is sent to the model (data-dictionary leakage rule). The labels are used for scoring only.
- The held-out file is never read. Plan P7 allows one frozen run only. Both scripts refuse `HEL-` records.
- The course CSVs and `data/` are git-ignored. Evidence rows contain the model output and IDs, not the narrative.

## Known limits
- The labels are rule-generated synthetic course labels (label_provenance), not bank ground truth.
- The 43-case sample over-represents the 27 rule-error cases on purpose (plan P3). Its overall accuracy is not an estimate of accuracy on all 653 cases.
- `evidence/synthetic_smoke_test/` holds an earlier run on 8 synthetic cases with a broader schema (baseline-v1, code 55c0d88).
- The parser fixes formatting drift only. It never guesses a missing or off-list category, so those outputs are recorded as `invalid`.
- `temperature=0` and `seed=42` are requested, but whether the backend honours the seed was not verified.
