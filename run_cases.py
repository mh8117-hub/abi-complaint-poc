"""Run the representative complaint cases through the model + parser and
save execution evidence.

Usage (VPN connected, env vars set):
    python run_cases.py --list-models
    python run_cases.py --model "llama-3.1-8b-instruct"
Offline self-check (no network, uses canned outputs):
    python -m unittest discover -s tests -v

Evidence written to evidence/run_<UTC timestamp>.jsonl and a
matching _summary.json (model, prompt version, git commit, pass counts).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import platform
import subprocess
import sys

from complaint_triage import build_messages, parse_model_output, PROMPT_VERSION
from complaint_triage.client import OpenWebUIClient

ROOT = pathlib.Path(__file__).parent
SCORED = ("issue_category", "urgency", "routing", "human_review_required")


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_cases(path: pathlib.Path) -> list:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama-3.1-8b-instruct")
    ap.add_argument("--cases", default=str(ROOT / "cases" / "cases.jsonl"))
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--list-models", action="store_true")
    args = ap.parse_args()

    client = OpenWebUIClient()
    if args.list_models:
        for m in client.list_models():
            print(m)
        return 0

    cases = load_cases(pathlib.Path(args.cases))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = ROOT / "evidence" / f"run_{stamp}.jsonl"
    out_path.parent.mkdir(exist_ok=True)

    counts = {"valid": 0, "invalid": 0, "unparseable": 0, "error": 0}
    field_hits = {k: 0 for k in SCORED}
    with out_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            row = {"case_id": case["id"], "case_type": case.get("type"), "expected": case.get("expected")}
            try:
                resp = client.chat(args.model, build_messages(case["text"]), temperature=args.temperature)
                row.update(raw_output=resp["content"], latency_s=resp["latency_s"],
                           usage=resp["usage"], model_reported=resp["model_reported"])
                result = parse_model_output(resp["content"])
                row["parse"] = result.to_dict()
                counts[result.status] += 1
                if result.status == "valid":
                    row["field_match"] = {k: result.record.get(k) == case["expected"].get(k) for k in SCORED}
                    for k, ok in row["field_match"].items():
                        field_hits[k] += ok
            except Exception as e:  # keep going; record the failure as evidence
                row["error"] = f"{type(e).__name__}: {e}"
                counts["error"] += 1
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            status = row.get("parse", {}).get("status", "error")
            print(f"{case['id']:4} {status:12} {row.get('latency_s', '-')}s  {row.get('field_match', row.get('error', ''))}")

    summary = {
        "run_utc": stamp,
        "git_commit": git_commit(),
        "endpoint": client.base_url + "/api/chat/completions",
        "model_requested": args.model,
        "temperature": args.temperature,
        "seed": 42,
        "prompt_version": PROMPT_VERSION,
        "n_cases": len(cases),
        "status_counts": counts,
        "field_accuracy_on_valid": {k: f"{v}/{counts['valid']}" for k, v in field_hits.items()},
        "client_host": platform.node(),
        "python": sys.version.split()[0],
    }
    (out_path.with_name(out_path.stem + "_summary.json")).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
