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
 * Sets or removes the authentication token in session storage.
 * @param {string|null} token - The token to set, or null to remove.
 */
function setAuthToken(token) {
    if (token) {
        sessionStorage.setItem('authToken', token);
    } else {
        sessionStorage.removeItem('authToken');
    }
}

/**
 * Retrieves the current user data from session storage.
 * @returns {object|null} The user object or null if not found/invalid.
 */
function getCurrentUser() {
    const userString = sessionStorage.getItem('currentUser');
    if (userString) {
        try {
            return JSON.parse(userString);
        } catch (e) {
            console.error("Erreur lors du parsing des données utilisateur:", e);
            sessionStorage.removeItem('currentUser');
            sessionStorage.removeItem('authToken'); // Also clear token if user data is corrupt
            return null;
        }
    }
    return null;
}

/**
 * Sets the current user data in session storage and updates login state.
 * @param {object|null} userData - The user data object, or null to clear.
 * @param {string|null} [token=null] - The auth token, if setting a new user.
 */
function setCurrentUser(userData, token = null) {
    if (userData) {
        sessionStorage.setItem('currentUser', JSON.stringify(userData));
        if (token) setAuthToken(token);
    } else {
        sessionStorage.removeItem('currentUser');
        sessionStorage.removeItem('authToken');
    }
    updateLoginState();
    updateCartCountDisplay(); // Cart display might depend on login state (e.g. merging carts)
}

/**
 * Logs out the current user.
 * Clears user data and token from session storage, updates UI.
 */
async function logoutUser() {
    const currentUser = getCurrentUser();
    // if (currentUser) {
        // Optional: Call a backend logout endpoint if it exists and is necessary
        // await makeApiRequest('/auth/logout', 'POST', null, true);
    // }
    setCurrentUser(null); // This will clear session storage and update UI
    showGlobalMessage("Vous avez été déconnecté.", "info");

    // Redirect if on account or payment page, otherwise just update state
    if (document.body.id === 'page-compte' || document.body.id === 'page-paiement') {
        window.location.href = 'compte.html';
    } else {
        updateLoginState(); // Redundant if setCurrentUser calls it, but safe.
        if (document.body.id === 'page-compte') displayAccountDashboard(); // Refresh account page view
    }
}

/**
 * Updates the UI elements (account links) based on the current login state.
 */
function updateLoginState() {
    const currentUser = getCurrentUser();
    const accountLinkDesktop = document.querySelector('header nav a[href="compte.html"]');
    const accountLinkMobile = document.querySelector('#mobile-menu-dropdown a[href="compte.html"]');
    const cartIconDesktop = document.querySelector('header a[href="panier.html"]');
    const cartIconMobile = document.querySelector('.md\\:hidden a[href="panier.html"]');

    if (currentUser) {
        if (accountLinkDesktop) accountLinkDesktop.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-7 h-7 text-brand-classic-gold"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg> <span class="ml-1 text-xs">${currentUser.prenom || 'Compte'}</span>`;
        if (accountLinkMobile) accountLinkMobile.textContent = `Mon Compte (${currentUser.prenom || ''})`;
    } else {
        if (accountLinkDesktop) accountLinkDesktop.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-7 h-7"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>`;
        if (accountLinkMobile) accountLinkMobile.textContent = 'Mon Compte';
    }
    // Ensure cart icons are always visible (count will be updated by updateCartCountDisplay)
    if(cartIconDesktop) cartIconDesktop.style.display = 'inline-flex';
    if(cartIconMobile) cartIconMobile.style.display = 'inline-flex';
}

/**
 * Handles the login form submission.
 * @param {Event} event - The form submission event.
 */
async function handleLogin(event) {
    event.preventDefault();
    const loginForm = event.target;
    clearFormErrors(loginForm); // Assumes clearFormErrors is in ui.js
    const emailField = loginForm.querySelector('#login-email');
    const passwordField = loginForm.querySelector('#login-password');
    const email = emailField.value;
    const password = passwordField.value;
    const loginMessageElement = document.getElementById('login-message');

    let isValid = true;
    if (loginMessageElement) loginMessageElement.textContent = '';

    if (!email || !validateEmail(email)) { // Assumes validateEmail is in ui.js
        setFieldError(emailField, "Veuillez entrer une adresse e-mail valide."); // Assumes setFieldError is in ui.js
        isValid = false;
    }
    if (!password) {
        setFieldError(passwordField, "Veuillez entrer votre mot de passe.");
        isValid = false;
    }
    if (!isValid) {
        showGlobalMessage("Veuillez corriger les erreurs dans le formulaire.", "error"); // Assumes showGlobalMessage is in ui.js
        return;
    }

    showGlobalMessage("Connexion en cours...", "info", 60000); // Long timeout for login process

    try {
        // Assumes makeApiRequest is in api.js and API_BASE_URL is in config.js
        const result = await makeApiRequest('/auth/login', 'POST', { email, password });
        if (result.success && result.user && result.token) {
            setCurrentUser(result.user, result.token);
            showGlobalMessage(result.message || "Connexion réussie!", "success");
            loginForm.reset();
            displayAccountDashboard(); // Display the dashboard view
        } else {
            setCurrentUser(null); // Clear any partial login state
            const generalErrorMessage = result.message || "Échec de la connexion. Vérifiez vos identifiants.";
            showGlobalMessage(generalErrorMessage, "error");
            if (loginMessageElement) loginMessageElement.textContent = generalErrorMessage;
            setFieldError(emailField, " "); // Mark fields as potentially incorrect (empty message or specific)
            setFieldError(passwordField, generalErrorMessage);
        }
    } catch (error) {
        setCurrentUser(null); // Clear any partial login state on error
        // Error message is already shown by makeApiRequest's catch block
        if (loginMessageElement) loginMessageElement.textContent = error.message || "Erreur de connexion au serveur.";
    }
}

/**
 * Handles the registration form submission.
 * Note: This is a placeholder as the actual registration form HTML is missing.
 * @param {Event} event - The form submission event.
 */
async function handleRegistrationForm(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form);
    
    const emailField = form.querySelector('#register-email'); // Assuming IDs like #register-email
    const passwordField = form.querySelector('#register-password');
    const confirmPasswordField = form.querySelector('#register-confirm-password');
    const nomField = form.querySelector('#register-nom');
    const prenomField = form.querySelector('#register-prenom');
    
    let isValid = true;

    if (!emailField.value || !validateEmail(emailField.value)) {
        setFieldError(emailField, "E-mail invalide."); isValid = false;
    }
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
        showGlobalMessage("Veuillez corriger les erreurs du formulaire d'inscription.", "error");
        return;
    }

    showGlobalMessage("Création du compte...", "info");
    try {
        const result = await makeApiRequest('/auth/register', 'POST', {
            email: emailField.value,
            password: passwordField.value,
            nom: nomField.value,
            prenom: prenomField.value
        });
        if (result.success) {
            showGlobalMessage(result.message || "Compte créé avec succès ! Veuillez vous connecter.", "success");
            form.reset();
            // Potentially switch to login form/tab or redirect to login page
        } else {
            showGlobalMessage(result.message || "Erreur lors de l'inscription.", "error");
        }
    } catch (error) {
        // Error message shown by makeApiRequest
        console.error("Erreur d'inscription:", error);
    }
}

/**
 * Displays the account dashboard if the user is logged in,
 * otherwise shows the login/register section.
 */
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
            logoutButton.removeEventListener('click', logoutUser); // Avoid multiple listeners
            logoutButton.addEventListener('click', logoutUser);
        }
        loadOrderHistory(); // Load order history when dashboard is displayed
    } else if (loginRegisterSection) {
        loginRegisterSection.style.display = 'block';
        if (accountDashboardSection) accountDashboardSection.style.display = 'none';
    }
}

/**
 * Loads and displays the user's order history.
 */
async function loadOrderHistory() {
    const orderHistoryContainer = document.getElementById('order-history-container');
    if (!orderHistoryContainer) return;

    const currentUser = getCurrentUser();
    if (!currentUser) {
        orderHistoryContainer.innerHTML = '<p class="text-sm text-brand-warm-taupe italic">Veuillez vous connecter pour voir votre historique.</p>';
        return;
    }

    orderHistoryContainer.innerHTML = '<p class="text-sm text-brand-warm-taupe italic">Chargement de l\'historique des commandes...</p>';
    try {
        // TODO: Replace with actual API call when endpoint is available
        // const ordersData = await makeApiRequest('/orders/history', 'GET', null, true);
        
        // Mockup for now, as /api/orders/history is not implemented in backend
        await new Promise(resolve => setTimeout(resolve, 500)); // Simulate network delay
        const ordersData = { success: true, orders: [] }; // Mockup: empty orders

        if (ordersData.success && ordersData.orders.length > 0) {
            let html = '<ul class="space-y-4">';
            ordersData.orders.forEach(order => {
                html += `
                    <li class="p-4 border border-brand-warm-taupe/50 rounded-md bg-white">
                        <div class="flex justify-between items-center mb-2">
                            <p class="font-semibold text-brand-near-black">Commande #${order.orderId || order.id}</p>
                            <span class="px-2 py-1 text-xs font-semibold rounded-full ${getOrderStatusClass(order.status)}">${order.status}</span>
                        </div>
                        <p class="text-sm"><strong>Date:</strong> ${new Date(order.date || order.order_date).toLocaleDateString('fr-FR')}</p>
                        <p class="text-sm"><strong>Total:</strong> ${parseFloat(order.totalAmount || order.total_amount).toFixed(2)} €</p>
                        <button class="text-sm text-brand-classic-gold hover:underline mt-2" onclick="viewOrderDetail('${order.orderId || order.id}')">Voir détails</button>
                    </li>
                `;
            });
            html += '</ul>';
            orderHistoryContainer.innerHTML = html;
        } else {
            orderHistoryContainer.innerHTML = '<p class="text-sm text-brand-warm-taupe italic">Vous n\'avez aucune commande pour le moment.</p>';
        }
    } catch (error) {
        orderHistoryContainer.innerHTML = `<p class="text-sm text-brand-truffle-burgundy italic">Impossible de charger l'historique des commandes: ${error.message}</p>`;
    }
}

/**
 * Placeholder function to view order details.
 * This would typically open a modal or navigate to an order detail page.
 * @param {string} orderId - The ID of the order to view.
 */
function viewOrderDetail(orderId) {
    // Implementation for viewing order details (e.g., open a modal, redirect)
    showGlobalMessage(`Détail de la commande #${orderId} (fonctionnalité à implémenter).`, 'info');
    console.log("Voir détails pour commande:", orderId);
}
