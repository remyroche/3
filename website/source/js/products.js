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
    const loadingMessageElement = document.getElementById('products-loading-message');// website/js/products.js
// Handles fetching and displaying products on listing and detail pages.

let allProducts = []; 
let currentProductDetail = null; 

/**
 * Fetches products from the API and displays them on the product listing page.
 * @param {string} [category='all'] - The category to filter by. 'all' fetches all products.
 */
async function fetchAndDisplayProducts(category = 'all') {
    const productsGrid = document.getElementById('products-grid');
    const loadingMessageElement = document.getElementById('products-loading-message');
    
    if (!productsGrid || !loadingMessageElement) {
        console.error("Product grid or loading message elements not found."); // No t() here, dev console
        return;
    }

    loadingMessageElement.textContent = t('public.products_page.loading');
    loadingMessageElement.style.display = 'block';
    productsGrid.innerHTML = ''; 

    try {
        const endpoint = category === 'all' ? '/products' : `/products?category=${encodeURIComponent(category)}`;
        const response = await makeApiRequest(endpoint); 
        
        if (!response || !response.success || !Array.isArray(response.products)) {
            console.error("Invalid product response format:", response);
            throw new Error(response.message || t('public.js.product_load_error')); // Using translated error
        }

        const productsToDisplay = response.products;

        if (category === 'all' && productsToDisplay.length > 0) {
            allProducts = productsToDisplay; 
        }

        if (productsToDisplay.length === 0) {
            loadingMessageElement.textContent = t('public.js.no_products_found');
            productsGrid.innerHTML = `<p class="col-span-full text-center text-brand-earth-brown py-8">${t('public.js.no_products_found')}</p>`;
        } else {
            loadingMessageElement.style.display = 'none';
            productsToDisplay.forEach(product => {
                let stockMessageHTML = '';
                let addToCartButtonHTML = '';

                if (product.weight_options && product.weight_options.length > 0) {
                    addToCartButtonHTML = `
                        <a href="produit-detail.html?id=${product.id}" class="block w-full text-center bg-brand-warm-taupe hover:bg-brand-warm-taupe/90 text-brand-cream font-semibold py-2 px-4 rounded transition-colors duration-300">
                            ${t('public.products_page.add_to_cart')}
                        </a>`;
                } else { 
                    if (product.stock_quantity > 0) {
                        addToCartButtonHTML = `
                            <button data-product-id="${product.id}" class="add-to-cart-list-btn w-full bg-brand-warm-taupe hover:bg-brand-warm-taupe/90 text-brand-cream font-semibold py-2 px-4 rounded transition-colors duration-300">
                                ${t('public.products_page.add_to_cart')}
                            </button>`;
                    } else {
                        stockMessageHTML = `<p class="text-xs text-brand-truffle-burgundy mb-1">${t('public.products_page.out_of_stock')}</p>`;
                        addToCartButtonHTML = `
                            <button class="w-full bg-stone-400 text-white font-semibold py-2 px-4 rounded cursor-not-allowed" disabled>
                                ${t('public.products_page.out_of_stock')}
                            </button>`;
                    }
                }
                if (product.stock_quantity <= 0 && !product.weight_options) {
                     addToCartButtonHTML = `
                        <button class="w-full bg-brand-warm-taupe text-brand-cream font-semibold py-2 px-4 rounded cursor-not-allowed opacity-50" disabled>
                            ${t('public.products_page.out_of_stock')}
                        </button>`;
                }
                const productCardHTML = `
                    <div class="product-card">
                        <a href="produit-detail.html?id=${product.id}">
                            <img src="${product.main_image_full_url || product.image_url_main || 'https://placehold.co/400x300/F5EEDE/7D6A4F?text=Image+Indisponible'}" alt="${product.name}" class="w-full h-64 object-cover" onerror="this.onerror=null;this.src='https://placehold.co/400x300/F5EEDE/7D6A4F?text=Image+Error';">
                        </a>
                        <div class="product-card-content p-4">
                            <a href="produit-detail.html?id=${product.id}" class="hover:text-brand-classic-gold transition-colors">
                                <h3 class="text-xl font-serif font-semibold text-brand-near-black mb-2">${product.name}</h3>
                            </a>
                            <p class="text-brand-earth-brown text-sm mb-3 h-16 overflow-hidden">${product.short_description || ''}</p>
                            ${stockMessageHTML}
                            <div class="mt-auto pt-2">${addToCartButtonHTML}</div>
                        </div>
                    </div>
                `;
                productsGrid.insertAdjacentHTML('beforeend', productCardHTML);

                const newCardElement = productsGrid.lastElementChild;
                const addToCartBtn = newCardElement.querySelector('.add-to-cart-list-btn');
                if (addToCartBtn) {
                    addToCartBtn.addEventListener('click', () => {
                        window.addToCart(product, 1, null); 
                    });
                }
            });
        }
    } catch (error) {
        loadingMessageElement.textContent = t('public.js.product_load_error');
        productsGrid.innerHTML = `<p class="col-span-full text-center text-brand-truffle-burgundy py-8">${t('public.js.product_load_error')} ${error.message}</p>`;
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
        if(loadingDiv) loadingDiv.textContent = t('public.js.no_product_specified');
        if(contentDiv) contentDiv.style.display = 'none';
        return;
    }
    
    if(loadingDiv) loadingDiv.style.display = 'block';
    if(contentDiv) contentDiv.style.display = 'none';

    try {
        const product = await makeApiRequest(`/products/${productId}`);
        currentProductDetail = product;

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
            weightOptionsSelect.innerHTML = '';
            product.weight_options.forEach(opt => {
                const optionElement = document.createElement('option');
                optionElement.value = opt.option_id;
                let optionText = `${opt.weight_grams}g - ${parseFloat(opt.price).toFixed(2)} €`;
                if(opt.stock_quantity <= 0) optionText += ` (${t('public.products_page.out_of_stock')})`;
                optionElement.textContent = optionText;
                optionElement.dataset.price = opt.price;
                optionElement.dataset.stock = opt.stock_quantity;
                optionElement.dataset.weightGrams = opt.weight_grams;
                if(opt.stock_quantity <= 0) optionElement.disabled = true;
                weightOptionsSelect.appendChild(optionElement);
            });
            
            let firstEnabledIndex = -1;
            for(let i=0; i<weightOptionsSelect.options.length; i++) {
                if(!weightOptionsSelect.options[i].disabled) {
                    firstEnabledIndex = i;
                    break;
                }
            }
            if(firstEnabledIndex !== -1) weightOptionsSelect.selectedIndex = firstEnabledIndex;
            
            updatePriceFromSelection(); 
            weightOptionsSelect.addEventListener('change', updatePriceFromSelection);
        } else if (product.base_price !== null) {
            priceDisplay.textContent = `${parseFloat(product.base_price).toFixed(2)} €`;
            priceUnit.textContent = ''; 
            weightOptionsContainer.classList.add('hidden');
             if (product.stock_quantity <= 0) {
                addToCartButton.textContent = t('public.products_page.out_of_stock');
                addToCartButton.disabled = true;
                addToCartButton.classList.replace('btn-gold','btn-secondary'); 
                addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
            }
        } else { 
            priceDisplay.textContent = t('public.product_detail.price_on_request');
            priceUnit.textContent = '';
            weightOptionsContainer.classList.add('hidden');
            addToCartButton.textContent = t('public.product_detail.unavailable');
            addToCartButton.disabled = true;
            addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
        }

        document.getElementById('product-species').textContent = product.species || 'N/A';
        document.getElementById('product-uses').textContent = product.ideal_uses || 'N/A';
        document.getElementById('product-sensory-description').innerHTML = product.long_description || product.sensory_description || t('public.product_detail.no_description');
        document.getElementById('product-pairing-suggestions').textContent = product.pairing_suggestions || t('public.product_detail.no_pairings');
        
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
                    img.onerror = () => { img.style.display='none'; }; 
                    thumbnailGallery.appendChild(img);
                }
            });
        }
        if(loadingDiv) loadingDiv.style.display = 'none';
        if(contentDiv) contentDiv.style.display = 'grid'; 
        initializeQuantityControls(); 
    } catch (error) {
        currentProductDetail = null; 
        console.error("Error in loadProductDetail:", error);
        const errorMsg = (error instanceof Error) ? error.message : t('public.js.product_detail_load_error');
        if (loadingDiv) {
            loadingDiv.innerHTML = `<p class="text-brand-truffle-burgundy">${t('public.js.product_detail_load_error')}: ${errorMsg}</p>`;
            loadingDiv.style.display = 'block'; 
        }
        if (contentDiv) {
            contentDiv.style.display = 'none';
        }
    }
}

/**
 * Initializes the quantity control buttons (+/-) on the product detail page.
 */
function initializeQuantityControls() {
    const quantityContainer = document.getElementById('quantity-select-controls');
    if (!quantityContainer) return;

    const quantityInput = quantityContainer.querySelector('#quantity-select');
    if (!quantityInput) return;

    quantityInput.addEventListener('input', () => {
        let currentValue = parseInt(quantityInput.value, 10);
        const minVal = parseInt(quantityInput.min, 10);
        const maxVal = parseInt(quantityInput.max, 10);

        if (isNaN(currentValue)) {
            quantityInput.value = minVal;
            return;
        }
        if (!isNaN(minVal) && currentValue < minVal) quantityInput.value = minVal;
        else if (!isNaN(maxVal) && currentValue > maxVal) quantityInput.value = maxVal;
    });
}

/**
 * Updates the displayed price and add-to-cart button state based on the selected weight option.
 */
function updatePriceFromSelection() {
    const weightOptionsSelect = document.getElementById('weight-options-select');
    const priceDisplay = document.getElementById('product-price-display');
    const priceUnit = document.getElementById('product-price-unit');
    const addToCartButton = document.getElementById('add-to-cart-button');

    if (!weightOptionsSelect || !priceDisplay || !priceUnit || !addToCartButton) return;
    
    const selectedOption = weightOptionsSelect.options[weightOptionsSelect.selectedIndex];

    if (selectedOption && selectedOption.value) { 
        priceDisplay.textContent = `${parseFloat(selectedOption.dataset.price).toFixed(2)} €`;
        priceUnit.textContent = `/ ${selectedOption.dataset.weightGrams}g`;
        if (parseInt(selectedOption.dataset.stock) <= 0 || selectedOption.disabled) {
            addToCartButton.textContent = t('public.products_page.out_of_stock');
            addToCartButton.disabled = true;
            addToCartButton.classList.replace('btn-gold','btn-secondary');
            addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
            addToCartButton.textContent = t('public.products_page.add_to_cart');
            addToCartButton.disabled = false;
            addToCartButton.classList.replace('btn-secondary','btn-gold');
            addToCartButton.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    } else if (currentProductDetail && currentProductDetail.base_price === null && (!currentProductDetail.weight_options || currentProductDetail.weight_options.length === 0)) {
        addToCartButton.textContent = t('public.product_detail.unavailable');
        addToCartButton.disabled = true;
        addToCartButton.classList.replace('btn-gold','btn-secondary');
        addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
    } else if (currentProductDetail && currentProductDetail.base_price !== null) {
        if (currentProductDetail.stock_quantity <= 0) {
            addToCartButton.textContent = t('public.products_page.out_of_stock');
            addToCartButton.disabled = true;
            addToCartButton.classList.replace('btn-gold','btn-secondary');
            addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
             addToCartButton.textContent = t('public.products_page.add_to_cart');
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

    let currentValue = parseInt(quantityInput.value, 10);
    if (isNaN(currentValue)) {
        currentValue = parseInt(quantityInput.min, 10) || 1;
    }
    currentValue += change;

    const minVal = parseInt(quantityInput.min, 10);
    const maxVal = parseInt(quantityInput.max, 10);

    if (!isNaN(minVal) && currentValue < minVal) currentValue = minVal;
    else if (isNaN(minVal) && currentValue < 1) currentValue = 1;
    if (!isNaN(maxVal) && currentValue > maxVal) currentValue = maxVal;
    
    quantityInput.value = currentValue;
}

/**
 * Handles adding the currently detailed product to the cart.
 */
function handleAddToCartFromDetail() {
    if (!currentProductDetail) {
        showGlobalMessage(t('public.js.add_to_cart_error_missing_details'), "error");
        return;
    }

    const quantityInput = document.getElementById('quantity-select');
    const quantity = quantityInput ? parseInt(quantityInput.value) : 1;

    const weightOptionsSelect = document.getElementById('weight-options-select');
    let variantInfoForCart = null; 

    if (currentProductDetail.weight_options && currentProductDetail.weight_options.length > 0 && weightOptionsSelect && weightOptionsSelect.value) {
        const selectedOptionElement = weightOptionsSelect.options[weightOptionsSelect.selectedIndex];
        
        if (selectedOptionElement && selectedOptionElement.dataset.price && !selectedOptionElement.disabled) {
            const selectedVariantId = parseInt(selectedOptionElement.value); 
            const selectedVariantData = currentProductDetail.weight_options.find(opt => opt.option_id === selectedVariantId);

            if (selectedVariantData) {
                variantInfoForCart = { 
                    id: selectedVariantData.option_id,
                    weight_grams: selectedVariantData.weight_grams,
                    price: parseFloat(selectedVariantData.price),
                };
            } else {
                showGlobalMessage(t('public.js.invalid_variant_selected'), "error");
                return;
            }
        } 
    }
    addToCart(currentProductDetail, quantity, variantInfoForCart); 
}
window.handleAddToCartFromDetail = handleAddToCartFromDetail;
