// website/source/js/products.js
// Manages fetching, displaying, and interacting with products on listing and detail pages.

// --- Global Variables / State ---
let allProductsData = []; // Cache for products, useful for filtering on nos-produits.html
let currentProductDetail = null; // Stores the full detail of the product being viewed on produit-detail.html
const ITEMS_PER_PAGE_NOS_PRODUITS = 12; 
let currentPageNosProduits = 1;

// --- Helper Functions ---

/**
 * Gets the current language from the HTML tag.
 * @returns {string} The current language code (e.g., 'fr', 'en').
 */
function getCurrentLanguage() {
    return document.documentElement.lang || 'fr';
}

/**
 * Internationalization function placeholder.
 * @param {string} key - The translation key.
 * @param {string} [defaultValue] - The default string if key not found.
 * @param {object} [options] - Interpolation options.
 * @returns {string} The translated string.
 */
function t(key, defaultValue, options = {}) {
    const lang = getCurrentLanguage();
    let translation = defaultValue || key;
    if (window.translations && window.translations[lang] && window.translations[lang][key]) {
        translation = window.translations[lang][key];
    } else if (window.translations && window.translations['fr'] && window.translations['fr'][key]) { // Fallback to FR
        translation = window.translations['fr'][key];
    }

    for (const optKey in options) {
        translation = translation.replace(new RegExp(`{{${optKey}}}`, 'g'), options[optKey]);
    }
    return translation;
}

/**
 * Generates a URL-friendly slug from a string.
 * @param {string} text The text to slugify.
 * @returns {string} The slugified text.
 */
function generateSlug(text) {
    if (!text) return '';
    return text.toString().toLowerCase()
        .normalize('NFKD') // Normalize accented characters
        .replace(/[\u0300-\u036f]/g, '') // Remove diacritics
        .trim()
        .replace(/\s+/g, '-') // Replace spaces with -
        .replace(/[^\w-]+/g, '') // Remove all non-word chars
        .replace(/--+/g, '-'); // Replace multiple - with single -
}


/**
 * Gets the minimum price for a variable product (lowest price among its active options).
 * @param {object} product - The product object with weight_options.
 * @returns {string} The minimum price formatted to 2 decimal places, or 'N/A'.
 */
function getMinPriceForVariableProduct(product) {
    if (!product || !product.weight_options || product.weight_options.length === 0) {
        return 'N/A';
    }
    const activeOptions = product.weight_options.filter(opt => opt.is_active && (opt.aggregate_stock_quantity || 0) > 0);
    if (activeOptions.length === 0) { // If all active options are out of stock, check any active option for price
        const anyActiveOption = product.weight_options.find(opt => opt.is_active);
        return anyActiveOption ? parseFloat(anyActiveOption.price).toFixed(2) : 'N/A';
    }

    const minPrice = activeOptions.reduce((min, opt) => {
        return (opt.price < min) ? opt.price : min;
    }, activeOptions[0].price);
    return parseFloat(minPrice).toFixed(2);
}


/**
 * Creates a product card HTML element.
 * @param {object} product - The product data object.
 * @returns {HTMLElement} The product card element.
 */
function displayProductCard(product) {
    const card = document.createElement('div');
    card.className = 'product-card bg-white rounded-lg shadow-lg overflow-hidden transition-all duration-300 ease-in-out hover:shadow-xl relative flex flex-col';

    const lang = getCurrentLanguage();
    const productName = (lang === 'en' && product.name_en) ? product.name_en : product.name_fr;
    const productDescription = (lang === 'en' && product.description_en) ? product.description_en : product.description_fr;
    const productSlug = product.slug || generateSlug(productName || product.product_code);
    
    let stockStatusHTML = '';
    // Use the property from the backend model directly
    const stockQuantity = product.aggregate_stock_quantity !== undefined ? product.aggregate_stock_quantity : 0;


    if (stockQuantity <= 0) {
        stockStatusHTML = `<span class="stock-tag out-of-stock">${t('product.out_of_stock', 'Épuisé')}</span>`;
    } else if (stockQuantity < 10) {
        stockStatusHTML = `<span class="stock-tag low-stock">${t('product.low_stock_short', 'Stock faible!')}</span>`;
    } else {
        // Optionally, don't show "En Stock" if it's abundant to keep UI cleaner, or show it:
        // stockStatusHTML = `<span class="stock-tag in-stock">${t('product.in_stock', 'En Stock')}</span>`;
    }

    card.innerHTML = `
        <a href="produit-detail.html?slug=${productSlug}" class="block group">
            <div class="aspect-square overflow-hidden">
                <img src="${product.main_image_full_url || product.main_image_url || 'https://placehold.co/300x300/F5EEDE/11120D?text=Maison+Trüvra'}" 
                     alt="${t('product.image_alt', 'Image de {{productName}}', { productName: productName || 'produit' })}" 
                     class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300 ease-in-out">
            </div>
            ${stockStatusHTML}
        </a>
        <div class="p-4 flex flex-col flex-grow">
            <h3 class="text-lg font-semibold font-serif text-mt-near-black mb-1 truncate" title="${productName || ''}">
                <a href="produit-detail.html?slug=${productSlug}" class="hover:text-mt-truffle-burgundy">${productName || t('product.default_name', 'Produit Maison Trüvra')}</a>
            </h3>
            <p class="text-xs text-mt-warm-taupe mb-2 truncate">${product.category_name || t('product.no_category', 'Non catégorisé')}</p>
            <p class="text-sm text-mt-earth-brown mb-3 text-ellipsis overflow-hidden line-clamp-2" style="min-height: 2.5em;">
                ${productDescription || t('product.default_description_short', 'Découvrez ce produit exceptionnel.')}
            </p>
            <div class="mt-auto">
                <p class="text-xl font-bold text-mt-truffle-burgundy mb-3">
                    ${product.base_price ? `€${parseFloat(product.base_price).toFixed(2)}` : (product.type === 'variable_weight' || (product.type && product.type.value === 'variable_weight') ? t('product.price_from', 'À partir de') + ` €${getMinPriceForVariableProduct(product)}` : t('product.price_on_request', 'Prix sur demande'))}
                </p>
                <button 
                    class="btn btn-primary w-full add-to-cart-list-btn ${stockQuantity <= 0 ? 'disabled' : ''}" 
                    data-product-id="${product.id}" 
                    data-product-slug="${productSlug}"
                    ${stockQuantity <= 0 ? 'disabled' : ''}>
                    <i class="fas fa-shopping-cart mr-2"></i> 
                    ${stockQuantity <= 0 ? t('product.out_of_stock', 'Épuisé') : (product.type === 'variable_weight' || (product.type && product.type.value === 'variable_weight') ? t('product.view_options', 'Voir Options') : t('product.add_to_cart', 'Ajouter au Panier'))}
                </button>
            </div>
        </div>
    `;

    const addToCartButton = card.querySelector('.add-to-cart-list-btn');
    if (addToCartButton && stockQuantity > 0) {
        addToCartButton.addEventListener('click', (e) => {
            e.stopPropagation();
            if (product.type === 'variable_weight' || (product.type && product.type.value === 'variable_weight')) {
                window.location.href = `produit-detail.html?slug=${productSlug}`;
            } else {
                // Pass the full product object, assuming it contains aggregate_stock_quantity
                if (typeof addToCart === 'function') { // Ensure addToCart from cart.js is available
                    addToCart(product, 1); 
                } else {
                    console.error("addToCart function not found. Ensure cart.js is loaded.");
                }
            }
        });
    }
    return card;
}

/**
 * Fetches and displays products on the "Nos Produits" page.
 */
async function fetchAndDisplayProducts(page = 1, categorySlug = null, searchTerm = null) {
    const productListContainer = document.getElementById('product-list-container');
    const paginationContainer = document.getElementById('pagination-container');
    const loadingIndicator = document.getElementById('loading-indicator'); // Assuming you have one

    if (!productListContainer) {
        // console.warn("Product list container not found on this page ('nos-produits.html').");
        return;
    }

    if (loadingIndicator) loadingIndicator.classList.remove('hidden');
    productListContainer.innerHTML = ''; // Clear current products

    try {
        let apiUrl = `/products?page=${page}&limit=${ITEMS_PER_PAGE_NOS_PRODUITS}`;
        if (categorySlug) {
            apiUrl += `&category=${categorySlug}`;
        }
        if (searchTerm) {
            apiUrl += `&search=${encodeURIComponent(searchTerm)}`;
        }

        const response = await makeApiRequest(apiUrl, 'GET');
        
        if (response.error) {
            throw new Error(response.error.message || 'Failed to fetch products');
        }

        allProductsData = response.products || []; // Cache for client-side filtering if needed later or if API doesn't filter
        const totalProducts = response.total_products || allProductsData.length; // Use API total if available
        const totalPages = response.total_pages || Math.ceil(totalProducts / ITEMS_PER_PAGE_NOS_PRODUITS);
        currentPageNosProduits = response.current_page || page;


        if (allProductsData.length === 0) {
            productListContainer.innerHTML = `<p class="text-center col-span-full text-mt-earth-brown py-10">${t('product.no_products_found', 'Aucun produit trouvé correspondant à vos critères.')}</p>`;
        } else {
            allProductsData.forEach(product => {
                if(product.is_active){ // Double check active status on client, though API should handle it
                     productListContainer.appendChild(displayProductCard(product));
                }
            });
        }

        if (paginationContainer) {
            renderPagination(paginationContainer, currentPageNosProduits, totalPages, (newPage) => {
                fetchAndDisplayProducts(newPage, categorySlug, searchTerm);
                window.scrollTo(0,0); // Scroll to top on page change
            });
        }

    } catch (error) {
        console.error('Error fetching products:', error);
        productListContainer.innerHTML = `<p class="text-center col-span-full text-red-500">${t('product.error.load_failed_list', 'Impossible de charger les produits. Veuillez réessayer plus tard.')}</p>`;
         if(typeof showGlobalMessage === 'function') showGlobalMessage(t('product.error.load_failed_toast', 'Erreur chargement produits.'), 'error');
    } finally {
        if (loadingIndicator) loadingIndicator.classList.add('hidden');
    }
}


// --- Product Detail Page Specific Functions ---

/**
 * Loads product details on the produit-detail.html page.
 */
async function loadProductDetail() {
    const urlParams = new URLSearchParams(window.location.search);
    const productSlug = urlParams.get('slug');
    const productDetailContainer = document.getElementById('product-detail-container');

    if (!productDetailContainer) {
        // console.warn('Product detail container not found on this page.');
        return;
    }
    if (!productSlug) {
        productDetailContainer.innerHTML = `<p class="text-center text-red-500">${t('product_detail.error.no_slug', 'Produit non spécifié.')}</p>`;
        return;
    }

    try {
        const product = await makeApiRequest(`/products/slug/${productSlug}`, 'GET'); // Ensure this API endpoint exists
        
        if (!product || product.error || !product.id) { // Check for product.id to ensure valid product data
             productDetailContainer.innerHTML = `<p class="text-center text-red-500">${t('product_detail.error.not_found', 'Produit non trouvé.')}</p>`;
             console.error("Product not found or API error:", product?.error || "No product ID in response");
             return;
        }
        currentProductDetail = product; 

        const lang = getCurrentLanguage();
        const productName = (lang === 'en' && product.name_en) ? product.name_en : product.name_fr;
        const productDescription = (lang === 'en' && product.description_en) ? product.description_en : product.description_fr;
        const productLongDescription = (lang === 'en' && product.long_description_en) ? product.long_description_en : product.long_description_fr;
        const sensoryEvaluation = (lang === 'en' && product.sensory_evaluation_en) ? product.sensory_evaluation_en : product.sensory_evaluation_fr;
        const foodPairings = (lang === 'en' && product.food_pairings_en) ? product.food_pairings_en : product.food_pairings_fr;
        const species = (lang === 'en' && product.species_en) ? product.species_en : product.species_fr;


        document.title = `${productName || product.name} - Maison Trüvra`;
        document.getElementById('breadcrumb-product-name').textContent = productName || product.name;

        document.getElementById('product-name').textContent = productName || product.name;
        document.getElementById('product-short-description').innerHTML = productDescription || product.description || '';
        
        const categoryLink = document.getElementById('product-category-link');
        if (product.category_name && product.category_slug) {
            categoryLink.innerHTML = `<a href="nos-produits.html?category=${product.category_slug}" class="hover:underline">${product.category_name}</a>`;
        } else {
            categoryLink.textContent = product.category_name || t('product.no_category', 'Non catégorisé');
        }

        setupImageGallery(product.images, product.main_image_full_url || product.main_image_url, productName || product.name);
        
        const optionsContainer = document.getElementById('product-options-container');
        const priceDisplay = document.getElementById('product-price');
        const quantitySelect = document.getElementById('quantity-select');
        const stockIndicator = document.getElementById('stock-indicator');
        const addToCartBtnDetail = document.getElementById('add-to-cart-btn');

        optionsContainer.innerHTML = ''; 
        stockIndicator.innerHTML = ''; 

        let currentAvailableStockForDisplay = 0; // Used to set max on quantity input

        if (product.type === 'variable_weight' || (product.type && product.type.value === 'variable_weight')) {
            if (product.weight_options && product.weight_options.length > 0) {
                const activeOptions = product.weight_options.filter(opt => opt.is_active);
                if (activeOptions.length > 0) {
                    optionsContainer.innerHTML = `
                        <label for="weight-options-select" class="block text-sm font-medium text-mt-near-black mb-1" data-translate-key="product_detail.choose_option">Choisissez une option :</label>
                        <select id="weight-options-select" class="form-select w-full md:w-1/2 rounded-md border-mt-warm-taupe focus:ring-mt-classic-gold focus:border-mt-classic-gold">
                            ${activeOptions.map(opt => {
                                const stockForOption = opt.aggregate_stock_quantity || 0;
                                return `<option value="${opt.option_id}" data-price="${opt.price}" data-stock="${stockForOption}" ${stockForOption <= 0 ? 'disabled' : ''}>
                                    ${opt.weight_grams}g - €${parseFloat(opt.price).toFixed(2)} ${stockForOption <= 0 ? `(${t('product.out_of_stock_short', 'Épuisé')})` : ''}
                                </option>`;
                            }).join('')}
                        </select>
                    `;
                    const weightSelect = document.getElementById('weight-options-select');
                    if(weightSelect) {
                        weightSelect.addEventListener('change', updatePriceAndStockFromSelection);
                        updatePriceAndStockFromSelection(); 
                    } else { 
                         priceDisplay.textContent = t('product.unavailable', 'Indisponible');
                         disableAddToCartButton(addToCartBtnDetail, t('product.out_of_stock_short', 'Épuisé'));
                         updateStockDisplayAndQuantityInput(0, stockIndicator, quantitySelect, addToCartBtnDetail);
                    }
                } else {
                    priceDisplay.textContent = t('product.unavailable', 'Indisponible');
                    optionsContainer.innerHTML = `<p class="text-mt-earth-brown">${t('product_detail.no_options_available', 'Aucune option disponible pour ce produit.')}</p>`;
                    disableAddToCartButton(addToCartBtnDetail, t('product.unavailable', 'Indisponible'));
                    updateStockDisplayAndQuantityInput(0, stockIndicator, quantitySelect, addToCartBtnDetail);
                }
            } else {
                priceDisplay.textContent = t('product.unavailable', 'Indisponible');
                optionsContainer.innerHTML = `<p class="text-mt-earth-brown">${t('product_detail.no_options_configured', 'Options non configurées.')}</p>`;
                disableAddToCartButton(addToCartBtnDetail, t('product.unavailable', 'Indisponible'));
                updateStockDisplayAndQuantityInput(0, stockIndicator, quantitySelect, addToCartBtnDetail);
            }
        } else { 
            priceDisplay.textContent = `€${parseFloat(product.base_price).toFixed(2)}`;
            currentAvailableStockForDisplay = product.aggregate_stock_quantity || 0;
            updateStockDisplayAndQuantityInput(currentAvailableStockForDisplay, stockIndicator, quantitySelect, addToCartBtnDetail);
        }

        document.getElementById('product-long-description').innerHTML = productLongDescription || product.long_description || t('product_detail.no_long_description', 'Pas de description détaillée disponible.');
        
        const sensoryAccordion = document.getElementById('sensory-evaluation-accordion');
        const sensoryP = document.getElementById('product-sensory-evaluation');
        if (sensoryEvaluation) {
            sensoryP.innerHTML = sensoryEvaluation; // Assuming it might contain HTML
            if (sensoryAccordion) sensoryAccordion.style.display = 'block';
        } else {
            if (sensoryAccordion) sensoryAccordion.style.display = 'none';
        }

        const pairingsAccordion = document.getElementById('food-pairings-accordion');
        const pairingsP = document.getElementById('product-food-pairings');
        if (foodPairings) {
            pairingsP.innerHTML = foodPairings; // Assuming it might contain HTML
            if (pairingsAccordion) pairingsAccordion.style.display = 'block';
        } else {
             if (pairingsAccordion) pairingsAccordion.style.display = 'none';
        }
        
        const speciesAccordion = document.getElementById('species-accordion');
        const speciesP = document.getElementById('product-species');
        if (species) {
            speciesP.textContent = species;
            if (speciesAccordion) speciesAccordion.style.display = 'block';
        } else {
            if (speciesAccordion) speciesAccordion.style.display = 'none';
        }

        const codeDisplay = document.querySelector('#product-code-display span');
        if(codeDisplay) codeDisplay.textContent = product.product_code || 'N/A';
        const preservationDisplay = document.querySelector('#product-preservation-display span');
        if(preservationDisplay && product.preservation_type) {
             preservationDisplay.textContent = t(`product.preservation.${product.preservation_type}`, product.preservation_type) 
        } else if (preservationDisplay) {
            preservationDisplay.textContent = 'N/A';
        }


        if (addToCartBtnDetail) {
            addToCartBtnDetail.removeEventListener('click', handleAddToCartFromDetail); // Remove previous if any
            addToCartBtnDetail.addEventListener('click', handleAddToCartFromDetail);
        }
        
        initializeAccordions();
        // loadProductReviews(product.id); 
        // loadRelatedProducts(product.category_id, product.id);

    } catch (error) {
        console.error('Failed to load product details:', error);
        productDetailContainer.innerHTML = `<p class="text-center text-red-500">${t('product_detail.error.load_failed', 'Impossible de charger les détails du produit.')} ${error.message || ''}</p>`;
        if (typeof showGlobalMessage === 'function') showGlobalMessage(t('product_detail.error.load_failed_toast', 'Erreur chargement détails produit.'), 'error');
    }
}

function handleAddToCartFromDetail() {
    const quantitySelect = document.getElementById('quantity-select');
    if (!currentProductDetail || !quantitySelect) return; 

    const quantity = parseInt(quantitySelect.value, 10);
    let selectedVariantInfo = null;
    
    if (currentProductDetail.type === 'variable_weight' || (currentProductDetail.type && currentProductDetail.type.value === 'variable_weight')) {
        const weightSelect = document.getElementById('weight-options-select');
        if (weightSelect && weightSelect.value) {
            const selectedOptionElement = weightSelect.options[weightSelect.selectedIndex];
            // Find the full option object from currentProductDetail to get all its details
            selectedVariantInfo = currentProductDetail.weight_options.find(opt => opt.option_id == selectedOptionElement.value);
            if (!selectedVariantInfo) { // Fallback if find by option_id fails somehow
                selectedVariantInfo = { 
                    option_id: selectedOptionElement.value,
                    weight_grams: parseFloat(selectedOptionElement.text.match(/(\d+(\.\d+)?)g/)[0]), // Attempt to parse weight
                    price: parseFloat(selectedOptionElement.dataset.price),
                    aggregate_stock_quantity: parseInt(selectedOptionElement.dataset.stock, 10) || 0,
                    // Try to find sku_suffix, crucial for backend identification
                    sku_suffix: currentProductDetail.weight_options.find(opt => opt.option_id == selectedOptionElement.value)?.sku_suffix || '' 
                };
            }
        } else if (currentProductDetail.weight_options && currentProductDetail.weight_options.length > 0) {
             if(typeof showGlobalMessage === 'function') showGlobalMessage(t('product_detail.error.select_option', 'Veuillez sélectionner une option.'), 'error');
            return;
        }
    }
    if (typeof addToCart === 'function') {
        addToCart(currentProductDetail, quantity, selectedVariantInfo);
    } else {
        console.error("addToCart function not found. Ensure cart.js is loaded.");
    }
}


function updatePriceAndStockFromSelection() {
    const weightSelect = document.getElementById('weight-options-select');
    const priceDisplay = document.getElementById('product-price');
    const quantitySelect = document.getElementById('quantity-select');
    const stockIndicator = document.getElementById('stock-indicator');
    const addToCartBtnDetail = document.getElementById('add-to-cart-btn');

    if (!weightSelect || !priceDisplay || !quantitySelect || !stockIndicator || !addToCartBtnDetail || !currentProductDetail || !currentProductDetail.weight_options) {
        // console.warn("One or more elements for price/stock update are missing, or currentProductDetail not set.");
        // If it's a simple product, this function shouldn't be called after initial setup.
        // This check is more for variable products where weightSelect is key.
        if (currentProductDetail && (currentProductDetail.type === 'simple' || (currentProductDetail.type && currentProductDetail.type.value === 'simple'))) {
            return; // No options to select for simple products
        }
        // If elements are missing on variable product page, it's an issue.
        if (!weightSelect && currentProductDetail && (currentProductDetail.type === 'variable_weight' || (currentProductDetail.type.value === 'variable_weight'))){
            disableAddToCartButton(addToCartBtnDetail, t('product.unavailable', 'Indisponible'));
            if(stockIndicator) stockIndicator.innerHTML = `<span class="text-red-600">${t('product_detail.no_options_available', 'Aucune option disponible.')}</span>`;
            if(priceDisplay) priceDisplay.textContent = "N/A";
            if(quantitySelect) {
                quantitySelect.max = "0"; quantitySelect.value = "0"; quantitySelect.disabled = true;
            }
        }
        return;
    }

    const selectedOptionElement = weightSelect.options[weightSelect.selectedIndex];
    if (selectedOptionElement && selectedOptionElement.value && selectedOptionElement.dataset.price) { // Check if it's a real option not a placeholder
        priceDisplay.textContent = `€${parseFloat(selectedOptionElement.dataset.price).toFixed(2)}`;
        const stock = parseInt(selectedOptionElement.dataset.stock, 10) || 0;
        updateStockDisplayAndQuantityInput(stock, stockIndicator, quantitySelect, addToCartBtnDetail);
    } else if (currentProductDetail.weight_options.length > 0 && (!selectedOptionElement || !selectedOptionElement.value) ) { 
        priceDisplay.textContent = t('product_detail.price_select_option', 'Prix selon option');
        disableAddToCartButton(addToCartBtnDetail, t('product_detail.select_option_prompt', 'Choisir option'));
        if(stockIndicator) stockIndicator.innerHTML = `<span class="text-mt-warm-taupe">${t('product_detail.select_option_for_stock', 'Sélectionnez une option pour voir le stock.')}</span>`;
        if(quantitySelect) {
            quantitySelect.max = "1"; 
            quantitySelect.value = "1";
            quantitySelect.disabled = true; 
        }
    } else { // No options, or invalid selection
        disableAddToCartButton(addToCartBtnDetail, t('product.unavailable', 'Indisponible'));
        if(stockIndicator) stockIndicator.innerHTML = `<span class="text-red-600">${t('product.unavailable', 'Indisponible')}</span>`;
        if(priceDisplay) priceDisplay.textContent = "N/A";
        if(quantitySelect) {
            quantitySelect.max = "0";
            quantitySelect.value = "0";
            quantitySelect.disabled = true;
        }
    }
}

function updateStockDisplayAndQuantityInput(stock, stockIndicatorEl, quantityInputEl, addToCartButtonEl) {
    if (!quantityInputEl || !stockIndicatorEl || !addToCartButtonEl) {
        // console.warn("Missing elements for stock display update: stockIndicator, quantityInput, or addToCartButton");
        return;
    }

    quantityInputEl.max = stock > 0 ? stock.toString() : "0";

    if (stock <= 0) {
        stockIndicatorEl.innerHTML = `<span class="text-red-600 font-semibold">${t('product.out_of_stock', 'Épuisé')}</span>`;
        quantityInputEl.value = "0";
        quantityInputEl.min = "0"; 
        quantityInputEl.disabled = true;
        disableAddToCartButton(addToCartButtonEl, t('product.out_of_stock', 'Épuisé'));
    } else {
        quantityInputEl.disabled = false;
        quantityInputEl.min = "1"; 
        // Ensure current value is not more than new stock, and not less than 1
        let currentVal = parseInt(quantityInputEl.value);
        if (isNaN(currentVal) || currentVal <= 0) {
             quantityInputEl.value = "1";
        } else if (currentVal > stock) {
            quantityInputEl.value = stock.toString(); // Adjust to max available if current value exceeds
        }
        
        if (stock < 10) {
            stockIndicatorEl.innerHTML = `<span class="text-mt-truffle-burgundy font-semibold">${t('product.low_stock_detail', 'Stock faible : Plus que {{count}} en stock !', { count: stock })}</span>`;
        } else {
            stockIndicatorEl.innerHTML = `<span class="text-mt-deep-sage-green">${t('product.in_stock_many', 'En stock')}</span>`;
        }
        enableAddToCartButton(addToCartButtonEl);
    }
}

function disableAddToCartButton(button, messageKey = 'product.out_of_stock') {
    if(button) {
        button.disabled = true;
        // Use a general disabled class if you have one, or specific Tailwind classes
        button.classList.add('opacity-50', 'cursor-not-allowed', 'bg-gray-400', 'hover:bg-gray-400'); 
        button.classList.remove('btn-primary'); // Remove primary styling if it interferes
        const span = button.querySelector('span'); // Assuming button text is in a span
        if(span) span.textContent = t(messageKey, 'Indisponible');
        else button.textContent = t(messageKey, 'Indisponible'); // Fallback if no span
    }
}
function enableAddToCartButton(button) {
     if(button) {
        button.disabled = false;
        button.classList.remove('opacity-50', 'cursor-not-allowed', 'bg-gray-400', 'hover:bg-gray-400');
        button.classList.add('btn-primary'); 
        const span = button.querySelector('span');
        if(span) span.textContent = t('product.add_to_cart', 'Ajouter au Panier');
        else button.textContent = t('product.add_to_cart', 'Ajouter au Panier');
    }
}

// --- Image Gallery Logic (Product Detail Page) ---
function setupImageGallery(imagesData = [], mainImageUrlDefault, productNameForAlt = "Produit") {
    const mainImage = document.getElementById('main-product-image');
    const thumbnailContainer = document.getElementById('thumbnail-container');
    const imageModal = document.getElementById('image-modal');
    const modalImageContent = document.getElementById('modal-image-content');
    const closeImageModalBtn = document.getElementById('close-image-modal');
    const prevImageBtn = document.getElementById('prev-image-btn');
    const nextImageBtn = document.getElementById('next-image-btn');

    if (!mainImage || !thumbnailContainer || !imageModal || !modalImageContent || !closeImageModalBtn || !prevImageBtn || !nextImageBtn) return;

    let allImages = [];
    const defaultAlt = t('product_detail.image_alt', 'Image de {{productName}}', { productName: productNameForAlt });

    if (mainImageUrlDefault) {
        allImages.push({ image_full_url: mainImageUrlDefault, alt_text: defaultAlt, is_primary: true });
    }
    if (imagesData && imagesData.length > 0) {
        imagesData.forEach(img => {
            // Ensure not to add the main image again if it's also in imagesData with is_primary=true
            const isAlreadyAddedAsMain = mainImageUrlDefault && img.image_full_url === mainImageUrlDefault && img.is_primary;
            if (img.image_full_url && !isAlreadyAddedAsMain) { 
                allImages.push({ 
                    image_full_url: img.image_full_url, 
                    alt_text: img.alt_text || defaultAlt, 
                    is_primary: mainImageUrlDefault ? img.is_primary : false // Only allow one primary
                });
            }
        });
    }
    
    // Consolidate: If main was added and it's also in imagesData as primary, ensure only one entry and it's primary
    if (mainImageUrlDefault) {
        const mainImageEntryIndex = allImages.findIndex(img => img.image_full_url === mainImageUrlDefault);
        if (mainImageEntryIndex !== -1) {
            allImages[mainImageEntryIndex].is_primary = true;
            // Remove other entries for the same URL if any, keeping the primary one
            allImages = allImages.filter((img, index) => img.image_full_url !== mainImageUrlDefault || index === mainImageEntryIndex);
        }
    }
    
    // Ensure at least one image is primary if multiple exist
    if (allImages.length > 0 && !allImages.some(img => img.is_primary)) {
        allImages[0].is_primary = true;
    }


    if (allImages.length === 0) { 
        allImages.push({ image_full_url: 'https://placehold.co/600x600/F5EEDE/11120D?text=Image+Indisponible', alt_text: t('product_detail.image_unavailable_alt', 'Image indisponible'), is_primary: true});
    }


    let currentImageIndex = allImages.findIndex(img => img.is_primary);
    if (currentImageIndex === -1 && allImages.length > 0) currentImageIndex = 0;


    function updateMainImage(index) {
        if (allImages[index]) {
            mainImage.src = allImages[index].image_full_url;
            mainImage.alt = allImages[index].alt_text || defaultAlt;
            currentImageIndex = index;
            updateThumbnailActiveStates();
        }
    }
    
    function updateThumbnailActiveStates() {
        const thumbnails = thumbnailContainer.querySelectorAll('img');
        thumbnails.forEach((thumb, idx) => {
            thumb.classList.toggle('active-thumbnail', idx === currentImageIndex);
            thumb.classList.toggle('opacity-50', idx !== currentImageIndex);
        });
    }

    thumbnailContainer.innerHTML = '';
    if (allImages.length > 1) {
        allImages.forEach((imgData, index) => {
            const thumb = document.createElement('img');
            thumb.src = imgData.image_full_url;
            thumb.alt = t('product_detail.thumbnail_alt', 'Miniature {{index}} pour {{productName}}', { index: index + 1, productName: productNameForAlt });
            thumb.className = 'w-full h-20 object-cover rounded-md cursor-pointer border-2 border-transparent hover:border-mt-classic-gold transition-all';
            thumb.addEventListener('click', () => updateMainImage(index));
            thumbnailContainer.appendChild(thumb);
        });
        prevImageBtn.classList.remove('hidden');
        nextImageBtn.classList.remove('hidden');
    } else {
         prevImageBtn.classList.add('hidden');
        nextImageBtn.classList.add('hidden');
    }

    if (allImages.length > 0 && currentImageIndex >= 0 && currentImageIndex < allImages.length) {
         updateMainImage(currentImageIndex); 
    }


    mainImage.addEventListener('click', () => {
        if (allImages[currentImageIndex]) {
            modalImageContent.src = allImages[currentImageIndex].image_full_url;
            modalImageContent.alt = allImages[currentImageIndex].alt_text || defaultAlt;
            imageModal.classList.remove('hidden');
            imageModal.classList.add('flex'); // Use flex for centering
            setTimeout(() => imageModal.classList.add('opacity-100'), 10); 
        }
    });
    closeImageModalBtn.addEventListener('click', () => {
        imageModal.classList.remove('opacity-100');
        setTimeout(() => imageModal.classList.add('hidden'), 300);
    });
    imageModal.addEventListener('click', (e) => { 
        if (e.target === imageModal) {
            closeImageModalBtn.click();
        }
    });

    prevImageBtn.addEventListener('click', () => {
        currentImageIndex = (currentImageIndex - 1 + allImages.length) % allImages.length;
        updateMainImage(currentImageIndex);
    });
    nextImageBtn.addEventListener('click', () => {
        currentImageIndex = (currentImageIndex + 1) % allImages.length;
        updateMainImage(currentImageIndex);
    });
}

// Accordion Logic 
function initializeAccordions() {
    const accordionToggles = document.querySelectorAll('.accordion-toggle');
    accordionToggles.forEach(button => {
        button.addEventListener('click', () => {
            const content = button.nextElementSibling;
            const icon = button.querySelector('i.fas'); // More specific selector

            button.classList.toggle('active');
            if (icon) { // Check if icon exists
                icon.classList.toggle('fa-chevron-down');
                icon.classList.toggle('fa-chevron-up');
            }
            
            if (content.style.maxHeight && content.style.maxHeight !== "0px") {
                content.style.maxHeight = "0px";
                button.setAttribute('aria-expanded', 'false');
            } else {
                content.style.maxHeight = content.scrollHeight + "px";
                button.setAttribute('aria-expanded', 'true');
            }
        });
    });
}

// --- Initialization based on page ---
document.addEventListener('DOMContentLoaded', () => {
    const bodyId = document.body.id;
    if (bodyId === 'page-nos-produits') {
        // This page typically has its own JS file (e.g. nos-produits.js) for initialization
        // For this example, we'll assume it might call fetchAndDisplayProducts if defined.
        if (typeof fetchAndDisplayProducts === 'function') {
            // console.log("products.js: Assuming nos-produits.js will call fetchAndDisplayProducts if needed.");
        }
    } else if (bodyId === 'page-produit-detail') {
        loadProductDetail();
    }
});

// If using products.js for nos-produits.html directly:
if (document.body.id === 'page-nos-produits') {
    document.addEventListener('DOMContentLoaded', () => {
        // Initial load
        const initialUrlParams = new URLSearchParams(window.location.search);
        const initialCategory = initialUrlParams.get('category');
        const initialSearch = initialUrlParams.get('search');
        fetchAndDisplayProducts(1, initialCategory, initialSearch);

        // Filter setup (example, more robust filtering would be in nos-produits.js)
        const categoryFilterSelect = document.getElementById('category-filter'); // Assuming it exists
        if (categoryFilterSelect) {
            categoryFilterSelect.addEventListener('change', (e) => {
                fetchAndDisplayProducts(1, e.target.value, initialUrlParams.get('search'));
            });
        }
        // Search setup
        // ...
    });
}

