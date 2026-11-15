"""Tests for the table-building helpers behind the Streamlit UI."""
import math

import pandas as pd

import agent
import ui_helpers as ui
from test_agent import THREAD, extraction, fake_client, run_until_pause


def paused_state(**overrides):
    graph = agent.build_graph(fake_client(extraction(**overrides)))
    run_until_pause(graph)
    return graph, graph.get_state(THREAD).values


def test_figures_table_has_one_row_per_figure_with_pages():
    _, state = paused_state()
    df = ui.figures_to_df(state)
    assert list(df["figure"]) == list(agent.FIELDS)
    assert df.loc[df["figure"] == "revenue", "current"].item() == 1000
    assert df.loc[df["figure"] == "revenue", "page (current)"].item() == "33"


def test_missing_values_show_as_nan():
    _, state = paused_state(revenue=None)
    df = ui.figures_to_df(state)
    assert math.isnan(df.loc[df["figure"] == "revenue", "current"].item())


def test_no_edits_when_table_unchanged():
    _, state = paused_state()
    df = ui.figures_to_df(state)
    assert ui.edits_from_df(df, df.copy()) == []


def test_edit_detected_for_changed_cell_only():
    _, state = paused_state()
    original = ui.figures_to_df(state)
    edited = original.copy()
    edited.loc[edited["figure"] == "revenue", "current"] = 1234.0
    assert ui.edits_from_df(original, edited) == [("current", "revenue", 1234.0)]


def test_clearing_a_cell_becomes_none():
    _, state = paused_state()
    original = ui.figures_to_df(state)
    edited = original.copy()
    edited.loc[edited["figure"] == "inventory", "prior"] = float("nan")
    assert ui.edits_from_df(original, edited) == [("prior", "inventory", None)]


def test_nan_to_nan_is_not_an_edit():
    _, state = paused_state(revenue=None)
    df = ui.figures_to_df(state)
    assert ui.edits_from_df(df, df.copy()) == []


def test_derived_table_sums_components():
    _, state = paused_state()
    d = ui.derived_df(ui.figures_to_df(state)).set_index("derived")
    assert d.loc["interest_expense", "current"] == 30   # |-20| is made positive in extraction, + 10
    assert d.loc["short_term_debt", "current"] == 50    # 30 + 20
    assert d.loc["total_debt", "current"] == 250        # 50 + 200


def test_derived_table_updates_with_edits():
    _, state = paused_state()
    df = ui.figures_to_df(state)
    df.loc[df["figure"] == "long_term_debt", "current"] = 1000.0
    d = ui.derived_df(df).set_index("derived")
    assert d.loc["total_debt", "current"] == 1050


def test_results_table_after_full_run():
    graph, _ = paused_state()
    for _ in graph.stream(None, THREAD):
        pass
    df = ui.results_df(graph.get_state(THREAD).values)
    assert len(df) == 8
    assert set(df.columns) == {"ratio", "current", "prior", "verdict", "rule"}
    assert df["verdict"].str.contains("🟢|🔴|⚪|➖").all()


def test_edited_count_counts_user_corrections():
    graph, _ = paused_state()
    agent.fix_figure(graph, THREAD, "current", "revenue", 1100)
    agent.fix_figure(graph, THREAD, "prior", "revenue", 900)
    assert ui.edited_count(graph.get_state(THREAD).values) == 2
