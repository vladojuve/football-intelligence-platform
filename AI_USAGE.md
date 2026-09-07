# AI usage

This project was built with heavy use of an AI coding assistant. This document
says what that means in practice, because "AI-assisted" covers everything from
autocomplete to "I did not read the output", and a reader is entitled to know
which.

**Tool:** Anthropic's Claude, via Claude Code, across roughly twenty working
sessions between July and September 2026.

## What the AI did

- **Wrote most of the code.** The ingestion, transformation, feature, similarity,
  clustering and application layers were drafted by the assistant from
  specifications given in conversation, then revised against review comments.
- **Wrote the tests.** All 168 of them, including the regression tests added
  after each bug below.
- **Wrote the documentation**, including this file, the metric dictionary, the
  methodology, the model and cluster cards and the README.
- **Ran the pipeline and the checks**, read the output, and diagnosed failures.
- **Proposed the architecture** — the raw / staging / curated / mart layering, the
  choice of DuckDB over Postgres, the decision to keep analytical settings in a
  YAML file rather than in code.

## What the human decided

- **Scope and non-goals.** In particular the explicit non-goal — no match-result
  or betting prediction — which shapes what the platform is allowed to claim.
- **The dataset.** The assistant audited every available competition-season and
  set out the trade-off; the choice of StatsBomb Open Data 2015/16, accepting
  event depth over recency, was the author's, made after separately investigating
  scraping and commercial APIs and rejecting them.
- **Which proposals to reject.** Several assistant suggestions were declined,
  including an action that would have temporarily renamed the local database — an
  environment-variable override was used instead, which turned out to be better
  for deployment too.
- **The product design.** The search-led home page, the top navigation, the
  percentile rings, the ring/table toggle and the "special players" idea were all
  specified by the author; the assistant implemented them.
- **When something was good enough to ship.**

## How the output was verified

Nothing here relies on the code looking correct. Four independent checks caught
things that review did not:

1. **A blocking quality gate.** The staging build runs 15 hard checks — schema,
   uniqueness, referential integrity, football sanity — and exits non-zero if any
   fails. The marts cannot be built from data that violates them.
2. **Face-validity checks against known football.** Every feature layer was
   spot-checked against the 2015/16 season before being trusted: are the xG
   leaders Agüero, Vardy and Kane; is Kompany top for aerials; is Leicester
   direct and shot-efficient; does the computed league table match the real final
   standings. It does, exactly.
3. **Stability testing rather than accuracy testing.** Neither model has ground
   truth, so both are evaluated on whether their answers survive perturbations
   that should not change them — match resampling, minutes thresholds, feature
   subsets, random restarts.
4. **Continuous integration.** Ruff and the full test suite on every push. Because
   the raw data is gitignored, CI has no local database and falls back to the
   committed one — so every run is also a test of the deployed configuration.

## What the AI got wrong

This is the part worth reading. Every one of these was written by the assistant,
passed review, and was caught by a check rather than by inspection.

| Bug | How it was caught | Why it mattered |
|---|---|---|
| Minutes computed as `last_end − first_start`, counting injury gaps as time on the pitch | Team-minutes reconciliation check | Every per-90 metric was slightly wrong. Fixing it made the warning count go **up** (7 → 15), which is more correct: short-handed periods now show honestly |
| Aerial duels all zero — `aerial_won` is nested per event type, not top-level | Face check showing every centre-back at 0% aerials | A whole feature was silently absent |
| Set-piece shot share of 54% — `play_pattern` labels the whole possession, not the shot | Comparison against published benchmarks | Redefined as corner/free-kick within 10s, excluding throw-ins → 25.5%, matching the benchmark |
| Similarity validation counted a recommendation as "lost" when the player left the candidate pool entirely | Reviewing what the number actually measured | It measured pool shrinkage, not ranking stability, and **understated** the model: 76% → 98% at the 1200-minute threshold |
| Data coverage displayed as "1%" for every player | A generated screenshot | Streamlit's `%%` appends a sign without scaling |
| A test asserting a pass starting at x = 95 was a final-third entry | The test failing | The code was right and the test was wrong — a reminder that AI-written tests are not an independent check of AI-written code |

The pattern: **the errors were in the football, not in the Python.** The code ran;
it computed the wrong quantity. Type checkers and linters cannot catch that, and
neither can reading it. Only comparing the output to something known can.

That last row is the important caveat about this whole workflow. Tests written by
the same assistant that wrote the code share its misunderstandings. The checks
that actually found problems were the ones grounded in something outside the
code: a published benchmark, a real league table, a reconciliation identity, a
screenshot of what a user would see.

## What is not AI-generated

- The data. All figures come from StatsBomb Open Data through the pipeline in
  this repository; nothing is illustrative, estimated or invented.
- The results quoted in the README, methodology and model cards. Each is
  reproducible by running the scripts named beside it.
- The judgement calls: what to build, what to refuse to claim, and when to stop.

## Reproducibility

Every number in this repository can be regenerated from the raw data:

```bash
.venv\Scripts\python scripts\download_data.py
.venv\Scripts\python scripts\build_staging.py
.venv\Scripts\python scripts\build_player_features.py
.venv\Scripts\python scripts\build_team_features.py
.venv\Scripts\python scripts\build_team_clusters.py
.venv\Scripts\python scripts\validate_similarity.py
```

The full pipeline was re-run end to end after the last data fix and reproduced
identical counts, identical clusters and the same 15 known warnings.
