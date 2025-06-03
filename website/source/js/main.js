// website/js/main.js
// Main script for initializing the frontend application and page-specific logic.

function initializeLangSwitcher() {
    const currentLang = document.documentElement.lang || 'fr'; 
    
    document.querySelectorAll('.lang-link').forEach(link => {
        const linkLang = link.dataset.lang; 
        
        try {
            const currentUrl = new URL(window.location.href);
            const newUrl = new URL(currentUrl);

            let pathSegments = newUrl.pathname.split('/').filter(segment => segment !== '');
            
            if (pathSegments.length > 0 && (pathSegments[0] === 'fr' || pathSegments[0] === 'en')) {
                pathSegments.shift(); 
            }

            newUrl.pathname = `/${linkLang}/${pathSegments.join('/')}`;

            if (newUrl.pathname === `/${linkLang}/` || newUrl.pathname === `/${linkLang}`) {
                newUrl.pathname = `/${linkLang}/index.html`;
            }
            if (newUrl.pathname.endsWith('/') && newUrl.pathname !== `/${linkLang}/`) {
                 newUrl.pathname = newUrl.pathname.slice(0, -1);
            }
            link.setAttribute('href', newUrl.href);
        } catch (error) {
            console.error("Error constructing language switch URL:", error);
            const pageName = window.location.pathname.split("/").pop() || 'index.html';
            link.setAttribute('href', `/${linkLang}/${pageName}${window.location.search}`);
        }

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
        console.error(typeof t === 'function' ? t('public.js.loading_header_error_console') : "Header placeholder not found."); 
        return;
    }
    try {
        const response = await fetch('header.html'); 
        if (!response.ok) {
            throw new Error(`${typeof t === 'function' ? t('public.js.loading_header_error_status') : "Header load error, status:"} ${response.status}`); 
        }
        const headerHtml = await response.text();
        headerPlaceholder.innerHTML = headerHtml;

        if (typeof initializeMobileMenu === 'function') initializeMobileMenu();
        if (typeof setActiveNavLink === 'function') setActiveNavLink();
        if (typeof updateLoginState === 'function') updateLoginState();
        if (typeof updateCartDisplay === 'function') updateCartDisplay(); 
        
        initializeLangSwitcher(); // Initialize language switcher after header is loaded

    } catch (error) {
        console.error("Failed to load header:", error); 
        headerPlaceholder.innerHTML = `<p class='text-center text-red-500'>${typeof t === 'function' ? t('public.js.loading_header_error_user') : "Error loading header."}</p>`; 
    }
}

async function loadFooter() {
    const footerPlaceholder = document.getElementById('footer-placeholder');
    if (!footerPlaceholder) {
        console.error(typeof t === 'function' ? t('public.js.loading_footer_error_console') : "Footer placeholder not found."); 
        return;
    }
    try {
        const response = await fetch('footer.html'); 
        if (!response.ok) {
            throw new Error(`${typeof t === 'function' ? t('public.js.loading_footer_error_status') : "Footer load error, status:"} ${response.status}`); 
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
        footerPlaceholder.innerHTML = `<p class='text-center text-red-500'>${typeof t === 'function' ? t('public.js.loading_footer_error_user') : "Error loading footer."}</p>`; 
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // Load header and footer first as they might contain elements other scripts depend on
    // or scripts that need to run early (like UI elements for auth state).
    await loadHeader(); 
    await loadFooter();

    // Fallback for currentYear if not in footer (e.g. if footer load fails or element is elsewhere)
    const globalCurrentYearEl = document.getElementById('currentYear');
    if (globalCurrentYearEl && !document.getElementById('footer-placeholder')?.querySelector('#currentYear')) {
         globalCurrentYearEl.textContent = new Date().getFullYear();
    }
    // Fallback for newsletter if not in footer
    if (typeof initializeNewsletterForm === 'function' && 
        document.getElementById('newsletter-form') && 
        !document.getElementById('footer-placeholder')?.querySelector('#newsletter-form')) {
        initializeNewsletterForm();
    }

    const bodyId = document.body.id;

    // Page-specific initializations
    if (bodyId === 'page-index') {
        // Specific logic for index page if any
        console.log("Main.js: Index page detected.");
    } else if (bodyId === 'page-nos-produits') {
        // This page is handled by nos-produits.js which self-initializes
        console.log("Main.js: Nos Produits page detected. Logic handled by nos-produits.js.");
    } else if (bodyId === 'page-produit-detail') {
        // product.js (or nos-produits.js if it handles detail view) self-initializes based on body ID
        console.log("Main.js: Produit Detail page detected. Logic handled by its specific JS.");
        // Example if a specific function needed to be called:
        // if (typeof initializeProductDetailPage === 'function') initializeProductDetailPage();
    } else if (bodyId === 'page-panier') {
        // cart.js self-initializes its page-specific parts (initCartPage) based on body ID
        console.log("Main.js: Panier page detected. Logic handled by cart.js.");
    } else if (bodyId === 'page-compte') {
        // auth.js handles showing login or dashboard based on auth state,
        // and displayAccountDashboard is called on authStateChanged.
        // Initial call might be useful if authStateChanged doesn't fire immediately or reliably on first load.
        if (typeof displayAccountDashboard === 'function') displayAccountDashboard();
        
        const loginForm = document.getElementById('login-form');
        if (loginForm && typeof handleLogin === 'function') { 
            loginForm.addEventListener('submit', handleLogin); 
        }
        
        const registrationForm = document.getElementById('registration-form');
        if (registrationForm && typeof handleRegistrationForm === 'function') {
            registrationForm.addEventListener('submit', handleRegistrationForm);
        }
        console.log("Main.js: Compte page detected.");
    } else if (bodyId === 'page-paiement') { 
        if (typeof initializeCheckoutPage === 'function') initializeCheckoutPage(); 
        console.log("Main.js: Paiement page detected.");
    } else if (bodyId === 'page-confirmation-commande') {
        if (typeof initializeConfirmationPage === 'function') initializeConfirmationPage(); 
        console.log("Main.js: Confirmation Commande page detected.");
    } else if (bodyId === 'page-professionnels') {
        // professionnels.js self-initializes based on body ID.
        console.log("Main.js: Professionnels page detected. Logic handled by professionnels.js.");
    } else if (bodyId === 'page-invoices-pro') {
        // invoices-pro.js self-initializes based on body ID.
        console.log("Main.js: Invoices-Pro page detected. Logic handled by invoices-pro.js.");
    }
    // Add other page-specific initializations here

    // Global Modal close listeners (if not already handled by ui.js on its own)
    document.querySelectorAll('.modal-overlay').forEach(modalOverlay => {
        modalOverlay.addEventListener('click', function(event) {
            if (event.target === modalOverlay && typeof closeModal === 'function') { 
                const modalId = this.id || this.dataset.modalId; 
                if(modalId) closeModal(modalId); 
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

    // Listen for authentication state changes for global UI updates
    document.addEventListener('authStateChanged', (event) => {
        console.log("Main.js: authStateChanged event received.");
        if (typeof updateLoginState === 'function') updateLoginState(); 
        if (typeof updateCartDisplay === 'function') updateCartDisplay();   

        // Re-evaluate page-specific views that depend on auth state
        const currentBodyId = document.body.id;
        if (currentBodyId === 'page-panier' && typeof initCartPage === 'function') {
            initCartPage(); 
        } else if (currentBodyId === 'page-compte' && typeof displayAccountDashboard === 'function') {
            displayAccountDashboard(); 
        } else if (currentBodyId === 'page-professionnels' && typeof window.updateProfessionalPageSpecificView === 'function') {
            // Assuming professionnels.js exposes its view update function globally or on window
            window.updateProfessionalPageSpecificView(); 
        } else if (currentBodyId === 'page-invoices-pro' && typeof loadInvoices === 'function') {
            // invoices-pro.js's loadInvoices might re-check auth, or we can trigger it.
            // For simplicity, if it's already loaded, it might re-render or handle auth internally.
            // If it needs an explicit re-trigger:
            // loadInvoices(1); // Or its own internal auth check will handle it.
        }
    });
});
