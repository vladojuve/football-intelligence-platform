"""Derived views the app shows but the marts do not store.

Everything here is cheap to recompute from tables that already exist, so it is
deliberately *not* another mart: a league table is a `groupby` over 380 rows, and
freezing it into the database would add a build step, a schema and a staleness
risk in exchange for nothing.

These functions take dataframes rather than reading the database themselves, so
they are testable without a Streamlit session or a built pipeline.
"""

from __future__ import annotations

import pandas as pd

from .labels import NOT_A_DISTINCTION, pretty

# Three points for a win, one for a draw — the scoring in use since 1981.
WIN_POINTS, DRAW_POINTS = 3, 1


def _team_match_rows(matches: pd.DataFrame) -> pd.DataFrame:
    """One row per team per match, so home and away can be aggregated together."""
    home = matches.rename(columns={
        "home_team": "team", "away_team": "opponent",
        "home_score": "goals_for", "away_score": "goals_against",
    }).assign(venue="Home")
    away = matches.rename(columns={
        "away_team": "team", "home_team": "opponent",
        "away_score": "goals_for", "home_score": "goals_against",
    }).assign(venue="Away")
    columns = ["match_id", "match_date", "match_week", "team", "opponent",
               "goals_for", "goals_against", "venue", "stadium", "referee"]
    long = pd.concat([home[columns], away[columns]], ignore_index=True)
    long["result"] = long.apply(
        lambda r: "W" if r.goals_for > r.goals_against
        else ("D" if r.goals_for == r.goals_against else "L"), axis=1)
    long["points"] = long["result"].map({"W": WIN_POINTS, "D": DRAW_POINTS, "L": 0})
    return long


def league_table(matches: pd.DataFrame) -> pd.DataFrame:
    """The final standings, ordered the way the Premier League orders them.

    Points, then goal difference, then goals scored. The league's fourth
    tiebreaker is a play-off, which never happened in this season, so it is not
    implemented — an alphabetical fallback would silently invent an ordering.
    """
    rows = _team_match_rows(matches)
    table = rows.groupby("team").agg(
        played=("match_id", "count"),
        won=("result", lambda s: (s == "W").sum()),
        drawn=("result", lambda s: (s == "D").sum()),
        lost=("result", lambda s: (s == "L").sum()),
        goals_for=("goals_for", "sum"),
        goals_against=("goals_against", "sum"),
        points=("points", "sum"),
    ).reset_index()
    table["goal_difference"] = table["goals_for"] - table["goals_against"]
    table = table.sort_values(
        ["points", "goal_difference", "goals_for"], ascending=False,
    ).reset_index(drop=True)
    table.insert(0, "position", range(1, len(table) + 1))
    return table


def club_record(matches: pd.DataFrame, team: str) -> dict:
    """Everything about a club that comes from results rather than from style.

    The style marts describe *how* a side played; this is the other half a club
    page needs — where they finished, how they did home and away, their best and
    worst afternoons.
    """
    rows = _team_match_rows(matches)
    ours = rows[rows["team"] == team].sort_values("match_date")
    if ours.empty:
        return {}

    table = league_table(matches)
    standing = table[table["team"] == team].iloc[0]

    def _venue(name: str) -> dict:
        subset = ours[ours["venue"] == name]
        return {
            "played": len(subset),
            "won": int((subset["result"] == "W").sum()),
            "drawn": int((subset["result"] == "D").sum()),
            "lost": int((subset["result"] == "L").sum()),
            "goals_for": int(subset["goals_for"].sum()),
            "goals_against": int(subset["goals_against"].sum()),
            "points": int(subset["points"].sum()),
        }

    margins = ours["goals_for"] - ours["goals_against"]
    best = ours.loc[margins.idxmax()]
    worst = ours.loc[margins.idxmin()]
    home_stadiums = ours[ours["venue"] == "Home"]["stadium"].dropna()

    return {
        "team": team,
        "position": int(standing["position"]),
        "points": int(standing["points"]),
        "played": int(standing["played"]),
        "won": int(standing["won"]),
        "drawn": int(standing["drawn"]),
        "lost": int(standing["lost"]),
        "goals_for": int(standing["goals_for"]),
        "goals_against": int(standing["goals_against"]),
        "goal_difference": int(standing["goal_difference"]),
        "clean_sheets": int((ours["goals_against"] == 0).sum()),
        "failed_to_score": int((ours["goals_for"] == 0).sum()),
        "home": _venue("Home"),
        "away": _venue("Away"),
        "biggest_win": _scoreline(best),
        "biggest_defeat": _scoreline(worst),
        "stadium": home_stadiums.mode().iloc[0] if not home_stadiums.empty else None,
        "form": "".join(ours["result"].tail(6)),
        "matches": ours,
    }


def _scoreline(row: pd.Series) -> str:
    versus = "vs" if row["venue"] == "Home" else "at"
    return f"{row['goals_for']}–{row['goals_against']} {versus} {row['opponent']}"


def special_players(
    player_season: pd.DataFrame, metrics: list[str], top_n: int = 3,
) -> pd.DataFrame:
    """Players who finished in the league's top `top_n` for any metric.

    Ranking is **league-wide, across every role**, because that is what "top
    three in the league" means. It is a deliberately different question from the
    percentiles elsewhere in the app, which are always within-role: a centre-back
    can be the league's best in the air without being near the top for shots, and
    both facts are worth surfacing.

    Metrics where a high value is a description rather than a distinction (a
    turnover count, say) are excluded — a "special players" table has to mean
    something, and being third for giving the ball away does not.
    """
    scored: list[dict] = []
    for metric in metrics:
        if metric in NOT_A_DISTINCTION or metric not in player_season.columns:
            continue
        available = player_season[player_season[metric].notna()]
        if available.empty:
            continue
        # `method="min"` gives joint leaders the same rank, which is correct:
        # two players tied for first are both first, and neither is second.
        ranks = available[metric].rank(ascending=False, method="min")
        leaders = available[ranks <= top_n]
        for _, row in leaders.iterrows():
            scored.append({
                "player_id": int(row["player_id"]),
                "team_id": int(row["team_id"]),
                "metric": metric,
                "metric_label": pretty(metric),
                "rank": int(ranks.loc[row.name]),
                "value": float(row[metric]),
            })
    if not scored:
        return pd.DataFrame(columns=["player_id", "team_id", "metric", "metric_label",
                                     "rank", "value"])
    return pd.DataFrame(scored).sort_values(["rank", "metric_label"]).reset_index(drop=True)


def summarise_special_players(entries: pd.DataFrame) -> pd.DataFrame:
    """Collapse the per-metric rows into one row per player."""
    if entries.empty:
        return pd.DataFrame(columns=["player_id", "top3_count", "best_rank", "metrics"])
    grouped = entries.groupby("player_id").agg(
        top3_count=("metric", "count"),
        best_rank=("rank", "min"),
        metrics=("metric_label", lambda s: ", ".join(s)),
    ).reset_index()
    return grouped.sort_values(["top3_count", "best_rank"],
                               ascending=[False, True]).reset_index(drop=True)
