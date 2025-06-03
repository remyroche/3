// website/js/products.js
// Handles fetching and displaying products on listing and detail pages for the public site.

let allProducts = []; 
let currentProductDetail = null; 

async function fetchAndDisplayProducts(category = 'all') {
    const productsGrid = document.getElementById('products-grid'); // Assumes this ID is on nos-produits.html
    const loadingMessageElement = document.getElementById('products-loading-message'); // Assumes this ID is on nos-produits.html
    
    if (!productsGrid || !loadingMessageElement) {
        console.error(t('public.js.product_grid_or_loading_missing')); // New key: public.js.product_grid_or_loading_missing
        return;
    }

    loadingMessageElement.textContent = t('public.products_page.loading'); // Key: public.products_page.loading
    loadingMessageElement.style.display = 'block';
    productsGrid.innerHTML = ''; 

    try {
        const endpoint = category === 'all' ? '/products' : `/products?category_slug=${encodeURIComponent(category)}`; // Assuming API filters by category_slug
        const response = await makeApiRequest(endpoint); 
        
        if (!response || !response.success || !Array.isArray(response.products)) {
            console.error("Invalid product response format:", response); // Dev-facing
            throw new Error(response.message || t('public.js.product_load_error')); // Key: public.js.product_load_error
        }

        const productsToDisplay = response.products;

        if (category === 'all' && productsToDisplay.length > 0) {
            allProducts = productsToDisplay; 
        }

        if (productsToDisplay.length === 0) {
            loadingMessageElement.textContent = t('public.js.no_products_found'); // Key: public.js.no_products_found
            const p = document.createElement('p');
            p.className = "col-span-full text-center text-brand-earth-brown py-8";
            p.textContent = t('public.js.no_products_found');
            productsGrid.appendChild(p);
        } else {
            loadingMessageElement.style.display = 'none';
            productsToDisplay.forEach(product => {
                let stockMessageHTML = ''; // This might remain HTML if it's simple static translated strings
                let addToCartButtonHTML = ''; // This will be a button or link, structure is important
                const productDetailUrl = `produit-detail.html?slug=${product.slug}`; // Use slug for detail URL

                if (product.weight_options && product.weight_options.length > 0) {
                     // For variable products, link to detail page to select options
                    addToCartButtonHTML = `
                        <a href="${productDetailUrl}" class="block w-full text-center bg-brand-warm-taupe hover:bg-brand-warm-taupe/90 text-brand-cream font-semibold py-2 px-4 rounded transition-colors duration-300">
                            ${t('public.products_page.view_options')}
                        </a>`; // New key: public.products_page.view_options (e.g., "View Options" / "Voir les options")
                } else { 
                    if (product.aggregate_stock_quantity > 0) { // Check aggregate_stock_quantity for simple products
                        addToCartButtonHTML = `
                            <button data-product-id="${product.id}" class="add-to-cart-list-btn w-full bg-brand-warm-taupe hover:bg-brand-warm-taupe/90 text-brand-cream font-semibold py-2 px-4 rounded transition-colors duration-300">
                                ${t('public.products_page.add_to_cart')}
                            </button>`; // Key: public.products_page.add_to_cart
                    } else {
                        stockMessageHTML = `<p class="text-xs text-brand-truffle-burgundy mb-1">${t('public.products_page.out_of_stock')}</p>`; // Key: public.products_page.out_of_stock
                        addToCartButtonHTML = `
                            <button class="w-full bg-stone-400 text-white font-semibold py-2 px-4 rounded cursor-not-allowed" disabled>
                                ${t('public.products_page.out_of_stock')}
                            </button>`;
                    }
                }
                
                if (product.aggregate_stock_quantity <= 0 && (!product.weight_options || product.weight_options.length === 0)) { // This check remains
                     addToCartButtonHTML = `
                        <button class="w-full bg-brand-warm-taupe text-brand-cream font-semibold py-2 px-4 rounded cursor-not-allowed opacity-50" disabled>
                            ${t('public.products_page.out_of_stock')}
                        </button>`;
                }

                const productCard = document.createElement('div');
                productCard.className = 'product-card';

                const linkWrapper = document.createElement('a');
                linkWrapper.href = productDetailUrl;

                const img = document.createElement('img');
                img.src = product.main_image_full_url || 'https://placehold.co/400x300/F5EEDE/7D6A4F?text=Image+Indisponible';
                img.alt = product.name; // Use product.name directly, assuming it's sanitized if from user input, or trusted internal data.
                img.className = 'w-full h-64 object-cover';
                img.onerror = () => { img.src = 'https://placehold.co/400x300/F5EEDE/7D6A4F?text=Image+Error'; };
                linkWrapper.appendChild(img);
                productCard.appendChild(linkWrapper);

                const contentDiv = document.createElement('div');
                contentDiv.className = 'product-card-content p-4';

                const nameLink = document.createElement('a');
                nameLink.href = productDetailUrl;
                nameLink.className = 'hover:text-brand-classic-gold transition-colors';
                const h3 = document.createElement('h3');
                h3.className = 'text-xl font-serif font-semibold text-brand-near-black mb-2';
                h3.textContent = product.name; // XSS: Using textContent
                nameLink.appendChild(h3);
                contentDiv.appendChild(nameLink);

                const descriptionP = document.createElement('p');
                descriptionP.className = 'text-brand-earth-brown text-sm mb-3 h-16 overflow-hidden';
                descriptionP.textContent = product.description || ''; // XSS: Using textContent
                contentDiv.appendChild(descriptionP);

                if (stockMessageHTML) {
                    const stockMessageDiv = document.createElement('div');
                    stockMessageDiv.innerHTML = stockMessageHTML; // Assuming this is safe, trusted HTML (translated string)
                    contentDiv.appendChild(stockMessageDiv);
                }
                
                const footerDiv = document.createElement('div');
                footerDiv.className = 'mt-auto pt-2';
                footerDiv.innerHTML = addToCartButtonHTML; // Buttons/links are generally safe as HTML if attributes are controlled.
                contentDiv.appendChild(footerDiv);
                
                productCard.appendChild(contentDiv);
                productsGrid.appendChild(productCard);


                const addToCartBtn = productCard.querySelector('.add-to-cart-list-btn');
                if (addToCartBtn) {
                    addToCartBtn.addEventListener('click', () => {
                        window.addToCart(product, 1, null); 
                    });
                }
            });
        }
    } catch (error) {
        loadingMessageElement.textContent = t('public.js.product_load_error');
        const p = document.createElement('p');
        p.className = "col-span-full text-center text-brand-truffle-burgundy py-8";
        p.textContent = `${t('public.js.product_load_error')} ${error.message || ''}`;
        productsGrid.appendChild(p);
    }
}

function setupCategoryFilters() {
    const filterContainer = document.getElementById('product-categories-filter'); // Assumes ID on nos-produits.html
    if (filterContainer) {
        const buttons = filterContainer.querySelectorAll('button');
        buttons.forEach(button => {
            button.addEventListener('click', () => {
                buttons.forEach(btn => btn.classList.remove('filter-active', 'bg-brand-earth-brown', 'text-brand-cream'));
                button.classList.add('filter-active', 'bg-brand-earth-brown', 'text-brand-cream');
                const categorySlug = button.dataset.categorySlug; // Assuming buttons have data-category-slug
                fetchAndDisplayProducts(categorySlug);
            });
        });
    }
}

async function loadProductDetail() { // For produit-detail.html
    const params = new URLSearchParams(window.location.search);
    const productSlug = params.get('slug'); // Expecting slug
    const loadingDiv = document.getElementById('product-detail-loading');
    const contentDiv = document.getElementById('product-detail-content');

    if (!productSlug) {
        if(loadingDiv) loadingDiv.textContent = t('public.js.no_product_specified'); // Key: public.js.no_product_specified
        if(contentDiv) contentDiv.style.display = 'none';
        return;
    }
    
    if(loadingDiv) loadingDiv.style.display = 'block';
    if(contentDiv) contentDiv.style.display = 'none';

    try {
        const product = await makeApiRequest(`/products/${productSlug}`); // API expects slug or code
        if (!product || !product.success || !product.product) { // Assuming API wraps single product in { success: true, product: {...} }
            throw new Error(product.message || t('public.js.product_not_found')); // New key: public.js.product_not_found
        }
        currentProductDetail = product.product; // Store the actual product object

        document.title = `${currentProductDetail.name} - ${t('public.js.maison_truvra_title_suffix')}`; // New key: public.js.maison_truvra_title_suffix (e.g., "Maison Trüvra")
        document.getElementById('product-name').textContent = currentProductDetail.name; // XSS: Using textContent
        const mainImage = document.getElementById('main-product-image');
        mainImage.src = currentProductDetail.main_image_full_url || 'https://placehold.co/600x500/F5EEDE/7D6A4F?text=Image';
        mainImage.alt = currentProductDetail.name; // Use product name directly for alt
        mainImage.onerror = () => { mainImage.src = 'https://placehold.co/600x500/F5EEDE/7D6A4F?text=Image+Error'; };

        document.getElementById('product-short-description').textContent = currentProductDetail.description || ''; // XSS: Using textContent
        
        const priceDisplay = document.getElementById('product-price-display');
        const priceUnit = document.getElementById('product-price-unit');
        const weightOptionsContainer = document.getElementById('weight-options-container');
        const weightOptionsSelect = document.getElementById('weight-options-select');
        const addToCartButton = document.getElementById('add-to-cart-button');

        if (currentProductDetail.weight_options && currentProductDetail.weight_options.length > 0) {
            weightOptionsContainer.classList.remove('hidden');
            weightOptionsSelect.innerHTML = '';
            currentProductDetail.weight_options.forEach(opt => {
                const optionElement = document.createElement('option');
                optionElement.value = opt.option_id; // Assuming weight_options have an option_id
                let optionText = `${opt.weight_grams}g - ${parseFloat(opt.price).toFixed(2)} €`;
                if(opt.aggregate_stock_quantity <= 0) optionText += ` (${t('public.products_page.out_of_stock')})`;
                optionElement.textContent = optionText; // XSS: Using textContent for option text
                optionElement.dataset.price = opt.price;
                optionElement.dataset.stock = opt.aggregate_stock_quantity;
                optionElement.dataset.weightGrams = opt.weight_grams;
                if(opt.aggregate_stock_quantity <= 0) optionElement.disabled = true;
                weightOptionsSelect.appendChild(optionElement);
            });
            
            let firstEnabledIndex = -1;
            for(let i=0; i<weightOptionsSelect.options.length; i++) {
                if(!weightOptionsSelect.options[i].disabled) { firstEnabledIndex = i; break; }
            }
            if(firstEnabledIndex !== -1) weightOptionsSelect.selectedIndex = firstEnabledIndex;
            else { /* All options out of stock */ }
            
            updatePriceFromSelection(); 
            weightOptionsSelect.addEventListener('change', updatePriceFromSelection);
        } else if (currentProductDetail.base_price !== null) {
            priceDisplay.textContent = `${parseFloat(currentProductDetail.base_price).toFixed(2)} €`; // XSS: Price is numeric, safe
            priceUnit.textContent = ''; 
            weightOptionsContainer.classList.add('hidden');
             if (currentProductDetail.aggregate_stock_quantity <= 0) {
                addToCartButton.textContent = t('public.products_page.out_of_stock'); // XSS: Translated string, assumed safe
                addToCartButton.disabled = true;
                addToCartButton.classList.replace('btn-gold','btn-secondary'); 
                addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
            }
        } else { 
            priceDisplay.textContent = t('public.product_detail.price_on_request'); // XSS: Translated string, assumed safe
            priceUnit.textContent = '';
            weightOptionsContainer.classList.add('hidden');
            addToCartButton.textContent = t('public.product_detail.unavailable'); // XSS: Translated string, assumed safe
            addToCartButton.disabled = true;
            addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
        }

        document.getElementById('product-species').textContent = currentProductDetail.species || t('common.notApplicable'); // XSS: Using textContent
        document.getElementById('product-uses').textContent = currentProductDetail.ideal_uses || t('common.notApplicable'); // XSS: Using textContent
        
        const longDesc = currentProductDetail.long_description || currentProductDetail.sensory_description || t('public.product_detail.no_description');
        // XSS: Using textContent for long description. If HTML is required, sanitization is crucial.
        // For now, assuming plain text for safety or that sanitization happens server-side if HTML is intended.
        document.getElementById('product-sensory-description').textContent = longDesc;
        
        document.getElementById('product-pairing-suggestions').textContent = currentProductDetail.pairing_suggestions || t('public.product_detail.no_pairings'); // XSS: Using textContent
        
        const thumbnailGallery = document.getElementById('product-thumbnail-gallery');
        thumbnailGallery.innerHTML = ''; 
        if (currentProductDetail.additional_images && Array.isArray(currentProductDetail.additional_images) && currentProductDetail.additional_images.length > 0) {
            currentProductDetail.additional_images.forEach(imgData => {
                const thumbUrl = imgData.image_full_url || imgData.image_url;
                if (thumbUrl) {
                    const img = document.createElement('img');
                    img.src = thumbUrl;
                    img.alt = `${currentProductDetail.name} ${t('public.js.thumbnail_alt_suffix')}`; // Alt text
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
        console.error("Error in loadProductDetail:", error); // Dev-facing
        const errorMsg = (error.data?.message || error.message || t('public.js.product_detail_load_error')); // Key: public.js.product_detail_load_error
        if (loadingDiv) {
            // XSS: Using textContent for error messages
            const p = document.createElement('p');
            p.className = "text-brand-truffle-burgundy";
            p.textContent = `${t('public.js.product_detail_load_error_prefix')}: ${errorMsg}`;
            loadingDiv.innerHTML = ''; // Clear previous content
            loadingDiv.appendChild(p);
            loadingDiv.style.display = 'block'; 
        }
        if (contentDiv) {
            contentDiv.style.display = 'none';
        }
    }
}

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
            quantityInput.value = minVal; return;
        }
        if (!isNaN(minVal) && currentValue < minVal) quantityInput.value = minVal;
        else if (!isNaN(maxVal) && currentValue > maxVal) quantityInput.value = maxVal;
    });
}

function updatePriceFromSelection() {
    const weightOptionsSelect = document.getElementById('weight-options-select');
    const priceDisplay = document.getElementById('product-price-display');
    const priceUnit = document.getElementById('product-price-unit');
    const addToCartButton = document.getElementById('add-to-cart-button');

    if (!weightOptionsSelect || !priceDisplay || !priceUnit || !addToCartButton || !currentProductDetail) return;
    
    const selectedOptionEl = weightOptionsSelect.options[weightOptionsSelect.selectedIndex];

    if (selectedOptionEl && selectedOptionEl.value) { 
        priceDisplay.textContent = `${parseFloat(selectedOptionEl.dataset.price).toFixed(2)} €`; // XSS: Price, safe
        priceUnit.textContent = `/ ${selectedOptionEl.dataset.weightGrams}g`; // XSS: Weight, safe
        if (parseInt(selectedOptionEl.dataset.stock) <= 0 || selectedOptionEl.disabled) {
            addToCartButton.textContent = t('public.products_page.out_of_stock'); // XSS: Translated string, assumed safe
            addToCartButton.disabled = true;
            addToCartButton.classList.replace('btn-gold','btn-secondary');
            addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
            addToCartButton.textContent = t('public.products_page.add_to_cart'); // XSS: Translated string, assumed safe
            addToCartButton.disabled = false;
            addToCartButton.classList.replace('btn-secondary','btn-gold');
            addToCartButton.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    } else if (currentProductDetail && currentProductDetail.base_price === null && (!currentProductDetail.weight_options || currentProductDetail.weight_options.length === 0)) {
        priceDisplay.textContent = t('public.product_detail.price_on_request'); // XSS: Translated string, assumed safe
        addToCartButton.textContent = t('public.product_detail.unavailable'); // XSS: Translated string, assumed safe
        addToCartButton.disabled = true;
        addToCartButton.classList.replace('btn-gold','btn-secondary');
        addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
    } else if (currentProductDetail && currentProductDetail.base_price !== null) { // Simple product
        priceDisplay.textContent = `${parseFloat(currentProductDetail.base_price).toFixed(2)} €`; // XSS: Price, safe
        priceUnit.textContent = '';
        if (currentProductDetail.aggregate_stock_quantity <= 0) {
            addToCartButton.textContent = t('public.products_page.out_of_stock'); // XSS: Translated string, assumed safe
            addToCartButton.disabled = true;
            addToCartButton.classList.replace('btn-gold','btn-secondary');
            addToCartButton.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
             addToCartButton.textContent = t('public.products_page.add_to_cart'); // XSS: Translated string, assumed safe
            addToCartButton.disabled = false;
            addToCartButton.classList.replace('btn-secondary','btn-gold');
            addToCartButton.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    }
}

function updateDetailQuantity(change) { // Used by inline +/- buttons if any, not directly present in provided HTML
    const quantityInput = document.getElementById('quantity-select');
    if (!quantityInput) return;
    // ... (rest of the logic is fine)
}

function handleAddToCartFromDetail() {
    if (!currentProductDetail) {
        showGlobalMessage(t('public.js.add_to_cart_error_missing_details'), "error"); // Key: public.js.add_to_cart_error_missing_details
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
                    id: selectedVariantData.option_id, // This should be the variant's unique ID from product_weight_options table
                    weight_grams: selectedVariantData.weight_grams,
                    price: parseFloat(selectedVariantData.price),
                    sku_suffix: selectedVariantData.sku_suffix // Important for cart item identification
                };
            } else {
                showGlobalMessage(t('public.js.invalid_variant_selected'), "error"); // Key: public.js.invalid_variant_selected
                return;
            }
        }  else {
             showGlobalMessage(t('public.js.select_valid_option'), "error"); // New key: public.js.select_valid_option (e.g. "Please select a valid option.")
            return;
        }
    }
    // For simple products, variantInfoForCart remains null.
    addToCart(currentProductDetail, quantity, variantInfoForCart); 
}
window.handleAddToCartFromDetail = handleAddToCartFromDetail; // Expose if called from HTML inline event

// Event listeners for nos-produits.html page (if product list)
if (document.body.id === 'page-nos-produits') {
    document.addEventListener('DOMContentLoaded', () => {
        fetchAndDisplayProducts('all'); // Default load
        setupCategoryFilters();
    });
}

// Event listener for produit-detail.html page
if (document.body.id === 'page-produit-detail') {
    document.addEventListener('DOMContentLoaded', () => {
        loadProductDetail();
        const addToCartBtn = document.getElementById('add-to-cart-button');
        if (addToCartBtn) {
            addToCartBtn.addEventListener('click', handleAddToCartFromDetail);
        }
    });
}
