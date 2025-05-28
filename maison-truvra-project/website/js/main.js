// website/js/main.js
// Main script for initializing the frontend application and page-specific logic.

document.addEventListener('DOMContentLoaded', () => {
    // --- Global Initializations ---
    initializeMobileMenu();     // From ui.js
    initializeNewsletterForm(); // From newsletter.js
    setActiveNavLink();         // From ui.js
    updateLoginState();         // From auth.js
    updateCartCountDisplay();   // From cart.js

    // Display current year in footer
    const currentYearEl = document.getElementById('currentYear');
    if (currentYearEl) {
        currentYearEl.textContent = new Date().getFullYear();
    }

    // --- Page-Specific Initializations ---
    const bodyId = document.body.id;

    if (bodyId === 'page-nos-produits') {
        fetchAndDisplayProducts('all'); // From product.js
        setupCategoryFilters();         // From product.js
    } else if (bodyId === 'page-produit-detail') {
        loadProductDetail();            // From product.js
        // Event listener for add to cart button on product detail page
        const addToCartDetailButton = document.getElementById('add-to-cart-button');
        if (addToCartDetailButton) {
            addToCartDetailButton.addEventListener('click', (event) => {
                event.preventDefault(); // Prevent default if it's a link styled as button
                handleAddToCartFromDetail(); // From cart.js
            });
        }
        // Event listeners for quantity update buttons on product detail page
        const quantityDecreaseButton = document.querySelector('#quantity-select-controls button[onclick*="updateDetailQuantity(-1)"]');
        const quantityIncreaseButton = document.querySelector('#quantity-select-controls button[onclick*="updateDetailQuantity(1)"]');
        if(quantityDecreaseButton) quantityDecreaseButton.addEventListener('click', () => updateDetailQuantity(-1)); // from product.js
        if(quantityIncreaseButton) quantityIncreaseButton.addEventListener('click', () => updateDetailQuantity(1)); // from product.js


    } else if (bodyId === 'page-panier') {
        displayCartItems();             // From cart.js
    } else if (bodyId === 'page-compte') {
        displayAccountDashboard();      // From auth.js
        const loginForm = document.getElementById('login-form');
        if (loginForm) {
            loginForm.addEventListener('submit', handleLogin); // From auth.js
        }
        
        // Placeholder for actual registration form setup
        const createAccountButton = document.querySelector('#login-register-section button[onclick*="inscription"]');
        if(createAccountButton){
            createAccountButton.addEventListener('click', (e) => {
                e.preventDefault();
                // Ideally, this would show a registration form/modal
                showGlobalMessage('Fonctionnalité d\'inscription non implémentée sur cette page. Veuillez contacter l\'administrateur.', 'info');
                // If a registration form with ID 'registration-form' existed:
                // const registrationForm = document.getElementById('registration-form');
                // if (registrationForm) registrationForm.addEventListener('submit', handleRegistrationForm); // from auth.js
            });
        }
    } else if (bodyId === 'page-paiement') { 
        initializeCheckoutPage();       // From checkout.js
    } else if (bodyId === 'page-confirmation-commande') {
        initializeConfirmationPage();   // From checkout.js
    }

    // --- Modal Global Event Listeners ---
    // Close modals when clicking on the overlay
    document.querySelectorAll('.modal-overlay').forEach(modalOverlay => {
        modalOverlay.addEventListener('click', function(event) {
            // Close only if the overlay itself (not its content) is clicked
            if (event.target === modalOverlay) { 
                closeModal(modalOverlay.id); // From ui.js
            }
        });
    });

    // Close modals with dedicated close buttons (if they have a common class e.g., 'modal-close-button')
    document.querySelectorAll('.modal-close-button').forEach(button => {
        button.addEventListener('click', function() {
            const modal = this.closest('.modal-overlay');
            if (modal) {
                closeModal(modal.id); // From ui.js
            }
        });
    });
});


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
        if (typeof updateCartCountDisplay === 'function') {
            updateCartCountDisplay();
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
document.addEventListener('DOMContentLoaded', async () => {
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
        // Assurez-vous que le conteneur des contrôles de quantité a un ID
        const quantityControls = document.getElementById('quantity-select-controls'); 
        if (quantityControls) { // Assumant que vous avez un div parent avec cet ID
            const decreaseButton = quantityControls.querySelector('button:first-child'); // Ou un ID plus spécifique
            const increaseButton = quantityControls.querySelector('button:last-child'); // Ou un ID plus spécifique
            if(decreaseButton && typeof updateDetailQuantity === 'function') decreaseButton.addEventListener('click', () => updateDetailQuantity(-1));
            if(increaseButton && typeof updateDetailQuantity === 'function') increaseButton.addEventListener('click', () => updateDetailQuantity(1));
        }
    } else if (bodyId === 'page-panier') {
        if (typeof displayCartItems === 'function') displayCartItems();
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
});

