from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from .api.routes import AudiobookAPI
from .api.auth.routes import auth_router
from .api.auth.tokens import JWTHandler
from dotenv import load_dotenv
from .core.database import initialize_db, populate_initial_data, get_db
from .api.account.routes import account_router
from .api.pricing.routes import pricing_router
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .utils.cleanup import cleanup_expired_audiobooks
import os

# Load environment variables
load_dotenv()

# Initialize the main FastAPI application
api = AudiobookAPI()
app = api.app

# Initialize database
initialize_db()

# After creating the app but before running it
populate_initial_data()

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up static files
app.mount("/static", StaticFiles(directory="audiobook_creator/static"), name="static")

# Set up cleanup scheduler
scheduler = AsyncIOScheduler()
scheduler.add_job(cleanup_expired_audiobooks, 'interval', hours=24, args=[next(get_db())])
scheduler.start()

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Paths that don't require authentication
    public_paths = [
        "/static/index.html",
        "/auth/login/google",
        "/auth/callback/google",
        "/auth/request-magic-link",
        "/auth/verify-magic-link",
        "/favicon.ico",
        "/demo-voices",
        "/static/pricing.html",
        "/api/pricing/voices",
        "/static/js/demo-player.js",
        "/static/js/common.js",
        "/auth/verify",
    ]
    
    # Check exact matches first
    if request.url.path in public_paths:
        return await call_next(request)
    
    # Check path patterns
    if request.url.path.startswith("/static/demo_files/"):
        return await call_next(request)
    
    # Check for authentication
    token = request.cookies.get("access_token")
    if not token or not token.startswith("Bearer "):
        # Only redirect GET requests to index.html
        if request.method == "GET":
            return RedirectResponse("/static/index.html")
        else:
            raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        JWTHandler.verify_token(token.split(" ")[1])
    except HTTPException:
        if request.method == "GET":
            return RedirectResponse("/static/index.html")
        else:
            raise HTTPException(status_code=401, detail="Invalid authentication")
    
    # If authenticated and trying to access root, redirect to create_conversion
    if request.url.path == "/":
        return RedirectResponse("/static/create_conversion.html")
        
    return await call_next(request)

# Mount static files for serving HTML pages
app.mount("/static", StaticFiles(directory="audiobook_creator/static"), name="static")

# Include the auth router
app.include_router(auth_router, prefix="/auth", tags=["auth"])

# Include the account router
app.include_router(account_router, prefix="/api", tags=["account"])

# Include the pricing router
app.include_router(pricing_router, prefix="/api", tags=["pricing"])

# Root redirect - for authenticated users will be redirected to create_conversion
# by the middleware, for unauthenticated users will be redirected to index.html
@app.get("/")
async def root():
    return RedirectResponse("/static/index.html")