from validation import validate_figures

GOOD = dict(revenue=1000, net_income=80, total_assets=900, equity=400,
            current_assets=300, current_liabilities=250, operating_cash_flow=120,
            inventory=100, receivables=90, total_liabilities_and_equity=900)


def run(cur=None, pri=None, meta=None):
    return validate_figures({"current": {**GOOD, **(cur or {})},
                             "prior": {**GOOD, **(pri or {})}}, meta or {})


def test_clean_data_has_no_issues():
    assert run() == []


def test_missing_required_current_figure_is_blocker():
    issues = run(cur={"revenue": None})
    assert any(i.startswith("BLOCKER") and "revenue" in i for i in issues)


def test_missing_prior_figure_is_only_warning():
    issues = run(pri={"revenue": None})
    assert any(i.startswith("WARNING") and "prior-year" in i for i in issues)
    assert not any(i.startswith("BLOCKER") for i in issues)


def test_financial_institution_is_blocked():
    issues = run(meta={"is_financial_institution": True})
    assert any(i.startswith("BLOCKER") and "bank" in i for i in issues)


def test_non_positive_revenue_is_blocker():
    issues = run(cur={"revenue": 0})
    assert any(i.startswith("BLOCKER") and "revenue" in i for i in issues)


def test_balance_sheet_mismatch_warns():
    issues = run(cur={"total_liabilities_and_equity": 1500})
    assert any("total_liabilities_and_equity" in i for i in issues)


def test_current_assets_above_total_assets_warns():
    issues = run(cur={"current_assets": 5000})
    assert any("exceed total_assets" in i for i in issues)


def test_revenue_jump_over_5x_warns():
    issues = run(cur={"revenue": 100000})
    assert any("factor" in i for i in issues)


def test_negative_debt_warns():
    issues = run(cur={"long_term_debt": -5})
    assert any("long_term_debt" in i and "negative" in i for i in issues)


def test_negative_interest_component_warns():
    issues = run(cur={"interest_on_debt": -5})
    assert any("interest_on_debt" in i and "negative" in i for i in issues)
