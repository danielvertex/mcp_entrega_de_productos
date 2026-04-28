"""FastMCP server para la app de entregas.

Monta la FastMCPApp como provider y expone el endpoint /health.
"""
import sys
from pathlib import Path

# Asegurar que el directorio padre esté en sys.path
# (necesario para fastmcp dev inspector)
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from fastmcp import FastMCP

from delivery_app.app import app

mcp = FastMCP("Delivery Server", providers=[app])


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    """Health check endpoint para Docker/nginx."""
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "ok", "app": "delivery-app"})


if __name__ == "__main__":
    mcp.run()
