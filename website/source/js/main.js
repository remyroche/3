// website/js/main.js
// Main script for initializing the frontend application and page-specific logic.

function initializeLangSwitcher() {
    const currentLang = document.documentElement.lang || 'fr'; 
    const pathSegments = window.location.pathname.split('/');
    let pageName = pathSegments.pop() || 'index.html'; // website/js/main.js
// Main script for initializing the frontend application and page-specific logic.

function initializeLangSwitcher() {
    const currentLang = document.documentElement.lang || 'fr'; 
    
    document.querySelectorAll('.lang-link').forEach(link => {
        const linkLang = link.dataset.lang; 
        
        try {
            const currentUrl = new URL(window.location.href);
            const newUrl = new URL(currentUrl); // Create a mutable copy

            // Split pathname into segments to handle language prefix
            let pathSegments = newUrl.pathname.split('/').filter(segment => segment !== '');
            
            // Remove existing language prefix if present
            if (pathSegments.length > 0 && (pathSegments[0] === 'fr' || pathSegments[0] === 'en')) {
                pathSegments.shift(); 
            }

            // Prepend the new language code
            newUrl.pathname = `/${linkLang}/${pathSegments.join('/')}`;

            // Ensure index.html for root paths of a language directory
            if (newUrl.pathname === `/${linkLang}/` || newUrl.pathname === `/${linkLang}`) {
                newUrl.pathname = `/${linkLang}/index.html`;
            }
            // Ensure path doesn't end with just / if it's not the root of the language
            if (newUrl.pathname.endsWith('/') && newUrl.pathname !== `/${linkLang}/`) {
                 newUrl.pathname = newUrl.pathname.slice(0, -1);
            }


            link.setAttribute('href', newUrl.href);

        } catch (error) {
            console.error("Error constructing language switch URL:", error);
            // Fallback or keep original link if URL parsing fails
            const pageName = window.location.pathname.split("/").pop() || 'index.html';
            link.setAttribute('href', `/${linkLang}/${pageName}${window.location.search}`);
        }

        // Style active language link (existing logic is fine)
        if (linkLang === currentLang) {
            link.style.opacity = '1';
            link.style.border = '2px solid #D4AF37'; 
            link.style.borderRadius = '4px';
            link.style.padding = '2px 4px';
            link.style.cursor = 'default';
            link.onclick = (e) => e.preventDefault(); 
        } else {
            link.style.opacity = '0.6';
            link.style.border = '2px solid transparent';
            link.style.padding = '2px 4px';
            link.style.cursor = 'pointer';
            link.onclick = null; 
            link.addEventListener('mouseover', () => { link.style.opacity = '1'; });
            link.addEventListener('mouseout', () => { link.style.opacity = '0.6'; });
        }
    });
}

async function loadHeader() {
    const headerPlaceholder = document.getElementById('header-placeholder');
    if (!headerPlaceholder) {
        console.error(t('public.js.loading_header_error_console')); 
        return;
    }
    try {
        const response = await fetch('header.html'); 
        if (!response.ok) {
            throw new Error(`${t('public.js.loading_header_error_status')} ${response.status}`); 
        }
        const headerHtml = await response.text();
        headerPlaceholder.innerHTML = headerHtml;

        if (typeof initializeMobileMenu === 'function') initializeMobileMenu();
        if (typeof setActiveNavLink === 'function') setActiveNavLink();
        if (typeof updateLoginState === 'function') updateLoginState();
        if (typeof updateCartDisplay === 'function') updateCartDisplay(); 
        
        initializeLangSwitcher();

    } catch (error) {
        console.error("Failed to load header:", error); 
        headerPlaceholder.innerHTML = `<p class='text-center text-red-500'>${t('public.js.loading_header_error_user')}</p>`; 
    }
}

async function loadFooter() {
    const footerPlaceholder = document.getElementById('footer-placeholder');
    if (!footerPlaceholder) {
        console.error(t('public.js.loading_footer_error_console')); 
        return;
    }
    try {
        const response = await fetch('footer.html'); 
        if (!response.ok) {
            throw new Error(`${t('public.js.loading_footer_error_status')} ${response.status}`); 
        }
        const footerHtml = await response.text();
        footerPlaceholder.innerHTML = footerHtml;

        if (typeof initializeNewsletterForm === 'function') {
            if (footerPlaceholder.querySelector('#newsletter-form')) {
                initializeNewsletterForm();
            }
        }
        const currentYearEl = footerPlaceholder.querySelector('#currentYear');
        if (currentYearEl) {
            currentYearEl.textContent = new Date().getFullYear();
        }

    } catch (error) {
        console.error("Failed to load footer:", error); 
        footerPlaceholder.innerHTML = `<p class='text-center text-red-500'>${t('public.js.loading_footer_error_user')}</p>`; 
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    await Promise.all([
        loadHeader(), 
        loadFooter()
    ]);

    const globalCurrentYearEl = document.getElementById('currentYear');
    if (globalCurrentYearEl && !document.getElementById('footer-placeholder')?.querySelector('#currentYear')) {
         globalCurrentYearEl.textContent = new Date().getFullYear();
    }
    if (typeof initializeNewsletterForm === 'function' && 
        document.getElementById('newsletter-form') && 
        !document.getElementById('footer-placeholder')?.querySelector('#newsletter-form')) {
        initializeNewsletterForm();
    }

    const bodyId = document.body.id;

    if (bodyId === 'page-index') {
        // Specific logic for index page if any
    } else if (bodyId === 'page-nos-produits') {
        // This page is handled by nos-produits.js which self-initializes with dynamic data
    } else if (bodyId === 'page-produit-detail') {
        if (typeof loadProductDetail === 'function') loadProductDetail(); 
        const addToCartDetailButton = document.getElementById('add-to-cart-button');
        if (addToCartDetailButton && typeof handleAddToCartFromDetail === 'function') {
            addToCartDetailButton.addEventListener('click', (event) => {
                event.preventDefault(); 
                handleAddToCartFromDetail(); 
            });
        }
    } else if (bodyId === 'page-panier') {
        if (typeof initCartPage === 'function') { 
            initCartPage(); 
        }
    } else if (bodyId === 'page-compte') {
        if (typeof displayAccountDashboard === 'function') displayAccountDashboard(); 
        const loginForm = document.getElementById('login-form');
        if (loginForm && typeof handleLogin === 'function') { 
            loginForm.addEventListener('submit', handleLogin); 
        }
        
        // Attach registration form handler
        const registrationForm = document.getElementById('registration-form'); // Ensure this ID matches your form in compte.html
        if (registrationForm && typeof handleRegistrationForm === 'function') {
            registrationForm.addEventListener('submit', handleRegistrationForm);
        }

        const createAccountButton = document.querySelector('#login-register-section button.btn-secondary'); // More specific selector if needed
        if(createAccountButton && typeof showGlobalMessage === 'function'){
            createAccountButton.addEventListener('click', (e) => {
                e.preventDefault();
                // Instead of a toast, this button might toggle visibility of the registration form
                // Or, if it's a separate page, it would be an <a> tag.
                // For now, keeping the toast as per original logic if registration is not on the same view.
                // If registration form is on the same page, you'd toggle its display here.
                // Example: document.getElementById('registration-form-section').style.display = 'block';
                //          document.getElementById('login-form-section').style.display = 'none';
                showGlobalMessage(t('public.js.registration_feature_not_implemented'), 'info'); 
            });
        }
         const forgotPasswordLink = document.querySelector('#login-form a[href="#"]'); 
        if (forgotPasswordLink) {
            forgotPasswordLink.addEventListener('click', (e) => {
                e.preventDefault();
                showGlobalMessage(t('public.js.password_reset_not_implemented'), 'info'); 
            });
        }
    } else if (bodyId === 'page-paiement') { 
        if (typeof initializeCheckoutPage === 'function') initializeCheckoutPage(); 
    } else if (bodyId === 'page-confirmation-commande') {
        if (typeof initializeConfirmationPage === 'function') initializeConfirmationPage(); 
    } else if (bodyId === 'page-professionnels') {
        // Logic is in professionnels.js, which should self-initialize
    }

    // Modal close listeners
    document.querySelectorAll('.modal-overlay').forEach(modalOverlay => {
        modalOverlay.addEventListener('click', function(event) {
            if (event.target === modalOverlay && typeof closeModal === 'function') { 
                closeModal(modalOverlay.id); 
            }
        });
    });
    document.querySelectorAll('.modal-close-button').forEach(button => { 
        button.addEventListener('click', function() {
            const modal = this.closest('.modal-overlay');
            if (modal && typeof closeModal === 'function') {
                closeModal(modal.id); 
            }
        });
    });

    // Listen for authentication state changes
    document.addEventListener('authStateChanged', (event) => {
        const currentBodyId = document.body.id;
        if (typeof updateLoginState === 'function') updateLoginState(); 
        if (typeof updateCartDisplay === 'function') updateCartDisplay();   

        if (currentBodyId === 'page-panier') {
            if (typeof initCartPage === 'function') initCartPage(); 
        } else if (currentBodyId === 'page-compte') {
            if (typeof displayAccountDashboard === 'function') displayAccountDashboard(); 
        } else if (currentBodyId === 'page-professionnels') {
            if (typeof updateProfessionalView === 'function') updateProfessionalView(); 
        }
    });
});
