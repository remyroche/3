// website/js/auth.js
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
    updateCartDisplay(); 
    document.dispatchEvent(new CustomEvent('authStateChanged', { detail: { isLoggedIn: !!userData } }));
}

async function logoutUser() {
    setCurrentUser(null); 
    showGlobalMessage(t('public.js.logged_out'), "info"); // Key: public.js.logged_out

    const bodyId = document.body.id;
    const protectedPages = ['page-compte', 'page-paiement', 'page-professionnels', 'page-invoices-pro']; // Added page-professionnels and page-invoices-pro
    if (protectedPages.includes(bodyId)) {
        window.location.href = 'compte.html'; // Default to account/login page
    }
}

function updateLoginState() {
    const currentUser = getCurrentUser();
    const accountLinkDesktop = document.querySelector('header nav a[href="compte.html"]');
    const accountLinkMobile = document.querySelector('#mobile-menu-dropdown a[href="compte.html"]');
    const cartIconDesktop = document.querySelector('header a[href="panier.html"]');
    const cartIconMobile = document.querySelector('.md\\:hidden a[href="panier.html"]'); // Corrected selector for mobile cart icon

    if (currentUser) {
        if (accountLinkDesktop) {
            // XSS: currentUser.prenom is dynamic. Use textContent for the name part.
            // Assuming the SVG part is static and safe.
            const svgIconHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-7 h-7 text-brand-classic-gold"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>`;
            const nameSpan = document.createElement('span');
            nameSpan.className = 'ml-1 text-xs';
            nameSpan.textContent = currentUser.prenom || t('public.nav.account');
            accountLinkDesktop.innerHTML = svgIconHTML; // Set SVG first
            accountLinkDesktop.appendChild(nameSpan); // Append textContent-based span
        }
        if (accountLinkMobile) accountLinkMobile.textContent = `${t('public.nav.account')} (${currentUser.prenom || ''})`; // XSS: currentUser.prenom via textContent
    } else {
        if (accountLinkDesktop) accountLinkDesktop.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-7 h-7"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>`; // Static SVG
        if (accountLinkMobile) accountLinkMobile.textContent = t('public.nav.account'); // Translated string
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
    if (loginMessageElement) loginMessageElement.textContent = ''; // XSS: Clearing content, safe

    if (!email || !validateEmail(email)) { 
        setFieldError(emailField, t('public.js.newsletter_invalid_email')); 
        isValid = false;
    }
    if (!password) {
        setFieldError(passwordField, t('public.js.password_required')); 
        isValid = false;
    }
    if (!isValid) {
        showGlobalMessage(t('public.js.fix_form_errors'), "error"); 
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
                const allowedOrigins = [window.location.origin]; 
                let isValidRedirect = false;
                try {
                    const parsedRedirectUrl = new URL(redirectUrl, window.location.origin); 
                    if (allowedOrigins.includes(parsedRedirectUrl.origin) || redirectUrl.startsWith('/')) {
                        isValidRedirect = true;
                    }
                } catch (e) {
                    console.warn("Invalid redirect URL format:", redirectUrl);
                }

                if (isValidRedirect) {
                    window.location.href = redirectUrl;
                } else {
                    console.warn("Blocked potentially unsafe redirect to:", redirectUrl);
                    window.location.href = 'compte.html'; 
                }
            } else {
                 window.location.href = 'compte.html'; 
            }
        } else {
            setCurrentUser(null); 
            const generalErrorMessage = result.message || t('public.js.login_failed');
            showGlobalMessage(generalErrorMessage, "error");
            if (loginMessageElement) loginMessageElement.textContent = generalErrorMessage; // XSS: Error message, assumed safe
            if (emailField) setFieldError(emailField, " "); 
            if (passwordField) setFieldError(passwordField, generalErrorMessage);
        }
    } catch (error) {
        setCurrentUser(null); 
        const errorMessage = error.data?.message || t('global.error_generic');
        if (loginMessageElement) loginMessageElement.textContent = errorMessage; // XSS: Error message, assumed safe
        showGlobalMessage(errorMessage, "error");
    }
}

function validatePasswordComplexity(password) {
    if (password.length < 8) {
        return "public.js.auth.password_min_chars"; 
    }
    if (!/[A-Z]/.test(password)) {
        return "public.js.auth.password_uppercase"; 
    }
    if (!/[a-z]/.test(password)) {
        return "public.js.auth.password_lowercase"; 
    }
    if (!/[0-9]/.test(password)) {
        return "public.js.auth.password_digit";    
    }
    return null; // Password is valid
}

async function handleRegistrationForm(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form); 
    
    const emailField = form.querySelector('#register-email');
    const passwordField = form.querySelector('#register-password');
    const confirmPasswordField = form.querySelector('#register-confirm-password');
    const nomField = form.querySelector('#register-nom'); // Assuming ID for last name
    const prenomField = form.querySelector('#register-prenom'); // Assuming ID for first name
    const roleSelectField = form.querySelector('#register-role'); // Assuming ID for role select
    const companyNameField = form.querySelector('#register-company-name'); // Assuming ID
    const siretNumberField = form.querySelector('#register-siret'); // Assuming ID
    const vatNumberField = form.querySelector('#register-vat'); // Assuming ID
    const registrationMessageElement = document.getElementById('registration-message'); // Assuming this ID exists in your HTML

    let isValid = true;

    if (!emailField || !emailField.value || !validateEmail(emailField.value)) { 
        setFieldError(emailField, t('public.js.newsletter_invalid_email')); 
        isValid = false;
    }
    if (!nomField || !nomField.value.trim()) {
        setFieldError(nomField, t('public.js.lastname_required')); 
        isValid = false;
    }
    if (!prenomField || !prenomField.value.trim()) {
        setFieldError(prenomField, t('public.js.firstname_required')); 
        isValid = false;
    }

    if (passwordField) {
        const passwordComplexityKey = validatePasswordComplexity(passwordField.value);
        if (passwordComplexityKey) {
            setFieldError(passwordField, t(passwordComplexityKey)); 
            isValid = false;
        } else if (confirmPasswordField && passwordField.value !== confirmPasswordField.value) {
            setFieldError(confirmPasswordField, t('public.js.passwords_do_not_match'));
            isValid = false;
        }
    } else {
         isValid = false; 
    }

    const role = roleSelectField ? roleSelectField.value : 'b2c_customer';
    let registrationData = {
        email: emailField ? emailField.value : '',
        password: passwordField ? passwordField.value : '',
        first_name: prenomField ? prenomField.value : '',
        last_name: nomField ? nomField.value : '',
        role: role
    };

    if (role === 'b2b_professional') {
        if (!companyNameField || !companyNameField.value.trim()) {
            setFieldError(companyNameField, "Le nom de l'entreprise est requis pour les comptes B2B."); // This message should be a key for t()
            isValid = false;
        }
        if (!siretNumberField || !siretNumberField.value.trim()) {
            setFieldError(siretNumberField, "Le numéro SIRET est requis pour les comptes B2B."); // This message should be a key for t()
            isValid = false;
        }
        registrationData.company_name = companyNameField ? companyNameField.value : '';
        registrationData.siret_number = siretNumberField ? siretNumberField.value : '';
        registrationData.vat_number = vatNumberField ? vatNumberField.value : '';
    }

    if (!isValid) {
        const errorMessage = t('public.js.fix_form_errors');
        if (registrationMessageElement) registrationMessageElement.textContent = errorMessage; // XSS: Error message assumed safe
        else showGlobalMessage(errorMessage, "error");
        return;
    }

    showGlobalMessage(t('public.js.creating_account'), "info"); 

    try {
        const result = await makeApiRequest('/auth/register', 'POST', registrationData);
        
        if (result.success) {
            const successMessage = result.message || t('public.js.registration_success');
            showGlobalMessage(successMessage, "success");
            form.reset();
            if (registrationMessageElement) registrationMessageElement.textContent = successMessage; // XSS: Success message assumed safe
        } else {
            const errorMessage = result.message || t('global.error_generic');
            if (registrationMessageElement) {
                registrationMessageElement.textContent = errorMessage; // XSS: Error message assumed safe
            } else {
                showGlobalMessage(errorMessage, "error");
            }
            if (result.message && result.message.toLowerCase().includes('password') && passwordField) {
                setFieldError(passwordField, result.message);
            }
        }
    } catch (error) {
        console.error("Registration error:", error);
        const errorMessage = error.data?.message || t('global.error_generic');
        if (registrationMessageElement) {
            registrationMessageElement.textContent = errorMessage; // XSS: Error message assumed safe
        } else {
            showGlobalMessage(errorMessage, "error");
        }
        if (error.data?.message && error.data.message.toLowerCase().includes('password') && passwordField) {
            setFieldError(passwordField, error.data.message);
        }
    }
}


function displayAccountDashboard() {
    const loginRegisterSection = document.getElementById('login-register-section');
    const accountDashboardSection = document.getElementById('account-dashboard-section');
    const currentUser = getCurrentUser();

    if (loginRegisterSection && accountDashboardSection) { 
        if (currentUser) {
            loginRegisterSection.style.display = 'none';
            accountDashboardSection.style.display = 'block';
            
            const dashboardUsername = document.getElementById('dashboard-username');
            const dashboardEmail = document.getElementById('dashboard-email');
            if(dashboardUsername) dashboardUsername.textContent = `${currentUser.prenom || ''} ${currentUser.nom || ''}`.trim() || t('public.account.dashboard_greeting_fallback'); // XSS: Names set with textContent
            if(dashboardEmail) dashboardEmail.textContent = currentUser.email; // XSS: Email set with textContent
            
            const logoutButton = document.getElementById('logout-button');
            if (logoutButton) {
                logoutButton.removeEventListener('click', logoutUser); 
                logoutButton.addEventListener('click', logoutUser);
            }
            loadOrderHistory(); 
        } else {
            loginRegisterSection.style.display = 'block';
            accountDashboardSection.style.display = 'none';
        }
    } else {
        console.warn("Account page sections not found for dashboard display logic.");
    }
}

async function loadOrderHistory() {
    const orderHistoryContainer = document.getElementById('order-history-container');
    if (!orderHistoryContainer) return;

    const currentUser = getCurrentUser();
    if (!currentUser) {
        const p = document.createElement('p');
        p.className = 'text-sm text-brand-warm-taupe italic';
        p.textContent = t('public.cart.login_prompt'); // XSS: Translated string
        orderHistoryContainer.innerHTML = ''; // Clear
        orderHistoryContainer.appendChild(p);
        return;
    }

    const pLoading = document.createElement('p');
    pLoading.className = 'text-sm text-brand-warm-taupe italic';
    pLoading.textContent = t('global.loading'); // XSS: Translated string
    orderHistoryContainer.innerHTML = ''; // Clear
    orderHistoryContainer.appendChild(pLoading);
    
    try {
        await new Promise(resolve => setTimeout(resolve, 500)); 
        const ordersData = { success: true, orders: [] }; // Dummy empty response

        if (ordersData.success && ordersData.orders.length > 0) {
            orderHistoryContainer.innerHTML = ''; // Clear loading
            const ul = document.createElement('ul');
            ul.className = 'space-y-4';
            ordersData.orders.forEach(order => {
                const li = document.createElement('li');
                li.className = 'p-4 border border-brand-warm-taupe/50 rounded-md bg-white';

                const divFlex = document.createElement('div');
                divFlex.className = 'flex justify-between items-center mb-2';
                
                const pOrderId = document.createElement('p');
                pOrderId.className = 'font-semibold text-brand-near-black';
                pOrderId.textContent = `${t('public.confirmation.order_number_label')} #${order.orderId || order.id}`; // XSS
                divFlex.appendChild(pOrderId);

                const spanStatus = document.createElement('span');
                spanStatus.className = `px-2 py-1 text-xs font-semibold rounded-full ${getOrderStatusClass(order.status)}`;
                spanStatus.textContent = order.status; // XSS: Status text
                divFlex.appendChild(spanStatus);
                li.appendChild(divFlex);

                const pDate = document.createElement('p');
                pDate.className = 'text-sm';
                const strongDate = document.createElement('strong');
                strongDate.textContent = t('public.js.order_date_label'); // XSS
                pDate.appendChild(strongDate);
                pDate.append(` ${new Date(order.date || order.order_date).toLocaleDateString(currentLang)}`); // XSS
                li.appendChild(pDate);
                
                const pTotal = document.createElement('p');
                pTotal.className = 'text-sm';
                const strongTotal = document.createElement('strong');
                strongTotal.textContent = t('public.cart.total'); // XSS
                pTotal.appendChild(strongTotal);
                pTotal.append(` ${parseFloat(order.totalAmount || order.total_amount).toFixed(2)} €`); // XSS
                li.appendChild(pTotal);

                const viewButton = document.createElement('button');
                viewButton.className = 'text-sm text-brand-classic-gold hover:underline mt-2';
                viewButton.textContent = t('public.confirmation.view_account_btn'); // XSS
                viewButton.onclick = () => viewOrderDetail(order.orderId || order.id);
                li.appendChild(viewButton);
                
                ul.appendChild(li);
            });
            orderHistoryContainer.appendChild(ul);
        } else {
            const pNoOrders = document.createElement('p');
            pNoOrders.className = 'text-sm text-brand-warm-taupe italic';
            pNoOrders.textContent = t('public.account.dashboard_orders_placeholder'); // XSS
            orderHistoryContainer.innerHTML = '';
            orderHistoryContainer.appendChild(pNoOrders);
        }
    } catch (error) {
        const pError = document.createElement('p');
        pError.className = 'text-sm text-brand-truffle-burgundy italic';
        pError.textContent = `${t('global.error_generic')}: ${error.message || error.data?.message}`; // XSS
        orderHistoryContainer.innerHTML = '';
        orderHistoryContainer.appendChild(pError);
    }
}

function viewOrderDetail(orderId) {
    showGlobalMessage(`${t('public.js.view_order_detail_prefix')} #${orderId}. ${t('public.js.feature_to_implement_suffix')}`, 'info');
}

function isUserLoggedIn() {
    return !!getCurrentUser();
}
