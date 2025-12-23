from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter()

class RenderMessagePayload(BaseModel):
    template: str
    context: Dict[str, Any]


@router.post("/render_message")
def render_message(payload: RenderMessagePayload):
    rendered = payload.template

    for key, value in payload.context.items():
        token = f"__{key.upper()}__"
        rendered = rendered.replace(token, str(value))

    return {
        "rendered": rendered
    }
