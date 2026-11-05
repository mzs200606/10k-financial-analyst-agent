"""Sector-specific thresholds and the GREEN / NEUTRAL / RED classifier."""

# rule = (direction, green_threshold, red_threshold)
THRESHOLDS = {
    "general": {
        "current_ratio":     ("higher", 1.5, 1.0),
        "quick_ratio":       ("higher", 1.0, 0.7),
        "debt_to_equity":    ("lower",  1.0, 2.0),
        "interest_coverage": ("higher", 5.0, 2.0),
        "net_margin":        ("higher", 10.0, 2.0),
        "roe":               ("higher", 15.0, 5.0),
        "roa":               ("higher", 5.0, 1.0),
        "ocf_to_net_income": ("higher", 1.0, 0.7),
    },
    "retail": {
        "current_ratio":     ("higher", 1.2, 0.9),
        "quick_ratio":       ("higher", 0.5, 0.3),
        "debt_to_equity":    ("lower",  1.0, 2.0),
        "interest_coverage": ("higher", 5.0, 2.0),
        "net_margin":        ("higher", 4.0, 1.0),
        "roe":               ("higher", 15.0, 5.0),
        "roa":               ("higher", 5.0, 1.5),
        "ocf_to_net_income": ("higher", 1.0, 0.7),
    },
    "tech": {
        "current_ratio":     ("higher", 2.0, 1.2),
        "quick_ratio":       ("higher", 1.5, 1.0),
        "debt_to_equity":    ("lower",  0.5, 1.5),
        "interest_coverage": ("higher", 10.0, 4.0),
        "net_margin":        ("higher", 15.0, 5.0),
        "roe":               ("higher", 15.0, 5.0),
        "roa":               ("higher", 8.0, 2.0),
        "ocf_to_net_income": ("higher", 1.0, 0.7),
    },
    "utilities_energy": {
        "current_ratio":     ("higher", 1.0, 0.7),
        "quick_ratio":       ("higher", 0.7, 0.4),
        "debt_to_equity":    ("lower",  1.5, 3.0),
        "interest_coverage": ("higher", 3.5, 1.8),
        "net_margin":        ("higher", 8.0, 2.0),
        "roe":               ("higher", 10.0, 4.0),
        "roa":               ("higher", 3.0, 1.0),
        "ocf_to_net_income": ("higher", 1.0, 0.7),
    },
}
SECTORS = list(THRESHOLDS)


def classify(value, rule):
    if value is None:
        return "N/A"
    direction, green, red = rule
    if direction == "higher":
        return "GREEN" if value >= green else ("RED" if value < red else "NEUTRAL")
    return "GREEN" if value <= green else ("RED" if value > red else "NEUTRAL")
