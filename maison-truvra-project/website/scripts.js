// Updated content for remyroche/maison-truvra-project/remyroche-maison-truvra-project-2a648141e4e38704789c3d54982835db943283aa/website/scripts.js
// --- Configuration ---
const API_BASE_URL = 'http://127.0.0.1:5001/api'; // URL de votre backend

// --- Helper Functions ---
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

async function makeApiRequest(endpoint, method = 'GET', body = null, requiresAuth = false) {
    const headers = { 'Content-Type': 'application/json' };
    if (requiresAuth) {
        const token = getAuthToken();
        if (!token) {
            showGlobalMessage("Vous n'êtes pas authentifié.", "error");
            throw new Error("Authentification requise.");
        }
        headers['Authorization'] = `Bearer ${token}`;
    }

    const config = {
        method: method,
        headers: headers,
    };

    if (body) {
        config.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
        if (!response.ok) {
            const errorResult = await response.json().catch(() => ({ message: "Erreur de communication avec le serveur." }));
            throw new Error(errorResult.message || `Erreur HTTP: ${response.status}`);
        }
        if (response.status === 204) {
            return { success: true, message: "Opération réussie (pas de contenu)." };
        }
        return await response.json();
    } catch (error) {
        console.error(`Erreur API pour ${method} ${endpoint}:`, error);
        showGlobalMessage(error.message || "Une erreur réseau est survenue.", "error");
        throw error; 
    }
}


// --- Mobile Menu ---
function initializeMobileMenu() {
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenuDropdown = document.getElementById('mobile-menu-dropdown');
    if (mobileMenuButton && mobileMenuDropdown) {
        mobileMenuButton.addEventListener('click', () => {
            mobileMenuDropdown.classList.toggle('hidden');
        });
    }
}

function closeMobileMenu() {
    const mobileMenuDropdown = document.getElementById('mobile-menu-dropdown');
    if (mobileMenuDropdown && !mobileMenuDropdown.classList.contains('hidden')) {
        mobileMenuDropdown.classList.add('hidden');
    }
}

// --- User Authentication & State ---
function getCurrentUser() {
    const userString = sessionStorage.getItem('currentUser');
    if (userString) {
        try {
            return JSON.parse(userString);
        } catch (e) {
            console.error("Erreur lors du parsing des données utilisateur:", e);
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
    updateCartCountDisplay(); 
}

function logoutUser() {
    const currentUser = getCurrentUser();
    if (currentUser) {
        // await makeApiRequest('/auth/logout', 'POST', null, true); // If backend endpoint exists
    }
    setCurrentUser(null);
    showGlobalMessage("Vous avez été déconnecté.", "info");
    if (document.body.id === 'page-compte' || document.body.id === 'page-paiement') { 
        window.location.href = 'compte.html'; 
    } else {
        updateLoginState(); 
        if (document.body.id === 'page-compte') displayAccountDashboard();
    }
}

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
    if(cartIconDesktop) cartIconDesktop.style.display = 'inline-flex';
    if(cartIconMobile) cartIconMobile.style.display = 'inline-flex';
}

async function handleLogin(event) {
    event.preventDefault();
    const loginForm = event.target;
    clearFormErrors(loginForm); // Clear previous errors
    const emailField = loginForm.querySelector('#login-email');
    const passwordField = loginForm.querySelector('#login-password');
    const email = emailField.value;
    const password = passwordField.value;
    const loginMessageElement = document.getElementById('login-message');

    let isValid = true;
    if (loginMessageElement) loginMessageElement.textContent = '';

    if (!email || !validateEmail(email)) {
        setFieldError(emailField, "Veuillez entrer une adresse e-mail valide.");
        isValid = false;
    }
    if (!password) {
        setFieldError(passwordField, "Veuillez entrer votre mot de passe.");
        isValid = false;
    }
    if (!isValid) {
        showGlobalMessage("Veuillez corriger les erreurs dans le formulaire.", "error");
        return;
    }

    showGlobalMessage("Connexion en cours...", "info", 60000); 

    try {
        const result = await makeApiRequest('/auth/login', 'POST', { email, password });
        if (result.success && result.user && result.token) {
            setCurrentUser(result.user, result.token);
            showGlobalMessage(result.message, "success");
            loginForm.reset();
            displayAccountDashboard();
        } else {
            setCurrentUser(null);
            const generalErrorMessage = result.message || "Échec de la connexion. Vérifiez vos identifiants.";
            showGlobalMessage(generalErrorMessage, "error");
            if (loginMessageElement) loginMessageElement.textContent = generalErrorMessage;
            setFieldError(emailField, " "); // Mark fields as potentially incorrect
            setFieldError(passwordField, generalErrorMessage); 
        }
    } catch (error) {
        setCurrentUser(null);
        if (loginMessageElement) loginMessageElement.textContent = error.message || "Erreur de connexion au serveur.";
    }
}

// Placeholder for a more complete registration form handler
async function handleRegistrationForm(event) { // Assumes a dedicated registration form
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
            // Potentially switch to login form/tab
        } else {
            showGlobalMessage(result.message || "Erreur lors de l'inscription.", "error");
        }
    } catch (error) {
        // Error message shown by makeApiRequest
    }
}


function displayAccountDashboard() {
    const loginRegisterSection = document.getElementById('login-register-section');
    const accountDashboardSection = document.getElementById('account-dashboard-section');
    const currentUser = getCurrentUser();

    if (currentUser && loginRegisterSection && accountDashboardSection) {
        loginRegisterSection.style.display = 'none';
        accountDashboardSection.style.display = 'block';
        document.getElementById('dashboard-username').textContent = `${currentUser.prenom || ''} ${currentUser.nom || ''}`;
        document.getElementById('dashboard-email').textContent = currentUser.email;
        const logoutButton = document.getElementById('logout-button');
        if (logoutButton) {
            logoutButton.removeEventListener('click', logoutUser); // Avoid multiple listeners
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
        orderHistoryContainer.innerHTML = '<p class="text-sm text-brand-warm-taupe italic">Veuillez vous connecter pour voir votre historique.</p>';
        return;
    }

    orderHistoryContainer.innerHTML = '<p class="text-sm text-brand-warm-taupe italic">Chargement de l\'historique des commandes...</p>';
    try {
        // const orders = await makeApiRequest('/orders/history', 'GET', null, true); // Backend endpoint needed
        await new Promise(resolve => setTimeout(resolve, 500)); // Simulate network delay
        const orders = { success: true, orders: [] }; // Mockup
        
        if (orders.success && orders.orders.length > 0) {
            let html = '<ul class="space-y-4">';
            orders.orders.forEach(order => {
                html += `
                    <li class="p-4 border border-brand-warm-taupe/50 rounded-md bg-white">
                        <div class="flex justify-between items-center mb-2">
                            <p class="font-semibold text-brand-near-black">Commande #${order.orderId || order.id}</p>
                            <span class="px-2 py-1 text-xs font-semibold rounded-full ${getOrderStatusClass(order.status)}">${order.status}</span>
                        </div>
                        <p class="text-sm"><strong>Date:</strong> ${new Date(order.date).toLocaleDateString('fr-FR')}</p>
                        <p class="text-sm"><strong>Total:</strong> ${parseFloat(order.totalAmount).toFixed(2)} €</p>
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

function getOrderStatusClass(status) { // Also used in admin_scripts.js, could be shared
    switch (status) {
        case 'Paid': return 'bg-green-100 text-green-800';
        case 'Shipped': return 'bg-blue-100 text-blue-800';
        case 'Delivered': return 'bg-purple-100 text-purple-800';
        case 'Pending': return 'bg-yellow-100 text-yellow-800';
        case 'Cancelled': return 'bg-red-100 text-red-800';
        default: return 'bg-gray-100 text-gray-800';
    }
}


// --- Newsletter Form Logic ---
function initializeNewsletterForm() {
    const newsletterForm = document.getElementById('newsletter-form');
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', async function (event) {
            event.preventDefault();
            const newsletterEmailInput = document.getElementById('email-newsletter');
            clearFormErrors(newsletterForm); // Clear previous errors

            const email = newsletterEmailInput.value;

            if (!email || !validateEmail(email)) {
                setFieldError(newsletterEmailInput, "Veuillez entrer une adresse e-mail valide.");
                showGlobalMessage("Veuillez entrer une adresse e-mail valide.", "error");
                return;
            }
            showGlobalMessage("Enregistrement en cours...", "info");
            try {
                // Assuming backend expects { email: "...", consentement: "Y" }
                const result = await makeApiRequest('/subscribe-newsletter', 'POST', { email: email, consentement: 'Y' }); 
                if (result.success) {
                    showGlobalMessage(result.message || "Merci ! Votre adresse a été enregistrée.", "success");
                    newsletterEmailInput.value = "";
                } else {
                     setFieldError(newsletterEmailInput, result.message || "Erreur d'inscription.");
                    showGlobalMessage(result.message || "Une erreur s'est produite.", "error");
                }
            } catch (error) {
                 setFieldError(newsletterEmailInput, error.message || "Erreur serveur.");
            }
        });
    }
}

function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
}

// --- Active Navigation Link ---
function setActiveNavLink() {
    const currentPage = window.location.pathname.split("/").pop() || "index.html";
    const navLinks = document.querySelectorAll('header nav .nav-link, #mobile-menu-dropdown .nav-link');
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        const linkPage = link.getAttribute('href').split("/").pop() || "index.html";
        if (linkPage === currentPage) {
            link.classList.add('active');
        }
    });
}

// --- Global Message Function ---
function showGlobalMessage(message, type = 'success', duration = 4000) {
    const toast = document.getElementById('global-message-toast');
    const textElement = document.getElementById('global-message-text');
    if (!toast || !textElement) {
        console.warn("Global message toast elements not found.");
        alert(message); 
        return;
    }

    textElement.textContent = message;
    toast.className = 'modal-message'; 

    if (type === 'error') toast.classList.add('bg-brand-truffle-burgundy', 'text-brand-cream');
    else if (type === 'info') toast.classList.add('bg-brand-slate-blue-grey', 'text-brand-cream');
    else toast.classList.add('bg-brand-deep-sage-green', 'text-brand-cream');
    
    toast.style.display = 'block';
    setTimeout(() => { toast.classList.add('show'); }, 10); 

    if (toast.currentTimeout) clearTimeout(toast.currentTimeout);
    if (toast.hideTimeout) clearTimeout(toast.hideTimeout);

    toast.currentTimeout = setTimeout(() => {
        toast.classList.remove('show');
        toast.hideTimeout = setTimeout(() => { toast.style.display = 'none'; }, 500);
    }, duration);
}

// --- Product Listing (`nos-produits.html`) ---
let allProducts = []; 

async function fetchAndDisplayProducts(category = 'all') {
    const productsGrid = document.getElementById('products-grid');
    const loadingMessageElement = document.getElementById('products-loading-message'); // Renamed for clarity
    if (!productsGrid || !loadingMessageElement) return;

    loadingMessageElement.textContent = "Chargement des produits...";
    loadingMessageElement.style.display = 'block'; // Make sure it's visible
    productsGrid.innerHTML = ''; 

    try {
        const endpoint = category === 'all' ? '/products' : `/products?category=${encodeURIComponent(category)}`;
        const products = await makeApiRequest(endpoint);
        
        if (category === 'all' && products.length > 0) {
            allProducts = products; 
        }

        const productsToDisplay = category === 'all' ? allProducts : products;

        if (productsToDisplay.length === 0) {
            loadingMessageElement.textContent = "Aucun produit trouvé dans cette catégorie.";
             productsGrid.innerHTML = `<p class="col-span-full text-center text-brand-earth-brown py-8">Aucun produit à afficher.</p>`;
        } else {
            loadingMessageElement.style.display = 'none';
            productsToDisplay.forEach(product => {
                const stockMessage = product.stock_quantity > 5 ? 'En stock' : (product.stock_quantity > 0 ? 'Stock limité!' : 'Épuisé');
                const stockClass = product.stock_quantity > 0 ? 'text-brand-deep-sage-green' : 'text-brand-truffle-burgundy';
                const productCard = `
                    <div class="product-card">
                        <a href="produit-detail.html?id=${product.id}">
                            <img src="${product.image_url_main || 'https://placehold.co/400x300/F5EEDE/7D6A4F?text=Image+Indisponible'}" alt="${product.name}" class="w-full h-64 object-cover">
                        </a>
                        <div class="product-card-content">
                            <h3 class="text-xl font-serif font-semibold text-brand-near-black mb-2">${product.name}</h3>
                            <p class="text-brand-earth-brown text-sm mb-3 h-16 overflow-hidden">${product.short_description || ''}</p>
                            <p class="text-lg font-semibold text-brand-truffle-burgundy mb-4">
                                ${product.starting_price !== "N/A" && product.starting_price !== null ? `À partir de ${parseFloat(product.starting_price).toFixed(2)} €` : (product.base_price ? `${parseFloat(product.base_price).toFixed(2)} €` : 'Prix sur demande')}
                            </p>
                             <p class="text-xs ${stockClass} mb-4">${stockMessage}</p>
                        </div>
                        <div class="product-card-footer p-4">
                            <a href="produit-detail.html?id=${product.id}" class="btn-primary block text-center text-sm py-2.5 ${product.stock_quantity <=0 ? 'opacity-50 cursor-not-allowed' : ''}">${product.stock_quantity <= 0 ? 'Épuisé' : 'Voir le produit'}</a>
                        </div>
                    </div>
                `;
                productsGrid.insertAdjacentHTML('beforeend', productCard);
            });
        }
    } catch (error) {
        loadingMessageElement.textContent = "Erreur lors du chargement des produits.";
        productsGrid.innerHTML = `<p class="col-span-full text-center text-brand-truffle-burgundy py-8">Impossible de charger les produits. ${error.message}</p>`;
    }
}

function setupCategoryFilters() {
    const filterContainer = document.getElementById('product-categories-filter');
    if (filterContainer) {
        const buttons = filterContainer.querySelectorAll('button');
        buttons.forEach(button => {
            button.addEventListener('click', () => {
                buttons.forEach(btn => btn.classList.remove('filter-active', 'bg-brand-earth-brown', 'text-brand-cream'));
                button.classList.add('filter-active', 'bg-brand-earth-brown', 'text-brand-cream');
                const category = button.dataset.category;
                fetchAndDisplayProducts(category);
            });
        });
    }
}

// --- Product Detail (`produit-detail.html`) ---
let currentProductDetail = null; 

async function loadProductDetail() {
    const params = new URLSearchParams(window.location.search);
    const productId = params.get('id');
    const loadingDiv = document.getElementById('product-detail-loading');
    const contentDiv = document.getElementById('product-detail-content');

    if (!productId) {
        if(loadingDiv) loadingDiv.textContent = "Aucun produit spécifié.";
        if(contentDiv) contentDiv.style.display = 'none';
        return;
    }
    
    if(loadingDiv) loadingDiv.style.display = 'block';
    if(contentDiv) contentDiv.style.display = 'none';

    try {
        const product = await makeApiRequest(`/products/${productId}`);
        currentProductDetail = product; 

        document.getElementById('product-name').textContent = product.name;
        document.getElementById('main-product-image').src = product.image_url_main || 'https://placehold.co/600x500/F5EEDE/7D6A4F?text=Image';
        document.getElementById('main-product-image').alt = product.name;
        document.getElementById('product-short-description').textContent = product.short_description || '';
        
        const priceDisplay = document.getElementById('product-price-display');
        const priceUnit = document.getElementById('product-price-unit');
        const weightOptionsContainer = document.getElementById('weight-options-container');
        const weightOptionsSelect = document.getElementById('weight-options-select');
        const addToCartButton = document.getElementById('add-to-cart-button');

        if (product.weight_options && product.weight_options.length > 0) {
            weightOptionsContainer.classList.remove('hidden');
            weightOptionsSelect.innerHTML = '';
            product.weight_options.forEach(opt => {
                const optionElement = document.createElement('option');
                optionElement.value = opt.option_id;
                optionElement.textContent = `${opt.weight_grams}g - ${parseFloat(opt.price).toFixed(2)} € ${opt.stock_quantity <= 0 ? '(Épuisé)' : `(Stock: ${opt.stock_quantity})`}`;
                optionElement.dataset.price = opt.price;
                optionElement.dataset.stock = opt.stock_quantity;
                optionElement.dataset.weightGrams = opt.weight_grams; 
                if(opt.stock_quantity <= 0) optionElement.disabled = true;
                weightOptionsSelect.appendChild(optionElement);
            });
            if (weightOptionsSelect.options.length > 0 && !weightOptionsSelect.options[0].disabled) {
                 weightOptionsSelect.selectedIndex = 0; // Select first available option
            } else { // Find first non-disabled if first is disabled
                let firstEnabledIndex = -1;
                for(let i=0; i<weightOptionsSelect.options.length; i++) {
                    if(!weightOptionsSelect.options[i].disabled) {
                        firstEnabledIndex = i;
                        break;
                    }
                }
                if(firstEnabledIndex !== -1) weightOptionsSelect.selectedIndex = firstEnabledIndex;
            }
            updatePriceFromSelection(); 
            weightOptionsSelect.addEventListener('change', updatePriceFromSelection);
        } else if (product.base_price !== null) {
            priceDisplay.textContent = `${parseFloat(product.base_price).toFixed(2)} €`;
            priceUnit.textContent = ''; 
            weightOptionsContainer.classList.add('hidden');
             if (product.stock_quantity <= 0) {
                addToCartButton.textContent = 'Épuisé';
                addToCartButton.disabled = true;
                addToCartButton.classList.replace('btn-gold','btn-secondary');
                addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
            }
        } else {
            priceDisplay.textContent = 'Prix sur demande';
            priceUnit.textContent = '';
            weightOptionsContainer.classList.add('hidden');
            addToCartButton.textContent = 'Indisponible';
            addToCartButton.disabled = true;
            addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
        }

        document.getElementById('product-species').textContent = product.species || 'N/A';
        document.getElementById('product-origin').textContent = product.origin || 'N/A';
        document.getElementById('product-seasonality').textContent = product.seasonality || 'N/A';
        document.getElementById('product-uses').textContent = product.ideal_uses || 'N/A';
        document.getElementById('product-sensory-description').innerHTML = product.long_description || product.sensory_description || 'Aucune description détaillée disponible.';
        document.getElementById('product-pairing-suggestions').textContent = product.pairing_suggestions || 'Aucune suggestion d\'accord disponible.';
        
        const thumbnailGallery = document.getElementById('product-thumbnail-gallery');
        thumbnailGallery.innerHTML = ''; 
        if (product.image_urls_thumb && Array.isArray(product.image_urls_thumb) && product.image_urls_thumb.length > 0) {
            product.image_urls_thumb.forEach(thumbUrl => {
                if (typeof thumbUrl === 'string') { // Ensure it's a string URL
                    const img = document.createElement('img');
                    img.src = thumbUrl;
                    img.alt = `${product.name} miniature`;
                    img.className = 'w-full h-24 object-cover rounded cursor-pointer hover:opacity-75 transition-opacity';
                    img.onclick = () => { document.getElementById('main-product-image').src = thumbUrl; };
                    thumbnailGallery.appendChild(img);
                }
            });
        }

        if(loadingDiv) loadingDiv.style.display = 'none';
        if(contentDiv) contentDiv.style.display = 'grid'; 
    } catch (error) {
        if(loadingDiv) loadingDiv.innerHTML = `<p class="text-brand-truffle-burgundy">Impossible de charger les détails du produit: ${error.message}</p>`;
        if(contentDiv) contentDiv.style.display = 'none';
    }
}

function updatePriceFromSelection() {
    const weightOptionsSelect = document.getElementById('weight-options-select');
    const selectedOption = weightOptionsSelect.options[weightOptionsSelect.selectedIndex];
    const priceDisplay = document.getElementById('product-price-display');
    const priceUnit = document.getElementById('product-price-unit');
    const addToCartButton = document.getElementById('add-to-cart-button');

    if (selectedOption) {
        priceDisplay.textContent = `${parseFloat(selectedOption.dataset.price).toFixed(2)} €`;
        priceUnit.textContent = `/ ${selectedOption.dataset.weightGrams}g`;
        if (parseInt(selectedOption.dataset.stock) <= 0 || selectedOption.disabled) {
            addToCartButton.textContent = 'Épuisé';
            addToCartButton.disabled = true;
            addToCartButton.classList.replace('btn-gold','btn-secondary'); // Ensure correct class for styling
            addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
            addToCartButton.textContent = 'Ajouter au Panier';
            addToCartButton.disabled = false;
            addToCartButton.classList.replace('btn-secondary','btn-gold');
            addToCartButton.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    } else if (currentProductDetail && currentProductDetail.base_price === null && (!currentProductDetail.weight_options || currentProductDetail.weight_options.length === 0)) {
        // Case where there are no variants and no base price (should ideally not happen for sellable products)
        addToCartButton.textContent = 'Indisponible';
        addToCartButton.disabled = true;
    }
}


function updateDetailQuantity(change) {
    const quantityInput = document.getElementById('quantity-select');
    let currentValue = parseInt(quantityInput.value);
    currentValue += change;
    if (currentValue < 1) currentValue = 1;
    if (currentValue > 10) currentValue = 10; 
    quantityInput.value = currentValue;
}

// --- Shopping Cart (`localStorage` based for this example) ---
function getCart() {
    const cartString = localStorage.getItem('maisonTruvraCart');
    return cartString ? JSON.parse(cartString) : [];
}

function saveCart(cart) {
    localStorage.setItem('maisonTruvraCart', JSON.stringify(cart));
    updateCartCountDisplay();
    if (document.body.id === 'page-panier') {
        displayCartItems();
    }
}

function addToCart(product, quantity, selectedOptionDetails = null) {
    let cart = getCart();
    const productId = product.id;
    const cartItemId = selectedOptionDetails ? `${productId}_${selectedOptionDetails.option_id}` : productId;

    const existingItemIndex = cart.findIndex(item => item.cartId === cartItemId);
    const stockAvailable = selectedOptionDetails ? parseInt(selectedOptionDetails.stock) : parseInt(product.stock_quantity);

    if (existingItemIndex > -1) {
        const newQuantity = cart[existingItemIndex].quantity + quantity;
        if (newQuantity > stockAvailable) {
            showGlobalMessage(`Stock insuffisant. Max: ${stockAvailable} pour ${product.name} ${selectedOptionDetails ? '('+selectedOptionDetails.weight_grams+'g)' : ''}.`, "error");
            return false;
        }
        cart[existingItemIndex].quantity = newQuantity;
    } else {
        if (stockAvailable < quantity) {
            showGlobalMessage(`Stock insuffisant pour ${product.name} ${selectedOptionDetails ? '('+selectedOptionDetails.weight_grams+'g)' : ''}. Disponible: ${stockAvailable}`, "error");
            return false; 
        }
        const cartItem = {
            cartId: cartItemId,
            id: productId,
            name: product.name,
            price: selectedOptionDetails ? parseFloat(selectedOptionDetails.price) : parseFloat(product.base_price),
            quantity: quantity,
            image: product.image_url_main || 'https://placehold.co/100x100/F5EEDE/7D6A4F?text=Img',
            variant: selectedOptionDetails ? `${selectedOptionDetails.weight_grams}g` : null,
            variant_option_id: selectedOptionDetails ? selectedOptionDetails.option_id : null,
            stock: stockAvailable
        };
        cart.push(cartItem);
    }
    saveCart(cart);
    return true; 
}

function handleAddToCartFromDetail() {
    if (!currentProductDetail) {
        showGlobalMessage("Détails du produit non chargés.", "error");
        return;
    }
    const quantity = parseInt(document.getElementById('quantity-select').value);
    const weightOptionsSelect = document.getElementById('weight-options-select');
    let selectedOptionDetails = null;

    if (currentProductDetail.weight_options && currentProductDetail.weight_options.length > 0) {
        const selectedRawOption = weightOptionsSelect.options[weightOptionsSelect.selectedIndex];
        if (!selectedRawOption || selectedRawOption.disabled) { // Check if option is disabled (e.g. out of stock)
             showGlobalMessage("Veuillez sélectionner une option de poids valide et en stock.", "error");
             return;
        }
        selectedOptionDetails = {
            option_id: selectedRawOption.value,
            price: selectedRawOption.dataset.price,
            weight_grams: selectedRawOption.dataset.weightGrams,
            stock: parseInt(selectedRawOption.dataset.stock)
        };
         if (selectedOptionDetails.stock < quantity) {
            showGlobalMessage(`Stock insuffisant pour ${currentProductDetail.name} (${selectedOptionDetails.weight_grams}g). Max: ${selectedOptionDetails.stock}`, "error");
            return;
        }
    } else { 
        if (currentProductDetail.stock_quantity < quantity) {
            showGlobalMessage(`Stock insuffisant pour ${currentProductDetail.name}. Max: ${currentProductDetail.stock_quantity}`, "error");
            return;
        }
    }
    
    const addedSuccessfully = addToCart(currentProductDetail, quantity, selectedOptionDetails);
    if (addedSuccessfully) {
        // showGlobalMessage(`${currentProductDetail.name} ${selectedOptionDetails ? '('+selectedOptionDetails.weight_grams+'g)' : ''} ajouté au panier!`, "success");
        openModal('add-to-cart-modal', currentProductDetail.name);
    }
}

function updateCartItemQuantity(cartItemId, newQuantity) {
    let cart = getCart();
    const itemIndex = cart.findIndex(item => item.cartId === cartItemId);
    if (itemIndex > -1) {
        if (newQuantity <= 0) {
            cart.splice(itemIndex, 1); 
        } else if (newQuantity > cart[itemIndex].stock) {
            showGlobalMessage(`Quantité maximale de ${cart[itemIndex].stock} atteinte pour ${cart[itemIndex].name}.`, "info");
            cart[itemIndex].quantity = cart[itemIndex].stock; 
        }
        else {
            cart[itemIndex].quantity = newQuantity;
        }
        saveCart(cart);
    }
}

function removeCartItem(cartItemId) {
    let cart = getCart();
    cart = cart.filter(item => item.cartId !== cartItemId);
    saveCart(cart);
}

function updateCartCountDisplay() {
    const cart = getCart();
    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
    const cartCountDesktop = document.getElementById('cart-item-count');
    const cartCountMobile = document.getElementById('mobile-cart-item-count');
    if(cartCountDesktop) cartCountDesktop.textContent = totalItems;
    if(cartCountMobile) cartCountMobile.textContent = totalItems; 
}

function displayCartItems() {
    const cartItemsContainer = document.getElementById('cart-items-container');
    const emptyCartMessage = document.getElementById('empty-cart-message'); // Should be within cartItemsContainer or handled together
    const cartSummaryContainer = document.getElementById('cart-summary-container');
    const cart = getCart();

    if (!cartItemsContainer || !cartSummaryContainer) return;
    
    cartItemsContainer.innerHTML = ''; 

    if (cart.length === 0) {
        cartItemsContainer.innerHTML = '<p id="empty-cart-message" class="text-center text-brand-earth-brown py-8">Votre panier est actuellement vide. <a href="nos-produits.html" class="text-brand-classic-gold hover:underline">Continuer vos achats</a></p>';
        cartSummaryContainer.style.display = 'none';
    } else {
        cartSummaryContainer.style.display = 'block'; 

        cart.forEach(item => {
            const itemTotal = item.price * item.quantity;
            const cartItemHTML = `
                <div class="cart-item" data-cart-item-id="${item.cartId}">
                    <div class="flex items-center flex-grow">
                        <img src="${item.image}" alt="${item.name}" class="cart-item-image">
                        <div>
                            <h3 class="text-md font-semibold text-brand-near-black">${item.name}</h3>
                            ${item.variant ? `<p class="text-xs text-brand-warm-taupe">${item.variant}</p>` : ''}
                            <p class="text-sm text-brand-classic-gold">${parseFloat(item.price).toFixed(2)} €</p>
                        </div>
                    </div>
                    <div class="flex items-center space-x-2 sm:space-x-3">
                        <div class="quantity-input-controls flex items-center">
                            <button onclick="changeCartItemQuantity('${item.cartId}', -1)" class="rounded-l">-</button>
                            <input type="number" value="${item.quantity}" min="1" max="${item.stock}" class="quantity-input cart-item-quantity-input" readonly data-id="${item.cartId}">
                            <button onclick="changeCartItemQuantity('${item.cartId}', 1)" class="rounded-r">+</button>
                        </div>
                        <p class="text-md font-semibold text-brand-near-black w-20 text-right">${itemTotal.toFixed(2)} €</p>
                        <button onclick="removeCartItem('${item.cartId}')" title="Supprimer l'article" class="text-brand-truffle-burgundy hover:text-red-700">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                        </button>
                    </div>
                </div>
            `;
            cartItemsContainer.insertAdjacentHTML('beforeend', cartItemHTML);
        });
        updateCartSummary();
    }
}

function changeCartItemQuantity(cartItemId, change) {
    const inputElement = document.querySelector(`.cart-item-quantity-input[data-id="${cartItemId}"]`);
    if (inputElement) { // Check if element exists
        let currentQuantity = parseInt(inputElement.value);
        updateCartItemQuantity(cartItemId, currentQuantity + change); 
    }
}


function updateCartSummary() {
    const cart = getCart();
    const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const shipping = subtotal > 0 && subtotal < 75 ? 7.50 : 0; // Example: free shipping over 75€
    const total = subtotal + shipping;

    document.getElementById('cart-subtotal').textContent = `${subtotal.toFixed(2)} €`;
    if (subtotal > 0) {
        document.getElementById('cart-shipping').textContent = shipping > 0 ? `${shipping.toFixed(2)} €` : 'Gratuite';
    } else {
         document.getElementById('cart-shipping').textContent = 'N/A';
    }
    document.getElementById('cart-total').textContent = `${total.toFixed(2)} €`;
}

// --- Checkout (`paiement.html`) ---
async function handleCheckout(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form);
    const cart = getCart();
    const currentUser = getCurrentUser();

    if (cart.length === 0) {
        showGlobalMessage("Votre panier est vide. Impossible de procéder au paiement.", "error");
        return;
    }

    let isValid = true;
    const requiredFields = [
        { id: 'checkout-email', validator: validateEmail, message: "E-mail invalide." },
        { id: 'checkout-firstname', message: "Prénom requis." },
        { id: 'checkout-lastname', message: "Nom requis." },
        { id: 'checkout-address', message: "Adresse requise." },
        { id: 'checkout-zipcode', message: "Code postal requis." },
        { id: 'checkout-city', message: "Ville requise." },
        { id: 'checkout-country', message: "Pays requis." }
    ];

    requiredFields.forEach(fieldInfo => {
        const fieldElement = form.querySelector(`#${fieldInfo.id}`);
        if (fieldElement) { // Field might not exist if user is logged in (e.g. email)
            const value = fieldElement.value.trim();
            if (!value || (fieldInfo.validator && !fieldInfo.validator(value))) {
                setFieldError(fieldElement, fieldInfo.message);
                isValid = false;
            }
        }
    });
    
    // Validate payment fields (basic presence check, actual validation would be via Stripe.js etc.)
    const paymentFields = ['card-number', 'card-expiry', 'card-cvc', 'cardholder-name'];
    paymentFields.forEach(id => {
        const field = form.querySelector(`#${id}`);
        if(field && !field.value.trim()){
            setFieldError(field, "Ce champ de paiement est requis.");
            isValid = false;
        }
    });


    if (!isValid) {
        showGlobalMessage("Veuillez corriger les erreurs dans le formulaire de paiement.", "error");
        return;
    }


    const customerEmail = currentUser ? currentUser.email : form.querySelector('#checkout-email').value;
    const shippingAddress = {
        firstname: form.querySelector('#checkout-firstname').value,
        lastname: form.querySelector('#checkout-lastname').value,
        address: form.querySelector('#checkout-address').value,
        apartment: form.querySelector('#checkout-apartment').value || '',
        zipcode: form.querySelector('#checkout-zipcode').value,
        city: form.querySelector('#checkout-city').value,
        country: form.querySelector('#checkout-country').value,
        phone: form.querySelector('#checkout-phone').value || ''
    };
    
    const orderData = {
        customerEmail: customerEmail,
        shippingAddress: shippingAddress,
        cartItems: cart.map(item => ({ 
            id: item.id, 
            name: item.name, 
            quantity: item.quantity, 
            price: item.price, 
            variant: item.variant,
            variant_option_id: item.variant_option_id
        })),
        userId: currentUser ? currentUser.id : null
    };

    showGlobalMessage("Traitement de la commande...", "info", 60000);

    try {
        const result = await makeApiRequest('/orders/checkout', 'POST', orderData, !!currentUser); 
        if (result.success) {
            showGlobalMessage(`Commande ${result.orderId} passée avec succès! Montant total: ${parseFloat(result.totalAmount).toFixed(2)} €`, "success", 10000);
            saveCart([]); 
            sessionStorage.setItem('lastOrderDetails', JSON.stringify(result));
            window.location.href = 'confirmation-commande.html'; 
        } else {
            showGlobalMessage(result.message || "Échec de la commande.", "error");
        }
    } catch (error) {
        // Error message shown by makeApiRequest
    }
}

// --- Form Validation Helpers (shared) ---
function setFieldError(field, message) {
    field.classList.add('border-red-500', 'ring-red-500'); // Add error class for styling
    let errorElement = field.parentElement.querySelector('.error-message'); // Search within parent
    if (!errorElement) { // If not found, create and append
        errorElement = document.createElement('p');
        errorElement.classList.add('error-message', 'text-xs', 'text-red-600', 'mt-1');
        field.parentElement.appendChild(errorElement); // Append to parent for better layout
    }
    errorElement.textContent = message;
}

function clearFormErrors(form) {
    form.querySelectorAll('.border-red-500, .ring-red-500').forEach(el => {
        el.classList.remove('border-red-500', 'ring-red-500');
    });
    form.querySelectorAll('.error-message').forEach(el => el.remove());
}


// --- Modals ---
function openModal(modalId, productName = '') {
    const modal = document.getElementById(modalId);
    if (modal) {
        if (modalId === 'add-to-cart-modal' && productName) {
            const modalProductName = modal.querySelector('#modal-product-name');
            if(modalProductName) modalProductName.textContent = `${productName} ajouté au panier !`;
        }
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}


// --- DOMContentLoaded ---
document.addEventListener('DOMContentLoaded', () => {
    initializeMobileMenu();
    initializeNewsletterForm();
    setActiveNavLink();
    updateLoginState(); 
    updateCartCountDisplay(); 

    const currentYearEl = document.getElementById('currentYear');
    if (currentYearEl) currentYearEl.textContent = new Date().getFullYear();

    if (document.body.id === 'page-nos-produits') {
        fetchAndDisplayProducts('all');
        setupCategoryFilters();
    } else if (document.body.id === 'page-produit-detail') {
        loadProductDetail();
    } else if (document.body.id === 'page-panier') {
        displayCartItems();
    } else if (document.body.id === 'page-compte') {
        displayAccountDashboard();
        const loginForm = document.getElementById('login-form');
        if (loginForm) loginForm.addEventListener('submit', handleLogin);
        
        // This is a placeholder - ideally you'd have a separate registration form or tab
        const createAccountButton = document.querySelector('#login-register-section button[onclick*="inscription"]');
        if(createAccountButton){
            createAccountButton.addEventListener('click', (e) => {
                e.preventDefault();
                showGlobalMessage('Fonctionnalité d\'inscription non implémentée sur cette page. Veuillez contacter l\'administrateur.', 'info');
            });
        }
    } else if (document.body.id === 'page-paiement') { 
        const checkoutForm = document.getElementById('checkout-form'); 
        if (checkoutForm) checkoutForm.addEventListener('submit', handleCheckout);
        
        const currentUser = getCurrentUser();
        const checkoutEmailField = document.getElementById('checkout-email');
        const checkoutFirstname = document.getElementById('checkout-firstname');
        const checkoutLastname = document.getElementById('checkout-lastname');


        if(currentUser && checkoutEmailField) {
            checkoutEmailField.value = currentUser.email;
            checkoutEmailField.readOnly = true; 
            checkoutEmailField.classList.add('bg-gray-100');
        }
        if(currentUser && checkoutFirstname && currentUser.prenom) {
            checkoutFirstname.value = currentUser.prenom;
        }
        if(currentUser && checkoutLastname && currentUser.nom) {
            checkoutLastname.value = currentUser.nom;
        }

        // Display cart summary on checkout page
        const cart = getCart();
        const checkoutCartSummary = document.getElementById('checkout-cart-summary');
        if(checkoutCartSummary && cart.length > 0){
            let summaryHtml = '<h3 class="text-lg font-serif text-brand-near-black mb-4">Récapitulatif de votre commande</h3><ul class="space-y-2 mb-4">';
            let subtotal = 0;
            cart.forEach(item => {
                summaryHtml += `<li class="flex justify-between text-sm"><span>${item.name} ${item.variant ? '('+item.variant+')' : ''} x ${item.quantity}</span> <span>${(item.price * item.quantity).toFixed(2)}€</span></li>`;
                subtotal += item.price * item.quantity;
            });
            const shipping = subtotal > 0 && subtotal < 75 ? 7.50 : 0;
            const total = subtotal + shipping;
            summaryHtml += `</ul>
                <div class="border-t border-brand-warm-taupe/30 pt-4 space-y-1">
                    <p class="flex justify-between text-sm"><span>Sous-total:</span> <span>${subtotal.toFixed(2)}€</span></p>
                    <p class="flex justify-between text-sm"><span>Livraison:</span> <span>${shipping > 0 ? shipping.toFixed(2)+'€' : 'Gratuite'}</span></p>
                    <p class="flex justify-between text-lg font-semibold text-brand-near-black"><span>Total:</span> <span>${total.toFixed(2)}€</span></p>
                </div>
            `;
            checkoutCartSummary.innerHTML = summaryHtml;
        } else if (checkoutCartSummary) {
            checkoutCartSummary.innerHTML = '<p>Votre panier est vide.</p>';
             const proceedButton = document.querySelector('#checkout-form button[type="submit"]');
            if(proceedButton) proceedButton.disabled = true;
        }


    } else if (document.body.id === 'page-confirmation-commande') {
        const orderDetailsString = sessionStorage.getItem('lastOrderDetails');
        const confirmationOrderIdEl = document.getElementById('confirmation-order-id');
        const confirmationTotalAmountEl = document.getElementById('confirmation-total-amount');
        const confirmationMessageEl = document.getElementById('confirmation-message');


        if (orderDetailsString && confirmationOrderIdEl && confirmationTotalAmountEl) {
            const orderDetails = JSON.parse(orderDetailsString);
            confirmationOrderIdEl.textContent = orderDetails.orderId;
            confirmationTotalAmountEl.textContent = parseFloat(orderDetails.totalAmount).toFixed(2);
            sessionStorage.removeItem('lastOrderDetails'); 
        } else if (confirmationMessageEl) {
            confirmationMessageEl.textContent = "Détails de la commande non trouvés. Veuillez vérifier vos e-mails ou contacter le support.";
            if(confirmationOrderIdEl) confirmationOrderIdEl.textContent = "N/A";
            if(confirmationTotalAmountEl) confirmationTotalAmountEl.textContent = "N/A";
        }
    }

    document.querySelectorAll('.modal-overlay').forEach(modalOverlay => {
        modalOverlay.addEventListener('click', function(event) {
            if (event.target === modalOverlay) { 
                closeModal(modalOverlay.id);
            }
        });
    });
});
