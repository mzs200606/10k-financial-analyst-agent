from flags import growth, trend_flags

BASE = dict(revenue=1000, net_income=80, total_assets=900, equity=400,
            current_assets=300, current_liabilities=250, operating_cash_flow=120,
            ebit=150, interest_expense=30, inventory=100, receivables=90,
            short_term_debt=50, long_term_debt=200)


def test_growth_percentage():
    assert growth(110, 100) == 10


def test_growth_returns_none_for_zero_or_missing_prior():
    assert growth(110, 0) is None
    assert growth(110, None) is None
    assert growth(None, 100) is None


def test_receivables_outpacing_revenue_is_flagged():
    cur = {**BASE, "revenue": 1050, "receivables": 120}
    flags = trend_flags(cur, BASE)
    assert any("Receivables" in f for f in flags)


def test_similar_growth_is_not_flagged():
    cur = {**BASE, "revenue": 1100, "receivables": 99, "inventory": 110}
    assert trend_flags(cur, BASE) == []


def test_inventory_outpacing_revenue_is_flagged():
    cur = {**BASE, "revenue": 1050, "inventory": 140}
    flags = trend_flags(cur, BASE)
    assert any("Inventory" in f for f in flags)


def test_debt_up_and_coverage_down_is_flagged():
    cur = {**BASE, "long_term_debt": 400, "interest_expense": 60}
    flags = trend_flags(cur, BASE)
    assert any("Debt rose" in f for f in flags)
