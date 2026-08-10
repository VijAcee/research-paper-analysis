from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from bson import ObjectId

from app.db import get_db
from app.auth import get_optional_user, get_current_user
from app.models.comparison import ComparisonRequest, ComparisonResponse
from app.services.openai_service import generate_paper_comparison
from app.routes.papers import get_client_ip_hash

router = APIRouter(prefix="/compare", tags=["Paper Comparison"])

def check_papers_accessibility(db, paper_ids: List[str], request: Request, user: Optional[dict]) -> List[dict]:
    """Ensures user has access to all the paper IDs they want to compare."""
    papers = []
    ip_hash = get_client_ip_hash(request)
    
    for pid in paper_ids:
        try:
            paper = db.papers.find_one({"_id": ObjectId(pid)})
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid paper ID: {pid}")
            
        if not paper:
            raise HTTPException(status_code=404, detail=f"Paper with ID {pid} not found")
            
        if paper.get("user_id") is not None:
            if not user or paper["user_id"] != user["id"]:
                raise HTTPException(status_code=403, detail=f"Access denied for paper: {paper['title']}")
        else:
            # Guest IP validation
            trial = db.free_trials.find_one({"ip_hash": ip_hash, "paper_id": pid})
            if not trial:
                raise HTTPException(status_code=403, detail=f"Session expired or unauthorized for paper: {paper['title']}")
                
        papers.append(paper)
    return papers

@router.post("", response_model=ComparisonResponse)
def compare_papers(
    body: ComparisonRequest,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    db = get_db()
    if len(body.paper_ids) < 2:
        raise HTTPException(status_code=400, detail="Comparison requires at least 2 papers.")
    if len(body.paper_ids) > 5:
        raise HTTPException(status_code=400, detail="Cannot compare more than 5 papers simultaneously.")
        
    # Check access to all selected papers
    papers = check_papers_accessibility(db, body.paper_ids, request, current_user)
    
    # Run OpenAI comparison service
    comp_result = generate_paper_comparison(papers)
    
    user_id = current_user["id"] if current_user else "anonymous"
    
    comparison_doc = {
        "user_id": user_id,
        "paper_ids": body.paper_ids,
        "title": comp_result["title"],
        "matrix": comp_result.get("matrix", []),
        "detailed_analysis": comp_result["detailed_analysis"],
        "conclusion": comp_result["conclusion"],
        "created_at": datetime.utcnow()
    }
    
    res = db.comparisons.insert_one(comparison_doc)
    comparison_doc["id"] = str(res.inserted_id)
    return ComparisonResponse(**comparison_doc)

@router.get("/history", response_model=List[ComparisonResponse])
def get_comparison_history(current_user: dict = Depends(get_current_user)):
    """Lists past comparisons for the user (only available to registered accounts)."""
    db = get_db()
    comparisons = list(db.comparisons.find({"user_id": current_user["id"]}).sort("created_at", -1))
    
    response = []
    for c in comparisons:
        c["id"] = str(c["_id"])
        response.append(ComparisonResponse(**c))
    return response

@router.get("/{comparison_id}", response_model=ComparisonResponse)
def get_comparison(comparison_id: str, request: Request, current_user: Optional[dict] = Depends(get_optional_user)):
    db = get_db()
    try:
        comp = db.comparisons.find_one({"_id": ObjectId(comparison_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Comparison not found")
        
    if not comp:
        raise HTTPException(status_code=404, detail="Comparison not found")
        
    # Accessibility checks
    if comp.get("user_id") != "anonymous":
        if not current_user or comp["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Unauthorized access to comparison record")
    else:
        # If anonymous comparison, verify the caller has access to at least one of the papers in it
        check_papers_accessibility(db, comp["paper_ids"][:1], request, current_user)
        
    comp["id"] = str(comp["_id"])
    return ComparisonResponse(**comp)

@router.delete("/{comparison_id}")
def delete_comparison(comparison_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        comp = db.comparisons.find_one({"_id": ObjectId(comparison_id), "user_id": current_user["id"]})
    except Exception:
        raise HTTPException(status_code=404, detail="Comparison not found")
        
    if not comp:
        raise HTTPException(status_code=404, detail="Comparison not found or unauthorized to delete")
        
    db.comparisons.delete_one({"_id": ObjectId(comparison_id)})
    return {"message": "Comparison entry removed successfully."}
