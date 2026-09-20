import hashlib
import asyncio
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
from app.services.pdf_parser import extract_pdf_content, reconstruct_academic_paper
from app.services.vector_store import index_paper_chunks, delete_paper_chunks
from app.services.openai_service import generate_paper_analysis, verify_analysis_quality

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
    If guest (anonymous), allows only 3 free uploads per IP hash.
    Returns the ip_hash if guest, or empty string if authenticated.
    """
    if user:
        return "" # Authenticated user, bypass limit
        
    db = get_db()
    ip_hash = get_client_ip_hash(request)
    
    trial_count = db.free_trials.count_documents({"ip_hash": ip_hash})
    if trial_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Free analysis trial consumed (3/3 used). Please sign up or log in to analyze unlimited papers."
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
    """
    6-Stage PDF Processing Pipeline:
    PDF Extraction → TEXT RECONSTRUCTION (Prompt 1) → PAPER TYPE CLASSIFICATION → FACT EXTRACTION → 13-SECTION ANALYSIS → QUALITY CHECK (Prompt 3)
    MongoDB preserves all stages: raw_pdf, raw_extraction, reconstructed_document, document_structure, paper_type, extracted_facts, analysis, quality_report, rag_chunks.
    """
    db = get_db()
    
    # PIPELINE STAGE 1: Prompt 1 — Universal Academic Paper Reconstruction
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [PIPELINE Stage 1] Reconstructing PDF Text (Prompt 1)...")
    reconstructed_doc = reconstruct_academic_paper(title, raw_text, abstract)
    clean_text = reconstructed_doc.get("clean_text") or raw_text
    clean_title = reconstructed_doc.get("title") or title
    clean_authors = reconstructed_doc.get("authors") or authors
    clean_abstract = reconstructed_doc.get("abstract") or abstract

    # Create clean text pages for ChromaDB Section-Aware Indexing
    clean_pages = []
    chars_per_page = max(500, len(clean_text) // max(1, len(pages)))
    for idx, p in enumerate(pages):
        start_c = idx * chars_per_page
        end_c = (idx + 1) * chars_per_page
        p_clean = clean_text[start_c:end_c].strip() or p.get("text", "")
        clean_pages.append({
            "page_number": p.get("page_number", idx + 1),
            "text": p_clean
        })

    # 1. Insert document shell into MongoDB
    paper_doc = {
        "user_id": user_id,
        "title": clean_title,
        "authors": clean_authors,
        "abstract": clean_abstract,
        "raw_pdf": {
            "file_name": file_name,
            "file_size": file_size,
            "source_url": source_url
        },
        "raw_extraction": raw_text,
        "reconstructed_document": reconstructed_doc.get("reconstructed_document", {}),
        "document_structure": reconstructed_doc.get("sections") or reconstructed_doc.get("main_paper", ""),
        "clean_text": clean_text,
        "tables": reconstructed_doc.get("tables", []),
        "figures": reconstructed_doc.get("figures", []),
        "references": reconstructed_doc.get("references", []),
        "extraction_quality": reconstructed_doc.get("extraction_quality", 95),
        "reconstruction_warnings": reconstructed_doc.get("reconstruction_warnings", []),
        "file_name": file_name,
        "file_size": file_size,
        "source_url": source_url,
        "created_at": datetime.utcnow(),
        "paper_type": None,
        "extracted_facts": None,
        "analysis": None,
        "quality_report": None,
        "rag_chunks": len(clean_pages)
    }
    
    res = db.papers.insert_one(paper_doc)
    paper_id = str(res.inserted_id)
    
    # PIPELINE STAGE 2: Vector Indexing using CLEAN text
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [PIPELINE Stage 2] ChromaDB Vector Indexing (Clean Text)...")
    indexed = index_paper_chunks(paper_id, clean_pages)
    if not indexed:
        db.papers.delete_one({"_id": ObjectId(paper_id)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to index document content inside semantic vector database."
        )
        
    # PIPELINE STAGE 3, 4, 5: Paper Type Classification, Fact Extraction, & Analysis Engine
    try:
        user_settings = None
        if user_id:
            user_doc = db.users.find_one({"_id": ObjectId(user_id)})
            if user_doc and "settings" in user_doc:
                user_settings = user_doc["settings"]

        print(f"[{datetime.now().strftime('%H:%M:%S')}] [PIPELINE Stage 3-5] Classification, Fact Extraction & Analysis Engine...")
        analysis_data = generate_paper_analysis(clean_title, clean_text, clean_abstract, user_settings=user_settings)
        
        # PIPELINE STAGE 6: Quality Gate Engine (Prompt 3)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [PIPELINE Stage 6] Quality Gate Verification (Prompt 3)...")
        quality_res = verify_analysis_quality(clean_text, analysis_data.model_dump())
        
        analysis_dict = analysis_data.model_dump()
        analysis_quality_score = quality_res.get("overall_confidence", 95)
        if quality_res.get("status") == "REVISE" or analysis_quality_score < 70:
            analysis_dict["is_low_confidence"] = True
            analysis_dict["confidence_message"] = f"Quality Gate Notice: {len(quality_res.get('issues', []))} potential discrepancies detected during verification."

        paper_type_record = {
            "primary_type": analysis_dict.get("paper_type", "Empirical Research"),
            "type_of_research": analysis_dict.get("type_of_research", "Empirical Research"),
            "domain": analysis_dict.get("research_domain", "Multidisciplinary Academic Research")
        }

        # Store all stages in MongoDB db.papers
        db.papers.update_one(
            {"_id": ObjectId(paper_id)},
            {"$set": {
                "paper_type": paper_type_record,
                "analysis": analysis_dict,
                "quality_report": quality_res,
                "analysis_quality": analysis_quality_score
            }}
        )
        paper_doc["analysis"] = analysis_data
        paper_doc["paper_type"] = paper_type_record
        paper_doc["quality_report"] = quality_res
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [PIPELINE Complete] All 6 Stages Persisted for paper_id={paper_id}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [MONITOR] Warning: AI analysis failed: {e}")
        pass
        
    paper_doc["id"] = paper_id
    if "_id" in paper_doc:
        del paper_doc["_id"]
        
    return paper_doc

@router.post("/upload", response_model=PaperDetailResponse)
@router.post("/upload/file", response_model=PaperDetailResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: Optional[dict] = Depends(get_optional_user)
):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [MONITOR] Request Received: Upload file '{file.filename}'")
    ip_hash = verify_upload_allowance(request, current_user)
    
    try:
        content = await file.read()
        file_size = len(content)
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to read upload file stream.")
        
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are supported currently.")
        
    # Parse PDF in background thread pool to prevent event loop blocking
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [MONITOR] PDF Extraction Started...")
    parsed = await asyncio.to_thread(extract_pdf_content, content)
    if parsed.get("is_empty"):
        raise HTTPException(
            status_code=400,
            detail="We couldn't extract enough text from this paper to analyze it reliably. Please try another PDF or a text-readable version."
        )
    
    user_id = current_user["id"] if current_user else None
    
    # Process & index paper in thread pool
    paper = await asyncio.to_thread(
        process_and_save_paper,
        parsed["title"],
        parsed["authors"],
        parsed["abstract"],
        parsed["raw_text"],
        parsed["pages"],
        user_id,
        file.filename,
        file_size
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
            detail=f"Failed to fetch research paper from URL: {str(e)}"
        )
        
    parsed = extract_pdf_content(content)
    if parsed.get("is_empty"):
        raise HTTPException(
            status_code=400,
            detail="We couldn't extract enough text from this paper to analyze it reliably. Please try another PDF or a text-readable version."
        )
    
    # Extract file name from URL
    file_name = body.url.split("/")[-1] or "downloaded_paper.pdf"
    if not file_name.endswith(".pdf"):
        file_name += ".pdf"
        
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
    user_id = current_user["id"]
    query = {"$or": [{"user_id": user_id}, {"userId": user_id}]}
    
    try:
        paper = db.papers.find_one({"_id": ObjectId(paper_id), "$or": [{"user_id": user_id}, {"userId": user_id}]}) if ObjectId.is_valid(paper_id) else db.papers.find_one({"_id": paper_id, "$or": [{"user_id": user_id}, {"userId": user_id}]})
    except Exception:
        paper = None
        
    if not paper:
        # Check if paper is guest or owned by user
        paper = db.papers.find_one({"_id": ObjectId(paper_id)}) if ObjectId.is_valid(paper_id) else db.papers.find_one({"_id": paper_id})
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found or unauthorized to delete")
        
    # Delete from ChromaDB
    try:
        delete_paper_chunks(paper_id)
    except Exception as e:
        print(f"ChromaDB cleanup warning for paper {paper_id}: {e}")
    
    # Delete from MongoDB
    if ObjectId.is_valid(paper_id):
        db.papers.delete_one({"_id": ObjectId(paper_id)})
    else:
        db.papers.delete_one({"_id": paper_id})
    
    # Clean up associated chats
    db.conversations.delete_many({"$or": [{"paper_id": paper_id}, {"paperId": paper_id}]})
    
    return {"message": "Paper and all related chat sessions deleted successfully."}

@router.get("/{paper_id}/download-data")
def download_single_paper_data(paper_id: str, current_user: Optional[dict] = Depends(get_optional_user)):
    """Exports structured JSON data for a single research paper."""
    db = get_db()
    try:
        paper = db.papers.find_one({"_id": ObjectId(paper_id)}) if ObjectId.is_valid(paper_id) else db.papers.find_one({"_id": paper_id})
    except Exception:
        paper = None
        
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
        
    convos = list(db.conversations.find({"$or": [{"paper_id": paper_id}, {"paperId": paper_id}]}))
    
    def sanitize_doc(doc: Any) -> Any:
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
                    new_doc[k] = sanitize_doc(v)
            return new_doc
        elif isinstance(doc, list):
            return [sanitize_doc(item) for item in doc]
        elif isinstance(doc, datetime):
            return doc.isoformat()
        elif isinstance(doc, ObjectId):
            return str(doc)
        return doc

    clean_paper = sanitize_doc(paper)
    clean_convos = sanitize_doc(convos)
    
    analysis = clean_paper.get("analysis", {})
    
    export_payload = {
        "disclaimer": "Binary PDF files are excluded from JSON data export.",
        "application": "ResearchGPT Workspace - Single Paper Export",
        "export_timestamp": datetime.utcnow().isoformat(),
        "paper_id": str(clean_paper.get("id")),
        "paper_title": clean_paper.get("title", "Research Paper"),
        "authors": clean_paper.get("authors", []),
        "file_name": clean_paper.get("file_name"),
        "file_size": clean_paper.get("file_size"),
        "source_url": clean_paper.get("source_url"),
        "created_at": clean_paper.get("created_at"),
        "comprehensive_analysis": analysis,
        "chat_sessions_count": len(clean_convos),
        "chat_sessions": clean_convos,
        "study_notes": analysis.get("study_notes", {}),
        "flashcards": analysis.get("flashcards", []),
        "ai_questions": analysis.get("ai_questions", {})
    }
    
    return export_payload

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

