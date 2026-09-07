"""League table, club record and the "special players" rule.

The league table is worth testing carefully because it is the one number on the
club page a reader will already know: if the app says Leicester finished second,
nothing else on the page will be believed.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.app.insights import (
    club_record,
    league_table,
    special_players,
    summarise_special_players,
)


@pytest.fixture
def matches() -> pd.DataFrame:
    """A tiny three-club round robin, played home and away.

    Alpha beat Beta twice and drew with Gamma twice -> 8 points.
    Beta beat Gamma twice and lost twice -> 6. Gamma drew twice and lost twice -> 2.
    """
    rows = [
        (1, "Alpha", "Beta", 2, 0), (2, "Beta", "Alpha", 0, 1),
        (3, "Alpha", "Gamma", 1, 1), (4, "Gamma", "Alpha", 0, 0),
        (5, "Beta", "Gamma", 3, 0), (6, "Gamma", "Beta", 1, 4),
    ]
    return pd.DataFrame([
        {"match_id": m, "match_date": pd.Timestamp("2015-08-01") + pd.Timedelta(days=m),
         "match_week": m, "home_team": h, "away_team": a,
         "home_score": hs, "away_score": as_, "stadium": f"{h} Park",
         "referee": "A Referee"}
        for m, h, a, hs, as_ in rows
    ])


def test_points_and_order(matches):
    table = league_table(matches)
    assert list(table["team"]) == ["Alpha", "Beta", "Gamma"]
    assert list(table["points"]) == [8, 6, 2]
    assert list(table["position"]) == [1, 2, 3]


def test_goals_balance_across_the_table(matches):
    """Every goal is someone's for and someone else's against."""
    table = league_table(matches)
    assert table["goals_for"].sum() == table["goals_against"].sum()
    assert table["goal_difference"].sum() == 0


def test_every_match_is_counted_once_per_side(matches):
    table = league_table(matches)
    assert table["played"].sum() == 2 * len(matches)
    assert (table["won"] + table["drawn"] + table["lost"] == table["played"]).all()


def test_goal_difference_breaks_a_points_tie():
    """Two clubs on equal points are separated by goal difference, not by name."""
    rows = [
        (1, "Zeta", "Omega", 5, 0),     # Zeta +5
        (2, "Omega", "Zeta", 1, 0),     # Omega +1
    ]
    frame = pd.DataFrame([
        {"match_id": m, "match_date": pd.Timestamp("2015-08-01"), "match_week": m,
         "home_team": h, "away_team": a, "home_score": hs, "away_score": as_,
         "stadium": "Ground", "referee": "A Referee"}
        for m, h, a, hs, as_ in rows
    ])
    table = league_table(frame)
    assert list(table["points"]) == [3, 3]
    assert table.iloc[0]["team"] == "Zeta"


def test_club_record_splits_home_from_away(matches):
    record = club_record(matches, "Alpha")
    assert record["position"] == 1
    assert record["played"] == 4
    assert record["home"]["played"] == 2
    assert record["away"]["played"] == 2
    assert record["home"]["points"] + record["away"]["points"] == record["points"]


def test_club_record_names_the_best_and_worst_results(matches):
    record = club_record(matches, "Gamma")
    assert record["biggest_defeat"] == "0–3 at Beta"
    assert record["clean_sheets"] == 1          # the 0-0 with Alpha
    assert record["failed_to_score"] == 2


def test_club_record_of_an_unknown_club_is_empty(matches):
    assert club_record(matches, "Nobody FC") == {}


# --- special players -------------------------------------------------------

@pytest.fixture
def season() -> pd.DataFrame:
    return pd.DataFrame([
        {"player_id": 1, "team_id": 10, "npxg_p90": 0.60, "turnovers_p90": 9.0},
        {"player_id": 2, "team_id": 10, "npxg_p90": 0.50, "turnovers_p90": 8.0},
        {"player_id": 3, "team_id": 20, "npxg_p90": 0.40, "turnovers_p90": 7.0},
        {"player_id": 4, "team_id": 20, "npxg_p90": 0.10, "turnovers_p90": 1.0},
        {"player_id": 5, "team_id": 30, "npxg_p90": None, "turnovers_p90": 2.0},
    ])


def test_only_the_top_three_qualify(season):
    entries = special_players(season, ["npxg_p90"], top_n=3)
    assert sorted(entries["player_id"]) == [1, 2, 3]
    assert entries.set_index("player_id").loc[1, "rank"] == 1


def test_a_high_turnover_count_is_not_a_distinction(season):
    """Being third in the league for losing the ball does not belong in a table
    headed "special players", so that metric is excluded by name."""
    entries = special_players(season, ["turnovers_p90"], top_n=3)
    assert entries.empty


def test_players_missing_the_metric_are_skipped_not_ranked_last(season):
    """A null is "not measured", not "worst" — it must not be ranked at all."""
    entries = special_players(season, ["npxg_p90"], top_n=5)
    assert 5 not in set(entries["player_id"])


def test_joint_leaders_share_the_rank():
    frame = pd.DataFrame([
        {"player_id": 1, "team_id": 1, "npxg_p90": 0.5},
        {"player_id": 2, "team_id": 1, "npxg_p90": 0.5},
        {"player_id": 3, "team_id": 1, "npxg_p90": 0.1},
    ])
    entries = special_players(frame, ["npxg_p90"], top_n=1)
    assert set(entries["player_id"]) == {1, 2}
    assert set(entries["rank"]) == {1}


def test_summary_counts_finishes_per_player(season):
    entries = special_players(season, ["npxg_p90", "key_passes_p90"], top_n=3)
    summary = summarise_special_players(entries)
    assert summary.iloc[0]["top3_count"] >= 1
    assert summary["top3_count"].sum() == len(entries)


def test_summary_of_nothing_is_an_empty_frame_not_a_crash():
    empty = special_players(pd.DataFrame({"player_id": [], "team_id": []}), ["npxg_p90"])
    assert summarise_special_players(empty).empty
