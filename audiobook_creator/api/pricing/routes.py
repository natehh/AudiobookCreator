from fastapi import APIRouter, Depends, UploadFile, HTTPException, File, Form
from sqlalchemy.orm import Session
from ...core.database import get_db, VoicePricing, VoiceTier
from pathlib import Path
from ...utils.ebook import get_chapters
import json
import urllib.parse
import tempfile
import os

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

@pricing_router.post("/pricing/calculate")
async def calculate_price(
    file: UploadFile = File(...),
    voice_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Calculate price for converting a file with selected voice."""
    try:
        voice_id = urllib.parse.unquote(voice_id)
        voice_data = json.loads(voice_id)
        if not isinstance(voice_data, dict) or 'price_per_char' not in voice_data or 'name' not in voice_data:
            raise HTTPException(400, "Invalid voice data format")
            
        price_per_char = float(voice_data['price_per_char'])
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename[file.filename.rfind('.'):]) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            # Get actual character count using the same method as converter
            chapters = get_chapters(Path(temp_path))
            char_count = sum(len(content) for _, content in chapters)
            
            # Calculate total price
            total_price = char_count * price_per_char
            
            return {
                "char_count": char_count,
                "price_per_char": price_per_char,
                "total_price": total_price,
                "voice_name": voice_data['name']
            }
        finally:
            # Clean up temporary file
            os.unlink(temp_path)
            
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid voice selection format")
    except ValueError as e:
        raise HTTPException(400, f"Invalid price format: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Error calculating price: {str(e)}")