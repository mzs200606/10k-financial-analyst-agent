"""End-to-end tests of the LangGraph agent using a fake Gemini client (no API key, no network)."""
import json
from types import SimpleNamespace

import pytest

import agent


def cell(value, page=33):
    return {"value": value, "page": page}


def extraction(**overrides):
    cur = dict(revenue=1000, net_income=80, total_assets=900, equity=400,
               current_assets=300, current_liabilities=250, operating_cash_flow=120,
               ebit=150, interest_on_debt=-20, interest_on_finance_leases=10,
               inventory=100, receivables=90, short_term_borrowings=30,
               current_portion_long_term_debt=20, long_term_debt=200,
               total_liabilities_and_equity=900)
    pri = {**cur, "revenue": 950, "net_income": 70, "receivables": 85}
    cur.update(overrides)
    return {"company_name": "TestCo", "units": "millions", "currency": "USD",
            "fiscal_year_current": "FY2025", "fiscal_year_prior": "FY2024",
            "is_financial_institution": False,
            "figures": {"current": {k: cell(v) for k, v in cur.items()},
                        "prior": {k: cell(v) for k, v in pri.items()}}}


def fake_client(data):
    return SimpleNamespace(
        files=SimpleNamespace(
            upload=lambda file: SimpleNamespace(name="files/1", uri="fake://1", mime_type="application/pdf",
                                                state=SimpleNamespace(name="ACTIVE")),
            get=lambda name: None),
        models=SimpleNamespace(
            generate_content=lambda model, contents, config: SimpleNamespace(text=json.dumps(data)),
            generate_content_stream=lambda model, contents, config: iter(
                [SimpleNamespace(text="Memo "), SimpleNamespace(text="text.")])))


THREAD = {"configurable": {"thread_id": "t1"}}


def run_until_pause(graph, sector="general"):
    for _ in graph.stream({"pdf_path": "fake.pdf", "sector": sector}, THREAD):
        pass


def test_pauses_for_human_review_before_ratios():
    graph = agent.build_graph(fake_client(extraction()))
    run_until_pause(graph)
    assert graph.get_state(THREAD).next == ("compute_ratios",)
    assert "verdicts" not in graph.get_state(THREAD).values


def test_resuming_computes_ratios_verdicts_and_memo():
    tokens = []
    graph = agent.build_graph(fake_client(extraction()), on_token=tokens.append)
    run_until_pause(graph)
    for _ in graph.stream(None, THREAD):
        pass
    state = graph.get_state(THREAD).values
    assert graph.get_state(THREAD).next == ()
    assert len(state["verdicts"]) == 8
    assert state["memo"] == "Memo text."
    assert tokens == ["Memo ", "text."]


def test_interest_coverage_is_derived_from_components():
    graph = agent.build_graph(fake_client(extraction()))
    run_until_pause(graph)
    for _ in graph.stream(None, THREAD):
        pass
    # ebit 150 / (interest on debt 20 + finance leases 10) = 5.0; negative sign from the LLM is made positive
    assert graph.get_state(THREAD).values["verdicts"]["interest_coverage"]["value"] == 5.0


def test_missing_required_figure_stops_the_run_before_review():
    graph = agent.build_graph(fake_client(extraction(revenue=None)))
    run_until_pause(graph)
    state = graph.get_state(THREAD)
    assert state.next == ()
    assert any(i.startswith("BLOCKER") for i in state.values["issues"])
    assert "verdicts" not in state.values


def test_bank_is_blocked():
    data = extraction()
    data["is_financial_institution"] = True
    graph = agent.build_graph(fake_client(data))
    run_until_pause(graph)
    assert any("bank" in i for i in graph.get_state(THREAD).values["issues"])


def test_fix_figure_updates_value_marks_it_edited_and_revalidates():
    graph = agent.build_graph(fake_client(extraction(revenue=None)))
    run_until_pause(graph)
    agent.fix_figure(graph, THREAD, "current", "revenue", 1000)
    state = graph.get_state(THREAD)
    assert state.values["figures"]["current"]["revenue"] == 1000.0
    assert state.values["pages"]["current"]["revenue"] == "edited"
    assert not any(i.startswith("BLOCKER") for i in state.values["issues"])


def test_fix_figure_rejects_unknown_field():
    graph = agent.build_graph(fake_client(extraction()))
    run_until_pause(graph)
    with pytest.raises(AssertionError):
        agent.fix_figure(graph, THREAD, "current", "not_a_field", 1)


def test_with_retry_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("503")
        return "ok"

    assert agent.with_retry(flaky) == "ok"
    assert calls["n"] == 3


def test_with_retry_gives_up_after_all_tries(monkeypatch):
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)

    def always_fails():
        raise RuntimeError("503")

    with pytest.raises(RuntimeError):
        agent.with_retry(always_fails, tries=3)


def test_to_number_handles_commas_parentheses_and_junk():
    assert agent.to_number("1,234") == 1234.0
    assert agent.to_number("(500)") == -500.0
    assert agent.to_number("$2,000") == 2000.0
    assert agent.to_number("n/a") is None
    assert agent.to_number(None) is None
