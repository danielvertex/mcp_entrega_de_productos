import sys
import os
from fastmcp import FastMCP
from delivery_app.app import app

mcp = FastMCP("Test", providers=[app])

if __name__ == "__main__":
    mcp.run()
