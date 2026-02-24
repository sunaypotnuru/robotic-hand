// app.js – LUNA SPA Controller

const socket = io(); // keep socket connection for real‑time updates

// DOM elements
const loginSection = document.getElementById('login-section');
const homeSection = document.getElementById('home-section');
const dashboardSection = document.getElementById('dashboard-section');
const navLinks = document.getElementById('nav-links');
const navUser = document.getElementById('nav-user');
const topNav = document.getElementById('top-nav');
const mainSidebar = document.getElementById('main-sidebar');
const mainContent = document.getElementById('main-content');
const animOverlay = document.getElementById('animation-overlay');
const lottieContainer = document.getElementById('lottie-container');

// Futuristic Lottie Animation for logging in
const animationURL = 'https://assets2.lottiefiles.com/packages/lf20_q7uarxsb.json';
const frontAnimationURL = 'https://assets3.lottiefiles.com/packages/lf20_ujmvyzvw.json';

let lottieAnim = null;
let frontLottieAnim = null;

// Check initial auth status
async function checkAuth() {
    try {
        const res = await fetch('/api/auth-status');
        const data = await res.json();

        if (data.authenticated) {
            if (loginSection) loginSection.style.display = 'none';
            if (homeSection) homeSection.style.display = 'none';

            // Check for a pending redirect from Flask-Login
            const urlParams = new URLSearchParams(window.location.search);
            const nextParam = urlParams.get('next');
            if (nextParam && window.location.pathname === '/') {
                window.location.href = nextParam;
                return;
            }

            if (window.location.pathname === '/') {
                if (dashboardSection) dashboardSection.style.display = 'block';
                if (topNav) topNav.style.display = 'none';
                if (mainSidebar) mainSidebar.style.display = 'flex';
                if (mainContent) mainContent.classList.add('with-sidebar');

                // Set sidebar home link active
                document.querySelectorAll('#main-sidebar .nav-item').forEach(item => item.classList.remove('active'));
                const homeLink = document.getElementById('side-nav-home');
                if (homeLink) homeLink.classList.add('active');
            } else {
                if (dashboardSection) dashboardSection.style.display = 'none';
            }
            updateNavForUser(data.user);
        } else {
            showGuestLayout();
        }
    } catch (e) {
        console.error("Auth check failed:", e);
        showGuestLayout();
    }
}

// Show Home Layout
function showHome() {
    if (homeSection) homeSection.style.display = 'flex';
    if (loginSection) loginSection.style.display = 'none';
    if (dashboardSection) dashboardSection.style.display = 'none';
    if (topNav) topNav.style.display = 'flex';
    if (mainSidebar) mainSidebar.style.display = 'none';
    if (mainContent) mainContent.classList.remove('with-sidebar');

    // Load Front Page Lottie
    if (!frontLottieAnim && document.getElementById('front-lottie-container')) {
        frontLottieAnim = lottie.loadAnimation({
            container: document.getElementById('front-lottie-container'),
            renderer: 'svg',
            loop: true,
            autoplay: true,
            path: frontAnimationURL
        });
    }
    updateNavForGuest();
}

// Show login form OR hide it for public pages
function showGuestLayout() {
    if (window.location.pathname === '/') {
        showHome();

        // Auto-open login if requested via URL
        if (window.location.search.includes('login=1')) {
            openLogin();
        }
    } else {
        // We are on a public page like /about, /features, so hide the login overlay completely
        if (loginSection) loginSection.style.display = 'none';
        if (homeSection) homeSection.style.display = 'none';
        if (dashboardSection) dashboardSection.style.display = 'none';
        updateNavForGuest();
    }
}

// Open Login form explicitly
function openLogin(e) {
    if (e) e.preventDefault();
    if (homeSection) homeSection.style.display = 'none';
    if (loginSection) loginSection.style.display = 'flex';
}

// Show dashboard after animation (Used during actual login)
function showDashboardWithAnimation(user) {
    playAnimation(() => {
        loginSection.style.display = 'none';

        const urlParams = new URLSearchParams(window.location.search);
        const nextParam = urlParams.get('next');
        if (nextParam) {
            window.location.href = nextParam;
            return;
        }

        if (window.location.pathname === '/') {
            if (dashboardSection) dashboardSection.style.display = 'block';
            if (topNav) topNav.style.display = 'none';
            if (mainSidebar) mainSidebar.style.display = 'flex';
            if (mainContent) mainContent.classList.add('with-sidebar');

            // Set sidebar home link active
            document.querySelectorAll('#main-sidebar .nav-item').forEach(item => item.classList.remove('active'));
            const homeLink = document.getElementById('side-nav-home');
            if (homeLink) homeLink.classList.add('active');
        }
        updateNavForUser(user);
    });
}

// Play Lottie animation, then call callback
function playAnimation(callback) {
    animOverlay.style.display = 'flex';

    let isDone = false;
    const safeCallback = () => {
        if (!isDone) {
            isDone = true;
            animOverlay.style.display = 'none';
            callback();
        }
    };

    // Failsafe in case animation fails to load (403, 404, etc)
    const fallbackTimer = setTimeout(safeCallback, 2500);

    try {
        if (!lottieAnim) {
            lottieAnim = lottie.loadAnimation({
                container: lottieContainer,
                renderer: 'svg',
                loop: false,
                autoplay: true,
                path: animationURL
            });
            lottieAnim.addEventListener('complete', safeCallback);
            lottieAnim.addEventListener('data_failed', safeCallback);
            lottieAnim.addEventListener('error', safeCallback);
        } else {
            lottieAnim.goToAndPlay(0, true);
            lottieAnim.addEventListener('complete', safeCallback, { once: true });
        }
    } catch (e) {
        safeCallback();
    }
}

// Update Navigation UI for Guest
function updateNavForGuest() {
    const p = window.location.pathname;
    navLinks.innerHTML = `
        <a href="/" class="nav-link ${p === '/' ? 'active' : ''}">Home</a>
        <a href="/about" class="nav-link ${p.startsWith('/about') ? 'active' : ''}">About LUNA</a>
        <a href="/features" class="nav-link ${p.startsWith('/features') ? 'active' : ''}">Features</a>
        <a href="/team" class="nav-link ${p.startsWith('/team') ? 'active' : ''}">Team</a>
        <a href="/contact" class="nav-link ${p.startsWith('/contact') ? 'active' : ''}">Contact</a>
    `;
    navUser.innerHTML = `<button class="btn-primary btn-login" style="padding: 5px 15px;">LOGIN</button>`;

    // Wire up all login buttons created dynamically
    setTimeout(() => {
        document.querySelectorAll('.btn-login, .open-login').forEach(btn => {
            btn.removeEventListener('click', openLogin);
            btn.addEventListener('click', openLogin);
        });
    }, 50);
}

// Update Navigation UI for Authenticated User
function updateNavForUser(user) {
    const p = window.location.pathname;
    let links = `
        <a href="/" class="nav-link ${p === '/' ? 'active' : ''}">Dashboard</a>
        <a href="/settings" class="nav-link ${p.startsWith('/settings') ? 'active' : ''}">AI Settings</a>
        <a href="/diagnostics" class="nav-link ${p.startsWith('/diagnostics') ? 'active' : ''}">Diagnostics</a>
        <a href="/logs" class="nav-link ${p.startsWith('/logs') ? 'active' : ''}">My Logs</a>`;
    if (user.role === 'admin') {
        links += `<a href="/admin" class="nav-link ${p.startsWith('/admin') ? 'active' : ''}" style="color: #ff0099">Admin</a>`;
    }
    navLinks.innerHTML = links;
    navUser.innerHTML = `
        <span class="user-name">👤 ${user.full_name || user.username} [${user.role.toUpperCase()}]</span>
        <button class="btn-logout" onclick="logout()">LOGOUT</button>
    `;
}

// AJAX login
async function login(username, password) {
    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (data.success) {
            // Hide login errors if any
            const errDiv = document.getElementById('login-error');
            if (errDiv) errDiv.style.display = 'none';

            showDashboardWithAnimation(data.user);
        } else {
            const errDiv = document.getElementById('login-error');
            if (errDiv) {
                errDiv.textContent = data.message;
                errDiv.style.display = 'block';
            } else {
                alert('Login failed: ' + data.message);
            }
        }
    } catch (e) {
        console.error("Login request failed:", e);
    }
}

// Logout
async function logout() {
    await fetch('/api/logout', { method: 'POST' });
    showGuestLayout();
}

// Attach login form submit handler
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.querySelector('#login-section form');
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const username = document.querySelector('[name="username"]').value;
            const password = document.querySelector('[name="password"]').value;
            login(username, password);
        });
    }

    // Bind any existing login buttons
    document.querySelectorAll('.btn-login, .open-login').forEach(btn => {
        btn.addEventListener('click', openLogin);
    });

    checkAuth();
});
