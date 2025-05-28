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
    // If there's a dedicated cart page, trigger its refresh if it's currently visible
    if (typeof displayCartOnPage === 'function' && document.getElementById('cart-items-container')) {
        displayCartOnPage();
    }
     // If on checkout page, update summary
    if (typeof displayCheckoutSummary === 'function' && document.getElementById('checkout-summary-container')) {
        displayCheckoutSummary();
    }
}


// Initialize cart display on page load
document.addEventListener('DOMContentLoaded', () => {
    updateCartDisplay(); 
    // If on cart page, render cart items
    if (window.location.pathname.includes('panier.html') || document.getElementById('cart-items-container')) {
        if (typeof displayCartOnPage === 'function') {
            displayCartOnPage();
        } else {
            console.warn('displayCartOnPage function not found, but cart page elements detected.');
        }
    }
});

// Example of how displayCartOnPage might look (to be placed in panier.js or similar)
/*
function displayCartOnPage() {
    const cartItems = getCartItems();
    const cartContainer = document.getElementById('cart-items-container'); // Assuming this ID exists on panier.html
    const cartTotalEl = document.getElementById('cart-total-price'); // Assuming this ID exists
    const cartEmptyMsg = document.getElementById('cart-empty-message');

    if (!cartContainer) return;
    cartContainer.innerHTML = ''; // Clear previous items

    if (cartItems.length === 0) {
        if(cartEmptyMsg) cartEmptyMsg.classList.remove('hidden');
        if(cartTotalEl) cartTotalEl.textContent = '0.00';
        // Hide checkout button or show "continue shopping"
        const checkoutButton = document.getElementById('checkout-button');
        if(checkoutButton) checkoutButton.classList.add('hidden');
        return;
    }
    
    if(cartEmptyMsg) cartEmptyMsg.classList.add('hidden');
    const checkoutButton = document.getElementById('checkout-button');
    if(checkoutButton) checkoutButton.classList.remove('hidden');


    cartItems.forEach(item => {
        const itemElement = document.createElement('div');
        itemElement.classList.add('flex', 'items-center', 'justify-between', 'py-4', 'border-b');
        itemElement.innerHTML = `
            <div class="flex items-center space-x-4">
                <img src="${item.image}" alt="${item.name}" class="w-16 h-16 object-cover rounded">
                <div>
                    <h3 class="text-lg font-semibold">${item.name}</h3>
                    <p class="text-sm text-gray-600">Prix: ${item.price.toFixed(2)} €</p>
                </div>
            </div>
            <div class="flex items-center space-x-3">
                <input type="number" value="${item.quantity}" min="1" 
                       class="w-16 text-center border-gray-300 rounded quantity-input" 
                       data-product-id="${item.id}" data-variant-id="${item.variantId || ''}">
                <p class="text-lg font-semibold">${(item.price * item.quantity).toFixed(2)} €</p>
                <button class="text-red-500 hover:text-red-700 remove-item-btn" 
                        data-product-id="${item.id}" data-variant-id="${item.variantId || ''}">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        cartContainer.appendChild(itemElement);
    });

    if (cartTotalEl) {
        cartTotalEl.textContent = getCartTotal().toFixed(2);
    }

    // Add event listeners for quantity changes and remove buttons
    document.querySelectorAll('.quantity-input').forEach(input => {
        input.addEventListener('change', (e) => {
            const newQuantity = parseInt(e.target.value);
            const productId = parseInt(e.target.dataset.productId);
            const variantId = e.target.dataset.variantId ? parseInt(e.target.dataset.variantId) : null;
            updateCartItemQuantity(productId, newQuantity, variantId);
            displayCartOnPage(); // Re-render cart
        });
    });

    document.querySelectorAll('.remove-item-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            const buttonEl = e.target.closest('button');
            const productId = parseInt(buttonEl.dataset.productId);
            const variantId = buttonEl.dataset.variantId ? parseInt(buttonEl.dataset.variantId) : null;
            removeFromCart(productId, variantId);
            displayCartOnPage(); // Re-render cart
        });
    });
}
*/

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
// updateCartDisplay is called internally and on DOMContentLoaded.

console.log("New cart.js loaded with full cart management logic.");