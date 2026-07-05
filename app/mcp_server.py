"""Optional: expose corpus retrieval as an MCP (Model Context Protocol) server.

Run:  python -m app.mcp_server
Then connect from an MCP client (e.g. Claude Desktop) via stdio.
"""
from mcp.server.fastmcp import FastMCP

from . import config, rag

mcp = FastMCP("fieldrag")


@mcp.tool()
def search_docs(query: str) -> str:
    """Semantic-search the NGS field-support doc corpus; returns top passages + sources."""
    hits = rag.retrieve(query, k=config.TOP_K)
    return "\n\n".join(f"[{h['source']}] {h['content']}" for h in hits)


@mcp.tool()
def ask(question: str) -> str:
    """Full grounded RAG answer with citations."""
    return rag.answer(question)["answer"]


if __name__ == "__main__":
    mcp.run()
