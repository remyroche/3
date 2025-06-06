<script>
document.addEventListener('DOMContentLoaded', () => {
    const productsGrid = document.getElementById('products-grid');
    const categoryFilters = document.getElementById('category-filters');
    let allProducts = [];

    // Fetch products and categories
    Promise.all([
        fetch('/api/products').then(res => res.json()),
        fetch('/api/categories').then(res => res.json())
    ])
    .then(([products, categories]) => {
        allProducts = products;
        displayProducts(allProducts);
        displayCategories(categories);
    })
    .catch(error => {
        console.error('Error loading products or categories:', error);
        productsGrid.innerHTML = '<p>Error loading content.</p>';
    });

    function displayProducts(products) {
        productsGrid.innerHTML = '';
        if (products.length === 0) {
            productsGrid.innerHTML = '<p>No products found.</p>';
            return;
        }
        products.forEach(product => {
            const productCard = `
                <div class="bg-white rounded-lg shadow-md p-4 flex flex-col transition-transform transform hover:-translate-y-1">
                    <a href="produit-detail.html?id=${product.id}" class="block">
                        <img src="${product.image_url || 'assets/images/placeholder.png'}" alt="${product.name}" class="rounded-md mb-4 h-48 w-full object-cover">
                        <h3 class="text-lg font-bold mb-2">${product.name}</h3>
                    </a>
                    <p class="text-gray-600 mb-4 flex-grow">${product.short_description}</p>
                    <div class="mt-auto flex justify-between items-center">
                        <span class="text-xl font-bold text-blue-600">${product.price} €</span>
                        <button class="bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 add-to-cart-btn" data-product-id="${product.id}">
                           ${window.i18n.add_to_cart}
                        </button>
                    </div>
                </div>
            `;
            productsGrid.innerHTML += productCard;
        });
    }

    function displayCategories(categories) {
        let filtersHtml = `<button class="block w-full text-left py-2 px-3 rounded bg-blue-500 text-white" data-category="all">${window.i18n.filter_all_categories}</button>`;
        categories.forEach(category => {
            filtersHtml += `<button class="block w-full text-left py-2 px-3 rounded hover:bg-gray-200" data-category="${category.id}">${category.name}</button>`;
        });
        categoryFilters.innerHTML = filtersHtml;

        // Add event listeners to filters
        categoryFilters.querySelectorAll('button').forEach(button => {
            button.addEventListener('click', (e) => {
                const categoryId = e.target.dataset.category;
                
                // Update active style
                categoryFilters.querySelectorAll('button').forEach(btn => btn.classList.remove('bg-blue-500', 'text-white'));
                e.target.classList.add('bg-blue-500', 'text-white');

                if (categoryId === 'all') {
                    displayProducts(allProducts);
                } else {
                    const filteredProducts = allProducts.filter(p => p.category_id == categoryId);
                    displayProducts(filteredProducts);
                }
            });
        });
    }
});
</script>

<!--------------------------------------------------------------------------------
-- File: website/source/js/products.js
--------------------------------------------------------------------------------->
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
            document.title = product.name; // Update page title
            const productHtml = `
                <div class="w-full md:w-1/2">
                    <img src="${product.image_url || 'assets/images/placeholder.png'}" alt="${product.name}" class="rounded-lg shadow-lg w-full">
                </div>
                <div class="w-full md:w-1/2">
                    <h1 class="text-4xl font-bold mb-4">${product.name}</h1>
                    <p class="text-gray-600 mb-6">${product.long_description}</p>
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
