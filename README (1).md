# 10-K Financial Analyst Agent

A LangGraph agent that reads a company's 10-K annual report (PDF), extracts the key financial figures, pauses for **human review**, computes financial ratios in plain Python, flags red flags, and writes a short due-diligence memo.

Built with **LangGraph** and **Google Gemini**. Runs in Google Colab.

> **Design principle:** the LLM only *reads* the filing and *writes* the memo. All math (ratios, trends, verdicts) is done in deterministic Python code, so no number in the memo is calculated by the model.

---

## What it does

1. **Upload**: sends the 10-K PDF to the Gemini Files API.
2. **Extract**: Gemini pulls 13 line items (revenue, net income, total assets, equity, current assets/liabilities, operating cash flow, EBIT, interest expense, inventory, receivables, short/long-term debt, total liabilities and equity) for the current and prior fiscal year, with the **page number** where each figure was found.
3. **Validate**: code checks the figures for problems: missing required values, balance sheet not balancing, current assets greater than total assets, revenue jumping more than 5x year over year, negative debt, and bank/insurer detection.
4. **Human review (checkpoint)**: the graph pauses. You see a table of every figure with its source page, then approve it or edit any value before continuing.
5. **Compute ratios**: current ratio, quick ratio, debt-to-equity, interest coverage, net margin, ROE, ROA, and OCF-to-net-income, for both years.
6. **Assess**: each ratio is rated 🟢 GREEN / ⚪ NEUTRAL / 🔴 RED against sector-specific thresholds (`general`, `retail`, `tech`, `utilities_energy`). Trend red flags are also checked (receivables or inventory growing faster than revenue, debt rising while interest coverage falls, weak cash conversion, negative equity).
7. **Memo**: Gemini streams a ~400-word memo (snapshot, healthy items, concerns, questions for management, limitations). It gives no buy/sell/hold recommendation.

## Workflow

```
upload_10k → extract_figures → validate ──(blocker?)──► END
                                   │
                                   ▼
                         ⏸ HUMAN REVIEW (approve / edit figures)
                                   │
                                   ▼
                      compute_ratios → assess → write_memo → END
```

## LangGraph features used

| Feature | Where |
|---|---|
| `StateGraph` with typed state | Whole pipeline |
| Conditional edges | Stops the run if validation finds a blocking issue |
| `interrupt_before` (human-in-the-loop) | Pauses before `compute_ratios` for figure review |
| `update_state(..., as_node=...)` | Applies human corrections and re-runs validation |
| `SqliteSaver` checkpointing | Saves every run so it can be resumed later |
| Time travel (`get_state_history`) | Re-scores the same figures under a different sector without re-uploading or re-extracting |
| Streaming | Memo prints token by token |

## Sample output (Walmart FY2025 10-K)

```
ratio                  current     prior   verdict   rule
current_ratio             0.82      0.83   🔴 RED      higher is better; green 1.5, red 1.0
quick_ratio               0.24      0.24   🔴 RED      higher is better; green 1.0, red 0.7
debt_to_equity            0.37      0.43   🟢 GREEN    lower is better; green 1.0, red 2.0
interest_coverage            —         —   ➖ N/A      (missing input)
net_margin                2.85      2.39   ⚪ NEUTRAL  higher is better; green 10.0, red 2.0
roe                      21.36      18.5   🟢 GREEN    higher is better; green 15.0, red 5.0
roa                       7.45      6.15   🟢 GREEN    higher is better; green 5.0, red 1.0
ocf_to_net_income         1.88       2.3   🟢 GREEN    higher is better; green 1.0, red 0.7

Red flags:
  🚩 Receivables grew 13.4% vs revenue 5.1% (possible aggressive revenue recognition or collection problems).
```

The full notebook output also includes the generated memo.

## How to run

1. Open `10_K_Financial_Analyst_Agent.ipynb` in Google Colab.
2. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/).
3. In Colab, open the **🔑 Secrets** tab (left sidebar), add a secret named `GEMINI_API_KEY`, and turn on notebook access.
4. Run the cells in order. When prompted, upload a 10-K PDF.
5. Set `SECTOR` (`general`, `retail`, `tech`, or `utilities_energy`) and a unique `THREAD_ID` for each filing.
6. At the review step, type `y` to approve, `e` to edit a figure, or `q` to quit.

Checkpoints are saved to Google Drive (`dd_agent/dd_checkpoints.db`) when running in Colab, or to the local folder otherwise.

## Tech stack

Python · LangGraph · langgraph-checkpoint-sqlite · Google Gemini (`google-genai`) · SQLite · Google Colab

## Known limitations

- **Non-financial companies only.** Banks and insurers are detected and blocked, because ratios like current ratio and debt-to-equity are not meaningful for them.
- **Interest coverage can come back N/A** when the filing doesn't disclose interest expense as a separate line item (as seen in the Walmart sample).
- **Thresholds are generic rules of thumb**, not industry-calibrated benchmarks.
- **Extraction depends on the LLM reading the PDF correctly.** That is why the human review step and page references exist. Always check the figures before approving.
- **Not investment advice.** This is a learning and screening tool.

## Roadmap

- [ ] Support multiple filings and multi-year trends
- [ ] Pull filings directly from SEC EDGAR
- [ ] Add more ratios and more sector profiles
- [ ] Export the memo to PDF or Word
- [ ] Add automated tests for the ratio and validation logic

## Author

**Zaneeq** · AI Data Specialist · Islamabad, Pakistan
