document.addEventListener('DOMContentLoaded', () => {
    // Ensure the user is a logged-in B2B user before proceeding
    const user = JSON.parse(localStorage.getItem('user'));
    if (!user || user.user_type !== 'b2b') {
        alert("Accès non autorisé. Veuillez vous connecter en tant que professionnel.");
        window.location.href = '/professionnels.html'; // Redirect to B2B login/landing
        return;
    }
    
    await displayCart(); 
    setupEventListeners();
});


async function displayCart() {
    const cartContainer = document.getElementById('cart-container');
    const cartTotalSpan = document.getElementById('cart-total');
    const cartSummaryDiv = document.getElementById('cart-summary');
    const token = localStorage.getItem('token');

    // Remove old discount line if it exists
    const oldDiscountLine = document.getElementById('discount-line');
    if (oldDiscountLine) oldDiscountLine.remove();

    try {
        // Fetch cart and loyalty info in parallel
        const [cartResponse, loyaltyResponse] = await Promise.all([
            fetch('/get_cart', { headers: { 'Authorization': `Bearer ${token}` } }),
            fetch('/pro/get_loyalty_info', { headers: { 'Authorization': `Bearer ${token}` } })
        ]);
        
        if (!cartResponse.ok) throw new Error('Could not fetch cart.');
        const cart = await cartResponse.json();

        let loyaltyInfo = { discount_percent: 0 };
        if (loyaltyResponse.ok) {
            loyaltyInfo = await loyaltyResponse.json();
        }

        cartContainer.innerHTML = ''; 

        if (!cart.items || cart.items.length === 0) {
            // ... (handle empty cart)
            return;
        }

        let subtotal = 0;
        cart.items.forEach(item => {
            // ... (render cart items)
            subtotal += item.product.price * item.quantity;
        });

        const discountAmount = (subtotal * loyaltyInfo.discount_percent) / 100;
        const finalTotal = subtotal - discountAmount;

        // Display discount info if applicable
        if (loyaltyInfo.discount_percent > 0) {
            const discountElement = document.createElement('div');
            discountElement.id = 'discount-line';
            discountElement.className = 'flex justify-between text-accent font-semibold mb-2';
            discountElement.innerHTML = `
                <span>Remise Fidélité (${loyaltyInfo.tier} -${loyaltyInfo.discount_percent}%):</span>
                <span>- ${discountAmount.toFixed(2)} €</span>
            `;
            // Insert before the total line
            cartSummaryDiv.querySelector('div.flex.justify-between').insertAdjacentElement('beforebegin', discountElement);
        }

        cartTotalSpan.textContent = `${finalTotal.toFixed(2)} €`;

    } catch (error) {

        console.error('Error displaying cart:', error);
        cartContainer.innerHTML = `<p class="text-red-500">Erreur lors du chargement du panier.</p>`;
    }
}

async function updateQuantity(productId, change) {
    const token = localStorage.getItem('token');
    try {
        const response = await fetch('/update_cart_quantity', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ product_id: productId, change: change })
        });
        if (response.ok) {
            displayCart(); // Refresh cart display
        }
    } catch (error) {
        console.error('Error updating quantity:', error);
    }
}

async function removeFromCart(productId) {
    const token = localStorage.getItem('token');
    try {
        const response = await fetch('/remove_from_cart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ product_id: productId })
        });
        if (response.ok) {
            displayCart(); // Refresh cart display
        }
    } catch (error) {
        console.error('Error removing item:', error);
    }
}


function setupEventListeners() {
    const cartContainer = document.getElementById('cart-container');

    cartContainer.addEventListener('click', (event) => {
        if (event.target.classList.contains('quantity-change')) {
            const productId = event.target.dataset.productId;
            const change = parseInt(event.target.dataset.change, 10);
            updateQuantity(productId, change);
        }
        if (event.target.classList.contains('remove-item')) {
            const productId = event.target.dataset.productId;
            removeFromCart(productId);
        }
    });
    
    // Standard Checkout Button
    const checkoutBtn = document.getElementById('checkout-btn');
    if (checkoutBtn) {
        checkoutBtn.addEventListener('click', () => {
            // Redirect to the standard payment page
            window.location.href = '/payment.html';
        });
    }

    // Request Quote Button
    const requestQuoteBtn = document.getElementById('request-quote-btn');
    if (requestQuoteBtn) {
        requestQuoteBtn.addEventListener('click', handleRequestQuote);
    }
}

async function handleRequestQuote() {
    const comment = document.getElementById('quote-comment').value;
    const token = localStorage.getItem('token');
    
    // Disable the button to prevent multiple clicks
    const button = document.getElementById('request-quote-btn');
    button.disabled = true;
    button.textContent = 'Envoi en cours...';

    try {
        const response = await fetch('/pro/request_quote', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ comment: comment })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to request quote');
        }

        alert('Votre demande de devis a été envoyée avec succès!');
        // Redirect to the professional dashboard to see the new quote
        window.location.href = '/pro/marchedespros.html';

    } catch (error) {
        console.error('Error requesting quote:', error);
        alert(`Erreur: ${error.message}`);
        button.disabled = false;
        button.textContent = 'Demander un devis';
    }
}
