import sys
from pathlib import Path
import os
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SERVER_MODULE = "app.mcp.starter_mcp_server"


# ============================================================
# MCP SERVER PARAMETERS
# ============================================================

server_parameters = StdioServerParameters(
    command=sys.executable,
    args=[
        "-m",
        SERVER_MODULE,
    ],
    cwd=str(PROJECT_ROOT),
    env={**os.environ},
)


# ============================================================
# GET AVAILABLE TOOLS
# ============================================================

async def get_available_tools():

    async with stdio_client(
        server_parameters
    ) as (
        read_stream,
        write_stream,
    ):

        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            await session.initialize()

            result = await session.list_tools()

            return result.tools


# ============================================================
# CALL TOOL
# ============================================================

async def call_tool(
    tool_name: str,
    arguments_data: dict | None = None,
):

    if arguments_data is None:
        arguments_data = {}

    async with stdio_client(
        server_parameters
    ) as (
        read_stream,
        write_stream,
    ):

        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            await session.initialize()

            result = await session.call_tool(
                tool_name,
                arguments_data,
            )

            return result