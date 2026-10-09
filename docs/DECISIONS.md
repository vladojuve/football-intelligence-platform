# Design decisions

Architectural decisions that are not obvious from reading the code, with the
reasoning and the evidence behind each. A decision belongs here when someone
could reasonably have chosen differently and would want to know why we did not.

Each record states what was decided, what the alternatives were, what it cost,
and what would make it wrong later. Records are append-only: if a decision is
reversed, the old record stays and a new one supersedes it.

---

## ADR-001 — Parquet files and DuckDB, not a database server

**Status:** accepted · **Decided** 2026-07-24 (Phase 2), no-server choice
reaffirmed 2026-07-29 · **Recorded** 2026-10-09

### Context

The pipeline turns 1,313,773 raw StatsBomb events into feature marts and then
serves them to a Streamlit app. That needs two things decided, and they are
genuinely separate decisions that are often conflated:

1. **A file format** for the staging layer — how flattened events sit on disk.
2. **A query engine** for the curated layer — what runs the aggregations, the
   quality checks and the app's reads.

The constraints were: a single developer, no concurrent writers, a dataset that
fits comfortably on a laptop, and a deployment target (Streamlit Community
Cloud) with no database attached and no budget.

### Decision

**Parquet for staging, DuckDB for curated, and no database server.**

```
data/raw/        unchanged JSON, as published        1,077 MB
data/staging/    Parquet, one file per match           150 MB
data/curated/    DuckDB, tables and marts              278 MB
data/sample/     DuckDB, marts only — committed          3 MB
```

### Alternatives considered — file format

| Option | Why not |
|---|---|
| **Keep the JSON** | 7× the disk, and every read re-parses text into Python objects. Measured at 13.4s for one aggregation that Parquet answers in 0.04s. |
| **CSV** | No types — every read guesses whether `team_id` is an integer. Nested fields have to be flattened into strings. Larger than Parquet as well. |
| **Pickle** | Fast, but Python-only, fragile across versions, and unsafe to load from an untrusted source. A dead end for anything handed to another tool or person. |
| **Feather / Arrow IPC** | Genuinely good and marginally faster to read, but compresses worse and is less universally supported. Parquet is what every other tool already reads. |

**Why Parquet wins here specifically.** Football event data is extraordinarily
repetitive — `type` is `"Pass"` roughly 400,000 times, `team_id` has twenty
distinct values across 1.3M rows — so dictionary encoding compresses it hard.
It is columnar, and the queries touch two or three columns out of about forty.
Types live in the file, so `match_date` comes back as a timestamp rather than a
string to re-parse. And one file per match means the build streams: it never
holds 1.3M rows in memory at once.

### Alternatives considered — query engine

| Option | What it offers | Why not here |
|---|---|---|
| **pandas alone** | No new dependency | ~45× slower on the benchmark below, and joins across four marts become a pile of `merge()` calls that read worse than SQL. No constraints, and no single artefact to ship. |
| **SQLite** | Standard library, zero install, single file | Row-oriented — built to fetch one record, not to aggregate 1.3M. Analytical SQL is weaker (limited window functions, no `QUALIFY`, fewer types). |
| **PostgreSQL** | A real database; the conventional "proper" answer | Needs a server, a connection string, credentials, and an install or a container. For one user with no concurrent writers that is pure cost. **Adding it would have been résumé-driven complexity**, and being able to defend its absence is worth more than pretending it was required. |
| **BigQuery / Snowflake** | Scales to terabytes | 1.3M rows is 150 MB. A cloud warehouse adds cost, latency, credentials and a network dependency to solve a problem this project does not have. |
| **Spark** | Scales further still | Same objection, plus a JVM. Spark starts paying off well above "fits on a laptop". |

**Why DuckDB wins here specifically.** It is in-process like SQLite, so there is
no server, port or credential. It gives real analytical SQL for the mart builds
and the quality checks. It **reads Parquet directly**, so the staging layer can
be queried with no database at all. And the whole thing is one file, which is
what actually makes the deployment work: `data/sample/app.duckdb` is 3 MB, sits
in the repository, and the deployed app reads it without running the pipeline. A
Postgres design would have needed a hosted database and a connection secret just
to show the project to someone.

### Evidence

Reproduce with `scripts/benchmark_storage.py`. One representative query — count
passes per team across every event — run four ways. Median of five runs after a
warm-up, because a cold first read came off disk 2–3× slower and a single timing
is not worth quoting.

| Approach | Time | Relative |
|---|---|---|
| DuckDB, table inside `curated.duckdb` | **0.003 s** | 1× |
| DuckDB, reading the Parquet files directly | **0.038 s** | 13× |
| pandas `read_parquet(columns=[...])` + groupby | **0.176 s** | 59× |
| Raw JSON, parsed in Python | **13.441 s** | ~4,500× |

Those timings are from one machine and will differ on another; the ordering and
the order of magnitude are the point, not the third decimal place.

### Consequences

**What this bought**

- Queries fast enough to explore with rather than wait on — the difference
  between 0.003s and 13s is the difference between iterating and not.
- SQL for the work SQL is good at: the 15 quality checks, the mart builds, the
  app's reads.
- A deployable artefact. The committed 3 MB database is why CI can test the
  *deployed* configuration on every push, and why the app runs on a free tier
  with no infrastructure.
- No operational surface: nothing to provision, secure, back up or pay for.

**What it cost — honestly**

- **`curated.duckdb` is 278 MB, larger than the 150 MB of Parquet it was built
  from.** DuckDB's storage is not more compact than Parquet here. We are paying
  disk for query speed and SQL ergonomics, not saving it.
- **One writer or many readers, never both.** Re-running `build_staging.py`
  requires stopping the Streamlit dev server first, because it holds a read-only
  connection. Postgres would not have that problem; for one developer it is an
  annoyance, on a team it would be a real constraint.
- **The SQL dialect has sharp edges.** `ATTACH` does not accept bound
  parameters, so `scripts/build_app_db.py` has to build that statement with an
  f-string; and `full` is a reserved word, which is why the attached database is
  aliased `src_db`. Small, but each cost time to discover.
- **Parquet is not human-readable.** Which is exactly why the raw layer stays as
  unchanged JSON — when a number looks wrong, the source can be read by eye.

### When this becomes the wrong choice

- **More than one writer** → PostgreSQL. DuckDB's single-writer model is a hard
  stop, not a tuning problem.
- **Data that no longer fits one machine** → a warehouse or Spark. The threshold
  is roughly tens of gigabytes on a laptop.
- **Many concurrent users needing low-latency point lookups** → DuckDB is an
  analytical engine; a busy web backend wants Postgres or a key-value store.
- **Streaming or frequently updated data** → Parquet files are immutable; you
  rewrite rather than update. Correct for a finished season, wrong for live
  data. Worth noting because a sibling project ingests daily — partitioning by
  date keeps Parquet viable there, but if it ever needs updates rather than
  appends, this record no longer applies to it.

### Related

- `src/config.py` — the paths
- `scripts/build_staging.py` — writes Parquet, loads DuckDB, runs the checks
- `scripts/build_app_db.py` — exports the committed 3 MB database
- `scripts/benchmark_storage.py` — regenerates every number above

---

## Decisions recorded elsewhere

Not everything significant belongs in this file. These were decided with their
reasoning, and that reasoning lives next to the thing it governs:

| Decision | Where |
|---|---|
| StatsBomb Open Data 2015/16 — event depth over recency | [METHODOLOGY.md](../METHODOLOGY.md), "Why this dataset"; audit in [data_audit.csv](data_audit.csv) |
| No match-result or betting prediction | [README](../README.md) and every page of the app |
| Analytical settings in `feature_config.yml` rather than in code | [artifacts/feature_config.yml](../artifacts/feature_config.yml) |
| Five role groups, and standardizing within them | [MODEL_CARD.md](MODEL_CARD.md) |
| k = 3, chosen on stability as well as silhouette | [CLUSTER_CARD.md](CLUSTER_CARD.md) |
| Repairing doubled apostrophes in staging, not in the app | [METRIC_DICTIONARY.md](METRIC_DICTIONARY.md) |
