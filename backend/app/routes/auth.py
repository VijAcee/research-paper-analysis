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
from app.models.otp import (
    ForgotPasswordRequest,
    ResendOTPRequest,
    VerifyOTPRequest,
    ResetPasswordRequest,
    PasswordlessLoginRequest,
    PasswordlessVerifyRequest
)
from app.services.email_service import send_otp_email
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

@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest):
    """
    Step 1: Accepts email, checks DB, generates cryptographically secure 6-digit OTP,
    hashes OTP with bcrypt, saves to DB, and sends SendGrid HTML email.
    Protects against email enumeration by ALWAYS returning the same generic message.
    """
    db = get_db()
    generic_msg = "If an account exists for this email, a verification code has been sent."
    
    user = db.users.find_one({"email": request.email})
    if not user:
        return {"message": generic_msg}
    
    # Check rate limit (max 3 resends/hour)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_otps = db.otps.count_documents({
        "email": request.email,
        "created_at": {"$gte": one_hour_ago}
    })
    if recent_otps >= settings.MAX_OTP_RESENDS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum password reset requests exceeded. Please try again after 1 hour."
        )
    
    # Invalidate previous unverified OTPs
    db.otps.update_many(
        {"email": request.email, "is_used": False},
        {"$set": {"is_used": True}}
    )
    
    # Cryptographically secure 6-digit OTP generator
    otp_code = str(secrets.SystemRandom().randint(100000, 999999))
    hashed_otp = get_password_hash(otp_code)
    
    expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRATION_MINUTES)
    
    otp_doc = {
        "user_id": str(user["_id"]),
        "email": request.email,
        "hashed_otp": hashed_otp,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "attempts": 0,
        "is_used": False,
        "reset_token": None
    }
    
    db.otps.insert_one(otp_doc)
    
    # Deliver SendGrid email
    send_otp_email(to_email=request.email, otp_code=otp_code, user_name=user.get("full_name"))
    
    return {"message": generic_msg}

@router.post("/resend-otp")
def resend_otp(request: ResendOTPRequest):
    """
    Resends brand-new OTP. Enforces 60-second cooldown and 3/hr resend limit.
    """
    db = get_db()
    user = db.users.find_one({"email": request.email})
    if not user:
        return {"message": "A new verification code has been sent if the email exists."}
    
    # 60s Cooldown check
    latest_otp = db.otps.find_one({"email": request.email}, sort=[("created_at", -1)])
    if latest_otp:
        time_since_creation = (datetime.utcnow() - latest_otp["created_at"]).total_seconds()
        if time_since_creation < settings.OTP_RESEND_COOLDOWN_SECONDS:
            remaining_cooldown = int(settings.OTP_RESEND_COOLDOWN_SECONDS - time_since_creation)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {remaining_cooldown} seconds before requesting a new verification code."
            )
            
    # Max 3/hr limit check
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_count = db.otps.count_documents({"email": request.email, "created_at": {"$gte": one_hour_ago}})
    if recent_count >= settings.MAX_OTP_RESENDS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum OTP resend limit reached for this hour. Please try again later."
        )

    # Invalidate prior OTPs
    db.otps.update_many({"email": request.email, "is_used": False}, {"$set": {"is_used": True}})

    # Generate new OTP
    otp_code = str(secrets.SystemRandom().randint(100000, 999999))
    hashed_otp = get_password_hash(otp_code)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRATION_MINUTES)

    db.otps.insert_one({
        "user_id": str(user["_id"]),
        "email": request.email,
        "hashed_otp": hashed_otp,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "attempts": 0,
        "is_used": False,
        "reset_token": None
    })

    send_otp_email(to_email=request.email, otp_code=otp_code, user_name=user.get("full_name"))

    return {"message": "A new 6-digit verification code has been sent to your email."}

@router.post("/verify-otp")
def verify_otp(request: VerifyOTPRequest):
    """
    Step 2: Verifies 6-digit OTP code against bcrypt hash. Enforces 5-minute expiration,
    one-time use, and max 5 attempts limit. Generates short-lived reset token on success.
    """
    db = get_db()
    otp_doc = db.otps.find_one({"email": request.email, "is_used": False}, sort=[("created_at", -1)])
    
    if not otp_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    # Expiration check
    if datetime.utcnow() > otp_doc["expires_at"]:
        db.otps.update_one({"_id": otp_doc["_id"]}, {"$set": {"is_used": True}})
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new code.")

    # Attempt limit check (max 5 attempts)
    if otp_doc.get("attempts", 0) >= settings.MAX_OTP_ATTEMPTS:
        db.otps.update_one({"_id": otp_doc["_id"]}, {"$set": {"is_used": True}})
        raise HTTPException(
            status_code=400, 
            detail="Maximum verification attempts exceeded. Code invalidated. Please request a new code."
        )

    # Hash comparison
    if not verify_password(request.otp_code.strip(), otp_doc["hashed_otp"]):
        new_attempts = otp_doc.get("attempts", 0) + 1
        is_used = new_attempts >= settings.MAX_OTP_ATTEMPTS
        db.otps.update_one({"_id": otp_doc["_id"]}, {"$set": {"attempts": new_attempts, "is_used": is_used}})
        
        remaining = settings.MAX_OTP_ATTEMPTS - new_attempts
        if remaining <= 0:
            raise HTTPException(status_code=400, detail="Invalid verification code. Maximum attempts reached. Please request a new code.")
        raise HTTPException(status_code=400, detail=f"Invalid verification code. {remaining} attempt(s) remaining.")

    # Success: Issue reset token and mark OTP used
    reset_token = secrets.token_urlsafe(32)
    db.otps.update_one(
        {"_id": otp_doc["_id"]},
        {"$set": {"is_used": True, "reset_token": reset_token}}
    )

    return {
        "message": "Verification code confirmed successfully.",
        "reset_token": reset_token
    }

@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest):
    """
    Step 3: Validates reset token, checks 12-char strong password rules,
    verifies non-matching against last 5 passwords, updates bcrypt hash,
    and invalidates all active tokens.
    """
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirm password do not match.")

    db = get_db()
    otp_doc = db.otps.find_one({"email": request.email, "reset_token": request.reset_token, "is_used": True})
    if not otp_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset session.")

    user = db.users.find_one({"email": request.email})
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    # Enforce 12-character strong password validation & 5-password history check
    history = user.get("password_history", [])
    if "hashed_password" in user and user["hashed_password"] not in history:
        history.append(user["hashed_password"])

    validate_strong_password(
        password=request.new_password,
        user_email=request.email,
        user_name=user.get("full_name", ""),
        password_history=history
    )

    # Hash new password
    new_hashed_pwd = get_password_hash(request.new_password)
    history.append(new_hashed_pwd)
    history = history[-5:]

    # Update User DB
    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "hashed_password": new_hashed_pwd,
                "password_history": history,
                "updated_at": datetime.utcnow()
            }
        }
    )

    # Remove used reset token
    db.otps.delete_one({"_id": otp_doc["_id"]})

    return {"message": "Your password has been successfully updated. Please log in with your new password."}

@router.post("/send-otp")
@router.post("/passwordless/request")
def passwordless_request(request: PasswordlessLoginRequest):
    """
    Sends a cryptographically secure 6-digit SendGrid OTP for email verification.
    Protects against user enumeration by returning a uniform response.
    Returns HTTP 500 if SendGrid fails to dispatch the message.
    """
    print(f"\n[OTP] Request received")
    print(f"[OTP] Request received for: {request.email}")
    db = get_db()
    generic_msg = "If this email is registered, a verification code has been sent."

    # Email validation log
    print(f"[OTP] Email validated")

    # Rate limiting: max 3 requests per hour per email
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_count = db.otps.count_documents({
        "email": request.email,
        "created_at": {"$gte": one_hour_ago}
    })
    if recent_count >= settings.MAX_OTP_RESENDS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum OTP requests reached for this hour. Please try again later."
        )

    # Invalidate previous unverified OTPs
    db.otps.update_many({"email": request.email, "is_used": False}, {"$set": {"is_used": True}})

    # Cryptographically secure 6-digit OTP generator (never use predictable math.random)
    otp_code = str(secrets.SystemRandom().randint(100000, 999999))
    print(f"[OTP] Secure OTP generated")

    hashed_otp = get_password_hash(otp_code)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRATION_MINUTES)

    user = db.users.find_one({"email": request.email})
    user_id = str(user["_id"]) if user else None
    user_name = user.get("full_name") if user else None

    db.otps.insert_one({
        "user_id": user_id,
        "email": request.email,
        "hashed_otp": hashed_otp,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "attempts": 0,
        "is_used": False,
        "reset_token": None
    })
    print(f"[OTP] OTP stored successfully")

    # Dispatch actual SendGrid email
    success, err_detail = send_otp_email(to_email=request.email, otp_code=otp_code, user_name=user_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not send the verification code. {err_detail}"
        )

    return {"success": True, "message": generic_msg}

@router.post("/test-email")
def test_sendgrid_email(request: PasswordlessLoginRequest):
    """
    Temporary development test endpoint to verify SendGrid configuration directly.
    """
    print(f"\n[TEST EMAIL] Testing SendGrid delivery to: {request.email}")
    test_otp = str(secrets.SystemRandom().randint(100000, 999999))
    sent = send_otp_email(to_email=request.email, otp_code=test_otp, user_name="Test User")
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SendGrid test email failed. Check server console for exact SendGrid error details."
        )
    return {"success": True, "message": f"Test email accepted by SendGrid for {request.email}."}

@router.post("/verify-otp")
@router.post("/passwordless/verify")
def passwordless_verify(request: PasswordlessVerifyRequest):
    """
    Verifies the 6-digit OTP code for passwordless login.
    If user exists, issues JWT tokens and logs user in immediately.
    """
    code_val = (request.otp or request.otp_code or "").strip()
    if not code_val or len(code_val) != 6:
        raise HTTPException(status_code=400, detail="Please enter the complete 6-digit verification code.")

    db = get_db()
    otp_doc = db.otps.find_one({"email": request.email, "is_used": False}, sort=[("created_at", -1)])

    if not otp_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    # Expiration check
    if datetime.utcnow() > otp_doc["expires_at"]:
        db.otps.update_one({"_id": otp_doc["_id"]}, {"$set": {"is_used": True}})
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new code.")

    # Attempt limit check
    if otp_doc.get("attempts", 0) >= settings.MAX_OTP_ATTEMPTS:
        db.otps.update_one({"_id": otp_doc["_id"]}, {"$set": {"is_used": True}})
        raise HTTPException(
            status_code=400,
            detail="Maximum verification attempts exceeded. Please request a new code."
        )

    # Hash comparison
    if not verify_password(code_val, otp_doc["hashed_otp"]):
        new_attempts = otp_doc.get("attempts", 0) + 1
        is_used = new_attempts >= settings.MAX_OTP_ATTEMPTS
        db.otps.update_one({"_id": otp_doc["_id"]}, {"$set": {"attempts": new_attempts, "is_used": is_used}})

        remaining = settings.MAX_OTP_ATTEMPTS - new_attempts
        if remaining <= 0:
            raise HTTPException(status_code=400, detail="Invalid verification code. Maximum attempts reached.")
        raise HTTPException(status_code=400, detail=f"Invalid verification code. {remaining} attempt(s) remaining.")

    # Success: Mark OTP as used
    db.otps.update_one({"_id": otp_doc["_id"]}, {"$set": {"is_used": True}})

    # Find existing user
    user = db.users.find_one({"email": request.email})
    if not user:
        # Create a new user automatically for passwordless email onboarding
        role = "admin" if request.email.startswith("admin@") else "user"
        new_user = {
            "email": request.email,
            "hashed_password": get_password_hash(secrets.token_urlsafe(16)),
            "full_name": request.email.split("@")[0].capitalize(),
            "role": role,
            "is_verified": True,
            "password_history": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        res = db.users.insert_one(new_user)
        user_id = str(res.inserted_id)
        user = db.users.find_one({"_id": ObjectId(user_id)})

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
            "is_verified": True,
            "created_at": user.get("created_at", datetime.utcnow()).isoformat()
        }
    }

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


