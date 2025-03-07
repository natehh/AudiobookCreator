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
from .utils.rate_limit import general_rate_limit
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

# Get allowed origins from environment or use a default
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:8000').split(',')

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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

# Add a middleware for global rate limiting (excluding static files)
@app.middleware("http")
async def global_rate_limiting(request: Request, call_next):
    # Skip rate limiting for static files and normal workflow paths
    if request.url.path.startswith("/static/") or \
       request.url.path.startswith("/api/payment") or \
       request.url.path.startswith("/api/pricing") or \
       request.url.path.startswith("/convert/") or \
       request.url.path.startswith("/download/") or \
       request.url.path.startswith("/auth/") or \
       request.url.path == "/" or \
       request.url.path == "/status/":
        return await call_next(request)
        
    # Apply general rate limiting for API endpoints
    # Note: We don't await the dependency directly because it would interfere with other routes
    # that already have rate limiting applied.
    
    # Only check at this level if the route doesn't start with a path we're already
    # checking in route-specific rate limiting (to avoid double-rate-limiting)
    try:
        await general_rate_limit(request)
    except HTTPException as exc:
        if exc.status_code == 429:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": exc.detail},
                headers=exc.headers
            )
        raise
    
    return await call_next(request)

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
        "/static/js/feedback.js",
        "/static/favicon-16x16.png",
        "/static/favicon-32x32.png",
        "/static/apple-touch-icon.png",
        "/static/android-chrome-192x192.png",
        "/static/android-chrome-512x512.png",
        "/static/site.webmanifest",
        "/auth/verify",
        "/api/payment/webhook",
        "/auth/refresh",  # Allow token refresh without authentication
    ]
    
    # Check exact matches first
    if request.url.path in public_paths:
        return await call_next(request)
    
    # Check path patterns
    if request.url.path.startswith("/static/demo_files/"):
        return await call_next(request)
    
    # Check for authentication
    access_token = request.cookies.get("access_token")
    if not access_token or not access_token.startswith("Bearer "):
        # Try to refresh if refresh token exists
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token and refresh_token.startswith("Bearer "):
            try:
                # Verify the refresh token
                refresh_token_value = refresh_token.split(" ")[1]
                email = JWTHandler.verify_token(refresh_token_value, check_type="refresh")
                
                # Generate a new access token
                new_access_token = JWTHandler.create_access_token({"sub": email})
                
                # Create response with new access token
                response = await call_next(request)
                
                # Add the new access token to response
                response.set_cookie(
                    key="access_token",
                    value=f"Bearer {new_access_token}",
                    httponly=True,
                    max_age=3600,  # 1 hour
                    secure=True,
                    samesite="lax"
                )
                
                return response
            except HTTPException:
                # If refresh token is invalid, continue to normal authentication flow
                pass
        
        # Only redirect GET requests to index.html
        if request.method == "GET":
            return RedirectResponse("/static/index.html")
        else:
            raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Verify the access token
        JWTHandler.verify_token(access_token.split(" ")[1], check_type="access")
    except HTTPException:
        # If access token is invalid but we have a refresh token, attempt to use it
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token and refresh_token.startswith("Bearer "):
            try:
                # Redirect to refresh endpoint which will handle token renewal
                return RedirectResponse("/auth/refresh", status_code=307)
            except HTTPException:
                if request.method == "GET":
                    return RedirectResponse("/static/index.html")
                else:
                    raise HTTPException(status_code=401, detail="Invalid authentication")
        else:
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