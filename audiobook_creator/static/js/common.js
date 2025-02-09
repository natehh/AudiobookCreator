// Navigation and authentication functions
async function updateNavigation() {
    try {
        const response = await fetch('/api/account', {
            credentials: 'include'
        });
        
        const isAuthenticated = response.ok;
        const navButtons = document.querySelector('.nav-buttons');
        
        if (isAuthenticated) {
            navButtons.innerHTML = `
                <a href="/static/create_conversion.html" class="nav-button">Create audiobook</a>
                <a href="/static/pricing.html" class="nav-button">Pricing</a>
                <a href="/static/account.html" class="nav-button">Account</a>
                <a href="#" class="nav-button" onclick="logout()">Logout</a>
            `;
        } else {
            window.location.href = '/static/index.html';
        }
        
        // Set active class for current page
        const currentPath = window.location.pathname;
        const currentButton = navButtons.querySelector(`[href="${currentPath}"]`);
        if (currentButton) {
            currentButton.classList.add('active');
        }
    } catch (error) {
        console.error('Error checking authentication:', error);
        window.location.href = '/static/index.html';
    }
}

async function logout() {
    try {
        await fetch('/auth/logout', {
            method: 'POST',
            credentials: 'include'
        });
        window.location.reload();
    } catch (error) {
        showMessage('Error logging out', 'error');
        window.location.reload();
    }
}

// Utility functions
function showMessage(text, type) {
    const messageDiv = document.getElementById('message');
    if (!messageDiv) return;
    
    messageDiv.textContent = text;
    messageDiv.className = `message ${type}`;
    messageDiv.style.display = 'block';
    
    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 5000);
}

// Initialize navigation when DOM is loaded
document.addEventListener('DOMContentLoaded', updateNavigation); 