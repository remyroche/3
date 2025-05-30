// website/js/main.js
// Main script for initializing the frontend application and page-specific logic.

async function loadHeader() {
    const headerPlaceholder = document.getElementById('header-placeholder');
    if (!headerPlaceholder) {
        console.error("L'élément #header-placeholder est introuvable.");
        return;
    }

    try {
        const response = await fetch('header.html'); // Assurez-vous que header.html est au bon endroit
        if (!response.ok) {
            throw new Error(`Erreur de chargement du header: ${response.status} ${response.statusText}`);
        }
        const headerHtml = await response.text();
        headerPlaceholder.innerHTML = headerHtml;

        // Initialiser les composants interactifs de l'en-tête
        if (typeof initializeMobileMenu === 'function') {
            initializeMobileMenu();
        }
        if (typeof setActiveNavLink === 'function') {
            setActiveNavLink();
        }
        if (typeof updateLoginState === 'function') {
            updateLoginState();
        }
        if (typeof updateCartDisplay === 'function') { // Changed from updateCartCountDisplay
            updateCartDisplay();
        }

    } catch (error) {
        console.error("Impossible de charger l'en-tête:", error);
        headerPlaceholder.innerHTML = "<p class='text-center text-red-500'>Erreur: L'en-tête n'a pas pu être chargé.</p>";
    }
}

/**
 * Charge le contenu de footer.html dans l'élément #footer-placeholder
 * et initialise les fonctionnalités du pied de page.
 */
async function loadFooter() {
    const footerPlaceholder = document.getElementById('footer-placeholder');
    if (!footerPlaceholder) {
        console.error("L'élément #footer-placeholder est introuvable.");
        return;
    }
    try {
        const response = await fetch('footer.html'); // Assurez-vous que footer.html est au bon endroit
        if (!response.ok) {
            throw new Error(`Erreur de chargement du footer: ${response.status} ${response.statusText}`);
        }
        const footerHtml = await response.text();
        footerPlaceholder.innerHTML = footerHtml;

        // Initialiser les éléments interactifs du footer si besoin
        if (typeof initializeNewsletterForm === 'function') {
            if (footerPlaceholder.querySelector('#newsletter-form')) { // Vérifie si le formulaire est bien dans le footer chargé
                initializeNewsletterForm();
            }
        }
        const currentYearEl = footerPlaceholder.querySelector('#currentYear'); // Chercher DANS le footer chargé
        if (currentYearEl) {
            currentYearEl.textContent = new Date().getFullYear();
        }

    } catch (error) {
        console.error("Impossible de charger le pied de page:", error);
        footerPlaceholder.innerHTML = "<p class='text-center text-red-500'>Erreur: Le pied de page n'a pas pu être chargé.</p>";
    }
}


// Exécuté une fois le DOM entièrement chargé
document.addEventListener('DOMContentLoaded', async () => { // Consolidated DOMContentLoaded
    // Charger l'en-tête et le pied de page en parallèle
    await Promise.all([
        loadHeader(),
        loadFooter()
    ]);

    // Initialisations globales qui ne dépendent PAS du header ou du footer directement
    // (celles qui en dépendent sont appelées DANS loadHeader/loadFooter)

    // Si #currentYear ou #newsletter-form sont en dehors du footer, initialisez-les ici :
    const globalCurrentYearEl = document.getElementById('currentYear');
    if (globalCurrentYearEl && !document.getElementById('footer-placeholder')?.querySelector('#currentYear')) {
         globalCurrentYearEl.textContent = new Date().getFullYear();
    }
    if (typeof initializeNewsletterForm === 'function' && !document.getElementById('footer-placeholder')?.querySelector('#newsletter-form')) {
        initializeNewsletterForm();
    }


    // Logique spécifique à chaque page
    const bodyId = document.body.id;

    if (bodyId === 'page-index') {
        // Aucune initialisation spécifique à la page index pour l'instant autre que celles du header/footer
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
        if (typeof initCartPage === 'function') { // Changed from displayCartItems
            initCartPage(); // From cart.js - handles login prompt or cart content
        } else {
            console.error('initCartPage function not found. Ensure cart.js is loaded.');
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
                showGlobalMessage('Fonctionnalité d\'inscription non implémentée sur cette page. Veuillez contacter l\'administrateur.', 'info');
            });
        }
    } else if (bodyId === 'page-paiement') { 
        if (typeof initializeCheckoutPage === 'function') initializeCheckoutPage();
    } else if (bodyId === 'page-confirmation-commande') {
        if (typeof initializeConfirmationPage === 'function') initializeConfirmationPage();
    }
    // ... autres pages ...

    // Initialisation des modales globales (si elles ne sont pas chargées dynamiquement)
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
        const isLoggedIn = event.detail.isLoggedIn;

        console.log(`Auth state changed on page ${currentBodyId}. User is now ${isLoggedIn ? 'logged in' : 'logged out'}.`);

        // Re-initialize components that depend on auth state for the current page
        if (typeof updateLoginState === 'function') updateLoginState(); // Update header links
        if (typeof updateCartDisplay === 'function') updateCartDisplay();   // Update cart icon

        if (currentBodyId === 'page-panier') {
            if (typeof initCartPage === 'function') {
                initCartPage(); // Re-check and display cart or login prompt
            }
        } else if (currentBodyId === 'page-compte') {
            if (typeof displayAccountDashboard === 'function') {
                displayAccountDashboard(); // Re-check and display login form or dashboard
            }
        }
        // Add other pages that need to react dynamically to login/logout here
    });
});
