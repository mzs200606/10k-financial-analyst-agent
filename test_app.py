"""Smoke tests that actually render the Streamlit app (with a fake Gemini) and click through it."""
import pytest
from streamlit.testing.v1 import AppTest

import agent
from test_agent import THREAD, extraction, fake_client, run_until_pause


def new_app():
    return AppTest.from_file("app.py", default_timeout=30)


def test_first_screen_renders_and_run_is_disabled_without_inputs(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = new_app().run()
    assert not at.exception
    assert at.title[0].value.endswith("10-K Financial Analyst Agent")
    run_button = next(b for b in at.button if b.label == "Run analysis")
    assert run_button.disabled


def paused_app(**overrides):
    graph = agent.build_graph(fake_client(extraction(**overrides)),
                              on_token=lambda t: None)
    run_until_pause(graph)
    holder = {"fn": lambda t: None}
    at = new_app()
    at.session_state["stage"] = "review"
    at.session_state["graph"] = graph
    at.session_state["thread"] = THREAD
    at.session_state["holder"] = holder
    at.session_state["version"] = 0
    return at.run()


def test_review_screen_renders_with_approve_enabled():
    at = paused_app()
    assert not at.exception
    approve = next(b for b in at.button if b.label == "Approve & continue")
    assert not approve.disabled


def test_review_screen_disables_approve_when_blocker_present():
    at = paused_app(revenue=None)
    assert not at.exception
    approve = next(b for b in at.button if b.label == "Approve & continue")
    assert approve.disabled
    assert any("BLOCKER" in e.value for e in at.error)


def test_approving_moves_to_results_with_memo():
    at = paused_app()
    next(b for b in at.button if b.label == "Approve & continue").click().run()
    assert not at.exception
    assert at.session_state["stage"] == "done"
    assert any("Memo text." in m.value for m in at.markdown)
    assert any(b.label == "Analyze another filing" for b in at.button)


def test_fixing_a_missing_figure_unblocks_approval_and_finishes():
    at = paused_app(revenue=None)
    graph = at.session_state["graph"]
    agent.fix_figure(graph, THREAD, "current", "revenue", 1000)
    assert graph.get_state(THREAD).next == ("compute_ratios",)
    at.run()
    approve = next(b for b in at.button if b.label == "Approve & continue")
    assert not approve.disabled
    approve.click().run()
    assert at.session_state["stage"] == "done"
    assert at.session_state["graph"].get_state(THREAD).values["verdicts"]["net_margin"]["value"] == 8.0
