"""Streamlit UI for the 10-K Financial Analyst Agent.  Run with:  streamlit run app.py"""
import os
import tempfile
import uuid

import streamlit as st

import agent
import ui_helpers as ui
from thresholds import SECTORS

DB_PATH = "dd_checkpoints.db"

st.set_page_config(page_title="10-K Financial Analyst Agent", page_icon="📊", layout="wide")
st.title("📊 10-K Financial Analyst Agent")
st.caption("Gemini reads the filing, you review the figures, and plain Python computes every ratio. "
           "No number in the memo is calculated by the model. Not investment advice.")

ss = st.session_state
ss.setdefault("stage", "input")
ss.setdefault("version", 0)


def default_key():
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    try:
        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return None


with st.sidebar:
    st.header("Settings")
    typed_key = st.text_input("Gemini API key", type="password",
                              help="Get one free at aistudio.google.com. It is used only for your session and is never saved.")
    api_key = typed_key or default_key()
    if not typed_key and api_key:
        st.caption("Using the key found in your environment.")
    st.markdown("---")
    st.caption("Steps: 1) upload  2) review the extracted figures  3) approve  4) read the results")


def thread_id():
    return ss.thread["configurable"]["thread_id"]


def get_state():
    return ss.graph.get_state(ss.thread)


def start_run(uploaded, sector, key):
    holder = {"fn": lambda token: None}
    client = agent.make_client(key)
    graph = agent.build_graph(client, agent.DEFAULT_MODEL, DB_PATH, on_token=lambda t: holder["fn"](t))
    thread = {"configurable": {"thread_id": uuid.uuid4().hex[:10]}}
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(uploaded.getvalue())
        path = f.name
    try:
        with st.spinner("Reading the filing with Gemini (this can take 30-90 seconds)..."):
            for _ in graph.stream({"pdf_path": path, "sector": sector}, thread):
                pass
    except Exception as e:
        st.error(f"Something went wrong: {type(e).__name__}: {e}")
        return
    finally:
        os.remove(path)
    ss.update(graph=graph, thread=thread, holder=holder, stage="review", version=0)
    st.rerun()


def reset():
    for k in ("graph", "thread", "holder"):
        ss.pop(k, None)
    ss.stage = "input"


# ------------------------------------------------------------------ stage 1: upload
if ss.stage == "input":
    uploaded = st.file_uploader("10-K annual report (PDF)", type="pdf")
    sector = st.selectbox("Sector rules", SECTORS,
                          help="Thresholds differ by sector, e.g. a retailer normally runs a lower current ratio than a software company.")
    if not api_key:
        st.info("Paste your Gemini API key in the sidebar to begin.")
    if st.button("Run analysis", type="primary", disabled=not (uploaded and api_key)):
        start_run(uploaded, sector, api_key)

# ------------------------------------------------------------------ stage 2: human review
elif ss.stage == "review":
    state = get_state().values
    st.subheader(f"{state['company']}: {state['fy_current']} vs {state['fy_prior']}")
    st.caption(f"Units: {state['units']} ({state['currency']}). Check each figure against the page shown, "
               "fix anything wrong in the Current / Prior columns, then approve.")

    blockers = [i for i in state["issues"] if i.startswith("BLOCKER")]
    for issue in state["issues"]:
        (st.error if issue.startswith("BLOCKER") else st.warning)(issue)

    original = ui.figures_to_df(state)
    edited = st.data_editor(
        original, hide_index=True, use_container_width=True,
        disabled=["figure", "page (current)", "page (prior)"],
        key=f"editor_{thread_id()}_{ss.version}",
    )
    edits = ui.edits_from_df(original, edited)

    st.markdown("**Derived by code** (updates as you edit)")
    st.dataframe(ui.derived_df(edited), hide_index=True, use_container_width=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    if col1.button("Apply edits & re-check", disabled=not edits):
        for period, key, value in edits:
            agent.fix_figure(ss.graph, ss.thread, period, key, value)
        ss.version += 1
        st.rerun()
    if col2.button("Approve & continue", type="primary", disabled=bool(blockers) or bool(edits)):
        placeholder, buf = st.empty(), []

        def show_token(token):
            buf.append(token)
            placeholder.markdown("".join(buf).replace("$", "\\$"))

        ss.holder["fn"] = show_token
        try:
            with st.spinner("Computing ratios and writing the memo..."):
                for _ in ss.graph.stream(None, ss.thread):
                    pass
        except Exception as e:
            st.error(f"Something went wrong: {type(e).__name__}: {e}")
        else:
            ss.stage = "done"
            st.rerun()
    if col3.button("Start over"):
        reset()
        st.rerun()
    if edits:
        st.caption("You have unapplied edits. Click 'Apply edits & re-check' first.")
    elif blockers:
        st.caption("Fix the BLOCKER items above to enable approval.")

# ------------------------------------------------------------------ stage 3: results
elif ss.stage == "done":
    state = get_state().values
    st.subheader(f"{state['company']}: {state['fy_current']} vs {state['fy_prior']}")
    n = ui.edited_count(state)
    if n:
        st.caption(f"✏️ {n} figure(s) were corrected by you during review.")

    st.dataframe(ui.results_df(state), hide_index=True, use_container_width=True)

    if state["flags"]:
        for flag in state["flags"]:
            st.warning(f"🚩 {flag}")
    else:
        st.success("No trend red flags.")

    st.markdown("### Memo")
    st.markdown(state["memo"].replace("$", "\\$"))
    st.download_button("Download memo (.md)", data=state["memo"],
                       file_name=f"{state['company']}_{state['fy_current']}_memo.md".replace(" ", "_"))
    if st.button("Analyze another filing"):
        reset()
        st.rerun()
