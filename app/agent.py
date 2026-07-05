"""LangGraph ReAct agent (Day-2 / stretch). Multi-step tool use over the corpus.

Requires: langgraph, langchain-google-vertexai.
"""
import time

from langchain_core.tools import tool
from langchain_google_vertexai import ChatVertexAI
from langgraph.prebuilt import create_react_agent

from . import config, rag


@tool
def search_docs(query: str) -> str:
    """Semantic-search the technical doc corpus. Returns top passages with their source."""
    hits = rag.retrieve(query, k=config.TOP_K)
    return "\n\n".join(f"[{h['source']}] {h['content']}" for h in hits)


@tool
def list_sources() -> str:
    """List the distinct source documents available in the corpus."""
    conn = rag.db.connect()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT source FROM chunks ORDER BY source")
    srcs = [r[0] for r in cur.fetchall()]
    cur.close(); conn.close()
    return ", ".join(srcs)


_llm = ChatVertexAI(model=config.GEN_MODEL, temperature=0)
_agent = create_react_agent(_llm, [search_docs, list_sources])

SYSTEM = (
    "You are a field-support assistant. Use search_docs (possibly multiple times) "
    "to ground every claim. Cite source filenames. If unknown, say so."
)


def run(question: str) -> dict:
    t0 = time.time()
    state = _agent.invoke({"messages": [("system", SYSTEM), ("user", question)]})
    final = state["messages"][-1].content
    return {"answer": final, "mode": "agent", "latency_ms": int((time.time() - t0) * 1000)}
