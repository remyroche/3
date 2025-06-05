// website/source/js/marchedespros.js
// Manages the B2B "Marché des Professionnels" e-commerce page.

// Ensure global utility functions like t(), showGlobalMessage(), makeApiRequest(),
// getCurrentUser(), isUserLoggedIn(), and potentially B2B cart functions are available.
// (These might be in utils.js, ui.js, auth.js, cart.js or a new b2b_cart.js)

// --- B2B Cart Specific Functions ---
const B2B_CART_STORAGE_KEY = 'maisonTruvraB2BCart';

function getB2BCartItems() {
    try {
        const cartJson = localStorage.getItem(B2B_CART_STORAGE_KEY);
        return cartJson ? JSON.parse(cartJson) : [];
    } catch (e) {
        console.error("Error parsing B2B cart from localStorage:", e);
        return [];
    }
}

function saveB2BCartItems(cartItems) {
    try {
        localStorage.setItem(B2B_CART_STORAGE_KEY, JSON.stringify(cartItems));
    } catch (e) {
        console.error("Error saving B2B cart to localStorage:", e);
        if (typeof showGlobalMessage === 'function') {
            showGlobalMessage(t('b2b_cart.error.saving_cart', 'Erreur sauvegarde panier pro.'), 'error');
        }
    }
}

function addToB2BCart(product, quantityToAdd, variantInfo = null) {
    if (!product || !product.id || typeof quantityToAdd !== 'number' || quantityToAdd <= 0) {
        console.error("Invalid product or quantity for addToB2BCart:", product, quantityToAdd);
        if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.error.invalid_product_data', 'Données produit invalides (B2B).'), 'error');
        return;
    }

    let cart = getB2BCartItems();
    // B2B item ID might need product ID and variant ID if variants have different B2B prices/SKUs
    const cartItemId = variantInfo ? `${product.id}-${variantInfo.option_id}` : product.id.toString();
    const existingItem = cart.find(item => item.id === cartItemId);

    // IMPORTANT: Ensure 'product.b2b_price' or similar is available and used.
    // This price should come from the API, reflecting the current B2B user's tier.
    const itemPrice = variantInfo ? (variantInfo.b2b_price || variantInfo.price) : (product.b2b_price || product.base_price);
    const itemName = product.name_fr || product.name; // Or use getTranslatedText

    // Stock check needs to consider B2B availability if different from B2C
    const availableStock = variantInfo ? (variantInfo.aggregate_stock_quantity || 0) : (product.aggregate_stock_quantity || 0);

    if (availableStock <= 0 && !existingItem) {
        if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.error.item_out_of_stock', '{{itemName}} est épuisé (B2B).', { itemName }), 'error');
        return;
    }

    if (existingItem) {
        const newQuantity = existingItem.quantity + quantityToAdd;
        if (newQuantity > availableStock) {
             if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.error.stock_limit_exceeded_update', 'Stock B2B insuffisant pour {{itemName}}.', { itemName }), 'warning');
            return;
        }
        existingItem.quantity = newQuantity;
    } else {
        if (quantityToAdd > availableStock) {
            if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.error.stock_limit_exceeded_add', 'Stock B2B insuffisant pour {{itemName}}.', { itemName }), 'warning');
            return;
        }
        const cartItem = {
            id: cartItemId,
            productId: product.id,
            name: itemName,
            price: itemPrice, // Store the B2B price
            quantity: quantityToAdd,
            image: product.main_image_full_url || product.main_image_url,
            slug: product.slug, // For linking to B2B detail page
            variantId: variantInfo ? variantInfo.option_id : null,
            variantLabel: variantInfo ? `${variantInfo.weight_grams}g` : null,
            skuSuffix: variantInfo ? variantInfo.sku_suffix : null,
            currentAvailableStock: availableStock
        };
        cart.push(cartItem);
    }
    saveB2BCartItems(cart);
    updateB2BCartDisplay();
    if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.added_success', '{{itemName}} ajouté au panier B2B.', { itemName }), 'success');
}

function updateB2BCartDisplay() {
    const cartItems = getB2BCartItems();
    const cartItemsContainer = document.getElementById('b2b-cart-items-display');
    const cartTotalHTElement = document.getElementById('b2b-cart-total-ht');
    const quoteCartSummaryModal = document.getElementById('quote-cart-summary-modal');


    if (cartItemsContainer) {
        cartItemsContainer.innerHTML = ''; // Clear previous items
        if (cartItems.length === 0) {
            cartItemsContainer.innerHTML = `<p class="text-mt-earth-brown">${t('b2b_shop.cart_empty', 'Votre panier professionnel est vide.')}</p>`;
        } else {
            cartItems.forEach(item => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'b2b-cart-item flex justify-between items-center py-1';
                itemDiv.innerHTML = `
                    <span class="item-name text-sm">${item.name} (x${item.quantity})</span>
                    <span class="item-total font-semibold">€${(item.price * item.quantity).toFixed(2)} HT</span>
                `;
                // Add remove/update quantity controls if needed for cart display
                cartItemsContainer.appendChild(itemDiv);
            });
        }
    }

    if (quoteCartSummaryModal) {
        const summaryContainer = quoteCartSummaryModal.querySelector('div') || quoteCartSummaryModal; // find a div or use the modal itself
        summaryContainer.innerHTML = `<h4 class="font-semibold mb-2">${t('b2b_shop.quote_modal_summary_title', 'Articles dans la demande :')}</h4>`;
        if (cartItems.length === 0) {
            summaryContainer.innerHTML += `<p class="text-xs">${t('b2b_shop.cart_empty', 'Votre panier professionnel est vide.')}</p>`;
        } else {
            const ul = document.createElement('ul');
            ul.className = "list-disc list-inside text-xs space-y-1";
            cartItems.forEach(item => {
                const li = document.createElement('li');
                li.textContent = `${item.name} - Quantité: ${item.quantity} @ €${item.price.toFixed(2)} HT/unité`;
                ul.appendChild(li);
            });
            summaryContainer.appendChild(ul);
        }
    }


    let totalHT = 0;
    cartItems.forEach(item => {
        totalHT += item.price * item.quantity;
    });

    if (cartTotalHTElement) {
        cartTotalHTElement.textContent = `€${totalHT.toFixed(2)}`;
    }
}

function clearB2BCart() {
    localStorage.removeItem(B2B_CART_STORAGE_KEY);
    updateB2BCartDisplay();
}


document.addEventListener('DOMContentLoaded', () => {
    // Page Guard: Ensure user is an authenticated and approved B2B professional
    const currentUser = typeof getCurrentUser === 'function' ? getCurrentUser() : null;
    if (!isUserLoggedIn() || !currentUser || currentUser.role !== 'b2b_professional' || currentUser.professional_status !== 'approved') {
        if (typeof showGlobalMessage === 'function') {
            showGlobalMessage(t('b2b_shop.auth_redirect_message', 'Accès réservé aux professionnels approuvés. Redirection...'), 'error');
        }
        setTimeout(() => {
            window.location.href = 'professionnels.html'; // Redirect to B2B login/info page
        }, 3000);
        return; // Stop further execution
    }

    // Welcome message
    const welcomeElement = document.getElementById('b2b-user-welcome');
    if (welcomeElement && currentUser) {
        // Assuming currentUser has company_name and b2b_tier (e.g., from enhanced /me endpoint or login response)
        const companyName = currentUser.company_name || t('b2b_shop.default_company_name', 'Partenaire Professionnel');
        const userTier = currentUser.b2b_tier || ''; // Fetch or determine B2B tier
        welcomeElement.textContent = t('b2b_shop.welcome_user', 'Bienvenue, {{company}} {{tierMsg}}', {
            company: companyName,
            tierMsg: userTier ? `(Tier: ${userTier})` : ''
        });
    }

    // Initialize UI elements and load data
    loadB2BCategories();
    loadB2BProducts();
    updateB2BCartDisplay(); // Initial cart display

    // --- Event Listeners for Filters and Search ---
    const categoryFilter = document.getElementById('b2b-category-filter');
    const sortByFilter = document.getElementById('b2b-sort-by');
    const searchInput = document.getElementById('b2b-search-products');

    if (categoryFilter) categoryFilter.addEventListener('change', () => loadB2BProducts());
    if (sortByFilter) sortByFilter.addEventListener('change', () => loadB2BProducts());
    if (searchInput) searchInput.addEventListener('input', debounce(() => loadB2BProducts(), 500));


    // --- Event Listeners for Purchasing Options ---
    const checkoutCCBtn = document.getElementById('b2b-checkout-cc-btn');
    const requestQuoteBtn = document.getElementById('b2b-request-quote-btn');
    const poUploadForm = document.getElementById('b2b-po-upload-form');
    const submitPOBtn = document.getElementById('b2b-submit-po-btn'); // If separate from form submit

    if (checkoutCCBtn) {
        checkoutCCBtn.addEventListener('click', handleB2BCheckoutCC);
    }
    if (requestQuoteBtn) {
        requestQuoteBtn.addEventListener('click', openB2BQuoteModal);
    }
    if (poUploadForm) {
        poUploadForm.addEventListener('submit', handleB2BPOUpload);
    } else if (submitPOBtn) { // If button is outside form and handles submission via JS
        submitPOBtn.addEventListener('click', handleB2BPOUpload);
    }

    // Quote Modal Listeners
    const closeQuoteModalBtn = document.getElementById('close-b2b-quote-modal');
    const cancelQuoteModalBtn = document.getElementById('cancel-b2b-quote-request-btn');
    const quoteRequestForm = document.getElementById('b2b-quote-request-form');

    if (closeQuoteModalBtn) closeQuoteModalBtn.addEventListener('click', () => closeAdminModal('b2b-quote-modal')); // Re-use admin_ui.js
    if (cancelQuoteModalBtn) cancelQuoteModalBtn.addEventListener('click', () => closeAdminModal('b2b-quote-modal'));
    if (quoteRequestForm) quoteRequestForm.addEventListener('submit', handleB2BQuoteSubmit);
});

async function loadB2BCategories() {
    const categoryFilterSelect = document.getElementById('b2b-category-filter');
    if (!categoryFilterSelect) return;

    try {
        // API endpoint might need adjustment to fetch categories relevant for B2B
        const response = await makeApiRequest('/api/products/categories?segment=b2b'); // Or similar
        if (response.success && response.categories) {
            categoryFilterSelect.innerHTML = `<option value="">${t('b2b_shop.all_categories', 'Toutes les catégories')}</option>`;
            response.categories.forEach(category => {
                if (category.is_active) { // Only show active categories
                    const option = document.createElement('option');
                    option.value = category.slug; // Or category.id if API expects ID
                    option.textContent = category.name_fr || category.name; // Or use getTranslatedText
                    categoryFilterSelect.appendChild(option);
                }
            });
        }
    } catch (error) {
        console.error("Failed to load B2B categories:", error);
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_shop.error.load_categories', 'Erreur chargement catégories B2B.'), 'error');
    }
}

async function loadB2BProducts(page = 1) {
    const productListContainer = document.getElementById('b2b-product-list-container');
    const loadingIndicator = document.getElementById('b2b-loading-indicator');
    const noProductsMessage = document.getElementById('b2b-no-products-message');
    const paginationContainer = document.getElementById('b2b-pagination-container');

    if (!productListContainer || !loadingIndicator || !noProductsMessage || !paginationContainer) return;

    loadingIndicator.classList.remove('hidden');
    noProductsMessage.classList.add('hidden');
    productListContainer.innerHTML = ''; // Clear previous products

    const category = document.getElementById('b2b-category-filter')?.value;
    const sortBy = document.getElementById('b2b-sort-by')?.value;
    const searchTerm = document.getElementById('b2b-search-products')?.value;

    try {
        // API endpoint must be B2B specific or accept parameters to return B2B data
        let apiUrl = `/api/products/b2b?page=${page}&limit=12`; // Example
        if (category) apiUrl += `&category_slug=${category}`;
        if (sortBy) apiUrl += `&sort=${sortBy}`;
        if (searchTerm) apiUrl += `&search=${encodeURIComponent(searchTerm)}`;

        const response = await makeApiRequest(apiUrl); // Assumes API handles B2B user context for pricing

        if (response.success && response.products) {
            if (response.products.length === 0) {
                noProductsMessage.classList.remove('hidden');
            } else {
                response.products.forEach(product => {
                    productListContainer.appendChild(createB2BProductCard(product));
                });
            }
            // renderB2BPagination(paginationContainer, response.current_page, response.total_pages);
        } else {
            noProductsMessage.classList.remove('hidden');
            if(typeof showGlobalMessage === 'function') showGlobalMessage(response.message || t('b2b_shop.error.load_products', 'Erreur chargement produits B2B.'), 'error');
        }
    } catch (error) {
        console.error("Error fetching B2B products:", error);
        noProductsMessage.classList.remove('hidden');
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_shop.error.load_products_network', 'Erreur réseau chargement produits B2B.'), 'error');
    } finally {
        loadingIndicator.classList.add('hidden');
    }
}

function createB2BProductCard(product) {
    const card = document.createElement('div');
    // Using general product-card styles, but can add b2b-product-card for overrides
    card.className = 'product-card b2b-product-card bg-white rounded-lg shadow-lg overflow-hidden transition-all duration-300 ease-in-out hover:shadow-xl relative flex flex-col';

    const productName = product.name_fr || product.name; // Or use getTranslatedText
    const productSlug = product.slug || generateSlug(productName); // generateSlug from utils.js
    const b2bPrice = product.b2b_price !== undefined ? product.b2b_price : (product.base_price || 0); // Crucial: API must provide this
    const retailPrice = product.retail_price || product.base_price; // Example if API sends it

    card.innerHTML = `
        <a href="produit-detail-pro.html?slug=${productSlug}" class="block group">
            <div class="aspect-square overflow-hidden">
                <img src="${product.main_image_full_url || product.main_image_url || 'https://placehold.co/300x300/F5EEDE/11120D?text=Maison+Trüvra'}" 
                     alt="${t('product.image_alt', 'Image de {{productName}}', { productName: productName })}" 
                     class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300 ease-in-out">
            </div>
        </a>
        <div class="p-4 flex flex-col flex-grow">
            <h3 class="card-title text-lg font-semibold font-serif text-mt-near-black mb-1 truncate" title="${productName}">
                <a href="produit-detail-pro.html?slug=${productSlug}" class="hover:text-mt-truffle-burgundy">${productName}</a>
            </h3>
            <p class="text-xs text-mt-warm-taupe mb-2 truncate">${product.category_name || t('product.no_category', 'Non catégorisé')}</p>
            
            <div class="b2b-pricing-info my-2">
                <p class="text-sm text-mt-earth-brown">${t('b2b_shop.your_price_label', 'Votre Prix:')} <span class="font-bold text-lg text-mt-truffle-burgundy">€${parseFloat(b2bPrice).toFixed(2)}</span> HT</p>
                ${retailPrice && retailPrice > b2bPrice ? `<p class="text-xs text-mt-warm-taupe">${t('b2b_shop.rrp_label', 'Prix Public Conseillé:')} <del>€${parseFloat(retailPrice).toFixed(2)}</del></p>` : ''}
            </div>

            <p class="text-sm text-mt-earth-brown mb-3 text-ellipsis overflow-hidden line-clamp-2" style="min-height: 2.5em;">
                ${product.description_fr || product.description || t('product.default_description_short', 'Découvrez ce produit exceptionnel.')}
            </p>
            <div class="mt-auto space-y-2">
                <a href="produit-detail-pro.html?slug=${productSlug}" class="btn btn-outline w-full">${t('b2b_shop.view_details_btn', 'Voir Détails & Options')}</a>
                <button class="btn btn-primary w-full add-to-b2b-cart-btn" data-product-id="${product.id}" data-product-name="${productName}" data-product-price="${b2bPrice}" data-product-image="${product.main_image_full_url || product.main_image_url}" data-product-slug="${productSlug}">
                    <i class="fas fa-plus-circle mr-2"></i>${t('b2b_shop.add_to_cart_quote_btn', 'Ajouter au Panier/Devis')}
                </button>
            </div>
        </div>
    `;

    const addToCartBtn = card.querySelector('.add-to-b2b-cart-btn');
    addToCartBtn.addEventListener('click', (e) => {
        // Create a simplified product object for the cart from data attributes
        const productForCart = {
            id: e.currentTarget.dataset.productId,
            name_fr: e.currentTarget.dataset.productName,
            b2b_price: parseFloat(e.currentTarget.dataset.productPrice),
            main_image_full_url: e.currentTarget.dataset.productImage,
            slug: e.currentTarget.dataset.productSlug,
            // Add other necessary fields like aggregate_stock_quantity if it's part of product object
            aggregate_stock_quantity: product.aggregate_stock_quantity 
        };
        // If product has variants, this should ideally navigate to detail page or open a variant selector
        if (product.type === 'variable_weight' && (!product.weight_options || product.weight_options.length > 0)) {
            window.location.href = `produit-detail-pro.html?slug=${productSlug}`;
        } else {
            addToB2BCart(productForCart, 1);
        }
    });
    return card;
}

function debounce(func, delay) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), delay);
    };
}

// --- Purchasing Option Handlers ---
function handleB2BCheckoutCC() {
    const cartItems = getB2BCartItems();
    if (cartItems.length === 0) {
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.empty_for_checkout', 'Votre panier B2B est vide pour le paiement.'), 'warning');
        return;
    }
    // Store B2B cart in a way payment-pro.html can access it
    // localStorage.setItem('checkoutB2BCart', JSON.stringify(cartItems));
    // Navigate to a B2B specific payment page
    window.location.href = 'payment-pro.html'; // Create this page, similar to payment.html
                                            // but it needs to fetch 'checkoutB2BCart'
                                            // and ensure backend create order uses B2B context
}

function openB2BQuoteModal() {
    const cartItems = getB2BCartItems();
    if (cartItems.length === 0) {
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.empty_for_quote', 'Votre panier B2B est vide pour une demande de devis.'), 'warning');
        return;
    }
    updateB2BCartDisplay(); // Ensure modal summary is up-to-date
    if (typeof openAdminModal === 'function') { // Re-use from admin_ui.js
        openAdminModal('b2b-quote-modal');
    } else {
        console.error("openAdminModal function not found.");
    }
}

async function handleB2BQuoteSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const notes = form.querySelector('#quote-notes').value;
    const contactPerson = form.querySelector('#quote-contact-person').value;
    const contactPhone = form.querySelector('#quote-contact-phone').value;
    const cartItems = getB2BCartItems();

    if (cartItems.length === 0) {
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.empty_for_quote_submit', 'Impossible de soumettre un devis vide.'), 'error');
        return;
    }

    const quoteData = {
        items: cartItems.map(item => ({
            product_id: item.productId, // Ensure these keys match backend expectations
            variant_id: item.variantId,
            quantity: item.quantity,
            price_at_request: item.price // The B2B price when added to cart
        })),
        notes: notes,
        contact_person: contactPerson,
        contact_phone: contactPhone
    };

    const submitButton = form.querySelector('#submit-b2b-quote-request-btn');
    submitButton.disabled = true;
    submitButton.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('common.sending', 'Envoi...')}`;

    try {
        const response = await makeApiRequest('/api/b2b/quote-requests', 'POST', quoteData, true); // true for auth
        if (response.success) {
            if(typeof showGlobalMessage === 'function') showGlobalMessage(response.message || t('b2b_quote.request_success', 'Demande de devis envoyée avec succès !'), 'success');
            clearB2BCart();
            closeAdminModal('b2b-quote-modal'); // Re-use from admin_ui.js
            form.reset();
        } else {
            if(typeof showGlobalMessage === 'function') showGlobalMessage(response.message || t('b2b_quote.request_failed', 'Échec envoi demande de devis.'), 'error');
        }
    } catch (error) {
        console.error("Quote request submission error:", error);
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('common.error_network', 'Erreur réseau lors de la demande de devis.'), 'error');
    } finally {
        submitButton.disabled = false;
        submitButton.innerHTML = t('b2b_shop.quote_modal_submit_btn', 'Envoyer la Demande de Devis');
    }
}

async function handleB2BPOUpload(event) {
    event.preventDefault(); // If called from form submit
    const poFileElement = document.getElementById('b2b-po-file');
    const poFile = poFileElement?.files[0];
    const cartItems = getB2BCartItems();

    if (!poFile) {
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_po.no_file_selected', 'Veuillez sélectionner un fichier de bon de commande.'), 'warning');
        return;
    }
    if (cartItems.length === 0) {
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_po.cart_empty_for_po', 'Votre panier est vide. Ajoutez des articles avant de soumettre un PO.'), 'warning');
        return;
    }

    const formData = new FormData();
    formData.append('purchase_order_file', poFile);
    formData.append('cart_items', JSON.stringify(cartItems.map(item => ({
        product_id: item.productId,
        variant_id: item.variantId,
        quantity: item.quantity,
        price_at_request: item.price
    }))));
    
    // Add other relevant data if needed by backend, e.g., user_id is handled by JWT

    const submitButton = document.getElementById('b2b-submit-po-btn'); // Assuming this is the button for direct click or form
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('common.uploading', 'Téléchargement...')}`;
    }


    try {
        const response = await makeApiRequest('/api/b2b/purchase-orders', 'POST', formData, true, true); // true for auth, true for FormData
        if (response.success) {
            if(typeof showGlobalMessage === 'function') showGlobalMessage(response.message || t('b2b_po.upload_success', 'Bon de commande soumis avec succès !'), 'success');
            clearB2BCart();
            if (poFileElement) poFileElement.value = ''; // Reset file input
            if (document.getElementById('b2b-po-upload-form')) document.getElementById('b2b-po-upload-form').reset();

        } else {
            if(typeof showGlobalMessage === 'function') showGlobalMessage(response.message || t('b2b_po.upload_failed', 'Échec soumission Bon de Commande.'), 'error');
        }
    } catch (error) {
        console.error("PO submission error:", error);
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('common.error_network', 'Erreur réseau - soumission PO.'), 'error');
    } finally {
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.innerHTML = t('b2b_shop.option_po_btn', 'Soumettre le Bon de Commande');
        }
    }
}

// Add missing translation keys to fr.json and en.json:
// "b2b_cart.error.saving_cart", "b2b_cart.error.invalid_product_data", "b2b_cart.error.item_out_of_stock",
// "b2b_cart.error.stock_limit_exceeded_update", "b2b_cart.error.stock_limit_exceeded_add", "b2b_cart.added_success",
// "b2b_shop.auth_redirect_message", "b2b_shop.default_company_name", "b2b_shop.welcome_user",
// "b2b_shop.error.load_categories", "b2b_shop.error.load_products", "b2b_shop.error.load_products_network",
// "b2b_shop.your_price_label", "b2b_shop.rrp_label", "b2b_shop.view_details_btn", "b2b_shop.add_to_cart_quote_btn",
// "b2b_cart.empty_for_checkout", "b2b_cart.empty_for_quote", "b2b_cart.empty_for_quote_submit",
// "common.sending", "b2b_quote.request_success", "b2b_quote.request_failed", "common.error_network",
// "b2b_po.no_file_selected", "b2b_po.cart_empty_for_po", "common.uploading", "b2b_po.upload_success", "b2b_po.upload_failed"
