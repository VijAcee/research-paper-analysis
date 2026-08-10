from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any

class MessageCitation(BaseModel):
    source_chunk_id: str
    page_number: Optional[int] = None
    text_snippet: str
    relevance_score: Optional[float] = None

class ChatMessage(BaseModel):
    role: str = Field(..., description="Either 'user' or 'assistant'")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    citations: Optional[List[MessageCitation]] = None

class ConversationResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    paper_id: str
    title: str
    messages: List[ChatMessage] = []
    created_at: datetime
    updated_at: datetime

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessage
