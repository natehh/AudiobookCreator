import stripe
from fastapi import HTTPException
import os
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class StripeService:
    @staticmethod
    async def create_payment_intent(amount_cents: int, customer_id: str = None):
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                customer=customer_id,
                payment_method_types=['card'],
                metadata={'type': 'pay_as_you_go'}
            )
            return intent
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def create_customer(email: str):
        try:
            customer = stripe.Customer.create(
                email=email,
            )
            return customer
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def get_customer(customer_id: str):
        try:
            return stripe.Customer.retrieve(customer_id)
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def add_payment_method(payment_method_id: str, customer_id: str):
        try:
            payment_method = stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id,
            )
            # Set as default payment method
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )
            return payment_method
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e)) 