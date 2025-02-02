from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...core.database import get_db, VoicePricing, VoiceTier

pricing_router = APIRouter()

@pricing_router.get("/pricing/voices")
async def get_voice_pricing(db: Session = Depends(get_db)):
    """Get all voice pricing information grouped by tier."""
    voices = db.query(VoicePricing).join(VoiceTier).filter(VoicePricing.is_active == True).all()
    
    # Group voices by tier
    voice_tiers = {}
    for voice in voices:
        tier_name = voice.tier_info.name
        if tier_name not in voice_tiers:
            voice_tiers[tier_name] = {
                "tier_name": tier_name,
                "price_per_char": voice.tier_info.price_per_char,
                "description": voice.tier_info.description,
                "voices": []
            }
        
        voice_tiers[tier_name]["voices"].append({
            "name": voice.name,
            "country": voice.country,
            "language": voice.language,
            "gender": voice.gender,
            "description": voice.description
        })
    
    return list(voice_tiers.values())