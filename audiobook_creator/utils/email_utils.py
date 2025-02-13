import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import HTTPException

def send_email(to: str, subject: str, body: str):
    """
    Send an email using the configured SMTP settings.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body text
    
    Raises:
        HTTPException: If email sending fails
    """
    try:
        sender_email = os.getenv("EMAIL_ADDRESS")
        sender_password = os.getenv("EMAIL_PASSWORD")
        
        if not sender_email or not sender_password:
            raise ValueError("Email configuration is missing")
        
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = to
        message["Subject"] = subject
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