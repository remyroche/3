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
    
    showGlobalMessage(`${quantity} x ${itemName} ${t('public.js.added_to_cart_suffix')}`, "success"); 
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
    if (document.body.id === 'page-panier' && typeof initCartPage === 'function') {
        initCartPage();
    }
    if (document.body.id === 'page-paiement' && typeof displayCheckoutSummary === 'function') { // from checkout.js
        displayCheckoutSummary();
    }
}

function initCartPage() {
    const cartLoginPrompt = document.getElementById('cart-login-prompt');
    const cartContentWrapper = document.getElementById('cart-content-wrapper');

    if (!cartLoginPrompt || !cartContentWrapper) return;

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
