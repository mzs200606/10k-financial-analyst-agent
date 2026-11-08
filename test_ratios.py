from ratios import compute_ratio, compute_all_ratios, with_derived

FIGS = dict(revenue=1000, net_income=80, total_assets=900, equity=400,
            current_assets=300, current_liabilities=250, operating_cash_flow=120,
            ebit=150, interest_expense=30, inventory=100, receivables=90,
            short_term_debt=50, long_term_debt=200)


def test_current_ratio():
    assert compute_ratio("current_ratio", with_derived(FIGS))["value"] == 1.2


def test_quick_ratio_excludes_inventory():
    assert compute_ratio("quick_ratio", with_derived(FIGS))["value"] == 0.8


def test_total_debt_is_sum_of_short_and_long_term():
    assert with_derived(FIGS)["total_debt"] == 250


def test_missing_inventory_defaults_to_zero():
    f = {**FIGS, "inventory": None}
    assert with_derived(f)["inventory"] == 0


def test_zero_denominator_returns_none_not_crash():
    f = {**FIGS, "current_liabilities": 0}
    result = compute_ratio("current_ratio", with_derived(f))
    assert result["value"] is None
    assert "zero denominator" in result["note"]


def test_negative_equity_makes_roe_none():
    f = {**FIGS, "equity": -100}
    result = compute_ratio("roe", with_derived(f))
    assert result["value"] is None


def test_missing_input_returns_none():
    f = {**FIGS, "ebit": None}
    result = compute_ratio("interest_coverage", with_derived(f))
    assert result["value"] is None
    assert result["note"] == "missing input"


def test_compute_all_ratios_returns_all_eight():
    assert len(compute_all_ratios(FIGS)) == 8
