from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

class JWTHandler:
    @staticmethod
    def create_access_token(data: dict, expires_delta: int = ACCESS_TOKEN_EXPIRE_MINUTES):
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(minutes=expires_delta)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str, check_type: str = None):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                raise HTTPException(status_code=401, detail="Invalid authentication token")
            
            # If type checking is requested, verify the token type
            if check_type and payload.get("type") != check_type:
                raise HTTPException(status_code=401, detail="Invalid token type")
            
            return email
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid authentication token")

class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        # First try to get token from cookie
        token = request.cookies.get("access_token")
        
        if token:
            # Remove 'Bearer ' if it exists in the cookie
            if token.startswith("Bearer "):
                token = token.replace("Bearer ", "")
                
            if not JWTHandler.verify_token(token):
                raise HTTPException(status_code=403, detail="Invalid token or expired token")
            return token
            
        # If no cookie, try the Authorization header
        credentials = await super(JWTBearer, self).__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(status_code=403, detail="Invalid authentication scheme")
            if not JWTHandler.verify_token(credentials.credentials):
                raise HTTPException(status_code=403, detail="Invalid token or expired token")
            return credentials.credentials
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code")