from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...core.database import get_db, User, Conversion
from ..auth.tokens import JWTBearer, JWTHandler
from pydantic import BaseModel
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

account_router = APIRouter()

class AccountUpdate(BaseModel):
    name: Optional[str] = None

class ConversionResponse(BaseModel):
    id: str
    title: str
    author: str
    status: str
    progress: float
    created_at: str
    voice: Optional[str] = None

@account_router.get("/account")
async def get_account_info(
    token: str = Depends(JWTBearer()),
    db: Session = Depends(get_db)
):
    """Get user account information."""
    email = JWTHandler.verify_token(token)
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "email": user.email,
        "name": user.name,
        "created_at": user.created_at.isoformat()
    }

@account_router.put("/account")
async def update_account(
    update: AccountUpdate,
    token: str = Depends(JWTBearer()),
    db: Session = Depends(get_db)
):
    """Update user account information."""
    email = JWTHandler.verify_token(token)
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if update.name is not None:
        user.name = update.name
    
    try:
        db.commit()
        return {"message": "Account updated successfully"}
    except Exception as e:
        logger.error(f"Error updating account: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update account")

@account_router.get("/conversions")
async def get_user_conversions(
    token: str = Depends(JWTBearer()),
    db: Session = Depends(get_db)
):
    """Get user's conversions."""
    email = JWTHandler.verify_token(token)
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    conversions = db.query(Conversion).filter(
        Conversion.user_id == user.id
    ).order_by(Conversion.created_at.desc()).all()
    
    return [
        ConversionResponse(
            id=conv.id,
            title=conv.title,
            author=conv.author,
            status=conv.status,
            progress=conv.progress,
            created_at=conv.created_at.isoformat(),
            voice=conv.voice_id
        ) for conv in conversions
    ]

@account_router.delete("/account")
async def delete_account(
    token: str = Depends(JWTBearer()),
    db: Session = Depends(get_db)
):
    """Delete user account and all associated data."""
    email = JWTHandler.verify_token(token)
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Delete all user's conversions first
        db.query(Conversion).filter(Conversion.user_id == user.id).delete()
        # Delete the user
        db.delete(user)
        db.commit()
        return {"message": "Account deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting account: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete account") 