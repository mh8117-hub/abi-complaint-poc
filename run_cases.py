"""Run complaint cases through the model + parser and save execution evidence.

Usage (VPN connected, env vars set; see README):
    py run_cases.py --list-models
    py run_cases.py --cases data/dev_billing_sample.jsonl
Offline self-check:  py -m unittest discover -s tests -v

Writes evidence/run_<UTC>.jsonl (one row per case: raw model output,
parsed record, errors, rule overrides, per-field match, latency, tokens;
the narrative itself is NOT copied) and run_<UTC>_summary.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import platform
import statistics
import subprocess
import sys

from complaint_triage import build_messages, parse_model_output, PROMPT_VERSION
from complaint_triage.client import OpenWebUIClient

ROOT = pathlib.Path(__file__).parent


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_cases(path: pathlib.Path) -> list:
    cases = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if any(str(c.get("id", "")).startswith("HEL-") for c in cases):
        raise SystemExit("Held-out records found in case file; refusing to run (plan item P7).")
    return cases


def pct(n, d):
    return f"{n}/{d}" + (f" ({100*n/d:.0f}%)" if d else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama-3.1-8b-instruct")
    ap.add_argument("--cases", default=str(ROOT / "data" / "dev_billing_sample.jsonl"))
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

    rows = []
    with out_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            row = {k: case.get(k) for k in ("id", "type", "word_count", "label_status", "reference_rule_routing", "expected")}
            try:
                resp = client.chat(args.model, build_messages(case["text"]), temperature=args.temperature)
                row.update(raw_output=resp["content"], latency_s=resp["latency_s"],
                           usage=resp["usage"], model_reported=resp["model_reported"])
                result = parse_model_output(resp["content"])
                row["parse"] = result.to_dict()
                if result.status == "valid":
                    try:
                        row["model_raw_human_review"] = json.loads(resp["content"][resp["content"].find("{"):resp["content"].rfind("}") + 1]).get("human_review_required")
                    except Exception:
                        row["model_raw_human_review"] = None
                    row["field_match"] = {k: result.record.get(k) == v for k, v in case["expected"].items()}
            except Exception as e:  # keep going; the failure is evidence
                row["error"] = f"{type(e).__name__}: {e}"
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            rows.append(row)
            print(f"{row['id']:10} {row.get('type',''):15} {row.get('parse', {}).get('status', 'error'):11} "
                  f"{row.get('latency_s', '-')}s {row.get('field_match', row.get('error', ''))}", flush=True)

    valid = [r for r in rows if r.get("parse", {}).get("status") == "valid"]
    status = {s: sum(1 for r in rows if r.get("parse", {}).get("status", "error") == s)
              for s in ("valid", "invalid", "unparseable", "error")}

    def acc(subset, key):
        v = [r for r in subset if r in valid]
        return pct(sum(r["field_match"][key] for r in v), len(subset))

    groups = sorted({r.get("type") for r in rows})
    lat = sorted(r["latency_s"] for r in rows if "latency_s" in r)
    reg = [r for r in rows if r["expected"].get("regulatory_concern")]
    reg_v = [r for r in reg if r in valid]
    summary = {
        "run_utc": stamp,
        "git_commit": git_commit(),
        "endpoint": client.base_url + "/api/chat/completions",
        "model_requested": args.model,
        "temperature": args.temperature,
        "seed": 42,
        "prompt_version": PROMPT_VERSION,
        "case_file": pathlib.Path(args.cases).name,
        "n_cases": len(rows),
        "status_counts": status,
        "routing_accuracy": {"all": acc(rows, "routing"), **{g: acc([r for r in rows if r.get("type") == g], "routing") for g in groups}},
        "reference_rule_routing_accuracy_same_cases": pct(sum(r["reference_rule_routing"] == r["expected"]["routing"] for r in rows), len(rows)),
        "human_review_accuracy_after_rules": acc(rows, "human_review_required"),
        "human_review_recall_on_regulatory_subset_after_rules": pct(sum(r["parse"]["record"]["human_review_required"] for r in reg_v), len(reg)),
        "fraud_concern_agreement": acc(rows, "fraud_concern"),
        "regulatory_concern_agreement": acc(rows, "regulatory_concern"),
        "rule_overrides_fired": sum(1 for r in valid if r["parse"]["rule_overrides"]),
        "latency_s": {"median": statistics.median(lat), "p95": lat[max(0, int(round(0.95 * len(lat))) - 1)], "max": lat[-1]} if lat else None,
        "client_host": platform.node(),
        "python": sys.version.split()[0],
    }
    (out_path.with_name(out_path.stem + "_summary.json")).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
