// website/admin/js/admin_auth.js
// Handles admin authentication, session management.

const ADMIN_TOKEN_KEY = 'adminAuthToken';
const ADMIN_USER_KEY = 'adminUser';

/**
 * Retrieves the admin authentication token from session storage.
 * @returns {string|null} The admin auth token or null if not found.
 */
function getAdminAuthToken() {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}

/**
 * Sets the admin authentication token in session storage.
 * @param {string} token - The admin auth token.
 */
function setAdminAuthToken(token) {
    if (token) {
        sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
    } else {
        sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    }
}

/**
 * Retrieves the admin user data from session storage.
 * @returns {object|null} The admin user object or null if not found/invalid.
 */
function getAdminUser() {
    const userString = sessionStorage.getItem(ADMIN_USER_KEY);
    if (userString) {
        try {
            return JSON.parse(userString);
        } catch (e) {
            console.error("Error parsing admin user data from session storage:", e);
            sessionStorage.removeItem(ADMIN_USER_KEY);
            sessionStorage.removeItem(ADMIN_TOKEN_KEY); // Clear token if user data is corrupt
            return null;
        }
    }
    return null;
}

/**
 * Sets the admin user data and token in session storage.
 * @param {object|null} userData - The admin user object.
 * @param {string|null} token - The admin auth token.
 */
function setAdminUserSession(userData, token) {
    if (userData && token) {
        sessionStorage.setItem(ADMIN_USER_KEY, JSON.stringify(userData));
        setAdminAuthToken(token);
    } else {
        sessionStorage.removeItem(ADMIN_USER_KEY);
        sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    }
    // Optionally, dispatch an event or call a UI update function here
    // updateAdminHeaderDisplay(); // Example
}


/**
 * Checks if an admin is logged in. Redirects to login page if not.
 * Updates the admin user greeting if logged in.
 * @returns {boolean} True if admin is logged in, false otherwise.
 */
function checkAdminLogin() {
    const token = getAdminAuthToken();
    const adminUser = getAdminUser();

    const onLoginPage = window.location.pathname.includes('admin_login.html');

    if (token && adminUser && adminUser.is_admin) {
        if (onLoginPage) {
            // Already logged in and on login page, redirect to dashboard
            window.location.href = 'admin_dashboard.html';
            return false; // Prevent login page from fully rendering
        }
        // Update greeting if element exists (moved to setupAdminUIGlobals in admin_main.js)
        return true; // Logged in and not on login page
    } else {
        if (!onLoginPage) {
            // Not logged in and not on login page, redirect to login
            window.location.href = 'admin_login.html';
            return false;
        }
        return true; // Allow login page to load if not logged in
    }
}

/**
 * Logs out the current admin user.
 * Clears admin data and token from session storage, shows a toast, and redirects to login.
 */
function adminLogout() {
    const adminUser = getAdminUser(); // Get user before clearing session for logging
    const adminEmailForLog = adminUser ? adminUser.email : 'Unknown';

    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    sessionStorage.removeItem(ADMIN_USER_KEY);
    
    if (typeof showAdminToast === 'function') {
        showAdminToast("You have been logged out.", "info");
    } else {
        alert("You have been logged out."); // Fallback
    }
    console.log(`Admin ${adminEmailForLog} logged out.`);
    window.location.href = 'admin_login.html';
}

/**
 * Handles the admin login form submission.
 * @param {Event} event - The form submission event.
 */
async function handleAdminLoginFormSubmit(event) {
    event.preventDefault();
    const emailInput = document.getElementById('admin-email');
    const passwordInput = document.getElementById('admin-password');
    const errorDisplayElement = document.getElementById('login-error-message');
    const loginButton = event.target.querySelector('button[type="submit"]');

    if (errorDisplayElement) {
        errorDisplayElement.textContent = '';
        errorDisplayElement.classList.add('hidden');
    }
    if(loginButton) loginButton.disabled = true;


    const email = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email || !password) {
        const msg = 'Please fill in all fields.';
        if (errorDisplayElement) {
            errorDisplayElement.textContent = msg;
            errorDisplayElement.classList.remove('hidden');
        }
        if (typeof showAdminToast === 'function') showAdminToast(msg, 'error');
        else alert(msg);
        if(loginButton) loginButton.disabled = false;
        return;
    }

    try {
        // adminApi.loginAdmin is defined in admin_api.js
        const result = await adminApi.loginAdmin(email, password);

        if (result.success && result.token && result.user) {
            setAdminUserSession(result.user, result.token); // Store user and token
            
            if (typeof showAdminToast === 'function') {
                showAdminToast('Login successful. Redirecting...', 'success');
            }
            console.log('Admin login successful for:', result.user.email);
            window.location.href = 'admin_dashboard.html';
        } else {
            // Error message should come from result.message (from Flask)
            const errorMessage = result.message || 'Invalid email or password.';
            if (errorDisplayElement) {
                errorDisplayElement.textContent = errorMessage;
                errorDisplayElement.classList.remove('hidden');
            }
            if (typeof showAdminToast === 'function') {
                showAdminToast(errorMessage, 'error');
            } else {
                alert(errorMessage);
            }
            if(loginButton) loginButton.disabled = false;
        }
    } catch (error) {
        console.error('Admin login error:', error);
        const errorMessage = error.data?.message || error.message || 'Login failed due to a server error.';
        if (errorDisplayElement) {
            errorDisplayElement.textContent = errorMessage;
            errorDisplayElement.classList.remove('hidden');
        }
        if (typeof showAdminToast === 'function') {
            showAdminToast(errorMessage, 'error');
        } else {
            alert(errorMessage);
        }
        if(loginButton) loginButton.disabled = false;
    }
}
