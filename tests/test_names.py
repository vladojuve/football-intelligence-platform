"""The doubled-apostrophe repair applied to StatsBomb player names.

`player_name` in the open-data lineup files is SQL-escaped and never unescaped:
`"N''Golo Kanté"`, `"John O''Shea"`. Ten Premier League 2015/16 players are
affected. The `player_nickname` field beside it is clean, which is what shows
this is an export artefact rather than the real spelling.
"""

from __future__ import annotations

import pytest

from src.transformations.names import clean_name


@pytest.mark.parametrize(("stored", "expected"), [
    ("N''Golo Kanté", "N'Golo Kanté"),
    ("John O''Shea", "John O'Shea"),
    ("Yann Gérard M''Vila", "Yann Gérard M'Vila"),
    ("Pape N''Diaye Souaré", "Pape N'Diaye Souaré"),
])
def test_doubled_apostrophes_collapse(stored, expected):
    assert clean_name(stored) == expected


def test_a_single_apostrophe_is_left_alone():
    """O'Shea keeps his apostrophe — only the doubled form is an artefact."""
    assert clean_name("John O'Shea") == "John O'Shea"


def test_names_without_apostrophes_are_untouched():
    assert clean_name("Jamie Vardy") == "Jamie Vardy"
    assert clean_name("Héctor Bellerín") == "Héctor Bellerín"


def test_a_missing_nickname_passes_through():
    """Most players have no nickname, and pandas hands that over as None."""
    assert clean_name(None) is None
