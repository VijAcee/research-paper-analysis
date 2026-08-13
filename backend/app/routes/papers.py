import hashlib
import requests
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, status
from bson import ObjectId

from app.db import get_db
from app.auth import get_optional_user, get_current_user
from app.models.paper import (
    PaperDetailResponse, 
    PaperListResponse, 
    URLUploadRequest, 
    TextUploadRequest
)
from app.services.pdf_parser import extract_pdf_content
from app.services.vector_store import index_paper_chunks, delete_paper_chunks
from app.services.openai_service import generate_paper_analysis

router = APIRouter(prefix="/papers", tags=["Papers"])

def get_client_ip_hash(request: Request) -> str:
    """Computes a SHA-256 hash of the client's IP address for anonymous rate limiting."""
    ip = "127.0.0.1"
    # Read potential reverse-proxy header first (for Colab / tunnel deployments)
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    return hashlib.sha256(ip.encode()).hexdigest()

def verify_upload_allowance(request: Request, user: Optional[dict]) -> str:
    """
    Checks if upload is permitted.
    If authenticated, uploads are allowed.
    If guest (anonymous), allows only 1 free upload per IP hash.
    Returns the ip_hash if guest, or empty string if authenticated.
    """
    if user:
        return "" # Authenticated user, bypass limit
        
    db = get_db()
    ip_hash = get_client_ip_hash(request)
    
    trial = db.free_trials.find_one({"ip_hash": ip_hash})
    if trial:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Free analysis trial consumed. Please create an account to upload more papers."
        )
    return ip_hash

def process_and_save_paper(
    title: str,
    authors: List[str],
    abstract: str,
    raw_text: str,
    pages: List[dict],
    user_id: Optional[str] = None,
    file_name: Optional[str] = None,
    file_size: Optional[int] = None,
    source_url: Optional[str] = None
) -> dict:
    """Parses text, chunks into vector DB, performs AI analysis, and saves to MongoDB."""
    db = get_db()
    
    # 1. Insert initial document to get an ID
    paper_doc = {
        "user_id": user_id,
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "file_name": file_name,
        "file_size": file_size,
        "source_url": source_url,
        "created_at": datetime.utcnow(),
        "analysis": None
    }
    
    res = db.papers.insert_one(paper_doc)
    paper_id = str(res.inserted_id)
    
    # 2. Chunk text and index in ChromaDB
    indexed = index_paper_chunks(paper_id, pages)
    if not indexed:
        db.papers.delete_one({"_id": ObjectId(paper_id)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to index document content inside semantic vector database."
        )
        
    # 3. Generate structured AI research analysis reading user settings
    try:
        user_settings = None
        if user_id:
            user_doc = db.users.find_one({"_id": ObjectId(user_id)})
            if user_doc and "settings" in user_doc:
                user_settings = user_doc["settings"]

        analysis_data = generate_paper_analysis(title, raw_text, abstract, user_settings=user_settings)
        # Store as dict inside Mongo
        db.papers.update_one(
            {"_id": ObjectId(paper_id)},
            {"$set": {"analysis": analysis_data.model_dump()}}
        )
        paper_doc["analysis"] = analysis_data
    except Exception as e:
        print(f"Warning: AI analysis failed: {e}")
        # Save as empty analysis details so UI doesn't crash
        pass
        
    paper_doc["id"] = paper_id
    if "_id" in paper_doc:
        del paper_doc["_id"]
        
    return paper_doc

@router.post("/upload/file", response_model=PaperDetailResponse)
def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: Optional[dict] = Depends(get_optional_user)
):
    ip_hash = verify_upload_allowance(request, current_user)
    
    try:
        content = file.file.read()
        file_size = len(content)
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to read upload file stream.")
        
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are supported currently.")
        
    # Parse PDF
    parsed = extract_pdf_content(content)
    
    user_id = current_user["id"] if current_user else None
    
    # Process
    paper = process_and_save_paper(
        title=parsed["title"],
        authors=parsed["authors"],
        abstract=parsed["abstract"],
        raw_text=parsed["raw_text"],
        pages=parsed["pages"],
        user_id=user_id,
        file_name=file.filename,
        file_size=file_size
    )
    
    # If anonymous guest, record trial consumption
    if ip_hash:
        db = get_db()
        db.free_trials.insert_one({
            "ip_hash": ip_hash,
            "paper_id": paper["id"],
            "used_at": datetime.utcnow()
        })
        
    return paper

@router.post("/upload/url", response_model=PaperDetailResponse)
def upload_url(
    request: Request,
    body: URLUploadRequest,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    ip_hash = verify_upload_allowance(request, current_user)
    
    # Download file
    try:
        res = requests.get(body.url, timeout=25)
        if res.status_code != 200:
            raise Exception(f"Server returned status {res.status_code}")
        content = res.content
        file_size = len(content)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download PDF from URL: {str(e)}"
        )
        
    # Extract file name from URL
    file_name = body.url.split("/")[-1] or "downloaded_paper.pdf"
    if not file_name.endswith(".pdf"):
        file_name += ".pdf"
        
    parsed = extract_pdf_content(content)
    user_id = current_user["id"] if current_user else None
    
    paper = process_and_save_paper(
        title=parsed["title"],
        authors=parsed["authors"],
        abstract=parsed["abstract"],
        raw_text=parsed["raw_text"],
        pages=parsed["pages"],
        user_id=user_id,
        file_name=file_name,
        file_size=file_size,
        source_url=body.url
    )
    
    if ip_hash:
        db = get_db()
        db.free_trials.insert_one({
            "ip_hash": ip_hash,
            "paper_id": paper["id"],
            "used_at": datetime.utcnow()
        })
        
    return paper

@router.post("/upload/text", response_model=PaperDetailResponse)
def upload_text(
    request: Request,
    body: TextUploadRequest,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    ip_hash = verify_upload_allowance(request, current_user)
    
    user_id = current_user["id"] if current_user else None
    authors_list = [a.strip() for a in body.authors.split(",")] if body.authors else ["Authors Unspecified"]
    
    # Process text into pages (chunk it manually for indexer)
    words = body.text.split()
    page_chunks = []
    # Arbitrary page splits (approx 500 words per page)
    words_per_page = 500
    for idx, i in enumerate(range(0, len(words), words_per_page)):
        page_chunks.append({
            "page_number": idx + 1,
            "text": " ".join(words[i:i+words_per_page])
        })
        
    abstract_text = body.text[:500] + "..." if len(body.text) > 500 else body.text
    
    paper = process_and_save_paper(
        title=body.title,
        authors=authors_list,
        abstract=abstract_text,
        raw_text=body.text,
        pages=page_chunks,
        user_id=user_id,
        file_name="Pasted_Text",
        file_size=len(body.text.encode('utf-8'))
    )
    
    if ip_hash:
        db = get_db()
        db.free_trials.insert_one({
            "ip_hash": ip_hash,
            "paper_id": paper["id"],
            "used_at": datetime.utcnow()
        })
        
    return paper

@router.get("", response_model=List[PaperListResponse])
def list_papers(current_user: dict = Depends(get_current_user)):
    db = get_db()
    papers = list(db.papers.find({"user_id": current_user["id"]}).sort("created_at", -1))
    
    response = []
    for p in papers:
        response.append({
            "id": str(p["_id"]),
            "title": p["title"],
            "authors": p.get("authors", []),
            "file_name": p.get("file_name"),
            "created_at": p["created_at"]
        })
    return response

@router.get("/{paper_id}", response_model=PaperDetailResponse)
def get_paper(paper_id: str, request: Request, current_user: Optional[dict] = Depends(get_optional_user)):
    db = get_db()
    try:
        paper = db.papers.find_one({"_id": ObjectId(paper_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Paper not found")
        
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
        
    # Check accessibility:
    # 1. If paper belongs to this user: OK
    # 2. If paper is a guest paper (user_id is None) and this request comes from the guest who just uploaded it:
    #    Let's check if the current IP hash matches the guest trial hash recorded for this paper.
    if paper.get("user_id") is not None:
        if not current_user or paper["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied. You do not own this research paper.")
    else:
        # Check IP hash
        ip_hash = get_client_ip_hash(request)
        trial = db.free_trials.find_one({"ip_hash": ip_hash, "paper_id": paper_id})
        if not trial:
            raise HTTPException(status_code=403, detail="Free analysis session expired. Please sign in to save your files.")
            
    paper["id"] = str(paper["_id"])
    return paper

@router.delete("/{paper_id}")
def delete_paper(paper_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        paper = db.papers.find_one({"_id": ObjectId(paper_id), "user_id": current_user["id"]})
    except Exception:
        raise HTTPException(status_code=404, detail="Paper not found")
        
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found or unauthorized to delete")
        
    # Delete from ChromaDB
    delete_paper_chunks(paper_id)
    
    # Delete from MongoDB
    db.papers.delete_one({"_id": ObjectId(paper_id)})
    
    # Clean up associated chats
    db.conversations.delete_many({"paper_id": paper_id})
    
    return {"message": "Paper and all related chat sessions deleted successfully."}

@router.post("/{paper_id}/reanalyze", response_model=PaperDetailResponse)
def reanalyze_paper(paper_id: str, current_user: dict = Depends(get_current_user)):
    """Re-generates AI research analysis for an existing paper using current user settings."""
    db = get_db()
    try:
        paper = db.papers.find_one({"_id": ObjectId(paper_id), "user_id": current_user["id"]})
    except Exception:
        raise HTTPException(status_code=404, detail="Paper not found")
        
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found or unauthorized")

    user_doc = db.users.find_one({"_id": ObjectId(current_user["id"])})
    user_settings = user_doc.get("settings", {}) if user_doc else {}

    title = paper.get("title", "Research Paper")
    abstract = paper.get("abstract", "")
    
    # Retrieve indexed chunks text or abstract
    from app.services.vector_store import query_paper_chunks
    chunks = query_paper_chunks(paper_id, query_text="background methodology results findings", top_k=8)
    raw_text = "\n\n".join([c["text"] for c in chunks]) if chunks else abstract

    analysis_data = generate_paper_analysis(title, raw_text, abstract, user_settings=user_settings)

    db.papers.update_one(
        {"_id": ObjectId(paper_id)},
        {"$set": {"analysis": analysis_data.model_dump()}}
    )
    
    paper["analysis"] = analysis_data
    paper["id"] = str(paper["_id"])
    return paper

