// Initialize Stripe
const stripe = Stripe(STRIPE_PUBLISHABLE_KEY);
const elements = stripe.elements();

// Create card element
const card = elements.create('card');
card.mount('#card-element');

// Handle form submission
async function handlePayment(amount) {
    try {
        // Create payment intent
        const response = await fetch('/payment/create-intent', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ amount }),
        });
        
        const { clientSecret } = await response.json();
        
        // Confirm payment
        const result = await stripe.confirmCardPayment(clientSecret, {
            payment_method: {
                card: card,
                billing_details: {
                    email: userEmail  // You'll need to set this variable
                }
            }
        });
        
        if (result.error) {
            // Handle error
            console.error(result.error);
            alert('Payment failed: ' + result.error.message);
        } else {
            // Payment successful
            if (result.paymentIntent.status === 'succeeded') {
                alert('Payment successful!');
                // Handle successful payment (e.g., start conversion process)
            }
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error processing payment');
    }
}

// Save card for future use
async function saveCard() {
    try {
        const result = await stripe.createPaymentMethod({
            type: 'card',
            card: card,
            billing_details: {
                email: userEmail  // You'll need to set this variable
            }
        });
        
        if (result.error) {
            throw result.error;
        }
        
        // Save payment method to your backend
        const response = await fetch('/payment/methods/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                payment_method_id: result.paymentMethod.id
            }),
        });
        
        const data = await response.json();
        if (data.status === 'success') {
            alert('Card saved successfully!');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error saving card');
    }
} 