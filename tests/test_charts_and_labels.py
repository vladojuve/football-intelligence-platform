"""Metric labels and the percentile ring.

Charts are hard to assert on, so these tests check the two things that would be
visibly wrong on the page: a percentile drawn at the wrong arc length, and a
label that reads as the opposite of the number beside it.
"""

from __future__ import annotations

import pytest

from src.app.charts import (
    band_colour,
    percentile_donut,
    ring_label,
    share_pie,
    wrap_label,
)
from src.app.labels import format_value, pretty, short


@pytest.mark.parametrize(("column", "expected"), [
    ("padj_tackles_p90", "Tackles per 90 (possession-adjusted)"),
    ("npxg_p90", "Non-penalty xG per 90"),
    ("zone14_entries_per_100_passes", "Zone 14 entries per 100 passes"),
    ("ppda", "PPDA (lower = presses harder)"),
])
def test_known_columns_get_their_written_label(column, expected):
    assert pretty(column) == expected


def test_unknown_columns_fall_back_to_the_naming_convention():
    """A new metric added to the marts must still read sensibly with no edit here."""
    assert pretty("brand_new_metric_p90") == "Brand new metric per 90"
    assert pretty("something_share") == "Something share"


def test_short_labels_never_cut_a_word_in_half():
    label = short("padj_interceptions_p90", limit=20)
    assert len(label) <= 20
    assert not label.endswith(" ")
    assert label in pretty("padj_interceptions_p90")


def test_shares_are_shown_as_percentages_and_counts_are_not():
    assert format_value("box_shot_share", 0.62) == "62%"
    assert format_value("pass_completion_pct", 0.874) == "87%"
    assert format_value("npxg_p90", 0.41) == "0.41"
    assert format_value("def_action_height", 52.4) == "52.4"


def test_a_missing_value_is_a_dash_not_a_zero():
    """Rates below their minimum-attempt guard are null on purpose; showing 0
    would read as "worst in the league" rather than "not measured"."""
    assert format_value("npxg_per_shot", None) == "—"
    assert format_value("npxg_per_shot", float("nan")) == "—"


def test_a_long_metric_name_wraps_rather_than_losing_its_ending():
    """"Final-third entries per 100 passes" clipped to "Final-third entries per"
    reads as a different metric, so the title wraps instead of truncating."""
    wrapped = wrap_label(pretty("final_third_entries_per_100_passes"))
    assert wrapped == "Final-third entries per<br>100 passes"
    assert "…" not in wrapped


def test_a_short_metric_name_is_left_on_one_line():
    assert wrap_label("Shots per 90") == "Shots per 90"


def test_wrapping_breaks_at_word_boundaries_only():
    wrapped = wrap_label("Interceptions per 90 (possession-adjusted)")
    for line in wrapped.split("<br>"):
        assert line == line.strip()
        assert not line.endswith("-") or line.endswith("possession-")


def test_a_name_too_long_for_the_line_budget_is_marked_as_shortened():
    wrapped = wrap_label("one two three four five six seven eight nine ten",
                         width=12, max_lines=2)
    assert wrapped.count("<br>") == 1
    assert wrapped.endswith("…")


def test_ring_labels_are_padded_to_a_fixed_number_of_lines():
    """A one-line and a two-line label must occupy the same height, or the rings
    in a row sit at different heights and the grid stops reading as a grid."""
    one_line = ring_label("Shots per 90")
    two_lines = ring_label(pretty("final_third_entries_per_100_passes"))
    assert one_line.count("\n") == two_lines.count("\n") == 1


def test_a_ring_label_keeps_the_whole_metric_name():
    label = ring_label(pretty("padj_interceptions_p90"))
    assert "Interceptions per 90" in label
    assert "(possession-adjusted)" in label


def test_the_ring_fills_in_proportion_to_the_percentile():
    figure = percentile_donut(73.0, "2.10")
    filled, empty = figure.data[0].values
    assert filled == pytest.approx(73.0)
    assert filled + empty == pytest.approx(100.0)


def test_the_ring_reports_the_percentile_as_a_rank():
    figure = percentile_donut(73.0)
    centre = " ".join(a.text for a in figure.layout.annotations)
    assert "73rd" in centre


@pytest.mark.parametrize(("value", "suffix"), [
    (1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"),
    (11, "11th"), (12, "12th"), (13, "13th"), (21, "21st"), (100, "100th"),
])
def test_ordinal_suffixes_including_the_teens(value, suffix):
    figure = percentile_donut(value)
    assert suffix in figure.layout.annotations[0].text


def test_percentiles_outside_the_range_are_clamped_not_drawn_backwards():
    """A percentile is 0-100 by construction, but a clamp is cheaper than a bug
    that renders an inverted ring if a caller ever passes a share by mistake."""
    for value, expected in ((-5.0, 0.0), (140.0, 100.0)):
        filled, empty = percentile_donut(value).data[0].values
        assert filled == pytest.approx(expected)
        assert empty == pytest.approx(100 - expected)


def test_a_higher_percentile_is_a_darker_green():
    assert band_colour(90) != band_colour(30)
    assert band_colour(90) == band_colour(85)


def test_share_pie_keeps_the_slice_order_it_was_given():
    """Plotly re-sorts pie slices by value unless told not to; the legend order
    here is meaningful (wide, halfspace, central reads left to right)."""
    figure = share_pie(["Wide", "Halfspace", "Central"], [0.55, 0.24, 0.21])
    assert list(figure.data[0].labels) == ["Wide", "Halfspace", "Central"]
    assert figure.data[0].sort is False
