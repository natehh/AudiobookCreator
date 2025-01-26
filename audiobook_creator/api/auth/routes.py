from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from ...core.database import get_db
from .google_oauth import get_google_auth_url, handle_google_callback

auth_router = APIRouter()

@auth_router.get("/login/google")
def login_google():
    """Redirects user to Google's OAuth login page."""
    return RedirectResponse(get_google_auth_url())

@auth_router.get("/callback/google")
def auth_callback(code: str, db=Depends(get_db)):
    """Handles the Google OAuth callback."""
    user = handle_google_callback(code, db)
    # Here, you would generate a token (e.g., JWT)
    return {"message": "Login successful", "user": user}
