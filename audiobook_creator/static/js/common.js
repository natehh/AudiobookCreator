// Navigation and authentication functions
const PUBLIC_ROUTES = new Set(['/', '/pricing', '/blog']);

async function updateNavigation() {
    const navButtons = document.querySelector('.nav-buttons');
    if (!navButtons) {
        return;
    }

    showAnonymousNavPending(true);

    try {
        console.log("updateNavigation called");
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000);

        const response = await fetch('/api/account', {
            credentials: 'include',
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            showAnonymousNavPending(false);
            return;
        }

        let isAuthenticated = false;
        try {
            const userData = await response.json();
            isAuthenticated = userData && userData.email;
            console.log("User data:", userData);
        } catch (e) {
            console.error("Failed to parse user data:", e);
            isAuthenticated = false;
        }

        console.log("Authentication status:", isAuthenticated);
        console.log("Current path:", window.location.pathname);

        if (isAuthenticated) {
            navButtons.dataset.state = 'authenticated';
            navButtons.innerHTML = `
                <a href="/create" class="nav-button">Create audiobook</a>
                <a href="/pricing" class="nav-button">Pricing</a>
                <a href="/account" class="nav-button">Account</a>
                <a href="#" class="nav-button" onclick="logout()">Logout</a>
            `;

            if (window.location.pathname === '/') {
                window.location.href = '/create';
                return;
            }
        } else if (!PUBLIC_ROUTES.has(window.location.pathname)) {
            window.location.href = '/';
            return;
        }

        const currentPath = window.location.pathname;
        const currentButton = navButtons.querySelector(`[href="${currentPath}"]`);
        if (currentButton) {
            currentButton.classList.add('active');
        }
    } catch (error) {
        console.error('Error checking authentication:', error);
        if (!PUBLIC_ROUTES.has(window.location.pathname)) {
            window.location.href = '/';
        } else {
            showAnonymousNavPending(false);
        }
    }
}

async function updateNavigationCommon() {
    await updateNavigation();
}

function showAnonymousNavPending(initial = false) {
    const navButtons = document.querySelector('.nav-buttons');
    if (!navButtons) {
        return;
    }

    const hasHighlight = typeof highlightSignup === 'function';
    const desiredState = initial ? 'loading' : 'anonymous';

    if (navButtons.dataset.state === desiredState) {
        return;
    }

    navButtons.dataset.state = desiredState;

    const loginAnchor = hasHighlight ? '<a href="#" class="nav-button" onclick="highlightSignup(event)">Log in</a>' : '<a href="/#login" class="nav-button">Log in</a>';
    const signupAnchor = hasHighlight ? '<a href="#" class="nav-button primary-button" onclick="highlightSignup(event)">Get Started</a>' : '<a href="/#signup" class="nav-button primary-button">Get Started</a>';

    navButtons.innerHTML = `
        <a href="/blog" class="nav-button">Resources</a>
        <a href="/pricing" class="nav-button">Pricing</a>
        ${loginAnchor}
        ${signupAnchor}
    `;
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
window.updateNavigationCommon = updateNavigationCommon; 