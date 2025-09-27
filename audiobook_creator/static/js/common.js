// Navigation and authentication functions
const LANDING_INITIAL_NAV = `
    <a href="/blog" class="nav-button">Resources</a>
    <a href="/pricing" class="nav-button">Pricing</a>
    <a href="#" class="nav-button" data-nav-login="true">Log in</a>
    <a href="#" class="nav-button primary-button" data-nav-signup="true">Get Started</a>
`;

async function updateNavigation() {
    const navButtons = document.querySelector('.nav-buttons');
    if (!navButtons) {
        return;
    }

    showAnonymousNavPending(true);

    let isAuthenticated = false;
    try {
        console.log("updateNavigation called");
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000);
        const response = await fetch('/auth/status', {
            credentials: 'include',
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (response.ok) {
            const data = await response.json();
            isAuthenticated = Boolean(data && data.authenticated);
            console.log("Authentication status:", isAuthenticated);
        }
    } catch (error) {
        console.error('Error checking authentication:', error);
    }

    if (isAuthenticated) {
        navButtons.dataset.state = 'authenticated';
        navButtons.innerHTML = `
            <a href="/create" class="nav-button">Create audiobook</a>
            <a href="/pricing" class="nav-button">Pricing</a>
            <a href="/account" class="nav-button">Account</a>
            <a href="#" class="nav-button" onclick="logout()">Logout</a>
        `;

        // Only redirect to create if we're on the exact root path
        if (window.location.pathname === '/') {
            window.location.href = '/create';
            return;
        }
    } else {
        showAnonymousNavPending(false);
    }

    const currentPath = window.location.pathname;
    const currentButton = navButtons.querySelector(`[href="${currentPath}"]`);
    if (currentButton) {
        currentButton.classList.add('active');
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

    if (navButtons.dataset.state === desiredState && navButtons.innerHTML.trim().length > 0) {
        return;
    }

    navButtons.dataset.state = desiredState;

    navButtons.innerHTML = LANDING_INITIAL_NAV;

    if (hasHighlight) {
        navButtons.querySelectorAll('[data-nav-login]').forEach(anchor => {
            anchor.addEventListener('click', event => {
                hideAnonOverlays();
                highlightSignup(event);
            });
        });
        navButtons.querySelectorAll('[data-nav-signup]').forEach(anchor => {
            anchor.addEventListener('click', event => {
                hideAnonOverlays();
                highlightSignup(event);
            });
        });
    } else {
        navButtons.querySelector('[data-nav-login]')?.setAttribute('href', '/#login');
        navButtons.querySelector('[data-nav-signup]')?.setAttribute('href', '/#signup');
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

function hideAnonOverlays() {
    const navButtons = document.querySelector('.nav-buttons');
    if (!navButtons || navButtons.dataset.state !== 'anonymous') {
        return;
    }

    navButtons.dataset.state = 'loading';
    navButtons.innerHTML = LANDING_INITIAL_NAV;

    navButtons.querySelector('[data-nav-login]')?.removeAttribute('data-nav-login');
    navButtons.querySelector('[data-nav-signup]')?.removeAttribute('data-nav-signup');
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