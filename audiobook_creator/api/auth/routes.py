from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from ...core.database import get_db, User, RefreshToken
from .google_oauth import get_google_auth_url, handle_google_callback
from .tokens import JWTHandler, JWTBearer, SECRET_KEY, ALGORITHM
from fastapi.responses import JSONResponse
from .magic_link import create_magic_link, verify_magic_link, create_user_from_magic_link
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, EmailStr
import logging
from datetime import datetime, timedelta, timezone
from jose import jwt as jose_jwt
from ...utils.rate_limit import auth_rate_limit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic model for refresh token requests
class RefreshTokenRequest(BaseModel):
    token: str
    user_id: int
    expires_at: datetime

async def get_current_user(
    token: str = Depends(JWTBearer()),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from the JWT token."""
    try:
        email = JWTHandler.verify_token(token, check_type="access")
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

auth_router = APIRouter()
class MagicLinkRequest(BaseModel):
    email: EmailStr

class RefreshRequest(BaseModel):
    refresh_token: str

def set_auth_cookies(response, access_token, refresh_token=None):
    """Helper function to set authentication cookies."""
    # Set the access token (short-lived)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=3600,  # 1 hour
        secure=True,
        samesite="lax"
    )
    
    # Set the refresh token (long-lived) if provided
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=f"Bearer {refresh_token}",
            httponly=True,
            max_age=30 * 24 * 3600,  # 30 days
            secure=True,
            samesite="lax"
        )
    
    return response

def store_refresh_token(token, user_id, db):
    """Store a refresh token in the database."""
    # Calculate expiration date (30 days from now)
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    
    # Create new refresh token entry using the SQLAlchemy model
    db_token = RefreshToken(
        token=token,
        user_id=user_id,
        expires_at=expires_at
    )
    
    # Add to database
    db.add(db_token)
    db.commit()
    
def revoke_refresh_token(token, db):
    """Mark a refresh token as revoked."""
    db_token = db.query(RefreshToken).filter(RefreshToken.token == token).first()
    if db_token:
        db_token.is_revoked = True
        db.commit()

@auth_router.get("/login/google")
def login_google():
    """Redirects user to Google's OAuth login page."""
    return RedirectResponse(get_google_auth_url())

@auth_router.get("/callback/google")
def auth_callback(code: str, db=Depends(get_db)):
    """Handles the Google OAuth callback."""
    user = handle_google_callback(code, db)
    
    # Generate tokens
    access_token = JWTHandler.create_access_token({"sub": user.email})
    refresh_token = JWTHandler.create_refresh_token({"sub": user.email})
    
    # Store refresh token in database
    store_refresh_token(refresh_token, user.id, db)
    
    # Set tokens in cookies and redirect
    response = RedirectResponse(url="/static/create_conversion.html")
    return set_auth_cookies(response, access_token, refresh_token)

@auth_router.get("/verify")
async def verify_auth(token: str = Depends(JWTBearer())):
    """Verify authentication status."""
    return JSONResponse({"authenticated": True})

@auth_router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: bool = Depends(auth_rate_limit)  # Add rate limiting
):
    """Refresh an access token using a valid refresh token."""
    try:
        # Get refresh token from cookie
        refresh_token_cookie = request.cookies.get("refresh_token")
        if not refresh_token_cookie or not refresh_token_cookie.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="No refresh token provided")
            
        refresh_token = refresh_token_cookie.replace("Bearer ", "")
        
        # Verify the refresh token
        email = JWTHandler.verify_token(refresh_token, check_type="refresh")
        
        # Get the user
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify the token exists in the database and is not revoked
        db_token = db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token,
            RefreshToken.user_id == user.id,
            RefreshToken.is_revoked == False
        ).first()
        
        if not db_token:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Create a new access token
        new_access_token = JWTHandler.create_access_token({"sub": email})
        
        # Set the new access token in cookie
        response = JSONResponse({"message": "Token refreshed successfully"})
        response.set_cookie(
            key="access_token",
            value=f"Bearer {new_access_token}",
            httponly=True,
            max_age=3600,  # 1 hour
            secure=True,
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@auth_router.post("/request-magic-link")
async def request_magic_link(
    request: MagicLinkRequest, 
    db: Session = Depends(get_db),
    _: bool = Depends(auth_rate_limit)  # Add rate limiting
):
    try:
        create_magic_link(request.email, db)
        return {"message": "Magic link sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to send magic link")

@auth_router.get("/verify-magic-link")
async def verify_magic_link_route(
    token: str,
    db: Session = Depends(get_db),
    _: bool = Depends(auth_rate_limit)  # Add rate limiting
):
    try:
        # Log the token type for debugging
        try:
            payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            token_type = payload.get("type")
            logger.info(f"Magic link token type: {token_type}")
        except Exception as e:
            logger.error(f"Error decoding token: {str(e)}")
        
        # Verify the magic link token
        email = verify_magic_link(token, db)
        logger.info(f"Successfully verified magic link for: {email}")
        
        # Get or create user
        user = create_user_from_magic_link(email, db)
        
        # Create tokens
        access_token = JWTHandler.create_access_token({"sub": email})
        refresh_token = JWTHandler.create_refresh_token({"sub": email})
        
        # Store refresh token
        store_refresh_token(refresh_token, user.id, db)
        
        # Set tokens and redirect
        response = RedirectResponse(url="/static/create_conversion.html")
        return set_auth_cookies(response, access_token, refresh_token)
        
    except Exception as e:
        logger.error(f"Magic link route error: {str(e)}")
        # Create an error response with a helpful message
        error_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Magic Link Error</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 40px; }
                .error-box { max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #ff0000; border-radius: 5px; }
                .button { display: inline-block; background: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 20px; }
            </style>
        </head>
        <body>
            <div class="error-box">
                <h2>Invalid or Expired Magic Link</h2>
                <p>The login link you clicked has expired or is invalid. Please request a new login link.</p>
                <a href="/static/index.html" class="button">Back to Login</a>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)

@auth_router.post("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    """Handle user logout."""
    response = JSONResponse({"message": "Logged out successfully"})
    
    # Try to get and revoke the refresh token if it exists
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token and refresh_token.startswith("Bearer "):
        token_value = refresh_token.replace("Bearer ", "")
        try:
            # Try to find and revoke the token in the database
            db_token = db.query(RefreshToken).filter(RefreshToken.token == token_value).first()
            if db_token:
                db_token.is_revoked = True
                db.commit()
                logger.info(f"Revoked refresh token for user {db_token.user_id}")
        except Exception as e:
            logger.error(f"Error revoking refresh token: {str(e)}")
    
    # Clear both tokens regardless of whether we successfully revoked the refresh token
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=True,
        samesite="lax"
    )
    
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True,
        samesite="lax"
    )
    
    return response