// Maison Trüvra - Shopping Cart Management
const CART_STORAGE_KEY = 'maisonTruvraCart';

function loadCart() {
    const cartJson = localStorage.getItem(CART_STORAGE_KEY);
    try {
        return cartJson ? JSON.parse(cartJson) : [];
    } catch (e) {
        console.error("Error parsing cart from localStorage:", e);
        return [];
    }
}

function saveCart(cartItems) {
    try {
        const cartJson = JSON.stringify(cartItems);
        localStorage.setItem(CART_STORAGE_KEY, cartJson);
    } catch (e) {
        console.error("Error saving cart to localStorage:", e);
    }
}

function addToCart(product, quantity = 1, variantInfo = null) {
    if (!product || !product.id || !product.name || (variantInfo ? !variantInfo.price : !product.base_price)) {
        showGlobalMessage(t('public.js.invalid_product_data'), "error");
        return;
    }

    const cart = loadCart();
    const itemPrice = variantInfo ? variantInfo.price : product.base_price;
    const itemName = variantInfo ? `${product.name} (${variantInfo.weight_grams}g)` : product.name;
    const itemSkuSuffix = variantInfo ? variantInfo.sku_suffix : null;
    const itemVariantId = variantInfo ? variantInfo.id : null;
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
                name: itemName,
                price: parseFloat(itemPrice),
                quantity: quantity,
                skuPrefix: product.sku_prefix,
                skuSuffix: itemSkuSuffix,
                image: itemMainImage,
                slug: product.slug
            });
        }
    }

    saveCart(cart);
    updateCartDisplay();
    showGlobalMessage(t('public.js.added_to_cart_toast', { qty: quantity, name: itemName }), "success");
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
        showGlobalMessage(t('public.js.item_removed_from_cart'), "info");
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
            cart.splice(itemIndex, 1);
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
    showGlobalMessage(t('public.js.cart_cleared'), "info");
}

function updateCartDisplay() {
    if (typeof updateCartIcon === 'function') {
        updateCartIcon(); 
    }
    if (document.body.id === 'page-panier' && typeof initCartPage === 'function') {
        initCartPage();
    }
    if (document.body.id === 'page-paiement' && typeof displayCheckoutSummary === 'function') {
        displayCheckoutSummary();
    }
}

function initCartPage() {
    const cartLoginPrompt = document.getElementById('cart-login-prompt');
    const cartContentWrapper = document.getElementById('cart-content-wrapper');

    if (!cartLoginPrompt || !cartContentWrapper) return;

    if (typeof isUserLoggedIn !== 'function') {
        cartLoginPrompt.style.display = 'block'; 
        cartContentWrapper.style.display = 'none';
        return;
    }

    if (isUserLoggedIn()) {
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

    cartItemsContainer.innerHTML = ''; 

    if (cartItems.length === 0) {
        emptyCartMessage.style.display = 'block';
        cartSummaryContainer.style.display = 'none';
    } else {
        emptyCartMessage.style.display = 'none';
        cartItems.forEach(item => {
            const itemElement = document.createElement('div');
            itemElement.classList.add('cart-item'); 
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
        cartSummaryContainer.style.display = 'block'; 
    }

    document.querySelectorAll('.quantity-change-btn').forEach(button => {
        button.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            const productId = parseInt(btn.dataset.productId);
            const variantId = btn.dataset.variantId ? parseInt(btn.dataset.variantId) : null;
            const change = parseInt(btn.dataset.change);
            const inputField = btn.parentElement.querySelector('.quantity-value-input');
            let currentQuantity = parseInt(inputField.value);
            let newQuantity = currentQuantity + change;
            if (newQuantity < 1) newQuantity = 1; 
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
            const variantId = btn.dataset.variantId ? parseInt(btn.dataset.variantId) : null;
            removeFromCart(productId, variantId);
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
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
