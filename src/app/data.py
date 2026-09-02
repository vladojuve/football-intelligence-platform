"""Cached data access for the Streamlit app.

Streamlit re-runs the whole script on every interaction, so everything that
touches disk or does real work is cached:

    @st.cache_resource  the DuckDB connection and the fitted style space
    @st.cache_data      dataframes loaded from the marts

Without this, moving a slider would re-open the database and re-fit PCA.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from ..clustering.style_model import StyleSpace, build_style_space
from ..config import DATA_DIR, PROJECT_ROOT, load_config
from ..similarity.feature_matrix import RoleMatrix, build_role_matrix

# The full curated database is built locally and gitignored (~277 MB, mostly raw
# events). The committed app database holds only the marts the app reads, so a
# deployment works without running the pipeline.
FULL_DB_PATH = DATA_DIR / "curated.duckdb"
APP_DB_PATH = DATA_DIR / "sample" / "app.duckdb"

# Resolution order: an explicit override, then the full local database, then the
# committed one. The override lets a deployment point somewhere else, and lets
# the tests exercise the shipped configuration without moving any files.
DB_PATH_ENV_VAR = "FIP_DB_PATH"


def _resolve_db_path() -> Path:
    override = os.environ.get(DB_PATH_ENV_VAR)
    if override:
        return Path(override)
    return FULL_DB_PATH if FULL_DB_PATH.exists() else APP_DB_PATH


DB_PATH = _resolve_db_path()
MANIFEST_PATH = DATA_DIR / "raw" / "manifest.json"


@st.cache_resource
def connection() -> duckdb.DuckDBPyConnection:
    """One read-only DuckDB connection shared across reruns."""
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_resource
def config() -> dict:
    return load_config()


def _table(name: str) -> pd.DataFrame:
    return connection().execute(f"SELECT * FROM {name}").df()


@st.cache_data
def player_season() -> pd.DataFrame:
    return _table("mart_player_season")


@st.cache_data
def team_season() -> pd.DataFrame:
    return _table("mart_team_season")


@st.cache_data
def team_match() -> pd.DataFrame:
    return _table("mart_team_match")


@st.cache_data
def team_style() -> pd.DataFrame:
    return _table("model_team_style")


def _event_count(con: duckdb.DuckDBPyConnection) -> int:
    """Raw event count: read from fact_events locally, or the frozen stat when
    running against the committed app database, which does not ship events."""
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if "fact_events" in tables:
        return con.execute("SELECT count(*) FROM fact_events").fetchone()[0]
    if "pipeline_stats" in tables:
        row = con.execute(
            "SELECT value FROM pipeline_stats WHERE metric = 'events'").fetchone()
        if row:
            return int(row[0])
    return 0


@st.cache_data
def dataset_summary() -> dict:
    """Coverage figures and the raw-layer download timestamp for the home page."""
    con = connection()
    counts = {
        "matches": con.execute("SELECT count(*) FROM dim_matches").fetchone()[0],
        "events": _event_count(con),
        "players_qualified": con.execute("SELECT count(*) FROM mart_player_season").fetchone()[0],
        "teams": con.execute("SELECT count(*) FROM mart_team_season").fetchone()[0],
    }
    downloaded_at = None
    if MANIFEST_PATH.exists():
        downloaded_at = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("downloaded_at")
    counts["downloaded_at"] = downloaded_at
    return counts


@st.cache_resource
def role_matrix(role: str) -> RoleMatrix:
    """The standardized feature matrix for one role group."""
    cfg = config()
    return build_role_matrix(
        player_season(), role, cfg["role_features"][role],
        cfg["similarity"]["winsorize_lower"], cfg["similarity"]["winsorize_upper"],
    )


@st.cache_resource
def style_space() -> StyleSpace:
    """The fitted PCA style space for teams."""
    cfg = config()["clustering"]
    return build_style_space(team_season(), cfg["pca_variance_target"], cfg["random_state"])


def display_name(row: pd.Series) -> str:
    """Prefer a player's common short name over their full registered name."""
    nickname = row.get("nickname")
    if isinstance(nickname, str) and nickname.strip():
        return nickname
    return row["player_name"]


@st.cache_data
def player_options() -> pd.DataFrame:
    """Selectable players with a readable label, sorted by name."""
    players = player_season()[
        ["player_id", "player_name", "nickname", "role", "primary_position",
         "minutes", "team_id"]
    ].copy()
    players["label"] = players.apply(
        lambda r: f"{display_name(r)}  ·  {r['role']}  ·  {r['minutes']:.0f} min", axis=1
    )
    return players.sort_values("label").reset_index(drop=True)


def read_markdown(filename: str) -> str:
    """Load a documentation file from the repository root or docs/."""
    for candidate in (PROJECT_ROOT / filename, PROJECT_ROOT / "docs" / filename):
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return f"_{filename} not found._"
