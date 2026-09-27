from typing import List, Optional
import traceback

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.ai_service import run_agent

router = APIRouter(prefix="/ai", tags=["AI"])


class ChatHistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    prompt: str
    history: Optional[List[ChatHistoryMessage]] = None


@router.post("/chat")
async def chat(request: ChatRequest):

    try:

        if not request.prompt or not request.prompt.strip():
            raise HTTPException(
                status_code=400,
                detail="Message is required."
            )

        history = []

        if request.history:
            history = [
                {
                    "role": message.role,
                    "content": message.content
                }
                for message in request.history
            ]

        result = await run_agent(
            request.prompt.strip(),
            history
        )

        return result

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )