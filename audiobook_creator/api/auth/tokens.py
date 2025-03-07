from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer
import os
from dotenv import load_dotenv
import secrets
import logging

load_dotenv()

# Get logger
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
# Shorter access token lifetime (60 minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = 60
# Longer refresh token lifetime (30 days)
REFRESH_TOKEN_EXPIRE_DAYS = 30

class JWTHandler:
    @staticmethod
    def create_access_token(data: dict):
        """Create a short-lived access token."""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(data: dict):
        """Create a long-lived refresh token."""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_magic_link_token(data: dict):
        """Create a short-lived token specifically for magic links."""
        to_encode = data.copy()
        # Magic links expire in 15 minutes
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire, "type": "magic_link"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str, check_type: str = None):
        """
        Verify a JWT token.
        
        Args:
            token: The JWT token to verify
            check_type: Optional type to check ('access', 'refresh', 'magic_link', etc.)
            
        Returns:
            The email (sub claim) from the token
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                raise HTTPException(status_code=401, detail="Invalid authentication token")
            
            # If type checking is requested, verify the token type
            if check_type and payload.get("type") != check_type:
                logger.warning(f"Token type mismatch. Expected: {check_type}, Got: {payload.get('type')}")
                raise HTTPException(status_code=401, detail="Invalid token type")
            
            return email
        except JWTError as e:
            logger.error(f"JWT error: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid authentication token")

class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True, check_refresh: bool = False):
        super(JWTBearer, self).__init__(auto_error=auto_error)
        self.check_refresh = check_refresh

    async def __call__(self, request: Request):
        # First try to get token from cookie
        token = request.cookies.get("access_token")
        
        if token:
            # Remove 'Bearer ' if it exists in the cookie
            if token.startswith("Bearer "):
                token = token.replace("Bearer ", "")
            
            try:
                # Check the appropriate token type
                token_type = "refresh" if self.check_refresh else "access"
                JWTHandler.verify_token(token, check_type=token_type)
                return token
            except HTTPException:
                pass
            
        # If no valid cookie, try the Authorization header
        credentials = await super(JWTBearer, self).__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(status_code=403, detail="Invalid authentication scheme")
            
            token_type = "refresh" if self.check_refresh else "access"
            JWTHandler.verify_token(credentials.credentials, check_type=token_type)
            return credentials.credentials
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code")