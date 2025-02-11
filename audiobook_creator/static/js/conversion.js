const API_URL = '';
let ws;

function initializeConversion() {
    const urlParams = new URLSearchParams(window.location.search);
    const conversionId = urlParams.get('id');
    if (!conversionId) {
        window.location.href = '/static/create_conversion.html';
        return;
    }

    fetchConversionState();
    setupWebSocket(conversionId);
}

async function fetchConversionState() {
    const urlParams = new URLSearchParams(window.location.search);
    const conversionId = urlParams.get('id');
    
    try {
        const response = await fetch(`${API_URL}/status/${conversionId}`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch conversion state');
        }
        
        const data = await response.json();
        updateConversionUI(data);
    } catch (error) {
        document.getElementById('error-message').textContent = `Error: ${error.message}`;
        document.getElementById('error-message').style.display = 'block';
    }
}

function setupWebSocket(conversionId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${conversionId}`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateConversionUI(data);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        document.getElementById('error-message').textContent = 'Error connecting to server';
        document.getElementById('error-message').style.display = 'block';
    };
    
    ws.onclose = () => {
        // Attempt to reconnect after a delay
        setTimeout(() => {
            if (document.getElementById('status').textContent !== 'Completed') {
                setupWebSocket(conversionId);
            }
        }, 5000);
    };
}

function updateConversionUI(data) {
    const progress = document.getElementById('progress');
    const progressContainer = document.getElementById('progress-container');
    const progressText = document.getElementById('progress-text');
    const status = document.getElementById('status');
    const downloadSection = document.getElementById('download-section');
    const errorMessage = document.getElementById('error-message');
    const title = document.getElementById('title');
    const author = document.getElementById('author');
    
    // Update book metadata if available
    if (data.metadata) {
        title.textContent = data.metadata.title || 'Untitled';
        author.textContent = data.metadata.author || '';
    }
    
    // Update progress and status
    if (data.progress !== undefined) {
        progressContainer.style.display = 'block';
        progress.style.width = `${data.progress * 100}%`;
        progressText.textContent = `${Math.round(data.progress * 100)}%`;
    }
    
    if (data.status === 'processing') {
        status.textContent = 'Your audiobook is being created. Feel free to leave this page - you can return to it later using the same URL.';
    } else {
        status.textContent = data.status;
    }
    
    if (data.status === 'completed') {
        downloadSection.style.display = 'block';
        if (ws) {
            ws.close();
        }
    } else if (data.status === 'failed') {
        errorMessage.textContent = data.error || 'Conversion failed';
        errorMessage.style.display = 'block';
        if (ws) {
            ws.close();
        }
    }
}

async function downloadAudiobook() {
    const urlParams = new URLSearchParams(window.location.search);
    const conversionId = urlParams.get('id');
    if (conversionId) {
        window.location.href = `/download/${conversionId}`;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeConversion); 