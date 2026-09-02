r"""Phase 8: export a small, committable database for the deployed app.

The full curated database is ~277 MB because it holds 1.3M raw events. The app
never queries those — it reads the feature marts and the style model, which
together are under a megabyte. This script copies just those tables into
`data/sample/app.duckdb`, which **is** committed so the app can be deployed
without running the pipeline.

What is published is derived aggregate data (per-90 metrics, percentiles, style
features) computed by this project, not StatsBomb's raw event data, which stays
local and gitignored. Attribution requirements still apply — see DATA_SOURCES.md.

Usage (from the repo root):
    .venv\Scripts\python scripts\build_app_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATA_DIR

SOURCE_DB = DATA_DIR / "curated.duckdb"
TARGET_DB = DATA_DIR / "sample" / "app.duckdb"

# Tables the app actually reads.
APP_TABLES = [
    "mart_player_season",
    "mart_team_season",
    "mart_team_match",
    "model_team_style",
    "dim_matches",
]


def main() -> None:
    if not SOURCE_DB.exists():
        print(f"{SOURCE_DB} not found — run the pipeline first.")
        sys.exit(1)

    TARGET_DB.parent.mkdir(parents=True, exist_ok=True)
    if TARGET_DB.exists():
        TARGET_DB.unlink()

    source = duckdb.connect(str(SOURCE_DB), read_only=True)
    # Coverage figures the app shows on the home page come from tables we do not
    # ship, so they are frozen into a tiny metadata table instead.
    event_count = source.execute("SELECT count(*) FROM fact_events").fetchone()[0]
    source.close()

    target = duckdb.connect(str(TARGET_DB))
    target.execute(f"ATTACH '{SOURCE_DB}' AS src_db (READ_ONLY)")
    for table in APP_TABLES:
        target.execute(f"CREATE TABLE {table} AS SELECT * FROM src_db.{table}")
        rows = target.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table:<24} {rows:>6} rows")
    target.execute("DETACH src_db")

    target.execute("CREATE TABLE pipeline_stats (metric VARCHAR, value BIGINT)")
    target.execute("INSERT INTO pipeline_stats VALUES ('events', ?)", [event_count])
    target.close()

    size_mb = TARGET_DB.stat().st_size / 1_000_000
    print(f"\nWrote {TARGET_DB} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
