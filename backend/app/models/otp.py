from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr

class OTPRecord(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: Optional[str] = None
    email: str
    hashed_otp: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    attempts: int = 0
    is_used: bool = False
    reset_token: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResendOTPRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp_code: Optional[str] = None
    otp: Optional[str] = None

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    reset_token: str
    new_password: str
    confirm_password: str

class PasswordlessLoginRequest(BaseModel):
    email: EmailStr

class PasswordlessVerifyRequest(BaseModel):
    email: EmailStr
    otp_code: Optional[str] = None
    otp: Optional[str] = None

