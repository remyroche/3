<script>
document.addEventListener('DOMContentLoaded', () => {
    const productsGrid = document.getElementById('products-grid');
    const categoryFilters = document.getElementById('category-filters');
    let allProducts = [];

    // Fetch products
    fetch('/api/products')
        .then(res => res.json())
        .then(products => {
            allProducts = products;
            displayProducts(allProducts);
        })
        .catch(error => {
            console.error('Error loading products:', error);
            productsGrid.innerHTML = '<p>Error loading products.</p>';
        });

    // Fetch categories and build filters
    fetch('/api/categories')
        .then(res => {
            if (!res.ok) throw new Error('Categories endpoint not found');
            return res.json();
        })
        .then(categories => {
            displayCategories(categories);
        })
        .catch(error => {
            console.warn('Could not load category filters:', error.message);
            if (categoryFilters) categoryFilters.style.display = 'none'; // Hide filter section
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
                    <p class="text-gray-600 mb-4 flex-grow">${product.description || ''}</p>
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
        if (!categoryFilters) return;
        let filtersHtml = `<button class="block w-full text-left py-2 px-3 rounded bg-blue-500 text-white" data-category="all">${window.i18n.filter_all_categories}</button>`;
        categories.forEach(category => {
            filtersHtml += `<button class="block w-full text-left py-2 px-3 rounded hover:bg-gray-200" data-category="${category.id}">${category.name}</button>`;
        });
        categoryFilters.innerHTML = filtersHtml;

        categoryFilters.querySelectorAll('button').forEach(button => {
            button.addEventListener('click', (e) => {
                const categoryId = e.target.dataset.category;
                
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
