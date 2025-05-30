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
        // admin_main.js handles redirecting from login page if already logged in.
        // So, no specific action needed here for the login page itself.
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
    const errorDisplayElement = document.getElementById('login-error-message'); // Corrected ID

    if (errorDisplayElement) {
        errorDisplayElement.textContent = '';
        errorDisplayElement.classList.add('hidden');
    }

    if (!email || !password) {
        if (errorDisplayElement) {
            errorDisplayElement.textContent = 'Veuillez remplir tous les champs.';
            errorDisplayElement.classList.remove('hidden');
        }
        showAdminToast('Veuillez remplir tous les champs.', 'error');
        return;
    }

    try {
        // Use loginAdmin function from admin_api.js which targets the Node.js backend
        // loginAdmin is expected to be globally available as admin_api.js is loaded before admin_auth.js
        if (typeof loginAdmin !== 'function') {
            console.error("loginAdmin function is not defined. Ensure admin_api.js is loaded correctly.");
            showAdminToast("Erreur de configuration de la page.", "error");
            return;
        }
        const result = await loginAdmin(email, password);

        // The loginAdmin function in admin_api.js returns a structure like:
        // { success: true, message: 'Login successful!', token: 'fake-jwt-token-for-demo' }
        // or { success: false, message: 'Invalid email or password.' }
        // The Node.js server.js currently doesn't return a user object, just a token.
        // We'll adapt to store the token and perhaps a generic admin user object.

        if (result.success && result.token) {
            sessionStorage.setItem('adminAuthToken', result.token);
            // Since Node.js backend doesn't send full user object, create a placeholder or fetch separately if needed.
            // For now, just acknowledge admin status. A real app might fetch user details using the token.
            sessionStorage.setItem('adminUser', JSON.stringify({ email: email, is_admin: true, prenom: 'Admin' })); // Placeholder user
            showAdminToast('Connexion réussie. Redirection...', 'success');
            window.location.href = 'admin_dashboard.html';
        } else {
            if (errorDisplayElement) {
                errorDisplayElement.textContent = result.message || 'E-mail ou mot de passe incorrect.';
                errorDisplayElement.classList.remove('hidden');
            }
            showAdminToast(result.message || 'Échec de la connexion.', 'error');
        }
    } catch (error) {
        console.error('Erreur de connexion admin:', error);
        if (errorDisplayElement) {
            errorDisplayElement.textContent = 'Erreur de communication avec le serveur.';
            errorDisplayElement.classList.remove('hidden');
        }
        showAdminToast('Erreur de connexion.', 'error');
    }
}
