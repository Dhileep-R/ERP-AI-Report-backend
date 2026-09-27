from typing import List

from fastapi import (
    APIRouter,
    Query,
    HTTPException
)

from pydantic import BaseModel

from app.services.sales_invoice_service import (
    search_sales_invoices,
    get_sales_invoice_by_id,
    create_sales_invoice,
    update_sales_invoice
)


router = APIRouter(
    prefix="/sales-invoices",
    tags=["Sales Invoices"]
)


# ============================================================
# REQUEST MODELS
# ============================================================

class SalesInvoiceLineItem(BaseModel):
    partId: int
    price: float
    quantity: int


class SalesInvoiceRequest(BaseModel):
    customerId: int
    lineItems: List[SalesInvoiceLineItem]

@router.get("")
async def search_sales_invoices_api(
    salesInvoiceNumber: str = Query(default=""),
    customerId: str = Query(default=""),
    fromDate: str = Query(default=""),
    toDate: str = Query(default="")
):

    try:

        invoices = search_sales_invoices(
            sales_invoice_number=salesInvoiceNumber,
            customer_id=customerId,
            from_date=fromDate,
            to_date=toDate
        )

        return {
            "success": True,
            "data": invoices
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Failed to search sales invoice"
        )

@router.get("/{sales_invoice_id}")
async def get_sales_invoice_api(
    sales_invoice_id: int
):

    try:

        invoice = get_sales_invoice_by_id(
            sales_invoice_id
        )

        if not invoice:

            raise HTTPException(
                status_code=404,
                detail="Sales invoice not found"
            )

        return {
            "success": True,
            "data": invoice
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Failed to get sales invoice"
        )

@router.post("")
async def create_sales_invoice_api(
    sales_invoice: SalesInvoiceRequest
):

    try:

        line_items = [
            item.model_dump()
            for item in sales_invoice.lineItems
        ]

        result = create_sales_invoice(
            customer_id=sales_invoice.customerId,
            line_items=line_items
        )

        if result.get("status"):

            raise HTTPException(
                status_code=result["status"],
                detail=result["error"]
            )

        return {
            "success": True,
            "message":
                "Sales invoice created successfully",
            "data": result
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Failed to create sales invoice"
        )

@router.put("/{sales_invoice_id}")
async def update_sales_invoice_api(
    sales_invoice_id: int,
    sales_invoice: SalesInvoiceRequest
):

    try:

        line_items = [
            item.model_dump()
            for item in sales_invoice.lineItems
        ]

        result = update_sales_invoice(
            sales_invoice_id=sales_invoice_id,
            customer_id=sales_invoice.customerId,
            line_items=line_items
        )

        if result.get("status"):

            raise HTTPException(
                status_code=result["status"],
                detail=result["error"]
            )

        return {
            "success": True,
            "message":
                "Sales invoice updated successfully",
            "data": result
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Failed to update sales invoice"
        )