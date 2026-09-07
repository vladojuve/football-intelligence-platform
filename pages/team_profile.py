"""Club profile: who they were that season, how they played, and who stood out.

Two halves that answer different questions. The **record** half comes from
results — where they finished, home and away, best and worst days — and needs no
model at all. The **style** half comes from the 28-feature marts and says nothing
about how good any of it was. Keeping them visibly separate is the point: the
league table is fact, the style profile is description.
"""

import pandas as pd
import streamlit as st

from src.app import charts, data, routing
from src.app.insights import summarise_special_players
from src.app.labels import format_value, pretty
from src.clustering.style_model import nearest_teams
from src.features.team_match import STYLE_FEATURES

RING_COUNT = 8
COLUMNS_PER_ROW = 4

# The same two shapes the player profile offers, for the same reason: the rings
# are read at a glance, the table is what a report looks like.
RINGS = "Rings"
TABLE = "Table & radar"
VIEWS = (RINGS, TABLE)

st.title(":material/shield: Club profile")

season = data.team_season()
style = data.team_style()
space = data.style_space()
matches_by_team = data.team_match()
fixtures = data.matches()
players = data.players()

team_names = sorted(season["team"])
requested = routing.param(routing.TEAM)
default_index = team_names.index(requested) if requested in team_names else None

with st.container(border=True):
    pick, features_column = st.columns([3, 2])
    team = pick.selectbox("Club", team_names, index=default_index,
                          placeholder="Select a club…")
    n_features = features_column.slider("Style features to list", 8,
                                        len(STYLE_FEATURES), 14)

if team is None:
    st.info("Pick a club, or search for one from the home page.",
            icon=":material/search:")
    st.stop()

if routing.param(routing.TEAM) != team:
    st.query_params[routing.TEAM] = team

row = season[season["team"] == team].iloc[0]
style_row = style[style["team"] == team].iloc[0]
record = data.club_record(team)

# --- Who they were ---------------------------------------------------------

st.header(team)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Final position", f"{record['position']}", border=True)
col2.metric("Points", record["points"], border=True)
col3.metric("Record (W-D-L)",
            f"{record['won']}-{record['drawn']}-{record['lost']}", border=True)
col4.metric("Goals (for-against)",
            f"{record['goals_for']}-{record['goals_against']}",
            f"{record['goal_difference']:+d} GD", delta_color="off", border=True)
col5.metric("Clean sheets", record["clean_sheets"], border=True)

info_left, info_right = st.columns(2)
with info_left, st.container(border=True):
    st.markdown("**Home and away**")
    splits = pd.DataFrame([
        {"Venue": "Home", **record["home"]},
        {"Venue": "Away", **record["away"]},
    ]).rename(columns={
        "played": "P", "won": "W", "drawn": "D", "lost": "L",
        "goals_for": "GF", "goals_against": "GA", "points": "Pts"})
    st.dataframe(splits, hide_index=True, width="stretch")
with info_right, st.container(border=True):
    st.markdown("**Season facts**")
    st.markdown(
        f"- **Style cluster:** {style_row['cluster_label']}\n"
        f"- **Home ground:** {record['stadium'] or 'unknown'}\n"
        f"- **Biggest win:** {record['biggest_win']}\n"
        f"- **Heaviest defeat:** {record['biggest_defeat']}\n"
        f"- **Failed to score in:** {record['failed_to_score']} matches\n"
        f"- **Last six results:** `{record['form']}`"
    )

# --- How they played -------------------------------------------------------

st.divider()
st.subheader("Style fingerprint")

view = st.segmented_control(
    "View", list(VIEWS), default=RINGS, key="club_view",
    label_visibility="collapsed",
) or RINGS

st.caption(
    "Percentile against the other 19 clubs on the features where this side was "
    "furthest from average. "
    + (
        "The number in each ring is the percentile; the value beneath it is the "
        "season average. A darker ring means a higher rank."
        if view == RINGS else
        "Green is the top quarter of the league, red the bottom quarter."
    )
)

percentiles = pd.DataFrame({
    "feature": STYLE_FEATURES,
    "percentile": [float(row[f"pct_{f}"]) * 100 for f in STYLE_FEATURES],
    "value": [float(row[f"{f}_mean"]) for f in STYLE_FEATURES],
})
percentiles["distance_from_average"] = (percentiles["percentile"] - 50).abs()
ranked = percentiles.sort_values("distance_from_average", ascending=False)
rings = ranked.head(RING_COUNT)

if view == RINGS:
    for start in range(0, len(rings), COLUMNS_PER_ROW):
        chunk = rings.iloc[start:start + COLUMNS_PER_ROW]
        slots = st.columns(COLUMNS_PER_ROW)
        for column, (_, feature_row) in zip(slots, chunk.iterrows(), strict=False):
            with column:
                st.markdown(charts.ring_label(pretty(feature_row["feature"])),
                            text_alignment="center", width="stretch")
                st.plotly_chart(
                    charts.percentile_donut(
                        percentile=feature_row["percentile"],
                        value_text=format_value(feature_row["feature"],
                                                feature_row["value"]),
                    ),
                    width="stretch",
                    key=f"team_ring_{feature_row['feature']}",
                    config={"displayModeBar": False},
                )
else:
    table_column, radar_column = st.columns([1, 1])
    dataset = data.config()["dataset"]

    with table_column:
        table_rows: list[tuple[str, str, float | None]] = [
            ("League", dataset["competition_name"], None),
            ("Season", dataset["season_name"], None),
            ("Finished", f"{record['position']} of {len(season)}", None),
            ("Style cluster", style_row["cluster_label"], None),
        ]
        for _, feature_row in rings.iterrows():
            table_rows.append((
                pretty(feature_row["feature"]),
                f"{charts.ordinal(feature_row['percentile'])} percentile",
                float(feature_row["percentile"]),
            ))
        table_rows.append(("Matches played", str(int(row["matches"])), None))

        st.dataframe(
            charts.profile_table(team, table_rows),
            hide_index=True, width="stretch", row_height=38,
            height=charts.table_height(len(table_rows)),
        )

    with radar_column:
        st.plotly_chart(
            charts.radar(
                labels=[charts.radar_label(pretty(f)) for f in rings["feature"]],
                series={team: [float(p) for p in rings["percentile"]]},
            ),
            width="stretch", key="club_radar",
        )

st.caption(
    "PPDA is inverted by nature: a **low** value means the side pressed hard, so a "
    "high percentile there means they pressed *less* than most."
)

# --- Where they played the ball -------------------------------------------

pie_column, bars_column = st.columns([1, 2])

with pie_column:
    # Wide, halfspace and everything else partition the same denominator —
    # touches in the attacking half — so this genuinely is a part of a whole.
    wide = float(row["wide_touch_share_mean"])
    halfspace = float(row["halfspace_touch_share_mean"])
    st.plotly_chart(
        charts.share_pie(
            labels=["Wide channel", "Halfspace", "Central & box"],
            values=[wide, halfspace, max(0.0, 1.0 - wide - halfspace)],
            title="Attacking-half touches by channel",
        ),
        width="stretch",
        key="team_channel_pie",
        config={"displayModeBar": False},
    )
    st.caption(
        "Share of this side's touches in the attacking half, by channel. "
        "League average: "
        f"{season['wide_touch_share_mean'].mean():.0%} wide, "
        f"{season['halfspace_touch_share_mean'].mean():.0%} halfspace."
    )

with bars_column:
    bars = ranked.head(n_features).copy()
    bars["feature"] = bars["feature"].map(pretty)
    st.plotly_chart(
        charts.percentile_bars(bars, "feature", "percentile",
                               title="Most distinctive features"),
        width="stretch",
        key="team_percentile_bars",
    )

# --- Special players -------------------------------------------------------

st.divider()
st.subheader("Special players")
st.caption(
    "Players who finished in the **league's top three** for a metric — ranked "
    "across all 344 qualified players, not within their role. This is the one "
    "place in the app that compares a centre-back to a striker, and it is "
    "deliberate: a league leader is a league leader."
)

entries = data.special_player_entries()
club_entries = entries[entries["team"] == team] if not entries.empty else entries

if club_entries.empty:
    st.info(f"No {team} player finished in the league's top three for any metric.",
            icon=":material/info:")
else:
    summary = summarise_special_players(club_entries)
    highest = int(summary["top3_count"].max())
    floor = 1
    if highest > 1:
        floor = st.slider(
            "Minimum number of top-three finishes", 1, highest, 1,
            help="Raise this when a club has too many players to read at a glance.",
        )
    shown = summary[summary["top3_count"] >= floor]
    shown = shown.merge(
        players[["player_id", "display_name", "role", "primary_position", "minutes"]],
        on="player_id", how="left")

    st.dataframe(
        shown[["display_name", "primary_position", "role", "top3_count",
               "best_rank", "metrics"]],
        hide_index=True, width="stretch",
        column_config={
            "display_name": "Player",
            "primary_position": "Position",
            "role": "Role group",
            "top3_count": st.column_config.NumberColumn(
                "Top-3 finishes", format="%d",
                help="How many metrics this player finished top three in"),
            "best_rank": st.column_config.NumberColumn(
                "Best rank", format="%d", help="1 = led the league"),
            "metrics": st.column_config.TextColumn("Metrics", width="large"),
        },
    )

    with st.expander("Every top-three finish, metric by metric"):
        detail = club_entries.merge(players[["player_id", "display_name"]],
                                    on="player_id", how="left")
        detail["value"] = [format_value(m, v) for m, v
                           in zip(detail["metric"], detail["value"], strict=True)]
        st.dataframe(
            detail[["display_name", "metric_label", "rank", "value"]]
            .sort_values(["rank", "metric_label"]),
            hide_index=True, width="stretch",
            column_config={"display_name": "Player", "metric_label": "Metric",
                           "rank": "League rank", "value": "Value"},
        )

    open_columns = st.columns(4)
    for slot, (_, player) in zip(open_columns, shown.head(4).iterrows(), strict=False):
        if slot.button(player["display_name"], key=f"special_{player['player_id']}",
                       icon=":material/person:", width="stretch"):
            routing.go(routing.PLAYER_PROFILE,
                       **{routing.PLAYER: int(player["player_id"])})

# --- Neighbours and consistency -------------------------------------------

st.divider()
left, right = st.columns(2)

with left:
    st.subheader("Most similar clubs")
    near = nearest_teams(space, team, n=5)
    near = near.merge(style[["team", "cluster_label"]], on="team", how="left")
    st.dataframe(
        near.round(2), hide_index=True, width="stretch",
        column_config={
            "team": "Club",
            "distance": st.column_config.NumberColumn(
                "Distance", help="Euclidean distance in the standardized style space"),
            "cluster_label": "Their cluster",
        },
    )
    st.caption("Computed across all 28 features — neighbours may sit in another cluster.")

with right:
    st.subheader("Versus the cluster centroid")
    cluster_teams = style[style["cluster_label"] == style_row["cluster_label"]]["team"]
    centroid = space.z.loc[cluster_teams].mean()
    deltas = (space.z.loc[team] - centroid).sort_values()
    comparison = pd.concat([deltas.head(4), deltas.tail(4)]).to_frame("difference")
    comparison.index.name = "feature"
    comparison = comparison.reset_index()
    comparison["feature"] = comparison["feature"].map(pretty)
    st.dataframe(
        comparison.round(2), hide_index=True, width="stretch",
        column_config={"feature": "Feature",
                       "difference": st.column_config.NumberColumn(
                           "vs cluster (z)",
                           help="Positive means higher than the cluster average")},
    )
    st.caption(f"Distance to centroid: **{style_row['centroid_distance']:.2f}** — "
               "higher means the label describes this side less well.")

st.divider()
st.subheader("Match-to-match variability")
st.caption(
    "How much each feature moves from game to game. A rigid side and an adaptable one "
    "can share the same season average — the spread is what separates them."
)

variability = pd.DataFrame({
    "feature": STYLE_FEATURES,
    "sd": [float(row[f"{f}_sd"]) for f in STYLE_FEATURES],
})
shares = variability[variability["sd"] < 1.0]      # comparable 0-1 scale features
shares = shares.nlargest(n_features, "sd").copy()
shares["feature"] = shares["feature"].map(pretty)
st.plotly_chart(charts.variability_bars(shares, "feature", "sd"), width="stretch",
                key="team_variability")

with st.expander("Match-by-match detail"):
    team_matches = matches_by_team[matches_by_team["team"] == team]
    feature = st.selectbox("Feature", STYLE_FEATURES, format_func=pretty,
                           index=STYLE_FEATURES.index("possession_share"))
    detail = team_matches[["match_id", "opponent", feature]].sort_values("match_id")
    st.line_chart(detail.set_index("match_id")[feature])
    st.dataframe(detail.round(3), hide_index=True, width="stretch",
                 column_config={"opponent": "Opponent", feature: pretty(feature)})

# --- Results ---------------------------------------------------------------

st.divider()
st.subheader("Results")

results = record["matches"][
    ["match_week", "match_date", "venue", "opponent", "goals_for",
     "goals_against", "result", "match_id"]
].copy()
results["score"] = results["goals_for"].astype(str) + "–" + \
    results["goals_against"].astype(str)
# Same labelled link as the fixture list, pointing at the matches page.
results["report"] = results["match_id"].map(routing.match_report_url)

selection = st.dataframe(
    results[["report", "match_week", "match_date", "venue", "opponent", "score",
             "result"]],
    hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
    key="club_results", row_height=44,
    column_config={
        "report": st.column_config.LinkColumn(
            "Match report", display_text=routing.OPEN_REPORT,
            width="medium", pinned=True,
            help="Style features, lineups and player totals for this match"),
        "match_week": st.column_config.NumberColumn("MW", format="%d"),
        "match_date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
        "venue": "Venue", "opponent": "Opponent", "score": "Score", "result": "",
    },
)
st.caption("Click **Open match report** on any row.")

chosen_rows = selection.selection["rows"] if selection and selection.selection else []
if chosen_rows:
    match_id = int(results.iloc[chosen_rows[0]]["match_id"])
    routing.go(routing.MATCHES, **{routing.MATCH: match_id})

st.caption(f"{len(fixtures)} matches in the dataset; {len(results)} of them {team}'s.")
