// Maison Trüvra - Checkout Logic
// This file handles the checkout process, including form validation,
// order summary display, and eventually payment processing and order creation.

// Ensure this script is loaded after config.js, api.js, cart.js, auth.js, ui.js

document.addEventListener('DOMContentLoaded', () => {
    const paymentForm = document.getElementById('payment-form');
    const checkoutSummaryContainer = document.getElementById('checkout-summary-container');
    const paymentButtonAmount = document.getElementById('payment-amount-button');
    // Stripe related variables (placeholders, to be initialized with Stripe.js)
    // let stripe; 
    // let cardElement;

    // Initialize Stripe (Placeholder - requires Stripe.js and publishable key)
    /*
    async function initializeStripe() {
        try {
            // stripe = Stripe('YOUR_STRIPE_PUBLISHABLE_KEY'); // Replace with your actual key
            // const elements = stripe.elements();
            // cardElement = elements.create('card', { hidePostalCode: true }); // Customize as needed
            // cardElement.mount('#card-element-placeholder'); // Mount to the div in payment.html

            // cardElement.on('change', (event) => {
            //     const displayError = document.getElementById('card-errors');
            //     if (event.error) {
            //         displayError.textContent = event.error.message;
            //     } else {
            //         displayError.textContent = '';
            //     }
            // });
            console.log("Stripe (simulated) initialized. Card element would be mounted.");
        } catch (error) {
            console.error("Failed to initialize Stripe:", error);
            showGlobalMessage("Erreur d'initialisation du module de paiement.", "error");
        }
    }
    */

    // Display Order Summary
    async function displayCheckoutSummary() {
        if (!checkoutSummaryContainer) return;

        const itemsContainer = document.getElementById('checkout-summary-items');
        const totalEl = document.getElementById('checkout-summary-total');
        
        if (!itemsContainer || !totalEl) {
            console.error("Checkout summary elements not found in payment.html");
            return;
        }

        const cartItems = await getCartItems(); // From cart.js
        itemsContainer.innerHTML = ''; // Clear previous items

        if (cartItems.length === 0) {
            itemsContainer.innerHTML = '<p class="text-gray-600">Votre panier est vide.</p>';
            totalEl.textContent = '0.00 €';
            if(paymentButtonAmount) paymentButtonAmount.textContent = '0.00';
            // Disable payment button if cart is empty
            const paymentButton = document.getElementById('submit-payment-button');
            if (paymentButton) paymentButton.disabled = true;
            return;
        }

        cartItems.forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.classList.add('flex', 'justify-between', 'text-sm', 'text-gray-600');
            itemDiv.innerHTML = `
                <span>${item.name} (x${item.quantity})</span>
                <span>${(item.price * item.quantity).toFixed(2)} €</span>
            `;
            itemsContainer.appendChild(itemDiv);
        });

        const cartTotal = getCartTotal(); // From cart.js
        totalEl.textContent = `${cartTotal.toFixed(2)} €`;
        if(paymentButtonAmount) paymentButtonAmount.textContent = cartTotal.toFixed(2);
        const paymentButton = document.getElementById('submit-payment-button');
        if (paymentButton) paymentButton.disabled = false;
    }


    if (paymentForm) {
        // initializeStripe(); // Call to set up Stripe Elements when payment form is present

        paymentForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            showGlobalMessage('Traitement de votre commande...', 'info');
            const paymentButton = document.getElementById('submit-payment-button');
            if (paymentButton) paymentButton.disabled = true;

            // --- TODO: Stripe Payment Processing Logic ---
            // 1. Create a PaymentIntent on your backend.
            //    Your backend should return the clientSecret of the PaymentIntent.
            //    const { clientSecret, error: backendError } = await makeApiRequest('/orders/create-payment-intent', 'POST', { amount: getCartTotal() * 100 }); // amount in cents
            //    if (backendError) {
            //        showGlobalMessage(backendError.message || "Erreur lors de la préparation du paiement.", "error");
            //        if (paymentButton) paymentButton.disabled = false;
            //        return;
            //    }

            // 2. Confirm the card payment with Stripe.js using the clientSecret and cardElement.
            //    const { paymentIntent, error: stripeError } = await stripe.confirmCardPayment(
            //        clientSecret, {
            //            payment_method: {
            //                card: cardElement,
            //                billing_details: { name: document.getElementById('card-name').value }, // Collect necessary billing details
            //            }
            //        }
            //    );

            //    if (stripeError) {
            //        showGlobalMessage(stripeError.message || "Erreur de paiement.", "error");
            //        if (paymentButton) paymentButton.disabled = false;
            //        return;
            //    }

            //    if (paymentIntent.status === 'succeeded') {
            //        // Payment succeeded, now create the order on your backend
            //        await createOrderOnBackend(paymentIntent);
            //    } else {
            //        showGlobalMessage("Le paiement n'a pas abouti. Statut: " + paymentIntent.status, "error");
            //        if (paymentButton) paymentButton.disabled = false;
            //    }
            // --- END TODO: Stripe Payment Processing Logic ---

            // --- Fallback/Simulation (if Stripe is not yet implemented) ---
            console.warn("SIMULATION: Paiement non intégré. Passage à la création de commande simulée.");
            // Simulate a successful payment for now to proceed with order creation.
            // In a real scenario, paymentIntent.id would come from Stripe.
            const simulatedPaymentIntent = { 
                id: `sim_${new Date().getTime()}`, 
                status: 'succeeded',
                amount: getCartTotal() * 100, // amount in cents
                currency: 'eur'
            }; 
            await createOrderOnBackend(simulatedPaymentIntent);
            // --- End Fallback/Simulation ---
        });
    }

    async function createOrderOnBackend(paymentResult) {
        const paymentButton = document.getElementById('submit-payment-button');
        const paymentMessageEl = document.getElementById('payment-message');
        if(paymentMessageEl) paymentMessageEl.textContent = '';


        const cartItems = getCartItems(); // From cart.js
        if (cartItems.length === 0) {
            showGlobalMessage("Votre panier est vide. Impossible de passer commande.", "error");
            if (paymentButton) paymentButton.disabled = false;
            return;
        }

        // Retrieve shipping and billing addresses from localStorage (set in a previous step)
        // This assumes a multi-step checkout where address is collected before payment.
        // If not, these fields need to be collected on this page or passed differently.
        const shippingAddress = JSON.parse(localStorage.getItem('shippingAddress'));
        const billingAddress = JSON.parse(localStorage.getItem('billingAddress')) || shippingAddress; // Use shipping if billing not separate

        if (!shippingAddress) {
            showGlobalMessage("Adresse de livraison manquante. Veuillez compléter les étapes précédentes.", "error");
            // Potentially redirect to address form
             window.location.href = 'checkout.html'; // Assuming checkout.html is the address step
            if (paymentButton) paymentButton.disabled = false;
            return;
        }

        const orderData = {
            items: cartItems.map(item => ({
                product_id: item.id,
                variant_id: item.variantId, // Will be null if not a variant
                quantity: item.quantity,
                unit_price: item.price,
                // item_uid: item.uid // If specific serialized items were chosen and stored in cart
            })),
            total_amount: getCartTotal(),
            currency: 'EUR', // Or from config/cart
            shipping_address: shippingAddress,
            billing_address: billingAddress,
            payment_details: { // Store relevant, non-sensitive payment info
                method: 'stripe', // Or other method
                transaction_id: paymentResult.id, // Stripe PaymentIntent ID
                status: paymentResult.status,
                amount_captured: paymentResult.amount / 100 // convert back from cents
            },
            // customer_notes: document.getElementById('customer-notes')?.value // If you have a notes field
        };

        try {
            const orderCreationResponse = await makeApiRequest('/orders/create', 'POST', orderData);
            showGlobalMessage(orderCreationResponse.message || "Commande créée avec succès!", "success");
            clearCart(); // From cart.js
            // Store order ID for confirmation page
            localStorage.setItem('lastOrderId', orderCreationResponse.order_id);
            // Redirect to order confirmation page
            window.location.href = 'confirmation-commande.html'; 
        } catch (error) {
            console.error("Order creation failed:", error);
            showGlobalMessage(error.message || "La création de la commande a échoué.", "error");
            if(paymentMessageEl) paymentMessageEl.textContent = `Erreur: ${error.message || "La création de la commande a échoué."}`;
            if (paymentButton) paymentButton.disabled = false;
            // Note: Handle payment reconciliation/refund if order creation fails after successful payment.
            // This often involves more complex backend logic and potentially manual review.
        }
    }

    // Initial display
    if (document.getElementById('payment-form') || document.getElementById('checkout-summary-container')) {
        if (!isUserLoggedIn()) { // from auth.js
            showGlobalMessage("Veuillez vous connecter pour finaliser votre commande.", "error");
            // Optional: Store cart and redirect to login, then return to checkout
            // saveCartForRedirect(); 
            // window.location.href = `compte.html?redirect=${encodeURIComponent(window.location.pathname)}`;
            // For now, just show message. User might be on payment page after login.
        }
        displayCheckoutSummary();
    }
});