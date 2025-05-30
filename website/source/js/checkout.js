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
    // let cardElement;
    // const stripePublishableKey = 'YOUR_STRIPE_PUBLISHABLE_KEY'; // Replace with your actual key from config or env

    // async function initializeStripe() {
    //     if (!stripePublishableKey || stripePublishableKey === 'YOUR_STRIPE_PUBLISHABLE_KEY') {
    //         console.warn("Stripe Publishable Key is not set. Payment processing will be simulated.");
    //         showGlobalMessage("Mode de paiement non configuré (simulation activée).", "info");
    //         return;
    //     }
    //     try {
    //         stripe = Stripe(stripePublishableKey);
    //         const elements = stripe.elements({
    //             // Optional: Add locale if you want Stripe Elements to match site language
    //             // locale: 'fr' 
    //         });
    //         cardElement = elements.create('card', { 
    //             hidePostalCode: true,
    //             // style: { base: { /* your custom styles */ } } 
    //         });
    //         const cardElementPlaceholder = document.getElementById('card-element-placeholder');
    //         if (cardElementPlaceholder) {
    //             cardElement.mount('#card-element-placeholder');
    //             cardElementPlaceholder.innerHTML = ''; // Clear placeholder text
    //         } else {
    //            console.error("Stripe card element placeholder not found in payment.html");
    //            showGlobalMessage("Erreur: Impossible d'afficher le formulaire de carte.", "error");
    //            return;
    //         }
            

    //         cardElement.on('change', (event) => {
    //             const displayError = document.getElementById('card-errors');
    //             if (displayError) {
    //                 if (event.error) {
    //                     displayError.textContent = event.error.message;
    //                 } else {
    //                     displayError.textContent = '';
    //                 }
    //             }
    //         });
    //         console.log("Stripe initialized and card element mounted.");
    //     } catch (error) {
    //         console.error("Failed to initialize Stripe:", error);
    //         showGlobalMessage("Erreur d'initialisation du module de paiement.", "error");
    //     }
    // }
    
    // Display Order Summary
    async function displayCheckoutSummary() {
        if (!checkoutSummaryContainer) return;

        const itemsContainer = document.getElementById('checkout-summary-items');
        const totalEl = document.getElementById('checkout-summary-total');
        
        if (!itemsContainer || !totalEl) {
            console.error("Checkout summary elements not found in payment.html");
            return;
        }

        const cartItems = getCartItems(); // From cart.js
        itemsContainer.innerHTML = ''; // Clear previous items

        if (cartItems.length === 0) {
            itemsContainer.innerHTML = '<p class="text-gray-600">Votre panier est vide.</p>';
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

        const cartTotal = getCartTotal(); // From cart.js
        totalEl.textContent = `${cartTotal.toFixed(2)} €`;
        if(paymentButtonAmount) paymentButtonAmount.textContent = cartTotal.toFixed(2);
        const paymentButton = document.getElementById('submit-payment-button');
        if (paymentButton) {
            paymentButton.disabled = false;
            paymentButton.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    }


    if (paymentForm) {
        // initializeStripe(); // Call to set up Stripe Elements

        paymentForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            showGlobalMessage('Traitement de votre commande...', 'info', 10000); // Longer timeout
            const paymentButton = document.getElementById('submit-payment-button');
            if (paymentButton) paymentButton.disabled = true;
            const paymentMessageEl = document.getElementById('payment-message');
            if(paymentMessageEl) paymentMessageEl.textContent = '';


            // --- TODO: Stripe Payment Processing Logic ---
            // This section needs to be implemented with your Stripe integration.
            //
            // if (!stripe || !cardElement) {
            //     showGlobalMessage("Le module de paiement n'est pas prêt. Veuillez réessayer.", "error");
            //     if (paymentButton) paymentButton.disabled = false;
            //     return;
            // }
            //
            // const cardholderName = document.getElementById('card-name').value;
            // if (!cardholderName) {
            //     showGlobalMessage("Veuillez entrer le nom sur la carte.", "error");
            //     setFieldError(document.getElementById('card-name'), "Nom requis."); // Assumes setFieldError from ui.js
            //     if (paymentButton) paymentButton.disabled = false;
            //     return;
            // }
            //
            // try {
            //     // 1. Create PaymentIntent on backend
            //     const intentResponse = await makeApiRequest('/orders/create-payment-intent', 'POST', { 
            //         amount: Math.round(getCartTotal() * 100), // Amount in cents
            //         currency: 'eur' // Or from config
            //     });
            //     if (!intentResponse.success || !intentResponse.client_secret) {
            //         throw new Error(intentResponse.message || "Erreur de préparation du paiement.");
            //     }
            //     const clientSecret = intentResponse.client_secret;
            //
            //     // 2. Confirm card payment with Stripe.js
            //     const { paymentIntent, error: stripeError } = await stripe.confirmCardPayment(
            //         clientSecret, {
            //             payment_method: {
            //                 card: cardElement,
            //                 billing_details: { name: cardholderName },
            //             }
            //         }
            //     );
            //
            //     if (stripeError) {
            //         throw new Error(stripeError.message || "Erreur de paiement Stripe.");
            //     }
            //
            //     if (paymentIntent.status === 'succeeded') {
            //         showGlobalMessage("Paiement réussi ! Finalisation de la commande...", "success");
            //         await createOrderOnBackend(paymentIntent);
            //     } else {
            //         throw new Error("Le paiement n'a pas abouti. Statut: " + paymentIntent.status);
            //     }
            // } catch (error) {
            //     console.error("Payment processing error:", error);
            //     showGlobalMessage(error.message || "Une erreur est survenue lors du paiement.", "error");
            //     if(paymentMessageEl) paymentMessageEl.textContent = `Erreur: ${error.message || "Une erreur est survenue lors du paiement."}`;
            //     if (paymentButton) paymentButton.disabled = false;
            // }
            // --- END TODO: Stripe Payment Processing Logic ---

            // --- Fallback/Simulation (Remove this when Stripe is integrated) ---
            console.warn("SIMULATION: Paiement Stripe non intégré. Passage à la création de commande simulée.");
            await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate payment processing delay
            const simulatedPaymentIntent = { 
                id: `sim_maison_truvra_${new Date().getTime()}`, 
                status: 'succeeded', // Simulate success
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
            showGlobalMessage("Votre panier est vide. Impossible de passer commande.", "error");
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
            console.error("Error parsing addresses from localStorage", e);
            showGlobalMessage("Erreur avec les adresses enregistrées. Veuillez réessayer.", "error");
            if (paymentButton) paymentButton.disabled = false;
            return;
        }


        if (!shippingAddress || !shippingAddress.address_line1 || !shippingAddress.city || !shippingAddress.postal_code || !shippingAddress.country || !shippingAddress.first_name || !shippingAddress.last_name) {
            showGlobalMessage("Adresse de livraison incomplète. Veuillez compléter les étapes précédentes.", "error");
            // window.location.href = 'checkout-address.html'; // Redirect to address form if separate
            if (paymentButton) paymentButton.disabled = false;
            return;
        }
        // Ensure billing address is also complete if provided and different
        if (billingAddress !== shippingAddress && (!billingAddress || !billingAddress.address_line1 || !billingAddress.city || !billingAddress.postal_code || !billingAddress.country || !billingAddress.first_name || !billingAddress.last_name)) {
            showGlobalMessage("Adresse de facturation incomplète.", "error");
            if (paymentButton) paymentButton.disabled = false;
            return;
        }


        const currentUser = getCurrentUser(); // from auth.js
        const orderData = {
            items: cartItems.map(item => ({
                product_id: item.id,
                variant_id: item.variantId || null,
                quantity: item.quantity,
                // unit_price: item.price, // Backend should fetch current price for security/accuracy
                // product_name: item.name, // Backend can fetch this
                // variant_description: item.variantDescription // Backend can fetch this
            })),
            // total_amount: getCartTotal(), // Backend should recalculate total for security
            currency: 'EUR',
            shipping_address: shippingAddress,
            billing_address: billingAddress,
            payment_details: { 
                method: 'stripe_simulation', // Change to 'stripe' with real integration
                transaction_id: paymentResult.id, 
                status: paymentResult.status,
                amount_captured: paymentResult.amount / 100 
            },
            customer_email: currentUser ? currentUser.email : shippingAddress.email, // Ensure email is captured
            // customer_notes: document.getElementById('customer-notes')?.value 
        };

        try {
            // makeApiRequest from api.js
            const orderCreationResponse = await makeApiRequest('/orders/create', 'POST', orderData, !!currentUser); // requiresAuth if user is logged in
            
            showGlobalMessage(orderCreationResponse.message || "Commande créée avec succès!", "success");
            clearCart(); 
            localStorage.setItem('lastOrderId', orderCreationResponse.order_id);
            localStorage.setItem('lastOrderTotal', orderCreationResponse.total_amount.toFixed(2)); // Store total for confirmation page
            
            // Remove address from localStorage after successful order
            localStorage.removeItem('shippingAddress');
            localStorage.removeItem('billingAddress');

            window.location.href = 'confirmation-commande.html'; 
        } catch (error) {
            console.error("Order creation failed on backend:", error);
            showGlobalMessage(error.message || "La création de la commande a échoué après le paiement.", "error");
            if(paymentMessageEl) paymentMessageEl.textContent = `Erreur critique: ${error.message || "La création de la commande a échoué. Veuillez contacter le support."}`;
            if (paymentButton) paymentButton.disabled = false;
            // CRITICAL: Handle payment reconciliation/refund if order creation fails *after* successful payment.
            // This usually involves backend logic and potentially manual intervention.
            // Log this error thoroughly on the backend.
        }
    }

    // Initial display and checks
    if (document.getElementById('payment-form') || checkoutSummaryContainer) {
        if (!isUserLoggedIn()) { // from auth.js
            // For guest checkout, shippingAddress must contain email.
            // If login is mandatory for checkout, redirect here.
            // showGlobalMessage("Veuillez vous connecter pour finaliser votre commande.", "info");
            // window.location.href = `compte.html?redirect=${encodeURIComponent(window.location.pathname)}`;
        }
        const cartItems = getCartItems();
        if (cartItems.length === 0 && window.location.pathname.includes('payment.html')) {
            showGlobalMessage("Votre panier est vide. Redirection...", "info");
            setTimeout(() => { window.location.href = 'nos-produits.html'; }, 2000);
        } else {
            displayCheckoutSummary();
        }
    }
});

// This function is called from main.js if on payment page
function initializeCheckoutPage() {
    // Specific initializations for payment.html if any, beyond DOMContentLoaded
    // For example, re-validating addresses from localStorage or user profile
    const shippingAddress = JSON.parse(localStorage.getItem('shippingAddress'));
    if (!shippingAddress && window.location.pathname.includes('payment.html')) {
        showGlobalMessage("Informations de livraison manquantes. Veuillez d'abord compléter l'adresse.", "error");
        // Redirect to address step if it's separate, e.g., 'checkout-address.html'
        // For now, we assume address is collected before reaching payment.html or is part of user profile.
    }
}

// This function is called from main.js if on confirmation page
function initializeConfirmationPage() {
    const orderIdEl = document.getElementById('confirmation-order-id');
    const totalAmountEl = document.getElementById('confirmation-total-amount');
    const lastOrderId = localStorage.getItem('lastOrderId');
    const lastOrderTotal = localStorage.getItem('lastOrderTotal');

    if (orderIdEl && totalAmountEl && lastOrderId && lastOrderTotal) {
        orderIdEl.textContent = lastOrderId;
        totalAmountEl.textContent = `${lastOrderTotal} €`;
        // Clear stored order details after displaying them
        localStorage.removeItem('lastOrderId');
        localStorage.removeItem('lastOrderTotal');
    } else if (orderIdEl) { // If on confirmation page but no order details
        orderIdEl.textContent = 'N/A';
        if(totalAmountEl) totalAmountEl.textContent = 'N/A';
        const confirmationMessageEl = document.getElementById('confirmation-message');
        if(confirmationMessageEl) confirmationMessageEl.textContent = "Détails de la commande non trouvés. Veuillez vérifier votre compte ou vos e-mails.";
    }
}
