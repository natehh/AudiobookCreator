const API_URL = '';
let currentFile = null;

// Setup drag and drop
function initializeCreateConversion() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const voiceSelection = document.getElementById('voiceSelection');
    const errorText = document.getElementById('error');

    // Initially hide the voice selection
    voiceSelection.style.display = 'none';

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
    const voiceSelection = document.getElementById('voiceSelection');
    const errorText = document.getElementById('error');

    const validExtensions = ['.epub', '.mobi', '.txt'];
    const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    
    if (!validExtensions.includes(fileExtension)) {
        errorText.textContent = 'Unsupported file format. Please use .epub, .mobi, or .txt files.';
        return;
    }

    currentFile = file;
    errorText.textContent = '';
    
    // Show the voice selection and update the drop zone
    dropZone.innerHTML = `<p>Selected file: ${file.name}</p>`;
    voiceSelection.style.display = 'block';
    
    // Calculate initial pricing if voice is already selected
    updatePricing();
    updateStartButton();
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
    formData.append('voice_id', encodeURIComponent(select.value));

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
        document.getElementById('totalPrice').textContent = data.total_price.toFixed(2);
        pricingInfo.style.display = 'block';
    } catch (error) {
        errorText.textContent = `Error calculating price: ${error.message}`;
    }
}

async function startConversion() {
    const select = document.getElementById('voiceSelect');
    if (!select.value) {
        errorText.textContent = 'Please select a voice first';
        return;
    }

    const formData = new FormData();
    formData.append('file', currentFile);
    const voiceData = JSON.parse(select.value);
    formData.append('voice_id', voiceData.voice_id);

    try {
        const response = await fetch(`${API_URL}/convert/`, {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error('Conversion failed');
        }

        const data = await response.json();
        window.location.href = `/static/conversion.html?id=${data.id}`;
    } catch (error) {
        errorText.textContent = `Error: ${error.message}`;
    }
}

function cancelSelection() {
    const dropZone = document.getElementById('dropZone');
    const voiceSelection = document.getElementById('voiceSelection');
    const errorText = document.getElementById('error');

    // Reset file selection
    currentFile = null;
    dropZone.innerHTML = `
        <p>Drag and drop your ebook file here or click to select</p>
        <p>Supported formats: .epub, .mobi, .txt</p>
    `;
    
    // Clear voice selection
    document.getElementById('voiceSelect').value = '';
    // Hide voice selection section
    voiceSelection.style.display = 'none';
    // Hide pricing info
    document.getElementById('pricingInfo').style.display = 'none';
    // Clear any error messages
    errorText.textContent = '';
    // Update start button state
    updateStartButton();
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeCreateConversion();
    setupDemoPlayer('demoPlayer');
}); 