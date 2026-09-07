"""Player profile: one player, twelve rings, and the numbers behind them.

Each ring is a percentile **within the player's own role group**, which is the
only comparison that means anything: a centre-back's passing volume against
other centre-backs says something, against wingers it says nothing.

The twelve are the features weighted most heavily for that role in
`feature_config.yml` — the same list the similarity model leans on — so the
profile shows what the model actually looks at, rather than a separate set of
metrics chosen to look good.
"""

import pandas as pd
import streamlit as st

from src.app import charts, data, routing
from src.app.labels import format_value, pretty
from src.similarity.engine import find_similar

RING_COUNT = 12
COLUMNS_PER_ROW = 4

st.title(":material/person: Player profile")

players = data.player_options()
season = data.player_season()
config = data.config()

# The page can be reached three ways — a search result, a link from a club or a
# match page, or the picker below — and all three land on the same URL.
requested = routing.int_param(routing.PLAYER)
if requested is not None and requested in set(players["player_id"]):
    default_index = int(players.index[players["player_id"] == requested][0])
else:
    default_index = None

choice = st.selectbox(
    "Player", players["label"], index=default_index,
    placeholder="Search for a player…",
)

if choice is None:
    st.info("Pick a player, or search for one from the home page.",
            icon=":material/search:")
    st.stop()

reference = players[players["label"] == choice].iloc[0]
player_id = int(reference["player_id"])
row = season[season["player_id"] == player_id].iloc[0]
role = row["role"]
matrix = data.role_matrix(role)
role_name = next(g["name"] for g in config["role_groups"] if g["key"] == role)

# Keep the URL in step with the picker so the page can be linked to and reloaded.
if routing.param(routing.PLAYER) != str(player_id):
    st.query_params[routing.PLAYER] = str(player_id)

# The name and club go in the heading rather than into `st.metric` tiles: a
# metric's value is rendered at heading size, so "Leicester City" and "Left
# Defensive Midfield" were being truncated to "Leiceste…" and "Left Def…".
# Metrics are for the values that are genuinely short — the numbers.
st.header(data.display_name(row))
st.caption(f"{reference['team']} · {row['primary_position']} · {role_name}")

col1, col2, col3 = st.columns(3)
col1.metric("Minutes", f"{row['minutes']:.0f}", border=True)
col2.metric("Matches", int(row["matches_played"]), border=True)
col3.metric("Role group", role, border=True)

if row["low_minutes"]:
    st.warning(
        f"{data.display_name(row)} played {row['minutes']:.0f} minutes, below the "
        f"{config['thresholds']['low_minutes_warning']}-minute mark. Per-90 values "
        "on a small sample move a lot.",
        icon=":material/warning:",
    )

# --- The twelve rings ------------------------------------------------------

st.subheader("Percentile profile")
st.caption(
    f"Ranked against the other {len(matrix.z) - 1} **{role_name.lower()}** with at "
    f"least {config['thresholds']['min_minutes_season']} minutes. The number in each "
    "ring is the percentile; the value beneath it is the raw metric. A darker ring "
    "means a higher rank."
)

weight_order = pd.Series(matrix.weights, index=matrix.features).sort_values(
    ascending=False)
ring_features = weight_order.head(RING_COUNT).index.tolist()

for start in range(0, len(ring_features), COLUMNS_PER_ROW):
    chunk = ring_features[start:start + COLUMNS_PER_ROW]
    for column, feature in zip(st.columns(COLUMNS_PER_ROW), chunk, strict=False):
        percentile = row.get(f"pct_{feature}")
        raw = row.get(feature)
        with column:
            st.markdown(charts.ring_label(pretty(feature)),
                        text_alignment="center", width="stretch")
            if pd.isna(percentile):
                # Rates below their minimum-attempt guard are null on purpose;
                # drawing a ring at zero would read as "worst in the league".
                st.info("Not enough attempts to report this rate.",
                        icon=":material/do_not_disturb_on:")
                continue
            st.plotly_chart(
                charts.percentile_donut(
                    percentile=float(percentile) * 100,
                    value_text=format_value(feature, float(raw)) if pd.notna(raw) else "",
                ),
                width="stretch",
                key=f"ring_{feature}",
                config={"displayModeBar": False},
            )

# --- Every role feature, with the numbers ----------------------------------

st.divider()
st.subheader("All role features")
st.caption(
    "The full feature set the similarity model uses for this role, with the raw "
    "value, the percentile and the weight each one carries."
)

detail = pd.DataFrame({
    "Feature": [pretty(f) for f in matrix.features],
    "Value": [row.get(f) for f in matrix.features],
    "Percentile": [
        None if pd.isna(row.get(f"pct_{f}")) else float(row[f"pct_{f}"]) * 100
        for f in matrix.features
    ],
    "Weight": [float(w) for w in matrix.weights],
})
detail["Value"] = [
    format_value(f, None if pd.isna(v) else float(v))
    for f, v in zip(matrix.features, detail["Value"], strict=True)
]

st.dataframe(
    detail.sort_values("Percentile", ascending=False, na_position="last"),
    hide_index=True, width="stretch",
    column_config={
        "Value": st.column_config.TextColumn("Value", width="small"),
        "Percentile": st.column_config.ProgressColumn(
            "Percentile in role", min_value=0, max_value=100, format="%.0f"),
        "Weight": st.column_config.NumberColumn(
            "Similarity weight", format="%.1f",
            help="How heavily this feature counts when matching players in this role"),
    },
)

# --- Where to go next ------------------------------------------------------

st.divider()
st.subheader("Most similar players")

similar = find_similar(
    matrix, season, player_id, top_n=5,
    min_minutes=config["thresholds"]["min_minutes_season"],
    min_coverage=config["similarity"]["min_feature_coverage"],
)

if similar.empty:
    st.info("No candidate cleared the coverage filter for this player.",
            icon=":material/info:")
else:
    # find_similar returns the registered name; the app shows the common one.
    similar = similar.merge(players[["player_id", "display_name", "team"]],
                            on="player_id", how="left")
    for _, candidate in similar.iterrows():
        row_columns = st.columns([3, 2, 1, 1])
        row_columns[0].markdown(
            f"**{candidate['display_name']}** · {candidate['team']}")
        row_columns[1].markdown(
            f"similarity **{candidate['similarity']:.3f}** · "
            f"{candidate['minutes']:.0f} min")
        if row_columns[2].button("Profile", key=f"sim_profile_{candidate['player_id']}"):
            routing.go(routing.PLAYER_PROFILE, **{routing.PLAYER: int(candidate["player_id"])})
        if row_columns[3].button("Compare", key=f"sim_compare_{candidate['player_id']}"):
            routing.go(
                routing.PLAYER_COMPARISON,
                **{routing.COMPARE_LEFT: player_id,
                   routing.COMPARE_RIGHT: int(candidate["player_id"])},
            )

if st.button("Full similarity search", icon=":material/search:", key="to_search"):
    routing.go(routing.PLAYER_SEARCH, **{routing.PLAYER: player_id})
