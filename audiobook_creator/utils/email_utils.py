import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import HTTPException
from datetime import datetime

def send_email(to: str, subject: str, body: str, is_html: bool = False):
    """
    Send an email using the configured SMTP settings.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body text
        is_html: Whether the body is HTML formatted
    
    Raises:
        HTTPException: If email sending fails
    """
    try:
        sender_email = os.getenv("EMAIL_ADDRESS")
        sender_password = os.getenv("EMAIL_PASSWORD")
        
        if not sender_email or not sender_password:
            raise ValueError("Email configuration is missing")
        
        message = MIMEMultipart("alternative")
        message["From"] = sender_email
        message["To"] = to
        message["Subject"] = subject
        
        # Attach the appropriate content type
        content_type = "html" if is_html else "plain"
        message.attach(MIMEText(body, content_type))
        
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

def send_conversion_confirmation(
    to: str, 
    conversion_id: str, 
    book_title: str, 
    book_author: str, 
    payment_amount: float = 0.0,
    base_url: str = None
):
    """
    Send a confirmation email for a new conversion.
    
    Args:
        to: Recipient email address
        conversion_id: The unique identifier for the conversion
        book_title: The title of the book being converted
        book_author: The author of the book
        payment_amount: The amount paid for the conversion (0 for free conversions)
        base_url: Base URL for the application (defaults to environment variable)
    
    Raises:
        HTTPException: If email sending fails
    """
    try:
        # Get base URL from environment if not provided
        if not base_url:
            base_url = os.getenv("BASE_URL", "https://audiobook-creator.com")
        
        # Remove trailing slash if present
        if base_url.endswith('/'):
            base_url = base_url[:-1]
            
        conversion_url = f"{base_url}/conversion/{conversion_id}"
        app_name = os.getenv("APP_NAME", "Audiobook Creator")
        
        # Create email subject
        subject = f"Your audiobook conversion for '{book_title}' has started"
        
        # Format currency
        formatted_amount = "${:.2f}".format(payment_amount)
        
        # Create HTML email body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Audiobook Conversion Started</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background-color: #4a6fa5;
                    padding: 20px;
                    text-align: center;
                    color: white;
                    border-radius: 5px 5px 0 0;
                }}
                .content {{
                    padding: 20px;
                    background-color: #f8f9fa;
                    border-radius: 0 0 5px 5px;
                    border: 1px solid #ddd;
                    border-top: none;
                }}
                .book-details {{
                    background-color: white;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                    border: 1px solid #eee;
                }}
                .payment-details {{
                    background-color: white;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                    border: 1px solid #eee;
                }}
                .button {{
                    background-color: #4a6fa5;
                    color: white;
                    padding: 12px 20px;
                    text-decoration: none;
                    border-radius: 5px;
                    display: inline-block;
                    font-weight: bold;
                }}
                .footer {{
                    margin-top: 30px;
                    text-align: center;
                    font-size: 12px;
                    color: #777;
                }}
                .stripe-receipt {{
                    border-left: 5px solid #6772e5;
                    padding-left: 15px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{app_name}</h1>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>Thank you for using our {app_name} service! We've started the conversion process for your book.</p>
                
                <div class="book-details">
                    <h2>Book Details</h2>
                    <p><strong>Title:</strong> {book_title}</p>
                    <p><strong>Author:</strong> {book_author}</p>
                    <p><strong>Conversion ID:</strong> {conversion_id}</p>
                </div>
        """
        
        # Add payment information for paid conversions
        if payment_amount > 0:
            html_body += f"""
                <div class="payment-details stripe-receipt">
                    <h2>Payment Receipt</h2>
                    <p><strong>Amount:</strong> {formatted_amount}</p>
                    <p><strong>Status:</strong> Paid</p>
                    <p><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
                </div>
            """
        
        html_body += f"""
                <p>You can track the progress of your conversion here:</p>
                <p style="text-align: center;">
                    <a href="{conversion_url}" class="button">View Conversion</a>
                </p>
                
                <p>Your audiobook will be available for download once the conversion is complete.</p>
                
                <p>Thank you for using our service!</p>
                
                <div class="footer">
                    <p>This is an automated message from {app_name}. Please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version as fallback
        plain_body = f"""Hello,

Thank you for using our {app_name} service! We've started the conversion process for your book.

Book Details:
- Title: {book_title}
- Author: {book_author}
- Conversion ID: {conversion_id}

"""
        
        if payment_amount > 0:
            plain_body += f"""Payment Information:
- Amount: {formatted_amount}
- Status: Paid

"""
        
        plain_body += f"""You can track the progress of your conversion here:
{conversion_url}

Your audiobook will be available for download once the conversion is complete.
        
Thank you for using our service!

The {app_name} Team
"""
        
        # Send the HTML email
        send_email(to, subject, html_body, is_html=True)
        
    except Exception as e:
        logging.error(f"Conversion confirmation email error: {str(e)}")
        # Log the error but don't raise an exception to prevent blocking the conversion process 