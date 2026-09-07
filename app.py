"""Football Intelligence Platform — Streamlit entry point.

Run from the repo root:
    .venv\\Scripts\\streamlit run app.py
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

st.set_page_config(
    page_title="Football Intelligence Platform",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from src.app import routing

# Navigation sits in the top header rather than the sidebar, which leaves the
# sidebar free for each page's own filters. The pages under the empty-string
# section are shown flat at the start of the bar; the rest become dropdowns, so
# eight pages fit without the bar wrapping.
PAGES = {
    "": [
        st.Page(routing.HOME, title="Home", icon=":material/home:", default=True),
        st.Page(routing.MATCHES, title="Matches", icon=":material/stadium:"),
    ],
    "Players": [
        st.Page(routing.PLAYER_SEARCH, title="Find similar players",
                icon=":material/search:"),
        st.Page(routing.PLAYER_PROFILE, title="Player profile",
                icon=":material/person:"),
        st.Page(routing.PLAYER_COMPARISON, title="Compare two players",
                icon=":material/compare_arrows:"),
    ],
    "Clubs": [
        st.Page(routing.TEAM_PROFILE, title="Club profile", icon=":material/shield:"),
        st.Page(routing.TEAM_STYLE_MAP, title="Style map", icon=":material/scatter_plot:"),
    ],
    "About": [
        st.Page(routing.METHODOLOGY, title="Methodology & data quality",
                icon=":material/book_2:"),
    ],
}

st.navigation(PAGES, position="top").run()

st.divider()
st.caption(
    "Data: **StatsBomb Open Data** — Premier League 2015/16. "
    "Results are descriptive, not a judgement of quality."
)
