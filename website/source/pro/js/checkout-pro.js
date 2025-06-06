//
// --- website/source/pro/js/checkout-pro.js ---
// Manages the professional B2B payment and checkout page.
//

// Assumes B2B_CART_STORAGE_KEY is available globally or defined here
const B2B_CART_STORAGE_KEY_CHECKOUT = 'maisonTruvraB2BCart';

document.addEventListener('DOMContentLoaded', () => {
    // This script is for 'page-payment-pro'
    if (document.body.id !== 'page-payment-pro') {
        return;
    }

    // --- Authentication & Authorization Check ---
    const currentUser = typeof getCurrentUser === 'function' ? getCurrentUser() : null;
    if (!currentUser || currentUser.role !== 'b2b_professional' || currentUser.professional_status !== 'approved') {
        if (typeof showGlobalMessage === 'function') {
            showGlobalMessage('Accès réservé. Redirection...', 'error');
        }
        setTimeout(() => { window.location.href = 'professionnels.html'; }, 3000);
        return;
    }

    const cartItems = getB2BCartItemsCheckout();
    if (cartItems.length === 0) {
        if (typeof showGlobalMessage === 'function') {
            showGlobalMessage('Votre panier est vide. Redirection...', 'info');
        }
        setTimeout(() => { window.location.href = 'marchedespros.html'; }, 2000);
        return;
    }

    // --- Page Initialization ---
    displayB2BPaymentSummary();
    setupB2BPaymentForm();
});

/**
 * Retrieves B2B cart items from localStorage for the checkout page.
 * @returns {Array} The array of cart items.
 */
function getB2BCartItemsCheckout() {
    try {
        const cartJson = localStorage.getItem(B2B_CART_STORAGE_KEY_CHECKOUT);
        return cartJson ? JSON.parse(cartJson) : [];
    } catch (e) {
        console.error("Error parsing B2B cart for checkout from localStorage:", e);
        return [];
    }
}

/**
 * Displays the final order summary on the payment page, including discounts.
 */
async function displayB2BPaymentSummary() {
    const summaryContainer = document.getElementById('payment-cart-items-summary');
    const subtotalEl = document.getElementById('payment-summary-subtotal-ht');
    const discountLabelEl = document.getElementById('payment-partnership-discount-label');
    const discountAmountEl = document.getElementById('payment-partnership-discount-amount');
    const discountContainerEl = document.getElementById('payment-partnership-discount-display');
    const vatEl = document.getElementById('payment-summary-vat');
    const totalEl = document.getElementById('payment-summary-total-ttc');
    const payButtonAmountEl = document.getElementById('payment-total-button-amount');

    if (!summaryContainer || !subtotalEl || !totalEl) {
        console.error("One or more summary elements are missing from payment-pro.html");
        return;
    }

    const cartItems = getB2BCartItemsCheckout();
    summaryContainer.innerHTML = ''; // Clear loading message

    if (cartItems.length === 0) {
        summaryContainer.textContent = 'Aucun article à payer.';
        return;
    }

    let subtotalHT = 0;
    cartItems.forEach(item => {
        subtotalHT += item.price * item.quantity;
        const itemDiv = document.createElement('div');
        itemDiv.className = 'flex justify-between items-center text-sm py-1';
        itemDiv.innerHTML = `
            <span class="flex-grow pr-2 truncate" title="${item.name}">${item.quantity} x ${item.name}</span>
            <span class="font-medium">€${(item.price * item.quantity).toFixed(2)}</span>
        `;
        summaryContainer.appendChild(itemDiv);
    });

    subtotalEl.textContent = `€${subtotalHT.toFixed(2)}`;

    // In a real scenario, discount should be validated via API.
    // Here we'll simulate based on stored user info.
    const currentUser = typeof getCurrentUser === 'function' ? getCurrentUser() : null;
    let discountPercent = 0; // Fetch or calculate discount for user's tier
    let discountAmount = 0;
    
    // This is a placeholder for fetching real-time discount info
    if (currentUser && currentUser.b2b_tier) {
       // A mapping of tier to discount % would be needed here, or an API call.
       // Example: const tierDiscounts = { 'gold': 5, 'platinum': 8 };
       // discountPercent = tierDiscounts[currentUser.b2b_tier] || 0;
    }
    
    if (discountPercent > 0) {
        discountAmount = subtotalHT * (discountPercent / 100);
        if(discountContainerEl) discountContainerEl.classList.remove('hidden');
        if(discountLabelEl) discountLabelEl.textContent = `Remise Partenaire (${currentUser.b2b_tier} -${discountPercent}%) :`;
        if(discountAmountEl) discountAmountEl.textContent = `-€${discountAmount.toFixed(2)}`;
    } else {
        if(discountContainerEl) discountContainerEl.classList.add('hidden');
    }

    const totalAfterDiscount = subtotalHT - discountAmount;
    const estimatedVAT = totalAfterDiscount * 0.20; // Assuming 20% VAT
    const finalTotalTTC = totalAfterDiscount + estimatedVAT;

    if (vatEl) vatEl.textContent = `€${estimatedVAT.toFixed(2)}`;
    if (totalEl) totalEl.textContent = `€${finalTotalTTC.toFixed(2)}`;
    if (payButtonAmountEl) payButtonAmountEl.textContent = `€${finalTotalTTC.toFixed(2)}`;
}


/**
 * Sets up the event listener for the B2B payment form submission.
 */
function setupB2BPaymentForm() {
    const paymentForm = document.getElementById('payment-form');
    if (paymentForm) {
        paymentForm.addEventListener('submit', handleB2BPayment);
    }
}

/**
 * Handles the (simulated) payment process and creates the B2B order on the backend.
 * @param {Event} event - The form submission event.
 */
async function handleB2BPayment(event) {
    event.preventDefault();
    const submitBtn = document.getElementById('submit-payment-btn');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> Traitement...`;

    if (typeof showGlobalMessage === 'function') {
        showGlobalMessage('Traitement de votre commande professionnelle...', 'info');
    }

    const cartItems = getB2BCartItemsCheckout();
    const orderData = {
        is_b2b_order: true,
        items: cartItems.map(item => ({
            product_id: item.productId,
            variant_id: item.variantId,
            quantity: item.quantity,
            price_at_purchase: item.price
        })),
        // The backend will calculate final totals with verified discounts and taxes
    };

    try {
        // In a real implementation, you would get a payment token from Stripe/etc. first
        // and include it in the orderData payload.
        // For now, we simulate success and go straight to order creation.
        
        const response = await makeApiRequest('/api/orders/create', 'POST', orderData, true);
        if (response.success) {
            if (typeof showGlobalMessage === 'function') showGlobalMessage('Commande B2B créée avec succès !', 'success');
            localStorage.removeItem(B2B_CART_STORAGE_KEY_CHECKOUT); // Clear cart on success
            // Redirect to a professional-specific confirmation page or dashboard
            window.location.href = `confirmation-commande.html?order_id=${response.order_id}`;
        }
    } catch (error) {
        console.error("B2B Order creation error:", error);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
    }
}
