"""Page paths and the query-parameter handoff between pages.

Pages address each other constantly — a search result opens a profile, a club
page opens one of its players, a fixture list opens a match — and each of those
jumps carries an id. Keeping the paths and the parameter names in one module
means a renamed page breaks in one place instead of five, and a link that opens
a profile always spells the parameter the same way.

Paths are relative to the entry point (`app.py`), which is what both `st.Page`
and `st.switch_page` expect.
"""

from __future__ import annotations

import streamlit as st

HOME = "pages/home.py"
PLAYER_SEARCH = "pages/player_search.py"
PLAYER_PROFILE = "pages/player_profile.py"
PLAYER_COMPARISON = "pages/player_comparison.py"
TEAM_PROFILE = "pages/team_profile.py"
TEAM_STYLE_MAP = "pages/team_style_map.py"
MATCHES = "pages/matches.py"
METHODOLOGY = "pages/methodology.py"

# Streamlit serves a page at its filename without the folder or the extension.
# `st.switch_page` wants the path above; a link inside a table needs this. They
# live together so renaming a page breaks both at once.
MATCHES_URL = "/matches"

# The label on that link. A bare row-selection checkbox is a 14px target with
# nothing saying what it does, so every table that leads to a match report
# carries a labelled link column instead, and they all say the same thing.
OPEN_REPORT = "Open match report  →"


def match_report_url(match_id: int | str) -> str:
    """The address of one match report, for a table's link column."""
    return f"{MATCHES_URL}?{MATCH}={match_id}"

# Query-parameter names, so a page reads exactly what another page wrote.
PLAYER = "player"
TEAM = "team"
MATCH = "match"
COMPARE_LEFT = "a"
COMPARE_RIGHT = "b"


def go(page: str, **params: str | int) -> None:
    """Switch to another page, carrying ids in the URL.

    Using the URL rather than session state means a profile can be linked to,
    bookmarked and reloaded — the page works the same whether the user arrived
    by clicking or by pasting a link.
    """
    st.switch_page(page, query_params={k: str(v) for k, v in params.items()})


def param(name: str) -> str | None:
    """Read one query parameter, or None if it is absent or empty."""
    value = st.query_params.get(name)
    if isinstance(value, list):          # repeated parameters: take the first
        value = value[0] if value else None
    return value or None


def int_param(name: str) -> int | None:
    """Read a query parameter that should be an id.

    A hand-edited URL is untrusted input like any other, so a non-numeric value
    is treated as absent rather than being allowed to raise on the page.
    """
    raw = param(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None
