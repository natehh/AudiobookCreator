async function loadAccountInfo() {
    try {
        const response = await fetch('/api/account', {
            credentials: 'include'
        });
        const data = await response.json();
        
        document.getElementById('email').value = data.email;
        document.getElementById('name').value = data.name || '';
    } catch (error) {
        showMessage('Error loading account information', 'error');
    }
}

async function loadConversions() {
    try {
        const response = await fetch('/api/conversions', {
            credentials: 'include'
        });
        const conversions = await response.json();
        
        console.log('Full conversion objects:', JSON.stringify(conversions, null, 2));
        
        const grid = document.getElementById('conversionsGrid');
        grid.innerHTML = conversions.map(conv => {
            console.log('Processing conversion:', JSON.stringify(conv, null, 2));
            console.log('Expiration date:', conv.expiration_date);
            
            // Handle UTC dates properly
            const now = new Date();
            const expiration = conv.expiration_date ? new Date(conv.expiration_date) : null;
            const isExpired = expiration ? expiration < now : false;
            const timeRemaining = expiration ? formatTimeLeft(expiration) : '';
            
            console.log('Is expired:', isExpired);
            console.log('Time remaining:', timeRemaining);
            
            return `
                <div class="conversion-card">
                    <a href="/static/conversion.html?id=${conv.id}" style="text-decoration: none; color: inherit;">
                        <h3>${conv.title}</h3>
                        <p>Author: ${conv.author}</p>
                        <p>Voice: ${conv.voice ? getFriendlyVoice(conv.voice) : 'Unknown'}</p>
                        <div class="conversion-status status-${conv.status.toLowerCase()}">
                            ${conv.status}
                        </div>
                        ${expiration ? 
                            `<div class="expiration-time ${isExpired ? 'expired' : ''}" data-expiration="${conv.expiration_date}">${timeRemaining}</div>` : 
                            ''}
                    </a>
                    ${conv.status === 'completed' && !isExpired ? 
                        `<a href="/download/${conv.id}" class="button" download>Download Audiobook</a>` : 
                        ''}
                </div>
            `;
        }).join('');

        // Set up periodic updates for time remaining
        const updateTimeRemaining = () => {
            const cards = document.querySelectorAll('.conversion-card');
            console.log('Found conversion cards:', cards.length);
            
            cards.forEach(card => {
                const expirationElement = card.querySelector('.expiration-time');
                console.log('Expiration element:', expirationElement);
                
                if (expirationElement) {
                    const expirationDate = expirationElement.getAttribute('data-expiration');
                    console.log('Expiration date from attribute:', expirationDate);
                    
                    if (expirationDate) {
                        const newTimeRemaining = formatTimeLeft(new Date(expirationDate));
                        console.log('New time remaining:', newTimeRemaining);
                        
                        if (newTimeRemaining === '(Expired)') {
                            expirationElement.classList.add('expired');
                            const downloadButton = card.querySelector('.button');
                            if (downloadButton) {
                                downloadButton.style.display = 'none';
                            }
                        }
                        expirationElement.textContent = newTimeRemaining;
                    }
                }
            });
        };

        // Clear any existing intervals before setting up a new one
        if (window.expirationUpdateInterval) {
            clearInterval(window.expirationUpdateInterval);
        }
        window.expirationUpdateInterval = setInterval(updateTimeRemaining, 10000);
        
        // Run the update immediately once
        updateTimeRemaining();
    } catch (error) {
        console.error('Error loading conversions:', error);
        showMessage('Error loading conversions', 'error');
    }
}

function formatTimeLeft(expirationDate) {
    if (!expirationDate) return '';
    
    const now = new Date();
    const expiration = new Date(expirationDate);
    const diffTime = expiration.getTime() - now.getTime();
    
    if (diffTime <= 0) {
        return '(Expired)';
    }
    
    const days = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diffTime % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diffTime % (1000 * 60 * 60)) / (1000 * 60));
    
    if (days === 0) {
        if (hours === 0) {
            return `(${minutes} minutes remaining)`;
        }
        return `(${hours} hours, ${minutes} minutes remaining)`;
    }
    
    return `(${days} days, ${hours} hours remaining)`;
}

async function loadPaymentMethods() {
    try {
        const response = await fetch('/api/payment-methods', {
            credentials: 'include'
        });
        const paymentMethods = await response.json();
        
        const container = document.getElementById('payment-methods');
        
        if (paymentMethods.length === 0) {
            container.innerHTML = `
                <div class="no-payment-methods">
                    No payment methods added yet
                </div>
            `;
            return;
        }
        
        container.innerHTML = paymentMethods.map(method => `
            <div class="payment-method">
                <div class="payment-method-info">
                    <div class="card-icon">💳</div>
                    <div class="card-details">
                        <div class="card-number">${method.card.brand} •••• ${method.card.last4}</div>
                        <div class="expiry">Expires ${method.card.exp_month}/${method.card.exp_year}</div>
                    </div>
                </div>
                <button onclick="removePaymentMethod('${method.id}')" class="remove-card">
                    Remove
                </button>
            </div>
        `).join('');
    } catch (error) {
        showMessage('Error loading payment methods', 'error');
    }
}

async function updateAccount() {
    const name = document.getElementById('name').value;
    
    try {
        const response = await fetch('/api/account', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({ name })
        });
        
        if (response.ok) {
            showMessage('Account updated successfully', 'success');
        } else {
            throw new Error('Failed to update account');
        }
    } catch (error) {
        showMessage('Error updating account', 'error');
    }
}

async function removePaymentMethod(paymentMethodId) {
    if (!confirm('Are you sure you want to remove this payment method?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/payment-methods/${paymentMethodId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        if (response.ok) {
            showMessage('Payment method removed successfully', 'success');
            loadPaymentMethods();
        } else {
            throw new Error('Failed to remove payment method');
        }
    } catch (error) {
        showMessage('Error removing payment method', 'error');
    }
}

async function confirmDeleteAccount() {
    if (confirm('Are you sure you want to delete your account? This action cannot be undone.')) {
        try {
            const response = await fetch('/api/account', {
                method: 'DELETE',
                credentials: 'include'
            });
            
            if (response.ok) {
                window.location.href = '/static/index.html';
            } else {
                throw new Error('Failed to delete account');
            }
        } catch (error) {
            showMessage('Error deleting account', 'error');
        }
    }
}

function manageBilling() {
    window.location.href = '/static/billing.html';
}

function getFriendlyVoice(voiceId) {
    const match = /-(\w+)Neural$/.exec(voiceId);
    return match ? match[1] : voiceId;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    loadAccountInfo();
    loadConversions();
    loadPaymentMethods();
}); 