from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from ...core.database import get_db, User
from .google_oauth import get_google_auth_url, handle_google_callback
from .tokens import JWTHandler, JWTBearer
from fastapi.responses import JSONResponse
from .magic_link import create_magic_link, verify_magic_link, create_user_from_magic_link
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_current_user(
    token: str = Depends(JWTBearer()),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from the JWT token."""
    try:
        email = JWTHandler.verify_token(token)
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

auth_router = APIRouter()
class MagicLinkRequest(BaseModel):
    email: EmailStr

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
async def verify_auth(token: str = Depends(JWTBearer())):
    """Verify authentication status."""
    return JSONResponse({"authenticated": True})

@auth_router.post("/request-magic-link")
async def request_magic_link(request: MagicLinkRequest, db: Session = Depends(get_db)):
    try:
        create_magic_link(request.email, db)
        return {"message": "Magic link sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to send magic link")

@auth_router.get("/verify-magic-link")
async def verify_magic_link_route(token: str, db: Session = Depends(get_db)):
    try:
        email = verify_magic_link(token, db)
        # Create a regular access token (not a magic link token)
        jwt_token = JWTHandler.create_access_token({"sub": email})
        
        response = RedirectResponse(url="/static/create_conversion.html")
        response.set_cookie(
            key="access_token",
            value=f"Bearer {jwt_token}",
            httponly=True,
            max_age=3600,
            secure=True,
            samesite="lax"
        )
        return response
    except Exception as e:
        logging.error(f"Magic link route error: {str(e)}")
        return RedirectResponse(url="/static/index.html")

@auth_router.post("/logout")
async def logout():
    """Handle user logout."""
    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return response