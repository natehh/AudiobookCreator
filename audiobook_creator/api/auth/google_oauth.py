import requests
from fastapi import HTTPException
from urllib.parse import urlencode
from ...core.database import get_or_create_user
from dotenv import load_dotenv
import os

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
GOOGLE_AUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

def get_google_auth_url():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "email profile",
        "access_type": "offline",
    }
    return f"{GOOGLE_AUTH_BASE}?{urlencode(params)}"

def handle_google_callback(code: str, db):
    # Exchange code for access token
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    response = requests.post(GOOGLE_TOKEN_URL, data=data)
    if not response.ok:
        raise HTTPException(status_code=400, detail="Failed to fetch access token")
    
    tokens = response.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_info = requests.get(GOOGLE_USER_INFO_URL, headers=headers).json()
    
    if "email" not in user_info:
        raise HTTPException(status_code=400, detail="Failed to fetch user information")
    
    return get_or_create_user(db, user_info)
