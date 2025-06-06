document.addEventListener('DOMContentLoaded', () => {
    // Ensure the user is a logged-in B2B user before proceeding
    const user = JSON.parse(localStorage.getItem('user'));
    if (!user || user.user_type !== 'b2b') {
        alert("Accès non autorisé. Veuillez vous connecter en tant que professionnel.");
        window.location.href = '/professionnels.html'; // Redirect to B2B login/landing
        return;
    }
    
    displayCart();
    setupEventListeners();
});

async function displayCart() {
    const cartContainer = document.getElementById('cart-container');
    const cartTotalSpan = document.getElementById('cart-total');
    const token = localStorage.getItem('token');

    try {
        const response = await fetch('/get_cart', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error('Could not fetch cart.');
        }

        const cart = await response.json();
        cartContainer.innerHTML = ''; // Clear loading message

        if (!cart.items || cart.items.length === 0) {
            cartContainer.innerHTML = '<p>Votre panier est vide.</p>';
            cartTotalSpan.textContent = '0.00 €';
            // Disable buttons if cart is empty
            document.getElementById('checkout-btn').disabled = true;
            document.getElementById('request-quote-btn').disabled = true;
            return;
        }

        let total = 0;
        cart.items.forEach(item => {
            const itemElement = document.createElement('div');
            itemElement.className = 'flex justify-between items-center mb-4 pb-4 border-b';
            itemElement.innerHTML = `
                <div class="flex items-center">
                    <img src="${item.product.images[0]?.image_url || 'https://placehold.co/80x80/eee/ccc?text=Image'}" alt="${item.product.name}" class="w-20 h-20 object-cover rounded mr-4">
                    <div>
                        <h4 class="font-semibold">${item.product.name}</h4>
                        <p class="text-sm text-gray-600">${item.product.price.toFixed(2)} €</p>
                    </div>
                </div>
                <div class="flex items-center">
                    <button class="quantity-change bg-gray-200 px-2 rounded" data-product-id="${item.product.id}" data-change="-1">-</button>
                    <span class="mx-2">${item.quantity}</span>
                    <button class="quantity-change bg-gray-200 px-2 rounded" data-product-id="${item.product.id}" data-change="1">+</button>
                    <button class="remove-item text-red-500 hover:text-red-700 ml-4" data-product-id="${item.product.id}">Supprimer</button>
                </div>
            `;
            cartContainer.appendChild(itemElement);
            total += item.product.price * item.quantity;
        });

        cartTotalSpan.textContent = `${total.toFixed(2)} €`;
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
