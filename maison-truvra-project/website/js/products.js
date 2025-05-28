// website/js/product.js
// Handles fetching and displaying products on listing and detail pages.

let allProducts = []; // Cache for all products, used for client-side filtering if implemented
let currentProductDetail = null; // Holds the data for the currently viewed product detail

/**
 * Fetches products from the API and displays them on the product listing page.
 * @param {string} [category='all'] - The category to filter by. 'all' fetches all products.
 */
async function fetchAndDisplayProducts(category = 'all') {
    const productsGrid = document.getElementById('products-grid');
    const loadingMessageElement = document.getElementById('products-loading-message');
    
    if (!productsGrid || !loadingMessageElement) {
        console.error("Éléments de la grille de produits ou message de chargement non trouvés.");
        return;
    }

    loadingMessageElement.textContent = "Chargement des produits...";
    loadingMessageElement.style.display = 'block';
    productsGrid.innerHTML = ''; // Clear previous products

    try {
        const endpoint = category === 'all' ? '/products' : `/products?category=${encodeURIComponent(category)}`;
        // makeApiRequest is from api.js
        const products = await makeApiRequest(endpoint); 
        
        if (category === 'all' && products.length > 0) {
            allProducts = products; // Cache all products if fetching all
        }

        const productsToDisplay = products; // API now handles filtering

        if (productsToDisplay.length === 0) {
            loadingMessageElement.textContent = "Aucun produit trouvé dans cette catégorie.";
            productsGrid.innerHTML = `<p class="col-span-full text-center text-brand-earth-brown py-8">Aucun produit à afficher.</p>`;
        } else {
            loadingMessageElement.style.display = 'none';
            productsToDisplay.forEach(product => {
                const stockMessage = product.stock_quantity > 5 ? 'En stock' : (product.stock_quantity > 0 ? 'Stock limité!' : 'Épuisé');
                const stockClass = product.stock_quantity > 0 ? 'text-brand-deep-sage-green' : 'text-brand-truffle-burgundy';
                const productCard = `
                    <div class="product-card">
                        <a href="produit-detail.html?id=${product.id}">
                            <img src="${product.image_url_main || 'https://placehold.co/400x300/F5EEDE/7D6A4F?text=Image+Indisponible'}" alt="${product.name}" class="w-full h-64 object-cover" onerror="this.onerror=null;this.src='https://placehold.co/400x300/F5EEDE/7D6A4F?text=Image+Erreur';">
                        </a>
                        <div class="product-card-content">
                            <h3 class="text-xl font-serif font-semibold text-brand-near-black mb-2">${product.name}</h3>
                            <p class="text-brand-earth-brown text-sm mb-3 h-16 overflow-hidden">${product.short_description || ''}</p>
                            <p class="text-lg font-semibold text-brand-truffle-burgundy mb-4">
                                ${product.starting_price !== "N/A" && product.starting_price !== null ? `À partir de ${parseFloat(product.starting_price).toFixed(2)} €` : (product.base_price ? `${parseFloat(product.base_price).toFixed(2)} €` : 'Prix sur demande')}
                            </p>
                             <p class="text-xs ${stockClass} mb-4">${stockMessage}</p>
                        </div>
                        <div class="product-card-footer p-4">
                            <a href="produit-detail.html?id=${product.id}" class="btn-primary block text-center text-sm py-2.5 ${product.stock_quantity <=0 ? 'opacity-50 cursor-not-allowed' : ''}">${product.stock_quantity <= 0 ? 'Épuisé' : 'Voir le produit'}</a>
                        </div>
                    </div>
                `;
                productsGrid.insertAdjacentHTML('beforeend', productCard);
            });
        }
    } catch (error) {
        loadingMessageElement.textContent = "Erreur lors du chargement des produits.";
        productsGrid.innerHTML = `<p class="col-span-full text-center text-brand-truffle-burgundy py-8">Impossible de charger les produits. ${error.message}</p>`;
    }
}

/**
 * Sets up event listeners for category filter buttons on the product listing page.
 */
function setupCategoryFilters() {
    const filterContainer = document.getElementById('product-categories-filter');
    if (filterContainer) {
        const buttons = filterContainer.querySelectorAll('button');
        buttons.forEach(button => {
            button.addEventListener('click', () => {
                buttons.forEach(btn => btn.classList.remove('filter-active', 'bg-brand-earth-brown', 'text-brand-cream'));
                button.classList.add('filter-active', 'bg-brand-earth-brown', 'text-brand-cream');
                const category = button.dataset.category;
                fetchAndDisplayProducts(category);
            });
        });
    }
}

/**
 * Loads and displays the details of a single product on the product detail page.
 */
async function loadProductDetail() {
    const params = new URLSearchParams(window.location.search);
    const productId = params.get('id');
    const loadingDiv = document.getElementById('product-detail-loading');
    const contentDiv = document.getElementById('product-detail-content');

    if (!productId) {
        if(loadingDiv) loadingDiv.textContent = "Aucun produit spécifié.";
        if(contentDiv) contentDiv.style.display = 'none';
        return;
    }
    
    if(loadingDiv) loadingDiv.style.display = 'block';
    if(contentDiv) contentDiv.style.display = 'none';

    try {
        // makeApiRequest is from api.js
        const product = await makeApiRequest(`/products/${productId}`);
        currentProductDetail = product; // Store globally for addToCart functionality

        document.getElementById('product-name').textContent = product.name;
        const mainImage = document.getElementById('main-product-image');
        mainImage.src = product.image_url_main || 'https://placehold.co/600x500/F5EEDE/7D6A4F?text=Image';
        mainImage.alt = product.name;
        mainImage.onerror = () => { mainImage.src = 'https://placehold.co/600x500/F5EEDE/7D6A4F?text=Image+Erreur'; };

        document.getElementById('product-short-description').textContent = product.short_description || '';
        
        const priceDisplay = document.getElementById('product-price-display');
        const priceUnit = document.getElementById('product-price-unit');
        const weightOptionsContainer = document.getElementById('weight-options-container');
        const weightOptionsSelect = document.getElementById('weight-options-select');
        const addToCartButton = document.getElementById('add-to-cart-button');

        if (product.weight_options && product.weight_options.length > 0) {
            weightOptionsContainer.classList.remove('hidden');
            weightOptionsSelect.innerHTML = ''; // Clear previous options
            product.weight_options.forEach(opt => {
                const optionElement = document.createElement('option');
                optionElement.value = opt.option_id; // Use option_id as value
                optionElement.textContent = `${opt.weight_grams}g - ${parseFloat(opt.price).toFixed(2)} € ${opt.stock_quantity <= 0 ? '(Épuisé)' : `(Stock: ${opt.stock_quantity})`}`;
                optionElement.dataset.price = opt.price;
                optionElement.dataset.stock = opt.stock_quantity;
                optionElement.dataset.weightGrams = opt.weight_grams;
                if(opt.stock_quantity <= 0) optionElement.disabled = true;
                weightOptionsSelect.appendChild(optionElement);
            });
            
            // Select first available option
            let firstEnabledIndex = -1;
            for(let i=0; i<weightOptionsSelect.options.length; i++) {
                if(!weightOptionsSelect.options[i].disabled) {
                    firstEnabledIndex = i;
                    break;
                }
            }
            if(firstEnabledIndex !== -1) weightOptionsSelect.selectedIndex = firstEnabledIndex;
            
            updatePriceFromSelection(); // Update price based on (newly) selected option
            weightOptionsSelect.addEventListener('change', updatePriceFromSelection);
        } else if (product.base_price !== null) {
            priceDisplay.textContent = `${parseFloat(product.base_price).toFixed(2)} €`;
            priceUnit.textContent = ''; 
            weightOptionsContainer.classList.add('hidden');
             if (product.stock_quantity <= 0) {
                addToCartButton.textContent = 'Épuisé';
                addToCartButton.disabled = true;
                addToCartButton.classList.replace('btn-gold','btn-secondary'); // Use appropriate classes
                addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
            }
        } else { // No base price and no weight options
            priceDisplay.textContent = 'Prix sur demande';
            priceUnit.textContent = '';
            weightOptionsContainer.classList.add('hidden');
            addToCartButton.textContent = 'Indisponible';
            addToCartButton.disabled = true;
            addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
        }

        document.getElementById('product-species').textContent = product.species || 'N/A';
        document.getElementById('product-origin').textContent = product.origin || 'N/A';
        document.getElementById('product-seasonality').textContent = product.seasonality || 'N/A';
        document.getElementById('product-uses').textContent = product.ideal_uses || 'N/A';
        document.getElementById('product-sensory-description').innerHTML = product.long_description || product.sensory_description || 'Aucune description détaillée disponible.';
        document.getElementById('product-pairing-suggestions').textContent = product.pairing_suggestions || 'Aucune suggestion d\'accord disponible.';
        
        const thumbnailGallery = document.getElementById('product-thumbnail-gallery');
        thumbnailGallery.innerHTML = ''; 
        if (product.image_urls_thumb && Array.isArray(product.image_urls_thumb) && product.image_urls_thumb.length > 0) {
            product.image_urls_thumb.forEach(thumbUrl => {
                if (typeof thumbUrl === 'string') {
                    const img = document.createElement('img');
                    img.src = thumbUrl;
                    img.alt = `${product.name} miniature`;
                    img.className = 'w-full h-24 object-cover rounded cursor-pointer hover:opacity-75 transition-opacity';
                    img.onclick = () => { 
                        const mainImgToUpdate = document.getElementById('main-product-image');
                        if (mainImgToUpdate) mainImgToUpdate.src = thumbUrl;
                    };
                    img.onerror = () => { img.style.display='none'; }; // Hide broken thumbnails
                    thumbnailGallery.appendChild(img);
                }
            });
        }

        if(loadingDiv) loadingDiv.style.display = 'none';
        if(contentDiv) contentDiv.style.display = 'grid'; // Or 'block' depending on layout
    } catch (error) {
        if(loadingDiv) loadingDiv.innerHTML = `<p class="text-brand-truffle-burgundy">Impossible de charger les détails du produit: ${error.message}</p>`;
        if(contentDiv) contentDiv.style.display = 'none';
    }
}

/**
 * Updates the displayed price and add-to-cart button state based on the selected weight option.
 */
function updatePriceFromSelection() {
    const weightOptionsSelect = document.getElementById('weight-options-select');
    const priceDisplay = document.getElementById('product-price-display');
    const priceUnit = document.getElementById('product-price-unit');
    const addToCartButton = document.getElementById('add-to-cart-button');

    if (!weightOptionsSelect || !priceDisplay || !priceUnit || !addToCartButton) {
        console.error("Un ou plusieurs éléments UI pour la sélection de prix sont manquants.");
        return;
    }
    
    const selectedOption = weightOptionsSelect.options[weightOptionsSelect.selectedIndex];

    if (selectedOption && selectedOption.value) { // Ensure a valid option is selected
        priceDisplay.textContent = `${parseFloat(selectedOption.dataset.price).toFixed(2)} €`;
        priceUnit.textContent = `/ ${selectedOption.dataset.weightGrams}g`;
        if (parseInt(selectedOption.dataset.stock) <= 0 || selectedOption.disabled) {
            addToCartButton.textContent = 'Épuisé';
            addToCartButton.disabled = true;
            addToCartButton.classList.replace('btn-gold','btn-secondary');
            addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
            addToCartButton.textContent = 'Ajouter au Panier';
            addToCartButton.disabled = false;
            addToCartButton.classList.replace('btn-secondary','btn-gold');
            addToCartButton.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    } else if (currentProductDetail && currentProductDetail.base_price === null && (!currentProductDetail.weight_options || currentProductDetail.weight_options.length === 0)) {
        // Fallback for products incorrectly configured (no base price, no variants)
        addToCartButton.textContent = 'Indisponible';
        addToCartButton.disabled = true;
        addToCartButton.classList.replace('btn-gold','btn-secondary');
        addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
    } else if (currentProductDetail && currentProductDetail.base_price !== null) {
        // This part handles products with a base_price (no variants selected or product has no variants)
        // It should be covered by the initial loadProductDetail logic.
        // If variants exist but none are selected (e.g. all out of stock), this might be a fallback.
        // Ensure addToCartButton state is correct for simple products too.
        if (currentProductDetail.stock_quantity <= 0) {
            addToCartButton.textContent = 'Épuisé';
            addToCartButton.disabled = true;
            addToCartButton.classList.replace('btn-gold','btn-secondary');
            addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
             addToCartButton.textContent = 'Ajouter au Panier';
            addToCartButton.disabled = false;
            addToCartButton.classList.replace('btn-secondary','btn-gold');
            addToCartButton.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    }
}

/**
 * Updates the quantity input on the product detail page.
 * @param {number} change - The amount to change the quantity by (+1 or -1).
 */
function updateDetailQuantity(change) {
    const quantityInput = document.getElementById('quantity-select');
    if (!quantityInput) return;
    let currentValue = parseInt(quantityInput.value);
    currentValue += change;
    if (currentValue < 1) currentValue = 1;
    if (currentValue > 10) currentValue = 10; // Max quantity limit
    quantityInput.value = currentValue;
}
