from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from bson import ObjectId

from app.db import get_db
from app.auth import get_optional_user, get_current_user
from app.models.chat import ChatRequest, ChatResponse, ChatMessage, ConversationResponse, MessageCitation
from app.services.openai_service import generate_chat_response
from app.routes.papers import get_client_ip_hash

router = APIRouter(prefix="/chat", tags=["Chat"])

def verify_paper_access(db, paper_id: str, request: Request, user: Optional[dict]) -> dict:
    """Verifies that the caller has access to the paper (authenticated owner or correct guest IP)."""
    try:
        paper = db.papers.find_one({"_id": ObjectId(paper_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Paper not found")
        
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
        
    if paper.get("user_id") is not None:
        if not user or paper["user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied. You do not own this research paper.")
    else:
        ip_hash = get_client_ip_hash(request)
        trial = db.free_trials.find_one({"ip_hash": ip_hash, "paper_id": paper_id})
        if not trial:
            raise HTTPException(status_code=403, detail="Free analysis session expired. Please sign in to ask questions.")
            
    return paper

@router.post("/{paper_id}", response_model=ChatResponse)
def chat_with_paper(
    paper_id: str,
    body: ChatRequest,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    db = get_db()
    # Verify paper exists and user has access
    paper = verify_paper_access(db, paper_id, request, current_user)
    
    conversation_id = body.conversation_id
    convo = None
    
    # 1. Retrieve or Create Conversation
    if conversation_id:
        try:
            convo = db.conversations.find_one({"_id": ObjectId(conversation_id)})
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
            
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation session not found")
    else:
        # Create a new conversation session
        user_id = current_user["id"] if current_user else None
        
        # Title is taken from the first user query, truncated
        convo_title = body.message[:40] + "..." if len(body.message) > 40 else body.message
        
        new_convo = {
            "user_id": user_id,
            "paper_id": paper_id,
            "title": convo_title,
            "messages": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        res = db.conversations.insert_one(new_convo)
        conversation_id = str(res.inserted_id)
        convo = new_convo
        convo["id"] = conversation_id
        
    # Standardize ID representation
    if "id" not in convo:
        convo["id"] = str(convo["_id"])
        
    # 2. Extract history for LLM prompt context
    history_messages = convo.get("messages", [])
    
    # 3. Call RAG chat completion service
    ai_result = generate_chat_response(
        paper_id=paper_id,
        paper_title=paper["title"],
        history=history_messages,
        user_message=body.message
    )
    
    # 4. Construct message docs
    user_msg_doc = {
        "role": "user",
        "content": body.message,
        "timestamp": datetime.utcnow()
    }
    
    assistant_msg_doc = {
        "role": "assistant",
        "content": ai_result["content"],
        "citations": ai_result["citations"],
        "timestamp": datetime.utcnow()
    }
    
    # 5. Save back to database
    db.conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {
            "$push": {
                "messages": {
                    "$each": [user_msg_doc, assistant_msg_doc]
                }
            },
            "$set": {
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {
        "conversation_id": conversation_id,
        "message": ChatMessage(**assistant_msg_doc)
    }

@router.get("/{paper_id}/conversations", response_model=List[ConversationResponse])
def get_conversations_for_paper(
    paper_id: str,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    db = get_db()
    
    # Free users can query conversations but let's filter correctly
    user_id = current_user["id"] if current_user else None
    
    query = {"paper_id": paper_id}
    if user_id:
        query["user_id"] = user_id
    else:
        # Guest: Match by IP trial check too
        ip_hash = get_client_ip_hash(request)
        trial = db.free_trials.find_one({"ip_hash": ip_hash, "paper_id": paper_id})
        if not trial:
            return []
        query["user_id"] = None
        
    convos = list(db.conversations.find(query).sort("updated_at", -1))
    
    response = []
    for c in convos:
        c["id"] = str(c["_id"])
        response.append(ConversationResponse(**c))
    return response

@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation_details(
    conversation_id: str,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    db = get_db()
    try:
        convo = db.conversations.find_one({"_id": ObjectId(conversation_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")
        
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation session not found")
        
    # Check permissions
    paper_id = convo["paper_id"]
    verify_paper_access(db, paper_id, request, current_user)
    
    convo["id"] = str(convo["_id"])
    return ConversationResponse(**convo)

@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    db = get_db()
    try:
        convo = db.conversations.find_one({"_id": ObjectId(conversation_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")
        
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation session not found")
        
    # Verify access
    verify_paper_access(db, convo["paper_id"], request, current_user)
    
    db.conversations.delete_one({"_id": ObjectId(conversation_id)})
    return {"message": "Conversation session deleted successfully."}
