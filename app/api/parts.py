from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.services.part_service import (
    search_parts,
    get_part_by_id,
    create_part,
    update_part,
)


router = APIRouter(
    prefix="/parts",
    tags=["Parts"]
)


# ============================================================
# REQUEST MODEL
# ============================================================

class PartRequest(BaseModel):
    partName: str
    partPrice: float


# ============================================================
# SEARCH PARTS
# GET /parts?partNumber=P001&partName=ABC
# ============================================================

@router.get("")
async def search_parts_api(
    partNumber: str = Query(default=""),
    partName: str = Query(default=""),
):

    try:
        parts = search_parts(
            part_number=partNumber,
            part_name=partName,
        )

        return {
            "success": True,
            "data": parts,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Failed to search parts"
        )


# ============================================================
# GET PART BY ID
# GET /parts/1
# ============================================================

@router.get("/{part_id}")
async def get_part_api(part_id: int):

    try:
        part = get_part_by_id(part_id)

        if not part:
            raise HTTPException(
                status_code=404,
                detail="Part not found"
            )

        return {
            "success": True,
            "data": part,
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Failed to get part"
        )


# ============================================================
# CREATE PART
# POST /parts
# ============================================================

@router.post("")
async def create_part_api(part: PartRequest):

    try:

        result = create_part(
            part.partName,
            part.partPrice
        )

        # ----------------------------------------------------
        # DUPLICATE PART
        # ----------------------------------------------------

        if result.get("status") == 409:
            raise HTTPException(
                status_code=409,
                detail='Part already exists'
            )

        return {
            "success": True,
            "message": "Part created successfully",
            "data": result,
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Failed to create part"
        )


# ============================================================
# UPDATE PART
# PUT /parts/1
# ============================================================

@router.put("/{part_id}")
async def update_part_api(
    part_id: int,
    part: PartRequest
):

    try:

        result = update_part(
            part_id,
            part.partName,
            part.partPrice
        )

        # ----------------------------------------------------
        # PART NOT FOUND
        # ----------------------------------------------------

        if result.get("status") == 404:
            raise HTTPException(
                status_code=404,
                detail=result["error"]
            )

        # ----------------------------------------------------
        # DUPLICATE PART
        # ----------------------------------------------------

        if result.get("status") == 409:
            raise HTTPException(
                status_code=409,
                detail=result["error"]
            )

        return {
            "success": True,
            "message": "Part updated successfully",
            "data": result,
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="Failed to update part"
        )