import secrets
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from sqlalchemy.exc import SQLAlchemyError
import logging
from .tokens import JWTHandler
from ...core.database import get_or_create_user

Base = declarative_base()

class MagicLink(Base):
    __tablename__ = "magic_links"
    
    token = Column(String, primary_key=True)
    email = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)

def create_magic_link(email: str, db: Session) -> str:
    try:
        # Generate a secure token
        token = JWTHandler.create_access_token({"sub": email})
        expires_at = datetime.utcnow() + timedelta(minutes=15)
        
        # Store the magic link
        magic_link = MagicLink(
            token=token,
            email=email,
            expires_at=expires_at
        )
        db.add(magic_link)
        db.commit()
        
        try:
            # Send the magic link email
            send_magic_link(email, token)
            return token
        except Exception as e:
            logging.error(f"Email sending failed: {str(e)}")
            # Rollback the database entry if email fails
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Failed to send email. Please try again later."
            )
            
    except SQLAlchemyError as e:
        logging.error(f"Database error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database error occurred. Please try again later."
        )

def send_magic_link(email: str, token: str):
    try:
        sender_email = os.getenv("EMAIL_ADDRESS")
        sender_password = os.getenv("EMAIL_PASSWORD")
        
        if not sender_email or not sender_password:
            raise ValueError("Email configuration is missing")
        
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = email
        message["Subject"] = "Your Magic Link"
        
        link = f"{os.getenv('APP_URL')}/auth/verify-magic-link?token={token}"
        body = f"Click this link to sign in: {link}\nThis link will expire in 15 minutes."
        message.attach(MIMEText(body, "plain"))
        
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)
            
    except Exception as e:
        logging.error(f"Email error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Email sending failed: {str(e)}"
        )

def verify_magic_link(token: str, db: Session) -> str:
    magic_link = db.query(MagicLink).filter(MagicLink.token == token).first()
    if not magic_link:
        raise HTTPException(status_code=400, detail="Invalid magic link")
    
    if magic_link.expires_at < datetime.utcnow():
        db.delete(magic_link)
        db.commit()
        raise HTTPException(status_code=400, detail="Magic link expired")
    
    email = magic_link.email
    db.delete(magic_link)
    db.commit()
    
    return email

def create_user_from_magic_link(email: str, db):
    user_info = {
        "email": email,
        "oauth_provider": "email",
        "id": None
    }
    return get_or_create_user(db, user_info)