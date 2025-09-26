const API_URL = '';
let currentFile = null;
let STRIPE_PUBLISHABLE_KEY = null;

// Setup drag and drop
function initializeCreateConversion() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const errorText = document.getElementById('error');

    // Setup file input click handler
    dropZone.addEventListener('click', () => fileInput.click());

    // Setup drag and drop handlers
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('dragover');
        
        const file = e.dataTransfer.files[0];
        handleFile(file);
    });

    // Setup file input change handler
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        handleFile(file);
    });

    // Initialize voice selection
    loadVoices();
    
    // Add event listeners for the action buttons
    document.getElementById('startConversion').addEventListener('click', startConversion);
    document.getElementById('cancelSelection').addEventListener('click', cancelSelection);
    document.getElementById('voiceSelect').addEventListener('change', () => {
        updatePricing();
        updateStartButton();
        updateSteps(2); // Progress to step 2 when voice is selected
    });
}

// Update the steps indicator
function updateSteps(activeStep) {
    const steps = document.querySelectorAll('.step');
    
    steps.forEach((step, index) => {
        // Convert from 0-based index to 1-based step number
        const stepNumber = index + 1;
        
        if (stepNumber < activeStep) {
            // Previous steps are marked as completed
            step.classList.remove('active');
            step.classList.add('completed');
        } else if (stepNumber === activeStep) {
            // Current step is active
            step.classList.add('active');
            step.classList.remove('completed');
        } else {
            // Future steps are neither active nor completed
            step.classList.remove('active');
            step.classList.remove('completed');
        }
    });
}

async function loadVoices() {
    try {
        const response = await fetch('/api/pricing/voices');
        const voiceTiers = await response.json();
        const select = document.getElementById('voiceSelect');
        
        voiceTiers.forEach(tier => {
            const optgroup = document.createElement('optgroup');
            optgroup.label = `${tier.tier_name} - $${tier.price_per_char.toFixed(6)}/char`;
            
            tier.voices.forEach(voice => {
                const option = document.createElement('option');
                option.value = JSON.stringify({
                    name: voice.name,
                    voice_id: voice.voice_id,
                    price_per_char: tier.price_per_char
                });
                option.textContent = `${voice.name} (${voice.country})`;
                optgroup.appendChild(option);
            });
            
            select.appendChild(optgroup);
        });
    } catch (error) {
        console.error('Error loading voices:', error);
        errorText.textContent = 'Error loading available voices';
    }
}

function updateStartButton() {
    const select = document.getElementById('voiceSelect');
    const startButton = document.getElementById('startConversion');
    startButton.disabled = !select.value || !currentFile;
}

async function handleFile(file) {
    if (!file) return;
    
    const dropZone = document.getElementById('dropZone');
    const errorText = document.getElementById('error');

    const validExtensions = ['.epub', '.mobi', '.txt'];
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    
    if (!validExtensions.includes(fileExtension)) {
        errorText.textContent = 'Unsupported file format. Please use .epub, .mobi, or .txt files.';
        return;
    }

    currentFile = file;
    errorText.textContent = '';
    
    // Update the drop zone to show selected file
    dropZone.innerHTML = `
        <div class="file-info">
            <div class="file-icon">📄</div>
            <div class="file-details">
                <div class="file-name">${file.name}</div>
                <div class="file-type">${file.type || fileExtension.toUpperCase().substring(1)} - ${formatFileSize(file.size)}</div>
            </div>
        </div>
        <div class="upload-subtext">Click to choose a different file</div>
        <input type="file" id="fileInput" accept=".epub,.mobi,.txt" style="display: none">
    `;
    
    // Update the file input reference since we replaced the HTML
    document.getElementById('fileInput').addEventListener('change', (e) => {
        const newFile = e.target.files[0];
        handleFile(newFile);
    });
    
    dropZone.classList.add('file-selected');
    
    // Progress to step 2
    updateSteps(2);
    
    // Calculate pricing if voice is already selected
    updatePricing();
    updateStartButton();
}

// Format file size in human-readable format
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' bytes';
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / 1048576).toFixed(1) + ' MB';
}

async function updatePricing() {
    const select = document.getElementById('voiceSelect');
    const pricingInfo = document.getElementById('pricingInfo');
    
    if (!select.value || !currentFile) {
        pricingInfo.style.display = 'none';
        return;
    }

    const formData = new FormData();
    formData.append('file', currentFile);
    const voiceData = JSON.parse(select.value);
    formData.append('voice_id', JSON.stringify({
        voice_id: voiceData.voice_id,
        price_per_char: voiceData.price_per_char
    }));

    try {
        const response = await fetch('/api/pricing/calculate', {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to calculate price');
        }

        const data = await response.json();
        
        document.getElementById('charCount').textContent = data.char_count.toLocaleString();
        document.getElementById('pricePerChar').textContent = data.price_per_char.toFixed(6);
        
        const calculatedPrice = data.total_price;
        const totalPriceElement = document.getElementById('totalPrice');

        if (calculatedPrice > 0 && calculatedPrice < 0.50) {
            // Show adjusted price with explanation
            totalPriceElement.textContent = '0.50';
            // Add or update minimum price message
            let minPriceMsg = document.getElementById('minPriceMessage');
            if (!minPriceMsg) {
                minPriceMsg = document.createElement('p');
                minPriceMsg.id = 'minPriceMessage';
                minPriceMsg.style.color = 'var(--primary-color)';
                minPriceMsg.style.fontSize = '0.9em';
                minPriceMsg.style.marginTop = '5px';
                pricingInfo.appendChild(minPriceMsg);
            }
            minPriceMsg.textContent = `(Adjusted from $${calculatedPrice.toFixed(2)} to minimum payment amount)`;
        } else {
            // Show regular price
            totalPriceElement.textContent = calculatedPrice.toFixed(2);
            // Remove minimum price message if it exists
            const minPriceMsg = document.getElementById('minPriceMessage');
            if (minPriceMsg) {
                minPriceMsg.remove();
            }
        }
        
        pricingInfo.style.display = 'block';
        
        // Enable step 3 when pricing is available
        updateSteps(3);
    } catch (error) {
        errorText.textContent = `Error calculating price: ${error.message}`;
    }
}

async function startConversion() {
    const select = document.getElementById('voiceSelect');
    const errorText = document.getElementById('error');
    const startButton = document.getElementById('startConversion');
    
    errorText.textContent = ''; // Clear any previous errors
    
    if (!select.value) {
        errorText.textContent = 'Please select a voice first';
        return;
    }

    try {
        startButton.disabled = true;
        startButton.innerHTML = '<div class="loader"></div> Processing...';
        
        const totalPriceElement = document.getElementById('totalPrice');
        const totalPrice = parseFloat(totalPriceElement.textContent);
        
        if (isNaN(totalPrice)) {
            throw new Error('Invalid price amount');
        }

        // Skip payment process if price is 0
        if (totalPrice === 0) {
            // Directly start conversion without payment
            const formData = new FormData();
            formData.append('file', currentFile);
            const voiceData = JSON.parse(select.value);
            formData.append('voice_id', voiceData.voice_id);
            formData.append('payment_id', 0); // Add a placeholder payment_id for free conversions

            const conversionResponse = await fetch(`${API_URL}/convert/`, {
                method: 'POST',
                body: formData,
                credentials: 'include'
            });

            if (!conversionResponse.ok) {
                const convError = await conversionResponse.json();
                throw new Error(convError.detail || 'Conversion failed');
            }

            const data = await conversionResponse.json();
            window.location.href = `/conversion?id=${data.id}`;
            return;
        }

        // For paid conversions, ensure minimum charge of $0.50
        const adjustedPrice = totalPrice < 0.50 ? 0.50 : totalPrice;

        // Create payment intent
        const formData = new FormData();
        formData.append('file', currentFile);
        const voiceData = JSON.parse(select.value);
        formData.append('voice_id', JSON.stringify({
            voice_id: voiceData.voice_id,
            price_per_char: voiceData.price_per_char
        }));
        
        const response = await fetch('/api/payment/create-intent', {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create payment');
        }

        const { clientSecret, payment_id } = await response.json();

        // Get the payment method
        const paymentMethodResponse = await fetch('/api/payment-methods', {
            credentials: 'include'
        });
        
        if (!paymentMethodResponse.ok) {
            throw new Error('Failed to get payment methods');
        }
        
        const paymentMethods = await paymentMethodResponse.json();

        if (!paymentMethods || paymentMethods.length === 0) {
            // Redirect to payment method page if no payment method is available
            window.location.href = '/payment';
            return;
        }

        // Use the first payment method
        const paymentMethod = paymentMethods[0];

        // Initialize Stripe
        if (!STRIPE_PUBLISHABLE_KEY) {
            throw new Error('Stripe not properly initialized');
        }
        const stripe = Stripe(STRIPE_PUBLISHABLE_KEY);

        // Confirm the payment
        const { error: confirmError, paymentIntent } = await stripe.confirmCardPayment(clientSecret, {
            payment_method: paymentMethod.id
        });

        if (confirmError) {
            throw new Error(confirmError.message);
        }

        if (paymentIntent.status !== 'succeeded') {
            throw new Error('Payment failed');
        }

        // If payment successful, start the conversion
        formData.append('payment_id', payment_id);

        const conversionResponse = await fetch(`${API_URL}/convert/`, {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });

        if (!conversionResponse.ok) {
            const convError = await conversionResponse.json();
            throw new Error(convError.detail || 'Conversion failed');
        }

        const data = await conversionResponse.json();
        window.location.href = `/conversion?id=${data.id}`;
    } catch (error) {
        console.error('Error in startConversion:', error);
        errorText.textContent = `Error: ${error.message}`;
        startButton.disabled = false;
        startButton.textContent = 'Create Audiobook';
    }
}

function cancelSelection() {
    const dropZone = document.getElementById('dropZone');
    const errorText = document.getElementById('error');

    // Reset file selection
    currentFile = null;
    dropZone.innerHTML = `
        <div class="upload-icon">📚</div>
        <div class="upload-text">Drag and drop your ebook file here</div>
        <div class="upload-subtext">or click to browse files</div>
        <div class="upload-subtext">Supported formats: .epub, .mobi, .txt</div>
        <input type="file" id="fileInput" accept=".epub,.mobi,.txt" style="display: none">
    `;
    
    // Re-add click event listener to the file input
    document.getElementById('fileInput').addEventListener('change', (e) => {
        const file = e.target.files[0];
        handleFile(file);
    });
    
    // Remove any classes added to the drop zone
    dropZone.classList.remove('file-selected');
    
    // Reset the voice dropdown
    document.getElementById('voiceSelect').value = '';
    
    // Hide pricing info
    document.getElementById('pricingInfo').style.display = 'none';
    
    // Clear any error messages
    errorText.textContent = '';
    
    // Update start button state
    updateStartButton();
    
    // Reset steps to step 1
    updateSteps(1);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Get Stripe publishable key
        const response = await fetch('/api/stripe-key');
        if (!response.ok) {
            throw new Error('Failed to get Stripe key');
        }
        const data = await response.json();
        STRIPE_PUBLISHABLE_KEY = data.publishableKey;
    } catch (error) {
        console.error('Error getting Stripe key:', error);
        document.getElementById('error').textContent = 'Error initializing payment system';
    }

    initializeCreateConversion();
    setupDemoPlayer('demoPlayer');
    
    // Add CSS for loading animation
    const style = document.createElement('style');
    style.textContent = `
        .loader {
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s ease-in-out infinite;
            margin-right: 10px;
            display: inline-block;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);
}); 