"""The 10-K due-diligence agent: prompts, Gemini helpers, LangGraph nodes and the graph builder.

No UI code lives here, so the same agent runs from the notebook, a Streamlit app, or the tests.
The LLM only reads the filing and writes the memo. All math lives in ratios.py, thresholds.py, validation.py, flags.py.
"""
import json
import re
import sqlite3
import time
from typing import TypedDict

from google.genai import types
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from flags import trend_flags
from ratios import FIELDS, compute_all_ratios
from thresholds import THRESHOLDS, classify
from validation import validate_figures

DEFAULT_MODEL = "gemini-3.6-flash"


# ---------------------------------------------------------------- Gemini helpers
def with_retry(fn, tries=5, wait=4):
    """Gemini occasionally returns 429/503. Retry with growing waits (4s, 8s, 16s, 32s) before giving up."""
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:
            if attempt == tries - 1:
                raise
            delay = wait * 2 ** attempt
            print(f"  (Gemini error: {type(e).__name__}. Retrying in {delay}s...)")
            time.sleep(delay)


def upload_pdf_to_gemini(client, pdf_path):
    """Upload to the Gemini Files API and wait until it is ready. Returns the file object."""
    f = with_retry(lambda: client.files.upload(file=pdf_path))
    while getattr(getattr(f, "state", None), "name", "ACTIVE") == "PROCESSING":
        time.sleep(2)
        f = client.files.get(name=f.name)
    if getattr(getattr(f, "state", None), "name", "ACTIVE") == "FAILED":
        raise RuntimeError("Gemini could not process this PDF.")
    return f


EXTRACTION_PROMPT = """
You are extracting data from a company's 10-K annual report. Use the CONSOLIDATED financial statements (Item 8).
Return ONLY a JSON object, no commentary, with exactly this structure:

{
  "company_name": string,
  "units": "units" | "thousands" | "millions" | "billions",   // the unit the statements are presented in
  "currency": string,
  "fiscal_year_current": string,   // e.g. "FY2025 (ended 2025-12-31)"
  "fiscal_year_prior": string,
  "is_financial_institution": boolean,   // true for banks, insurers, broker-dealers
  "figures": {
    "current": { "<field>": {"value": number or null, "page": integer or null}, ... },
    "prior":   { "<field>": {"value": number or null, "page": integer or null}, ... }
  }
}

"current" = the most recent fiscal year column. "prior" = the immediately preceding fiscal year column.
Each <field> must be one of these, with these exact meanings:
- revenue: total net sales / total revenues
- net_income: net income attributable to the company's shareholders
- ebit: operating income (income from operations). null if not reported.
- interest_expense: ONLY if the filing shows a single total interest expense line. Positive number, gross (NOT net of interest income). Otherwise null.
- interest_on_debt: ONLY if interest is shown in separate lines (e.g. "Interest: Debt", "Finance lease"). Interest on debt/borrowings, positive number. Do NOT use "interest, net" or interest income. Otherwise null.
- interest_on_finance_leases: ONLY if interest is shown in separate lines. The finance lease interest line, positive number. null if none or if interest_expense is filled.
- total_assets
- total_liabilities_and_equity: the balance sheet total of liabilities and equity
- equity: total shareholders' equity attributable to the company (exclude noncontrolling interests)
- current_assets
- current_liabilities
- inventory: null if the company reports no inventory
- receivables: accounts receivable, net (trade receivables)
- short_term_borrowings: short-term borrowings / notes payable / commercial paper in current liabilities. Exclude all lease liabilities. null if none.
- current_portion_long_term_debt: "long-term debt due within one year" / current maturities of long-term debt. Exclude all lease liabilities. null if none.
- long_term_debt: non-current debt. Exclude all lease liabilities. null if none.
- operating_cash_flow: net cash provided by (used in) operating activities

Rules:
- Numbers exactly as printed, in the statements' own units, no commas or currency symbols. Negatives as negative numbers.
- Do NOT add, subtract, or compute anything. Copy single line items only.
- "page" is the page number where you found the figure (approximate is fine).
- If a line item does not exist, use {"value": null, "page": null}. Never guess.
""".strip()


def to_number(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", "").replace("$", "")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def gemini_extract(client, model_id, file_uri, mime_type):
    """Ask Gemini for structured figures. Returns the parsed JSON dict."""
    part = types.Part.from_uri(file_uri=file_uri, mime_type=mime_type)
    response = with_retry(lambda: client.models.generate_content(
        model=model_id,
        contents=[part, EXTRACTION_PROMPT],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
    ))
    raw = (response.text or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("Could not parse Gemini output as JSON. Raw output:\n", raw[:2000])
        raise


MEMO_PROMPT = """
You are a financial analyst writing a short due-diligence memo for a human reader.
Use ONLY the numbers in the JSON below. Do not compute new numbers and do not use outside knowledge about the company.
Do NOT give a buy/sell/hold recommendation.

Write (max ~400 words) with these headings:
1. Snapshot (company, period, sector rules applied)
2. What looks healthy (GREEN items)
3. What looks off (RED items and red flags, with the numbers)
4. Questions to ask management (3-5, tied to the flags)
5. Limitations (mention that thresholds are generic rules of thumb for the sector, figures were extracted from the PDF and reviewed by a human, and list any validation WARNINGS)

DATA:
""".strip()


def print_token(token):
    print(token, end="", flush=True)


def gemini_stream_memo(client, model_id, payload, on_token=print_token):
    """Streams the memo token by token to on_token (default: print) and returns the full text."""
    prompt = MEMO_PROMPT + "\n" + json.dumps(payload, indent=2)
    parts = []
    stream = with_retry(lambda: client.models.generate_content_stream(
        model=model_id, contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2),
    ))
    for chunk in stream:
        if chunk.text:
            on_token(chunk.text)
            parts.append(chunk.text)
    return "".join(parts)


# ---------------------------------------------------------------- graph state and nodes
class DDState(TypedDict):
    pdf_path: str
    sector: str
    file_name: str
    file_uri: str
    mime_type: str
    company: str
    units: str
    currency: str
    fy_current: str
    fy_prior: str
    is_financial_institution: bool
    figures: dict
    pages: dict
    issues: list
    ratios: dict
    verdicts: dict
    flags: list
    memo: str


def validate(state: DDState):
    return {"issues": validate_figures(state["figures"], state)}


def route_after_validate(state: DDState):
    return "blocked" if any(i.startswith("BLOCKER") for i in state["issues"]) else "compute_ratios"


def compute_ratios(state: DDState):
    return {"ratios": {
        "current": compute_all_ratios(state["figures"]["current"]),
        "prior":   compute_all_ratios(state["figures"]["prior"]),
    }}


def assess(state: DDState):
    rules = THRESHOLDS[state["sector"]]
    verdicts = {}
    for name, r in state["ratios"]["current"].items():
        verdicts[name] = {
            "value": r["value"],
            "prior_value": state["ratios"]["prior"][name]["value"],
            "verdict": classify(r["value"], rules[name]),
            "rule": f"{rules[name][0]} is better; green {rules[name][1]}, red {rules[name][2]}",
            "note": r["note"],
        }
    flags = trend_flags(state["figures"]["current"], state["figures"]["prior"])
    if verdicts["ocf_to_net_income"]["verdict"] == "RED":
        flags.append(f"Earnings quality: operating cash flow is only {verdicts['ocf_to_net_income']['value']}x net income.")
    eq = state["figures"]["current"].get("equity")
    if eq is not None and eq <= 0:
        flags.append("Shareholders' equity is zero or negative.")
    return {"verdicts": verdicts, "flags": flags}


def build_graph(client, model_id=DEFAULT_MODEL, db_path=":memory:", on_token=print_token):
    """Build and compile the agent. The graph pauses before compute_ratios so a human can review the figures.

    client:   a google.genai Client
    db_path:  SQLite file for checkpoints (":memory:" for throwaway runs and tests)
    on_token: called with each piece of the memo as it streams
    """

    def upload_10k(state: DDState):
        print(f"Uploading {state['pdf_path']} to Gemini...")
        f = upload_pdf_to_gemini(client, state["pdf_path"])
        return {"file_name": f.name, "file_uri": f.uri, "mime_type": f.mime_type}

    def extract_figures(state: DDState):
        print("Extracting figures with Gemini (can take 30-90s for a long 10-K)...")
        data = gemini_extract(client, model_id, state["file_uri"], state["mime_type"])
        figures, pages = {"current": {}, "prior": {}}, {"current": {}, "prior": {}}
        for period in ("current", "prior"):
            raw = (data.get("figures") or {}).get(period) or {}
            for k in FIELDS:
                cell = raw.get(k) or {}
                figures[period][k] = to_number(cell.get("value"))
                pages[period][k] = cell.get("page")
            for k in ("interest_expense", "interest_on_debt", "interest_on_finance_leases"):
                if figures[period][k] is not None:
                    figures[period][k] = abs(figures[period][k])
        return {
            "company": data.get("company_name", "Unknown"),
            "units": data.get("units", "unknown"),
            "currency": data.get("currency", ""),
            "fy_current": data.get("fiscal_year_current", ""),
            "fy_prior": data.get("fiscal_year_prior", ""),
            "is_financial_institution": bool(data.get("is_financial_institution", False)),
            "figures": figures,
            "pages": pages,
        }

    def write_memo(state: DDState):
        print("\n--- MEMO (streaming) ---\n")
        payload = {
            "company": state["company"], "period": state["fy_current"], "prior_period": state["fy_prior"],
            "units": state["units"], "currency": state["currency"], "sector_rules": state["sector"],
            "ratios": state["verdicts"], "red_flags": state["flags"],
            "validation_issues": state["issues"],
        }
        return {"memo": gemini_stream_memo(client, model_id, payload, on_token)}

    builder = StateGraph(DDState)
    builder.add_node("upload_10k", upload_10k)
    builder.add_node("extract_figures", extract_figures)
    builder.add_node("validate", validate)
    builder.add_node("compute_ratios", compute_ratios)
    builder.add_node("assess", assess)
    builder.add_node("write_memo", write_memo)

    builder.set_entry_point("upload_10k")
    builder.add_edge("upload_10k", "extract_figures")
    builder.add_edge("extract_figures", "validate")
    builder.add_conditional_edges("validate", route_after_validate,
                                  {"compute_ratios": "compute_ratios", "blocked": END})
    builder.add_edge("compute_ratios", "assess")
    builder.add_edge("assess", "write_memo")
    builder.add_edge("write_memo", END)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    return builder.compile(checkpointer=SqliteSaver(conn), interrupt_before=["compute_ratios"])


# ---------------------------------------------------------------- human review helper
def fix_figure(graph, thread, period, key, value):
    """Correct one figure, re-run validation, and write it back as if the 'validate' node produced it."""
    assert period in ("current", "prior") and key in FIELDS, f"period must be current/prior; key must be one of {FIELDS}"
    s = graph.get_state(thread).values
    figures = json.loads(json.dumps(s["figures"]))
    pages = json.loads(json.dumps(s["pages"]))
    figures[period][key] = None if value is None else float(value)
    pages[period][key] = "edited"
    issues = validate_figures(figures, s)
    graph.update_state(thread, {"figures": figures, "pages": pages, "issues": issues}, as_node="validate")
