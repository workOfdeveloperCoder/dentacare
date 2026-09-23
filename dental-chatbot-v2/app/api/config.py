from typing import Any

from fastapi import APIRouter, HTTPException

from app.chat_engine import ChatEngine


router = APIRouter(tags=["Config"])
engine = ChatEngine()


@router.get("/flows/{flow_key}/config")
def flow_config(flow_key: str) -> dict[str, Any]:
    try:
        return engine.get_public_config(flow_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
