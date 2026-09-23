from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.chat_engine import ChatEngine

import traceback

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


engine = ChatEngine()


class ChatRequest(BaseModel):

    flow_key: str | None = Field(
        default=None,
        max_length=100,
    )

    session_token: str | None = Field(
        default=None,
        max_length=100,
    )

    message: str | None = Field(
        default=None,
        max_length=2000,
    )

    option_key: str | None = Field(
        default=None,
        max_length=200,
    )


@router.post("")
def chat(
    request: ChatRequest,
) -> dict[str, Any]:

    try:

        # =================================================
        # START NEW SESSION
        # =================================================

        if not request.session_token:

            if not request.flow_key:

                raise HTTPException(
                    status_code=400,
                    detail="flow_key is required.",
                )

            return engine.start_session(
                flow_key=request.flow_key,
            )


        # =================================================
        # CONTINUE EXISTING SESSION
        # =================================================

        return engine.process_input(
            session_token=request.session_token,
            message=request.message,
            option_key=request.option_key,
        )


    # =====================================================
    # EXPECTED CLIENT / BUSINESS ERROR
    # =====================================================

    except HTTPException:
        raise


    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


    # =====================================================
    # UNEXPECTED SERVER ERROR
    # =====================================================

    except Exception as exc:

        traceback.print_exc()

        # Do not expose database errors, SQL errors,
        # filesystem paths, stack traces, etc. to clients.

        raise HTTPException(
            status_code=500,
            detail=(
                "We're having trouble processing your request "
                "right now. Please try again."
            ),
        ) from exc