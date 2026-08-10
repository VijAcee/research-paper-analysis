from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from bson import ObjectId
from typing import Optional
import io
import urllib.parse

from app.db import get_db
from app.auth import get_optional_user, get_current_user
from app.services.exporter import (
    generate_citations, 
    export_as_markdown, 
    export_as_text, 
    export_as_docx, 
    export_as_pdf
)
from app.routes.papers import get_client_ip_hash
from app.routes.chat import verify_paper_access
from app.routes.compare import check_papers_accessibility

router = APIRouter(prefix="/exports", tags=["Exports & Citations"])

def build_file_response(title: str, sections: dict, file_format: str) -> StreamingResponse:
    """Helper to convert structured content sections into a file streaming response."""
    file_format = file_format.lower().strip()
    
    # URL encode filename for safe headers
    safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)[:50]
    
    if file_format == "md":
        content = export_as_markdown(title, sections)
        response = StreamingResponse(io.BytesIO(content.encode('utf-8')), media_type="text/markdown")
        response.headers["Content-Disposition"] = f"attachment; filename={safe_title}.md"
        return response
        
    elif file_format == "txt":
        content = export_as_text(title, sections)
        response = StreamingResponse(io.BytesIO(content.encode('utf-8')), media_type="text/plain")
        response.headers["Content-Disposition"] = f"attachment; filename={safe_title}.txt"
        return response
        
    elif file_format == "docx":
        try:
            content = export_as_docx(title, sections)
            response = StreamingResponse(io.BytesIO(content), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            response.headers["Content-Disposition"] = f"attachment; filename={safe_title}.docx"
            return response
        except ImportError:
            raise HTTPException(status_code=500, detail="Word export is unavailable. python-docx is not installed.")
            
    elif file_format == "pdf":
        try:
            content = export_as_pdf(title, sections)
            response = StreamingResponse(io.BytesIO(content), media_type="application/pdf")
            response.headers["Content-Disposition"] = f"attachment; filename={safe_title}.pdf"
            return response
        except ImportError:
            raise HTTPException(status_code=500, detail="PDF export is unavailable. ReportLab is not installed.")
            
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported export format: {file_format}")

import re # needed in regex clean

@router.get("/paper/{paper_id}/summary")
def export_paper_summary(
    paper_id: str,
    format: str = "md",
    request: Request = None,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    db = get_db()
    # Check paper permissions
    paper = verify_paper_access(db, paper_id, request, current_user)
    
    analysis = paper.get("analysis")
    if not analysis:
        raise HTTPException(status_code=400, detail="No AI summary generated for this paper yet.")
        
    # Compile sections to export
    sections = {
        "Executive Summary": analysis.get("executive_summary", ""),
        "Research Objective": analysis.get("research_objective", ""),
        "Problem Statement": analysis.get("problem_statement", ""),
        "Methodology": analysis.get("methodology", ""),
        "Datasets": analysis.get("dataset_information", ""),
        "Key Findings": analysis.get("key_findings", []),
        "Contributions": analysis.get("major_contributions", []),
        "Advantages": analysis.get("advantages", []),
        "Limitations": analysis.get("limitations", []),
        "Prerequisite Knowledge": analysis.get("prerequisite_knowledge", [])
    }
    
    return build_file_response(f"AI Summary: {paper['title']}", sections, format)

@router.get("/chat/{conversation_id}")
def export_chat(
    conversation_id: str,
    format: str = "md",
    request: Request = None,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    db = get_db()
    try:
        convo = db.conversations.find_one({"_id": ObjectId(conversation_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
        
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    # Check permission
    verify_paper_access(db, convo["paper_id"], request, current_user)
    
    messages = convo.get("messages", [])
    chat_log = []
    for msg in messages:
        role_label = "User" if msg["role"] == "user" else "PaperLens"
        timestamp = msg["timestamp"].strftime("%Y-%m-%d %H:%M") if isinstance(msg.get("timestamp"), datetime) else ""
        chat_log.append(f"[{timestamp}] {role_label}:\n{msg['content']}\n")
        
    sections = {
        "Chat Transcript": "\n".join(chat_log)
    }
    
    return build_file_response(f"Chat Transcript: {convo['title']}", sections, format)

@router.get("/review/{review_id}")
def export_review(
    review_id: str,
    format: str = "md",
    request: Request = None,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    db = get_db()
    try:
        review = db.reviews.find_one({"_id": ObjectId(review_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID")
        
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
        
    # Check permissions
    if review.get("user_id") != "anonymous":
        if not current_user or review["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Unauthorized review access")
    else:
        check_papers_accessibility(db, review["paper_ids"][:1], request, current_user)
        
    sections = {
        "Literature Review Draft": review["content"]
    }
    
    return build_file_response(review["title"], sections, format)

@router.get("/compare/{comparison_id}")
def export_comparison(
    comparison_id: str,
    format: str = "md",
    request: Request = None,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    db = get_db()
    try:
        comp = db.comparisons.find_one({"_id": ObjectId(comparison_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid comparison ID")
        
    if not comp:
        raise HTTPException(status_code=404, detail="Comparison report not found")
        
    # Permissions
    if comp.get("user_id") != "anonymous":
        if not current_user or comp["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Unauthorized comparison access")
    else:
        check_papers_accessibility(db, comp["paper_ids"][:1], request, current_user)
        
    sections = {
        "Detailed Comparative Analysis": comp["detailed_analysis"],
        "Conclusion": comp["conclusion"]
    }
    
    return build_file_response(comp["title"], sections, format)

@router.get("/citations/{paper_id}")
def get_paper_citations(
    paper_id: str,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """Generates formatted citations for a research paper in multiple formats."""
    db = get_db()
    paper = verify_paper_access(db, paper_id, request, current_user)
    
    # Gather metadata fields for bibliography builders
    title = paper["title"]
    authors = paper.get("authors", [])
    
    # Try to extract publication year from analysis keywords or metadata
    year = None
    created = paper.get("created_at")
    if isinstance(created, datetime):
        year = created.year
        
    # Build standard response
    citations = generate_citations(
        title=title,
        authors=authors,
        year=year,
        journal=paper.get("file_name", "Academic Resource") if paper.get("file_name") != "Pasted_Text" else "Research Workspace Document",
        url=paper.get("source_url")
    )
    return citations
