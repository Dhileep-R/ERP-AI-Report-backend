from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.services.customer_service import (
    search_customers,
    create_customer,
    update_customer,
    get_customer_by_id,
)


router = APIRouter(
    prefix="/customers",
    tags=["Customers"]
)


# ============================================================
# REQUEST MODEL
# ============================================================

class CustomerRequest(BaseModel):
    name: str


# ============================================================
# SEARCH CUSTOMERS
# GET /customers/?name=abc
# ============================================================

@router.get("")
async def search_customer_api(
    name: str = Query(default="")
):
    try:
        search_value = name.strip()

        customers = search_customers(search_value)

        return {
            "success": True,
            "data": customers,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Failed to search customers"
        )


# ============================================================
# GET CUSTOMER BY ID
# GET /customers/1
# ============================================================

@router.get("/{customer_id}")
async def get_customer_api(customer_id: int):

    try:
        customer = get_customer_by_id(customer_id)

        if not customer:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        return {
            "success": True,
            "data": customer,
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Failed to get customer"
        )


# ============================================================
# CREATE CUSTOMER
# POST /customers/
# ============================================================

@router.post("")
async def create_customer_api(
    customer: CustomerRequest
):

    try:

        customer_name = customer.name.strip()

        result = create_customer(customer_name)

        # Duplicate customer
        if result.get("status") == 409:
            raise HTTPException(
                status_code=409,
                detail='Customer already exists'
            )

        return {
            "success": True,
            "message": "Customer created successfully",
            "data": result,
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Failed to create customer"
        )


# ============================================================
# UPDATE CUSTOMER
# PUT /customers/1
# ============================================================

@router.put("/{customer_id}")
async def update_customer_api(
    customer_id: int,
    customer: CustomerRequest
):

    try:

        customer_name = customer.name.strip()

        result = update_customer(
            customer_id,
            customer_name
        )

        # Customer not found
        if result.get("status") == 404:
            raise HTTPException(
                status_code=404,
                detail=result["error"]
            )

        # Duplicate customer name
        if result.get("status") == 409:
            raise HTTPException(
                status_code=409,
                detail=result["error"]
            )

        return {
            "success": True,
            "message": "Customer updated successfully",
            "data": result,
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Failed to update customer"
        )