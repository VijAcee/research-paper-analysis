from datetime import datetime, timedelta
import secrets
import re
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId

from app.config import settings
from app.db import get_db
from app.auth import (
    get_password_hash, 
    verify_password, 
    create_access_token, 
    create_refresh_token,
    decode_token, 
    get_current_user
)
from app.models.auth import (
    UserRegister, 
    UserLogin, 
    UserResponse, 
    TokenResponse, 
    TokenRefreshRequest, 
    PasswordResetRequest,
    UserUpdateRequest,
    ChangePasswordRequest
)
from app.services.vector_store import delete_paper_chunks

router = APIRouter(prefix="/auth", tags=["Authentication"])

def validate_strong_password(password: str, user_email: str, user_name: str = "", password_history: list = None):
    """Enforces 12-character strong password requirements & 5-password history check."""
    if len(password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters long.")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one lowercase letter.")
    if not re.search(r"[0-9]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one number.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one special character.")
    
    # Name / Email substring check
    email_name = user_email.split("@")[0].lower()
    if email_name and email_name in password.lower():
        raise HTTPException(status_code=400, detail="Password cannot contain your email username.")
    if user_name and len(user_name) >= 3 and user_name.lower() in password.lower():
        raise HTTPException(status_code=400, detail="Password cannot contain your name.")
    
    # Password history check (last 5 passwords)
    if password_history:
        for old_hash in password_history[-5:]:
            if verify_password(password, old_hash):
                raise HTTPException(status_code=400, detail="New password cannot match any of your last 5 passwords.")

@router.post("/register")
def register(user_in: UserRegister):
    db = get_db()
    email_clean = user_in.email.strip().lower()
    if db.users.find_one({"email": email_clean}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists. Please sign in instead."
        )
    
    role = "admin" if email_clean.startswith("admin@") else "user"
    full_name = user_in.full_name or email_clean.split("@")[0].capitalize()
    hashed_pwd = get_password_hash(user_in.password)
    
    new_user = {
        "email": email_clean,
        "hashed_password": hashed_pwd,
        "full_name": full_name,
        "role": role,
        "is_verified": True,
        "password_history": [hashed_pwd],
        "settings": {
            "explanation_level": "Standard",
            "analysis_length": "Detailed",
            "language": "English",
            "theme": "System Default"
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    res = db.users.insert_one(new_user)
    user_id = str(res.inserted_id)
    
    access_token = create_access_token(data={"sub": user_id, "role": role})
    refresh_token = create_refresh_token(data={"sub": user_id, "role": role})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": email_clean,
            "full_name": full_name,
            "is_verified": True
        }
    }

@router.post("/login")
def login(credentials: UserLogin):
    db = get_db()
    email_clean = credentials.email.strip().lower()
    user = db.users.find_one({"email": email_clean})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No account found with this email address.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Please try again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user_id = str(user["_id"])
    role = user.get("role", "user")
    access_token = create_access_token(data={"sub": user_id, "role": role})
    refresh_token = create_refresh_token(data={"sub": user_id, "role": role})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": user["email"],
            "full_name": user.get("full_name", user["email"].split("@")[0]),
            "is_verified": True
        }
    }

@router.post("/refresh", response_model=TokenResponse)
def refresh(refresh_in: TokenRefreshRequest):
    payload = decode_token(refresh_in.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token type"
        )
        
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token content"
        )
        
    db = get_db()
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session expired or user deleted"
        )
        
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

@router.put("/update", response_model=UserResponse)
def update_profile(update_in: UserUpdateRequest, current_user: dict = Depends(get_current_user)):
    db = get_db()
    update_data = {}
    if update_in.full_name is not None:
        update_data["full_name"] = update_in.full_name
    if update_in.password is not None:
        new_hash = get_password_hash(update_in.password)
        update_data["hashed_password"] = new_hash
        # Update history
        history = current_user.get("password_history", [])
        history.append(new_hash)
        update_data["password_history"] = history[-5:]
        
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        db.users.update_one({"_id": ObjectId(current_user["id"])}, {"$set": update_data})
        
    updated_user = db.users.find_one({"_id": ObjectId(current_user["id"])})
    updated_user["id"] = str(updated_user["_id"])
    return updated_user

@router.post("/change-password")
def change_password(request: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """
    Normal Change Password Path (Authenticated User):
    1. Identifies user from authenticated JWT token session.
    2. Verifies current_password against stored hashed_password.
    3. If incorrect: rejects with "Current password is incorrect."
    4. If correct: validates new password, hashes it, and updates DB.
    """
    db = get_db()
    user_id = current_user["id"]
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    # 1. Verify Current Password against stored hash
    if not verify_password(request.current_password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect."
        )

    # 2. Validate New Password
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")

    # 3. Hash New Password & Update DB
    new_hashed_pwd = get_password_hash(request.new_password)
    history = user.get("password_history", [])
    history.append(new_hashed_pwd)
    history = history[-5:]

    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "hashed_password": new_hashed_pwd,
                "password_history": history,
                "updated_at": datetime.utcnow()
            }
        }
    )

    return {"message": "Password updated successfully."}

@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user)):
    """Logs out the current session."""
    return {"message": "Logged out successfully."}

@router.post("/logout-all")
def logout_all_sessions(current_user: dict = Depends(get_current_user)):
    """
    Logs out the user from all active devices and sessions
    by updating the user token_version timestamp in the database.
    """
    db = get_db()
    user_id = current_user["id"]
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"token_version": datetime.utcnow()}}
    )
    return {"message": "Logged out from all active devices and sessions."}

@router.delete("/delete-account")
def delete_account(current_user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = current_user["id"]
    
    user_papers = list(db.papers.find({"user_id": user_id}))
    for paper in user_papers:
        paper_id = str(paper["_id"])
        delete_paper_chunks(paper_id)
        
    db.papers.delete_many({"user_id": user_id})
    db.conversations.delete_many({"user_id": user_id})
    db.reviews.delete_many({"user_id": user_id})
    db.bookmarks.delete_many({"user_id": user_id})
    db.comparisons.delete_many({"user_id": user_id})
    db.users.delete_one({"_id": ObjectId(user_id)})
    
    return {"message": "Your account and all associated research documents have been permanently deleted."}


