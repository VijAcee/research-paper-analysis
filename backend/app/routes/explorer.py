from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from pydantic import BaseModel

from app.db import get_db
from app.auth import get_current_user
from app.models.paper import BookmarkCreate, BookmarkResponse
from app.services.academic_search import search_related_papers, summarize_external_paper

router = APIRouter(prefix="/explorer", tags=["Academic Explorer"])

class ExternalSummaryRequest(BaseModel):
    title: str
    abstract: str

@router.get("/search")
def search_explorer(query: str, limit: Optional[int] = 8):
    """
    Searches external archives (arXiv and Semantic Scholar) for relevant academic work.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
        
    papers = search_related_papers(query, limit=limit)
    return papers

@router.post("/summarize")
def summarize_external(body: ExternalSummaryRequest):
    """
    Generates a quick summary of a discovered external paper without uploading it first.
    """
    summary = summarize_external_paper(body.title, body.abstract)
    return {"summary": summary}

@router.post("/bookmarks", response_model=BookmarkResponse)
def add_bookmark(body: BookmarkCreate, current_user: dict = Depends(get_current_user)):
    """
    Saves a paper (either uploaded locally or discovered via search) to the user's bookmarks list.
    """
    db = get_db()
    
    # Check if already bookmarked
    existing = db.bookmarks.find_one({
        "user_id": current_user["id"],
        "title": body.title
    })
    
    if existing:
        existing["id"] = str(existing["_id"])
        return BookmarkResponse(**existing)
        
    bookmark_doc = {
        "user_id": current_user["id"],
        "paper_id": body.paper_id,
        "external_id": body.external_id,
        "title": body.title,
        "authors": body.authors,
        "abstract": body.abstract,
        "url": body.url,
        "source": body.source,
        "publication_year": body.publication_year,
        "created_at": datetime.utcnow()
    }
    
    res = db.bookmarks.insert_one(bookmark_doc)
    bookmark_doc["id"] = str(res.inserted_id)
    return BookmarkResponse(**bookmark_doc)

@router.get("/bookmarks", response_model=List[BookmarkResponse])
def list_bookmarks(current_user: dict = Depends(get_current_user)):
    """
    Lists all bookmarks saved by the authenticated user.
    """
    db = get_db()
    bookmarks = list(db.bookmarks.find({"user_id": current_user["id"]}).sort("created_at", -1))
    
    response = []
    for b in bookmarks:
        b["id"] = str(b["_id"])
        response.append(BookmarkResponse(**b))
    return response

@router.delete("/bookmarks/{bookmark_id}")
def remove_bookmark(bookmark_id: str, current_user: dict = Depends(get_current_user)):
    """
    Removes a bookmarked paper from the database.
    """
    db = get_db()
    try:
        bookmark = db.bookmarks.find_one({"_id": ObjectId(bookmark_id), "user_id": current_user["id"]})
    except Exception:
        raise HTTPException(status_code=404, detail="Bookmark not found")
        
    if not bookmark:
        raise HTTPException(status_code=404, detail="Bookmark not found or unauthorized to delete")
        
    db.bookmarks.delete_one({"_id": ObjectId(bookmark_id)})
    return {"message": "Paper bookmark removed successfully."}
