from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from bson import ObjectId

from app.db import get_db
from app.auth import get_current_user
from app.services.vector_store import delete_paper_chunks

router = APIRouter(prefix="/settings", tags=["User Settings"])

# Map normalized internal values to canonical UI labels and internal codes
EXP_MAP = {
    "simple": ("simple", "Simple"),
    "standard": ("standard", "Standard"),
    "advanced": ("advanced", "Advanced"),
    "Simple": ("simple", "Simple"),
    "Standard": ("standard", "Standard"),
    "Advanced": ("advanced", "Advanced"),
}

LEN_MAP = {
    "short": ("short", "Short"),
    "detailed": ("detailed", "Detailed"),
    "Short": ("short", "Short"),
    "Detailed": ("detailed", "Detailed"),
}

LANG_MAP = {
    "en": ("en", "English"),
    "hi": ("hi", "Hindi"),
    "english": ("en", "English"),
    "hindi": ("hi", "Hindi"),
    "English": ("en", "English"),
    "Hindi": ("hi", "Hindi"),
}

THEME_MAP = {
    "light": ("light", "Light"),
    "dark": ("dark", "Dark"),
    "system": ("system", "System Default"),
    "system default": ("system", "System Default"),
    "Light": ("light", "Light"),
    "Dark": ("dark", "Dark"),
    "System Default": ("system", "System Default"),
}

class UserSettingsModel(BaseModel):
    # Stable internal codes (Primary schema)
    explanationLevel: str = Field(default="standard", description="simple, standard, or advanced")
    analysisLength: str = Field(default="detailed", description="short or detailed")
    language: str = Field(default="en", description="en or hi")
    appearance: str = Field(default="system", description="light, dark, or system")

    # Backward/Forward compatible display labels
    explanation_level: str = Field(default="Standard", description="Simple, Standard, or Advanced")
    analysis_length: str = Field(default="Detailed", description="Short or Detailed")
    lang_code: str = Field(default="en", description="en or hi")
    theme: str = Field(default="System Default", description="Light, Dark, or System Default")

class SettingsUpdateRequest(BaseModel):
    explanationLevel: Optional[str] = None
    explanation_level: Optional[str] = None
    analysisLength: Optional[str] = None
    analysis_length: Optional[str] = None
    language: Optional[str] = None
    lang_code: Optional[str] = None
    appearance: Optional[str] = None
    theme: Optional[str] = None

@router.get("", response_model=UserSettingsModel)
def get_user_settings(current_user: dict = Depends(get_current_user)):
    """Retrieves settings for the currently authenticated user with defaults."""
    db = get_db()
    user_id = current_user["id"]
    
    try:
        user_doc = db.users.find_one({"_id": ObjectId(user_id)}) if ObjectId.is_valid(user_id) else db.users.find_one({"_id": user_id})
    except Exception:
        user_doc = db.users.find_one({"_id": user_id})
        
    settings = user_doc.get("settings", {}) if user_doc else {}

    raw_exp = settings.get("explanationLevel") or settings.get("explanation_level") or "standard"
    raw_len = settings.get("analysisLength") or settings.get("analysis_length") or "detailed"
    raw_lang = settings.get("language") or settings.get("lang_code") or "en"
    raw_theme = settings.get("appearance") or settings.get("theme") or "system"

    exp_code, exp_label = EXP_MAP.get(str(raw_exp).strip(), ("standard", "Standard"))
    len_code, len_label = LEN_MAP.get(str(raw_len).strip(), ("detailed", "Detailed"))
    lang_code, lang_label = LANG_MAP.get(str(raw_lang).strip(), ("en", "English"))
    theme_code, theme_label = THEME_MAP.get(str(raw_theme).strip(), ("system", "System Default"))

    return UserSettingsModel(
        explanationLevel=exp_code,
        explanation_level=exp_label,
        analysisLength=len_code,
        analysis_length=len_label,
        language=lang_code,
        lang_code=lang_code,
        appearance=theme_code,
        theme=theme_label
    )

@router.put("", response_model=UserSettingsModel)
def update_user_settings(
    settings_in: SettingsUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Updates settings for the currently authenticated user with partial update merge."""
    db = get_db()
    user_id = current_user["id"]

    target_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
    try:
        user_doc = db.users.find_one({"_id": target_id})
    except Exception:
        user_doc = db.users.find_one({"_id": user_id})
        
    existing_settings = user_doc.get("settings", {}) if user_doc else {}

    # Partial merge updates:
    exp_input = settings_in.explanationLevel or settings_in.explanation_level
    if exp_input is not None:
        if str(exp_input).strip() not in EXP_MAP:
            raise HTTPException(status_code=400, detail="Invalid explanationLevel. Expected: simple, standard, or advanced.")
        exp_code, exp_label = EXP_MAP[str(exp_input).strip()]
        existing_settings["explanationLevel"] = exp_code
        existing_settings["explanation_level"] = exp_label

    len_input = settings_in.analysisLength or settings_in.analysis_length
    if len_input is not None:
        if str(len_input).strip() not in LEN_MAP:
            raise HTTPException(status_code=400, detail="Invalid analysisLength. Expected: short or detailed.")
        len_code, len_label = LEN_MAP[str(len_input).strip()]
        existing_settings["analysisLength"] = len_code
        existing_settings["analysis_length"] = len_label

    lang_input = settings_in.language or settings_in.lang_code
    if lang_input is not None:
        if str(lang_input).strip() not in LANG_MAP:
            raise HTTPException(status_code=400, detail="Invalid language. Expected: en or hi.")
        lang_code, lang_label = LANG_MAP[str(lang_input).strip()]
        existing_settings["language"] = lang_code
        existing_settings["lang_code"] = lang_code
        existing_settings["display_language"] = lang_label

    theme_input = settings_in.appearance or settings_in.theme
    if theme_input is not None:
        if str(theme_input).strip() not in THEME_MAP:
            raise HTTPException(status_code=400, detail="Invalid appearance. Expected: light, dark, or system.")
        theme_code, theme_label = THEME_MAP[str(theme_input).strip()]
        existing_settings["appearance"] = theme_code
        existing_settings["theme"] = theme_label

    # Ensure canonical defaults for missing keys
    if "explanationLevel" not in existing_settings:
        existing_settings["explanationLevel"] = "standard"
        existing_settings["explanation_level"] = "Standard"
    if "analysisLength" not in existing_settings:
        existing_settings["analysisLength"] = "detailed"
        existing_settings["analysis_length"] = "Detailed"
    if "language" not in existing_settings:
        existing_settings["language"] = "en"
        existing_settings["lang_code"] = "en"
        existing_settings["display_language"] = "English"
    if "appearance" not in existing_settings:
        existing_settings["appearance"] = "system"
        existing_settings["theme"] = "System Default"

    existing_settings["updated_at"] = datetime.utcnow()

    db.users.update_one(
        {"_id": target_id},
        {"$set": {"settings": existing_settings}},
        upsert=True
    )
    
    return UserSettingsModel(
        explanationLevel=existing_settings["explanationLevel"],
        explanation_level=existing_settings.get("explanation_level", "Standard"),
        analysisLength=existing_settings["analysisLength"],
        analysis_length=existing_settings.get("analysis_length", "Detailed"),
        language=existing_settings["language"],
        lang_code=existing_settings.get("lang_code", "en"),
        appearance=existing_settings["appearance"],
        theme=existing_settings.get("theme", "System Default")
    )

@router.delete("/papers")
def delete_all_user_papers(current_user: dict = Depends(get_current_user)):
    """Deletes all uploaded research papers for the currently authenticated user."""
    db = get_db()
    user_id = current_user["id"]
    
    query = {"$or": [{"user_id": user_id}, {"userId": user_id}]}
    papers = list(db.papers.find(query))
    for paper in papers:
        paper_id = str(paper["_id"])
        try:
            delete_paper_chunks(paper_id)
        except Exception as e:
            print(f"Vector chunk cleanup warning for paper {paper_id}: {e}")
        try:
            db.conversations.delete_many({"$or": [{"paper_id": paper_id}, {"paperId": paper_id}]})
        except Exception:
            pass
        
    res = db.papers.delete_many(query)
    return {
        "message": "All uploaded papers have been deleted.",
        "count": res.deleted_count
    }

@router.delete("/history")
def clear_user_analysis_history(current_user: dict = Depends(get_current_user)):
    """Clears all paper analysis history and stored chat sessions for the user without deleting papers."""
    db = get_db()
    user_id = current_user["id"]
    
    query = {"$or": [{"user_id": user_id}, {"userId": user_id}]}
    res = db.conversations.delete_many(query)
    return {
        "message": "Your paper analysis history and stored chat sessions have been permanently cleared.",
        "count": res.deleted_count
    }

@router.get("/download-data")
def download_user_data(current_user: dict = Depends(get_current_user)):
    """Downloads personal account data, metadata, history, notes, and flashcards stored for the user."""
    db = get_db()
    user_id = current_user["id"]
    
    try:
        user_doc = db.users.find_one({"_id": ObjectId(user_id)}) if ObjectId.is_valid(user_id) else db.users.find_one({"_id": user_id})
    except Exception:
        user_doc = None

    email = user_doc.get("email", current_user.get("email", "user@local")) if user_doc else current_user.get("email", "user@local")
    full_name = user_doc.get("full_name", current_user.get("full_name", "Research User")) if user_doc else current_user.get("full_name", "Research User")
    settings = user_doc.get("settings", {}) if user_doc else {}

    user_papers = list(db.papers.find({"$or": [{"user_id": user_id}, {"userId": user_id}]}))
    user_convos = list(db.conversations.find({"$or": [{"user_id": user_id}, {"userId": user_id}]}))

    def sanitize_mongo_doc(doc: Any) -> Any:
        if isinstance(doc, dict):
            new_doc = {}
            for k, v in doc.items():
                if k == "_id":
                    new_doc["id"] = str(v)
                elif isinstance(v, datetime):
                    new_doc[k] = v.isoformat()
                elif isinstance(v, ObjectId):
                    new_doc[k] = str(v)
                else:
                    new_doc[k] = sanitize_mongo_doc(v)
            return new_doc
        elif isinstance(doc, list):
            return [sanitize_mongo_doc(item) for item in doc]
        elif isinstance(doc, datetime):
            return doc.isoformat()
        elif isinstance(doc, ObjectId):
            return str(doc)
        return doc

    clean_papers = sanitize_mongo_doc(user_papers)
    clean_convos = sanitize_mongo_doc(user_convos)

    study_notes = []
    flashcards = []
    saved_questions = []

    for p in clean_papers:
        if isinstance(p, dict):
            analysis = p.get("analysis", {})
            if isinstance(analysis, dict):
                if "notes" in analysis and analysis["notes"]:
                    study_notes.append({"paper_id": p.get("id"), "paper_title": p.get("title"), "notes": analysis["notes"]})
                if "flashcards" in analysis and analysis["flashcards"]:
                    flashcards.append({"paper_id": p.get("id"), "paper_title": p.get("title"), "flashcards": analysis["flashcards"]})
                if "questions" in analysis and analysis["questions"]:
                    saved_questions.append({"paper_id": p.get("id"), "paper_title": p.get("title"), "questions": analysis["questions"]})

    export_payload = {
        "disclaimer": "Binary PDF files are excluded from this JSON data export.",
        "application": "ResearchGPT Workspace",
        "export_timestamp": datetime.utcnow().isoformat(),
        "user_profile": {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "created_at": datetime.utcnow().isoformat(),
            "settings": settings
        },
        "uploaded_papers_count": len(clean_papers),
        "uploaded_papers": clean_papers,
        "chat_sessions_count": len(clean_convos),
        "chat_sessions": clean_convos,
        "study_notes": study_notes,
        "flashcards": flashcards,
        "saved_questions": saved_questions
    }
    
    return export_payload
