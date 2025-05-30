// Maison Trüvra - Shopping Cart Management
// This file handles client-side cart operations using localStorage.

const CART_STORAGE_KEY = 'maisonTruvraCart';

/**
 * Loads the cart from localStorage.
 * @returns {Array<Object>} An array of cart item objects.
 */
function loadCart() {
    const cartJson = localStorage.getItem(CART_STORAGE_KEY);
    try {
        return cartJson ? JSON.parse(cartJson) : [];
    } catch (e) {
        console.error("Error parsing cart from localStorage:", e);
        return []; // Return empty cart on error
    }
}

/**
 * Saves the cart to localStorage.
 * @param {Array<Object>} cartItems - The array of cart items to save.
 */
function saveCart(cartItems) {
    try {
        const cartJson = JSON.stringify(cartItems);
        localStorage.setItem(CART_STORAGE_KEY, cartJson);
    } catch (e) {
        console.error("Error saving cart to localStorage:", e);
    }
}

/**
 * Adds an item to the shopping cart or updates its quantity if it already exists.
 * @param {Object} product - The product object to add. Must include id, name, price.
 * @param {number} quantity - The quantity to add.
 * @param {Object} [variantInfo=null] - Optional variant information (e.g., { id, weight_grams, price, sku_suffix }).
 * If variantInfo is provided, its price overrides product.price.
 */
function addToCart(product, quantity = 1, variantInfo = null) {
    if (!product || !product.id || !product.name || (variantInfo ? !variantInfo.price : !product.base_price)) {
        console.error("addToCart: Invalid product or variant data provided.", product, variantInfo);
        showGlobalMessage("Erreur: Impossible d'ajouter le produit au panier (données invalides).", "error");
        return;
    }

    const cart = loadCart();
    const itemPrice = variantInfo ? variantInfo.price : product.base_price;
    const itemName = variantInfo ? `${product.name} (${variantInfo.weight_grams}g)` : product.name; // Or use sku_suffix for more detail
    const itemSkuSuffix = variantInfo ? variantInfo.sku_suffix : null;
    const itemVariantId = variantInfo ? variantInfo.id : null;
    const itemMainImage = product.main_image_full_url || product.main_image_url || 'https://placehold.co/100x100/eee/ccc?text=Image';


    // Check if item (with specific variant if applicable) already exists in cart
    const existingItemIndex = cart.findIndex(item => 
        item.id === product.id && 
        (itemVariantId ? item.variantId === itemVariantId : !item.variantId) // Match variant or ensure no variant
    );

    if (existingItemIndex > -1) {
        // Item exists, update quantity
        cart[existingItemIndex].quantity += quantity;
        if (cart[existingItemIndex].quantity <= 0) { // If quantity becomes zero or less, remove it
            cart.splice(existingItemIndex, 1);
        }
    } else {
        // New item
        if (quantity > 0) {
            cart.push({
                id: product.id, // Product ID
                variantId: itemVariantId, // product_weight_options.id if applicable
                name: itemName,
                price: parseFloat(itemPrice),
                quantity: quantity,
                skuPrefix: product.sku_prefix, // Store for reference
                skuSuffix: itemSkuSuffix,      // Store for reference
                image: itemMainImage,
                slug: product.slug // For linking back to product page
                // Add other relevant product/variant details if needed (e.g., unit_of_measure)
            });
        }
    }

    saveCart(cart);
    updateCartDisplay(); // Update cart icon and any other cart UI elements
    showGlobalMessage(`${quantity} x ${itemName} ajouté au panier!`, "success");
    console.log("Cart updated:", loadCart());
}

/**
 * Removes an item completely from the cart.
 * @param {number} productId - The ID of the product to remove.
 * @param {number} [variantId=null] - The ID of the variant to remove (if applicable).
 */
function removeFromCart(productId, variantId = null) {
    let cart = loadCart();
    const initialLength = cart.length;
    cart = cart.filter(item => 
        !(item.id === productId && (variantId ? item.variantId === variantId : !item.variantId))
    );

    if (cart.length < initialLength) {
        saveCart(cart);
        updateCartDisplay();
        showGlobalMessage("Article retiré du panier.", "info");
    }
}

/**
 * Updates the quantity of a specific item in the cart.
 * If quantity becomes 0 or less, the item is removed.
 * @param {number} productId - The ID of the product.
 * @param {number} newQuantity - The new quantity for the item.
 * @param {number} [variantId=null] - The ID of the variant (if applicable).
 */
function updateCartItemQuantity(productId, newQuantity, variantId = null) {
    const cart = loadCart();
    const itemIndex = cart.findIndex(item => 
        item.id === productId && 
        (variantId ? item.variantId === variantId : !item.variantId)
    );

    if (itemIndex > -1) {
        if (newQuantity > 0) {
            cart[itemIndex].quantity = newQuantity;
        } else {
            cart.splice(itemIndex, 1); // Remove item if quantity is 0 or less
        }
        saveCart(cart);
        updateCartDisplay();
        // showGlobalMessage("Quantité mise à jour dans le panier.", "info"); // Optional message
    }
}

/**
 * Gets all items currently in the cart.
 * @returns {Array<Object>} An array of cart item objects.
 */
function getCartItems() {
    return loadCart();
}

/**
 * Calculates the total price of all items in the cart.
 * @returns {number} The total price.
 */
function getCartTotal() {
    const cart = loadCart();
    return cart.reduce((total, item) => total + (item.price * item.quantity), 0);
}

/**
 * Gets the total number of individual items in the cart (sum of quantities).
 * @returns {number} The total count of items.
 */
function getCartItemCount() {
    const cart = loadCart();
    return cart.reduce((count, item) => count + item.quantity, 0);
}

/**
 * Clears all items from the shopping cart.
 */
function clearCart() {
    localStorage.removeItem(CART_STORAGE_KEY);
    updateCartDisplay();
    // showGlobalMessage("Panier vidé.", "info"); // Optional
    console.log("Cart cleared.");
}

/**
 * Updates the cart display elements (e.g., cart icon count).
 * This function relies on `updateCartIcon` being available from `ui.js` or similar.
 */
function updateCartDisplay() {
    if (typeof updateCartIcon === 'function') {
        updateCartIcon(); // From ui.js to update the cart icon in the header
    }
    // If on cart page, re-initialize to reflect changes
    if (document.body.id === 'page-panier' && typeof initCartPage === 'function') {
        initCartPage();
    }
     // If on checkout page, update summary
    if (document.body.id === 'page-paiement' && typeof displayCheckoutSummary === 'function') {
        displayCheckoutSummary();
    }
}

/**
 * Initializes the cart page: shows login prompt or cart contents.
 */
function initCartPage() {
    const cartLoginPrompt = document.getElementById('cart-login-prompt');
    const cartContentWrapper = document.getElementById('cart-content-wrapper');

    if (!cartLoginPrompt || !cartContentWrapper) {
        // console.error('Cart page elements (cart-login-prompt or cart-content-wrapper) not found.');
        return; // Not on the cart page or elements missing
    }

    if (typeof isUserLoggedIn !== 'function') {
        console.error('isUserLoggedIn function is not available. Ensure auth.js is loaded.');
        cartLoginPrompt.style.display = 'block'; // Fallback: show login prompt
        cartContentWrapper.style.display = 'none';
        return;
    }

    if (isUserLoggedIn()) {
        cartLoginPrompt.style.display = 'none';
        cartContentWrapper.style.display = 'block'; // Or 'flex' etc. depending on your layout
        displayCartOnPage(); // Render the actual cart items and summary
    } else {
        cartLoginPrompt.style.display = 'block';
        cartContentWrapper.style.display = 'none';
    }
}

/**
 * Displays the cart items and summary on the cart page.
 * This function is called by initCartPage when the user is logged in.
 */
function displayCartOnPage() {
    const cartItems = getCartItems();
    const cartItemsContainer = document.getElementById('cart-items-container');
    const emptyCartMessage = document.getElementById('empty-cart-message');
    const cartSummaryContainer = document.getElementById('cart-summary-container');
    const cartSubtotalEl = document.getElementById('cart-subtotal');
    const cartTotalEl = document.getElementById('cart-total');

    if (!cartItemsContainer || !emptyCartMessage || !cartSummaryContainer || !cartSubtotalEl || !cartTotalEl) {
        console.error('One or more cart display elements are missing from panier.html.');
        return;
    }

    cartItemsContainer.innerHTML = ''; // Clear previous items

    if (cartItems.length === 0) {
        emptyCartMessage.style.display = 'block';
        cartSummaryContainer.style.display = 'none';
    } else {
        emptyCartMessage.style.display = 'none';
        cartItems.forEach(item => {
            const itemElement = document.createElement('div');
            itemElement.classList.add('cart-item'); // Uses Tailwind @apply from panier.html
            itemElement.innerHTML = `
                <img src="${item.image || 'https://placehold.co/80x80/F5EEDE/7D6A4F?text=Img'}" alt="${item.name}" class="cart-item-image">
                <div class="flex-grow mx-4">
                    <p class="font-semibold text-brand-near-black">${item.name}</p>
                    <div class="flex items-center mt-1">
                        <div class="quantity-input-controls flex items-center">
                            <button data-product-id="${item.id}" data-variant-id="${item.variantId || ''}" data-change="-1" class="quantity-change-btn px-2 py-0.5 border border-brand-warm-taupe/50 text-brand-near-black hover:bg-brand-warm-taupe/20 text-sm rounded-l">-</button>
                            <input type="number" value="${item.quantity}" min="1" max="99" 
                                   class="w-10 sm:w-12 text-center border-y border-brand-warm-taupe/50 py-1 text-sm appearance-none quantity-value-input" 
                                   data-product-id="${item.id}" data-variant-id="${item.variantId || ''}" readonly>
                            <button data-product-id="${item.id}" data-variant-id="${item.variantId || ''}" data-change="1" class="quantity-change-btn px-2 py-0.5 border border-brand-warm-taupe/50 text-brand-near-black hover:bg-brand-warm-taupe/20 text-sm rounded-r">+</button>
                        </div>
                    </div>
                </div>
                <div class="text-right">
                    <p class="font-semibold text-brand-earth-brown">${(item.price * item.quantity).toFixed(2)} €</p>
                    <button class="text-xs text-brand-truffle-burgundy hover:underline mt-1 remove-item-btn" 
                            data-product-id="${item.id}" data-variant-id="${item.variantId || ''}">
                        Retirer
                    </button>
                </div>
            `;
            cartItemsContainer.appendChild(itemElement);
        });

        const total = getCartTotal();
        cartSubtotalEl.textContent = `${total.toFixed(2)} €`;
        cartTotalEl.textContent = `${total.toFixed(2)} €`; // Assuming shipping is calculated later or is free for now
        cartSummaryContainer.style.display = 'block'; // Or 'flex' if your CSS requires it
    }

    // Add event listeners for new quantity buttons and remove buttons
    document.querySelectorAll('.quantity-change-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            const productId = parseInt(btn.dataset.productId);
            const variantId = btn.dataset.variantId ? parseInt(btn.dataset.variantId) : null;
            const change = parseInt(btn.dataset.change);
            const inputField = btn.parentElement.querySelector('.quantity-value-input');
            let currentQuantity = parseInt(inputField.value);
            let newQuantity = currentQuantity + change;
            if (newQuantity < 1) newQuantity = 1; // Min quantity is 1
            if (newQuantity > 99) newQuantity = 99; // Max quantity
            
            if (newQuantity !== currentQuantity) { // Only update if quantity actually changes
                updateCartItemQuantity(productId, newQuantity, variantId);
                // initCartPage will be called by updateCartDisplay, which is called by updateCartItemQuantity
            }
        });
    });

    document.querySelectorAll('.remove-item-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            const productId = parseInt(btn.dataset.productId);
            const variantId = btn.dataset.variantId ? parseInt(btn.dataset.variantId) : null;
            removeFromCart(productId, variantId);
            // initCartPage will be called by updateCartDisplay, which is called by removeFromCart
        });
    });
}

// Initialize cart display on page load
document.addEventListener('DOMContentLoaded', () => {
    updateCartDisplay(); 
    // initCartPage() is called by main.js if on 'page-panier'
    // and also by the authStateChanged listener in main.js
});

// Make functions globally available if they are called from inline HTML event handlers
// or from other scripts that don't import them as modules.
// For modern development, using event listeners attached from JS is preferred.
window.addToCart = addToCart;
window.removeFromCart = removeFromCart;
window.updateCartItemQuantity = updateCartItemQuantity;
window.getCartItems = getCartItems;
window.getCartTotal = getCartTotal;
window.getCartItemCount = getCartItemCount;
window.clearCart = clearCart;
window.initCartPage = initCartPage; // Make initCartPage globally available for main.js
// updateCartDisplay is called internally and on DOMContentLoaded.

console.log("New cart.js loaded with full cart management logic.");