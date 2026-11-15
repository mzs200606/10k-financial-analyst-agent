"""Pure functions that turn agent state into tables for the UI. No Streamlit code here, so they are easy to test."""
import math

import pandas as pd

from ratios import FIELDS, with_derived

ICON = {"GREEN": "🟢", "RED": "🔴", "NEUTRAL": "⚪", "N/A": "➖"}
DERIVED = ("interest_expense", "short_term_debt", "total_debt")


def _clean(x):
    """NaN / None -> None, everything else -> float."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return float(x)


def figures_to_df(state):
    """One row per extracted figure: current value, prior value and the page each came from."""
    figs, pages = state["figures"], state["pages"]
    return pd.DataFrame({
        "figure": FIELDS,
        "current": pd.Series([figs["current"].get(k) for k in FIELDS], dtype="float64"),
        "prior": pd.Series([figs["prior"].get(k) for k in FIELDS], dtype="float64"),
        "page (current)": [None if pages["current"].get(k) is None else str(pages["current"][k]) for k in FIELDS],
        "page (prior)": [None if pages["prior"].get(k) is None else str(pages["prior"][k]) for k in FIELDS],
    })


def edits_from_df(original, edited):
    """Compare the table before and after the user's edits. Returns [(period, figure, new_value_or_None), ...]."""
    edits = []
    for i in range(len(original)):
        key = original.at[i, "figure"]
        for period in ("current", "prior"):
            old, new = _clean(original.at[i, period]), _clean(edited.at[i, period])
            if old != new:
                edits.append((period, key, new))
    return edits


def derived_df(df):
    """Values the code adds up itself (interest, short-term debt, total debt), computed from the table as shown."""
    out = {}
    for period in ("current", "prior"):
        figs = {row["figure"]: _clean(row[period]) for _, row in df.iterrows()}
        d = with_derived(figs)
        out[period] = [d[k] for k in DERIVED]
    return pd.DataFrame({"derived": list(DERIVED),
                         "current": pd.Series(out["current"], dtype="float64"),
                         "prior": pd.Series(out["prior"], dtype="float64")})


def results_df(state):
    """The ratio table: value, prior value, coloured verdict and the rule behind it."""
    rows = []
    for name, v in state["verdicts"].items():
        rule = v["rule"] + (f" ({v['note']})" if v["note"] else "")
        rows.append({"ratio": name, "current": v["value"], "prior": v["prior_value"],
                     "verdict": f"{ICON[v['verdict']]} {v['verdict']}", "rule": rule})
    df = pd.DataFrame(rows)
    df["current"] = df["current"].astype("float64")
    df["prior"] = df["prior"].astype("float64")
    return df


def edited_count(state):
    """How many figures the user corrected by hand (the agent marks their page as 'edited')."""
    return sum(1 for period in ("current", "prior") for p in state["pages"][period].values() if p == "edited")
