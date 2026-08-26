from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class PaginatedResponse(BaseModel):
    total: int
    items: List[Any]
    page: int
    size: int
