// website/js/auth.js
// Handles user authentication, session management, and account display.

/**
 * Retrieves the authentication token from session storage.
 * @returns {string|null} The auth token or null if not found.
 */
function getAuthToken() {
    return sessionStorage.getItem('authToken');
}

/**
 * Sets or removes the authentication token in session storage.// website/js/auth.js
// Handles user authentication, session management, and account display.

function getAuthToken() {
    return sessionStorage.getItem('authToken');
}

function setAuthToken(token) {
    if (token) {
        sessionStorage.setItem('authToken', token);
    } else {
        sessionStorage.removeItem('authToken');
    }
}

function getCurrentUser() {
    const userString = sessionStorage.getItem('currentUser');
    if (userString) {
        try {
            return JSON.parse(userString);
        } catch (e) {
            sessionStorage.removeItem('currentUser');
            sessionStorage.removeItem('authToken');
            return null;
        }
    }
    return null;
}

function setCurrentUser(userData, token = null) {
    if (userData) {
        sessionStorage.setItem('currentUser', JSON.stringify(userData));
        if (token) setAuthToken(token);
    } else {
        sessionStorage.removeItem('currentUser');
        sessionStorage.removeItem('authToken');
    }
    updateLoginState();
    updateCartDisplay(); // Changed from updateCartCountDisplay
    document.dispatchEvent(new CustomEvent('authStateChanged', { detail: { isLoggedIn: !!userData } }));
}

async function logoutUser() {
    setCurrentUser(null); 
    showGlobalMessage(t('public.js.logged_out'), "info");

    const bodyId = document.body.id;
    if (bodyId === 'page-compte' || bodyId === 'page-paiement') {
        window.location.href = 'compte.html';
    }
}

function updateLoginState() {
    const currentUser = getCurrentUser();
    const accountLinkDesktop = document.querySelector('header nav a[href="compte.html"]');
    const accountLinkMobile = document.querySelector('#mobile-menu-dropdown a[href="compte.html"]');
    const cartIconDesktop = document.querySelector('header a[href="panier.html"]');
    const cartIconMobile = document.querySelector('.md\\:hidden a[href="panier.html"]');

    if (currentUser) {
        if (accountLinkDesktop) accountLinkDesktop.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-7 h-7 text-brand-classic-gold"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg> <span class="ml-1 text-xs">${currentUser.prenom || t('public.nav.account')}</span>`;
        if (accountLinkMobile) accountLinkMobile.textContent = `${t('public.nav.account')} (${currentUser.prenom || ''})`;
    } else {
        if (accountLinkDesktop) accountLinkDesktop.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-7 h-7"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>`;
        if (accountLinkMobile) accountLinkMobile.textContent = t('public.nav.account');
    }
    if(cartIconDesktop) cartIconDesktop.style.display = 'inline-flex';
    if(cartIconMobile) cartIconMobile.style.display = 'inline-flex';
}

async function handleLogin(event) {
    event.preventDefault();
    const loginForm = event.target;
    clearFormErrors(loginForm); 
    const emailField = loginForm.querySelector('#login-email');
    const passwordField = loginForm.querySelector('#login-password');
    const email = emailField.value;
    const password = passwordField.value;
    const loginMessageElement = document.getElementById('login-message');

    let isValid = true;
    if (loginMessageElement) loginMessageElement.textContent = '';

    if (!email || !validateEmail(email)) { 
        setFieldError(emailField, t('public.js.newsletter_invalid_email')); 
        isValid = false;
    }
    if (!password) {
        setFieldError(passwordField, t('public.account.password_label')); // Or a more specific "Password required"
        isValid = false;
    }
    if (!isValid) {
        showGlobalMessage(t('global.error_generic'), "error"); 
        return;
    }

    showGlobalMessage(t('public.js.logging_in'), "info", 60000); 

    try {
        const result = await makeApiRequest('/auth/login', 'POST', { email, password });
        if (result.success && result.user && result.token) {
            setCurrentUser(result.user, result.token);
            showGlobalMessage(result.message || t('public.js.login_success'), "success");
            loginForm.reset();
            const urlParams = new URLSearchParams(window.location.search);
            const redirectUrl = urlParams.get('redirect');
            if (redirectUrl) {
                window.location.href = redirectUrl;
            }
        } else {
            setCurrentUser(null); 
            const generalErrorMessage = result.message || t('public.js.login_failed');
            showGlobalMessage(generalErrorMessage, "error");
            if (loginMessageElement) loginMessageElement.textContent = generalErrorMessage;
            setFieldError(emailField, " "); 
            setFieldError(passwordField, generalErrorMessage);
        }
    } catch (error) {
        setCurrentUser(null); 
        if (loginMessageElement) loginMessageElement.textContent = error.message || t('global.error_generic');
    }
}

async function handleRegistrationForm(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form);
    
    const emailField = form.querySelector('#register-email'); 
    const passwordField = form.querySelector('#register-password');
    const confirmPasswordField = form.querySelector('#register-confirm-password');
    const nomField = form.querySelector('#register-nom');
    const prenomField = form.querySelector('#register-prenom');
    
    let isValid = true;

    if (!emailField.value || !validateEmail(emailField.value)) {
        setFieldError(emailField, t('public.js.newsletter_invalid_email')); isValid = false;
    }
    // Add more specific translated validation messages if needed
    if (!nomField.value.trim()) {
        setFieldError(nomField, "Nom requis."); isValid = false;
    }
    if (!prenomField.value.trim()) {
        setFieldError(prenomField, "Prénom requis."); isValid = false;
    }
    if (passwordField.value.length < 8) {
        setFieldError(passwordField, "Le mot de passe doit faire au moins 8 caractères."); isValid = false;
    }
    if (passwordField.value !== confirmPasswordField.value) {
        setFieldError(confirmPasswordField, "Les mots de passe ne correspondent pas."); isValid = false;
    }

    if (!isValid) {
        showGlobalMessage(t('global.error_generic'), "error");
        return;
    }

    showGlobalMessage(t('public.account.create_account_btn') + "...", "info"); // "Creating account..."
    try {
        const result = await makeApiRequest('/auth/register', 'POST', {
            email: emailField.value,
            password: passwordField.value,
            nom: nomField.value,
            prenom: prenomField.value
        });
        if (result.success) {
            showGlobalMessage(result.message || t('public.js.login_success'), "success"); // Or a specific registration success message
            form.reset();
        } else {
            showGlobalMessage(result.message || t('global.error_generic'), "error");
        }
    } catch (error) {
        console.error("Registration error:", error);
    }
}

function displayAccountDashboard() {
    const loginRegisterSection = document.getElementById('login-register-section');
    const accountDashboardSection = document.getElementById('account-dashboard-section');
    const currentUser = getCurrentUser();

    if (currentUser && loginRegisterSection && accountDashboardSection) {
        loginRegisterSection.style.display = 'none';
        accountDashboardSection.style.display = 'block';
        
        const dashboardUsername = document.getElementById('dashboard-username');
        const dashboardEmail = document.getElementById('dashboard-email');
        if(dashboardUsername) dashboardUsername.textContent = `${currentUser.prenom || ''} ${currentUser.nom || ''}`;
        if(dashboardEmail) dashboardEmail.textContent = currentUser.email;
        
        const logoutButton = document.getElementById('logout-button');
        if (logoutButton) {
            logoutButton.removeEventListener('click', logoutUser); 
            logoutButton.addEventListener('click', logoutUser);
        }
        loadOrderHistory(); 
    } else if (loginRegisterSection) {
        loginRegisterSection.style.display = 'block';
        if (accountDashboardSection) accountDashboardSection.style.display = 'none';
    }
}

async function loadOrderHistory() {
    const orderHistoryContainer = document.getElementById('order-history-container');
    if (!orderHistoryContainer) return;

    const currentUser = getCurrentUser();
    if (!currentUser) {
        orderHistoryContainer.innerHTML = `<p class="text-sm text-brand-warm-taupe italic">${t('public.cart.login_prompt')}</p>`; // "Please log in to see your history."
        return;
    }

    orderHistoryContainer.innerHTML = `<p class="text-sm text-brand-warm-taupe italic">${t('global.loading')}</p>`;
    try {
        await new Promise(resolve => setTimeout(resolve, 500)); 
        const ordersData = { success: true, orders: [] }; 

        if (ordersData.success && ordersData.orders.length > 0) {
            let html = '<ul class="space-y-4">';
            ordersData.orders.forEach(order => {
                html += `
                    <li class="p-4 border border-brand-warm-taupe/50 rounded-md bg-white">
                        <div class="flex justify-between items-center mb-2">
                            <p class="font-semibold text-brand-near-black">${t('public.confirmation.order_number_label')} #${order.orderId || order.id}</p>
                            <span class="px-2 py-1 text-xs font-semibold rounded-full ${getOrderStatusClass(order.status)}">${order.status}</span>
                        </div>
                        <p class="text-sm"><strong>Date:</strong> ${new Date(order.date || order.order_date).toLocaleDateString(currentLang)}</p>
                        <p class="text-sm"><strong>${t('public.cart.total')}</strong> ${parseFloat(order.totalAmount || order.total_amount).toFixed(2)} €</p>
                        <button class="text-sm text-brand-classic-gold hover:underline mt-2" onclick="viewOrderDetail('${order.orderId || order.id}')">${t('public.confirmation.view_account_btn')}</button> </li>
                `;
            });
            html += '</ul>';
            orderHistoryContainer.innerHTML = html;
        } else {
            orderHistoryContainer.innerHTML = `<p class="text-sm text-brand-warm-taupe italic">${t('public.account.dashboard_orders_placeholder')}</p>`;
        }
    } catch (error) {
        orderHistoryContainer.innerHTML = `<p class="text-sm text-brand-truffle-burgundy italic">${t('global.error_generic')}: ${error.message}</p>`;
    }
}

function viewOrderDetail(orderId) {
    showGlobalMessage(`${t('public.confirmation.order_number_label')} #${orderId} (${t('global.loading')}).`, 'info'); // "Order Detail #... (feature to implement)"
}

function isUserLoggedIn() {
    return !!getCurrentUser();
}
