<script>
document.addEventListener('DOMContentLoaded', () => {
    const productDetailContainer = document.getElementById('product-detail-container');
    const urlParams = new URLSearchParams(window.location.search);
    const productId = urlParams.get('id');

    if (!productId) {
        productDetailContainer.innerHTML = `<p>${window.i18n.product_not_found}</p>`;
        return;
    }

    fetch(`/api/products/${productId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Product not found');
            }
            return response.json();
        })
        .then(product => {
            document.title = product.name;
            const productHtml = `
                <div class="w-full md:w-1/2">
                    <img src="${product.image_url || 'assets/images/placeholder.png'}" alt="${product.name}" class="rounded-lg shadow-lg w-full">
                </div>
                <div class="w-full md:w-1/2">
                    <h1 class="text-4xl font-bold mb-4">${product.name}</h1>
                    <p class="text-gray-600 mb-6">${product.description || ''}</p>
                    <div class="flex items-center justify-between mb-6">
                        <span class="text-3xl font-bold text-blue-600">${product.price} €</span>
                        <div class="flex items-center">
                            <label for="quantity" class="mr-4 font-semibold">${window.i18n.product_quantity}:</label>
                            <input type="number" id="quantity" name="quantity" value="1" min="1" class="w-20 border-gray-300 border p-2 rounded-md">
                        </div>
                    </div>
                    <button class="w-full bg-blue-600 text-white font-bold py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors duration-300 add-to-cart-btn" data-product-id="${product.id}">
                        ${window.i18n.add_to_cart}
                    </button>
                </div>
            `;
            productDetailContainer.innerHTML = productHtml;
        })
        .catch(error => {
            console.error('Error fetching product details:', error);
            productDetailContainer.innerHTML = `<p class="text-red-500">${window.i18n.product_not_found}</p>`;
        });
});
</script>

