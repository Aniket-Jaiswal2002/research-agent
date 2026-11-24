"""ResearchMind as an MCP server.

Exposes the same retrieval tools the agent uses, so any MCP client
(Claude Desktop, Cursor, Claude Code, your own agent) can search your PDFs.

    python mcp_server.py            # stdio transport

Claude Desktop config (claude_desktop_config.json):
    {"mcpServers": {"researchmind": {
        "command": "python",
        "args": ["C:/path/to/research-agent/mcp_server.py"]}}}
"""
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))  # vector_store/ is relative

try:  # MCP Python SDK 2.x
    from mcp.server.mcpserver import MCPServer  # noqa: E402
except ImportError:  # SDK 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer  # noqa: E402
from ingest import list_pdfs  # noqa: E402
import tools as rm_tools  # noqa: E402

mcp = MCPServer("researchmind")


@mcp.tool()
def list_documents() -> list[str]:
    """List the PDFs that have been ingested and can be searched."""
    return list_pdfs()


@mcp.tool()
def search_pdf(query: str, document: str | None = None) -> str:
    """Semantic search over an ingested PDF. Returns the most relevant passages,
    each prefixed with [Source: file, Page N]. Search by topic or meaning, not by
    page number. `document` is a name from list_documents(); defaults to the
    first ingested PDF."""
    docs = list_pdfs()
    if not docs:
        return "No PDFs have been ingested. Run: python ingest.py yourfile.pdf"
    name = document or rm_tools.active_pdf["name"] or docs[0]
    if name not in docs:
        return f"Unknown document '{name}'. Available: {', '.join(docs)}"
    rm_tools.set_active_pdf(name)
    return rm_tools.pdf_search_tool.invoke({"query": query})


@mcp.tool()
def web_search(query: str) -> str:
    """Search the web (Tavily) for current information not in the PDFs.
    Returns titles, URLs and snippets."""
    return str(rm_tools.web_search_tool.invoke({"query": query}))


if __name__ == "__main__":
    mcp.run()
