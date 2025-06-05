// website/source/js/cart.js

/**
 * Adds an item to the cart or updates its quantity.
 * @param {object} product - The product object from the API (should include id, name, price, main_image_url, aggregate_stock_quantity).
 * @param {number} quantity - The quantity to add.
 * @param {object} [variantInfo=null] - Optional variant information (e.g., { option_id, weight_grams, price, sku_suffix, aggregate_stock_quantity }).
 */
function addToCart(product, quantity, variantInfo = null) {
    if (!product || !product.id || quantity <= 0) {
        console.error("Invalid product or quantity for addToCart:", product, quantity);
        if (typeof showGlobalMessage === 'function') showGlobalMessage(t('cart.error.invalid_product_data', 'Données produit invalides.'), 'error');
        return;
    }

    let cart = getCartItems();
    const cartItemId = variantInfo ? `${product.id}-${variantInfo.option_id}` : product.id.toString();
    
    const existingItemIndex = cart.findIndex(item => item.id === cartItemId);
    
    let itemName = (getCurrentLanguage() === 'en' && product.name_en) ? product.name_en : product.name_fr;
    if (!itemName) itemName = product.name; // Fallback
    if (variantInfo && variantInfo.weight_grams) {
        itemName += ` (${variantInfo.weight_grams}g)`;
    }

    // Determine available stock for this specific item/variant
    const availableStock = variantInfo ? (variantInfo.aggregate_stock_quantity || 0) : (product.aggregate_stock_quantity || 0);

    if (existingItemIndex > -1) {
        // Item exists, check stock before updating quantity
        const newQuantity = cart[existingItemIndex].quantity + quantity;
        if (newQuantity > availableStock) {
            if (typeof showGlobalMessage === 'function') {
                showGlobalMessage(t('cart.error.stock_limit_exceeded_update', 'Stock insuffisant pour augmenter la quantité de {{itemName}}. Max: {{count}}.', { itemName: itemName, count: availableStock }), 'warning', 5000);
            }
            return; // Don't update if new quantity exceeds stock
        }
        cart[existingItemIndex].quantity = newQuantity;
    } else {
        // New item, check stock before adding
        if (quantity > availableStock) {
            if (typeof showGlobalMessage === 'function') {
                showGlobalMessage(t('cart.error.stock_limit_exceeded_add', 'Stock insuffisant pour {{itemName}}. Seulement {{count}} disponible(s).', { itemName: itemName, count: availableStock }), 'warning', 5000);
            }
            // Optionally, add only the available stock instead of none:
            // if (availableStock > 0) {
            //     quantity = availableStock; 
            //     showGlobalMessage(t('cart.info.quantity_adjusted_to_stock', 'Quantité ajustée au stock disponible pour {{itemName}}.', { itemName: itemName }), 'info', 4000);
            // } else {
            //     return; // Don't add if completely out of stock
            // }
            return; // For now, strictly prevent adding if requested > available
        }
        
        const cartItem = {
            id: cartItemId,
            productId: product.id, // Store base product ID
            name: itemName,
            price: variantInfo ? variantInfo.price : product.base_price,
            quantity: quantity,
            image: product.main_image_full_url || product.main_image_url || 'https://placehold.co/100x100/F5EEDE/11120D?text=Item',
            slug: product.slug, // For linking back to product page
            variantId: variantInfo ? variantInfo.option_id : null, // Store ProductWeightOption.id if variant
            variantLabel: variantInfo ? `${variantInfo.weight_grams}g` : null, // For display
            skuSuffix: variantInfo ? variantInfo.sku_suffix : null, // For backend processing
            availableStock: availableStock // Store current stock for reference (might get stale)
        };
        cart.push(cartItem);
    }

    saveCartItems(cart);
    updateCartDisplay(); // Update mini-cart, cart count in header
    if (typeof showCartToast === 'function') showCartToast(itemName, quantity); // Show "Added to cart" toast
    
    // If on cart page, refresh the full cart display
    if (document.body.id === 'page-panier') {
        displayCartOnPage();
    }
}


// --- Other Cart Functions (getCartItems, saveCartItems, updateCartDisplay, etc.) ---

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
        return []; // Return empty cart on error
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
        miniCartItemsContainer.innerHTML = ''; // Clear existing items

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
                        <p class="text-sm font-medium text-mt-near-black truncate">${item.name}</p>
                        <p class="text-xs text-mt-earth-brown">${item.quantity} x €${parseFloat(item.price).toFixed(2)}</p>
                    </div>
                    <span class="text-sm font-semibold text-mt-near-black ml-2">€${(item.quantity * item.price).toFixed(2)}</span>
                `;
                miniCartItemsContainer.appendChild(itemElement);
            });
            miniCartTotalElement.textContent = `€${totalPrice.toFixed(2)}`;
        }
    }
     // Update full cart page if currently on it
    if (document.body.id === 'page-panier') {
        displayCartOnPage();
    }
}



function displayCartOnPage() {
    const cartItems = getCartItems();
    const cartItemsContainer = document.getElementById('cart-items-container');
    const emptyCartMessage = document.getElementById('empty-cart-message');
    const cartSummaryContainer = document.getElementById('cart-summary-container');
    const cartSubtotalEl = document.getElementById('cart-subtotal');
    const cartTotalEl = document.getElementById('cart-total');

    if (!cartItemsContainer || !emptyCartMessage || !cartSummaryContainer || !cartSubtotalEl || !cartTotalEl) return;

    // Clear previous items, but preserve the emptyCartMessage element.
    Array.from(cartItemsContainer.children).forEach(child => {
        if (child !== emptyCartMessage) {
            cartItemsContainer.removeChild(child);
        }
    });


    if (cartItems.length === 0) {
        emptyCartMessage.style.display = 'block'; 
        cartSummaryContainer.style.display = 'none';
    } else {
        emptyCartMessage.style.display = 'none'; 
        cartItems.forEach(item => {
            const itemElement = document.createElement('div');
            itemElement.classList.add('cart-item'); 
            
            const img = document.createElement('img');
            img.src = item.image || 'https://placehold.co/80x80/F5EEDE/7D6A4F?text=Img';
            img.alt = item.name; // Alt text from item name
            img.className = 'cart-item-image';
            itemElement.appendChild(img);

            const infoDiv = document.createElement('div');
            infoDiv.className = 'flex-grow mx-4';
            
            const nameP = document.createElement('p');
            nameP.className = 'font-semibold text-brand-near-black';
            nameP.textContent = item.name; // XSS: Using textContent
            infoDiv.appendChild(nameP);

            const quantityControlsDiv = document.createElement('div');
            quantityControlsDiv.className = 'flex items-center mt-1';
            const innerQuantityDiv = document.createElement('div');
            innerQuantityDiv.className = 'quantity-input-controls flex items-center';

            const minusButton = document.createElement('button');
            minusButton.dataset.productId = item.id;
            minusButton.dataset.variantId = item.variantId || '';
            minusButton.dataset.change = "-1";
            minusButton.className = 'quantity-change-btn px-2 py-0.5 border border-brand-warm-taupe/50 text-brand-near-black hover:bg-brand-warm-taupe/20 text-sm rounded-l';
            minusButton.textContent = '-';
            innerQuantityDiv.appendChild(minusButton);

            const quantityInput = document.createElement('input');
            quantityInput.type = 'number';
            quantityInput.value = item.quantity;
            quantityInput.min = "1";
            quantityInput.max = "99";
            quantityInput.className = 'w-10 sm:w-12 text-center border-y border-brand-warm-taupe/50 py-1 text-sm appearance-none quantity-value-input';
            quantityInput.dataset.productId = item.id;
            quantityInput.dataset.variantId = item.variantId || '';
            quantityInput.readOnly = true;
            innerQuantityDiv.appendChild(quantityInput);

            const plusButton = document.createElement('button');
            plusButton.dataset.productId = item.id;
            plusButton.dataset.variantId = item.variantId || '';
            plusButton.dataset.change = "1";
            plusButton.className = 'quantity-change-btn px-2 py-0.5 border border-brand-warm-taupe/50 text-brand-near-black hover:bg-brand-warm-taupe/20 text-sm rounded-r';
            plusButton.textContent = '+';
            innerQuantityDiv.appendChild(plusButton);
            
            quantityControlsDiv.appendChild(innerQuantityDiv);
            infoDiv.appendChild(quantityControlsDiv);
            itemElement.appendChild(infoDiv);

            const priceDiv = document.createElement('div');
            priceDiv.className = 'text-right';
            const itemTotalP = document.createElement('p');
            itemTotalP.className = 'font-semibold text-brand-earth-brown';
            itemTotalP.textContent = `${(item.price * item.quantity).toFixed(2)} €`; // XSS: Price, safe
            priceDiv.appendChild(itemTotalP);

            const removeButton = document.createElement('button');
            removeButton.className = 'text-xs text-brand-truffle-burgundy hover:underline mt-1 remove-item-btn';
            removeButton.dataset.productId = item.id;
            removeButton.dataset.variantId = item.variantId || '';
            removeButton.textContent = t('public.cart.remove_item'); // XSS: Translated string, assumed safe
            priceDiv.appendChild(removeButton);
            
            itemElement.appendChild(priceDiv);
            cartItemsContainer.appendChild(itemElement);
        });

        const total = getCartTotal();
        cartSubtotalEl.textContent = `${total.toFixed(2)} €`; // XSS: Price, safe
        cartTotalEl.textContent = `${total.toFixed(2)} €`; // XSS: Price, safe
        cartSummaryContainer.style.display = 'block'; // md:flex based on Tailwind, block is fine.
    }

    // Re-attach event listeners for quantity and remove buttons
    document.querySelectorAll('.quantity-change-btn').forEach(button => {
        button.removeEventListener('click', handleQuantityChange); // Remove old listener first
        button.addEventListener('click', handleQuantityChange);
    });

    document.querySelectorAll('.remove-item-btn').forEach(button => {
        button.removeEventListener('click', handleRemoveItem); // Remove old listener first
        button.addEventListener('click', handleRemoveItem);
    });
}

function handleQuantityChange(e) {
    const btn = e.currentTarget;
    const productId = parseInt(btn.dataset.productId);
    const variantIdStr = btn.dataset.variantId;
    const variantId = variantIdStr && variantIdStr !== 'null' && variantIdStr !== 'undefined' ? parseInt(variantIdStr) : null;
    const change = parseInt(btn.dataset.change);
    const inputField = btn.parentElement.querySelector('.quantity-value-input');
    let currentQuantity = parseInt(inputField.value);
    let newQuantity = currentQuantity + change;
    if (newQuantity < 1 && change < 0) newQuantity = 0; 
    else if (newQuantity < 1) newQuantity = 1; 
    if (newQuantity > 99) newQuantity = 99; 
    
    if (newQuantity !== currentQuantity) { 
        updateCartItemQuantity(productId, newQuantity, variantId);
    }
}

function handleRemoveItem(e) {
    const btn = e.currentTarget;
    const productId = parseInt(btn.dataset.productId);
    const variantIdStr = btn.dataset.variantId;
    const variantId = variantIdStr && variantIdStr !== 'null' && variantIdStr !== 'undefined' ? parseInt(variantIdStr) : null;
    removeFromCart(productId, variantId);
}


document.addEventListener('DOMContentLoaded', () => {
    if (document.body.id === 'page-panier') { 
        initCartPage();
    }
    updateCartDisplay(); 
});

window.addToCart = addToCart;
window.removeFromCart = removeFromCart;
window.updateCartItemQuantity = updateCartItemQuantity;
window.getCartItems = getCartItems;
window.getCartTotal = getCartTotal;
window.getCartItemCount = getCartItemCount;
window.clearCart = clearCart;
window.initCartPage = initCartPage;
