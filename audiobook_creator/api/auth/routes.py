from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from ...core.database import get_db
from .google_oauth import get_google_auth_url, handle_google_callback
from .tokens import JWTHandler
from fastapi.responses import JSONResponse

auth_router = APIRouter()

@auth_router.get("/login/google")
def login_google():
    """Redirects user to Google's OAuth login page."""
    return RedirectResponse(get_google_auth_url())

@auth_router.get("/callback/google")
def auth_callback(code: str, db=Depends(get_db)):
    """Handles the Google OAuth callback."""
    user = handle_google_callback(code, db)
    
    # Generate JWT token
    token = JWTHandler.create_access_token({"sub": user.email})
    
    # Set token in cookie and redirect to create_conversion page
    response = RedirectResponse(url="/static/create_conversion.html")
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=3600,
        secure=True,
        samesite="lax"
    )
    return response

@auth_router.get("/verify")
async def verify_auth(token: str = Depends(JWTHandler.verify_token)):
    """Verify authentication status."""
    return JSONResponse({"authenticated": True})