// website/js/main.js
// Main script for initializing the frontend application and page-specific logic.

/**
 * Initializes the language switcher links and highlights the current language.
 */
function initializeLangSwitcher() {
    const path = window.location.pathname;
    const pathSegments = path.split('/').filter(Boolean); // e.g., ['dist', 'fr', 'index.html'] or ['fr', 'index.html']

    let currentLang = 'fr'; // Default// website/js/main.js
// Main script for initializing the frontend application and page-specific logic.
// This version assumes that translations are handled by a build script (scripts/build.js)
// which replaces {{key}} in HTML and t('key') in JS files with static translated strings.

/**
 * Initializes the language switcher links.
 * It determines the current language from the HTML lang attribute (set by the build script)
 * and constructs links to the equivalent page in the other language.
 */
function initializeLangSwitcher() {
    // Determine current language from the <html lang="..."> attribute
    const currentLang = document.documentElement.lang || 'fr'; // Default to 'fr' if not set
    
    // Determine the current page's path relative to the language directory.
    // Example: if current URL is /dist/fr/nos-produits.html, pageName should be nos-produits.html
    // This logic assumes a structure like /dist/{lang}/page.html
    const pathSegments = window.location.pathname.split('/');
    let pageName = pathSegments.pop() || 'index.html'; // Get the last segment (file name) or default to index.html
    if (pageName === currentLang && pathSegments.length > 0) { 
        // This handles cases where the URL might be just /dist/fr/ (implicitly index.html)
        // or if the last segment was the lang code itself (e.g. from a base URL redirect)
        pageName = 'index.html';
    }


    document.querySelectorAll('.lang-link').forEach(link => {
        const linkLang = link.dataset.lang; // 'fr' or 'en'

        // Construct the new href.
        // Assumes HTML files are directly inside /fr/ or /en/ subdirectories.
        // e.g., if current page is /fr/nos-produits.html and link is for 'en', new href is '../en/nos-produits.html'
        const newHref = `../${linkLang}/${pageName}`;
        link.setAttribute('href', newHref);

        if (linkLang === currentLang) {
            link.style.opacity = '1';
            link.style.border = '2px solid #D4AF37'; // Gold border for active
            link.style.borderRadius = '4px';
            link.style.padding = '2px 4px';
            link.style.cursor = 'default';
            link.onclick = (e) => e.preventDefault(); // Prevent navigation for current language
        } else {
            link.style.opacity = '0.6';
            link.style.border = '2px solid transparent';
            link.style.padding = '2px 4px';
            link.style.cursor = 'pointer';
            link.onclick = null; // Ensure click works for other language link
             // Add hover effects for non-active links
            link.addEventListener('mouseover', () => { link.style.opacity = '1'; });
            link.addEventListener('mouseout', () => { link.style.opacity = '0.6'; });
        }
    });
}

/**
 * Loads the header.html content into the #header-placeholder div.
 * Initializes header-specific functionalities after loading.
 */
async function loadHeader() {
    const headerPlaceholder = document.getElementById('header-placeholder');
    if (!headerPlaceholder) {
        // console.error("Header placeholder #header-placeholder not found.");
        // Since t() is not available at runtime, use a generic or pre-translated error.
        // The build script should have replaced any t('public.js.loading_header_error') calls.
        console.error("{{public.js.loading_header_error}}"); 
        return;
    }

    try {
        // Path to header.html should be relative to the final HTML file location.
        // If HTML files are in /dist/fr/ or /dist/en/, header.html needs to be accessible.
        // Assuming header.html is copied by the build script into each language directory or is accessible via a relative path.
        // For simplicity, if header.html is also processed by build.js, it will be in the same directory.
        const response = await fetch('header.html'); 
        if (!response.ok) {
            // Error message will be pre-translated by build.js if it uses t()
            throw new Error(`{{public.js.loading_header_error}}: ${response.status}`);
        }
        const headerHtml = await response.text();
        headerPlaceholder.innerHTML = headerHtml;

        // Initialize components within the loaded header
        if (typeof initializeMobileMenu === 'function') initializeMobileMenu();
        if (typeof setActiveNavLink === 'function') setActiveNavLink();
        if (typeof updateLoginState === 'function') updateLoginState();
        if (typeof updateCartDisplay === 'function') updateCartDisplay(); // From ui.js
        
        // Initialize language switcher now that its HTML is loaded
        initializeLangSwitcher();

    } catch (error) {
        console.error("Failed to load header:", error);
        // Error message will be pre-translated by build.js
        headerPlaceholder.innerHTML = `<p class='text-center text-red-500'>{{public.js.loading_header_error}}</p>`;
    }
}

/**
 * Loads the footer.html content into the #footer-placeholder div.
 * Initializes footer-specific functionalities after loading.
 */
async function loadFooter() {
    const footerPlaceholder = document.getElementById('footer-placeholder');
    if (!footerPlaceholder) {
        // console.error("Footer placeholder #footer-placeholder not found.");
        console.error("{{public.js.loading_footer_error}}");
        return;
    }
    try {
        // Assuming footer.html is copied by the build script into each language directory or accessible via a relative path.
        const response = await fetch('footer.html'); 
        if (!response.ok) {
            throw new Error(`{{public.js.loading_footer_error}}: ${response.status}`);
        }
        const footerHtml = await response.text();
        footerPlaceholder.innerHTML = footerHtml;

        // Initialize components within the loaded footer
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
        footerPlaceholder.innerHTML = `<p class='text-center text-red-500'>{{public.js.loading_footer_error}}</p>`;
    }
}

// Main execution block after DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    // Load common components
    await Promise.all([
        loadHeader(), // This will also initialize the lang switcher
        loadFooter()
    ]);

    // Initialize global elements not tied to header/footer if they exist outside them
    const globalCurrentYearEl = document.getElementById('currentYear');
    if (globalCurrentYearEl && !document.getElementById('footer-placeholder')?.querySelector('#currentYear')) {
         globalCurrentYearEl.textContent = new Date().getFullYear();
    }
    // If newsletter form is outside footer and needs init
    if (typeof initializeNewsletterForm === 'function' && 
        document.getElementById('newsletter-form') && 
        !document.getElementById('footer-placeholder')?.querySelector('#newsletter-form')) {
        initializeNewsletterForm();
    }

    // Page-specific initializations
    const bodyId = document.body.id;

    if (bodyId === 'page-index') {
        // Specific logic for index page if any
    } else if (bodyId === 'page-nos-produits') {
        if (typeof fetchAndDisplayProducts === 'function') fetchAndDisplayProducts('all');
        if (typeof setupCategoryFilters === 'function') setupCategoryFilters();
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
        const createAccountButton = document.querySelector('#login-register-section button.btn-secondary');
        if(createAccountButton && typeof showGlobalMessage === 'function'){
            createAccountButton.addEventListener('click', (e) => {
                e.preventDefault();
                // This message will be pre-translated by build.js
                showGlobalMessage("{{public.js.registration_feature_not_implemented}}", 'info');
            });
        }
         const forgotPasswordLink = document.querySelector('#login-form a[href="#"]'); // More specific selector
        if (forgotPasswordLink) {
            forgotPasswordLink.addEventListener('click', (e) => {
                e.preventDefault();
                showGlobalMessage("{{public.js.password_reset_not_implemented}}", 'info');
            });
        }
    } else if (bodyId === 'page-paiement') { 
        if (typeof initializeCheckoutPage === 'function') initializeCheckoutPage();
    } else if (bodyId === 'page-confirmation-commande') {
        if (typeof initializeConfirmationPage === 'function') initializeConfirmationPage();
    }

    // Initialize global modals (if any)
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

    // Listen for authentication state changes (e.g., after login/logout)
    document.addEventListener('authStateChanged', (event) => {
        const currentBodyId = document.body.id;
        // const isLoggedIn = event.detail.isLoggedIn; // This detail may not be needed if UI updates are simple

        // Re-initialize components that depend on auth state for the current page
        if (typeof updateLoginState === 'function') updateLoginState(); 
        if (typeof updateCartDisplay === 'function') updateCartDisplay();   

        if (currentBodyId === 'page-panier') {
            if (typeof initCartPage === 'function') initCartPage(); 
        } else if (currentBodyId === 'page-compte') {
            if (typeof displayAccountDashboard === 'function') displayAccountDashboard(); 
        }
        // Other page-specific updates based on auth state can be added here
    });
});
