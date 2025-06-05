// website/source/js/cart.js

/**
 * Internationalization function placeholder (assumed to be globally available or defined in ui.js/main.js).
 * @param {string} key - The translation key.
 * @param {string} [defaultValue] - The default string if key not found.
 * @param {object} [options] - Interpolation options for replacing placeholders like {{count}}.
 * @returns {string} The translated string.
 */
function t(key, defaultValue, options = {}) {
    const lang = document.documentElement.lang || 'fr';
    let translation = defaultValue || key;

    if (window.translations && window.translations[lang] && window.translations[lang][key]) {
        translation = window.translations[lang][key];
    } else if (window.translations && window.translations['fr'] && window.translations['fr'][key]) {
        translation = window.translations['fr'][key];
    }
    
    for (const optKey in options) {
        translation = translation.replace(new RegExp(`{{${optKey}}}`, 'g'), options[optKey]);
    }
    return translation;
}

/**
 * Gets the current language from the HTML tag.
 * @returns {string} The current language code (e.g., 'fr', 'en').
 */
function getCurrentLanguage() {
    return document.documentElement.lang || 'fr';
}


/**
 * Adds an item to the cart or updates its quantity.
 * Performs a stock check before adding/updating.
 * @param {object} product - The product object (must include id, name_fr, name_en, base_price, aggregate_stock_quantity, main_image_url, slug).
 * @param {number} quantityToAdd - The quantity to add.
 * @param {object} [variantInfo=null] - Optional variant information (e.g., { option_id, weight_grams, price, sku_suffix, aggregate_stock_quantity }).
 */
function addToCart(product, quantityToAdd, variantInfo = null) {
    if (!product || !product.id || typeof quantityToAdd !== 'number' || quantityToAdd <= 0) {
        console.error("Invalid product or quantity for addToCart:", product, quantityToAdd);
        if (typeof showGlobalMessage === 'function') showGlobalMessage(t('cart.error.invalid_product_data', 'Données produit invalides pour l\'ajout au panier.'), 'error');
        return;
    }

    let cart = getCartItems();
    const cartItemId = variantInfo ? `${product.id}-${variantInfo.option_id}` : product.id.toString();
    
    const existingItem = cart.find(item => item.id === cartItemId);
    
    const lang = getCurrentLanguage();
    let itemName = (lang === 'en' && product.name_en) ? product.name_en : product.name_fr;
    if (!itemName) itemName = product.name || t('cart.default_item_name', 'Article'); 
    if (variantInfo && variantInfo.weight_grams) {
        itemName += ` (${variantInfo.weight_grams}g)`;
    }

    const availableStock = variantInfo ? (variantInfo.aggregate_stock_quantity || 0) : (product.aggregate_stock_quantity || 0);

    if (availableStock <= 0 && !existingItem) { // If item is totally out of stock and not already in cart
        if (typeof showGlobalMessage === 'function') {
            showGlobalMessage(t('cart.error.item_out_of_stock', '{{itemName}} est actuellement épuisé.', { itemName: itemName }), 'error', 5000);
        }
        return; 
    }

    if (existingItem) {
        const newQuantity = existingItem.quantity + quantityToAdd;
        if (newQuantity > availableStock) {
            if (typeof showGlobalMessage === 'function') {
                showGlobalMessage(t('cart.error.stock_limit_exceeded_update', 'Stock insuffisant pour ajouter {{quantityToAdd}} de plus pour {{itemName}}. Max: {{count}}.', { quantityToAdd: quantityToAdd, itemName: itemName, count: availableStock }), 'warning', 7000);
            }
            return; 
        }
        existingItem.quantity = newQuantity;
    } else { // New item
        if (quantityToAdd > availableStock) {
            if (typeof showGlobalMessage === 'function') {
                showGlobalMessage(t('cart.error.stock_limit_exceeded_add', 'Stock insuffisant pour {{itemName}}. Seulement {{count}} disponible(s). Vous avez demandé {{requested}}.', { itemName: itemName, count: availableStock, requested: quantityToAdd }), 'warning', 7000);
            }
             return; 
        }
        
        const cartItem = {
            id: cartItemId,
            productId: product.id,
            name: itemName,
            price: variantInfo ? variantInfo.price : product.base_price,
            quantity: quantityToAdd,
            image: product.main_image_full_url || product.main_image_url || 'https://placehold.co/100x100/F5EEDE/11120D?text=Item',
            slug: product.slug,
            variantId: variantInfo ? variantInfo.option_id : null,
            variantLabel: variantInfo ? `${variantInfo.weight_grams}g` : null,
            skuSuffix: variantInfo ? variantInfo.sku_suffix : null, 
            currentAvailableStock: availableStock 
        };
        cart.push(cartItem);
    }

    saveCartItems(cart);
    updateCartDisplay(); 
    if (typeof showCartToast === 'function') showCartToast(itemName, quantityToAdd); 
    
    if (document.body.id === 'page-panier') {
        displayCartOnPage();
    }
}

/**
 * Retrieves cart items from localStorage.
 * @returns {Array} The array of cart items.
 */
function getCartItems() {
    try {
        const cartJson = localStorage.getItem('maisonTruvraCart');
        return cartJson ? JSON.parse(cartJson) : [];
    } catch (e) {
        console.error("Error parsing cart from localStorage:", e);
        return [];
    }
}

/**
 * Saves cart items to localStorage.
 * @param {Array} cartItems - The array of cart items to save.
 */
function saveCartItems(cartItems) {
    try {
        localStorage.setItem('maisonTruvraCart', JSON.stringify(cartItems));
    } catch (e) {
        console.error("Error saving cart to localStorage:", e);
        if (typeof showGlobalMessage === 'function') {
            showGlobalMessage(t('cart.error.saving_cart', 'Erreur lors de la sauvegarde du panier.'), 'error');
        }
    }
}

/**
 * Updates the cart display (e.g., item count in header, mini-cart).
 */
function updateCartDisplay() {
    const cart = getCartItems();
    const cartItemCountElement = document.getElementById('cart-item-count');
    const miniCartItemsContainer = document.getElementById('mini-cart-items');
    const miniCartTotalElement = document.getElementById('mini-cart-total');
    const miniCartEmptyMsg = document.getElementById('mini-cart-empty-msg');
    const miniCartCheckoutBtn = document.getElementById('mini-cart-checkout-btn');

    let totalItems = 0;
    let totalPrice = 0;

    cart.forEach(item => {
        totalItems += item.quantity;
        totalPrice += item.price * item.quantity;
    });

    if (cartItemCountElement) {
        cartItemCountElement.textContent = totalItems;
        cartItemCountElement.classList.toggle('hidden', totalItems === 0);
    }

    if (miniCartItemsContainer && miniCartTotalElement && miniCartEmptyMsg && miniCartCheckoutBtn) {
        miniCartItemsContainer.innerHTML = ''; 

        if (cart.length === 0) {
            miniCartEmptyMsg.style.display = 'block';
            miniCartCheckoutBtn.classList.add('hidden');
            miniCartTotalElement.parentElement.classList.add('hidden');
        } else {
            miniCartEmptyMsg.style.display = 'none';
            miniCartCheckoutBtn.classList.remove('hidden');
            miniCartTotalElement.parentElement.classList.remove('hidden');

            cart.forEach(item => {
                const itemElement = document.createElement('div');
                itemElement.className = 'mini-cart-item flex items-center py-2 border-b border-mt-cream-dark';
                itemElement.innerHTML = `
                    <img src="${item.image}" alt="${item.name}" class="w-12 h-12 object-cover rounded mr-3">
                    <div class="flex-grow">
                        <p class="text-sm font-medium text-mt-near-black truncate" title="${item.name}">${item.name}</p>
                        <p class="text-xs text-mt-earth-brown">${item.quantity} x €${parseFloat(item.price).toFixed(2)}</p>
                    </div>
                    <span class="text-sm font-semibold text-mt-near-black ml-2">€${(item.quantity * item.price).toFixed(2)}</span>
                `;
                miniCartItemsContainer.appendChild(itemElement);
            });
            miniCartTotalElement.textContent = `€${totalPrice.toFixed(2)}`;
        }
    }
    if (document.body.id === 'page-panier') {
        displayCartOnPage();
    }
}

/**
 * Displays the full cart on the panier.html page.
 */
function displayCartOnPage() {
    const cartItemsContainer = document.getElementById('cart-items-container');
    const cartSummaryTotal = document.getElementById('cart-summary-total');
    const cartSummarySubtotal = document.getElementById('cart-summary-subtotal');
    const emptyCartMessage = document.getElementById('empty-cart-message');
    const cartTableAndSummary = document.getElementById('cart-table-and-summary'); // Parent of table and summary
    const checkoutButtonCartPage = document.getElementById('checkout-button-cart-page');

    if (!cartItemsContainer || !cartSummaryTotal || !emptyCartMessage || !cartTableAndSummary || !checkoutButtonCartPage) {
        return;
    }

    const cart = getCartItems();
    cartItemsContainer.innerHTML = ''; 

    if (cart.length === 0) {
        emptyCartMessage.classList.remove('hidden');
        cartTableAndSummary.classList.add('hidden');
        // checkoutButtonCartPage remains visible but should be handled by its own event listener
        if(cartSummarySubtotal) cartSummarySubtotal.textContent = '€0.00';
        cartSummaryTotal.textContent = '€0.00';
        return;
    }

    emptyCartMessage.classList.add('hidden');
    cartTableAndSummary.classList.remove('hidden');
    
    let subtotal = 0;

    cart.forEach(item => {
        const itemRow = document.createElement('tr');
        itemRow.className = 'cart-item-row border-b border-mt-cream-dark';
        const maxStockForItem = item.currentAvailableStock || 100; // Fallback max if stock unknown
        
        itemRow.innerHTML = `
            <td class="py-4 px-2 md:px-4">
                <div class="flex items-center">
                    <img src="${item.image}" alt="${item.name}" class="w-16 h-16 md:w-20 md:h-20 object-cover rounded-md mr-3 md:mr-4">
                    <div>
                        <a href="produit-detail.html?slug=${item.slug}" class="font-semibold text-mt-near-black hover:text-mt-truffle-burgundy text-sm md:text-base" title="${item.name}">${item.name}</a>
                        ${item.variantLabel ? `<p class="text-xs text-mt-earth-brown">${item.variantLabel}</p>` : ''}
                    </div>
                </div>
            </td>
            <td class="py-4 px-2 md:px-4 text-center">€${parseFloat(item.price).toFixed(2)}</td>
            <td class="py-4 px-2 md:px-4">
                <div class="flex items-center justify-center">
                    <button class="quantity-change-btn text-mt-warm-taupe hover:text-mt-near-black p-1" data-item-id="${item.id}" data-change="-1" aria-label="${t('cart.decrease_quantity', 'Diminuer la quantité')}">
                        <i class="fas fa-minus-circle"></i>
                    </button>
                    <input type="number" value="${item.quantity}" min="1" max="${maxStockForItem}" 
                           class="quantity-input-cart w-12 mx-1 text-center border border-mt-cream-dark rounded-md focus:ring-mt-classic-gold focus:border-mt-classic-gold" 
                           data-item-id="${item.id}" aria-label="${t('cart.item_quantity', 'Quantité de l\'article')}">
                    <button class="quantity-change-btn text-mt-warm-taupe hover:text-mt-near-black p-1" data-item-id="${item.id}" data-change="1" aria-label="${t('cart.increase_quantity', 'Augmenter la quantité')}">
                        <i class="fas fa-plus-circle"></i>
                    </button>
                </div>
                ${item.quantity > item.currentAvailableStock ? `<p class="text-xs text-red-500 mt-1 text-center">${t('cart.error.requested_qty_unavailable', 'Quantité demandée indisponible (Max: {{max}})', {max: item.currentAvailableStock})}</p>` : ''}
                ${item.currentAvailableStock > 0 && item.currentAvailableStock < 10 && item.quantity <= item.currentAvailableStock ? `<p class="text-xs text-mt-truffle-burgundy mt-1 text-center">${t('cart.info.low_stock_cart', 'Stock faible: {{count}} restants', {count: item.currentAvailableStock})}</p>` : ''}
            </td>
            <td class="py-4 px-2 md:px-4 text-right font-semibold text-mt-near-black">€${(item.price * item.quantity).toFixed(2)}</td>
            <td class="py-4 px-2 md:px-4 text-right">
                <button class="remove-from-cart-btn text-mt-truffle-burgundy hover:text-red-700" data-item-id="${item.id}" aria-label="${t('cart.remove_item', 'Supprimer l\'article')}">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </td>
        `;
        cartItemsContainer.appendChild(itemRow);
        subtotal += item.price * item.quantity;
    });

    if(cartSummarySubtotal) cartSummarySubtotal.textContent = `€${subtotal.toFixed(2)}`;
    cartSummaryTotal.textContent = `€${subtotal.toFixed(2)}`; 

    cartItemsContainer.querySelectorAll('.quantity-change-btn').forEach(button => {
        button.addEventListener('click', handleQuantityChangeInCart);
    });
    cartItemsContainer.querySelectorAll('.quantity-input-cart').forEach(input => {
        input.addEventListener('change', handleQuantityInputChangeInCart);
    });
    cartItemsContainer.querySelectorAll('.remove-from-cart-btn').forEach(button => {
        button.addEventListener('click', handleRemoveFromCart);
    });
}

function handleQuantityChangeInCart(event) {
    const button = event.currentTarget;
    const itemId = button.dataset.itemId;
    const change = parseInt(button.dataset.change, 10);
    const inputField = button.closest('td').querySelector('.quantity-input-cart'); // Find input in the same cell
    if (!inputField) return;
    let currentQuantity = parseInt(inputField.value, 10);
    let newQuantity = currentQuantity + change;
    
    updateCartItemQuantity(itemId, newQuantity); // This will handle stock checks and removal if 0
}

function handleQuantityInputChangeInCart(event) {
    const input = event.currentTarget;
    const itemId = input.dataset.itemId;
    let newQuantity = parseInt(input.value, 10);

    if (isNaN(newQuantity) || newQuantity < 0) { 
        newQuantity = 0; // If invalid, treat as trying to remove or set to 0
    }
    updateCartItemQuantity(itemId, newQuantity);
}

function handleRemoveFromCart(event) {
    const button = event.currentTarget;
    const itemId = button.dataset.itemId;
    removeFromCart(itemId);
}

function removeFromCart(cartItemId) {
    let cart = getCartItems();
    const itemToRemove = cart.find(item => item.id === cartItemId);
    cart = cart.filter(item => item.id !== cartItemId);
    saveCartItems(cart);
    updateCartDisplay(); 
    if (document.body.id === 'page-panier') { 
        displayCartOnPage();
    }
    if (itemToRemove && typeof showGlobalMessage === 'function') {
        showGlobalMessage(t('cart.item_removed_toast', '{{itemName}} supprimé du panier.', { itemName: itemToRemove.name }), 'info', 3000);
    }
}

function updateCartItemQuantity(cartItemId, newQuantityInput) {
    let cart = getCartItems();
    const itemIndex = cart.findIndex(item => item.id === cartItemId);
    let newQuantity = parseInt(newQuantityInput, 10); // Ensure it's an integer

    if (itemIndex > -1) {
        if (isNaN(newQuantity) || newQuantity <= 0) { // If new quantity is 0 or invalid, remove item
            removeFromCart(cartItemId);
            return;
        }

        const itemToUpdate = cart[itemIndex];
        const availableStock = itemToUpdate.currentAvailableStock || 0; 

        if (newQuantity > availableStock) {
            if (typeof showGlobalMessage === 'function') {
                showGlobalMessage(t('cart.error.stock_limit_exceeded_cart_update', 'Stock insuffisant pour {{itemName}}. Max: {{count}}.', { itemName: itemToUpdate.name, count: availableStock }), 'warning', 5000);
            }
            // Reset quantity to max available if user tries to exceed.
            cart[itemIndex].quantity = availableStock; 
        } else {
            cart[itemIndex].quantity = newQuantity;
        }
        
        saveCartItems(cart);
        updateCartDisplay();
        if (document.body.id === 'page-panier') {
            displayCartOnPage(); 
        }
    }
}

function clearCart() {
    localStorage.removeItem('maisonTruvraCart');
    updateCartDisplay();
    if (document.body.id === 'page-panier') {
        displayCartOnPage();
    }
    if (typeof showGlobalMessage === 'function') {
        showGlobalMessage(t('cart.cleared_toast', 'Panier vidé.'), 'info');
    }
}

function getCartTotal() {
    const cart = getCartItems();
    return cart.reduce((total, item) => total + (item.price * item.quantity), 0);
}

// --- Initial setup ---
document.addEventListener('DOMContentLoaded', () => {
    updateCartDisplay(); 
    if (document.body.id === 'page-panier') {
        displayCartOnPage();
    }

    const checkoutButtonCartPage = document.getElementById('checkout-button-cart-page');
    if (checkoutButtonCartPage) {
        checkoutButtonCartPage.addEventListener('click', (event) => {
            const cart = getCartItems();
            if (cart.length === 0) {
                event.preventDefault(); 
                if(typeof showGlobalMessage === 'function') showGlobalMessage(t('cart.error.empty_cart_checkout', 'Votre panier est vide.'), 'error');
            } else {
                // Optional: final quick stock check before navigating to payment
                let canProceed = true;
                for(const item of cart) {
                    if (item.quantity > item.currentAvailableStock) {
                        canProceed = false;
                        if(typeof showGlobalMessage === 'function') {
                            showGlobalMessage(t('cart.error.final_stock_check_failed', 'Certains articles ne sont plus disponibles en quantité suffisante. Veuillez vérifier votre panier.'), 'error', 6000);
                        }
                        displayCartOnPage(); // Refresh cart to show updated stock issues
                        break;
                    }
                }
                if (!canProceed) {
                    event.preventDefault();
                } else {
                    // Allow navigation to payment.html
                    // window.location.href = 'payment.html'; // If not a direct link
                }
            }
        });
    }
});
