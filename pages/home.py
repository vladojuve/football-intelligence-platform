"""Home: one search box, the way you would expect a search page to work.

The page is deliberately near-empty above the fold. Every other page in the app
needs you to already know what you are looking for — a role group, a cluster, a
minutes threshold — and this one does not: type a name, get the page about it.
"""

import streamlit as st

from src.app import data, routing
from src.app.search import search_all

# Keeps the search block in the middle of a wide screen instead of pinned to the
# left edge, which is what makes it read as a search page rather than a form.
_LEFT, _CENTRE, _RIGHT = st.columns([1, 2.2, 1])

with _CENTRE:
    st.markdown("")
    st.title("⚽ Football Intelligence", text_alignment="center")
    st.markdown(
        "#### Search for a player or a team to get detailed data "
        "from the 2015/16 season.",
        text_alignment="center", width="stretch",
    )

    query = st.text_input(
        "Search",
        key="home_query",
        placeholder="Try “Ngolo Kante”, “Leicester”, or “Arsenal vs Leicester”…",
        label_visibility="collapsed",
        icon=":material/search:",
    )
    # Centred under the box rather than left-aligned beneath it: the button and
    # the field read as one control that way. Pressing Enter in the box does the
    # same thing — the button is there because a search page is expected to have
    # one, not because it is the only way through.
    with st.container(horizontal=True, horizontal_alignment="center"):
        searched = st.button("Search", type="primary", icon=":material/search:")

players = data.player_options()
teams = data.team_style()
fixtures = data.matches()

query = (query or "").strip()

if query:
    hits = search_all(players, teams, fixtures, query)
    total = sum(len(group) for group in hits.values())

    with _CENTRE:
        if total == 0:
            st.warning(
                f"Nothing matched “{query}”. Only players with at least 600 minutes "
                "in the 2015/16 Premier League are in the database.",
                icon=":material/search_off:",
            )
        else:
            st.divider()

        # Players first: they are the most common thing to look for, and a query
        # that names a club still returns that club immediately below.
        sections = [
            ("player", "Players", routing.PLAYER_PROFILE, routing.PLAYER),
            ("team", "Clubs", routing.TEAM_PROFILE, routing.TEAM),
            ("match", "Matches", routing.MATCHES, routing.MATCH),
        ]
        for kind, heading, page, parameter in sections:
            group = hits[kind]
            if not group:
                continue
            st.markdown(f"**{heading}**")
            for hit in group:
                if st.button(
                    f"{hit.title}  ·  {hit.subtitle}",
                    key=f"hit_{kind}_{hit.key}",
                    width="stretch",
                ):
                    routing.go(page, **{parameter: hit.key})
            st.markdown("")
elif searched:
    with _CENTRE:
        st.info("Type a name first.", icon=":material/edit:")

# --- Below the search: what is actually in here ---------------------------

st.divider()

summary = data.dataset_summary()
config = data.config()["dataset"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Matches", f"{summary['matches']:,}", border=True)
col2.metric("Events", f"{summary['events']:,}", border=True)
col3.metric("Qualified players", summary["players_qualified"], border=True)
col4.metric("Teams", summary["teams"], border=True)

st.caption(
    f"{config['competition_name']} {config['season_name']} · "
    f"raw data downloaded {summary['downloaded_at'] or 'unknown'}"
)

left, right = st.columns(2)

with left, st.container(border=True):
    st.subheader("Player recruitment similarity")
    st.markdown(
        """
Pick a reference player and get a ranked list of players who **do similar
things**, with an explanation of *why* each one is similar and where they differ.

- Features are standardized **within role group**, so a centre-back is never
  compared against a winger's scale.
- Candidates are filtered by role, minutes and data coverage **before** scoring.
- Every result decomposes into the dimensions where the players match and clash.
"""
    )
    if st.button("Find similar players", icon=":material/search:",
                 key="cta_similar"):
        routing.go(routing.PLAYER_SEARCH)

with right, st.container(border=True):
    st.subheader("Team playing-style classification")
    st.markdown(
        """
28 style features per team per match — possession, directness, territory, width,
pressing, transitions, chance profile and risk — aggregated to a season profile
**and its match-to-match variability**.

- PCA reveals the main style axes; k-means groups teams into style clusters.
- Cluster labels were written **after** inspecting the centroids, never before.
- Nearest-team similarity crosses cluster boundaries, so no side is trapped by
  its label.
"""
    )
    if st.button("Open the style map", icon=":material/scatter_plot:",
                 key="cta_style"):
        routing.go(routing.TEAM_STYLE_MAP)

st.warning(
    "**These results are descriptive.** Similarity means two players *do similar "
    "things* — it is not evidence of equal quality, tactical fit for a particular "
    "system, or transfer value. Team clusters describe how sides played, not how well. "
    "This platform makes no match-result predictions.",
    icon=":material/warning:",
)

st.info(
    "Data provided by **StatsBomb**. See the Methodology page for metric definitions, "
    "validation results and known limitations.",
    icon=":material/info:",
)
