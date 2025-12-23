from pydantic import BaseModel
from typing import Literal, Optional, Dict, Any


class SlotPayload(BaseModel):
    coureur_id: str
    mode: Literal["FIRST", "NEXT"]

    options: Optional[Dict[str, Any]] = None
