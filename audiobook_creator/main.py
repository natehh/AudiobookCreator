from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, Response, FileResponse
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
from pathlib import Path

# Load environment variables
load_dotenv()

# Initialize the main FastAPI application
api = AudiobookAPI()
app = api.app

# Static directory references
STATIC_DIR = Path(__file__).parent / "static"
PUBLIC_HTML_PATHS = {"/", "/pricing", "/blog"}
AUTH_REQUIRED_HTML_PATHS = {"/create", "/conversion", "/account", "/payment"}
HTML_PAGE_PATHS = PUBLIC_HTML_PATHS | AUTH_REQUIRED_HTML_PATHS


def is_public_route(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    return normalized in PUBLIC_HTML_PATHS

# Helper for serving static HTML files via clean routes
def html_response(filename: str) -> FileResponse:
    file_path = STATIC_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(file_path, media_type="text/html")

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
    raw_path = request.url.path
    path = raw_path.rstrip("/") or "/"

    if path.startswith("/static/") or \
       path.startswith("/api/payment") or \
       path.startswith("/api/pricing") or \
       path.startswith("/convert/") or \
       path.startswith("/download/") or \
       path.startswith("/auth/") or \
       is_public_route(raw_path) or \
       path == "/status":
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
    public_paths = {
        "/auth/login/google",
        "/auth/callback/google",
        "/auth/request-magic-link",
        "/auth/verify-magic-link",
        "/favicon.ico",
        "/demo-voices",
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
        "/robots.txt",
        "/sitemap.xml",
    }
    raw_path = request.url.path
    path = raw_path.rstrip("/") or "/"
    public_paths.update(PUBLIC_HTML_PATHS)
    
    # Check exact matches first
    if path in public_paths or is_public_route(raw_path):
        return await call_next(request)
    
    # Check path patterns
    if path.startswith("/static/demo_files/"):
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
        
        # For HTML pages, send unauthenticated users to the landing page
        if request.method in ["GET", "HEAD"] and path in AUTH_REQUIRED_HTML_PATHS:
            return RedirectResponse("/")
        else:
            # Return a proper response instead of raising an exception
            return Response(status_code=401, headers={"WWW-Authenticate": "Bearer"}, content="Authentication required")
    
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
                if request.method in ["GET", "HEAD"] and path in AUTH_REQUIRED_HTML_PATHS:
                    return RedirectResponse("/")
                else:
                    return Response(status_code=401, headers={"WWW-Authenticate": "Bearer"}, content="Invalid authentication")
        else:
            if request.method in ["GET", "HEAD"] and path in AUTH_REQUIRED_HTML_PATHS:
                return RedirectResponse("/")
            else:
                return Response(status_code=401, headers={"WWW-Authenticate": "Bearer"}, content="Invalid authentication")
    
    # If authenticated and trying to access root, redirect to create_conversion
    if path == "/":
        return RedirectResponse("/create")
        
    return await call_next(request)

# Include the auth router
app.include_router(auth_router, prefix="/auth", tags=["auth"])

# Include the account router
app.include_router(account_router, prefix="/api", tags=["account"])

# Include the pricing router
app.include_router(pricing_router, prefix="/api", tags=["pricing"])

# Root route - served without .html extension; authenticated users are redirected
# to the create conversion flow by the auth middleware
@app.get("/")
async def root():
    return html_response("index.html")


@app.get("/pricing")
async def pricing_page():
    return html_response("pricing.html")


@app.get("/blog")
async def blog_page():
    return html_response("blog.html")


@app.get("/create")
async def create_conversion_page():
    return html_response("create_conversion.html")


@app.get("/conversion")
async def conversion_page():
    return html_response("conversion.html")


@app.get("/account")
async def account_page():
    return html_response("account.html")


@app.get("/payment")
async def payment_page():
    return html_response("payment.html")

# SEO routes
@app.get("/robots.txt", response_class=Response)
async def robots_txt():
    """Serve robots.txt for search engine crawlers."""
    with open("audiobook_creator/static/robots.txt", "r") as f:
        content = f.read()
    return Response(content=content, media_type="text/plain")

@app.get("/sitemap.xml", response_class=Response)
async def sitemap_xml():
    """Serve sitemap.xml for search engine crawlers."""
    with open("audiobook_creator/static/sitemap.xml", "r") as f:
        content = f.read()
    return Response(content=content, media_type="application/xml")