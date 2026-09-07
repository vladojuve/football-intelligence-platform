"""Repair the one systematic text defect in the source lineup files.

StatsBomb's open-data `player_name` field carries **doubled apostrophes** —
`"N''Golo Kanté"`, `"John O''Shea"`, `"Yann Gérard M''Vila"` — because the
export was written by a process that SQL-escaped the string and never unescaped
it. The `player_nickname` field beside it is unaffected, which is what confirms
it is an export artefact rather than how the names are actually stored: no data
source spells the same player two ways in adjacent fields.

Ten players in Premier League 2015/16 are affected. The repair belongs here, in
staging, not in the app: raw stays byte-identical to what StatsBomb published,
and every downstream table gets the corrected name once rather than each page
having to remember to fix it.
"""

from __future__ import annotations

# Only the doubled ASCII apostrophe is collapsed. A doubled typographic
# apostrophe (’’) would be a real pair of quotation marks, and a single
# apostrophe is of course legitimate — O'Shea keeps his.
_ESCAPED_APOSTROPHE = "''"


def clean_name(name: object) -> object:
    """Undo the SQL-escaping in a player name, leaving anything else alone."""
    if not isinstance(name, str):
        return name
    return name.replace(_ESCAPED_APOSTROPHE, "'")
