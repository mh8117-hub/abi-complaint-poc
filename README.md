# Complaint triage: model call + structured-output parser (candidate contribution)

ABI Week 4, Assignment 4. This is a bounded candidate component for the team's baseline scaffold. It answers one question: **what can an unadapted, locally hosted model already do?**

```
complaint text -> prompt (baseline-v1) -> Open WebUI on DGX Spark (Llama-3.1-8B-Instruct)
              -> parser: extract -> normalize -> validate -> deterministic rules
              -> evidence/run_<ts>.jsonl  (raw output + parsed record + errors + latency)
```

## Files
| Path | Purpose |
|---|---|
| `complaint_triage/schema.py` | Output contract: fields, allowed categories, urgency, risk flags, routing queues |
| `complaint_triage/prompt.py` | Baseline system prompt (zero-shot, no examples) |
| `complaint_triage/client.py` | Open WebUI client, standard library only |
| `complaint_triage/parser.py` | Parses raw model text into a validated record or a logged failure; applies rules R1/R2 |
| `cases/cases.jsonl` | 8 synthetic representative cases with expected labels, including 2 edge cases (privacy, prompt injection) |
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

python run_cases.py --list-models                # copy the exact model id
python run_cases.py --model "<exact id>"
```

## Verified API facts
Open WebUI's chat endpoint is `POST /api/chat/completions`, not the OpenAI-style `/v1/chat/completions`. Authentication uses `Authorization: Bearer <key>`. Models are listed with `GET /api/models`. Source: https://docs.openwebui.com/getting-started/api-endpoints/. The docs do not document `response_format` JSON mode, so this component does not rely on it. JSON is requested in the prompt and enforced by the parser.

## Blocker and workaround (course DGX)
On the course Open WebUI (v0.11.3 at 172.22.42.174:8080), API keys are disabled by the admin: Settings > Account shows no API Keys section. The documented alternative is the user's JWT. To get it, open the site while logged in, press F12, and in the Console type `localStorage.token`. Put the value in `OPENWEBUI_API_KEY`. The JWT expires and is tied to a personal login, so it is fine for a PoC but not for a shared service. The team should ask the course admin for a service API key.

## Deterministic rules (run after the model; they can only make handling stricter)
- **R1**: a `fraud`, `regulatory` or `vulnerable_customer` flag sets `human_review_required=true`.
- **R2**: `urgency=High` sets `escalation=true`.

## Known limits
- The 8 cases are synthetic and the labels are one student's judgment. They are not a benchmark.
- The parser fixes formatting drift only. It never guesses a missing or off-list category, so those outputs are recorded as `invalid`.
- `temperature=0` and `seed=42` are requested, but whether the backend honours the seed was not verified.
