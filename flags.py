"""Trend red flags comparing the current year with the prior year."""
from ratios import with_derived, compute_ratio

# A flag fires only if the gap is bigger than this many percentage points (cuts noise).
TREND_TOLERANCE_PP = 5.0


def growth(cur, pri):
    if cur is None or pri in (None, 0):
        return None
    return (cur - pri) / abs(pri) * 100


def trend_flags(cur, pri):
    cur, pri = with_derived(cur), with_derived(pri)
    flags = []
    rev_g = growth(cur.get("revenue"), pri.get("revenue"))

    rec_g = growth(cur.get("receivables"), pri.get("receivables"))
    if rev_g is not None and rec_g is not None and rec_g - rev_g > TREND_TOLERANCE_PP:
        flags.append(f"Receivables grew {rec_g:.1f}% vs revenue {rev_g:.1f}% (possible aggressive revenue recognition or collection problems).")

    inv_g = growth(cur.get("inventory") or None, pri.get("inventory") or None)
    if rev_g is not None and inv_g is not None and inv_g - rev_g > TREND_TOLERANCE_PP:
        flags.append(f"Inventory grew {inv_g:.1f}% vs revenue {rev_g:.1f}% (possible demand weakness or obsolescence risk).")

    cov_c = compute_ratio("interest_coverage", cur)["value"]
    cov_p = compute_ratio("interest_coverage", pri)["value"]
    if cur["total_debt"] > pri["total_debt"] and cov_c is not None and cov_p is not None and cov_c < cov_p:
        flags.append(f"Debt rose ({pri['total_debt']:,.0f} -> {cur['total_debt']:,.0f}) while interest coverage fell ({cov_p} -> {cov_c}).")
    return flags
