// Navigation and authentication functions
async function updateNavigation() {
    try {
        console.log("updateNavigation called");
        const response = await fetch('/api/account', {
            credentials: 'include'
        });
        
        let isAuthenticated = false;
        
        if (response.ok) {
            try {
                // Try to parse the response as JSON to verify we got actual user data
                const userData = await response.json();
                isAuthenticated = userData && userData.email; // Check if we have a user email
                console.log("User data:", userData);
            } catch (e) {
                console.error("Failed to parse user data:", e);
                isAuthenticated = false;
            }
        }
        
        console.log("Authentication status:", isAuthenticated);
        console.log("Current path:", window.location.pathname);
        
        const navButtons = document.querySelector('.nav-buttons');
        
        if (isAuthenticated) {
            console.log("Setting authenticated navigation");
            navButtons.innerHTML = `
                <a href="/static/create_conversion.html" class="nav-button">Create audiobook</a>
                <a href="/static/pricing.html" class="nav-button">Pricing</a>
                <a href="/static/account.html" class="nav-button">Account</a>
                <a href="#" class="nav-button" onclick="logout()">Logout</a>
            `;
            
            // If we're on the index page and authenticated, redirect to create_conversion
            if (window.location.pathname === '/static/index.html' || window.location.pathname === '/') {
                console.log("Redirecting authenticated user from index to create_conversion");
                window.location.href = '/static/create_conversion.html';
                return; // Stop execution to prevent further navigation changes
            }
        } else {
            // For pricing page, show limited navigation without redirecting
            if (window.location.pathname === '/static/pricing.html') {
                console.log("Setting unauthenticated pricing page navigation");
                navButtons.innerHTML = `
                    <a href="/static/create_conversion.html" class="nav-button">Create audiobook</a>
                    <a href="/static/pricing.html" class="nav-button">Pricing</a>
                    <a href="/static/index.html#signup" class="nav-button">Sign Up</a>
                    <a href="/static/index.html#login" class="nav-button">Login</a>
                `;
            } else if (window.location.pathname !== '/static/index.html' && window.location.pathname !== '/') {
                // Only redirect to index if we're not already there
                console.log("Redirecting to index page");
                window.location.href = '/static/index.html';
                return; // Stop execution to prevent further navigation changes
            }
        }
        
        // Set active class for current page
        const currentPath = window.location.pathname;
        const currentButton = navButtons.querySelector(`[href="${currentPath}"]`);
        if (currentButton) {
            currentButton.classList.add('active');
        }
    } catch (error) {
        console.error('Error checking authentication:', error);
        // Don't redirect if on pricing page
        if (window.location.pathname === '/static/pricing.html') {
            // Default to unauthenticated navigation on error for pricing page
            const navButtons = document.querySelector('.nav-buttons');
            navButtons.innerHTML = `
                <a href="/static/create_conversion.html" class="nav-button">Create audiobook</a>
                <a href="/static/pricing.html" class="nav-button">Pricing</a>
                <a href="/static/index.html#signup" class="nav-button">Sign Up</a>
                <a href="/static/index.html#login" class="nav-button">Login</a>
            `;
        } else if (window.location.pathname !== '/static/index.html' && window.location.pathname !== '/') {
            window.location.href = '/static/index.html';
        }
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