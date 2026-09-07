"""Plain-English search across players, teams and matches.

Football names carry diacritics, apostrophes and hyphens that nobody types into
a search box: `N'Golo Kanté` is entered as "Ngolo Kante", `Mesut Özil` as "Ozil",
`Héctor Bellerín` as "Hector Bellerin". Substring matching on the raw name fails
every one of those, so both the query and the searchable text are pushed through
:func:`normalize` first — Unicode-decomposed, accent-stripped, punctuation
removed — and matching happens on that flattened form.

Results are ranked rather than merely filtered, because "kane" should return
Harry Kane ahead of anyone who merely contains those letters, and a typo should
still find something instead of an empty page.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

import pandas as pd

# Punctuation splits into two kinds, and the distinction matters. Apostrophes
# and full stops are *deleted*, because "N'Golo" is typed "Ngolo" — turning them
# into a space would leave "n golo", which no query ever matches. Hyphens and
# slashes become a *space*, because "Loftus-Cheek" is typed "Loftus Cheek".
_DELETED = re.compile(r"['‘’ʼ.]+")
_PUNCTUATION = re.compile(r"[^a-z0-9 ]+")
_WHITESPACE = re.compile(r"\s+")

# A fuzzy match below this similarity is noise rather than a near miss.
FUZZY_THRESHOLD = 0.78

# Letters that survive NFKD unchanged because they are distinct letters rather
# than an accented base — decomposition cannot help, so they are mapped by hand.
_UNDECOMPOSABLE = {
    "ø": "o", "æ": "ae", "ß": "ss", "đ": "d", "ł": "l", "ð": "d", "þ": "th",
}


def normalize(text: object) -> str:
    """Flatten a name to the form a user would actually type.

    `"N'Golo Kanté"` and `"Ngolo Kante"` both become `"ngolo kante"`, so the two
    compare equal. NFKD splits an accented character into its base letter plus a
    combining mark, and the marks are then dropped.
    """
    if not isinstance(text, str):
        return ""
    lowered = text.lower()
    for special, plain in _UNDECOMPOSABLE.items():
        lowered = lowered.replace(special, plain)
    decomposed = unicodedata.normalize("NFKD", lowered)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    stripped = _DELETED.sub("", stripped)
    return _WHITESPACE.sub(" ", _PUNCTUATION.sub(" ", stripped)).strip()


def _score(haystack: str, needle: str) -> float:
    """How well a normalized query matches one normalized candidate, 0 to 1.

    The tiers are deliberately coarse — an exact hit always outranks a surname
    prefix, which always outranks a mid-word substring — and closeness only
    breaks ties inside a tier.
    """
    if not needle or not haystack:
        return 0.0
    if haystack == needle:
        return 1.0
    tokens = haystack.split()
    if haystack.startswith(needle):
        return 0.95
    # Searching by surname is the common case, so a token prefix ranks almost as
    # highly as a full-name prefix: "kante" against "ngolo kante".
    if any(token.startswith(needle) for token in tokens):
        return 0.90
    query_tokens = needle.split()
    if len(query_tokens) > 1 and all(
        any(token.startswith(part) for token in tokens) for part in query_tokens
    ):
        return 0.88
    if needle in haystack:
        return 0.80
    # Last resort: a typo or a wrong ending ("kanty", "bellerine").
    ratio = max(
        SequenceMatcher(None, haystack, needle).ratio(),
        max((SequenceMatcher(None, token, needle).ratio() for token in tokens),
            default=0.0),
    )
    return ratio * 0.75 if ratio >= FUZZY_THRESHOLD else 0.0


@dataclass(frozen=True)
class Hit:
    """One search result, already resolved to the page that can display it."""

    kind: str            # "player" | "team" | "match"
    key: str             # id or name, passed to the target page as a query param
    title: str
    subtitle: str
    score: float


def _rank(rows: list[tuple[float, Hit]], limit: int) -> list[Hit]:
    rows.sort(key=lambda pair: (-pair[0], pair[1].title))
    return [hit for _, hit in rows[:limit]]


# Common short names, normalized. These live here rather than in the database
# because they are a search affordance, not data about the season.
TEAM_ALIASES: dict[str, list[str]] = {
    "Tottenham Hotspur": ["spurs", "tottenham", "thfc"],
    "Manchester United": ["man utd", "man united", "manutd", "united", "mufc"],
    "Manchester City": ["man city", "mancity", "city", "mcfc"],
    "Newcastle United": ["newcastle", "toon", "nufc"],
    "West Bromwich Albion": ["west brom", "wba", "baggies", "albion"],
    "West Ham United": ["west ham", "hammers", "whufc"],
    "Leicester City": ["leicester", "foxes", "lcfc"],
    "Liverpool": ["lfc", "reds"],
    "Arsenal": ["afc", "gunners"],
    "Chelsea": ["cfc", "blues"],
    "Everton": ["efc", "toffees"],
    "Aston Villa": ["villa", "avfc"],
    "Crystal Palace": ["palace", "cpfc", "eagles"],
    "Stoke City": ["stoke", "potters"],
    "Swansea City": ["swansea", "swans"],
    "Southampton": ["saints", "soton"],
    "Sunderland": ["black cats", "safc"],
    "Watford": ["hornets"],
    "Norwich City": ["norwich", "canaries"],
    "AFC Bournemouth": ["bournemouth", "cherries"],
}


def _team_forms(team: str) -> list[str]:
    return [normalize(team), *TEAM_ALIASES.get(team, [])]


def search_players(players: pd.DataFrame, query: str, limit: int = 8) -> list[Hit]:
    """Match against both the registered name and the common short name.

    StatsBomb stores a full registered name and a separate nickname, and the two
    can be spelled differently, so searching either has to work.
    """
    needle = normalize(query)
    if not needle:
        return []
    rows: list[tuple[float, Hit]] = []
    for row in players.itertuples():
        best = max(_score(normalize(row.player_name), needle),
                   _score(normalize(row.nickname), needle))
        if best <= 0:
            continue
        nickname = row.nickname
        display = nickname if isinstance(nickname, str) and nickname.strip() \
            else row.player_name
        team = getattr(row, "team", "") or ""
        rows.append((best, Hit(
            kind="player", key=str(row.player_id), title=display,
            subtitle=" · ".join(part for part in (
                team, row.primary_position, f"{row.minutes:.0f} min") if part),
            score=best,
        )))
    return _rank(rows, limit)


def search_teams(teams: pd.DataFrame, query: str, limit: int = 5) -> list[Hit]:
    """Match team names, including the informal ones people actually type.

    Nobody searches for "Tottenham Hotspur" — they type "spurs".
    """
    needle = normalize(query)
    if not needle:
        return []
    rows: list[tuple[float, Hit]] = []
    for row in teams.itertuples():
        best = max(_score(form, needle) for form in _team_forms(row.team))
        if best <= 0:
            continue
        rows.append((best, Hit(
            kind="team", key=row.team, title=row.team,
            subtitle=str(getattr(row, "cluster_label", "") or "Club profile"),
            score=best,
        )))
    return _rank(rows, limit)


def search_matches(matches: pd.DataFrame, query: str, limit: int = 6) -> list[Hit]:
    """Match a fixture by either club, or by both ("arsenal leicester")."""
    needle = normalize(query)
    if not needle:
        return []
    query_tokens = needle.split()
    rows: list[tuple[float, Hit]] = []
    for row in matches.itertuples():
        home_forms, away_forms = _team_forms(row.home_team), _team_forms(row.away_team)
        pair = f"{normalize(row.home_team)} {normalize(row.away_team)}"
        # A single club name should surface its fixtures, but below that club's
        # own profile page, hence the discount.
        best = max(
            _score(pair, needle),
            max(_score(form, needle) for form in home_forms) * 0.6,
            max(_score(form, needle) for form in away_forms) * 0.6,
        )
        if len(query_tokens) > 1:
            names_home = any(any(_score(f, part) >= 0.80 for f in home_forms)
                             for part in query_tokens)
            names_away = any(any(_score(f, part) >= 0.80 for f in away_forms)
                             for part in query_tokens)
            if names_home and names_away:      # both clubs named, either order
                best = max(best, 0.97)
        if best <= 0.45:
            continue
        date = pd.to_datetime(row.match_date).strftime("%d %b %Y")
        rows.append((best, Hit(
            kind="match", key=str(row.match_id),
            title=f"{row.home_team} {row.home_score}–{row.away_score} {row.away_team}",
            subtitle=f"Matchweek {row.match_week} · {date}",
            score=best,
        )))
    return _rank(rows, limit)


def search_all(players: pd.DataFrame, teams: pd.DataFrame, matches: pd.DataFrame,
               query: str) -> dict[str, list[Hit]]:
    """Everything a single search box looks through, grouped by kind."""
    return {
        "player": search_players(players, query),
        "team": search_teams(teams, query),
        "match": search_matches(matches, query),
    }
