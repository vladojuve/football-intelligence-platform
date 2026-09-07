r"""Generate docs/PROJECT_GUIDE.pdf - a plain-language walkthrough of the build.

The guide explains the whole project to someone who has not read the code, naming
the file behind every claim. It is generated rather than hand-written so it can be
regenerated when the project changes, instead of quietly going stale.

Usage (from the repo root):
    .venv\Scripts\python scripts\build_project_guide.py

Two rendering constraints shaped this file:

- The built-in Helvetica has no en/em dash or curly quote glyphs, and reportlab
  draws a black box for a missing glyph. Every string therefore goes through
  `ascii_only`.
- A long path with no space in it will not wrap and overflows the column, so
  `wrap_path` inserts a zero-width break after each slash.
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import PROJECT_ROOT

OUT_PATH = PROJECT_ROOT / "docs" / "PROJECT_GUIDE.pdf"

GREEN = colors.HexColor("#0B8A3D")
DARK = colors.HexColor("#14261B")
MUTED = colors.HexColor("#5E7268")
RULE = colors.HexColor("#D5E7DC")
TINT = colors.HexColor("#F2F8F4")

# Smart punctuation the built-in fonts cannot draw.
_SUBSTITUTIONS = {
    "\u2014": " - ", "\u2013": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u00d7": "x",
    "\u2265": ">=", "\u2264": "<=", "\u2192": "->", "\u00e9": "e",
    "\u00e8": "e", "\u00fc": "u", "\u00f6": "o", "\u00e1": "a",
}


def ascii_only(text: str) -> str:
    """Replace glyphs Helvetica cannot draw, so nothing renders as a black box."""
    for bad, good in _SUBSTITUTIONS.items():
        text = text.replace(bad, good)
    return text.encode("ascii", "replace").decode("ascii")


def wrap_path(text: str) -> str:
    """Let a long path break after a slash instead of overflowing its column."""
    return text.replace("/", "/<br/>") if len(text) > 26 and "/" in text else text


_SHEET = getSampleStyleSheet()

BODY = ParagraphStyle(
    "Body", parent=_SHEET["BodyText"], fontName="Helvetica", fontSize=9.5,
    leading=13.5, textColor=DARK, spaceAfter=6, alignment=TA_LEFT,
)
LEAD = ParagraphStyle("Lead", parent=BODY, fontSize=11, leading=15,
                      textColor=MUTED, spaceAfter=10)
H1 = ParagraphStyle("H1", parent=BODY, fontName="Helvetica-Bold", fontSize=20,
                    leading=24, textColor=DARK, spaceAfter=4, spaceBefore=0)
H2 = ParagraphStyle("H2", parent=BODY, fontName="Helvetica-Bold", fontSize=13.5,
                    leading=17, textColor=GREEN, spaceBefore=14, spaceAfter=6,
                    keepWithNext=1)
H3 = ParagraphStyle("H3", parent=BODY, fontName="Helvetica-Bold", fontSize=10.5,
                    leading=14, textColor=DARK, spaceBefore=10, spaceAfter=4,
                    keepWithNext=1)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=8.5, leading=11.5,
                      spaceAfter=0)
CELL_HEAD = ParagraphStyle("CellHead", parent=CELL, fontName="Helvetica-Bold",
                           textColor=colors.white)
CODE = ParagraphStyle("Code", parent=CELL, fontName="Courier", fontSize=8,
                      leading=11)
NOTE = ParagraphStyle("Note", parent=BODY, fontSize=9, leading=12.5,
                      textColor=MUTED, leftIndent=8, spaceBefore=2)


def para(text: str, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(ascii_only(text), style)


def bullets(items: list[str]) -> list:
    return [para(f"&bull;&nbsp;&nbsp;{item}") for item in items]


def table(header: list[str], rows: list[list[str]], widths: list[float],
          code_column: int | None = None) -> Table:
    """A two- or three-column reference table with the project's green header."""
    data = [[Paragraph(ascii_only(h), CELL_HEAD) for h in header]]
    for row in rows:
        cells = []
        for index, value in enumerate(row):
            style = CODE if index == code_column else CELL
            cells.append(Paragraph(ascii_only(wrap_path(value)), style))
        data.append(cells)
    built = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    built.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TINT]),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return built


def decorate(canvas, doc) -> None:
    """Running header and footer on every page."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, A4[1] - 12 * mm,
                      "Football Intelligence Platform - project guide")
    canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm,
                           f"Page {doc.page}")
    canvas.setStrokeColor(RULE)
    canvas.line(20 * mm, A4[1] - 14 * mm, A4[0] - 20 * mm, A4[1] - 14 * mm)
    canvas.drawString(
        20 * mm, 12 * mm,
        ascii_only("Data provided by StatsBomb. Results are descriptive: "
                   "similarity means two players do similar things, not that "
                   "they are equally good."))
    canvas.restoreState()


def story() -> list:
    """The document, in order."""
    full = A4[0] - 40 * mm
    flow: list = []

    flow += [
        para("Football Intelligence Platform", H1),
        para("What we built, in plain language - with the file names", LEAD),
        para(
            "<b>What the project does.</b> It answers two questions about "
            "football, using the record of every single touch in a season:"),
    ]
    flow += bullets([
        "<b>Who plays like this player?</b> Pick a player, get a ranked list of "
        "others who do similar things - plus the reasons why.",
        "<b>Which teams play alike?</b> Group the 20 teams by their style of "
        "play, and show what makes each group different.",
    ])
    flow += [
        para(
            "It deliberately does not predict match results. It describes what "
            "happened, which is what a scout or analyst actually needs."),
        para("The data", H3),
        para(
            "StatsBomb Open Data for the Premier League 2015/16 season: 380 "
            "matches and 1,313,773 individual events (every pass, shot, tackle "
            "and pressure, each with pitch coordinates). It is free and legal to "
            "use with attribution. We chose depth over recency: newer free data "
            "has only summary totals, which cannot support the spatial features "
            "this project is built on."),
        para("Repository: github.com/SamiRadulov/football-intelligence-platform",
             NOTE),

        para("1. The big picture: data flows downhill", H2),
        para(
            "Everything is built as a chain of layers. Each layer only reads from "
            "the one above it and never edits it. If a number looks wrong, you "
            "can walk back up the chain to find where it came from."),
        table(
            ["Layer", "What lives there", "Where"],
            [
                ["1. Raw", "The original StatsBomb JSON files, completely unchanged",
                 "data/raw/"],
                ["2. Staging", "The same data flattened into clean tables (Parquet files)",
                 "data/staging/"],
                ["3. Curated", "Those tables loaded into a database that can be queried",
                 "data/curated.duckdb"],
                ["4. Marts", "The finished per-player and per-team measurements",
                 "tables inside that database"],
                ["5. Models",
                  "Similarity and the team style groups", "src/similarity/, src/clustering/"],
                ["6. App", "The website that shows all of it", "app.py, pages/"],
            ],
            [full * 0.14, full * 0.56, full * 0.30], code_column=2),
        para(
            "The build stops if any of 15 hard quality checks fails, so the "
            "finished measurements can never be built from data that breaks "
            "them.", NOTE),

        para("2. What was built, phase by phase", H2),

        para("Phase 0 - Choosing the data", H3),
        para(
            "Every free competition-season was audited before anything was built. "
            "The audit is saved so the choice can be re-examined."),
        table(
            ["File", "What it does"],
            [["scripts/data_audit.py", "Counts what each dataset actually contains"],
             ["docs/data_audit.csv", "The audit result"],
             ["artifacts/feature_config.yml",
              "Every analytical setting in one editable file, so choices are "
              "reviewable without reading code"]],
            [full * 0.34, full * 0.66], code_column=0),

        para("Phase 1 - Getting the data", H3),
        table(
            ["File", "What it does"],
            [["src/ingestion/statsbomb_open_data.py", "Downloads one file, safely and repeatably"],
             ["scripts/download_data.py", "Downloads the whole season"],
             ["data/raw/manifest.json", "A record of exactly what was downloaded and when"]],
            [full * 0.34, full * 0.66], code_column=0),
        para(
            "Downloads are idempotent: a file is written to a temporary name and "
            "renamed only when complete, so an interrupted run never leaves a "
            "half-file behind.", NOTE),

        para("Phase 2 - Cleaning it up", H3),
        table(
            ["File", "What it does"],
            [["src/transformations/matches.py", "The fixture list"],
             ["src/transformations/players.py", "The player list"],
             ["src/transformations/minutes.py", "Who was on the pitch, and for how long"],
             ["src/transformations/events.py", "1.3 million events into one flat table"],
             ["src/transformations/names.py", "Repairs a spelling fault in the source data"],
             ["src/validation/checks.py", "The 15 quality checks"],
             ["scripts/build_staging.py", "Runs all of the above"]],
            [full * 0.34, full * 0.66], code_column=0),

        para("Phase 3 - Measuring players", H3),
        table(
            ["File", "What it does"],
            [["src/features/roles.py", "Sorts players into five position groups"],
             ["src/features/player_match.py", "What each player did in each match"],
             ["src/features/player_season.py", "Season totals turned into fair per-90 rates"],
             ["scripts/build_player_features.py", "Runs it"]],
            [full * 0.34, full * 0.66], code_column=0),
        para(
            "Everything is compared <b>within a position group</b>. Forty passes "
            "per 90 minutes means one thing for a centre-back and something else "
            "for a winger, so a centre-back is only ever ranked against other "
            "centre-backs."),

        para("Phase 4 - Finding similar players", H3),
        table(
            ["File", "What it does"],
            [["src/similarity/feature_matrix.py", "Puts every player on a comparable scale"],
             ["src/similarity/engine.py", "The similarity calculation and its explanation"],
             ["scripts/find_similar.py", "Ask a question from the command line"],
             ["scripts/validate_similarity.py", "Proves the answers are stable"]],
            [full * 0.34, full * 0.66], code_column=0),
        para(
            "Two rules make the answers defensible. Candidates are filtered by "
            "position and minutes <b>before</b> anything is scored, so an "
            "unsuitable player cannot appear by statistical fluke. And every "
            "result comes with the reasons: where the two players match, and "
            "where they differ."),
        para(
            "It works: Kante returns Gueye, Cork and Dembele. Ozil returns "
            "De Bruyne, Silva and Payet.", NOTE),

        para("Phase 5 and 6 - Measuring and grouping teams", H3),
        table(
            ["File", "What it does"],
            [["src/features/pitch.py",
               "Shared pitch geometry, so player and team definitions cannot drift apart"],
             ["src/features/team_match.py", "28 style measurements per team per match"],
             ["src/features/team_season.py", "Season averages, and how much each varies"],
             ["src/clustering/style_model.py", "The grouping maths"],
             ["scripts/build_team_clusters.py",
              "Run with --explore first to inspect the options, then again to save the model"]],
            [full * 0.34, full * 0.66], code_column=0),
        para(
            "The groups were named only after looking at what defined them, "
            "never decided in advance."),
        table(
            ["Style", "Teams", "What defines them"],
            [["Possession-dominant high press",
              "Arsenal, Chelsea, Liverpool, Man City, Man Utd, Spurs",
              "Keep the ball, play high up the pitch, press aggressively, few long balls"],
             ["Direct and wide",
              "Palace, Leicester, Norwich, Southampton, Sunderland, Watford, "
              "West Brom, West Ham",
              "Move the ball forward quickly, many long passes and crosses, less possession"],
             ["Deep build-up, low territory",
              "Bournemouth, Villa, Everton, Newcastle, Stoke, Swansea",
              "Play in their own half, pass backwards more, rarely reach the final third"]],
            [full * 0.22, full * 0.40, full * 0.38]),
        para("The honest caveat we wrote down", H3),
        para(
            "The first group is exactly the big six. That means style and quality "
            "are tangled together, because better teams naturally have more "
            "possession. We state this openly rather than waiting for someone to "
            "spot it. The counter-evidence: the direct and wide group contains "
            "both the champions (Leicester) and two relegated sides, so the "
            "groups are not simply the league table."),

        para("Phase 7 and 8 - The app, and putting it online", H3),
        para("Eight pages, reachable from one search box."),
        table(
            ["File", "The page"],
            [["app.py", "The entry point - start the app with this"],
             ["pages/home.py", "One search box over players, clubs and fixtures"],
             ["pages/player_search.py", "Find similar players"],
             ["pages/player_profile.py",
               "One player: twelve percentile rings, or a report-style table"],
             ["pages/player_comparison.py", "Compare two players side by side"],
             ["pages/team_profile.py",
               "One club: its record, its style, its league-leading players"],
             ["pages/team_style_map.py", "The map of team styles"],
             ["pages/matches.py", "All 380 fixtures, and a full report for any one of them"],
             ["pages/methodology.py", "How it works, and the limitations"],
             ["src/app/search.py", "Search that accepts names as they are typed"],
             ["src/app/data.py", "Loads data once and remembers it, so the app stays fast"],
             ["src/app/charts.py", "The charts"]],
            [full * 0.34, full * 0.66], code_column=0),
        para(
            "Charts show percentiles rather than statistical scores, because "
            "\"84th percentile among centre-backs\" means something to a human "
            "and \"z = +1.02\" does not."),
        para(
            "Search works in plain English. Apostrophes and accents are optional, "
            "because they are stripped from both the query and the name before "
            "matching: \"Ngolo Kante\" is an exact match for the stored "
            "\"N'Golo Kante\", and \"spurs\" finds Tottenham Hotspur.", NOTE),
        table(
            ["File", "What it does"],
            [["scripts/build_app_db.py",
               "Makes a small 3.4 MB database holding only the finished results"],
             ["data/sample/app.duckdb",
               "That database - the only data file stored in the repository"],
             [".streamlit/config.toml", "The colours and text sizes"],
             [".github/workflows/ci.yml", "Runs the tests automatically on every change"],
             ["scripts/capture_screenshots.py", "Regenerates the README screenshots"]],
            [full * 0.34, full * 0.66], code_column=0),
        para(
            "Because the raw data is not stored in the repository, the automatic "
            "test run has to use that small database - which means every test run "
            "is also a test of exactly what gets deployed.", NOTE),

        para("3. How we know it works", H2),
        para(
            "There are 168 automatic tests. They run in about a minute and check "
            "the things that are easy to get quietly wrong."),
        table(
            ["Test file", "What it protects"],
            [["tests/test_ingestion.py", "The download addresses are correct"],
             ["tests/test_minutes.py",
               "Minutes are counted correctly, including the injury-gap bug"],
             ["tests/test_events.py", "Events are flattened correctly, including the aerials bug"],
             ["tests/test_names.py", "The spelling repair fixes the fault and nothing else"],
             ["tests/test_roles.py", "Players land in the right position group"],
             ["tests/test_player_match.py",
              "The football definitions: progressive pass, box entry, penalties excluded"],
             ["tests/test_similarity.py", "The similarity maths behaves sensibly"],
             ["tests/test_team_match.py", "Team measurements, including the set-piece fix"],
             ["tests/test_clustering.py", "Grouping finds groups that really are there"],
             ["tests/test_search.py", "Names typed without accents still find the player"],
             ["tests/test_insights.py", "The league table, and the top-three rule"],
             ["tests/test_app_smoke.py", "Every page of the app loads without crashing"]],
            [full * 0.30, full * 0.70], code_column=0),
        para("The pattern worth noticing", H3),
        para(
            "Four real bugs were found in this project: minutes counting injury "
            "gaps, aerial duels missing entirely, set pieces defined too loosely, "
            "and ten player names arriving with doubled apostrophes. None of them "
            "were found by staring at code - the code ran fine and produced the "
            "wrong number. Each was caught by asking <b>does this look like "
            "football?</b> and then investigating instead of assuming. That habit "
            "is the single most valuable thing here."),

        para("4. The commands", H2),
        para("Run these from the project folder. Steps 1 to 5 only need running once."),
        para('cd "C:\\Users\\user\\Documents\\Claude\\Projects\\'
             'Football Intelligence platform"', CODE),
        Spacer(1, 4),
        table(
            ["Step", "Command"],
            [["1. Download the data (~1.2 GB, one-off)",
              ".venv\\Scripts\\python scripts\\download_data.py"],
             ["2. Build the clean tables",
              ".venv\\Scripts\\python scripts\\build_staging.py"],
             ["3. Build the player metrics",
              ".venv\\Scripts\\python scripts\\build_player_features.py"],
             ["4. Build the team style metrics",
              ".venv\\Scripts\\python scripts\\build_team_features.py"],
             ["5. Group the teams by style",
              ".venv\\Scripts\\python scripts\\build_team_clusters.py"],
             ["Start the app", ".venv\\Scripts\\streamlit run app.py"],
             ["Ask a similarity question",
              '.venv\\Scripts\\python scripts\\find_similar.py "Kante"'],
             ["Run all the tests", ".venv\\Scripts\\python -m pytest -q"]],
            [full * 0.42, full * 0.58], code_column=1),

        para("5. The written documents", H2),
        table(
            ["File", "What it contains"],
            [["README.md", "The front page: what it is and how to run it"],
             ["METHODOLOGY.md", "How the models work, the validation results, and the limitations"],
             ["docs/MODEL_CARD.md",
               "The player similarity model: what to use it for, and where it fails"],
             ["docs/CLUSTER_CARD.md",
               "The team style groups: how they were chosen, and their limits"],
             ["docs/METRIC_DICTIONARY.md", "Every metric defined precisely, with its denominator"],
             ["AI_USAGE.md",
               "How this was built with an AI assistant, including what it got wrong"],
             ["DATA_SOURCES.md", "Where the data comes from and the attribution required"],
             ["artifacts/feature_config.yml", "All the analytical settings in one editable file"]],
            [full * 0.32, full * 0.68], code_column=0),
        para("The one thing to remember", H3),
        para(
            "The value of this project is not that it uses clever maths. It is "
            "that every number can be traced back to a definition, every "
            "definition is written down, and every claim has been checked against "
            "what actually happened on the pitch. That is what makes it "
            "defensible when someone asks you about it."),
    ]
    return flow


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    document = BaseDocTemplate(
        str(OUT_PATH), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=18 * mm,
        title="Football Intelligence Platform - project guide",
        author="Samuil Radulov",
    )
    frame = Frame(document.leftMargin, document.bottomMargin,
                  document.width, document.height, id="body")
    document.addPageTemplates([
        PageTemplate(id="all", frames=[frame], onPage=decorate)])
    document.build(story())

    size_kb = OUT_PATH.stat().st_size / 1000
    print(f"Wrote {OUT_PATH} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
