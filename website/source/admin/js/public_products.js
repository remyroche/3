// website/js/public_products.js
document.addEventListener('DOMContentLoaded', () => {
    const productsContainer = document.getElementById('products-container'); // You'll need a div with this ID in nos-produits.html
    const loadingMessage = document.getElementById('loading-products-message'); // The "Chargement des produits..." element

    if (!productsContainer) {
        console.error('Product container not found on the page.');
        if(loadingMessage) loadingMessage.textContent = 'Erreur: Conteneur de produits non trouvé.';
        return;
    }
// website/admin/js/public_products.js
// Note: This script seems to be intended for a public page (nos-produits.html)
// but is located in the admin/js folder. Assuming it might be used by an admin-controlled
// public view or was misplaced. It should use the public `t()` function if available on that page.
// For now, will use hardcoded strings or keys that would be defined in public JSON.

document.addEventListener('DOMContentLoaded', () => {
    const productsContainer = document.getElementById('products-container'); 
    const loadingMessage = document.getElementById('loading-products-message'); 

    if (!productsContainer) {
        if(loadingMessage) loadingMessage.textContent = 'Error: Product container not found.'; // Fallback, non-translated
        return;
    }

    async function fetchAndDisplayProducts() {
        if (loadingMessage) {
            loadingMessage.textContent = t ? t('public.products_page.loading') : 'Loading products...';
            loadingMessage.style.display = 'block';
        }
        productsContainer.innerHTML = ''; 

        try {
            // Assuming API_BASE_URL is globally available (e.g., from a config.js loaded on the public page)
            const response = await fetch(`${API_BASE_URL}/api/products`); 
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            if (loadingMessage) loadingMessage.style.display = 'none';

            if (data.success && data.products && data.products.length > 0) {
                data.products.forEach(product => {
                    if (product.is_published) {
                        const productCard = createProductCard(product);
                        productsContainer.appendChild(productCard);
                    }
                });
                if (productsContainer.children.length === 0) {
                     productsContainer.innerHTML = `<p class="text-center text-gray-600">${t ? t('public.js.no_products_found') : 'No published products to display at the moment.'}</p>`;
                }
            } else if (data.success && data.products.length === 0) {
                productsContainer.innerHTML = `<p class="text-center text-gray-600">${t ? t('public.js.no_products_found') : 'No products available at the moment.'}</p>`;
            } else {
                productsContainer.innerHTML = `<p class="text-center text-red-500">${t ? t('public.js.product_load_error') : 'Could not load products'}: ${data.message || (t ? t('global.error_generic') : 'Invalid server response')}</p>`;
            }
        } catch (error) {
            if (loadingMessage) loadingMessage.style.display = 'none';
            productsContainer.innerHTML = `<p class="text-center text-red-500">${t ? t('public.js.product_load_error') : 'An error occurred while loading products. Please try again later.'}</p>`;
        }
    }

    function createProductCard(product) {
        const card = document.createElement('div');
        card.className = 'product-card bg-white shadow-lg rounded-lg overflow-hidden transform hover:scale-105 transition-transform duration-300'; 

        let priceDisplay = t ? t('public.product_detail.price_on_request') : "Price unavailable";
        let mainImageUrl = product.image_url_main || 'img/placeholder.png'; 

        if (product.weight_options && product.weight_options.length > 0) {
            priceDisplay = `${t ? t('public.product_detail.price_on_request') : 'Starting at'} ${parseFloat(product.weight_options[0].price).toFixed(2)} €`; // Example, adapt as needed
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
                <button onclick="handlePublicAddToCart('${product.id}')" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded transition-colors duration-300">
                    ${t ? t('public.products_page.add_to_cart') : 'Add to Cart'}
                </button>
            </div>
        `;
        return card;
    }

    fetchAndDisplayProducts();
});

function handlePublicAddToCart(productId) {
    // This function would need access to the public cart.js `addToCart` function
    // and product details. For simplicity, this is a placeholder.
    // A real implementation would fetch product details then call the main addToCart.
    console.log(`Product ${productId} add to cart action (public page).`);
    if (typeof addToCart === 'function' && typeof showGlobalMessage === 'function' && typeof t === 'function') {
        // Simulate fetching product then adding.
        // In a real scenario, you'd fetch the product object first.
        showGlobalMessage(t('public.js.added_to_cart_toast', { qty: 1, name: `Product ${productId}` }), 'success');
    } else {
        alert(`Product ${productId} added to cart (simulation).`);
    }
}
