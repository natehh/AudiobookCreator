from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from .api.routes import AudiobookAPI
from .api.auth.routes import auth_router
from .api.auth.tokens import JWTHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the main FastAPI application
api = AudiobookAPI()
app = api.app

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Paths that don't require authentication
    public_paths = [
        "/static/index.html",
        "/auth/login/google",
        "/auth/callback/google",
        "/favicon.ico"
    ]
    
    if request.url.path in public_paths:
        return await call_next(request)
    
    # Check for authentication
    token = request.cookies.get("access_token")
    if not token or not token.startswith("Bearer "):
        return RedirectResponse("/static/index.html")
    
    try:
        JWTHandler.verify_token(token.split(" ")[1])
    except HTTPException:
        return RedirectResponse("/static/index.html")
    
    # If authenticated and trying to access root, redirect to create_conversion
    if request.url.path == "/":
        return RedirectResponse("/static/create_conversion.html")
        
    return await call_next(request)

# Mount static files for serving HTML pages
app.mount("/static", StaticFiles(directory="audiobook_creator/static"), name="static")

# Include the auth router
app.include_router(auth_router, prefix="/auth", tags=["auth"])

# Root redirect - for authenticated users will be redirected to create_conversion.html
# by the middleware, for unauthenticated users will be redirected to index.html
@app.get("/")
async def root():
    return RedirectResponse("/static/index.html")