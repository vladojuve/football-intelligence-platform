"""Plotly chart builders for the app.

Charts show **percentiles** rather than z-scores wherever a user is reading a
profile: "84th percentile among centre-backs" is immediately meaningful in a way
that "z = +1.02" is not. Raw values are always available alongside.

Colours mirror `.streamlit/config.toml` so charts sit inside the app's green
palette instead of falling back to Plotly's default blues. They are duplicated
rather than read from the theme at runtime because a figure has to be buildable
outside a Streamlit session — the tests do exactly that.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Same list as `chartCategoricalColors` in .streamlit/config.toml. Two greens
# lead, then a slate and an amber: three shades of one hue stop being separable
# once a chart carries more than two series, and that hits colour-blind viewers
# hardest.
SERIES_COLOURS = ["#0B8A3D", "#7ACB97", "#1B4D33", "#4A6D7C", "#C98A2B",
                  "#9BC5A8", "#2E7D52"]

GREEN = "#0B8A3D"
GRID_COLOUR = "rgba(20,38,27,0.14)"
TRACK_COLOUR = "#E7F1EA"          # the unfilled part of a donut
MUTED_TEXT = "#5E7268"

# Percentile bands, darkest at the top. A donut is read at a glance, so the
# shade carries the magnitude as well as the arc length does.
_BANDS = [(80, "#0B6A39"), (60, "#0B8A3D"), (40, "#52AE7C"), (20, "#9BC5A8")]
_LOWEST = "#C7DCCF"

# A ring label may wrap to two lines. Every label is padded to this many lines
# so a grid of rings keeps its circles on one baseline, whatever the names do.
TITLE_LINES = 2


def band_colour(percentile: float) -> str:
    """The green shade for a percentile — darker means higher."""
    for floor, colour in _BANDS:
        if percentile >= floor:
            return colour
    return _LOWEST


def _base_layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(gridcolor=GRID_COLOUR, zerolinecolor=GRID_COLOUR)
    fig.update_yaxes(gridcolor=GRID_COLOUR, zerolinecolor=GRID_COLOUR)
    return fig


def _ordinal(value: float) -> str:
    """98 -> '98th'. Percentiles read as ranks, so they get a rank suffix."""
    number = round(value)
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def wrap_label(label: str, width: int = 24, max_lines: int = 2) -> str:
    """Break a metric name across lines instead of letting Plotly clip it.

    A chart title does not wrap on its own, so "Final-third entries per 100
    passes" was being cut to "Final-third entries per" — which reads as a
    different, wrong metric. Wrapping keeps the whole name; only a name too long
    for `max_lines` is shortened, and then at a word boundary.
    """
    words, lines, current = label.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1] + "…"
    return "<br>".join(lines)


def ring_label(text: str, lines: int = TITLE_LINES) -> str:
    """The markdown caption that goes *above* a ring, not inside it.

    Plotly positions a multi-line title from its last line, so a two-line title
    puts its first line above the top of the figure, where it is clipped. Rather
    than fight that, the label is rendered by Streamlit — which also means it
    picks up the app's font and type scale instead of Plotly's.

    Every label is padded to the same number of lines with a zero-width space,
    so a row of rings has its circles on one baseline whatever the names do.
    """
    parts = wrap_label(text, max_lines=lines).split("<br>")
    parts += ["​"] * (lines - len(parts))
    return "  \n".join(f"**{part}**" for part in parts)


def percentile_donut(
    percentile: float, value_text: str = "", height: int = 210,
) -> go.Figure:
    """One metric as a filled ring: arc length and shade both carry the percentile.

    A ring is used rather than a full pie because the empty centre is where the
    number goes, and a number plus a proportion is what a reader actually wants
    here — a whole pie would have to put the figure in a legend instead.
    """
    filled = max(0.0, min(100.0, float(percentile)))
    colour = band_colour(filled)
    fig = go.Figure(
        go.Pie(
            values=[filled, 100 - filled],
            hole=0.68,
            sort=False,
            direction="clockwise",
            rotation=0,
            marker=dict(colors=[colour, TRACK_COLOUR],
                        line=dict(color="#FFFFFF", width=1)),
            textinfo="none",
            hoverinfo="skip",
        )
    )
    fig.add_annotation(
        text=f"<b>{_ordinal(filled)}</b>", x=0.5, y=0.54, showarrow=False,
        font=dict(size=26, color=colour), xref="paper", yref="paper",
    )
    if value_text:
        fig.add_annotation(
            text=value_text, x=0.5, y=0.34, showarrow=False,
            font=dict(size=14, color=MUTED_TEXT), xref="paper", yref="paper",
        )
    # No Plotly title — the label is drawn above the figure by `ring_label`.
    fig.update_layout(
        height=height,
        margin=dict(l=6, r=6, t=6, b=6),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


def share_pie(labels: list[str], values: list[float], title: str = "",
              height: int = 300) -> go.Figure:
    """A genuine part-of-whole pie — only for values that really do sum to one."""
    fig = go.Figure(
        go.Pie(
            labels=labels, values=values, hole=0.45, sort=False,
            marker=dict(colors=SERIES_COLOURS[: len(labels)],
                        line=dict(color="#FFFFFF", width=2)),
            texttemplate="%{label}<br>%{percent}",
            hovertemplate="%{label}: %{value:.1f} (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        title=title, height=height, showlegend=False,
        margin=dict(l=10, r=10, t=44, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def radar(labels: list[str], series: dict[str, list[float]], title: str = "") -> go.Figure:
    """Percentile radar comparing one or two profiles (values 0-100)."""
    fig = go.Figure()
    for i, (name, values) in enumerate(series.items()):
        colour = SERIES_COLOURS[i % len(SERIES_COLOURS)]
        fig.add_trace(
            go.Scatterpolar(
                r=values + values[:1],          # close the loop
                theta=labels + labels[:1],
                name=name,
                fill="toself",
                line=dict(color=colour, width=2),
                opacity=0.55,
                hovertemplate="%{theta}<br>%{r:.0f}th percentile<extra>" + name + "</extra>",
            )
        )
    fig.update_layout(
        title=title,
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], gridcolor=GRID_COLOUR),
            angularaxis=dict(gridcolor=GRID_COLOUR),
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    return _base_layout(fig, height=560)


def percentile_bars(
    frame: pd.DataFrame, label_column: str, value_column: str,
    colour_column: str | None = None, title: str = "",
) -> go.Figure:
    """Horizontal percentile bars (0-100), highest at the top."""
    ordered = frame.sort_values(value_column)
    fig = px.bar(
        ordered, x=value_column, y=label_column, orientation="h",
        color=colour_column, color_discrete_sequence=SERIES_COLOURS,
        range_x=[0, 100], title=title,
    )
    if colour_column is None:
        fig.update_traces(marker_color=[band_colour(v) for v in ordered[value_column]])
    fig.add_vline(x=50, line_dash="dot", line_color=GRID_COLOUR)
    fig.update_traces(hovertemplate="%{y}: %{x:.0f}th percentile<extra></extra>")
    fig.update_layout(yaxis_title=None, xaxis_title="Percentile within group")
    return _base_layout(fig, height=max(340, 26 * len(ordered)))


def grouped_bars(
    frame: pd.DataFrame, label_column: str, value_columns: list[str], title: str = ""
) -> go.Figure:
    """Side-by-side comparison bars for two players/teams."""
    melted = frame.melt(id_vars=label_column, value_vars=value_columns,
                        var_name="who", value_name="percentile")
    fig = px.bar(
        melted, x="percentile", y=label_column, color="who", orientation="h",
        barmode="group", color_discrete_sequence=SERIES_COLOURS,
        range_x=[0, 100], title=title,
    )
    fig.add_vline(x=50, line_dash="dot", line_color=GRID_COLOUR)
    fig.update_traces(hovertemplate="%{y}<br>%{x:.0f}th percentile<extra>%{fullData.name}</extra>")
    fig.update_layout(yaxis_title=None, xaxis_title="Percentile within role")
    return _base_layout(fig, height=max(380, 34 * frame[label_column].nunique()))


def head_to_head_bars(
    frame: pd.DataFrame, label_column: str, left_column: str, right_column: str,
    left_name: str, right_name: str, title: str = "",
) -> go.Figure:
    """Two teams on the same features, mirrored around a shared axis.

    A single match is read as one side against the other, so the two bars grow
    outward from the middle rather than stacking left-aligned: which way the
    pair leans is then visible without comparing bar lengths in your head.
    """
    ordered = frame.iloc[::-1]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=ordered[label_column], x=-ordered[left_column], orientation="h",
        name=left_name, marker_color=SERIES_COLOURS[0],
        customdata=ordered[left_column],
        hovertemplate="%{y}<br>%{customdata:.2f}<extra>" + left_name + "</extra>",
    ))
    fig.add_trace(go.Bar(
        y=ordered[label_column], x=ordered[right_column], orientation="h",
        name=right_name, marker_color=SERIES_COLOURS[3],
        hovertemplate="%{y}<br>%{x:.2f}<extra>" + right_name + "</extra>",
    ))
    fig.update_layout(barmode="relative", title=title, yaxis_title=None,
                      xaxis_title=f"← {left_name}    ·    {right_name} →")
    fig.update_xaxes(showticklabels=False)
    fig.add_vline(x=0, line_color=GRID_COLOUR)
    return _base_layout(fig, height=max(380, 34 * len(ordered)))


def style_scatter(
    frame: pd.DataFrame, x: str, y: str, label_column: str, colour_column: str,
    highlight: str | None = None, x_title: str = "", y_title: str = "",
) -> go.Figure:
    """PCA style map: one point per team, coloured by cluster, labelled."""
    fig = px.scatter(
        frame, x=x, y=y, color=colour_column, text=label_column,
        color_discrete_sequence=SERIES_COLOURS,
        hover_data={x: ":.2f", y: ":.2f", colour_column: True, label_column: False},
    )
    fig.update_traces(marker=dict(size=14, line=dict(width=1, color="rgba(20,38,27,0.35)")),
                      textposition="top center", textfont=dict(size=13))
    if highlight is not None and highlight in frame[label_column].values:
        point = frame[frame[label_column] == highlight].iloc[0]
        fig.add_trace(
            go.Scatter(
                x=[point[x]], y=[point[y]], mode="markers", name=highlight,
                marker=dict(size=26, color="rgba(0,0,0,0)",
                            line=dict(width=3, color="#C98A2B")),
                hoverinfo="skip", showlegend=False,
            )
        )
    fig.add_hline(y=0, line_dash="dot", line_color=GRID_COLOUR)
    fig.add_vline(x=0, line_dash="dot", line_color=GRID_COLOUR)
    fig.update_layout(xaxis_title=x_title or x, yaxis_title=y_title or y)
    return _base_layout(fig, height=640)


def variability_bars(frame: pd.DataFrame, label_column: str, value_column: str,
                     title: str = "") -> go.Figure:
    """Match-to-match standard deviation, as a rigid-vs-adaptable read."""
    ordered = frame.sort_values(value_column)
    fig = px.bar(ordered, x=value_column, y=label_column, orientation="h",
                 color_discrete_sequence=[SERIES_COLOURS[0]], title=title)
    fig.update_traces(hovertemplate="%{y}: sd %{x:.3f}<extra></extra>")
    fig.update_layout(yaxis_title=None, xaxis_title="Match-to-match standard deviation")
    return _base_layout(fig, height=max(340, 26 * len(ordered)))
