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
        const response = await fetch(`${API_URL}/convert/${conversionId}`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch conversion state');
        }
        
        const data = await response.json();
        updateConversionUI(data);
    } catch (error) {
        document.getElementById('error').textContent = `Error: ${error.message}`;
    }
}

function setupWebSocket(conversionId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/conversion/${conversionId}`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateConversionUI(data);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        document.getElementById('error').textContent = 'Error connecting to server';
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
    const progressBar = document.getElementById('progressBar');
    const statusText = document.getElementById('status');
    const downloadBtn = document.getElementById('downloadBtn');
    const errorText = document.getElementById('error');
    
    progressBar.style.width = `${data.progress * 100}%`;
    statusText.textContent = data.status;
    
    if (data.status === 'completed') {
        downloadBtn.style.display = 'block';
        downloadBtn.onclick = () => {
            window.location.href = `/download/${data.id}`;
        };
        if (ws) {
            ws.close();
        }
    } else if (data.status === 'failed') {
        errorText.textContent = data.error || 'Conversion failed';
        if (ws) {
            ws.close();
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeConversion); 