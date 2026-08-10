from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Any, Optional

class ComparisonRequest(BaseModel):
    paper_ids: List[str]

class ComparisonResponse(BaseModel):
    id: str
    user_id: str
    paper_ids: List[str]
    title: str
    matrix: List[Dict[str, Any]] = []  # Detailed rows comparing features (e.g. Methodology, Dataset, etc.)
    detailed_analysis: str  # Markdown generated analysis text
    conclusion: str
    created_at: datetime
