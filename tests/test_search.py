"""Search must work for names as they are typed, not as they are spelled.

Every case here comes from a name that actually appears in the 2015/16 squad
lists, because the failure mode this module exists to prevent is real: a user
types "Ngolo Kante", the database holds "N'Golo Kanté", and a substring match
returns nothing.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.app.search import (
    normalize,
    search_matches,
    search_players,
    search_teams,
)


@pytest.mark.parametrize(
    ("stored", "typed"),
    [
        ("N'Golo Kanté", "Ngolo Kante"),
        ("N'Golo Kanté", "ngolo kante"),
        ("Mesut Özil", "Mesut Ozil"),
        ("Héctor Bellerín", "Hector Bellerin"),
        ("Nicolás Otamendi", "Nicolas Otamendi"),
        ("Cheikhou Kouyaté", "Cheikhou Kouyate"),
        ("Bacary Sagna", "  BACARY   SAGNA  "),
        ("Ruben Loftus-Cheek", "Ruben Loftus Cheek"),
        ("Shane Duffy", "shane duffy"),
    ],
)
def test_typed_form_normalizes_to_the_stored_form(stored, typed):
    assert normalize(stored) == normalize(typed)


def test_apostrophes_close_up_rather_than_splitting():
    """The distinction the rest of the module depends on.

    An apostrophe is deleted, so "N'Golo" becomes one token and matches "Ngolo".
    A hyphen becomes a space, because "Loftus-Cheek" is typed with one.
    """
    assert normalize("N'Golo") == "ngolo"
    assert normalize("Loftus-Cheek") == "loftus cheek"


def test_normalize_tolerates_missing_values():
    """Nicknames are null for most players, and pandas gives that back as NaN."""
    assert normalize(None) == ""
    assert normalize(float("nan")) == ""


@pytest.fixture
def players() -> pd.DataFrame:
    return pd.DataFrame([
        {"player_id": 1, "player_name": "N'Golo Kanté", "nickname": None,
         "primary_position": "Center Defensive Midfield", "minutes": 3000.0,
         "team": "Leicester City"},
        {"player_id": 2, "player_name": "Mesut Özil", "nickname": None,
         "primary_position": "Center Attacking Midfield", "minutes": 2900.0,
         "team": "Arsenal"},
        {"player_id": 3, "player_name": "Jamie Vardy", "nickname": None,
         "primary_position": "Center Forward", "minutes": 3100.0,
         "team": "Leicester City"},
        {"player_id": 4, "player_name": "Sergio Leonel Agüero del Castillo",
         "nickname": "Sergio Agüero", "primary_position": "Center Forward",
         "minutes": 2100.0, "team": "Manchester City"},
    ])


def test_accentless_query_finds_the_accented_player(players):
    hits = search_players(players, "Ngolo Kante")
    assert hits[0].title == "N'Golo Kanté"
    assert hits[0].score == pytest.approx(1.0)


def test_surname_alone_is_enough(players):
    assert search_players(players, "vardy")[0].title == "Jamie Vardy"
    assert search_players(players, "ozil")[0].title == "Mesut Özil"


def test_the_nickname_is_searched_as_well_as_the_registered_name(players):
    """StatsBomb registers full legal names; nobody searches for those."""
    hits = search_players(players, "Aguero")
    assert hits[0].title == "Sergio Agüero"


def test_a_typo_still_returns_the_intended_player(players):
    hits = search_players(players, "kanty")
    assert hits and hits[0].title == "N'Golo Kanté"


def test_nonsense_returns_nothing_rather_than_everything(players):
    assert search_players(players, "zzzzzz") == []


def test_an_empty_query_returns_nothing(players):
    assert search_players(players, "   ") == []


def test_exact_name_outranks_a_partial_one(players):
    """Ranking, not just filtering: a full match must come first."""
    frame = pd.concat([players, pd.DataFrame([{
        "player_id": 5, "player_name": "Kane Vardy-Smith", "nickname": None,
        "primary_position": "Center Forward", "minutes": 700.0, "team": "Watford"}])],
        ignore_index=True)
    hits = search_players(frame, "Jamie Vardy")
    assert hits[0].title == "Jamie Vardy"


@pytest.fixture
def teams() -> pd.DataFrame:
    return pd.DataFrame([
        {"team": "Tottenham Hotspur", "cluster_label": "Possession"},
        {"team": "Leicester City", "cluster_label": "Direct and wide"},
        {"team": "Manchester United", "cluster_label": "Possession"},
    ])


@pytest.mark.parametrize(("typed", "expected"), [
    ("spurs", "Tottenham Hotspur"),
    ("tottenham", "Tottenham Hotspur"),
    ("foxes", "Leicester City"),
    ("man utd", "Manchester United"),
    ("leicester", "Leicester City"),
])
def test_informal_club_names_resolve(typed, expected):
    frame = pd.DataFrame([
        {"team": "Tottenham Hotspur"}, {"team": "Leicester City"},
        {"team": "Manchester United"},
    ])
    assert search_teams(frame, typed)[0].title == expected


def test_club_search_ignores_a_miss(teams):
    assert search_teams(teams, "barcelona") == []


@pytest.fixture
def fixtures() -> pd.DataFrame:
    return pd.DataFrame([
        {"match_id": 1, "match_date": "2016-02-14", "match_week": 26,
         "home_team": "Arsenal", "away_team": "Leicester City",
         "home_score": 2, "away_score": 1},
        {"match_id": 2, "match_date": "2015-09-26", "match_week": 7,
         "home_team": "Leicester City", "away_team": "Arsenal",
         "home_score": 2, "away_score": 5},
        {"match_id": 3, "match_date": "2016-01-13", "match_week": 21,
         "home_team": "Tottenham Hotspur", "away_team": "Leicester City",
         "home_score": 0, "away_score": 1},
    ])


def test_naming_both_clubs_finds_the_fixture_in_either_order(fixtures):
    hits = search_matches(fixtures, "arsenal leicester")
    titles = [h.title for h in hits]
    assert "Arsenal 2–1 Leicester City" in titles
    assert "Leicester City 2–5 Arsenal" in titles
    # The reverse order has to work identically — a fixture has no canonical
    # spoken order.
    assert {h.title for h in search_matches(fixtures, "leicester arsenal")} == set(titles)


def test_a_single_club_still_surfaces_its_fixtures(fixtures):
    hits = search_matches(fixtures, "spurs")
    assert hits and "Tottenham Hotspur" in hits[0].title


def test_match_hits_carry_the_id_the_report_page_needs(fixtures):
    hit = search_matches(fixtures, "arsenal leicester")[0]
    assert hit.kind == "match"
    assert int(hit.key) in set(fixtures["match_id"])
