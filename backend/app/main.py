import os
import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import (
    auth, 
    papers, 
    chat, 
    explorer, 
    compare, 
    reviews, 
    exports,
    settings as settings_route
)

app = FastAPI(
    title="PaperLens API",
    description="Production-grade microservices API for PaperLens: semantic searches, RAG chats, comparisons and document parsing with strict JWT security and user data isolation.",
    version="1.0.0"
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers & Request Logger Middleware
@app.middleware("http")
async def add_security_headers_and_logging(request: Request, call_next):
    start_time = datetime.datetime.now()
    if not request.url.path.endswith("/health"):
        print(f"[{start_time.strftime('%H:%M:%S')}] [MONITOR] Request Received: {request.method} {request.url.path}")
    
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Include sub-routers
app.include_router(auth.router, prefix="/api")
app.include_router(papers.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(explorer.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(exports.router, prefix="/api")
app.include_router(settings_route.router, prefix="/api")

@app.on_event("startup")
def startup_checks():
    print("[CONFIG] PaperLens Backend Service Started.")

@app.get("/health")
def root_health_check():
    """Root health endpoint returning status: ok."""
    return {"status": "ok"}

@app.get("/api/health")
def api_health_check():
    """API health endpoint returning status: ok."""
    return {
        "status": "ok",
        "timestamp": datetime.datetime.now().isoformat(),
        "environment": settings.ENVIRONMENT,
        "security": "JWT_AUTH_ISOLATED"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
