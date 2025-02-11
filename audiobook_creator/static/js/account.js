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
        
        const grid = document.getElementById('conversionsGrid');
        grid.innerHTML = conversions.map(conv => `
            <div class="conversion-card">
                <a href="/static/conversion.html?id=${conv.id}" style="text-decoration: none; color: inherit;">
                    <h3>${conv.title}</h3>
                    <p>Author: ${conv.author}</p>
                    <div class="conversion-status status-${conv.status.toLowerCase()}">
                        ${conv.status}
                    </div>
                </a>
                ${conv.status === 'completed' ? 
                    `<a href="/download/${conv.id}" class="button" download>Download Audiobook</a>` : 
                    ''}
            </div>
        `).join('');
    } catch (error) {
        showMessage('Error loading conversions', 'error');
    }
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

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    loadAccountInfo();
    loadConversions();
    loadPaymentMethods();
}); 