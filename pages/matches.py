"""Matches: every fixture in the season, and everything the pipeline knows about one.

The page has two modes in one file. Without a `?match=` parameter it is the
fixture list; with one it is the match report. They are not split into two pages
because the list exists only to reach the report — a separate page would put a
dead end in the top navigation.

The report is assembled from four tables that were built for other purposes:
`dim_matches` for the result, `mart_team_match` for the two style profiles,
`fact_lineups` for who played, and `mart_player_match` for what they did. Nothing
here is a new mart.
"""

import pandas as pd
import streamlit as st

from src.app import charts, data, routing
from src.app.labels import format_value, pretty
from src.features.team_match import STYLE_FEATURES

st.title(":material/stadium: Matches")

fixtures = data.matches()
team_matches = data.team_match()
available = data.tables()

selected_id = routing.int_param(routing.MATCH)

# --- Fixture list ----------------------------------------------------------

if selected_id is None or selected_id not in set(fixtures["match_id"]):
    st.caption(
        f"All {len(fixtures)} Premier League matches of "
        f"{data.config()['dataset']['season_name']}. Select a row to open the "
        "full report."
    )

    clubs = sorted(set(fixtures["home_team"]) | set(fixtures["away_team"]))
    with st.container(border=True):
        club_column, week_column = st.columns([2, 3])
        club = club_column.selectbox("Club", ["All clubs", *clubs])
        weeks = week_column.slider(
            "Matchweek", int(fixtures["match_week"].min()),
            int(fixtures["match_week"].max()),
            (int(fixtures["match_week"].min()), int(fixtures["match_week"].max())),
        )

    shown = fixtures[fixtures["match_week"].between(*weeks)]
    if club != "All clubs":
        shown = shown[(shown["home_team"] == club) | (shown["away_team"] == club)]

    listing = shown[["match_week", "match_date", "home_team", "home_score",
                     "away_score", "away_team", "stadium", "match_id"]].copy()
    listing["score"] = listing["home_score"].astype(str) + "–" + \
        listing["away_score"].astype(str)

    selection = st.dataframe(
        listing[["match_week", "match_date", "home_team", "score", "away_team",
                 "stadium"]],
        hide_index=True, width="stretch", height=560,
        on_select="rerun", selection_mode="single-row", key="fixture_list",
        column_config={
            "match_week": st.column_config.NumberColumn("MW", format="%d"),
            "match_date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
            "home_team": "Home", "score": "Score", "away_team": "Away",
            "stadium": "Stadium",
        },
    )
    rows = selection.selection["rows"] if selection and selection.selection else []
    if rows:
        routing.go(routing.MATCHES,
                   **{routing.MATCH: int(listing.iloc[rows[0]]["match_id"])})
    st.stop()

# --- Match report ----------------------------------------------------------

match = fixtures[fixtures["match_id"] == selected_id].iloc[0]
home, away = match["home_team"], match["away_team"]

if st.button("All matches", icon=":material/arrow_back:"):
    st.query_params.clear()
    st.rerun()

st.header(f"{home} {match['home_score']}–{match['away_score']} {away}")
st.caption(
    f"Matchweek {match['match_week']} · "
    f"{pd.to_datetime(match['match_date']).strftime('%A %d %B %Y')} · "
    f"{match['stadium'] or 'stadium unknown'} · "
    f"referee {match['referee'] or 'unknown'}"
)

sides = team_matches[team_matches["match_id"] == selected_id]
if len(sides) != 2:
    st.warning("No style features were built for this match.", icon=":material/warning:")
    st.stop()

home_side = sides[sides["team"] == home].iloc[0]
away_side = sides[sides["team"] == away].iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"{home} possession", f"{home_side['possession_share']:.0%}", border=True)
col2.metric(f"{away} possession", f"{away_side['possession_share']:.0%}", border=True)
col3.metric(f"{home} field tilt", f"{home_side['field_tilt']:.0%}", border=True)
col4.metric(f"{away} field tilt", f"{away_side['field_tilt']:.0%}", border=True)

# --- The two sides on the same features ------------------------------------

st.subheader("How the two sides played")

# Only the features that are already a 0-1 share go on the mirrored chart: bars
# growing from a shared centre are only comparable when both halves use the same
# scale, and PPDA or a distance in metres would dwarf everything else.
share_features = [
    feature for feature in STYLE_FEATURES
    if team_matches[feature].dropna().le(1.0).all()
    and team_matches[feature].dropna().ge(0.0).all()
]

mirror = pd.DataFrame({
    "feature": [pretty(f) for f in share_features],
    home: [float(home_side[f]) for f in share_features],
    away: [float(away_side[f]) for f in share_features],
})
st.plotly_chart(
    charts.head_to_head_bars(mirror, "feature", home, away, home, away),
    width="stretch", key="match_mirror",
)
st.caption(
    "Every style feature that is expressed as a share, mirrored around the centre. "
    "The remaining features use their own units and are in the table below."
)

with st.expander("All 28 style features, with units"):
    full = pd.DataFrame({
        "Feature": [pretty(f) for f in STYLE_FEATURES],
        home: [format_value(f, float(home_side[f])) for f in STYLE_FEATURES],
        away: [format_value(f, float(away_side[f])) for f in STYLE_FEATURES],
    })
    st.dataframe(full, hide_index=True, width="stretch")
    st.caption(
        "Possession share and field tilt are opponent-relative and sum to 1.0 across "
        "the two sides. PPDA is inverted: lower means more aggressive pressing."
    )

# --- Who played and what they did ------------------------------------------

st.divider()
st.subheader("Players")

if "fact_lineups" not in available or "mart_player_match" not in available:
    st.info(
        "Per-player match detail is not in this database build. Run "
        "`scripts/build_app_db.py` to include `fact_lineups` and `mart_player_match`.",
        icon=":material/info:",
    )
    st.stop()

lineups = data.lineups()
per_match = data.player_match()
qualified = set(data.players()["player_id"])

match_lineups = lineups[lineups["match_id"] == selected_id]
match_players = per_match[per_match["match_id"] == selected_id]

STAT_COLUMNS = {
    "touches": "Touches", "passes": "Passes", "passes_completed": "Completed",
    "prog_passes": "Prog. passes", "prog_carries": "Prog. carries",
    "final_third_entries": "Final-third entries", "box_entries": "Box entries",
    "key_passes": "Key passes", "xg_assisted": "xG assisted",
    "shots": "Shots", "npxg": "npxG", "np_goals": "NP goals",
    "pressures": "Pressures", "tackles": "Tackles",
    "interceptions": "Interceptions", "recoveries": "Recoveries",
    "aerials_won": "Aerials won", "turnovers": "Turnovers",
}

# All eighteen columns at once do not fit on a laptop screen, and a table that
# scrolls sideways is a table nobody reads the right-hand end of. The two views
# below are the questions actually asked of a match: what did they do with the
# ball, and what did they do without it.
STAT_VIEWS = {
    "On the ball": ["touches", "passes", "passes_completed", "prog_passes",
                    "prog_carries", "final_third_entries", "box_entries",
                    "key_passes", "xg_assisted", "shots", "npxg", "np_goals"],
    "Off the ball": ["touches", "pressures", "tackles", "interceptions",
                     "recoveries", "aerials_won", "turnovers"],
    "Everything": list(STAT_COLUMNS),
}

view = st.segmented_control("Statistics", list(STAT_VIEWS), default="On the ball",
                            key="match_stat_view")
columns_shown = STAT_VIEWS[view or "On the ball"]

for side in (home, away):
    side_lineup = match_lineups[match_lineups["team"] == side]
    if side_lineup.empty:
        continue
    st.markdown(f"### {side}")

    stats = side_lineup.merge(
        match_players.drop(columns=["team_id"], errors="ignore"),
        on=["match_id", "player_id"], how="left",
    )
    stats["Role"] = stats["is_starter"].map({True: "Starter", False: "Substitute"})
    stats["Profile"] = stats["player_id"].isin(qualified)

    table = stats[["player_name", "position", "Role", "minutes",
                   *[c for c in columns_shown if c in stats.columns]]].copy()
    table = table.sort_values(["Role", "minutes"], ascending=[True, False])

    st.dataframe(
        table, hide_index=True, width="stretch",
        column_config={
            "player_name": st.column_config.TextColumn("Player", width="medium"),
            "position": "Position",
            "minutes": st.column_config.NumberColumn("Min", format="%.0f"),
            "xg_assisted": st.column_config.NumberColumn("xG assisted", format="%.2f"),
            "npxg": st.column_config.NumberColumn("npxG", format="%.2f"),
            **{column: STAT_COLUMNS[column] for column in STAT_COLUMNS
               if column in table.columns and column not in ("npxg", "xg_assisted")},
        },
    )

    on_the_pitch = side_lineup[side_lineup["played"]]
    st.caption(
        f"{len(side_lineup)} named, {len(on_the_pitch)} played. Counts are raw match "
        "totals, not per-90 rates — a substitute's numbers are not comparable to a "
        "starter's without adjusting for minutes."
    )

    # Only players who cleared the 600-minute season threshold have a profile.
    with_profiles = stats[stats["Profile"]].head(6)
    if not with_profiles.empty:
        buttons = st.columns(min(6, len(with_profiles)))
        for slot, (_, player) in zip(buttons, with_profiles.iterrows(), strict=False):
            if slot.button(player["player_name"].split()[-1],
                           key=f"match_player_{player['player_id']}",
                           icon=":material/person:", width="stretch"):
                routing.go(routing.PLAYER_PROFILE,
                           **{routing.PLAYER: int(player["player_id"])})

st.divider()
club_left, club_right, _ = st.columns([1, 1, 3])
if club_left.button(home, icon=":material/shield:", key="match_home_club"):
    routing.go(routing.TEAM_PROFILE, **{routing.TEAM: home})
if club_right.button(away, icon=":material/shield:", key="match_away_club"):
    routing.go(routing.TEAM_PROFILE, **{routing.TEAM: away})
