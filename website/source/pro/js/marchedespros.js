<script>
document.addEventListener('DOMContentLoaded', function() {
    const productsContainer = document.getElementById('products-container');
    const token = localStorage.getItem('proToken');

    if (!token) {
        window.location.href = 'professionnels.html';
        return;
    }

    fetch('/api/products', { // Assuming a generic products API for now
        headers: {
            'Authorization': `Bearer ${token}`
        }
    })
    .then(response => response.json())
    .then(products => {
        products.forEach(product => {
            const productCard = `
                <div class="bg-white rounded-lg shadow-md p-4 flex flex-col">
                    <img src="${product.image_url || '../assets/images/placeholder.png'}" alt="${product.name}" class="rounded-md mb-4 h-48 w-full object-cover">
                    <h3 class="text-lg font-bold mb-2">${product.name}</h3>
                    <p class="text-gray-600 mb-4">${product.description}</p>
                    <div class="mt-auto flex justify-between items-center">
                        <span class="text-xl font-bold">${product.price} €</span>
                        <button class="bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 add-to-cart-pro" data-product-id="${product.id}">
                            ${window.i18n.add_to_cart}
                        </button>
                    </div>
                </div>
            `;
            productsContainer.innerHTML += productCard;
        });
    })
    .catch(error => {
        console.error('Error fetching products:', error);
        productsContainer.innerHTML = '<p>Error loading products.</p>';
    });
});
</script>


// --- B2B Cart Specific Functions ---
const B2B_CART_STORAGE_KEY = 'maisonTruvraB2BCart';
let currentB2BProductsCache = []; // Cache for currently displayed products with B2B pricing
let b2bUserTier = null; // To store the logged-in B2B user's tier


document.addEventListener('DOMContentLoaded', () => {
    loadDashboardInfo();
    loadQuotes();
    loadOrders();
    // Invoices are on a separate page, so no need to load them here.
});

async function loadDashboardInfo() {
    const token = localStorage.getItem('token');
    try {
        const response = await fetch('/pro/dashboard_info', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error('Failed to fetch dashboard info');
        
        const data = await response.json();
        
        document.getElementById('partnership-level').textContent = data.partnership_level || 'Bronze';
        document.getElementById('partnership-discount').textContent = `Remise de ${data.discount_percent || 0}%`;
        document.getElementById('annual-spend').textContent = `${(data.annual_spend || 0).toFixed(2)} €`;
        document.getElementById('referral-credit').textContent = `${(data.referral_credit_balance || 0).toFixed(2)} €`;

    } catch (error) {
        console.error('Error loading dashboard info:', error);
    }
}

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
            showGlobalMessage(t('b2b_cart.error.saving_cart', 'Erreur lors de la sauvegarde du panier professionnel.'), 'error');
        }
    }
}

function addToB2BCart(productData, quantityToAdd) {
    // productData should be an object containing at least:
    // id, name_fr, b2b_price, main_image_full_url, slug, aggregate_stock_quantity
    // and if it's a variant, variantId, variantLabel, skuSuffix
    if (!productData || !productData.id || typeof quantityToAdd !== 'number' || quantityToAdd <= 0) {
        console.error("Invalid product data or quantity for addToB2BCart:", productData, quantityToAdd);
        if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.error.invalid_product_data', 'Données produit invalides pour ajout au panier B2B.'), 'error');
        return;
    }

    let cart = getB2BCartItems();
    const cartItemId = productData.variantId ? `${productData.id}-${productData.variantId}` : productData.id.toString();
    const existingItemIndex = cart.findIndex(item => item.id === cartItemId);

    const itemName = productData.name_fr || productData.name || t('b2b_cart.default_item_name', 'Article B2B');
    const itemPrice = parseFloat(productData.b2b_price); // This IS THE B2B PRICE from API
    const availableStock = parseInt(productData.aggregate_stock_quantity || 0);

    if (isNaN(itemPrice)) {
        if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.error.invalid_price', `Prix invalide pour ${itemName}.`), 'error');
        return;
    }

    if (existingItemIndex > -1) {
        const newQuantity = cart[existingItemIndex].quantity + quantityToAdd;
        if (newQuantity > availableStock) {
            if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.error.stock_limit_exceeded_update', `Stock B2B insuffisant pour ${itemName}. Max: ${availableStock}`), 'warning');
            return;
        }
        cart[existingItemIndex].quantity = newQuantity;
    } else {
        if (quantityToAdd > availableStock) {
            if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.error.stock_limit_exceeded_add', `Stock B2B insuffisant pour ${itemName}. Max: ${availableStock}`), 'warning');
            return;
        }
        const cartItem = {
            id: cartItemId,
            productId: productData.id, // Original product ID
            name: itemName,
            price: itemPrice, // B2B specific price
            quantity: quantityToAdd,
            image: productData.main_image_full_url || productData.main_image_url || 'https://placehold.co/100x100/F5EEDE/11120D?text=Pro',
            slug: productData.slug, // For linking to B2B detail page
            variantId: productData.variantId || null,
            variantLabel: productData.variantLabel || null,
            skuSuffix: productData.skuSuffix || null,
            currentAvailableStock: availableStock,
            // Store any other B2B specific details needed for order/quote if API provides them
            product_code: productData.product_code
        };
        cart.push(cartItem);
    }
    saveB2BCartItems(cart);
    updateB2BCartDisplay();
    if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.added_success', `{{itemName}} ajouté au panier B2B.`, { itemName: itemName }), 'success');
}


function updateB2BCartItemQuantity(cartItemId, newQuantity) {
    let cart = getB2BCartItems();
    const itemIndex = cart.findIndex(item => item.id === cartItemId);

    if (itemIndex > -1) {
        if (isNaN(newQuantity) || newQuantity <= 0) {
            cart.splice(itemIndex, 1); // Remove item if quantity is invalid or zero
            if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.item_removed', 'Article retiré du panier B2B.'), 'info');
        } else {
            const item = cart[itemIndex];
            if (newQuantity > item.currentAvailableStock) {
                if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.error.stock_limit_exceeded_update', `Stock B2B insuffisant pour ${item.name}. Max: ${item.currentAvailableStock}`), 'warning');
                cart[itemIndex].quantity = item.currentAvailableStock; // Adjust to max available
            } else {
                cart[itemIndex].quantity = newQuantity;
            }
        }
        saveB2BCartItems(cart);
        updateB2BCartDisplay();
    }
}

function removeB2BCartItem(cartItemId) {
    let cart = getB2BCartItems();
    const itemName = cart.find(item => item.id === cartItemId)?.name || t('b2b_cart.an_item', 'Un article');
    cart = cart.filter(item => item.id !== cartItemId);
    saveB2BCartItems(cart);
    updateB2BCartDisplay();
    if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.item_removed_specific', `{{itemName}} retiré du panier B2B.`, { itemName: itemName }), 'info');
}

function updateB2BCartDisplay() {
    const cartItems = getB2BCartItems();
    const cartItemsContainer = document.getElementById('b2b-cart-items-display');
    const cartTotalHTElement = document.getElementById('b2b-cart-total-ht');
    const quoteCartSummaryModalDiv = document.getElementById('quote-cart-summary-modal'); // The div inside the modal

    if (cartItemsContainer) {
        cartItemsContainer.innerHTML = '';
        if (cartItems.length === 0) {
            cartItemsContainer.innerHTML = `<p class="text-mt-earth-brown text-sm italic">${t('b2b_shop.cart_empty', 'Votre panier professionnel est vide.')}</p>`;
        } else {
            cartItems.forEach(item => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'b2b-cart-item flex justify-between items-center py-2 border-b border-mt-cream-dark last:border-b-0';
                itemDiv.innerHTML = `
                    <div class="flex-grow pr-2">
                        <p class="item-name text-sm font-medium text-mt-near-black truncate" title="${item.name}">${item.name} ${item.variantLabel ? `(${item.variantLabel})` : ''}</p>
                        <p class="text-xs text-mt-earth-brown">€${item.price.toFixed(2)} HT/unité</p>
                    </div>
                    <div class="flex items-center">
                        <input type="number" value="${item.quantity}" min="1" max="${item.currentAvailableStock}" 
                               class="b2b-cart-item-qty-input w-16 text-sm p-1 border border-mt-warm-taupe rounded-md text-center mr-2" 
                               data-item-id="${item.id}">
                        <span class="item-total font-semibold text-sm text-mt-near-black w-20 text-right">€${(item.price * item.quantity).toFixed(2)}</span>
                        <button class="remove-b2b-item-btn text-mt-truffle-burgundy hover:text-red-700 ml-2 text-xs" data-item-id="${item.id}" aria-label="Remove item">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                `;
                cartItemsContainer.appendChild(itemDiv);
            });
            // Add listeners for new quantity inputs and remove buttons
            cartItemsContainer.querySelectorAll('.b2b-cart-item-qty-input').forEach(input => {
                input.addEventListener('change', (e) => updateB2BCartItemQuantity(e.target.dataset.itemId, parseInt(e.target.value)));
            });
            cartItemsContainer.querySelectorAll('.remove-b2b-item-btn').forEach(button => {
                button.addEventListener('click', (e) => removeB2BCartItem(e.currentTarget.dataset.itemId));
            });
        }
    }

    if (quoteCartSummaryModalDiv) {
        quoteCartSummaryModalDiv.innerHTML = `<h4 class="font-semibold mb-2 text-mt-near-black">${t('b2b_shop.quote_modal_summary_title', 'Articles dans la demande :')}</h4>`;
        if (cartItems.length === 0) {
            quoteCartSummaryModalDiv.innerHTML += `<p class="text-xs text-mt-earth-brown italic">${t('b2b_shop.cart_empty', 'Votre panier professionnel est vide.')}</p>`;
        } else {
            const ul = document.createElement('ul');
            ul.className = "list-disc list-inside text-xs space-y-1 text-mt-earth-brown";
            cartItems.forEach(item => {
                const li = document.createElement('li');
                li.textContent = `${item.name} ${item.variantLabel ? `(${item.variantLabel})` : ''} - Quantité: ${item.quantity} @ €${item.price.toFixed(2)} HT/unité`;
                ul.appendChild(li);
            });
            quoteCartSummaryModalDiv.appendChild(ul);
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
    if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.cleared', 'Panier B2B vidé.'), 'info');
}

// --- Page Initialization and Core Logic ---
document.addEventListener('DOMContentLoaded', async () => {
    if (document.body.id !== 'page-marche-des-pros' && document.body.id !== 'page-produit-detail-pro') {
        return; // Only run on B2B shop or B2B product detail pages
    }

    const currentUser = typeof getCurrentUser === 'function' ? getCurrentUser() : null;
    if (!isUserLoggedIn() || !currentUser || currentUser.role !== 'b2b_professional' || currentUser.professional_status !== 'approved') {
        if (typeof showGlobalMessage === 'function') {
            showGlobalMessage(t('b2b_shop.auth_redirect_message', 'Accès réservé aux professionnels approuvés. Redirection...'), 'error');
        }
        setTimeout(() => { window.location.href = 'professionnels.html'; }, 3000);
        return;
    }
    b2bUserTier = currentUser.b2b_tier; // Store user's tier

    const welcomeElement = document.getElementById('b2b-user-welcome');
    if (welcomeElement && currentUser) {
        const companyName = currentUser.company_name || t('b2b_shop.default_company_name', 'Partenaire Professionnel');
        const tierDisplay = b2bUserTier ? t(`b2b_tier.${b2bUserTier}`, b2bUserTier.charAt(0).toUpperCase() + b2bUserTier.slice(1)) : '';
        welcomeElement.textContent = t('b2b_shop.welcome_user', `Bienvenue, {{company}} {{tierMsg}}`, {
            company: companyName,
            tierMsg: tierDisplay ? `(Tier: ${tierDisplay})` : ''
        });
    }

    if (document.body.id === 'page-marche-des-pros') {
        await loadB2BCategories();
        await loadB2BProducts();
        updateB2BCartDisplay();

        const categoryFilter = document.getElementById('b2b-category-filter');
        const sortByFilter = document.getElementById('b2b-sort-by');
        const searchInput = document.getElementById('b2b-search-products');

        if (categoryFilter) categoryFilter.addEventListener('change', () => loadB2BProducts());
        if (sortByFilter) sortByFilter.addEventListener('change', () => loadB2BProducts());
        if (searchInput) searchInput.addEventListener('input', debounce(() => loadB2BProducts(), 500));

        const checkoutCCBtn = document.getElementById('b2b-checkout-cc-btn');
        const requestQuoteBtn = document.getElementById('b2b-request-quote-btn');
        const poUploadForm = document.getElementById('b2b-po-upload-form');

        if (checkoutCCBtn) checkoutCCBtn.addEventListener('click', handleB2BCheckoutCC);
        if (requestQuoteBtn) requestQuoteBtn.addEventListener('click', openB2BQuoteModal);
        if (poUploadForm) poUploadForm.addEventListener('submit', handleB2BPOUpload);

        const closeQuoteModalBtn = document.getElementById('close-b2b-quote-modal');
        const cancelQuoteModalBtn = document.getElementById('cancel-b2b-quote-request-btn');
        const quoteRequestForm = document.getElementById('b2b-quote-request-form');

        if (closeQuoteModalBtn) closeQuoteModalBtn.addEventListener('click', () => closeAdminModal('b2b-quote-modal'));
        if (cancelQuoteModalBtn) cancelQuoteModalBtn.addEventListener('click', () => closeAdminModal('b2b-quote-modal'));
        if (quoteRequestForm) quoteRequestForm.addEventListener('submit', handleB2BQuoteSubmit);
    }

    if (document.body.id === 'page-produit-detail-pro') {
        await loadB2BProductDetail();
         updateB2BCartDisplay(); // Also update if there's a mini-cart component shared
    }
});

async function loadB2BCategories() {
    const categoryFilterSelect = document.getElementById('b2b-category-filter');
    if (!categoryFilterSelect) return;
    try {
        const response = await makeApiRequest('/api/products/categories?segment=b2b'); // Assuming API can filter for B2B categories
        if (response.success && response.categories) {
            categoryFilterSelect.innerHTML = `<option value="">${t('b2b_shop.all_categories', 'Toutes les catégories')}</option>`;
            response.categories.forEach(category => {
                if (category.is_active) {
                    const option = document.createElement('option');
                    option.value = category.slug;
                    option.textContent = category.name_fr || category.name;
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

    if (!productListContainer || !loadingIndicator || !noProductsMessage || !paginationContainer) {
         console.warn("One or more B2B product display elements are missing.");
        return;
    }

    loadingIndicator.classList.remove('hidden');
    noProductsMessage.classList.add('hidden');
    productListContainer.innerHTML = '';

    const category = document.getElementById('b2b-category-filter')?.value;
    const sortBy = document.getElementById('b2b-sort-by')?.value;
    const searchTerm = document.getElementById('b2b-search-products')?.value;

    try {
        let apiUrl = `/api/b2b/products?page=${page}&limit=12`; // Use the new B2B products endpoint
        if (category) apiUrl += `&category_slug=${category}`;
        if (sortBy) apiUrl += `&sort=${sortBy}`;
        if (searchTerm) apiUrl += `&search=${encodeURIComponent(searchTerm)}`;

        const response = await makeApiRequest(apiUrl, 'GET', null, true); // true for auth

        if (response.success && response.products) {
            currentB2BProductsCache = response.products; // Cache for adding to cart
            if (response.products.length === 0) {
                noProductsMessage.classList.remove('hidden');
            } else {
                response.products.forEach(product => {
                    productListContainer.appendChild(createB2BProductCard(product));
                });
            }
            if (typeof renderPagination === 'function' && response.pagination) { // General pagination renderer
                 renderPagination(paginationContainer, response.pagination, (newPage) => loadB2BProducts(newPage));
            } else if (paginationContainer) {
                paginationContainer.innerHTML = ''; // Clear if no pagination data or renderer
            }
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
    card.className = 'product-card b2b-product-card bg-white rounded-lg shadow-lg overflow-hidden transition-all duration-300 ease-in-out hover:shadow-xl relative flex flex-col';

    const productName = product.name_fr || product.name;
    const productSlug = product.slug || (typeof generateSlug === 'function' ? generateSlug(productName) : productName.toLowerCase().replace(/\s+/g, '-'));
    
    // product.b2b_price is THE price for this user's tier for this product/base variant
    // product.retail_price is the B2C price for comparison
    const displayB2BPrice = product.b2b_price !== null && product.b2b_price !== undefined ? parseFloat(product.b2b_price) : null;
    const displayRetailPrice = product.retail_price !== null && product.retail_price !== undefined ? parseFloat(product.retail_price) : null;
    const stockQuantity = product.aggregate_stock_quantity || 0;

    let priceHTML = '';
    if (displayB2BPrice !== null) {
        priceHTML = `<p class="text-sm text-mt-earth-brown">${t('b2b_shop.your_price_label', 'Votre Prix:')} <span class="font-bold text-lg text-mt-truffle-burgundy">€${displayB2BPrice.toFixed(2)}</span> HT</p>`;
        if (displayRetailPrice !== null && displayRetailPrice > displayB2BPrice) {
            priceHTML += `<p class="text-xs text-mt-warm-taupe">${t('b2b_shop.rrp_label', 'Prix Public Conseillé:')} <del>€${displayRetailPrice.toFixed(2)}</del></p>`;
        }
    } else {
        priceHTML = `<p class="text-lg font-bold text-mt-truffle-burgundy">${t('b2b_shop.price_on_request_or_options', 'Voir options/Devis')}</p>`;
    }


    card.innerHTML = `
        <a href="produit-detail-pro.html?slug=${productSlug}" class="block group">
            <div class="aspect-square overflow-hidden bg-mt-cream-light">
                <img src="${product.main_image_full_url || 'https://placehold.co/300x300/F5EEDE/7D6A4F?text=Image+Produit'}" 
                     alt="${t('product.image_alt', 'Image de {{productName}}', { productName: productName })}" 
                     class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300 ease-in-out"
                     onerror="this.onerror=null;this.src='https://placehold.co/300x300/F5EEDE/7D6A4F?text=Image+Indisponible';">
            </div>
        </a>
        <div class="p-4 flex flex-col flex-grow">
            <h3 class="card-title text-lg font-semibold font-serif text-mt-near-black mb-1 truncate" title="${productName}">
                <a href="produit-detail-pro.html?slug=${productSlug}" class="hover:text-mt-truffle-burgundy">${productName}</a>
            </h3>
            <p class="text-xs text-mt-warm-taupe mb-2 truncate">${product.category_name || t('product.no_category', 'Non catégorisé')}</p>
            <div class="b2b-pricing-info my-2">${priceHTML}</div>
            <p class="text-sm text-mt-earth-brown mb-3 text-ellipsis overflow-hidden line-clamp-2" style="min-height: 2.5em;">
                ${product.description_fr || product.description || t('product.default_description_short', 'Découvrez ce produit exceptionnel.')}
            </p>
            <div class="mt-auto space-y-2">
                <a href="produit-detail-pro.html?slug=${productSlug}" class="btn btn-outline w-full text-sm py-2">${t('b2b_shop.view_details_btn', 'Voir Détails & Options')}</a>
                ${ (product.type !== 'variable_weight' || (product.weight_options_b2b && product.weight_options_b2b.length === 0) ) && stockQuantity > 0 && displayB2BPrice !== null ? `
                    <button class="btn btn-primary w-full add-to-b2b-cart-btn text-sm py-2" data-product-id="${product.id}">
                        <i class="fas fa-plus-circle mr-2"></i>${t('b2b_shop.add_to_cart_quote_btn', 'Ajouter au Panier/Devis')}
                    </button>
                ` : (stockQuantity <= 0 ? `<button class="btn btn-disabled w-full text-sm py-2" disabled>${t('product.out_of_stock', 'Épuisé')}</button>` : '')}
            </div>
        </div>
    `;

    const addToCartBtn = card.querySelector('.add-to-b2b-cart-btn');
    if (addToCartBtn) {
        addToCartBtn.addEventListener('click', (e) => {
            const clickedProductId = e.currentTarget.dataset.productId;
            const productToAdd = currentB2BProductsCache.find(p => p.id.toString() === clickedProductId);
            if (productToAdd) {
                // For simple products, add directly. For variable, this button implies a default variant or should not be shown without selection.
                // The condition above for rendering this button already checks if it's NOT variable OR has no options.
                addToB2BCart(productToAdd, 1); // Add 1 unit by default
            } else {
                console.error("Product not found in cache for cart addition:", clickedProductId);
                if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.error.product_not_in_cache', 'Erreur: produit non trouvé pour ajout.'), 'error');
            }
        });
    }
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
    localStorage.setItem('maisonTruvraCheckoutType', 'b2b_cc'); // Flag for payment page
    localStorage.setItem('maisonTruvraCartForCheckout', JSON.stringify(cartItems)); // Pass current B2B cart
    window.location.href = 'payment-pro.html'; // Navigate to B2B payment page
}

function openB2BQuoteModal() {
    const cartItems = getB2BCartItems();
    if (cartItems.length === 0) {
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_cart.empty_for_quote', 'Votre panier B2B est vide pour une demande de devis.'), 'warning');
        return;
    }
    updateB2BCartDisplay(); // Ensure modal summary is up-to-date
    if (typeof openAdminModal === 'function') {
        openAdminModal('b2b-quote-modal');
    } else {
        console.error("openAdminModal function not found (needed for B2B Quote Modal).");
        alert(t('b2b_cart.error.modal_function_missing', 'Erreur: Impossible d\'ouvrir le formulaire de devis.'));
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
            product_id: item.productId,
            variant_id: item.variantId,
            quantity: item.quantity,
            price_at_request: item.price // The B2B price when item was added to cart
        })),
        notes: notes,
        contact_person: contactPerson,
        contact_phone: contactPhone
    };

    const submitButton = form.querySelector('#submit-b2b-quote-request-btn');
    const originalButtonText = submitButton.innerHTML;
    submitButton.disabled = true;
    submitButton.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> ${t('common.sending', 'Envoi...')}`;

    try {
        const response = await makeApiRequest('/api/b2b/quote-requests', 'POST', quoteData, true); // true for auth
        if (response.success) {
            if(typeof showGlobalMessage === 'function') showGlobalMessage(response.message || t('b2b_quote.request_success', 'Demande de devis envoyée avec succès ! Notre équipe vous contactera.'), 'success', 7000);
            clearB2BCart();
            if (typeof closeAdminModal === 'function') closeAdminModal('b2b-quote-modal');
            form.reset();
        } else {
            if(typeof showGlobalMessage === 'function') showGlobalMessage(response.message || t('b2b_quote.request_failed', 'Échec de l\'envoi de la demande de devis.'), 'error');
        }
    } catch (error) {
        console.error("Quote request submission error:", error);
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('common.error_network', 'Erreur réseau lors de l\'envoi de la demande de devis.'), 'error');
    } finally {
        submitButton.disabled = false;
        submitButton.innerHTML = originalButtonText;
    }
}

async function handleB2BPOUpload(event) {
    event.preventDefault();
    const poForm = event.target.closest('form') || document.getElementById('b2b-po-upload-form'); // Get form
    const poFileElement = poForm.querySelector('#b2b-po-file');
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
        price_at_request: item.price, // B2B price at time of cart add
        product_code: item.product_code, // Send product code for easier admin matching
        sku_suffix: item.skuSuffix
    }))));
    
    const poNumberFromClient = prompt(t('b2b_po.prompt_po_number', 'Veuillez entrer votre numéro de Bon de Commande (optionnel) :'), '');
    if(poNumberFromClient !== null) { // User didn't cancel prompt
        formData.append('client_po_number', poNumberFromClient.trim());
    }


    const submitButton = poForm.querySelector('button[type="submit"]') || document.getElementById('b2b-submit-po-btn');
    const originalButtonText = submitButton.innerHTML;
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> ${t('common.uploading', 'Téléchargement...')}`;
    }

    try {
        // Last boolean 'true' indicates FormData request for makeApiRequest
        const response = await makeApiRequest('/api/b2b/purchase-orders', 'POST', formData, true, true);
        if (response.success) {
            if(typeof showGlobalMessage === 'function') showGlobalMessage(response.message || t('b2b_po.upload_success', 'Bon de commande soumis avec succès ! Nous allons l\'examiner.'), 'success', 7000);
            clearB2BCart();
            poForm.reset(); // Reset the form
        } else {
            if(typeof showGlobalMessage === 'function') showGlobalMessage(response.message || t('b2b_po.upload_failed', 'Échec de la soumission du Bon de Commande.'), 'error');
        }
    } catch (error) {
        console.error("PO submission error:", error);
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('common.error_network', 'Erreur réseau - soumission du Bon de Commande.'), 'error');
    } finally {
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.innerHTML = originalButtonText;
        }
    }
}


// --- B2B Product Detail Page Logic ---
let currentB2BProductDetail = null;

async function loadB2BProductDetail() {
    const urlParams = new URLSearchParams(window.location.search);
    const productSlug = urlParams.get('slug');
    const detailContainer = document.getElementById('b2b-product-detail-container');

    if (!detailContainer || !productSlug) {
        if (detailContainer) detailContainer.innerHTML = `<p class="text-center text-red-500">${t('b2b_product_detail.error.no_slug_or_container', 'Produit non spécifié ou conteneur manquant.')}</p>`;
        return;
    }
    detailContainer.innerHTML = `<p class="text-center text-mt-earth-brown py-10">${t('b2b_product_detail.loading', 'Chargement des détails du produit B2B...')}</p>`;

    try {
        // API endpoint must provide B2B pricing based on authenticated user's tier
        const response = await makeApiRequest(`/api/b2b/products/${productSlug}`, 'GET', null, true); // Use B2B endpoint and require auth

        if (!response.success || !response.product) {
            detailContainer.innerHTML = `<p class="text-center text-red-500">${response.message || t('b2b_product_detail.error.not_found', 'Produit B2B non trouvé.')}</p>`;
            return;
        }
        currentB2BProductDetail = response.product;
        renderB2BProductDetail(currentB2BProductDetail);
    } catch (error) {
        console.error('Failed to load B2B product details:', error);
        detailContainer.innerHTML = `<p class="text-center text-red-500">${t('b2b_product_detail.error.load_failed', 'Impossible de charger les détails du produit B2B.')}</p>`;
        if (typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_product_detail.error.load_failed_toast', 'Erreur chargement détails produit B2B.'), 'error');
    }
}

function renderB2BProductDetail(product) {
    document.title = `${product.name_fr || product.name} - Marché Pro - Maison Trüvra`;
    document.getElementById('breadcrumb-b2b-product-name').textContent = product.name_fr || product.name;

    // Image Gallery (can reuse logic from products.js or adapt it)
    if (typeof setupImageGallery === 'function') { // Assuming setupImageGallery is global from products.js
        setupImageGallery(
            product.additional_images || [],
            product.main_image_full_url || product.main_image_url,
            product.name_fr || product.name,
            'b2b-main-product-image',      // Main image ID
            'b2b-thumbnail-container',   // Thumbnail container ID
            'b2b-image-modal',           // Modal ID
            'b2b-modal-image-content',   // Modal image content ID
            'b2b-close-image-modal',     // Modal close button ID
            'b2b-prev-image-btn',        // Prev button ID
            'b2b-next-image-btn'         // Next button ID
        );
    }


    document.getElementById('b2b-product-name').textContent = product.name_fr || product.name;
    document.getElementById('b2b-product-short-description').innerHTML = product.description_fr || product.description || '';
    
    const categoryLinkEl = document.getElementById('b2b-product-category-link');
    if (product.category_name && product.category_slug) {
        categoryLinkEl.innerHTML = `<a href="marchedespros.html?category_slug=${product.category_slug}" class="hover:underline">${product.category_name}</a>`;
    } else {
        categoryLinkEl.textContent = product.category_name || t('product.no_category', 'Non catégorisé');
    }

    const optionsContainer = document.getElementById('b2b-product-options-container');
    const priceDisplay = document.getElementById('b2b-product-price');
    const rrpDisplay = document.getElementById('b2b-product-rrp');
    const quantitySelect = document.getElementById('b2b-quantity-select');
    const stockIndicator = document.getElementById('b2b-stock-indicator');
    const addToCartBtnDetail = document.getElementById('b2b-add-to-cart-btn');

    optionsContainer.innerHTML = '';
    stockIndicator.innerHTML = '';

    // Tiered price for the main product/default variant
    const mainB2BPrice = product.b2b_price !== null && product.b2b_price !== undefined ? parseFloat(product.b2b_price) : null;
    const mainRetailPrice = product.retail_price !== null && product.retail_price !== undefined ? parseFloat(product.retail_price) : null;

    if (mainB2BPrice !== null) {
        priceDisplay.textContent = `€${mainB2BPrice.toFixed(2)} HT`;
        if (rrpDisplay && mainRetailPrice !== null && mainRetailPrice > mainB2BPrice) {
            rrpDisplay.querySelector('del').textContent = `€${mainRetailPrice.toFixed(2)}`;
            rrpDisplay.classList.remove('hidden');
        } else if (rrpDisplay) {
            rrpDisplay.classList.add('hidden');
        }
    } else {
        priceDisplay.textContent = t('b2b_shop.price_on_request_or_options', 'Voir options/Devis');
        if (rrpDisplay) rrpDisplay.classList.add('hidden');
    }


    if (product.type === 'variable_weight' && product.weight_options_b2b && product.weight_options_b2b.length > 0) {
        optionsContainer.innerHTML = `
            <label for="b2b-weight-options-select" class="block text-sm font-medium text-mt-near-black mb-1">${t('b2b_product_detail.choose_option', 'Choisissez une option de poids :')}</label>
            <select id="b2b-weight-options-select" class="form-select w-full md:w-2/3 rounded-md border-mt-warm-taupe focus:ring-mt-classic-gold focus:border-mt-classic-gold">
                <option value="">-- ${t('b2b_product_detail.select_an_option', 'Sélectionner')} --</option>
                ${product.weight_options_b2b.map(opt => {
                    const stockForOption = opt.aggregate_stock_quantity || 0;
                    const optionB2BPrice = parseFloat(opt.b2b_price); // Already tiered price from API
                    return `<option value="${opt.option_id}" data-b2b-price="${optionB2BPrice.toFixed(2)}" data-retail-price="${parseFloat(opt.retail_price || 0).toFixed(2)}" data-stock="${stockForOption}" ${stockForOption <= 0 ? 'disabled' : ''}>
                        ${opt.weight_grams}g (${opt.sku_suffix}) - €${optionB2BPrice.toFixed(2)} HT ${stockForOption <= 0 ? `(${t('product.out_of_stock_short', 'Épuisé')})` : ''}
                    </option>`;
                }).join('')}
            </select>
        `;
        const weightSelect = document.getElementById('b2b-weight-options-select');
        weightSelect.addEventListener('change', updateB2BPriceAndStockFromSelectionDetail);
        updateB2BPriceAndStockFromSelectionDetail(); // Initial call to set stock for default/first option
    } else { // Simple product
        updateB2BStockDisplayAndQuantityInput(product.aggregate_stock_quantity || 0, stockIndicator, quantitySelect, addToCartBtnDetail);
    }

    document.getElementById('b2b-product-long-description').innerHTML = product.long_description_fr || product.long_description || t('product_detail.no_long_description', 'Pas de description détaillée disponible.');
    // Populate other accordion sections (sensory, pairings, species) similarly, using B2B specific fields if they exist in `product` object
    // Example for sensory:
    const sensoryAccordion = document.getElementById('b2b-sensory-evaluation-accordion');
    const sensoryP = document.getElementById('b2b-product-sensory-evaluation');
    if (product.sensory_evaluation_fr || product.sensory_evaluation) {
        sensoryP.innerHTML = product.sensory_evaluation_fr || product.sensory_evaluation;
        if (sensoryAccordion) sensoryAccordion.style.display = 'block';
    } else {
        if (sensoryAccordion) sensoryAccordion.style.display = 'none';
    }
    // ... repeat for food_pairings, species, b2b_specific_info ...


    document.querySelector('#b2b-product-code-display span').textContent = product.product_code || 'N/A';
    const preservationType = product.preservation_type ? t(`product.preservation.${product.preservation_type}`, product.preservation_type) : 'N/A';
    document.querySelector('#b2b-product-preservation-display span').textContent = preservationType;

    addToCartBtnDetail.removeEventListener('click', handleB2BAddToCartFromDetail);
    addToCartBtnDetail.addEventListener('click', handleB2BAddToCartFromDetail);

    if (typeof initializeAccordions === 'function') initializeAccordions(); // from ui.js or products.js
}

function updateB2BPriceAndStockFromSelectionDetail() {
    const weightSelect = document.getElementById('b2b-weight-options-select');
    const priceDisplay = document.getElementById('b2b-product-price');
    const rrpDisplay = document.getElementById('b2b-product-rrp');
    const quantitySelect = document.getElementById('b2b-quantity-select');
    const stockIndicator = document.getElementById('b2b-stock-indicator');
    const addToCartBtnDetail = document.getElementById('b2b-add-to-cart-btn');

    if (!weightSelect || !currentB2BProductDetail || !currentB2BProductDetail.weight_options_b2b) return;

    const selectedOptionEl = weightSelect.options[weightSelect.selectedIndex];
    if (selectedOptionEl && selectedOptionEl.value) {
        const selectedB2BPrice = parseFloat(selectedOptionEl.dataset.b2bPrice);
        const selectedRetailPrice = parseFloat(selectedOptionEl.dataset.retailPrice);
        const stock = parseInt(selectedOptionEl.dataset.stock, 10) || 0;

        priceDisplay.textContent = `€${selectedB2BPrice.toFixed(2)} HT`;
        if (rrpDisplay && selectedRetailPrice > 0 && selectedRetailPrice > selectedB2BPrice) {
            rrpDisplay.querySelector('del').textContent = `€${selectedRetailPrice.toFixed(2)}`;
            rrpDisplay.classList.remove('hidden');
        } else if (rrpDisplay) {
            rrpDisplay.classList.add('hidden');
        }
        updateB2BStockDisplayAndQuantityInput(stock, stockIndicator, quantitySelect, addToCartBtnDetail);
    } else { // No option selected, might revert to main product price or show placeholder
        const mainB2BPrice = currentB2BProductDetail.b2b_price !== null && currentB2BProductDetail.b2b_price !== undefined ? parseFloat(currentB2BProductDetail.b2b_price) : null;
        if (mainB2BPrice !== null) {
             priceDisplay.textContent = `€${mainB2BPrice.toFixed(2)} HT`;
        } else {
            priceDisplay.textContent = t('b2b_shop.price_select_option', 'Prix selon option');
        }
        if (rrpDisplay) rrpDisplay.classList.add('hidden');
        updateB2BStockDisplayAndQuantityInput(0, stockIndicator, quantitySelect, addToCartBtnDetail, true); // Disable add to cart if no option selected
    }
}

function updateB2BStockDisplayAndQuantityInput(stock, stockIndicatorEl, quantityInputEl, addToCartButtonEl, disableCartButton = false) {
    if (!quantityInputEl || !stockIndicatorEl || !addToCartButtonEl) return;

    quantityInputEl.max = stock > 0 ? stock.toString() : "0";

    if (stock <= 0 || disableCartButton) {
        stockIndicatorEl.innerHTML = stock <= 0 ? `<span class="text-red-600 font-semibold">${t('product.out_of_stock', 'Épuisé')}</span>` : `<span class="text-mt-warm-taupe">${t('b2b_product_detail.select_option_for_stock', 'Sélectionnez une option pour voir le stock.')}</span>`;
        quantityInputEl.value = disableCartButton ? "1" : "0"; // Keep 1 if just waiting for selection, 0 if truly out of stock
        quantityInputEl.min = disableCartButton ? "1" : "0";
        quantityInputEl.disabled = (stock <= 0 || disableCartButton);
        
        if (stock <=0 ) {
            addToCartButtonEl.disabled = true;
            addToCartButtonEl.innerHTML = `<i class="fas fa-times-circle mr-2"></i> ${t('product.out_of_stock', 'Épuisé')}`;
        } else if (disableCartButton) {
             addToCartButtonEl.disabled = true;
             addToCartButtonEl.innerHTML = `<i class="fas fa-plus-circle mr-2"></i> ${t('b2b_product_detail.select_option_prompt_btn', 'Choisir une Option')}`;
        }
    } else {
        quantityInputEl.disabled = false;
        quantityInputEl.min = "1";
        let currentVal = parseInt(quantityInputEl.value);
        if (isNaN(currentVal) || currentVal <= 0) quantityInputEl.value = "1";
        else if (currentVal > stock) quantityInputEl.value = stock.toString();
        
        stockIndicatorEl.innerHTML = stock < 10 ? 
            `<span class="text-mt-truffle-burgundy font-semibold">${t('product.low_stock_detail', 'Stock faible : Plus que {{count}} en stock !', { count: stock })}</span>` :
            `<span class="text-mt-deep-sage-green">${t('product.in_stock_many', 'En stock')}</span>`;
        
        addToCartButtonEl.disabled = false;
        addToCartButtonEl.innerHTML = `<i class="fas fa-plus-circle mr-2"></i> ${t('b2b_product_detail.add_to_cart_quote', 'Ajouter au Panier/Devis')}`;
    }
}

function handleB2BAddToCartFromDetail() {
    if (!currentB2BProductDetail) return;
    const quantity = parseInt(document.getElementById('b2b-quantity-select').value, 10);
    let selectedVariant = null;
    let productDataForCart = { ...currentB2BProductDetail }; // Clone base product

    if (currentB2BProductDetail.type === 'variable_weight' && currentB2BProductDetail.weight_options_b2b && currentB2BProductDetail.weight_options_b2b.length > 0) {
        const weightSelect = document.getElementById('b2b-weight-options-select');
        if (!weightSelect || !weightSelect.value) {
            if(typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_product_detail.error.select_option_add', 'Veuillez sélectionner une option de poids.'), 'error');
            return;
        }
        selectedVariant = currentB2BProductDetail.weight_options_b2b.find(opt => opt.option_id.toString() === weightSelect.value);
        if (!selectedVariant) {
            if(typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_product_detail.error.invalid_option_selected', 'Option sélectionnée invalide.'), 'error');
            return;
        }
        // Override productDataForCart with variant specific B2B data
        productDataForCart.variantId = selectedVariant.option_id;
        productDataForCart.variantLabel = `${selectedVariant.weight_grams}g (${selectedVariant.sku_suffix})`;
        productDataForCart.b2b_price = selectedVariant.b2b_price; // This is the crucial tiered price for the variant
        productDataForCart.aggregate_stock_quantity = selectedVariant.aggregate_stock_quantity;
        productDataForCart.skuSuffix = selectedVariant.sku_suffix;
    } else if (currentB2BProductDetail.type === 'variable_weight' && (!currentB2BProductDetail.weight_options_b2b || currentB2BProductDetail.weight_options_b2b.length === 0)) {
        // Variable product with no active/available options from API for this user tier
        if(typeof showGlobalMessage === 'function') showGlobalMessage(t('b2b_product_detail.error.no_options_available_add', 'Aucune option disponible pour ce produit B2B.'), 'error');
        return;
    }
    // For simple products, productDataForCart already has the correct b2b_price from API

    if (quantity > 0) {
        addToB2BCart(productDataForCart, quantity);
    }
}

// General renderPagination function - can be moved to ui.js or utils.js if used elsewhere
function renderPagination(container, paginationData, pageChangeCallback) {
    if (!container || !paginationData || paginationData.total_pages <= 1) {
        if(container) container.innerHTML = '';
        return;
    }
    // Store current filters to pass them along with page change
    const currentFilters = getCurrentB2BFilters();


    let html = '<div class="pagination-controls space-x-1 flex justify-center items-center">';
    html += `<button class="btn btn-outline btn-sm ${paginationData.current_page === 1 ? 'opacity-50 cursor-not-allowed' : 'hover:bg-mt-cream'}" 
                     onclick="handleB2BPageChange(${paginationData.current_page - 1})"
                     ${paginationData.current_page === 1 ? 'disabled' : ''}>
                     <i class="fas fa-chevron-left"></i> <span class="hidden sm:inline ml-1">${t('pagination.previous', 'Précédent')}</span>
             </button>`;

    const maxPagesToShow = 5;
    let startPage = Math.max(1, paginationData.current_page - Math.floor(maxPagesToShow / 2));
    let endPage = Math.min(paginationData.total_pages, startPage + maxPagesToShow - 1);
    if (endPage - startPage + 1 < maxPagesToShow && startPage > 1) {
        startPage = Math.max(1, endPage - maxPagesToShow + 1);
    }

    if (startPage > 1) {
        html += `<button class="btn btn-outline btn-sm hover:bg-mt-cream" onclick="handleB2BPageChange(1)">1</button>`;
        if (startPage > 2) html += `<span class="px-2 py-1 text-mt-warm-taupe">...</span>`;
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="btn btn-sm ${i === paginationData.current_page ? 'btn-primary' : 'btn-outline hover:bg-mt-cream'}" 
                         onclick="handleB2BPageChange(${i})"
                         ${i === paginationData.current_page ? 'disabled aria-current="page"' : ''}>
                         ${i}
                 </button>`;
    }

    if (endPage < paginationData.total_pages) {
        if (endPage < paginationData.total_pages - 1) html += `<span class="px-2 py-1 text-mt-warm-taupe">...</span>`;
        html += `<button class="btn btn-outline btn-sm hover:bg-mt-cream" onclick="handleB2BPageChange(${paginationData.total_pages})">${paginationData.total_pages}</button>`;
    }

    html += `<button class="btn btn-outline btn-sm ${paginationData.current_page === paginationData.total_pages ? 'opacity-50 cursor-not-allowed' : 'hover:bg-mt-cream'}" 
                     onclick="handleB2BPageChange(${paginationData.current_page + 1})"
                     ${paginationData.current_page === paginationData.total_pages ? 'disabled' : ''}>
                     <span class="hidden sm:inline mr-1">${t('pagination.next', 'Suivant')}</span> <i class="fas fa-chevron-right"></i>
             </button>`;
    html += '</div>';
    container.innerHTML = html;
    
    // Make pageChangeCallback accessible or re-attach listeners if needed
    window.handleB2BPageChange = (newPage) => {
        const currentFilters = getCurrentB2BFilters(); // Get filters at the moment of page change
        loadB2BProducts(newPage, currentFilters); // Pass filters to loadB2BProducts
    };
}
function getCurrentB2BFilters() {
    const category = document.getElementById('b2b-category-filter')?.value;
    const sortBy = document.getElementById('b2b-sort-by')?.value;
    const searchTerm = document.getElementById('b2b-search-products')?.value;
    const filters = {};
    if (category) filters.category_slug = category;
    if (sortBy) filters.sort = sortBy;
    if (searchTerm) filters.search = searchTerm;
    return filters;
}


// Add any missing translation keys to fr.json and en.json as indicated in comments or by usage.
// For example:
// "b2b_cart.error.saving_cart", "b2b_cart.error.invalid_product_data", "b2b_cart.error.item_out_of_stock",
// "b2b_cart.default_item_name", "b2b_cart.error.invalid_price", "b2b_cart.error.stock_limit_exceeded_update",
// "b2b_cart.error.stock_limit_exceeded_add", "b2b_cart.added_success", "b2b_cart.item_removed",
// "b2b_cart.an_item", "b2b_cart.item_removed_specific", "b2b_cart.cleared",
// "b2b_shop.auth_redirect_message", "b2b_shop.default_company_name", "b2b_shop.welcome_user",
// "b2b_tier.standard", "b2b_tier.gold", "b2b_tier.platinum", // Add all your tier names
// "b2b_shop.all_categories", "b2b_shop.error.load_categories", "b2b_shop.error.load_products",
// "b2b_shop.error.load_products_network", "product.image_alt", "product.no_category",
// "b2b_shop.your_price_label", "b2b_shop.rrp_label", "b2b_shop.price_on_request_or_options",
// "product.default_description_short", "b2b_shop.view_details_btn", "b2b_shop.add_to_cart_quote_btn",
// "product.out_of_stock", "b2b_cart.error.product_not_in_cache",
// "b2b_cart.empty_for_checkout", "b2b_cart.empty_for_quote", "b2b_cart.error.modal_function_missing",
// "common.sending", "b2b_quote.request_success", "b2b_quote.request_failed", "common.error_network",
// "b2b_po.no_file_selected", "b2b_po.cart_empty_for_po", "common.uploading",
// "b2b_po.upload_success", "b2b_po.upload_failed", "b2b_po.prompt_po_number",
// "b2b_product_detail.error.no_slug_or_container", "b2b_product_detail.loading",
// "b2b_product_detail.error.not_found", "b2b_product_detail.error.load_failed",
// "b2b_product_detail.error.load_failed_toast", "b2b_product_detail.choose_option",
// "b2b_product_detail.select_an_option", "product.out_of_stock_short",
// "b2b_product_detail.select_option_for_stock", "b2b_product_detail.select_option_prompt_btn",
// "product.low_stock_detail", "product.in_stock_many", "b2b_product_detail.error.select_option_add",
// "b2b_product_detail.error.invalid_option_selected", "b2b_product_detail.error.no_options_available_add",
// "pagination.previous", "pagination.next"
