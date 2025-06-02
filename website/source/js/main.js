// website/js/main.js
// Main script for initializing the frontend application and page-specific logic.

function initializeLangSwitcher() {
    const currentLang = document.documentElement.lang || 'fr'; 
    const pathSegments = window.location.pathname.split('/');
    let pageName = pathSegments.pop() || 'index.html'; 
    if (pageName === currentLang && pathSegments.length > 0) { 
        pageName = 'index.html';
    }

    document.querySelectorAll('.lang-link').forEach(link => {
        const linkLang = link.dataset.lang; 
        const currentPathname = window.location.pathname;
        let baseHref = currentPathname;

        // Logic to switch between /fr/ and /en/ paths
        // Assumes build structure like /dist/{lang}/page.html or just /{lang}/page.html
        const langPathRegex = /^\/(fr|en)\//;
        if (langPathRegex.test(currentPathname)) {
            baseHref = currentPathname.replace(langPathRegex, `/${linkLang}/`);
        } else if (currentPathname.startsWith(`/${currentLang}/`)) { // case like /fr
             baseHref = currentPathname.replace(`/${currentLang}/`, `/${linkLang}/`);
        } else { // If no lang in path (e.g. root, or dev serving from source)
             // This might need to be smarter if your dev and prod URL structures differ significantly without lang prefix
             baseHref = `/${linkLang}${currentPathname.startsWith('/') ? '' : '/'}${pageName}`;
        }
        
        // Ensure baseHref points to a file, not just a directory, if pageName is index.html
        if (baseHref.endsWith(`/${linkLang}/`)) {
            baseHref += 'index.html';
        }


        link.setAttribute('href', baseHref);

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
        console.error(t('public.js.loading_header_error_console')); // New key for console
        return;
    }
    try {
        const response = await fetch('header.html'); 
        if (!response.ok) {
            throw new Error(`${t('public.js.loading_header_error_status')} ${response.status}`); // New key
        }
        const headerHtml = await response.text();
        headerPlaceholder.innerHTML = headerHtml;

        if (typeof initializeMobileMenu === 'function') initializeMobileMenu();
        if (typeof setActiveNavLink === 'function') setActiveNavLink();
        if (typeof updateLoginState === 'function') updateLoginState();
        if (typeof updateCartDisplay === 'function') updateCartDisplay(); 
        
        initializeLangSwitcher();

    } catch (error) {
        console.error("Failed to load header:", error); // Dev-facing
        headerPlaceholder.innerHTML = `<p class='text-center text-red-500'>${t('public.js.loading_header_error_user')}</p>`; // New key for user
    }
}

async function loadFooter() {
    const footerPlaceholder = document.getElementById('footer-placeholder');
    if (!footerPlaceholder) {
        console.error(t('public.js.loading_footer_error_console')); // New key for console
        return;
    }
    try {
        const response = await fetch('footer.html'); 
        if (!response.ok) {
            throw new Error(`${t('public.js.loading_footer_error_status')} ${response.status}`); // New key
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
        console.error("Failed to load footer:", error); // Dev-facing
        footerPlaceholder.innerHTML = `<p class='text-center text-red-500'>${t('public.js.loading_footer_error_user')}</p>`; // New key for user
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
        // If there were static parts of this page needing JS init, it would go here.
    } else if (bodyId === 'page-produit-detail') {
        if (typeof loadProductDetail === 'function') loadProductDetail(); // from products.js
        const addToCartDetailButton = document.getElementById('add-to-cart-button');
        if (addToCartDetailButton && typeof handleAddToCartFromDetail === 'function') {
            addToCartDetailButton.addEventListener('click', (event) => {
                event.preventDefault(); 
                handleAddToCartFromDetail(); 
            });
        }
    } else if (bodyId === 'page-panier') {
        if (typeof initCartPage === 'function') { // from cart.js
            initCartPage(); 
        }
    } else if (bodyId === 'page-compte') {
        if (typeof displayAccountDashboard === 'function') displayAccountDashboard(); // from auth.js
        const loginForm = document.getElementById('login-form');
        if (loginForm && typeof handleLogin === 'function') { // from auth.js
            loginForm.addEventListener('submit', handleLogin); 
        }
        const createAccountButton = document.querySelector('#login-register-section button.btn-secondary');
        if(createAccountButton && typeof showGlobalMessage === 'function'){
            createAccountButton.addEventListener('click', (e) => {
                e.preventDefault();
                showGlobalMessage(t('public.js.registration_feature_not_implemented'), 'info'); // Key: public.js.registration_feature_not_implemented
            });
        }
         const forgotPasswordLink = document.querySelector('#login-form a[href="#"]'); 
        if (forgotPasswordLink) {
            forgotPasswordLink.addEventListener('click', (e) => {
                e.preventDefault();
                showGlobalMessage(t('public.js.password_reset_not_implemented'), 'info'); // Key: public.js.password_reset_not_implemented
            });
        }
    } else if (bodyId === 'page-paiement') { 
        if (typeof initializeCheckoutPage === 'function') initializeCheckoutPage(); // from checkout.js
    } else if (bodyId === 'page-confirmation-commande') {
        if (typeof initializeConfirmationPage === 'function') initializeConfirmationPage(); // from checkout.js
    } else if (bodyId === 'page-professionnels') {
        // Logic is in professionnels.js, which should self-initialize
    }

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

    document.addEventListener('authStateChanged', (event) => {
        const currentBodyId = document.body.id;
        if (typeof updateLoginState === 'function') updateLoginState(); 
        if (typeof updateCartDisplay === 'function') updateCartDisplay();   

        if (currentBodyId === 'page-panier') {
            if (typeof initCartPage === 'function') initCartPage(); 
        } else if (currentBodyId === 'page-compte') {
            if (typeof displayAccountDashboard === 'function') displayAccountDashboard(); 
        } else if (currentBodyId === 'page-professionnels') {
            if (typeof updateProfessionalView === 'function') updateProfessionalView(); // from professionnels.js
        }
    });
});
