r"""Measure the storage choices recorded in docs/DECISIONS.md.

ADR-001 claims that Parquet plus DuckDB is the right pair for this project. The
numbers behind that claim should be reproducible rather than remembered, so this
script regenerates them: the size of each layer, and the time one representative
aggregation takes against each of the four ways the data could be stored.

The query — count passes per team across all 1.3M events — is deliberately
typical of the pipeline's real work: it scans every row, touches two columns, and
groups. Nothing here is tuned to flatter any option.

Usage (from the repo root):
    .venv\Scripts\python scripts\benchmark_storage.py

Layers that have not been built yet are skipped, so this runs on a fresh clone
(which only has the committed app database) as well as on a full local build.
"""

from __future__ import annotations

import glob
import json
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATA_DIR

RAW_EVENTS = DATA_DIR / "raw" / "events"
STAGING_EVENTS = DATA_DIR / "staging" / "fact_events"
CURATED_DB = DATA_DIR / "curated.duckdb"
APP_DB = DATA_DIR / "sample" / "app.duckdb"

# One query, expressed once. `{source}` is whatever that storage option calls the
# events: a table name, or a function reading Parquet files.
QUERY = """
    SELECT team_id, count(*) AS passes
    FROM {source}
    WHERE type = 'Pass'
    GROUP BY team_id
    ORDER BY passes DESC
"""


def directory_size_mb(path: Path) -> tuple[int, float]:
    """(file count, megabytes) for a directory, or (1, size) for a single file."""
    if path.is_file():
        return 1, path.stat().st_size / 1_048_576
    files = [p for p in path.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files) / 1_048_576


def report_sizes() -> None:
    print("Layer sizes")
    print(f"  {'path':<34}{'files':>7}{'MB':>10}")
    for label, path in (
        ("data/raw/events (JSON)", RAW_EVENTS),
        ("data/staging/fact_events (Parquet)", STAGING_EVENTS),
        ("data/curated.duckdb", CURATED_DB),
        ("data/sample/app.duckdb", APP_DB),
    ):
        if not path.exists():
            print(f"  {label:<34}{'—':>7}{'not built':>10}")
            continue
        count, megabytes = directory_size_mb(path)
        print(f"  {label:<34}{count:>7}{megabytes:>10.1f}")
    print()


# A single timing is not worth quoting: the first read of a file comes off disk
# and every later one comes out of the OS page cache, which moved these numbers
# by 2-3x between runs. The median of several repeats, after one warm-up, is
# stable enough to put in a document.
REPEATS = 5


def timed(label: str, run) -> None:
    """Time a query `REPEATS` times after a warm-up, and report the median."""
    result = run()                                    # warm-up, not measured
    timings = []
    for _ in range(REPEATS):
        start = time.perf_counter()
        run()
        timings.append(time.perf_counter() - start)
    median = sorted(timings)[len(timings) // 2]
    print(f"  {label:<52}{median:>9.3f}s{len(result):>7} rows")


def benchmark() -> None:
    print(f"One aggregation over 1.3M events, four ways "
          f"(median of {REPEATS}, after a warm-up)")

    if CURATED_DB.exists():
        connection = duckdb.connect(str(CURATED_DB), read_only=True)
        try:
            timed("DuckDB, table in curated.duckdb",
                  lambda: connection.execute(QUERY.format(source="fact_events")).df())
        finally:
            connection.close()

    if STAGING_EVENTS.exists():
        pattern = str(STAGING_EVENTS / "*.parquet")
        connection = duckdb.connect()
        try:
            timed("DuckDB, straight over the Parquet files",
                  lambda: connection.execute(
                      QUERY.format(source=f"read_parquet('{pattern}')")).df())
        finally:
            connection.close()

        def with_pandas() -> pd.Series:
            # Only the two columns the query needs are read off disk — the whole
            # point of a columnar format.
            frame = pd.read_parquet(STAGING_EVENTS, columns=["type", "team_id"])
            return frame[frame["type"] == "Pass"].groupby("team_id").size()

        timed("pandas read_parquet(columns=...) + groupby", with_pandas)

    if RAW_EVENTS.exists():
        def from_json() -> dict:
            counts: dict[int, int] = {}
            for path in glob.glob(str(RAW_EVENTS / "*.json")):
                with open(path, encoding="utf-8") as handle:
                    for event in json.load(handle):
                        if event.get("type", {}).get("name") != "Pass":
                            continue
                        team_id = event.get("team", {}).get("id")
                        counts[team_id] = counts.get(team_id, 0) + 1
            return counts

        timed("raw JSON, parsed in Python", from_json)

    print()


def main() -> None:
    if not any(p.exists() for p in (RAW_EVENTS, STAGING_EVENTS, CURATED_DB)):
        print("Nothing to measure: run scripts/build_staging.py first.")
        sys.exit(1)
    report_sizes()
    benchmark()
    print("Recorded in docs/DECISIONS.md (ADR-001).")


if __name__ == "__main__":
    main()
