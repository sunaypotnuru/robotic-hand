// router.js - Client-Side Router

const pages = {
    dashboard: document.getElementById('dashboard-section'),
    settings: document.getElementById('page-settings'),
    diagnostics: document.getElementById('page-diagnostics'),
    logs: document.getElementById('page-logs'),
    profile: document.getElementById('page-profile'),
    admin: document.getElementById('page-admin')
};

let currentPage = null;

// Hide all pages
function hideAllPages() {
    Object.values(pages).forEach(page => {
        if (page) page.style.display = 'none';
    });
}

// Show a specific page by name
function showPage(pageName, addToHistory = true) {
    if (pageName === 'admin' || pageName.startsWith('admin_')) {
        // We let normal navigation handle admin for now to fallback to full reloads.
        return;
    }

    if (!pages[pageName]) {
        console.warn(`Page "${pageName}" not found in SPA. Falling back to normal navigation.`);
        return;
    }

    hideAllPages();
    pages[pageName].style.display = 'block';
    currentPage = pageName;

    // Update URL
    if (addToHistory) {
        const url = pageName === 'dashboard' ? '/' : `/${pageName}`;
        history.pushState({ page: pageName }, '', url);
    }

    // Initialize page components
    initPage(pageName);
    
    // Update active class on nav links
    if (window.setActiveNavLink) {
        window.setActiveNavLink();
    }
}

// Initialize page-specific functionality
function initPage(pageName) {
    switch (pageName) {
        case 'dashboard':
            if (window.initDashboard) window.initDashboard();
            break;
        case 'settings':
            if (window.initSettings) window.initSettings();
            break;
        case 'diagnostics':
            if (window.initDiagnostics) window.initDiagnostics();
            break;
        case 'logs':
            if (window.initLogs) window.initLogs();
            break;
        case 'profile':
            if (window.initProfile) window.initProfile();
            break;
        default:
            break;
    }
}

// Handle browser back/forward
window.addEventListener('popstate', (event) => {
    if (event.state && event.state.page) {
        showPage(event.state.page, false);
    } else {
        // Default to dashboard if logged in, else home
        if (window.isLoggedIn && window.isLoggedIn()) {
            showPage('dashboard', false);
        } else if (window.showHome) {
            window.showHome();
        }
    }
});

// Intercept link clicks
document.addEventListener('click', (e) => {
    const link = e.target.closest('a');
    if (!link) return;

    const href = link.getAttribute('href');
    if (!href || link.target === '_blank' || href.startsWith('http') || href.startsWith('#')) return;

    // Check if it's an internal link handled by SPA
    if (href.startsWith('/')) {
        const pageName = href.substring(1) || 'dashboard';
        
        // Admin pages and other non-SPA pages fall back to default browser navigation
        if (pageName.startsWith('admin') || pageName === 'about' || pageName === 'contact' || pageName === 'features' || pageName === 'team') {
            return;
        }

        if (pages[pageName] || pageName === 'dashboard') {
            e.preventDefault();
            showPage(pageName);
        }
    }
});

// Expose for use in app.js
window.router = { showPage };
