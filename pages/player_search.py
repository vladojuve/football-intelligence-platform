"""Player search: pick a reference player, filter candidates, rank by similarity."""

import streamlit as st

from src.app import data, routing
from src.similarity.engine import find_similar

st.title(":material/search: Find similar players")
st.caption(
    "Candidates are filtered by role, minutes and data coverage **before** similarity "
    "is computed, so an incompatible role can never surface on a statistical fluke."
)

players = data.player_options()
season = data.player_season()
config = data.config()

# Filters live on the page rather than in the sidebar: navigation moved to the
# top header, so the sidebar starts collapsed and anything hidden in it would
# effectively not exist.
requested = routing.int_param(routing.PLAYER)
default_index = (
    int(players.index[players["player_id"] == requested][0])
    if requested is not None and requested in set(players["player_id"])
    else None
)

with st.container(border=True):
    pick, minutes_column, count_column, toggle_column = st.columns([3, 2, 1.4, 1.6])
    choice = pick.selectbox("Reference player", players["label"], index=default_index,
                            placeholder="Search for a player…")
    min_minutes = minutes_column.slider("Minimum minutes played", 600, 3400, 900,
                                        step=100)
    top_n = count_column.slider("Results", 5, 25, 10, step=5)
    exclude_team = toggle_column.checkbox("Exclude team-mates", value=False)

if choice is None:
    st.info("Select a reference player to begin.", icon=":material/person_search:")
    st.stop()

reference = players[players["label"] == choice].iloc[0]
player_id = int(reference["player_id"])
role = reference["role"]
matrix = data.role_matrix(role)
ref_row = season[season["player_id"] == player_id].iloc[0]

if routing.param(routing.PLAYER) != str(player_id):
    st.query_params[routing.PLAYER] = str(player_id)

# Long text belongs in the heading, not in a metric tile — a metric renders its
# value at heading size and truncates rather than wrapping.
st.header(data.display_name(ref_row))
st.caption(f"{reference['team']} · {ref_row['primary_position']}")

col1, col2, col3 = st.columns(3)
col1.metric("Role group", role, border=True)
col2.metric("Minutes", f"{ref_row['minutes']:.0f}", border=True)
col3.metric("Matches", int(ref_row["matches_played"]), border=True)

results = find_similar(
    matrix, season, player_id,
    top_n=top_n, min_minutes=min_minutes,
    min_coverage=config["similarity"]["min_feature_coverage"],
    exclude_same_team=exclude_team,
)

st.caption(
    f"Compared against {len(matrix.z) - 1} other **{role}** players "
    f"on {len(matrix.features)} role-specific features."
)

if results.empty:
    st.warning("No candidates match those filters. Try lowering the minutes threshold.")
    st.stop()

table = results.merge(players[["player_id", "display_name", "team"]],
                      on="player_id", how="left")
table["similarity"] = table["similarity"].round(3)
table["most alike on"] = table["most_similar_on"].apply(lambda fs: ", ".join(fs[:3]))
table["differs most on"] = table["biggest_differences"].apply(lambda fs: ", ".join(fs))
table["⚠"] = table["low_minutes"].map({True: "low minutes", False: ""})
# Coverage is stored as a 0-1 share; Streamlit's "%%" only appends a percent
# sign, it does not scale, so convert here.
table["coverage"] = table["coverage"] * 100

st.dataframe(
    table[["display_name", "team", "minutes", "similarity", "coverage",
           "most alike on", "differs most on", "⚠"]],
    hide_index=True,
    width="stretch",
    column_config={
        "display_name": st.column_config.TextColumn("Player"),
        "team": st.column_config.TextColumn("Club"),
        "minutes": st.column_config.NumberColumn("Minutes", format="%.0f"),
        "similarity": st.column_config.ProgressColumn(
            "Similarity", min_value=0.0, max_value=1.0, format="%.3f"),
        "coverage": st.column_config.NumberColumn(
            "Data coverage", format="%.0f%%",
            help="Share of this role's features actually available for the player"),
    },
)

st.caption(
    "**Similarity** is weighted cosine on features standardized within the role group: "
    "it measures whether two players deviate from their role's average in the same "
    "directions. It is descriptive, not a ranking of quality."
)

st.divider()
st.subheader("Open a result")

for _, candidate in table.iterrows():
    columns = st.columns([3, 2, 1, 1])
    columns[0].markdown(f"**{candidate['display_name']}** · {candidate['team']}")
    columns[1].markdown(f"similarity **{candidate['similarity']:.3f}**")
    if columns[2].button("Profile", key=f"open_profile_{candidate['player_id']}"):
        routing.go(routing.PLAYER_PROFILE,
                   **{routing.PLAYER: int(candidate["player_id"])})
    if columns[3].button("Compare", key=f"open_compare_{candidate['player_id']}"):
        routing.go(
            routing.PLAYER_COMPARISON,
            **{routing.COMPARE_LEFT: player_id,
               routing.COMPARE_RIGHT: int(candidate["player_id"])},
        )
