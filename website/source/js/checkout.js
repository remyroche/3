// Maison Trüvra - Checkout Logic

document.addEventListener('DOMContentLoaded', () => {
    const paymentForm = document.getElementById('payment-form');
    const checkoutSummaryContainer = document.getElementById('checkout-summary-container');
    const paymentButtonAmount = document.getElementById('payment-amount-button');
    
    async function displayCheckoutSummary() {
        if (!checkoutSummaryContainer) return;

        const itemsContainer = document.getElementById('checkout-summary-items');
        const totalEl = document.getElementById('checkout-summary-total');
        // Maison Trüvra - Checkout Logic

document.addEventListener('DOMContentLoaded', () => {
    const paymentForm = document.getElementById('payment-form');
    const checkoutSummaryContainer = document.getElementById('checkout-summary-container');
    const paymentButtonAmount = document.getElementById('payment-amount-button');

    
    async function displayCheckoutSummary() {
        if (!checkoutSummaryContainer) return;

        const itemsContainer = document.getElementById('checkout-summary-items');
        const totalEl = document.getElementById('checkout-summary-total');
        
        if (!itemsContainer || !totalEl) return;

        const cartItems = getCartItems(); 
        itemsContainer.innerHTML = ''; 

        if (cartItems.length === 0) {
            const p = document.createElement('p');
            p.className = "text-gray-600";
            p.textContent = t('public.cart.empty_message'); // XSS: Translated string, assumed safe
            itemsContainer.appendChild(p);
            totalEl.textContent = '0.00 €';
            if(paymentButtonAmount) paymentButtonAmount.textContent = '0.00';
            const paymentButton = document.getElementById('submit-payment-button');
            if (paymentButton) {
                paymentButton.disabled = true;
                paymentButton.classList.add('opacity-50', 'cursor-not-allowed');
            }
            return;
        }

        cartItems.forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.classList.add('flex', 'justify-between', 'text-sm', 'text-gray-600', 'py-1');
            
            const nameSpan = document.createElement('span');
            nameSpan.textContent = `${item.name} (x${item.quantity})`; // XSS: item.name set via textContent
            itemDiv.appendChild(nameSpan);

            const priceSpan = document.createElement('span');
            priceSpan.textContent = `${(item.price * item.quantity).toFixed(2)} €`; // XSS: Price, safe
            itemDiv.appendChild(priceSpan);
            
            itemsContainer.appendChild(itemDiv);
        });

        const cartTotal = getCartTotal(); 
        totalEl.textContent = `${cartTotal.toFixed(2)} €`; // XSS: Price, safe
        if(paymentButtonAmount) paymentButtonAmount.textContent = cartTotal.toFixed(2); // XSS: Price, safe
        const paymentButton = document.getElementById('submit-payment-button');
        if (paymentButton) {
            paymentButton.disabled = false;
            paymentButton.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    }

    if (paymentForm) {
        paymentForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            showGlobalMessage(t('public.js.order_processing'), 'info', 10000);  // Key: public.js.order_processing
            const paymentButton = document.getElementById('submit-payment-button');
            if (paymentButton) paymentButton.disabled = true;
            const paymentMessageEl = document.getElementById('payment-message');
            if(paymentMessageEl) paymentMessageEl.textContent = '';

            // --- Fallback/Simulation ---
            console.warn("SIMULATION: Stripe payment not integrated. Proceeding with simulated order creation."); // Dev-facing
            await new Promise(resolve => setTimeout(resolve, 1500)); 
            const simulatedPaymentIntent = { 
                id: `sim_maison_truvra_${new Date().getTime()}`, 
                status: 'succeeded', 
                amount: Math.round(getCartTotal() * 100), 
                currency: 'eur'
            }; 
            await createOrderOnBackend(simulatedPaymentIntent);
            // --- End Fallback/Simulation ---
        });
    }

    async function createOrderOnBackend(paymentResult) {
        const paymentButton = document.getElementById('submit-payment-button');
        const paymentMessageEl = document.getElementById('payment-message');
        const cartItems = getCartItems(); 

        if (cartItems.length === 0) {
            showGlobalMessage(t('public.js.cart_is_empty_redirecting'), "error"); // Key: public.js.cart_is_empty_redirecting
            if (paymentButton) paymentButton.disabled = false;
            return;
        }

        const shippingAddressString = localStorage.getItem('shippingAddress');
        const billingAddressString = localStorage.getItem('billingAddress');
        let shippingAddress, billingAddress;

        try {
            shippingAddress = shippingAddressString ? JSON.parse(shippingAddressString) : null;
            billingAddress = billingAddressString ? JSON.parse(billingAddressString) : shippingAddress;
        } catch (e) {
            showGlobalMessage(t('global.error_generic'), "error"); // Key: global.error_generic
            if (paymentButton) paymentButton.disabled = false;
            return;
        }

        if (!shippingAddress || !shippingAddress.address_line1 || !shippingAddress.city || !shippingAddress.postal_code || !shippingAddress.country || !shippingAddress.first_name || !shippingAddress.last_name) {
            showGlobalMessage(t('public.js.missing_shipping_info'), "error"); // Key: public.js.missing_shipping_info
            if (paymentButton) paymentButton.disabled = false;
            return;
        }
        if (billingAddress !== shippingAddress && (!billingAddress || !billingAddress.address_line1 || !billingAddress.city || !billingAddress.postal_code || !billingAddress.country || !billingAddress.first_name || !billingAddress.last_name)) {
            showGlobalMessage(t('public.js.missing_billing_info'), "error"); // New key: public.js.missing_billing_info
            if (paymentButton) paymentButton.disabled = false;
            return;
        }

        const currentUser = getCurrentUser(); 
        const orderData = {
            items: cartItems.map(item => ({
                product_id: item.id,
                variant_id: item.variantId || null,
                quantity: item.quantity,
            })),
            currency: 'EUR', // Should ideally come from config or cart
            shipping_address: shippingAddress,
            billing_address: billingAddress,
            payment_details: { 
                method: 'stripe_simulation', 
                transaction_id: paymentResult.id, 
                status: paymentResult.status,
                amount_captured: paymentResult.amount / 100 
            },
            customer_email: currentUser ? currentUser.email : (shippingAddress.email || t('public.js.email_not_provided')), // New key: public.js.email_not_provided
        };

        try {
            const orderCreationResponse = await makeApiRequest('/orders/create', 'POST', orderData, !!currentUser); 
            showGlobalMessage(orderCreationResponse.message || t('public.confirmation.success_message'), "success"); // Key: public.confirmation.success_message
            clearCart(); 
            localStorage.setItem('lastOrderId', orderCreationResponse.order_id);
            localStorage.setItem('lastOrderTotal', orderCreationResponse.total_amount.toFixed(2)); 
            localStorage.removeItem('shippingAddress');
            localStorage.removeItem('billingAddress');
            window.location.href = 'confirmation-commande.html'; 
        } catch (error) {
            const errorMessage = error.data?.message || t('public.js.order_creation_failed'); // Key: public.js.order_creation_failed
            showGlobalMessage(errorMessage, "error");
            if(paymentMessageEl) paymentMessageEl.textContent = `${t('global.error_generic')}: ${errorMessage}`;
            if (paymentButton) paymentButton.disabled = false;
        }
    }

    if (document.body.id === 'page-paiement' || (document.body.id === 'page-checkout' && checkoutSummaryContainer)) { // Assuming page-paiement is the correct ID
        const cartItems = getCartItems();
        if (cartItems.length === 0 && window.location.pathname.includes('payment.html')) { // Or checkout.html
            showGlobalMessage(t('public.js.cart_is_empty_redirecting'), "info");
            setTimeout(() => { window.location.href = 'nos-produits.html'; }, 2000);
        } else {
            displayCheckoutSummary();
        }
    }
});

function initializeCheckoutPage() { // Called from main.js for page-paiement
    const shippingAddress = JSON.parse(localStorage.getItem('shippingAddress'));
    if (!shippingAddress && (window.location.pathname.includes('payment.html') || window.location.pathname.includes('checkout.html'))) {
        showGlobalMessage(t('public.js.missing_shipping_info_redirect_checkout'), "error"); // New key: public.js.missing_shipping_info_redirect_checkout (e.g., "Shipping info missing. Please complete address first. Redirecting...")
    }
}

function initializeConfirmationPage() { // Called from main.js for page-confirmation-commande
    const orderIdEl = document.getElementById('confirmation-order-id');
    const totalAmountEl = document.getElementById('confirmation-total-amount');
    const lastOrderId = localStorage.getItem('lastOrderId');
    const lastOrderTotal = localStorage.getItem('lastOrderTotal');

    if (orderIdEl && totalAmountEl && lastOrderId && lastOrderTotal) {
        orderIdEl.textContent = lastOrderId; // XSS: Order ID, generally safe (numeric/specific format)
        totalAmountEl.textContent = `${lastOrderTotal} €`; // XSS: Price, safe
        localStorage.removeItem('lastOrderId');
        localStorage.removeItem('lastOrderTotal');
    } else if (orderIdEl) { 
        orderIdEl.textContent = t('common.notApplicable'); // XSS: Translated string, assumed safe
        if(totalAmountEl) totalAmountEl.textContent = t('common.notApplicable');
        const confirmationMessageEl = document.getElementById('confirmation-message');
        if(confirmationMessageEl) confirmationMessageEl.textContent = t('public.js.order_details_not_found'); // XSS: Translated string, assumed safe
    }
}
