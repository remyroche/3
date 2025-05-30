// website/js/products.js
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
        // Use the public /products endpoint. Backend handles filtering for published products.
        const endpoint = category === 'all' ? '/products' : `/products?category=${encodeURIComponent(category)}`;
        // makeApiRequest is from api.js
        const response = await makeApiRequest(endpoint); // response is { success: true, products: [...] }
        
        if (!response || !response.success || !Array.isArray(response.products)) {
            console.error("Invalid product response format:", response);
            throw new Error(response.message || "Format de réponse des produits invalide ou échec de la requête.");
        }

        const productsToDisplay = response.products;

        if (category === 'all' && productsToDisplay.length > 0) {
            allProducts = productsToDisplay; // Cache all products if fetching all
        }

        if (productsToDisplay.length === 0) {
            loadingMessageElement.textContent = "Aucun produit trouvé dans cette catégorie.";
            productsGrid.innerHTML = `<p class="col-span-full text-center text-brand-earth-brown py-8">Aucun produit à afficher.</p>`;
        } else {
            loadingMessageElement.style.display = 'none';
            productsToDisplay.forEach(product => {
                // Determine stock message and button state
                let stockMessageHTML = '';
                let addToCartButtonHTML = '';

                if (product.weight_options && product.weight_options.length > 0) {
                    // For products with variants, link to detail page
                    addToCartButtonHTML = `
                        <a href="produit-detail.html?id=${product.id}" class="block w-full text-center bg-brand-warm-taupe hover:bg-brand-warm-taupe/90 text-brand-cream font-semibold py-2 px-4 rounded transition-colors duration-300">
                            Ajouter au Panier
                        </a>`;
                    // Stock message could indicate if any variant is available, or just omit for simplicity on listing
                } else { // Simple product
                    if (product.stock_quantity > 0) {
                        addToCartButtonHTML = `
                            <button data-product-id="${product.id}" class="add-to-cart-list-btn w-full bg-brand-warm-taupe hover:bg-brand-warm-taupe/90 text-brand-cream font-semibold py-2 px-4 rounded transition-colors duration-300">
                                Ajouter au Panier
                            </button>`;
                    } else {
                        stockMessageHTML = `<p class="text-xs text-brand-truffle-burgundy mb-1">Épuisé</p>`;
                        addToCartButtonHTML = `
                            <button class="w-full bg-stone-400 text-white font-semibold py-2 px-4 rounded cursor-not-allowed" disabled>
                                Épuisé
                            </button>`; // This will be changed below to warm-taupe
                    }
                }
                // Apply warm-taupe color to the disabled button as well
                if (product.stock_quantity <= 0 && !product.weight_options) {
                     addToCartButtonHTML = `
                        <button class="w-full bg-brand-warm-taupe text-brand-cream font-semibold py-2 px-4 rounded cursor-not-allowed opacity-50" disabled>
                            Épuisé
                        </button>`;
                }
                const productCardHTML = `
                    <div class="product-card">
                        <a href="produit-detail.html?id=${product.id}">
                            <img src="${product.main_image_full_url || product.image_url_main || 'https://placehold.co/400x300/F5EEDE/7D6A4F?text=Image+Indisponible'}" alt="${product.name}" class="w-full h-64 object-cover" onerror="this.onerror=null;this.src='https://placehold.co/400x300/F5EEDE/7D6A4F?text=Image+Erreur';">
                        </a>
                        <div class="product-card-content p-4">
                            <a href="produit-detail.html?id=${product.id}" class="hover:text-brand-classic-gold transition-colors">
                                <h3 class="text-xl font-serif font-semibold text-brand-near-black mb-2">${product.name}</h3>
                            </a>
                            <p class="text-brand-earth-brown text-sm mb-3 h-16 overflow-hidden">${product.short_description || ''}</p>
                            ${stockMessageHTML}                            <div class="mt-auto pt-2">${addToCartButtonHTML}</div>
                        </div>
                    </div>
                `;
                productsGrid.insertAdjacentHTML('beforeend', productCardHTML);

                // Add event listener for "Ajouter au Panier" button if it exists for this card
                const newCardElement = productsGrid.lastElementChild;
                const addToCartBtn = newCardElement.querySelector('.add-to-cart-list-btn');
                if (addToCartBtn) {
                    // The 'product' variable from the forEach loop is in scope here.
                    // It contains the necessary details for cart.js's addToCart function.
                    addToCartBtn.addEventListener('click', () => {
                        window.addToCart(product, 1, null); // product is from the forEach loop, null for variantInfo
                    });
                }
            });
        }
    } catch (error) {
        loadingMessageElemeOnt.textContent = "Erreur lors du chargement des produits.";
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
    console.log('[products.js] loadProductDetail: Starting to load product detail.');
    const params = new URLSearchParams(window.location.search);
    const productId = params.get('id');
    const loadingDiv = document.getElementById('product-detail-loading');
    const contentDiv = document.getElementById('product-detail-content');

    if (!productId) {
        if(loadingDiv) loadingDiv.textContent = "Aucun produit spécifié.";
        console.warn('[products.js] loadProductDetail: No product ID found in URL.');
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
        mainImage.src = product.main_image_full_url || product.image_url_main || 'https://placehold.co/600x500/F5EEDE/7D6A4F?text=Image';
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
                optionElement.textContent = `${opt.weight_grams}g - ${parseFloat(opt.price).toFixed(2)} € ${opt.stock_quantity <= 0 ? '(Épuisé)' : ''}`;
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
        // document.getElementById('product-origin').textContent = product.origin || 'N/A'; // Already commented out
        // document.getElementById('product-seasonality').textContent = product.seasonality || 'N/A'; // Already commented out
        
        // To remove the "Utilisations idéales" data, we comment out the line that populates it.
        // You will also need to remove the corresponding "Utilisations idéales" label from your produit-detail.html file.
        // document.getElementById('product-uses').textContent = product.ideal_uses || 'N/A';
        document.getElementById('product-sensory-description').innerHTML = product.long_description || product.sensory_description || 'Aucune description détaillée disponible.';
        document.getElementById('product-pairing-suggestions').textContent = product.pairing_suggestions || 'Aucune suggestion d\'accord disponible.';
        
        const thumbnailGallery = document.getElementById('product-thumbnail-gallery');
        thumbnailGallery.innerHTML = ''; 
        if (product.additional_images && Array.isArray(product.additional_images) && product.additional_images.length > 0) {
            product.additional_images.forEach(imgData => {
                const thumbUrl = imgData.image_full_url || imgData.image_url;
                if (thumbUrl) {
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
        console.log('[products.js] loadProductDetail: Product details displayed. Attempting to initialize quantity controls.');
        initializeQuantityControls(); // Initialize quantity +/- buttons
    } catch (error) {
        currentProductDetail = null; // Reset on error
        console.error("ERREUR DÉTAILLÉE dans loadProductDetail:", error); // Log the full error object
        console.error('[products.js] loadProductDetail: Catch block executed. Error loading product details.');
        const errorMsg = (error instanceof Error) ? error.message : "Une erreur inconnue est survenue lors du chargement des détails.";
        if (loadingDiv) {
            loadingDiv.innerHTML = `<p class="text-brand-truffle-burgundy">Impossible de charger les détails du produit: ${errorMsg}</p>`;
            loadingDiv.style.display = 'block'; // Ensure it's visible
        } else {
            console.error("L'élément 'product-detail-loading' est introuvable dans le DOM (catch block).");
        }
        if (contentDiv) {
            contentDiv.style.display = 'none';
        }
    }
}

/**
 * Initializes the quantity control buttons (+/-) on the product detail page.
 * This function should be called after the product detail content,
 * including the quantity controls, is loaded into the DOM.
 */
function initializeQuantityControls() {
    console.log('[products.js] initializeQuantityControls: Function called.');
    const quantityContainer = document.getElementById('quantity-select-controls');
    if (!quantityContainer) {
        console.warn('[products.js] initializeQuantityControls: Quantity container #quantity-select-controls NOT FOUND.');
        // This can happen if the function is called on a page without these controls (should not be the case here)
        // or before the DOM elements are ready.
        return;
    }

    const quantityInput = quantityContainer.querySelector('#quantity-select');

    if (!quantityInput) {
        console.warn('[products.js] initializeQuantityControls: Input #quantity-select not found.');
        return;
    }
    console.log('[products.js] initializeQuantityControls: Quantity input found. Adding input event listener.');

    quantityInput.addEventListener('input', () => {
        console.log(`[products.js] Quantity input changed. New raw value: "${quantityInput.value}"`);
        let currentValue = parseInt(quantityInput.value, 10);
        const minVal = parseInt(quantityInput.min, 10);
        const maxVal = parseInt(quantityInput.max, 10);

        if (isNaN(currentValue)) {
            // If user types non-numeric or clears input, reset to min
            quantityInput.value = minVal;
            console.log(`[products.js] Input NaN, reset to min: ${minVal}`);
            return;
        }

        if (!isNaN(minVal) && currentValue < minVal) {
            quantityInput.value = minVal;
            console.log(`[products.js] Input below min, clamped to: ${minVal}`);
        } else if (!isNaN(maxVal) && currentValue > maxVal) {
            quantityInput.value = maxVal;
            console.log(`[products.js] Input above max, clamped to: ${maxVal}`);
        }
    });

    console.log('[products.js] initializeQuantityControls: Input event listener attached to #quantity-select.');
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
 * Reads min/max values from the input's attributes.
 * @param {number} change - The amount to change the quantity by (+1 or -1).
 */
function updateDetailQuantity(change) {
    console.log(`[products.js] updateDetailQuantity: Called with change = ${change}`);
    const quantityInput = document.getElementById('quantity-select');
    if (!quantityInput) {
        console.warn('Quantity input #quantity-select not found for updateDetailQuantity.');
        return;
    }
    console.log(`[products.js] updateDetailQuantity: Current input value = "${quantityInput.value}"`);

    let currentValue = parseInt(quantityInput.value, 10);
    // If parsing fails (e.g. empty string or non-numeric), try to get a default from min attribute or 1
    if (isNaN(currentValue)) {
        currentValue = parseInt(quantityInput.min, 10);
        if (isNaN(currentValue)) { // If min is also not a number or not set
            currentValue = 1; // Default to 1
        }
    }

    currentValue += change;

    const minVal = parseInt(quantityInput.min, 10);
    const maxVal = parseInt(quantityInput.max, 10);

    // Apply min boundary
    if (!isNaN(minVal) && currentValue < minVal) {
        currentValue = minVal;
    } else if (isNaN(minVal) && currentValue < 1) { // Fallback if min attribute is missing/invalid
        currentValue = 1; // Default min
    }
    // Apply max boundary (ensure maxVal is a number before comparing)
    if (!isNaN(maxVal) && currentValue > maxVal) {
        currentValue = maxVal;
    }
    quantityInput.value = currentValue;
    console.log(`[products.js] updateDetailQuantity: New input value = ${currentValue}`);
}

/**
 * Handles adding the currently detailed product to the cart.
 * Gathers quantity and selected variant (if any).
 */
function handleAddToCartFromDetail() {
    if (!currentProductDetail) {
        console.error("Product details (currentProductDetail) not available to add to cart.");
        showGlobalMessage("Erreur: Impossible d'ajouter le produit car les détails sont manquants.", "error");
        return;
    }

    const quantityInput = document.getElementById('quantity-select');
    const quantity = quantityInput ? parseInt(quantityInput.value) : 1;

    const weightOptionsSelect = document.getElementById('weight-options-select');
    let variantInfoForCart = null; // This is the third argument for addToCart function in cart.js

    // Check if the product uses weight options and a valid one is selected
    if (currentProductDetail.weight_options && currentProductDetail.weight_options.length > 0 && weightOptionsSelect && weightOptionsSelect.value) {
        const selectedOptionElement = weightOptionsSelect.options[weightOptionsSelect.selectedIndex];
        
        if (selectedOptionElement && selectedOptionElement.dataset.price && !selectedOptionElement.disabled) {
            const selectedVariantId = parseInt(selectedOptionElement.value); // This is product_weight_options.id
            const selectedVariantData = currentProductDetail.weight_options.find(opt => opt.option_id === selectedVariantId);

            if (selectedVariantData) {
                variantInfoForCart = { // Structure this as expected by cart.js's addToCart variantInfo parameter
                    id: selectedVariantData.option_id,
                    weight_grams: selectedVariantData.weight_grams,
                    price: parseFloat(selectedVariantData.price),
                    // sku_suffix: selectedVariantData.sku_suffix, // if you have SKU suffixes and need them
                };
            } else {
                showGlobalMessage("Erreur: Variante sélectionnée non valide ou introuvable.", "error");
                return;
            }
        } // If no valid option selected or all are disabled, variantInfoForCart remains null. addToCart will use base_price if applicable.
    }
    addToCart(currentProductDetail, quantity, variantInfoForCart); // addToCart is from cart.js
}
window.handleAddToCartFromDetail = handleAddToCartFromDetail; // Make it globally accessible for main.js
