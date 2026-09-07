"""Player comparison: side-by-side percentiles, radar and the weighted-distance breakdown."""

import pandas as pd
import streamlit as st

from src.app import charts, data, routing
from src.app.labels import pretty, short
from src.similarity.engine import explain_pair, weighted_cosine_matrix

st.title(":material/compare_arrows: Compare two players")
st.caption(
    "Both players must be in the same role group — comparing a centre-back to a "
    "winger on the same scale would be meaningless."
)

players = data.player_options()
season = data.player_season()


def _preselect(parameter: str, in_role: pd.DataFrame) -> int | None:
    """Turn a `?a=<player_id>` link into a position in the picker."""
    player_id = routing.int_param(parameter)
    if player_id is None:
        return None
    matches = in_role.index[in_role["player_id"] == player_id]
    return int(matches[0]) if len(matches) else None


# A link from the search or profile page carries both ids, so the role group has
# to follow from the players rather than the other way round.
roles = sorted(players["role"].unique())
linked = routing.int_param(routing.COMPARE_LEFT)
if linked is not None and linked in set(players["player_id"]):
    linked_role = players.loc[players["player_id"] == linked, "role"].iloc[0]
    role_index = roles.index(linked_role)
else:
    role_index = roles.index("AM_W") if "AM_W" in roles else 0

with st.container(border=True):
    role_column, left_column, right_column, radar_column = st.columns([1.2, 3, 3, 1.6])
    role = role_column.selectbox("Role group", roles, index=role_index)
    in_role = players[players["role"] == role].reset_index(drop=True)
    left_choice = left_column.selectbox(
        "Player A", in_role["label"], index=_preselect(routing.COMPARE_LEFT, in_role),
        placeholder="Select a player…")
    right_choice = right_column.selectbox(
        "Player B", in_role["label"], index=_preselect(routing.COMPARE_RIGHT, in_role),
        placeholder="Select a player…")
    n_features = radar_column.slider("Features on the radar", 6, 14, 10)

if left_choice is None or right_choice is None:
    st.info("Select two players of the same role group.", icon=":material/group:")
    st.stop()
if left_choice == right_choice:
    st.warning("Pick two different players.")
    st.stop()

left_id = int(in_role[in_role["label"] == left_choice].iloc[0]["player_id"])
right_id = int(in_role[in_role["label"] == right_choice].iloc[0]["player_id"])
matrix = data.role_matrix(role)
indexed = season.set_index("player_id")
left_row, right_row = indexed.loc[left_id], indexed.loc[right_id]
left_name, right_name = data.display_name(left_row), data.display_name(right_row)

st.query_params.update({routing.COMPARE_LEFT: str(left_id),
                        routing.COMPARE_RIGHT: str(right_id)})

similarity = weighted_cosine_matrix(matrix.z, matrix.weights).loc[left_id, right_id]

col1, col2, col3 = st.columns(3)
col1.metric(left_name, f"{left_row['minutes']:.0f} min",
            left_row["primary_position"], delta_arrow="off", delta_color="off", border=True)
col2.metric(right_name, f"{right_row['minutes']:.0f} min",
            right_row["primary_position"], delta_arrow="off", delta_color="off", border=True)
col3.metric("Similarity", f"{similarity:.3f}", border=True)

breakdown = explain_pair(matrix, left_id, right_id)

# --- Radar of the most heavily weighted features --------------------------
weight_order = pd.Series(matrix.weights, index=matrix.features).sort_values(ascending=False)
radar_features = weight_order.head(n_features).index.tolist()


def _percentiles(player_id: int, features: list[str]) -> list[float]:
    row = indexed.loc[player_id]
    return [float((row.get(f"pct_{f}") or 0.0) * 100) for f in features]


st.subheader("Profile")
st.plotly_chart(
    charts.radar(
        labels=[short(f, limit=20) for f in radar_features],
        series={left_name: _percentiles(left_id, radar_features),
                right_name: _percentiles(right_id, radar_features)},
    ),
    width="stretch",
)
st.caption(f"Percentiles within the **{role}** group. Showing the {n_features} features "
           "weighted most heavily for this role.")

# --- Percentile comparison across every role feature ----------------------
st.subheader("All role features")
comparison = pd.DataFrame({
    "feature": [pretty(f) for f in matrix.features],
    left_name: _percentiles(left_id, matrix.features),
    right_name: _percentiles(right_id, matrix.features),
})
st.plotly_chart(
    charts.grouped_bars(comparison, "feature", [left_name, right_name]),
    width="stretch",
)

# --- Where they match and where they differ -------------------------------
st.divider()
left_table, right_table = st.columns(2)
with left_table:
    st.subheader("Most alike")
    closest = breakdown.head(5).copy()
    closest["feature"] = closest["feature"].map(pretty)
    st.dataframe(
        closest[["feature", "reference_value", "candidate_value"]].round(3),
        hide_index=True, width="stretch",
        column_config={"feature": "Feature", "reference_value": left_name,
                       "candidate_value": right_name},
    )
with right_table:
    st.subheader("Biggest differences")
    furthest = breakdown.tail(5).iloc[::-1].copy()
    furthest["feature"] = furthest["feature"].map(pretty)
    st.dataframe(
        furthest[["feature", "reference_value", "candidate_value"]].round(3),
        hide_index=True, width="stretch",
        column_config={"feature": "Feature", "reference_value": left_name,
                       "candidate_value": right_name},
    )

with st.expander("Raw values and weighted distance per feature"):
    detail = breakdown.copy()
    detail["feature"] = detail["feature"].map(pretty)
    detail = detail.rename(columns={
        "reference_value": left_name, "candidate_value": right_name,
        "gap": "weighted gap"})
    st.dataframe(
        detail[["feature", left_name, right_name, "weighted gap"]].round(3),
        hide_index=True, width="stretch",
    )
    st.caption(
        "**Weighted gap** is the absolute difference in standardized values, scaled by "
        "the feature's role weight — small means the players match on that dimension."
    )

open_left, open_right, _ = st.columns([1, 1, 3])
if open_left.button(f"{left_name}'s profile", icon=":material/person:"):
    routing.go(routing.PLAYER_PROFILE, **{routing.PLAYER: left_id})
if open_right.button(f"{right_name}'s profile", icon=":material/person:"):
    routing.go(routing.PLAYER_PROFILE, **{routing.PLAYER: right_id})
