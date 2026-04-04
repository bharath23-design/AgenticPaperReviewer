"""
Streamlit UI — Agentic Research Paper Evaluator
Run with: streamlit run app.py
"""

import os
import re

import requests
import streamlit as st
from dotenv import load_dotenv

from src.logger import get_logger

log = get_logger("app")

load_dotenv()

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agentic Paper Reviewer",
    page_icon="📄",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.verdict-pass     { color: #28a745; font-weight: bold; font-size: 1.3em; }
.verdict-cond     { color: #fd7e14; font-weight: bold; font-size: 1.3em; }
.verdict-fail     { color: #dc3545; font-weight: bold; font-size: 1.3em; }
.score-card       { background: #f8f9fa; border-radius: 8px; padding: 12px; margin: 4px; text-align: center; }
.step-complete    { color: #28a745; }
.step-running     { color: #007bff; }
</style>
""", unsafe_allow_html=True)


# ── Ollama health check ───────────────────────────────────────────────────────

def check_ollama(model: str) -> tuple[bool, str]:
    """
    Returns (ok, message).
    Checks that Ollama is reachable and that `model` is pulled.
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        return False, (
            f"Cannot reach Ollama at `{base_url}`. "
            "**Start Ollama** by opening the Ollama app or running `ollama serve` in a terminal."
        )
    except Exception as exc:
        return False, f"Ollama health check failed: {exc}"

    installed = {m["name"].split(":")[0] for m in resp.json().get("models", [])}
    installed_full = {m["name"] for m in resp.json().get("models", [])}
    model_base = model.split(":")[0]

    if model not in installed_full and model_base not in installed:
        return False, (
            f"Model **`{model}`** is not pulled yet. "
            f"Run `ollama pull {model}` in a terminal and try again."
        )

    return True, "OK"


def _friendly_error(raw: str) -> str:
    """Extract the human-readable root cause from a captured traceback string."""
    # Find the last 'Error:' or 'Exception:' line in the traceback
    lines = raw.strip().splitlines()

    # Connection refused → give an actionable message
    if "Connection refused" in raw or "ConnectError" in raw:
        return (
            "Ollama is not running or refused the connection.\n\n"
            "**Fix:** Open the Ollama app or run `ollama serve` in a terminal, then try again."
        )

    # Find last non-empty meaningful line
    for line in reversed(lines):
        line = line.strip()
        if line and not line.startswith("File ") and not line.startswith("^"):
            return line

    return lines[-1] if lines else raw


# ── Sidebar — configuration ──────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")
    st.markdown("---")

    model_name = st.selectbox(
        "Ollama Model",
        options=["llama3.2", "llama3.2:1b", "llama3.1:8b", "mistral", "gemma2:2b", "phi3"],
        index=0,
        help="Make sure the model is pulled: `ollama pull <model>`",
    )
    os.environ["OLLAMA_MODEL"] = model_name

    st.markdown("---")
    st.markdown("### How to use")
    st.markdown("""
1. Paste an **arXiv URL** (e.g. `https://arxiv.org/abs/2404.00001`)
2. Choose an **Ollama model**
3. Click **Analyze Paper**
4. Download the Markdown report
    """)

    st.markdown("---")
    st.markdown("### Prerequisites")
    st.code("pip install -r requirements.txt\nollama pull llama3.2", language="bash")


# ── Main area ─────────────────────────────────────────────────────────────────
st.title("📄 Agentic Research Paper Evaluator")
st.caption("Multi-agent peer-review simulation powered by LangGraph + Ollama")

col_url, col_btn = st.columns([5, 1])
with col_url:
    url = st.text_input(
        "arXiv Paper URL",
        placeholder="https://arxiv.org/abs/2404.00001",
        label_visibility="collapsed",
    )
with col_btn:
    analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)

st.markdown("---")

STEPS = [
    ("scrape",        "🌐 Scraping arXiv paper"),
    ("decompose",     "✂️  Decomposing sections"),
    ("consistency",   "🔍 Checking consistency"),
    ("grammar",       "✍️  Evaluating grammar"),
    ("novelty",       "💡 Assessing novelty"),
    ("fact_check",    "✅ Fact-checking claims"),
    ("authenticity",  "🔒 Scoring authenticity"),
    ("report",        "📝 Generating report"),
]

STEP_NAMES = {k: label for k, label in STEPS}


def _score_color(score: int) -> str:
    if score >= 70:
        return "green"
    if score >= 50:
        return "orange"
    return "red"


def render_results(state: dict):
    """Render the final review results in the Streamlit UI."""
    meta = state.get("paper_metadata", {})
    c    = state.get("consistency_result",  {})
    g    = state.get("grammar_result",      {})
    n    = state.get("novelty_result",      {})
    f    = state.get("fact_check_result",   {})
    a    = state.get("authenticity_result", {})

    # Paper info
    st.subheader(f"📰 {meta.get('title', 'Unknown Title')}")
    authors = ", ".join(meta.get("authors", [])[:4])
    st.caption(f"{authors} · {meta.get('published', '')} · {', '.join(meta.get('categories', []))}")

    st.markdown("---")

    # Overall verdict banner
    report = state.get("final_report", "")
    if "PASS" in report and "FAIL" not in report and "CONDITIONAL" not in report:
        verdict_label = "PASS"
        css_class = "verdict-pass"
    elif "CONDITIONAL PASS" in report:
        verdict_label = "CONDITIONAL PASS"
        css_class = "verdict-cond"
    else:
        verdict_label = "FAIL"
        css_class = "verdict-fail"

    st.markdown(
        f'<div class="{css_class}">Overall Verdict: {verdict_label}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    # Score cards
    fab_prob = a.get("fabrication_probability", 20)
    scores = {
        "Consistency":  c.get("score", 0),
        "Grammar":      g.get("grammar_score", 0),
        "Novelty":      n.get("novelty_score", 0),
        "Fact-Check":   f.get("fact_check_score", 0),
        "Integrity":    100 - fab_prob,
    }

    cols = st.columns(5)
    for col, (label, score) in zip(cols, scores.items()):
        col.metric(label=label, value=f"{score}/100")

    st.markdown("---")

    # Detailed tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 Consistency", "✍️ Grammar", "💡 Novelty", "✅ Fact-Check", "🔒 Authenticity"
    ])

    with tab1:
        st.metric("Score", f"{c.get('score', 'N/A')}/100")
        st.markdown(f"**Verdict:** `{c.get('verdict', 'N/A')}`")
        st.markdown(c.get("explanation", ""))
        if c.get("strengths"):
            st.markdown("**Strengths:**")
            for s in c["strengths"]:
                st.markdown(f"- {s}")
        if c.get("issues"):
            st.markdown("**Issues:**")
            for issue in c["issues"]:
                st.markdown(f"- ⚠️ {issue}")

    with tab2:
        col1, col2, col3 = st.columns(3)
        col1.metric("Grammar",  f"{g.get('grammar_score', 'N/A')}/100")
        col2.metric("Clarity",  f"{g.get('clarity_score', 'N/A')}/100")
        col3.metric("Tone",     f"{g.get('tone_score', 'N/A')}/100")
        st.markdown(f"**Rating:** `{g.get('rating', 'N/A')}`")
        st.markdown(g.get("explanation", ""))
        if g.get("issues"):
            st.markdown("**Language Issues:**")
            for issue in g["issues"]:
                st.markdown(f"- {issue}")

    with tab3:
        st.metric("Novelty Score", f"{n.get('novelty_score', 'N/A')}/100")
        st.markdown(f"**Novelty Index:** `{n.get('novelty_index', 'N/A')}`")
        st.markdown(n.get("explanation", ""))
        if n.get("key_differentiators"):
            st.markdown("**Key Differentiators:**")
            for d in n["key_differentiators"]:
                st.markdown(f"- {d}")
        related = n.get("related_papers_metadata", [])
        if related:
            st.markdown("**Related Papers:**")
            for p in related[:5]:
                st.markdown(
                    f"- [`{p.get('arxiv_id')}`] *{p.get('title')}* ({p.get('published')})"
                )

    with tab4:
        st.metric("Fact-Check Score", f"{f.get('fact_check_score', 'N/A')}/100")
        st.markdown(f"**Claims Examined:** {f.get('total_claims_checked', 0)}")
        st.markdown(f.get("summary", ""))

        verified     = f.get("verified_claims", [])
        questionable = f.get("questionable_claims", [])
        unverifiable = f.get("unverifiable_claims", [])

        if verified:
            st.markdown("**Verified Claims:**")
            for item in verified:
                st.markdown(f"- ✅ {item.get('claim', '')} — _{item.get('note', '')}_")
        if questionable:
            st.markdown("**Questionable Claims:**")
            for item in questionable:
                st.markdown(f"- ⚠️ {item.get('claim', '')} — _{item.get('note', '')}_")
        if unverifiable:
            st.markdown("**Unverifiable Claims:**")
            for item in unverifiable:
                st.markdown(f"- ❓ {item.get('claim', '')} — _{item.get('note', '')}_")

    with tab5:
        fab  = a.get("fabrication_probability", 0)
        repro = a.get("reproducibility_score", 0)
        col1, col2 = st.columns(2)
        col1.metric("Fabrication Risk", f"{fab}%")
        col2.metric("Reproducibility", f"{repro}/100")
        st.markdown(f"**Risk Level:** `{a.get('risk_level', 'N/A')}`")
        st.markdown(f"**Recommendation:** `{a.get('recommendation', 'N/A')}`")
        st.markdown(a.get("explanation", ""))
        if a.get("red_flags"):
            st.markdown("**Red Flags:**")
            for flag in a["red_flags"]:
                st.markdown(f"- [{flag.get('severity', 'minor').upper()}] {flag.get('flag', '')}")

    st.markdown("---")

    # Download report
    if report:
        st.download_button(
            label="⬇️ Download Markdown Report",
            data=report,
            file_name=f"review_{meta.get('arxiv_id', 'paper')}.md",
            mime="text/markdown",
        )
        with st.expander("Preview Full Report"):
            st.markdown(report)


# ── Main execution logic ──────────────────────────────────────────────────────
if analyze_clicked:
    if not url.strip():
        st.error("Please enter an arXiv URL.")
        st.stop()

    # ── Pre-flight: verify Ollama is up and model is available ────────────
    with st.spinner("Checking Ollama connection..."):
        ok, msg = check_ollama(model_name)
    if not ok:
        log.error("Ollama pre-flight failed: %s", msg)
        st.error(f"Ollama not ready — {msg}")
        st.stop()
    log.info("Ollama pre-flight passed — model=%s url=%s", model_name, url.strip())

    # Import graph here to avoid slow startup
    from src.graph import create_review_graph, ReviewState

    graph = create_review_graph()

    initial_state: ReviewState = {
        "url": url.strip(),
        "model_name": model_name,
        "paper_metadata": {},
        "paper_text": "",
        "abstract": "",
        "sections": {},
        "consistency_result": {},
        "grammar_result": {},
        "novelty_result": {},
        "fact_check_result": {},
        "authenticity_result": {},
        "final_report": "",
        "current_step": "starting",
        "error": None,
    }

    # Progress tracking
    progress_placeholder = st.empty()
    status_placeholder   = st.empty()
    result_placeholder   = st.empty()

    NODE_ORDER = [k for k, _ in STEPS]
    completed_steps = []
    final_state = None

    with progress_placeholder.container():
        progress_bar = st.progress(0)
        step_cols = st.columns(len(STEPS))
        step_indicators = {}
        for i, (key, label) in enumerate(STEPS):
            step_indicators[key] = step_cols[i].empty()
            step_indicators[key].markdown(f"⬜ {label.split(' ', 1)[1]}")

    try:
        for step_output in graph.stream(initial_state):
            node_name = list(step_output.keys())[0]
            state_update = step_output[node_name]

            completed_steps.append(node_name)
            progress = len(completed_steps) / len(STEPS)
            progress_bar.progress(progress)

            # Mark completed steps
            for key in completed_steps:
                if key in step_indicators:
                    label = STEP_NAMES.get(key, key).split(" ", 1)[1]
                    step_indicators[key].markdown(f"✅ {label}")

            # Mark current running step
            next_idx = len(completed_steps)
            if next_idx < len(NODE_ORDER):
                next_key = NODE_ORDER[next_idx]
                if next_key in step_indicators:
                    label = STEP_NAMES.get(next_key, next_key).split(" ", 1)[1]
                    step_indicators[next_key].markdown(f"🔄 {label}")

            status_placeholder.info(
                f"Completed: **{STEP_NAMES.get(node_name, node_name)}**"
            )

            # Accumulate final state
            if final_state is None:
                final_state = dict(initial_state)
            final_state.update(state_update)

        # Done
        progress_bar.progress(1.0)
        status_placeholder.success("Analysis complete!")

        if final_state and final_state.get("error"):
            log.error("Pipeline error: %s", final_state["error"][:300])
            friendly = _friendly_error(final_state["error"])
            st.error(friendly)
            with st.expander("Full error details"):
                st.code(final_state["error"], language="text")
        elif final_state:
            with result_placeholder.container():
                render_results(final_state)

    except Exception as e:
        friendly = _friendly_error(str(e))
        st.error(f"Unexpected error: {friendly}")
        with st.expander("Full error details"):
            import traceback
            st.code(traceback.format_exc(), language="text")

elif not analyze_clicked:
    st.info("Enter an arXiv URL and click **Analyze** to begin the peer-review simulation.")

    st.markdown("### Example Papers to Try")
    examples = [
        ("Attention Is All You Need", "https://arxiv.org/pdf/1706.03762"),
        ("BERT", "https://arxiv.org/pdf/1810.04805"),
        ("ResNet", "https://arxiv.org/pdf/1512.03385"),
        ("GPT-4 Technical Report", "https://arxiv.org/pdf/2303.08774"),
    ]
    for title, link in examples:
        st.markdown(f"- [{title}]({link}) — `{link}`")
