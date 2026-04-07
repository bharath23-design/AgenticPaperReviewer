"""
LangGraph workflow — orchestrates the full paper review pipeline.

Graph topology (sequential):
  START
    → scrape_paper
    → decompose_sections
    → analyze_consistency
    → analyze_grammar
    → analyze_novelty
    → verify_facts
    → score_authenticity
    → generate_report
  END
"""

from __future__ import annotations
import time
import traceback
from typing import Any, Dict, Optional, TypedDict
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from .agents.authenticity_agent import AuthenticityAgent
from .agents.consistency_agent import ConsistencyAgent
from .agents.fact_check_agent import FactCheckAgent
from .agents.grammar_agent import GrammarAgent
from .agents.novelty_agent import NoveltyAgent
from .decomposer import decompose_paper
from .logger import get_logger
from .report_generator import generate_report
from .scraper import scrape_paper

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class ReviewState(TypedDict):
    url: str
    model_name: str
    # Populated by scrape node
    paper_metadata: Dict[str, Any]
    paper_text: str
    abstract: str
    # Populated by decompose node
    sections: Dict[str, str]
    # Populated by agent nodes
    consistency_result: Dict[str, Any]
    grammar_result: Dict[str, Any]
    novelty_result: Dict[str, Any]
    fact_check_result: Dict[str, Any]
    authenticity_result: Dict[str, Any]
    # Populated by report node
    final_report: str
    # Status tracking
    current_step: str
    error: Optional[str]


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

def _safe_run(node_name: str, fn, state: ReviewState) -> dict:
    """Wrap a node function with error capture and timing."""
    log.info(">>> Node START: %s", node_name)
    t0 = time.time()
    try:
        result = fn(state)
        log.info("<<< Node DONE:  %s (%.1fs)", node_name, time.time() - t0)
        return result
    except Exception as exc:
        tb = traceback.format_exc()
        log.error("<<< Node ERROR: %s (%.1fs) — %s", node_name, time.time() - t0, exc)
        log.debug("Traceback for %s:\n%s", node_name, tb)
        return {
            "error": f"[{node_name}] {exc}\n{tb}",
            "current_step": node_name,
        }


def node_scrape(state: ReviewState) -> dict:
    result = scrape_paper(state["url"])
    return {
        "paper_metadata": result["metadata"],
        "paper_text": result["full_text"],
        "abstract": result["abstract"],
        "current_step": "scraped",
    }


def node_decompose(state: ReviewState) -> dict:
    model_name = state.get("model_name", "llama3.2")
    llm = ChatOllama(model=model_name, temperature=0.1)
    sections = decompose_paper(
        full_text=state["paper_text"],
        abstract=state["abstract"],
        llm=llm,
    )
    return {"sections": sections, "current_step": "decomposed"}


def node_consistency(state: ReviewState) -> dict:
    agent = ConsistencyAgent(model_name=state.get("model_name"))
    result = agent.analyze(state["sections"])
    return {"consistency_result": result, "current_step": "consistency_done"}


def node_grammar(state: ReviewState) -> dict:
    agent = GrammarAgent(model_name=state.get("model_name"))
    result = agent.analyze(state["sections"])
    return {"grammar_result": result, "current_step": "grammar_done"}


def node_novelty(state: ReviewState) -> dict:
    agent = NoveltyAgent(model_name=state.get("model_name"))
    result = agent.analyze(state["sections"], state["paper_metadata"])
    return {"novelty_result": result, "current_step": "novelty_done"}


def node_fact_check(state: ReviewState) -> dict:
    agent = FactCheckAgent(model_name=state.get("model_name"))
    result = agent.analyze(state["sections"])
    return {"fact_check_result": result, "current_step": "fact_check_done"}


def node_authenticity(state: ReviewState) -> dict:
    agent = AuthenticityAgent(model_name=state.get("model_name"))
    result = agent.analyze(state["sections"], state["paper_metadata"])
    return {"authenticity_result": result, "current_step": "authenticity_done"}


def node_report(state: ReviewState) -> dict:
    report = generate_report(state)
    return {"final_report": report, "current_step": "complete"}


# ---------------------------------------------------------------------------
# Safe wrappers (so one agent failure doesn't crash the graph)
# ---------------------------------------------------------------------------

def safe_scrape(state):      
    return _safe_run("scrape",       node_scrape,       state)

def safe_decompose(state):    
    return _safe_run("decompose",    node_decompose,    state)

def safe_consistency(state):  
    return _safe_run("consistency",  node_consistency,  state)

def safe_grammar(state):      
    return _safe_run("grammar",      node_grammar,      state)

def safe_novelty(state):      
    return _safe_run("novelty",      node_novelty,      state)

def safe_fact_check(state):   
    return _safe_run("fact_check",   node_fact_check,   state)

def safe_authenticity(state): 
    return _safe_run("authenticity", node_authenticity, state)

def safe_report(state):       
    return _safe_run("report",       node_report,       state)


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def create_review_graph():
    """Build and compile the LangGraph review pipeline."""
    builder = StateGraph(ReviewState)

    builder.add_node("scrape",        safe_scrape)
    builder.add_node("decompose",     safe_decompose)
    builder.add_node("consistency",   safe_consistency)
    builder.add_node("grammar",       safe_grammar)
    builder.add_node("novelty",       safe_novelty)
    builder.add_node("fact_check",    safe_fact_check)
    builder.add_node("authenticity",  safe_authenticity)
    builder.add_node("report",        safe_report)

    builder.add_edge(START,          "scrape")
    builder.add_edge("scrape",       "decompose")
    builder.add_edge("decompose",    "consistency")
    builder.add_edge("consistency",  "grammar")
    builder.add_edge("grammar",      "novelty")
    builder.add_edge("novelty",      "fact_check")
    builder.add_edge("fact_check",   "authenticity")
    builder.add_edge("authenticity", "report")
    builder.add_edge("report",       END)

    return builder.compile()


def run_review(url: str, model_name: str = "llama3.2") -> ReviewState:
    """Convenience function: run the full pipeline and return final state."""
    log.info("=== REVIEW STARTED === url=%s model=%s", url, model_name)
    t_start = time.time()
    graph = create_review_graph()
    initial_state: ReviewState = {
        "url": url,
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
    final_state = graph.invoke(initial_state)
    elapsed = time.time() - t_start
    if final_state.get("error"):
        log.error("=== REVIEW FAILED === %.1fs — %s", elapsed, final_state["error"][:200])
    else:
        log.info("=== REVIEW COMPLETE === %.1fs", elapsed)
    return final_state