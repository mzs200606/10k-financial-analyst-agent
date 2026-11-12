"""Financial figures and ratio calculations. Pure Python, no LLM calls."""

# Figures we ask the LLM to extract. Everything is "as reported" in the filing's own units (ratios don't depend on units).
REQUIRED = ["revenue", "net_income", "total_assets", "equity",
            "current_assets", "current_liabilities", "operating_cash_flow"]
OPTIONAL = ["ebit", "interest_expense", "interest_on_debt", "interest_on_finance_leases",
            "inventory", "receivables", "short_term_borrowings", "current_portion_long_term_debt",
            "long_term_debt", "total_liabilities_and_equity"]
FIELDS = REQUIRED + OPTIONAL


def _sum_or_none(*values):
    """Sum the values that exist. If none exist, return None (so 'missing' stays 'missing', not 0)."""
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def with_derived(f):
    """Copy a period's figures and add derived values. All additions happen HERE, never in the LLM.

    - interest_expense: the single total line if the filing has one, else interest on debt + on finance leases.
    - short_term_debt: short-term borrowings + current portion of long-term debt (unless given directly).
    - total_debt: short_term_debt + long_term_debt.
    """
    f = dict(f)
    if f.get("interest_expense") is None:
        f["interest_expense"] = _sum_or_none(f.get("interest_on_debt"), f.get("interest_on_finance_leases"))
    if f.get("short_term_debt") is None:
        f["short_term_debt"] = _sum_or_none(f.get("short_term_borrowings"), f.get("current_portion_long_term_debt"))
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
