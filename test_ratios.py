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


# --- derived interest expense and short-term debt (step 4) ---

def test_interest_expense_summed_from_components_when_no_total_line():
    f = {**FIGS, "interest_expense": None, "interest_on_debt": 2000, "interest_on_finance_leases": 250}
    assert with_derived(f)["interest_expense"] == 2250


def test_direct_interest_expense_wins_over_components():
    f = {**FIGS, "interest_expense": 30, "interest_on_debt": 2000, "interest_on_finance_leases": 250}
    assert with_derived(f)["interest_expense"] == 30


def test_one_interest_component_is_enough():
    f = {**FIGS, "interest_expense": None, "interest_on_debt": 2000}
    assert with_derived(f)["interest_expense"] == 2000


def test_no_interest_data_stays_missing_not_zero():
    f = {**FIGS, "interest_expense": None}
    assert with_derived(f)["interest_expense"] is None
    assert compute_ratio("interest_coverage", with_derived(f))["note"] == "missing input"


def test_interest_coverage_works_from_components():
    f = {**FIGS, "interest_expense": None, "interest_on_debt": 20, "interest_on_finance_leases": 10}
    assert compute_ratio("interest_coverage", with_derived(f))["value"] == 5.0


def test_short_term_debt_summed_from_components():
    f = {k: v for k, v in FIGS.items() if k != "short_term_debt"}
    f.update(short_term_borrowings=3000, current_portion_long_term_debt=2500, long_term_debt=30000)
    d = with_derived(f)
    assert d["short_term_debt"] == 5500
    assert d["total_debt"] == 35500


def test_only_one_short_term_component_still_counts():
    f = {k: v for k, v in FIGS.items() if k != "short_term_debt"}
    f.update(short_term_borrowings=None, current_portion_long_term_debt=2500, long_term_debt=100)
    assert with_derived(f)["total_debt"] == 2600
