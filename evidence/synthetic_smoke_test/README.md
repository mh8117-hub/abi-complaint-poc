# Synthetic smoke test (superseded)

The first DGX runs on 26 Sep 2026: 8 hand-written synthetic complaints, 2 runs each, using the broader 9-field / 6-queue schema (prompt `baseline-v1`).
- Code: commit `55c0d88`. Evidence first committed in `6ec4435`.
- The case file was `cases/cases.jsonl`, which was removed from HEAD in `6095019`. Check out `55c0d88` to reproduce.
- Kept because the Assignment 4 record cites two findings from it: the model obeyed an instruction embedded in complaint C08, and only 4/8 raw outputs repeated at temperature 0.

The current results on the course development data are in `evidence/` (runs `20260926T194442Z` and `20260926T195259Z`, code `6095019`).
