# dummy_mcp_server.py
import uvicorn
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

mcp_server = FastMCP("DummyServer", stateless_http=True)

@mcp_server.tool()
def echo_tool(message: str) -> str:
    print(f"Dummy MCP Server: 'echo_tool' called with message: '{message}'")
    response = f"Echo from dummy MCP: {message}"
    print(f"Dummy MCP Server: sending response: '{response}'")
    return response

if __name__ == "__main__":
    print("Starting dummy MCP server on port 8001...")
    app = FastAPI(title=mcp_server.name)
    app.mount("/mcp", mcp_server.streamable_http_app()) # Standard MCP path
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
