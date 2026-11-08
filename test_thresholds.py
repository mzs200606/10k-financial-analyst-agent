from thresholds import THRESHOLDS, SECTORS, classify


def test_higher_is_better_green():
    assert classify(2.0, ("higher", 1.5, 1.0)) == "GREEN"


def test_higher_is_better_neutral():
    assert classify(1.2, ("higher", 1.5, 1.0)) == "NEUTRAL"


def test_higher_is_better_red():
    assert classify(0.5, ("higher", 1.5, 1.0)) == "RED"


def test_lower_is_better_green_and_red():
    rule = ("lower", 1.0, 2.0)
    assert classify(0.5, rule) == "GREEN"
    assert classify(3.0, rule) == "RED"


def test_boundary_values_count_as_green():
    assert classify(1.5, ("higher", 1.5, 1.0)) == "GREEN"
    assert classify(1.0, ("lower", 1.0, 2.0)) == "GREEN"


def test_none_value_is_na():
    assert classify(None, ("higher", 1.5, 1.0)) == "N/A"


def test_same_value_gets_different_verdict_by_sector():
    value = 1.2
    assert classify(value, THRESHOLDS["retail"]["current_ratio"]) == "GREEN"
    assert classify(value, THRESHOLDS["tech"]["current_ratio"]) == "NEUTRAL"


def test_every_sector_defines_the_same_ratios():
    names = set(THRESHOLDS["general"])
    for sector in SECTORS:
        assert set(THRESHOLDS[sector]) == names
