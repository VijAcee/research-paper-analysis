from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from bson import ObjectId

from app.db import get_db
from app.auth import get_current_user
from app.services.vector_store import delete_paper_chunks

router = APIRouter(prefix="/settings", tags=["User Settings"])

class UserSettingsModel(BaseModel):
    explanation_level: str = Field(default="Standard", description="Simple, Standard, or Advanced")
    analysis_length: str = Field(default="Detailed", description="Short or Detailed")
    language: str = Field(default="English", description="Target analysis language")
    theme: str = Field(default="System Default", description="Light, Dark, or System Default")

@router.get("", response_model=UserSettingsModel)
def get_user_settings(current_user: dict = Depends(get_current_user)):
    """Retrieves settings for the currently authenticated user."""
    db = get_db()
    user_id = current_user["id"]
    user_doc = db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
        
    settings = user_doc.get("settings", {})
    return UserSettingsModel(
        explanation_level=settings.get("explanation_level", "Standard"),
        analysis_length=settings.get("analysis_length", "Detailed"),
        language=settings.get("language", "English"),
        theme=settings.get("theme", "System Default")
    )

@router.put("", response_model=UserSettingsModel)
def update_user_settings(
    settings_in: UserSettingsModel,
    current_user: dict = Depends(get_current_user)
):
    """Updates settings for the currently authenticated user."""
    db = get_db()
    user_id = current_user["id"]
    
    # Validate explanation level
    if settings_in.explanation_level not in ["Simple", "Standard", "Advanced"]:
        raise HTTPException(status_code=400, detail="Explanation level must be Simple, Standard, or Advanced.")
        
    # Validate analysis length
    if settings_in.analysis_length not in ["Short", "Detailed"]:
        raise HTTPException(status_code=400, detail="Analysis length must be Short or Detailed.")
        
    # Validate theme
    if settings_in.theme not in ["Light", "Dark", "System Default"]:
        raise HTTPException(status_code=400, detail="Theme must be Light, Dark, or System Default.")

    # Validate language
    if settings_in.language not in ["English", "Hindi"]:
        raise HTTPException(status_code=400, detail="Language must be English or Hindi.")

    updated_settings = {
        "explanation_level": settings_in.explanation_level,
        "analysis_length": settings_in.analysis_length,
        "language": settings_in.language,
        "theme": settings_in.theme,
        "updated_at": datetime.utcnow()
    }

    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"settings": updated_settings}}
    )
    
    return settings_in

@router.delete("/papers")
def delete_all_user_papers(current_user: dict = Depends(get_current_user)):
    """Deletes all uploaded research papers for the currently authenticated user."""
    db = get_db()
    user_id = current_user["id"]
    
    papers = list(db.papers.find({"user_id": user_id}))
    for paper in papers:
        paper_id = str(paper["_id"])
        delete_paper_chunks(paper_id)
        
    res = db.papers.delete_many({"user_id": user_id})
    return {
        "message": f"Successfully deleted {res.deleted_count} uploaded papers.",
        "count": res.deleted_count
    }

@router.delete("/history")
def clear_user_analysis_history(current_user: dict = Depends(get_current_user)):
    """Clears all chat conversations and analysis history for the currently authenticated user."""
    db = get_db()
    user_id = current_user["id"]
    
    res = db.conversations.delete_many({"user_id": user_id})
    return {
        "message": f"Successfully cleared analysis and chat history across {res.deleted_count} sessions.",
        "count": res.deleted_count
    }

@router.get("/download-data")
def download_user_data(current_user: dict = Depends(get_current_user)):
    """Downloads personal account data and research-paper-related data stored for the authenticated user."""
    db = get_db()
    user_id = current_user["id"]
    
    user_doc = db.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User profile not found.")
        
    user_papers = list(db.papers.find({"user_id": user_id}))
    user_convos = list(db.conversations.find({"user_id": user_id}))
    
    # Sanitize database IDs for export
    for p in user_papers:
        p["id"] = str(p["_id"])
        if "_id" in p:
            del p["_id"]
        
    for c in user_convos:
        c["id"] = str(c["_id"])
        if "_id" in c:
            del c["_id"]
        
    export_payload = {
        "user_profile": {
            "id": user_id,
            "email": user_doc.get("email"),
            "full_name": user_doc.get("full_name"),
            "created_at": user_doc.get("created_at", datetime.utcnow()).isoformat() if isinstance(user_doc.get("created_at"), datetime) else str(user_doc.get("created_at")),
            "settings": user_doc.get("settings", {})
        },
        "uploaded_papers_count": len(user_papers),
        "uploaded_papers": user_papers,
        "chat_conversations_count": len(user_convos),
        "chat_conversations": user_convos,
        "export_timestamp": datetime.utcnow().isoformat()
    }
    
    return export_payload
