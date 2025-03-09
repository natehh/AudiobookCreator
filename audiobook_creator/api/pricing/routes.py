from fastapi import APIRouter, Depends, UploadFile, HTTPException, File, Form, Request
from sqlalchemy.orm import Session
from ...core.database import get_db, VoicePricing, VoiceTier, Payment, Usage, User
from ...core.stripe_service import StripeService
from ...core.converter import get_chapters
from ..auth.routes import get_current_user
from typing import Optional
from pydantic import BaseModel
import json
import urllib.parse
import tempfile
import os
from pathlib import Path
import stripe

pricing_router = APIRouter()

class PaymentMethodCreate(BaseModel):
    payment_method_id: str

class PaymentIntentCreate(BaseModel):
    amount: float

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
            "description": voice.description,
            "voice_id": voice.voice_id
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
        if not isinstance(voice_data, dict) or 'price_per_char' not in voice_data or 'voice_id' not in voice_data:
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
                "voice_id": voice_data['voice_id']
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

@pricing_router.post("/payment/create-intent")
async def create_payment_intent(
    file: UploadFile = File(...),
    voice_id: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a payment intent based on file and voice selection."""
    try:
        # Calculate price using same logic as /pricing/calculate
        voice_id = urllib.parse.unquote(voice_id)
        voice_data = json.loads(voice_id)
        if not isinstance(voice_data, dict) or 'price_per_char' not in voice_data or 'voice_id' not in voice_data:
            raise HTTPException(400, "Invalid voice data format")
            
        price_per_char = float(voice_data['price_per_char'])
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename[file.filename.rfind('.'):]) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            # Calculate price using same method as pricing/calculate
            chapters = get_chapters(Path(temp_path))
            char_count = sum(len(content) for _, content in chapters)
            total_price = char_count * price_per_char
            
            # Enforce minimum payment of $0.50
            if total_price > 0:
                total_price = max(total_price, 0.50)
            
            # Convert amount to cents for Stripe
            amount_cents = int(total_price * 100)
            
            # Create or get Stripe customer
            if not current_user.stripe_customer_id:
                customer = await StripeService.create_customer(current_user.email)
                current_user.stripe_customer_id = customer.id
                db.commit()
            
            # Create payment intent
            intent = await StripeService.create_payment_intent(
                amount_cents=amount_cents,
                customer_id=current_user.stripe_customer_id
            )
            
            # Create payment record
            payment = Payment(
                user_id=current_user.id,
                amount=total_price,
                stripe_payment_intent_id=intent.id,
                status='pending'
            )
            db.add(payment)
            db.commit()
            
            return {
                "clientSecret": intent.client_secret,
                "payment_id": payment.id
            }
        finally:
            # Clean up temporary file
            os.unlink(temp_path)
            
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid voice selection format")
    except ValueError as e:
        raise HTTPException(400, f"Invalid price format: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@pricing_router.post("/payment-methods/add")
async def add_payment_method(
    payment_method: PaymentMethodCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a payment method to the user's account."""
    try:
        # Create or get Stripe customer
        if not current_user.stripe_customer_id:
            try:
                customer = await StripeService.create_customer(current_user.email)
                current_user.stripe_customer_id = customer.id
                db.commit()
            except Exception as e:
                print(f"Error creating Stripe customer: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to create Stripe customer: {str(e)}"
                )
        
        try:
            # Attach payment method to customer
            payment_method = await StripeService.add_payment_method(
                payment_method_id=payment_method.payment_method_id,
                customer_id=current_user.stripe_customer_id
            )
            return {"status": "success", "payment_method": payment_method}
        except Exception as e:
            print(f"Error attaching payment method: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to attach payment method: {str(e)}"
            )
    except Exception as e:
        print(f"Unexpected error in add_payment_method: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=str(e))

@pricing_router.post("/payment/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Stripe webhook events."""
    try:
        body = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        try:
            event = stripe.Webhook.construct_event(
                body,
                sig_header,
                os.getenv("STRIPE_WEBHOOK_SECRET")
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        if event.type == "payment_intent.succeeded":
            payment_intent = event.data.object
            # Update payment status
            payment = db.query(Payment).filter_by(
                stripe_payment_intent_id=payment_intent.id
            ).first()
            if payment:
                payment.status = "succeeded"
                db.commit()
                
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@pricing_router.get("/stripe-key")
async def get_stripe_key(current_user: User = Depends(get_current_user)):
    """Get Stripe publishable key."""
    key = os.getenv("STRIPE_PUBLISHABLE_KEY")
    if not key:
        raise HTTPException(
            status_code=500,
            detail="Stripe publishable key not found in environment variables"
        )
    return {"publishableKey": key}

@pricing_router.get("/payment-methods")
async def get_payment_methods(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's payment methods."""
    try:
        if not current_user.stripe_customer_id:
            return []
        
        customer = await StripeService.get_customer(current_user.stripe_customer_id)
        payment_methods = stripe.PaymentMethod.list(
            customer=current_user.stripe_customer_id,
            type="card"
        )
        
        return payment_methods.data
    except Exception as e:
        print(f"Error getting payment methods: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@pricing_router.delete("/payment-methods/{payment_method_id}")
async def delete_payment_method(
    payment_method_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a payment method."""
    try:
        if not current_user.stripe_customer_id:
            raise HTTPException(status_code=400, detail="No customer ID found")
        
        # Detach the payment method from the customer
        payment_method = stripe.PaymentMethod.detach(payment_method_id)
        return {"status": "success", "payment_method": payment_method}
    except Exception as e:
        print(f"Error deleting payment method: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))