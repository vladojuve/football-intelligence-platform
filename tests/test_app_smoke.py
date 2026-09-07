"""Smoke tests: every app page must render without raising.

Pages are exercised through `app.py` and `switch_page`, the same way a user
reaches them, because navigation context only exists inside `st.navigation` —
running a page file standalone would test it in a situation that never occurs.

Interactive paths (selecting a player, a club, a match) are covered too, since
that is where page-level bugs actually live.

These need a built database, so they skip cleanly on a machine that has not run
the pipeline yet — the rest of the suite is pure unit tests with no data
dependency.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.app.data import DB_PATH

# AppTest resolves relative paths against the file that calls it, so a bare
# "app.py" would be looked up inside tests/. Absolute paths keep these tests
# independent of the working directory they are run from.
REPO_ROOT = Path(__file__).resolve().parent.parent

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="no app database built; run scripts/build_staging.py or build_app_db.py",
)

PAGES = [
    "pages/home.py",
    "pages/player_search.py",
    "pages/player_profile.py",
    "pages/player_comparison.py",
    "pages/team_style_map.py",
    "pages/team_profile.py",
    "pages/matches.py",
    "pages/methodology.py",
]

TIMEOUT = 120


def _open(page: str | None = None, **query_params: str) -> AppTest:
    """Run the app, optionally navigating to a page with query parameters."""
    app = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=TIMEOUT)
    for key, value in query_params.items():
        app.query_params[key] = value
    app.run()
    if page is not None:
        app.switch_page(str(REPO_ROOT / page))
        app.run()
    return app


def _assert_clean(app: AppTest) -> None:
    assert not app.exception, [e.value for e in app.exception]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page):
    _assert_clean(_open(page))


def test_home_reports_dataset_coverage():
    app = _open("pages/home.py")
    labels = [m.label for m in app.metric]
    assert "Matches" in labels
    assert "Qualified players" in labels


def test_home_search_finds_a_player_typed_without_accents():
    """The whole point of the search box: "Ngolo Kante" must find N'Golo Kanté."""
    app = _open("pages/home.py")
    app.text_input[0].set_value("Ngolo Kante").run()

    _assert_clean(app)
    labels = [b.label for b in app.button]
    assert any("Kant" in label for label in labels), labels


def test_home_search_reports_a_miss_instead_of_failing():
    app = _open("pages/home.py")
    app.text_input[0].set_value("qqqzzz").run()

    _assert_clean(app)
    assert any("Nothing matched" in w.value for w in app.warning)


def test_player_search_returns_ranked_candidates():
    app = _open("pages/player_search.py")
    options = app.selectbox[0].options
    vardy = next(o for o in options if "Vardy" in o)

    app.selectbox[0].select(vardy).run()

    _assert_clean(app)
    assert "Role group" in [m.label for m in app.metric]
    assert len(app.dataframe) >= 1          # the ranked results table


def test_player_search_respects_the_minutes_filter():
    app = _open("pages/player_search.py")
    vardy = next(o for o in app.selectbox[0].options if "Vardy" in o)
    app.selectbox[0].select(vardy).run()

    app.slider[0].set_value(3000).run()      # very few players qualify
    _assert_clean(app)


def test_player_profile_opens_from_a_link_and_draws_its_rings():
    """A `?player=<id>` link is how every other page opens a profile."""
    from src.app import data

    player = data.player_options().iloc[0]
    app = _open("pages/player_profile.py", player=str(int(player["player_id"])))

    _assert_clean(app)
    assert {"Minutes", "Matches", "Role group"} <= {m.label for m in app.metric}
    # The name is a heading rather than a metric, because a metric value is
    # rendered at heading size and truncates instead of wrapping.
    assert player["display_name"] in [h.value for h in app.header]
    assert app.selectbox[0].value is not None


def test_player_profile_switches_between_rings_and_the_table_view():
    """Both shapes of the percentile profile have to render for the same player."""
    from src.app import data

    player = data.player_options().iloc[0]
    app = _open("pages/player_profile.py", player=str(int(player["player_id"])))

    control = app.segmented_control[0]
    assert control.value == "Rings"

    control.set_value("Table & radar").run()
    _assert_clean(app)
    # The table view adds a dataframe the ring view does not have.
    assert len(app.dataframe) >= 2


def test_player_profile_ignores_a_nonsense_player_parameter():
    """A hand-edited URL must land on the picker, not on a traceback."""
    app = _open("pages/player_profile.py", player="not-an-id")

    _assert_clean(app)
    assert app.selectbox[0].value is None


def test_player_comparison_renders_two_player_breakdown():
    app = _open("pages/player_comparison.py")
    app.selectbox[0].select("ST").run()

    options = app.selectbox[1].options
    app.selectbox[1].select(options[0]).run()
    app.selectbox[2].select(options[1]).run()

    _assert_clean(app)
    assert any(m.label == "Similarity" for m in app.metric)
    assert len(app.dataframe) >= 2          # "most alike" and "biggest differences"


def test_player_comparison_rejects_the_same_player_twice():
    app = _open("pages/player_comparison.py")
    app.selectbox[0].select("ST").run()
    same = app.selectbox[1].options[0]
    app.selectbox[1].select(same).run()
    app.selectbox[2].select(same).run()

    _assert_clean(app)
    assert any("two different players" in w.value for w in app.warning)


def test_team_profile_renders_record_style_and_special_players():
    app = _open("pages/team_profile.py", team="Leicester City")

    _assert_clean(app)
    labels = {m.label: m.value for m in app.metric}
    assert labels.get("Final position") == "1"          # champions that season
    assert "Points" in labels
    headers = [s.value for s in app.subheader]
    assert "Special players" in headers
    assert "Style fingerprint" in headers


def test_club_profile_switches_between_rings_and_the_table_view():
    app = _open("pages/team_profile.py", team="Leicester City")

    control = app.segmented_control[0]
    assert control.value == "Rings"

    control.set_value("Table & radar").run()
    _assert_clean(app)
    assert "Special players" in [s.value for s in app.subheader]


def test_team_style_map_selects_every_cluster_by_default():
    app = _open("pages/team_style_map.py")
    _assert_clean(app)
    assert len(app.multiselect[0].value) >= 2


def test_matches_lists_every_fixture():
    app = _open("pages/matches.py")
    _assert_clean(app)
    assert any("380" in c.value for c in app.caption)


def test_match_report_opens_from_a_link():
    from src.app import data

    fixtures = data.matches()
    match = fixtures.iloc[0]
    app = _open("pages/matches.py", match=str(int(match["match_id"])))

    _assert_clean(app)
    headers = " ".join(h.value for h in app.header)
    assert match["home_team"] in headers
    assert match["away_team"] in headers
    assert any(s.value == "Players" for s in app.subheader)


def test_methodology_page_embeds_the_docs():
    app = _open("pages/methodology.py")
    _assert_clean(app)
    body = " ".join(m.value for m in app.markdown)
    assert "StatsBomb" in body


# --- deployment database ---------------------------------------------------

def test_committed_app_database_has_everything_the_app_reads():
    """The deployed app runs against data/sample/app.duckdb, not the full
    curated database, so that file must carry every table the pages query."""
    import duckdb

    from src.app.data import APP_DB_PATH

    assert APP_DB_PATH.exists(), "run scripts/build_app_db.py"
    con = duckdb.connect(str(APP_DB_PATH), read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        required = {"mart_player_season", "mart_team_season", "mart_team_match",
                    "model_team_style", "dim_matches", "pipeline_stats",
                    # the match report needs these two
                    "fact_lineups", "mart_player_match"}
        assert required <= tables, f"missing: {sorted(required - tables)}"
        assert con.execute("SELECT count(*) FROM mart_player_season").fetchone()[0] > 0
        assert con.execute("SELECT count(*) FROM model_team_style").fetchone()[0] > 0
        assert con.execute("SELECT count(*) FROM fact_lineups").fetchone()[0] > 0
    finally:
        con.close()
