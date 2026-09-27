import json
import sys

from mcp.server.mcpserver import MCPServer

from app.services.db_tools import (
    get_customers,
    get_parts,
    get_sales_invoices,
)


mcp_server = MCPServer(
    "erp-mcp-server"
)


# ============================================================
# GET CUSTOMERS
# ============================================================

@mcp_server.tool(
    name="getCustomers",
    description="Get the list of customers from the ERP system.",
)
async def get_customers_tool() -> str:

    try:

        result = get_customers()

        return json.dumps(
            result,
            default=str,
        )

    except Exception as error:

        return json.dumps({
            "error": str(error)
        })


# ============================================================
# GET PARTS
# ============================================================

@mcp_server.tool(
    name="getParts",
    description="Get the list of available parts from the ERP system.",
)
async def get_parts_tool() -> str:

    try:

        result = get_parts()

        return json.dumps(
            result,
            default=str,
        )

    except Exception as error:

        return json.dumps({
            "error": str(error)
        })


# ============================================================
# GET SALES ORDERS
# ============================================================

@mcp_server.tool(
    name="getSalesInvoices",
    description="Get sales invoices using optional filters.",
)
async def get_sales_invoices_tool(

    salesInvoiceNumber: str | None = None,
    customerName: str | None = None,
    partNumber: str | None = None,
    fromDate: str | None = None,
    toDate: str | None = None,

    includeCustomerSummary: bool = False,
    includePartSummary: bool = False,
    includeUnusedCustomers: bool = False,
    includeUnusedParts: bool = False,

) -> str:

    try:

        result = get_sales_invoices(

            sales_invoice_number=salesInvoiceNumber,
            customer_name=customerName,
            part_number=partNumber,
            from_date=fromDate,
            to_date=toDate,

            include_customer_summary=includeCustomerSummary,
            include_part_summary=includePartSummary,
            include_unused_customers=includeUnusedCustomers,
            include_unused_parts=includeUnusedParts,
        )

        return json.dumps(
            result,
            default=str,
        )

    except Exception as error:

        return json.dumps({
            "error": str(error)
        })


# ============================================================
# START MCP SERVER
# ============================================================

async def start_mcp_server():

    await mcp_server.run_stdio_async()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    import asyncio

    asyncio.run(
        start_mcp_server()
    )