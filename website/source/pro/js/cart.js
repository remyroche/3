document.addEventListener('DOMContentLoaded', () => {
    displayCart();
    setupB2BFeatures(); // New function to handle B2B specific UI
});

function displayCart() {
    // ... (existing displayCart function logic)
}

function updateQuantity(productId, change) {
    // ... (existing updateQuantity function logic)
}

function removeFromCart(productId) {
    // ... (existing removeFromCart function logic)
}

function setupB2BFeatures() {
    const user = JSON.parse(localStorage.getItem('user'));
    const quoteSection = document.getElementById('b2b-quote-section');
    
    // Show the quote section only if the user is a B2B user
    if (user && user.user_type === 'b2b' && quoteSection) {
        quoteSection.style.display = 'block';

        const requestQuoteBtn = document.getElementById('request-quote-btn');
        if (requestQuoteBtn) {
            requestQuoteBtn.addEventListener('click', handleRequestQuote);
        }
    }
}

async function handleRequestQuote() {
    const comment = document.getElementById('quote-comment').value;
    const token = localStorage.getItem('token');

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

        const result = await response.json();
        alert('Votre demande de devis a été envoyée avec succès!');
        // Redirect to the professional dashboard to see the new quote
        window.location.href = '/pro/marchedespros.html';

    } catch (error) {
        console.error('Error requesting quote:', error);
        alert(`Erreur: ${error.message}`);
    }
}

// Event listener for the standard checkout button
const checkoutBtn = document.getElementById('checkout-btn');
if (checkoutBtn) {
    checkoutBtn.addEventListener('click', () => {
        window.location.href = '/payment.html';
    });
}
