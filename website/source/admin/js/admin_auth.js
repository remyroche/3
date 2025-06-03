// website/source/admin/js/admin_auth.js

const ADMIN_TOKEN_KEY = 'adminAuthToken';
const ADMIN_USER_KEY = 'adminUser';
// To store email temporarily between password and TOTP steps
const PENDING_TOTP_EMAIL_KEY = 'pendingTotpAdminEmail'; 

function getAdminAuthToken() {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}// website/source/admin/js/admin_auth.js

const ADMIN_TOKEN_KEY = 'adminAuthToken';
const ADMIN_USER_KEY = 'adminUser';
const PENDING_TOTP_EMAIL_KEY = 'pendingTotpAdminEmail'; 

function getAdminAuthToken() {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}

function setAdminAuthToken(token) {
    if (token) {
        sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
    } else {
        sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    }
}

function getAdminUser() {
    const userString = sessionStorage.getItem(ADMIN_USER_KEY);
    if (userString) {
        try {
            return JSON.parse(userString);
        } catch (e) {
            console.error("Error parsing admin user data from session storage:", e);
            clearAdminSession(); 
            return null;
        }
    }
    return null;
}

function setAdminUserSession(userData, token) {
    if (userData && token) {
        sessionStorage.setItem(ADMIN_USER_KEY, JSON.stringify(userData));
        setAdminAuthToken(token);
    } else {
        clearAdminSession();
    }
}

function clearAdminSession() {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    sessionStorage.removeItem(ADMIN_USER_KEY);
    sessionStorage.removeItem(PENDING_TOTP_EMAIL_KEY); 
}

function checkAdminLogin() {
    const token = getAdminAuthToken();
    const adminUser = getAdminUser();
    const onLoginPage = window.location.pathname.includes('admin_login.html');

    if (token && adminUser && adminUser.is_admin) {
        if (onLoginPage) {
            window.location.href = 'admin_dashboard.html';
            return false; 
        }
        return true;
    } else {
        clearAdminSession(); 
        if (!onLoginPage) {
            window.location.href = 'admin_login.html';
            return false;
        }
        return true; 
    }
}

function adminLogout() {
    const adminUser = getAdminUser();
    const adminEmailForLog = adminUser ? adminUser.email : 'Unknown';
    clearAdminSession();
    
    if (typeof showAdminToast === 'function') {
        showAdminToast("You have been logged out.", "info");
    } else {
        alert("You have been logged out.");
    }
    console.log(`Admin ${adminEmailForLog} logged out.`);
    window.location.href = 'admin_login.html';
}

async function handleAdminLoginFormSubmit(event) {
    event.preventDefault();
    const emailInput = document.getElementById('admin-email');
    const passwordInput = document.getElementById('admin-password');
    const errorDisplayElement = document.getElementById('login-error-message');
    const passwordSection = document.getElementById('password-section');
    const totpSection = document.getElementById('totp-section');
    const submitPasswordButton = document.getElementById('submit-password-button');
    const submitTotpButton = document.getElementById('submit-totp-button');

    // Clear previous PENDING_TOTP_EMAIL_KEY from sessionStorage at the start of a new login attempt
    sessionStorage.removeItem(PENDING_TOTP_EMAIL_KEY);

    if (errorDisplayElement) {
        errorDisplayElement.textContent = ''; // Safe
        errorDisplayElement.classList.add('hidden');
    }
    if(submitPasswordButton) submitPasswordButton.disabled = true;

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email || !password) {
        const msg = 'Please fill in all fields.';
        if (errorDisplayElement) { errorDisplayElement.textContent = msg; errorDisplayElement.classList.remove('hidden'); } // Safe
        if (typeof showAdminToast === 'function') showAdminToast(msg, 'error');
        else alert(msg);
        if(submitPasswordButton) submitPasswordButton.disabled = false;
        return;
    }

    try {
        const result = await adminApi.loginAdminStep1Password(email, password);

        if (result.success) {
            if (result.totp_required) {
                sessionStorage.setItem(PENDING_TOTP_EMAIL_KEY, email); 
                passwordSection.classList.add('hidden');
                submitPasswordButton.classList.add('hidden');
                totpSection.classList.remove('hidden');
                document.getElementById('admin-totp-code').focus();
                if (typeof showAdminToast === 'function') showAdminToast(result.message || 'Please enter your TOTP code.', 'info');
            } else {
                setAdminUserSession(result.user, result.token);
                if (typeof showAdminToast === 'function') showAdminToast(result.message || 'Login successful!', 'success');
                window.location.href = 'admin_dashboard.html';
            }
        } else {
            const errorMessage = result.message || 'Invalid email or password.';
            if (errorDisplayElement) { errorDisplayElement.textContent = errorMessage; errorDisplayElement.classList.remove('hidden'); } // Safe
            if (typeof showAdminToast === 'function') showAdminToast(errorMessage, 'error');
        }
    } catch (error) {
        console.error('Admin login step 1 error:', error);
        const errorMessage = error.data?.message || error.message || 'Login failed due to a server error.';
        if (errorDisplayElement) { errorDisplayElement.textContent = errorMessage; errorDisplayElement.classList.remove('hidden'); } // Safe
        if (typeof showAdminToast === 'function') showAdminToast(errorMessage, 'error');
    } finally {
        if(submitPasswordButton) submitPasswordButton.disabled = false;
    }
}

async function handleTotpVerification() {
    const totpCodeInput = document.getElementById('admin-totp-code');
    const errorDisplayElement = document.getElementById('login-error-message'); 
    const submitTotpButton = document.getElementById('submit-totp-button');
    const email = sessionStorage.getItem(PENDING_TOTP_EMAIL_KEY);

    if (errorDisplayElement) { errorDisplayElement.textContent = ''; errorDisplayElement.classList.add('hidden');} // Safe
    if(submitTotpButton) submitTotpButton.disabled = true;

    const totpCode = totpCodeInput.value.trim();

    if (!email) {
        if (typeof showAdminToast === 'function') showAdminToast('Login session expired. Please start over.', 'error');
        window.location.reload(); 
        return;
    }
    if (!totpCode) {
        const msg = 'Please enter the TOTP code.';
        if (errorDisplayElement) { errorDisplayElement.textContent = msg; errorDisplayElement.classList.remove('hidden'); } // Safe
        if (typeof showAdminToast === 'function') showAdminToast(msg, 'error');
        if(submitTotpButton) submitTotpButton.disabled = false;
        return;
    }

    try {
        const result = await adminApi.loginAdminStep2VerifyTotp(email, totpCode);
        if (result.success && result.token && result.user) {
            setAdminUserSession(result.user, result.token);
            sessionStorage.removeItem(PENDING_TOTP_EMAIL_KEY); // Clear on success
            if (typeof showAdminToast === 'function') showAdminToast(result.message || 'Login successful!', 'success');
            window.location.href = 'admin_dashboard.html';
        } else {
            const errorMessage = result.message || 'Invalid TOTP code.';
            if (errorDisplayElement) { errorDisplayElement.textContent = errorMessage; errorDisplayElement.classList.remove('hidden'); } // Safe
            if (typeof showAdminToast === 'function') showAdminToast(errorMessage, 'error');
            totpCodeInput.focus(); 
        }
    } catch (error) {
        console.error('Admin TOTP verification error:', error);
        const errorMessage = error.data?.message || error.message || 'TOTP verification failed due to a server error.';
        if (errorDisplayElement) { errorDisplayElement.textContent = errorMessage; errorDisplayElement.classList.remove('hidden'); } // Safe
        if (typeof showAdminToast === 'function') showAdminToast(errorMessage, 'error');
    } finally {
        if(submitTotpButton) submitTotpButton.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const simpleLoginButton = document.getElementById('simplelogin-button');
    if (simpleLoginButton) {
        simpleLoginButton.addEventListener('click', () => {
            if (typeof adminApi !== 'undefined' && typeof adminApi.initiateSimpleLogin === 'function') {
                adminApi.initiateSimpleLogin();
            } else {
                console.error("adminApi.initiateSimpleLogin is not defined.");
                showAdminToast("SimpleLogin integration error. Please contact support.", "error");
            }
        });
    }

    const submitTotpButton = document.getElementById('submit-totp-button');
    if (submitTotpButton) {
        submitTotpButton.addEventListener('click', handleTotpVerification);
    }
    const totpCodeInput = document.getElementById('admin-totp-code');
    if (totpCodeInput) {
        totpCodeInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault(); 
                handleTotpVerification();
            }
        });
    }
});
