from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...core.database import get_db, VoicePricing

pricing_router = APIRouter()

@pricing_router.get("/pricing/voices")
async def get_voice_pricing(db: Session = Depends(get_db)):
    """Get all voice pricing information."""
    voices = db.query(VoicePricing).filter(VoicePricing.is_active == True).all()
    return [
        {
            "name": voice.name,
            "country": voice.country,
            "language": voice.language,
            "price_per_char": voice.price_per_char,
            "gender": voice.gender,
            "description": voice.description,
            "is_neural": voice.is_neural
        }
        for voice in voices
    ]