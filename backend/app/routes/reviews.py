from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from bson import ObjectId

from app.db import get_db
from app.auth import get_optional_user, get_current_user
from app.models.review import LiteratureReviewRequest, LiteratureReviewResponse
from app.services.openai_service import generate_literature_review
from app.routes.compare import check_papers_accessibility

router = APIRouter(prefix="/reviews", tags=["Literature Reviews"])

@router.post("", response_model=LiteratureReviewResponse)
def generate_review(
    body: LiteratureReviewRequest,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    db = get_db()
    if len(body.paper_ids) < 2:
        raise HTTPException(status_code=400, detail="Literature review requires at least 2 papers.")
    if len(body.paper_ids) > 10:
        raise HTTPException(status_code=400, detail="Cannot synthesize more than 10 papers in a single review.")
        
    # Check access to all selected papers
    papers = check_papers_accessibility(db, body.paper_ids, request, current_user)
    
    # Run OpenAI literature review synthesis service
    review_result = generate_literature_review(papers, custom_title=body.title)
    
    user_id = current_user["id"] if current_user else "anonymous"
    
    review_doc = {
        "user_id": user_id,
        "paper_ids": body.paper_ids,
        "title": review_result["title"],
        "content": review_result["content"],
        "created_at": datetime.utcnow()
    }
    
    res = db.reviews.insert_one(review_doc)
    review_doc["id"] = str(res.inserted_id)
    return LiteratureReviewResponse(**review_doc)

@router.get("/history", response_model=List[LiteratureReviewResponse])
def get_review_history(current_user: dict = Depends(get_current_user)):
    """Lists past literature reviews (registered users only)."""
    db = get_db()
    reviews = list(db.reviews.find({"user_id": current_user["id"]}).sort("created_at", -1))
    
    response = []
    for r in reviews:
        r["id"] = str(r["_id"])
        response.append(LiteratureReviewResponse(**r))
    return response

@router.get("/{review_id}", response_model=LiteratureReviewResponse)
def get_review(review_id: str, request: Request, current_user: Optional[dict] = Depends(get_optional_user)):
    db = get_db()
    try:
        review = db.reviews.find_one({"_id": ObjectId(review_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Literature review not found")
        
    if not review:
        raise HTTPException(status_code=404, detail="Literature review not found")
        
    # Check accessibility
    if review.get("user_id") != "anonymous":
        if not current_user or review["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Unauthorized access to literature review record")
    else:
        # Verify access for at least one paper
        check_papers_accessibility(db, review["paper_ids"][:1], request, current_user)
        
    review["id"] = str(review["_id"])
    return LiteratureReviewResponse(**review)

@router.delete("/{review_id}")
def delete_review(review_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    try:
        review = db.reviews.find_one({"_id": ObjectId(review_id), "user_id": current_user["id"]})
    except Exception:
        raise HTTPException(status_code=404, detail="Literature review not found")
        
    if not review:
        raise HTTPException(status_code=404, detail="Literature review not found or unauthorized to delete")
        
    db.reviews.delete_one({"_id": ObjectId(review_id)})
    return {"message": "Literature review entry removed successfully."}
