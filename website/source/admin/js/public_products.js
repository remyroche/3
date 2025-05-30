// website/js/public_products.js
document.addEventListener('DOMContentLoaded', () => {
    const productsContainer = document.getElementById('products-container'); // You'll need a div with this ID in nos-produits.html
    const loadingMessage = document.getElementById('loading-products-message'); // The "Chargement des produits..." element

    if (!productsContainer) {
        console.error('Product container not found on the page.');
        if(loadingMessage) loadingMessage.textContent = 'Erreur: Conteneur de produits non trouvé.';
        return;
    }

    async function fetchAndDisplayProducts() {
        if (loadingMessage) loadingMessage.style.display = 'block';
        productsContainer.innerHTML = ''; // Clear previous products if any

        try {
            // Use the API_BASE_URL from your admin_config.js if it's also loaded on this page,
            // or define it directly if admin_config.js is not meant for public pages.
            // For simplicity, let's assume API_BASE_URL is available or hardcode for now.
            // const API_BASE_URL = 'http://localhost:3000'; // Or get from a shared config

            const response = await fetch(`${API_BASE_URL}/api/products`); // API_BASE_URL from admin_config.js
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            if (loadingMessage) loadingMessage.style.display = 'none';

            if (data.success && data.products && data.products.length > 0) {
                data.products.forEach(product => {
                    // Only display published products
                    if (product.is_published) {
                        const productCard = createProductCard(product);
                        productsContainer.appendChild(productCard);
                    }
                });
                if (productsContainer.children.length === 0) {
                     productsContainer.innerHTML = '<p class="text-center text-gray-600">Aucun produit publié à afficher pour le moment.</p>';
                }
            } else if (data.success && data.products.length === 0) {
                productsContainer.innerHTML = '<p class="text-center text-gray-600">Aucun produit disponible pour le moment.</p>';
            } else {
                productsContainer.innerHTML = `<p class="text-center text-red-500">Impossible de charger les produits: ${data.message || 'Réponse invalide du serveur'}</p>`;
            }
        } catch (error) {
            console.error('Error fetching products:', error);
            if (loadingMessage) loadingMessage.style.display = 'none';
            productsContainer.innerHTML = `<p class="text-center text-red-500">Une erreur est survenue lors du chargement des produits. Veuillez réessayer plus tard.</p>`;
        }
    }

    function createProductCard(product) {
        const card = document.createElement('div');
        card.className = 'product-card bg-white shadow-lg rounded-lg overflow-hidden transform hover:scale-105 transition-transform duration-300'; // Add your Tailwind classes

        // Determine price: use first weight option if available, otherwise base_price
        let priceDisplay = "Prix non disponible";
        let mainImageUrl = product.image_url_main || 'img/placeholder.png'; // Fallback image

        if (product.weight_options && product.weight_options.length > 0) {
            // Display price of the first variant, or a range, or "À partir de X €"
            priceDisplay = `À partir de ${parseFloat(product.weight_options[0].price).toFixed(2)} €`;
        } else if (product.base_price !== null && product.base_price !== undefined) {
            priceDisplay = `${parseFloat(product.base_price).toFixed(2)} €`;
        }

        card.innerHTML = `
            <a href="produit-detail.html?id=${product.id}" class="block">
                <img src="${mainImageUrl}" alt="${product.name}" class="w-full h-48 object-cover">
                <div class="p-4">
                    <h3 class="text-lg font-semibold text-gray-800 mb-1">${product.name}</h3>
                    <p class="text-sm text-gray-600 mb-2 truncate">${product.short_description}</p>
                    <p class="text-md font-bold text-indigo-600">${priceDisplay}</p>
                </div>
            </a>
            <div class="p-4 border-t border-gray-200">
                <button onclick="addToCart('${product.id}')" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded transition-colors duration-300">
                    Ajouter au Panier
                </button>
            </div>
        `;
        // Note: The addToCart function and produit-detail.html page would need to be implemented.
        return card;
    }

    // Call the function to load products
    fetchAndDisplayProducts();
});

// Placeholder addToCart function - you'll need to implement actual cart logic
function addToCart(productId) {
    console.log(`Product ${productId} added to cart (placeholder).`);
    // Here you would typically interact with a cart management system (e.g., localStorage, backend API)
    alert(`Produit ${productId} ajouté au panier (simulation).`);
}
