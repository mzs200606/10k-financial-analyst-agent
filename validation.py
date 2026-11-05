"""Sanity checks on extracted figures. Issues starting with BLOCKER stop the pipeline."""
from ratios import REQUIRED


def validate_figures(figures, meta):
    issues = []
    cur, pri = figures["current"], figures["prior"]

    if meta.get("is_financial_institution"):
        issues.append("BLOCKER: company looks like a bank/insurer. Current ratio, D/E etc. are not meaningful for these. v1 supports non-financial companies only.")

    for k in REQUIRED:
        if cur.get(k) is None:
            issues.append(f"BLOCKER: current-year '{k}' is missing (fix it with fix_figure).")
        if pri.get(k) is None:
            issues.append(f"WARNING: prior-year '{k}' is missing, so trend checks that need it are skipped.")

    if cur.get("revenue") is not None and cur["revenue"] <= 0:
        issues.append("BLOCKER: current revenue is not positive.")

    ta, tle = cur.get("total_assets"), cur.get("total_liabilities_and_equity")
    if ta and tle and abs(ta - tle) / ta > 0.005:
        issues.append(f"WARNING: total_assets {ta} != total_liabilities_and_equity {tle}. One may be from the wrong column or page.")

    ca = cur.get("current_assets")
    if ca is not None:
        if (cur.get("inventory") or 0) + (cur.get("receivables") or 0) > ca:
            issues.append("WARNING: inventory + receivables exceed current_assets.")
        if cur.get("total_assets") is not None and ca > cur["total_assets"]:
            issues.append("WARNING: current_assets exceed total_assets.")

    r_c, r_p = cur.get("revenue"), pri.get("revenue")
    if r_c and r_p and not (0.2 <= r_c / r_p <= 5):
        issues.append(f"WARNING: revenue changed by a factor of {r_c / r_p:.2f}x year over year. Possible wrong column.")

    for k in ["inventory", "receivables", "short_term_debt", "long_term_debt", "current_liabilities", "interest_expense"]:
        if cur.get(k) is not None and cur[k] < 0:
            issues.append(f"WARNING: current-year '{k}' is negative.")
    return issues
