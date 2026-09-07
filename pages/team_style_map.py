"""Team style map: the PCA style space, coloured by cluster."""

import streamlit as st

from src.app import charts, data, routing
from src.app.labels import pretty

st.title(":material/scatter_plot: Style map")

space = data.style_space()
style = data.team_style()

pc1_share, pc2_share = space.explained_variance[0], space.explained_variance[1]
clusters = sorted(style["cluster_label"].unique())

with st.container(border=True):
    cluster_column, highlight_column = st.columns([3, 2])
    selected = cluster_column.multiselect("Style clusters", clusters, default=clusters)
    highlight = highlight_column.selectbox("Highlight a club", sorted(style["team"]),
                                           index=None, placeholder="Optional…")

frame = style[style["cluster_label"].isin(selected)]
if frame.empty:
    st.warning("Select at least one cluster.")
    st.stop()

st.plotly_chart(
    charts.style_scatter(
        frame, x="pc1", y="pc2", label_column="team", colour_column="cluster_label",
        highlight=highlight,
        x_title=f"PC1 — control vs directness ({pc1_share:.0%} of variance)",
        y_title=f"PC2 — advanced territory vs deep play ({pc2_share:.0%} of variance)",
    ),
    width="stretch",
)

st.caption(
    "Clubs close together played similarly. The axes are the two strongest style "
    "dimensions found in the data, not chosen in advance."
)

if highlight is not None and st.button(f"Open {highlight}'s profile",
                                       icon=":material/shield:"):
    routing.go(routing.TEAM_PROFILE, **{routing.TEAM: highlight})

st.divider()
st.subheader("What the axes mean")

axis_left, axis_right = st.columns(2)
for column, pc, share in ((axis_left, "PC1", pc1_share), (axis_right, "PC2", pc2_share)):
    loadings = space.loadings[pc].sort_values(ascending=False)
    with column, st.container(border=True):
        st.markdown(f"**{pc}** — {share:.0%} of variance")
        st.markdown("_High end:_ " + ", ".join(
            pretty(f) for f in loadings.head(4).index))
        st.markdown("_Low end:_ " + ", ".join(
            pretty(f) for f in loadings.tail(4).index))

st.divider()
st.subheader("Clusters")
st.caption("Labels were written **after** inspecting the centroids — never before.")

for label in clusters:
    members = style[style["cluster_label"] == label]
    with st.expander(f"{label}  ({len(members)} clubs)"):
        st.write(", ".join(sorted(members["team"])))
        st.dataframe(
            members[["team", "centroid_distance", "nearest_teams"]]
            .sort_values("centroid_distance", ascending=False).round(2),
            hide_index=True, width="stretch",
            column_config={
                "team": "Club",
                "centroid_distance": st.column_config.NumberColumn(
                    "Distance to centroid",
                    help="Higher means this label describes the club less well"),
                "nearest_teams": "Nearest clubs (any cluster)",
            },
        )

st.info(
    "A cluster label is a summary, not a boundary. Nearest-team similarity is computed "
    "in the full standardized feature space, so a side's closest neighbours can sit in "
    "another cluster — Liverpool's, for instance, include Everton.",
    icon=":material/info:",
)
