import os
import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .tokens import JWTHandler
from ...core.database import get_or_create_user
from ...utils.email_utils import send_email

def create_magic_link(email: str, db: Session) -> str:
    try:
        # Generate a JWT token that expires in 15 minutes
        token = JWTHandler.create_magic_link_token({"sub": email})
        
        # Send the magic link email
        send_magic_link(email, token)
        return token
            
    except Exception as e:
        logging.error(f"Magic link error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create magic link. Please try again later."
        )

def send_magic_link(email: str, token: str):
    try:
        link = f"{os.getenv('APP_URL')}/auth/verify-magic-link?token={token}"
        body = f"Click this link to sign in: {link}\nThis link will expire in 15 minutes."
        
        send_email(
            to=email,
            subject="Your Signup Link for AudiobookCreator",
            body=body
        )
            
    except Exception as e:
        logging.error(f"Email error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Email sending failed: {str(e)}"
        )

def verify_magic_link(token: str, db: Session) -> str:
    try:
        # Verify the token and check it's a magic link type
        email = JWTHandler.verify_token(token, check_type="magic_link")
        
        # Create the user if they don't exist
        user_info = {
            "email": email,
            "oauth_provider": "email"
        }
        user = create_user_from_magic_link(email, db)
        return email
    except Exception as e:
        logging.error(f"Magic link verification error: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid or expired magic link")

def create_user_from_magic_link(email: str, db):
    user_info = {
        "email": email,
        "oauth_provider": "email",
        "id": None
    }
    return get_or_create_user(db, user_info)