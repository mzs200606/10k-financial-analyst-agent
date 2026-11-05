"""Financial figures and ratio calculations. Pure Python, no LLM calls."""

# Figures we ask the LLM to extract. Everything is "as reported" in the filing's own units (ratios don't depend on units).
REQUIRED = ["revenue", "net_income", "total_assets", "equity",
            "current_assets", "current_liabilities", "operating_cash_flow"]
OPTIONAL = ["ebit", "interest_expense", "inventory", "receivables",
            "short_term_debt", "long_term_debt", "total_liabilities_and_equity"]
FIELDS = REQUIRED + OPTIONAL


def with_derived(f):
    """Copy a period's figures and add derived values. total_debt is summed HERE, not by the LLM."""
    f = dict(f)
    f["total_debt"] = (f.get("short_term_debt") or 0) + (f.get("long_term_debt") or 0)
    if f.get("inventory") is None:
        f["inventory"] = 0
    return f


def _positive(x, name):
    if x is None or x <= 0:
        raise ValueError(f"{name} is not positive")
    return x


RATIOS = {
    "current_ratio":     lambda f: (f["current_assets"] / f["current_liabilities"],
                                    f"current_assets {f['current_assets']} / current_liabilities {f['current_liabilities']}"),
    "quick_ratio":       lambda f: ((f["current_assets"] - f["inventory"]) / f["current_liabilities"],
                                    f"(current_assets {f['current_assets']} - inventory {f['inventory']}) / current_liabilities {f['current_liabilities']}"),
    "debt_to_equity":    lambda f: (f["total_debt"] / _positive(f["equity"], "equity"),
                                    f"total_debt {f['total_debt']} / equity {f['equity']}"),
    "interest_coverage": lambda f: (f["ebit"] / f["interest_expense"],
                                    f"ebit {f['ebit']} / interest_expense {f['interest_expense']}"),
    "net_margin":        lambda f: (f["net_income"] / f["revenue"] * 100,
                                    f"net_income {f['net_income']} / revenue {f['revenue']} (%)"),
    "roe":               lambda f: (f["net_income"] / _positive(f["equity"], "equity") * 100,
                                    f"net_income {f['net_income']} / equity {f['equity']} (%)"),
    "roa":               lambda f: (f["net_income"] / f["total_assets"] * 100,
                                    f"net_income {f['net_income']} / total_assets {f['total_assets']} (%)"),
    "ocf_to_net_income": lambda f: (f["operating_cash_flow"] / _positive(f["net_income"], "net_income"),
                                    f"operating_cash_flow {f['operating_cash_flow']} / net_income {f['net_income']}"),
}


def compute_ratio(name, f):
    """Returns {"value": float|None, "formula": str, "note": str|None}. Never raises."""
    try:
        value, formula = RATIOS[name](f)
        return {"value": round(value, 2), "formula": formula, "note": None}
    except ZeroDivisionError:
        return {"value": None, "formula": "", "note": "zero denominator (e.g. no interest expense)"}
    except ValueError as e:
        return {"value": None, "formula": "", "note": str(e)}
    except (TypeError, KeyError):
        return {"value": None, "formula": "", "note": "missing input"}


def compute_all_ratios(f):
    f = with_derived(f)
    return {name: compute_ratio(name, f) for name in RATIOS}
