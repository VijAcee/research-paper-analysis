from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class LiteratureReviewRequest(BaseModel):
    paper_ids: List[str]
    title: Optional[str] = None

class LiteratureReviewResponse(BaseModel):
    id: str
    user_id: str
    paper_ids: List[str]
    title: str
    content: str  # Structured Markdown review
    created_at: datetime
