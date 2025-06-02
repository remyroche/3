// Maison Trüvra - Checkout Logic
// This file handles the checkout process, including form validation,
// order summary display, and eventually payment processing and order creation.

// Ensure this script is loaded after config.js, api.js, cart.js, auth.js, ui.js

document.addEventListener('DOMContentLoaded', () => {
    const paymentForm = document.getElementById('payment-form');
    const checkoutSummaryContainer = document.getElementById('checkout-summary-container');
    const paymentButtonAmount = document.getElementById('payment-amount-button');
    
    // TODO: Stripe.js Integration
    // let stripe; 
    // let cardElement;// Maison Trüvra - Checkout Logic

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
            itemsContainer.innerHTML = `<p class="text-gray-600">${t('public.cart.empty_message')}</p>`;
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
            itemDiv.innerHTML = `
                <span>${item.name} (x${item.quantity})</span>
                <span>${(item.price * item.quantity).toFixed(2)} €</span>
            `;
            itemsContainer.appendChild(itemDiv);
        });

        const cartTotal = getCartTotal(); 
        totalEl.textContent = `${cartTotal.toFixed(2)} €`;
        if(paymentButtonAmount) paymentButtonAmount.textContent = cartTotal.toFixed(2);
        const paymentButton = document.getElementById('submit-payment-button');
        if (paymentButton) {
            paymentButton.disabled = false;
            paymentButton.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    }

    if (paymentForm) {
        paymentForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            showGlobalMessage(t('public.js.order_processing'), 'info', 10000); 
            const paymentButton = document.getElementById('submit-payment-button');
            if (paymentButton) paymentButton.disabled = true;
            const paymentMessageEl = document.getElementById('payment-message');
            if(paymentMessageEl) paymentMessageEl.textContent = '';

            // --- Fallback/Simulation ---
            console.warn("SIMULATION: Stripe payment not integrated. Proceeding with simulated order creation.");
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
            showGlobalMessage(t('public.js.cart_is_empty_redirecting'), "error");
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
            showGlobalMessage(t('global.error_generic'), "error"); // Generic error for parsing
            if (paymentButton) paymentButton.disabled = false;
            return;
        }

        if (!shippingAddress || !shippingAddress.address_line1 || !shippingAddress.city || !shippingAddress.postal_code || !shippingAddress.country || !shippingAddress.first_name || !shippingAddress.last_name) {
            showGlobalMessage(t('public.js.missing_shipping_info'), "error");
            if (paymentButton) paymentButton.disabled = false;
            return;
        }
        if (billingAddress !== shippingAddress && (!billingAddress || !billingAddress.address_line1 || !billingAddress.city || !billingAddress.postal_code || !billingAddress.country || !billingAddress.first_name || !billingAddress.last_name)) {
            showGlobalMessage(t('public.js.missing_shipping_info'), "error"); // Assuming same message for billing
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
            currency: 'EUR',
            shipping_address: shippingAddress,
            billing_address: billingAddress,
            payment_details: { 
                method: 'stripe_simulation', 
                transaction_id: paymentResult.id, 
                status: paymentResult.status,
                amount_captured: paymentResult.amount / 100 
            },
            customer_email: currentUser ? currentUser.email : shippingAddress.email,
        };

        try {
            const orderCreationResponse = await makeApiRequest('/orders/create', 'POST', orderData, !!currentUser); 
            showGlobalMessage(orderCreationResponse.message || t('public.confirmation.success_message'), "success");
            clearCart(); 
            localStorage.setItem('lastOrderId', orderCreationResponse.order_id);
            localStorage.setItem('lastOrderTotal', orderCreationResponse.total_amount.toFixed(2)); 
            localStorage.removeItem('shippingAddress');
            localStorage.removeItem('billingAddress');
            window.location.href = 'confirmation-commande.html'; 
        } catch (error) {
            showGlobalMessage(error.message || t('public.js.order_creation_failed'), "error");
            if(paymentMessageEl) paymentMessageEl.textContent = `${t('global.error_generic')}: ${error.message || t('public.js.order_creation_failed')}`;
            if (paymentButton) paymentButton.disabled = false;
        }
    }

    if (document.getElementById('payment-form') || checkoutSummaryContainer) {
        const cartItems = getCartItems();
        if (cartItems.length === 0 && window.location.pathname.includes('payment.html')) {
            showGlobalMessage(t('public.js.cart_is_empty_redirecting'), "info");
            setTimeout(() => { window.location.href = 'nos-produits.html'; }, 2000);
        } else {
            displayCheckoutSummary();
        }
    }
});

function initializeCheckoutPage() {
    const shippingAddress = JSON.parse(localStorage.getItem('shippingAddress'));
    if (!shippingAddress && window.location.pathname.includes('payment.html')) {
        showGlobalMessage(t('public.js.missing_shipping_info'), "error");
    }
}

function initializeConfirmationPage() {
    const orderIdEl = document.getElementById('confirmation-order-id');
    const totalAmountEl = document.getElementById('confirmation-total-amount');
    const lastOrderId = localStorage.getItem('lastOrderId');
    const lastOrderTotal = localStorage.getItem('lastOrderTotal');

    if (orderIdEl && totalAmountEl && lastOrderId && lastOrderTotal) {
        orderIdEl.textContent = lastOrderId;
        totalAmountEl.textContent = `${lastOrderTotal} €`;
        localStorage.removeItem('lastOrderId');
        localStorage.removeItem('lastOrderTotal');
    } else if (orderIdEl) { 
        orderIdEl.textContent = 'N/A';
        if(totalAmountEl) totalAmountEl.textContent = 'N/A';
        const confirmationMessageEl = document.getElementById('confirmation-message');
        if(confirmationMessageEl) confirmationMessageEl.textContent = t('public.js.order_details_not_found');
    }
}
