// Maison Trüvra - Shopping Cart Management
const CART_STORAGE_KEY = 'maisonTruvraCart';

function loadCart() {
    const cartJson = localStorage.getItem(CART_STORAGE_KEY);
    try {
        return cartJson ? JSON.parse(cartJson) : [];
    } catch (e) {
        console.error("Error parsing cart from localStorage:", e); // Dev-facing
        return [];
    }
}

function saveCart(cartItems) {
    try {
        const cartJson = JSON.stringify(cartItems);
        localStorage.setItem(CART_STORAGE_KEY, cartJson);
    } catch (e) {
        console.error("Error saving cart to localStorage:", e); // Dev-facing
    }
}

function addToCart(product, quantity = 1, variantInfo = null) {
    if (!product || !product.id || !product.name || (variantInfo ? typeof variantInfo.price !== 'number' : typeof product.base_price !== 'number')) {
        showGlobalMessage(t('public.js.invalid_product_data'), "error"); // Key: public.js.invalid_product_data
        return;
    }

    const cart = loadCart();
    const itemPrice = variantInfo ? variantInfo.price : product.base_price;
    const itemName = variantInfo ? `${product.name} (${variantInfo.weight_grams}g)` : product.name;
    const itemSkuSuffix = variantInfo ? variantInfo.sku_suffix : null;
    const itemVariantId = variantInfo ? variantInfo.id : null; // Assuming variantInfo has an 'id' if it's a variant from DB
    const itemMainImage = product.main_image_full_url || product.image_url_main || 'https://placehold.co/100x100/eee/ccc?text=Image';

    const existingItemIndex = cart.findIndex(item => 
        item.id === product.id && 
        (itemVariantId ? item.variantId === itemVariantId : !item.variantId)
    );

    if (existingItemIndex > -1) {
        cart[existingItemIndex].quantity += quantity;
        if (cart[existingItemIndex].quantity <= 0) {
            cart.splice(existingItemIndex, 1);
        }
    } else {
        if (quantity > 0) {
            cart.push({
                id: product.id,
                variantId: itemVariantId,
                name: itemName, // This name includes weight if applicable, used for display
                price: parseFloat(itemPrice),
                quantity: quantity,
                skuPrefix: product.sku_prefix, // Or product.product_code after refactor
                skuSuffix: itemSkuSuffix,
                image: itemMainImage,
                slug: product.slug
            });
        }
    }

    saveCart(cart);
    updateCartDisplay();
    
    // For dynamic messages like this, direct string construction is often clearer if t() doesn't handle placeholders well with build.js
    // Option 1: Using a template key if your build.js and locale files support it (e.g. %qty% x %name% added to cart!)
    // let message = t('public.js.added_to_cart_toast'); 
    // message = message.replace('%qty%', quantity).replace('%name%', itemName);
    // showGlobalMessage(message, "success");
    // Option 2: Simpler, construct in JS with a translated suffix
    showGlobalMessage(`${quantity} x ${itemName} ${t('public.js.added_to_cart_suffix')}`, "success"); 
    // New key: public.js.added_to_cart_suffix (e.g., "added to cart!" or "ajouté(s) au panier !")
}

function removeFromCart(productId, variantId = null) {
    let cart = loadCart();
    const initialLength = cart.length;
    cart = cart.filter(item => 
        !(item.id === productId && (variantId ? item.variantId === variantId : !item.variantId))
    );

    if (cart.length < initialLength) {
        saveCart(cart);
        updateCartDisplay();
        showGlobalMessage(t('public.js.item_removed_from_cart'), "info"); // Key: public.js.item_removed_from_cart
    }
}

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
            cart.splice(itemIndex, 1); // Remove if quantity is zero or less
        }
        saveCart(cart);
        updateCartDisplay();
        // Optional: showGlobalMessage(t('public.js.cart_updated'), "info"); // New key: public.js.cart_updated
    }
}

function getCartItems() {
    return loadCart();
}

function getCartTotal() {
    const cart = loadCart();
    return cart.reduce((total, item) => total + (item.price * item.quantity), 0);
}

function getCartItemCount() {
    const cart = loadCart();
    return cart.reduce((count, item) => count + item.quantity, 0);
}

function clearCart() {
    localStorage.removeItem(CART_STORAGE_KEY);
    updateCartDisplay();
    showGlobalMessage(t('public.js.cart_cleared'), "info"); // Key: public.js.cart_cleared
}

function updateCartDisplay() {
    if (typeof updateCartIcon === 'function') { // from ui.js
        updateCartIcon(); 
    }
    // If on the cart page, refresh its content
    if (document.body.id === 'page-panier' && typeof initCartPage === 'function') {
        initCartPage();
    }
    // If on the payment page, refresh its summary
    if (document.body.id === 'page-paiement' && typeof displayCheckoutSummary === 'function') { // from checkout.js
        displayCheckoutSummary();
    }
}

// Initialize or update cart display when the cart page is loaded
function initCartPage() {
    const cartLoginPrompt = document.getElementById('cart-login-prompt');
    const cartContentWrapper = document.getElementById('cart-content-wrapper');

    if (!cartLoginPrompt || !cartContentWrapper) return;

    // Assuming isUserLoggedIn is globally available from auth.js
    if (typeof isUserLoggedIn === 'function' && isUserLoggedIn()) {
        cartLoginPrompt.style.display = 'none';
        cartContentWrapper.style.display = 'block'; 
        displayCartOnPage(); 
    } else {
        cartLoginPrompt.style.display = 'block';
        cartContentWrapper.style.display = 'none';
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

    // Clear previous items, but keep the empty message element if it's part of the static HTML.
    // If emptyCartMessage is dynamically added, this clear is fine.
    // Assuming emptyCartMessage is static and its display is toggled.
    while (cartItemsContainer.firstChild && cartItemsContainer.firstChild !== emptyCartMessage) {
        cartItemsContainer.removeChild(cartItemsContainer.firstChild);
    }


    if (cartItems.length === 0) {
        emptyCartMessage.style.display = 'block'; // Show empty message
        if (cartItemsContainer.children.length > 1) { // If other items were there, clear them (safety)
            cartItemsContainer.innerHTML = ''; // Clear fully
            cartItemsContainer.appendChild(emptyCartMessage); // Re-add if needed
        }
        cartSummaryContainer.style.display = 'none';
    } else {
        emptyCartMessage.style.display = 'none'; // Hide empty message
        cartItems.forEach(item => {
            const itemElement = document.createElement('div');
            itemElement.classList.add('cart-item'); 
            // The t('public.cart.remove_item') will be replaced by build.js
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
                        ${t('public.cart.remove_item')} 
                    </button>
                </div>
            `;
            cartItemsContainer.appendChild(itemElement);
        });

        const total = getCartTotal();
        cartSubtotalEl.textContent = `${total.toFixed(2)} €`;
        cartTotalEl.textContent = `${total.toFixed(2)} €`; 
        cartSummaryContainer.style.display = 'block'; // md:flex based on Tailwind, block is fine.
    }

    // Re-attach event listeners for quantity and remove buttons
    document.querySelectorAll('.quantity-change-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            const productId = parseInt(btn.dataset.productId);
            // Ensure variantId is correctly parsed or null
            const variantIdStr = btn.dataset.variantId;
            const variantId = variantIdStr && variantIdStr !== 'null' && variantIdStr !== 'undefined' ? parseInt(variantIdStr) : null;

            const change = parseInt(btn.dataset.change);
            const inputField = btn.parentElement.querySelector('.quantity-value-input');
            let currentQuantity = parseInt(inputField.value);
            let newQuantity = currentQuantity + change;
            if (newQuantity < 1 && change < 0) newQuantity = 0; // Allow reducing to 0 to remove
            else if (newQuantity < 1) newQuantity = 1; // Don't go below 1 if incrementing from 0 or direct set
            if (newQuantity > 99) newQuantity = 99; 
            
            if (newQuantity !== currentQuantity) { 
                updateCartItemQuantity(productId, newQuantity, variantId);
            }
        });
    });

    document.querySelectorAll('.remove-item-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            const productId = parseInt(btn.dataset.productId);
            const variantIdStr = btn.dataset.variantId;
            const variantId = variantIdStr && variantIdStr !== 'null' && variantIdStr !== 'undefined' ? parseInt(variantIdStr) : null;
            removeFromCart(productId, variantId);
        });
    });
}

// Initial display update on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    if (document.body.id === 'page-panier') { // Only run initCartPage if on the cart page
        initCartPage();
    }
    updateCartDisplay(); // Update icon globally
});

// Expose functions to global scope if not using modules
window.addToCart = addToCart;
window.removeFromCart = removeFromCart;
window.updateCartItemQuantity = updateCartItemQuantity;
window.getCartItems = getCartItems;
window.getCartTotal = getCartTotal;
window.getCartItemCount = getCartItemCount;
window.clearCart = clearCart;
window.initCartPage = initCartPage;
