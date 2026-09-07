"""Readable names for the metric columns.

The database column names are deliberately terse and machine-facing
(`padj_tackles_p90`, `zone14_entries_per_100_passes`). Those are correct in the
data layer and unreadable in a chart title, so the translation lives here — one
place, shared by every page, rather than an ad-hoc `.replace("_", " ")` per page
that would drift.

Anything not listed falls through :func:`pretty`, which expands the suffixes the
naming convention already guarantees.
"""

from __future__ import annotations

# Suffix expansions applied in order. `_p90` before `_pct` matters only for
# readability, not correctness — no column carries both.
_SUFFIXES = [
    ("_per_100_passes", " per 100 passes"),
    ("_p90", " per 90"),
    ("_pct", " %"),
]

# Where the plain expansion would still be cryptic or plain wrong.
OVERRIDES: dict[str, str] = {
    # Player — passing and possession
    "pass_attempts_p90": "Passes attempted per 90",
    "pass_completion_pct": "Pass completion %",
    "forward_pass_share": "Forward pass share",
    "long_pass_share": "Long pass share",
    "turnovers_p90": "Turnovers per 90",
    "prog_passes_p90": "Progressive passes per 90",
    "prog_carries_p90": "Progressive carries per 90",
    "final_third_entries_p90": "Final-third entries per 90",
    "box_entries_p90": "Box entries per 90",
    # Player — creation and shooting
    "key_passes_p90": "Key passes per 90",
    "xg_assisted_p90": "xG assisted per 90",
    "crosses_box_p90": "Crosses into the box per 90",
    "through_balls_p90": "Through balls per 90",
    "shots_p90": "Shots per 90",
    "npxg_p90": "Non-penalty xG per 90",
    "box_shot_share": "Share of shots from the box",
    "npxg_per_shot": "Non-penalty xG per shot",
    "np_goals_minus_npxg": "Non-penalty goals minus xG",
    # Player — defending
    "padj_pressures_p90": "Pressures per 90 (possession-adjusted)",
    "padj_tackles_p90": "Tackles per 90 (possession-adjusted)",
    "padj_interceptions_p90": "Interceptions per 90 (possession-adjusted)",
    "blocks_p90": "Blocks per 90",
    "recoveries_p90": "Recoveries per 90",
    "def_action_height": "Average height of defensive actions",
    # Player — duels, touches and territory
    "dribble_success_pct": "Dribble success %",
    "aerial_involvement_p90": "Aerial duels per 90",
    "aerial_win_pct": "Aerial win %",
    "touches_att_third_share": "Share of touches in the final third",
    "receptions_final_third_p90": "Receptions in the final third per 90",
    "pressured_actions_share": "Share of actions under pressure",
    "zone14_receptions_p90": "Zone 14 receptions per 90",
    "zone14_entries_p90": "Zone 14 entries per 90",
    "halfspace_touch_share": "Halfspace touch share",
    "wide_touch_share": "Wide touch share",
    # Team style
    "possession_share": "Possession share",
    "pass_completion": "Pass completion",
    "passes_per_possession": "Passes per possession",
    "backward_pass_share": "Backward pass share",
    "forward_dist_per_pass": "Forward metres per pass",
    "prog_actions_per_100_passes": "Progressive actions per 100 passes",
    "final_third_entries_per_100_passes": "Final-third entries per 100 passes",
    "field_tilt": "Field tilt",
    "att_third_touch_share": "Attacking-third touch share",
    "mean_action_x": "Average action height",
    "zone14_entries_per_100_passes": "Zone 14 entries per 100 passes",
    "cross_share": "Cross share",
    "switch_share": "Switch share",
    "ppda": "PPDA (lower = presses harder)",
    "high_regain_share": "High regain share",
    "counter_shot_share": "Counter-attack shot share",
    "shots_per_100_passes": "Shots per 100 passes",
    "mean_shot_distance": "Average shot distance",
    "set_piece_shot_share": "Set-piece shot share",
    "turnovers_per_100_passes": "Turnovers per 100 passes",
    "pressured_pass_completion": "Pass completion under pressure",
    "own_half_loss_share": "Share of losses in own half",
}

# Metrics where a high value is a *description*, not a distinction — being third
# in the league for turnovers is not a credential.
NOT_A_DISTINCTION = {"turnovers_p90", "pressured_actions_share"}

# Metrics expressed as a 0-1 share or rate, so the app knows to show a percentage.
SHARE_LIKE_SUFFIXES = ("_share", "_pct")


def pretty(column: str) -> str:
    """A human-readable label for a metric column."""
    if column in OVERRIDES:
        return OVERRIDES[column]
    label = column
    for suffix, replacement in _SUFFIXES:
        if label.endswith(suffix):
            label = label[: -len(suffix)] + replacement
            break
    label = label.replace("_", " ").strip()
    return label[:1].upper() + label[1:]


def short(column: str, limit: int = 26) -> str:
    """A label that fits above a small chart, without a mid-word cut."""
    label = pretty(column)
    if len(label) <= limit:
        return label
    # Drop a trailing parenthetical first — it is the least load-bearing part.
    if "(" in label:
        trimmed = label[: label.index("(")].strip()
        if len(trimmed) <= limit:
            return trimmed
        label = trimmed
    words = label.split()
    out: list[str] = []
    for word in words:
        if len(" ".join([*out, word])) > limit:
            break
        out.append(word)
    return " ".join(out) if out else label[:limit]


def format_value(column: str, value: float | None) -> str:
    """Format a raw metric value the way its own units read."""
    if value is None or (isinstance(value, float) and value != value):
        return "—"
    if column.endswith(SHARE_LIKE_SUFFIXES):
        return f"{value * 100:.0f}%" if value <= 1.0 else f"{value:.0f}%"
    if abs(value) < 1:
        return f"{value:.2f}"
    if abs(value) < 10:
        return f"{value:.2f}"
    return f"{value:.1f}"
