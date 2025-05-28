// website/admin/js/admin_auth.js
// Handles admin authentication, session management.

/**
 * Retrieves the admin authentication token from session storage.
 * @returns {string|null} The admin auth token or null if not found.
 */
function getAdminAuthToken() {
    return sessionStorage.getItem('adminAuthToken');
}

/**
 * Retrieves the admin user data from session storage.
 * @returns {object|null} The admin user object or null if not found/invalid.
 */
function getAdminUser() {
    const userString = sessionStorage.getItem('adminUser');
    if (userString) {
        try {
            return JSON.parse(userString);
        } catch (e) {
            console.error("Erreur lors du parsing des données admin utilisateur:", e);
            sessionStorage.removeItem('adminUser');
            sessionStorage.removeItem('adminAuthToken'); // Clear token if user data is corrupt
            return null;
        }
    }
    return null;
}

/**
 * Checks if an admin is logged in. Redirects to login page if not.
 * Updates the admin user greeting if logged in.
 * @returns {boolean} True if admin is logged in, false otherwise.
 */
function checkAdminLogin() {
    const token = getAdminAuthToken();
    const adminUser = getAdminUser();

    // Check if on the login page itself to prevent redirect loop
    if (window.location.pathname.includes('admin_login.html')) {
        // If already on login page and token exists, try to redirect to dashboard
        if (token && adminUser && adminUser.is_admin) {
            // window.location.href = 'admin_dashboard.html'; // This was causing issues in the original admin_login.html
            // It's better to handle this check on pages *other* than login.
        }
        return true; // Allow login page to load
    }

    // For all other admin pages, require login
    if (!token || !adminUser || !adminUser.is_admin) {
        window.location.href = 'admin_login.html';
        return false;
    }

    // Update greeting if element exists
    const greetingElement = document.getElementById('admin-user-greeting');
    if (greetingElement) {
        greetingElement.textContent = `Bonjour, ${adminUser.prenom || adminUser.email}!`;
    }
    return true;
}

/**
 * Logs out the current admin user.
 * Clears admin data and token from session storage, shows a toast, and redirects to login.
 */
function adminLogout() {
    sessionStorage.removeItem('adminAuthToken');
    sessionStorage.removeItem('adminUser');
    showAdminToast("Vous avez été déconnecté.", "info"); // Assumes showAdminToast is in admin_ui.js
    window.location.href = 'admin_login.html';
}

/**
 * Handles the admin login form submission.
 * This function is specific to admin_login.html and might be included directly there
 * or called from admin_main.js if admin_login.html includes admin_main.js.
 * For modularity, it's defined here.
 * @param {Event} event - The form submission event.
 */
async function handleAdminLoginFormSubmit(event) {
    event.preventDefault();
    const email = document.getElementById('admin-email').value;
    const password = document.getElementById('admin-password').value;
    const messageElement = document.getElementById('admin-login-message');
    if (messageElement) messageElement.textContent = '';

    if (!email || !password) {
        if (messageElement) messageElement.textContent = 'Veuillez remplir tous les champs.';
        return;
    }

    try {
        // Note: Admin login might use a general auth endpoint or a specific admin one.
        // The original admin_login.html uses /api/auth/login.
        // We'll assume API_BASE_URL is for general API and is loaded.
        const response = await fetch(`${API_BASE_URL}/auth/login`, { // Or API_ADMIN_BASE_URL if login is admin-specific
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const result = await response.json();

        if (response.ok && result.success && result.user && result.user.is_admin) {
            sessionStorage.setItem('adminAuthToken', result.token);
            sessionStorage.setItem('adminUser', JSON.stringify(result.user));
            showAdminToast('Connexion réussie. Redirection...', 'success');
            window.location.href = 'admin_dashboard.html';
        } else if (response.ok && result.success && result.user && !result.user.is_admin) {
            if (messageElement) messageElement.textContent = 'Accès refusé. Ce compte n\'est pas un administrateur.';
            showAdminToast('Accès administrateur requis.', 'error');
        } else {
            if (messageElement) messageElement.textContent = result.message || 'E-mail ou mot de passe incorrect.';
            showAdminToast(result.message || 'Échec de la connexion.', 'error');
        }
    } catch (error) {
        console.error('Erreur de connexion admin:', error);
        if (messageElement) messageElement.textContent = 'Erreur de communication avec le serveur.';
        showAdminToast('Erreur de connexion.', 'error');
    }
}
