"""FastMCP server para la app de entregas.

Monta la FastMCPApp como provider y expone el endpoint /health.
"""

from fastmcp import FastMCP

from .app import app

mcp = FastMCP("Delivery Server", providers=[app])


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    """Health check endpoint para Docker/nginx."""
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "ok", "app": "delivery-app"})


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
