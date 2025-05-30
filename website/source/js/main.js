// website/js/main.js
// Main script for initializing the frontend application and page-specific logic.

/**
 * Initializes the language switcher links and highlights the current language.
 */
function initializeLangSwitcher() {
    const path = window.location.pathname;
    const pathSegments = path.split('/').filter(Boolean); // e.g., ['dist', 'fr', 'index.html'] or ['fr', 'index.html']

    let currentLang = 'fr'; // Default
    let langIndex = pathSegments.indexOf('fr');
    if (langIndex === -1) {
        langIndex = pathSegments.indexOf('en');
    }

    let pagePath = 'index.html'; // Default page

    if (langIndex !== -1) {
        currentLang = pathSegments[langIndex];
        if (langIndex + 1 < pathSegments.length) {
            pagePath = pathSegments.slice(langIndex + 1).join('/');
        }
    } else {
        // Fallback to HTML lang attribute if no lang in path
        currentLang = document.documentElement.lang || 'fr';
    }

    const otherLang = currentLang === 'fr' ? 'en' : 'fr';
    const newHref = `../${otherLang}/${pagePath}`;// website/js/main.js
// Main script for initializing the frontend application and page-specific logic.

let currentLang = 'fr'; // Default language
let translations = {}; // To store loaded translations

/**
 * Fetches and loads translation data for the given language.
 * @param {string} lang - The language code (e.g., 'fr', 'en').
 */
async function loadTranslations(lang) {
    try {
        const response = await fetch(`../locales/${lang}.json`); // Path relative to HTML files in dist/lang/
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        translations = await response.json();
        currentLang = lang;
        console.log(`Translations loaded for ${lang}`);
        // After loading, re-apply translations to the page
        applyTranslationsToPage();
        initializeLangSwitcher(); // Re-initialize switcher to reflect current lang
    } catch (error) {
        console.error(`Could not load translations for ${lang}:`, error);
        // Fallback or error handling
        if (lang !== 'fr') { // Try loading French as a fallback if English fails
            console.warn("Falling back to French translations.");
            await loadTranslations('fr');
        } else {
            // If French also fails, the page will show keys or default text
            document.documentElement.lang = 'fr'; // Default lang attribute
        }
    }
}

/**
 * Translates a key using the loaded dictionary.
 * @param {string} key - The translation key (e.g., "public.nav.home").
 * @param {object} [replacements={}] - Optional replacements for placeholders in format {placeholder: value}.
 * @returns {string} The translated string, or the key itself if not found.
 */
function t(key, replacements = {}) {
    let text = translations[key] || key;
    for (const placeholder in replacements) {
        text = text.replace(new RegExp(`%${placeholder}%`, 'g'), replacements[placeholder]);
    }
    return text;
}


/**
 * Applies loaded translations to all elements with data-translate attributes.
 */
function applyTranslationsToPage() {
    document.querySelectorAll('[data-translate]').forEach(element => {
        const key = element.dataset.translate;
        const translatedText = t(key);
        if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
            if (element.placeholder) element.placeholder = translatedText;
        } else {
            element.innerHTML = translatedText; // Use innerHTML to allow for HTML in translations if needed
        }
    });
    // Set the lang attribute on the HTML tag
    document.documentElement.lang = currentLang;

    // Update page title
    const pageTitleKey = document.body.dataset.pageTitleKey; // e.g. public.index.title
    if (pageTitleKey) {
        document.title = t(pageTitleKey);
    }
}


/**
 * Initializes the language switcher links and highlights the current language.
 * Determines current language from the path (e.g., /dist/fr/index.html).
 */
function initializeLangSwitcher() {
    const path = window.location.pathname;
    // Expected path: /dist/{lang}/page.html or /{lang}/page.html if dist is root
    const pathSegments = path.split('/').filter(Boolean); 
    
    let detectedLang = 'fr'; // Default
    let pagePathAfterLang = 'index.html'; // Default page

    // Try to find 'fr' or 'en' in path segments
    const langIndexFR = pathSegments.indexOf('fr');
    const langIndexEN = pathSegments.indexOf('en');

    if (langIndexFR !== -1) {
        detectedLang = 'fr';
        pagePathAfterLang = pathSegments.slice(langIndexFR + 1).join('/') || 'index.html';
    } else if (langIndexEN !== -1) {
        detectedLang = 'en';
        pagePathAfterLang = pathSegments.slice(langIndexEN + 1).join('/') || 'index.html';
    } else {
        // Fallback if lang not in path (e.g. local dev without /dist/{lang}/ structure)
        // This part might need adjustment based on your exact dev server setup.
        // For now, we'll rely on the initially loaded `currentLang`.
        detectedLang = currentLang; 
        // Try to guess pagePath if not index.html
        if (pathSegments.length > 0 && pathSegments[pathSegments.length -1].endsWith('.html')) {
            pagePathAfterLang = pathSegments[pathSegments.length -1];
        }
    }
    
    currentLang = detectedLang; // Update global currentLang based on detection

    document.querySelectorAll('.lang-link').forEach(link => {
        const linkLang = link.dataset.lang;
        // Construct new href: go up one level from current lang dir, then into other lang dir
        const newHref = `../${linkLang}/${pagePathAfterLang}`; 
        link.setAttribute('href', newHref);

        if (linkLang === currentLang) {
            link.style.opacity = '1';
            link.style.border = '2px solid #D4AF37';
            link.style.borderRadius = '4px';
            link.style.padding = '2px 4px'; // Added horizontal padding
            link.style.cursor = 'default';
            link.onclick = (e) => e.preventDefault(); // Prevent navigation
        } else {
            link.style.opacity = '0.6';
            link.style.border = '2px solid transparent';
            link.style.padding = '2px 4px';
            link.style.cursor = 'pointer';
            link.onclick = null; // Ensure click works for other lang
        }

        if (linkLang !== currentLang) {
            link.addEventListener('mouseover', () => { link.style.opacity = '1' });
            link.addEventListener('mouseout', () => { link.style.opacity = '0.6' });
        } else {
            link.onmouseover = null;
            link.onmouseout = null;
        }
    });
}


async function loadHeader() {
    const headerPlaceholder = document.getElementById('header-placeholder');
    if (!headerPlaceholder) {
        console.error("Header placeholder #header-placeholder not found.");
        return;
    }

    try {
        const response = await fetch('header.html'); 
        if (!response.ok) {
            throw new Error(t('public.js.loading_header_error') + `: ${response.status}`);
        }
        const headerHtml = await response.text();
        headerPlaceholder.innerHTML = headerHtml;

        if (typeof initializeMobileMenu === 'function') initializeMobileMenu();
        if (typeof setActiveNavLink === 'function') setActiveNavLink();
        if (typeof updateLoginState === 'function') updateLoginState();
        if (typeof updateCartDisplay === 'function') updateCartDisplay();
        
        // Language switcher init is now part of loadTranslations flow
        // but we ensure it's called after header content is in DOM.
        // If translations are already loaded, this will just update styles.
        initializeLangSwitcher(); 
        applyTranslationsToPage(); // Apply to newly loaded header content

    } catch (error) {
        console.error("Failed to load header:", error);
        headerPlaceholder.innerHTML = `<p class='text-center text-red-500'>${t('public.js.loading_header_error')}</p>`;
    }
}

async function loadFooter() {
    const footerPlaceholder = document.getElementById('footer-placeholder');
    if (!footerPlaceholder) {
        console.error("Footer placeholder #footer-placeholder not found.");
        return;
    }
    try {
        const response = await fetch('footer.html'); 
        if (!response.ok) {
            throw new Error(t('public.js.loading_footer_error') + `: ${response.status}`);
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
        applyTranslationsToPage(); // Apply to newly loaded footer content

    } catch (error) {
        console.error("Failed to load footer:", error);
        footerPlaceholder.innerHTML = `<p class='text-center text-red-500'>${t('public.js.loading_footer_error')}</p>`;
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // Determine initial language from path or default to 'fr'
    const pathSegments = window.location.pathname.split('/').filter(Boolean);
    let initialLang = 'fr';
    const langIndexFR = pathSegments.indexOf('fr');
    const langIndexEN = pathSegments.indexOf('en');
    if (langIndexEN !== -1) initialLang = 'en';
    else if (langIndexFR !== -1) initialLang = 'fr';
    
    await loadTranslations(initialLang); // Load translations first

    await Promise.all([
        loadHeader(),
        loadFooter()
    ]);

    const globalCurrentYearEl = document.getElementById('currentYear');
    if (globalCurrentYearEl && !document.getElementById('footer-placeholder')?.querySelector('#currentYear')) {
         globalCurrentYearEl.textContent = new Date().getFullYear();
    }
    if (typeof initializeNewsletterForm === 'function' && !document.getElementById('footer-placeholder')?.querySelector('#newsletter-form')) {
        initializeNewsletterForm();
    }

    const bodyId = document.body.id;

    if (bodyId === 'page-index') {
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
                showGlobalMessage(t('public.js.registration_feature_not_implemented'), 'info');
            });
        }
    } else if (bodyId === 'page-paiement') { 
        if (typeof initializeCheckoutPage === 'function') initializeCheckoutPage();
    } else if (bodyId === 'page-confirmation-commande') {
        if (typeof initializeConfirmationPage === 'function') initializeConfirmationPage();
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
        const isLoggedIn = event.detail.isLoggedIn;

        if (typeof updateLoginState === 'function') updateLoginState(); 
        if (typeof updateCartDisplay === 'function') updateCartDisplay();   

        if (currentBodyId === 'page-panier') {
            if (typeof initCartPage === 'function') initCartPage(); 
        } else if (currentBodyId === 'page-compte') {
            if (typeof displayAccountDashboard === 'function') displayAccountDashboard(); 
        }
    });
});
