// website/admin/js/admin_products.js
// Logic for managing products in the Admin Panel.

let productsForAdmin = []; // Cache for products list in admin panel
let editingProductId = null; // Tracks if a product is being edited

/**
 * Initializes product management functionalities:
 * - Sets up event listeners for form buttons.
 * - Loads the initial list of products.
 */
function initializeProductManagement() {
    const showFormButton = document.getElementById('show-add-product-form-button');
    const productFormSection = document.getElementById('add-edit-product-section');
    const productForm = document.getElementById('product-form');
    const cancelFormButton = document.getElementById('cancel-product-form-button');
    const addWeightOptionButton = document.getElementById('add-weight-option-button');
    const assetsPreviewSection = document.getElementById('product-assets-preview-section'); // Get the new section

    if (showFormButton && productFormSection) {
        showFormButton.addEventListener('click', () => {
            editingProductId = null;
            if (productForm) productForm.reset();
            clearFormErrors(productForm); // Assumes clearFormErrors from admin_ui.js
            const formTitle = document.getElementById('product-form-title');
            if (formTitle) formTitle.textContent = "Ajouter un Nouveau Produit";
            const productIdField = document.getElementById('product-id');
            if (productIdField) productIdField.readOnly = false;
            
            const weightOptionsContainer = document.getElementById('weight-options-container');
            if (weightOptionsContainer) weightOptionsContainer.innerHTML = ''; // Clear old options
            
            if(assetsPreviewSection) assetsPreviewSection.style.display = 'none'; // Hide assets preview

            productFormSection.style.display = 'block';
            showFormButton.style.display = 'none';
        });
    }

    if (cancelFormButton && productFormSection && showFormButton) {
        cancelFormButton.addEventListener('click', () => {
            productFormSection.style.display = 'none';
            showFormButton.style.display = 'inline-flex'; // Or 'block'
            if (productForm) productForm.reset();
            clearFormErrors(productForm);
            editingProductId = null;
            if(assetsPreviewSection) assetsPreviewSection.style.display = 'none'; // Hide assets preview
        });
    }

    if (productForm) {
        productForm.addEventListener('submit', handleProductFormSubmit);
    }

    if (addWeightOptionButton) {
        addWeightOptionButton.addEventListener('click', () => addWeightOptionRow()); // Pass no args for new row
    }

    loadAdminProductsList();
}

/**
 * Adds a new row for a weight/price option to the product form.
 * @param {object} [option] - Optional existing option data for editing.
 * Expected: { option_id: number, weight_grams: string, price: string, initial_stock: string }
 */
function addWeightOptionRow(option = { option_id: null, weight_grams: '', price: '', initial_stock: '' }) {
    const container = document.getElementById('weight-options-container');
    if (!container) return;

    const optionIndex = container.children.length;
    const optionIdInputHtml = option.option_id ? `<input type="hidden" name="weight_options[${optionIndex}][option_id]" value="${option.option_id}">` : '';

    const rowHtml = `
        <div class="weight-option-row grid grid-cols-1 md:grid-cols-4 gap-3 items-center border p-3 rounded-md mb-2">
            ${optionIdInputHtml}
            <div>
                <label class="text-xs font-medium text-brand-near-black">Poids (g) <span class="text-red-500">*</span></label>
                <input type="number" name="weight_options[${optionIndex}][weight_grams]" class="form-input-admin text-sm p-2 mt-1" value="${option.weight_grams}" placeholder="Ex: 20" required>
            </div>
            <div>
                <label class="text-xs font-medium text-brand-near-black">Prix (€) <span class="text-red-500">*</span></label>
                <input type="number" name="weight_options[${optionIndex}][price]" step="0.01" class="form-input-admin text-sm p-2 mt-1" value="${option.price}" placeholder="Ex: 75.00" required>
            </div>
            <div>
                <label class="text-xs font-medium text-brand-near-black">Stock Initial/Actuel <span class="text-red-500">*</span></label>
                <input type="number" name="weight_options[${optionIndex}][initial_stock]" step="1" min="0" class="form-input-admin text-sm p-2 mt-1" value="${option.initial_stock}" placeholder="Ex: 10" required>
            </div>
            <button type="button" class="btn-admin-danger text-xs py-1 px-2 self-end mt-4 md:mt-0" onclick="this.parentElement.remove()">Retirer</button>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', rowHtml);
}


/**
 * Handles the submission of the add/edit product form.
 * @param {Event} event - The form submission event.
 */
async function handleProductFormSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const assetsPreviewSection = document.getElementById('product-assets-preview-section');
    const assetsLinksContainer = document.getElementById('product-assets-links');

    if(assetsPreviewSection) assetsPreviewSection.style.display = 'none'; // Hide preview initially
    if(assetsLinksContainer) assetsLinksContainer.innerHTML = ''; // Clear previous links

    clearFormErrors(form);
    if (!validateProductForm(form)) return;

    const formData = new FormData(form);
    const productData = {};
    
    for (let [key, value] of formData.entries()) {
        if (!key.startsWith('weight_options')) {
            if (key === 'base_price' || key === 'initial_stock_quantity') {
                productData[key] = value ? parseFloat(value) : null;
                if (key === 'initial_stock_quantity' && productData[key] === null) productData[key] = 0;
            } else if (key === 'is_published') {
                productData[key] = formData.get('is_published') === 'on';
            } else {
                productData[key] = value;
            }
        }
    }
    productData.is_published = form.querySelector('#product-is-published').checked;

    const weightOptions = [];
    document.querySelectorAll('#weight-options-container .weight-option-row').forEach((row) => {
        const optionIdField = row.querySelector(`input[name*="[option_id]"]`);
        const weightGramsField = row.querySelector(`input[name*="[weight_grams]"]`);
        const priceField = row.querySelector(`input[name*="[price]"]`);
        const initialStockField = row.querySelector(`input[name*="[initial_stock]"]`);

        if (weightGramsField && priceField && initialStockField) {
            const opt = {
                weight_grams: parseInt(weightGramsField.value),
                price: parseFloat(priceField.value),
                initial_stock: parseInt(initialStockField.value)
            };
            if(optionIdField && optionIdField.value) opt.option_id = parseInt(optionIdField.value);
            weightOptions.push(opt);
        }
    });

    if (weightOptions.length > 0) {
        productData.weight_options = weightOptions;
        productData.base_price = null; 
        productData.initial_stock_quantity = 0; 
    } else {
        if (productData.base_price === null) {
            // Validation should catch this if no variants and no base_price
        }
        if(productData.initial_stock_quantity === null) productData.initial_stock_quantity = 0;
    }

    try {
        const thumbString = formData.get('image_urls_thumb');
        productData.image_urls_thumb = thumbString.trim() ? JSON.parse(thumbString) : [];
        if (!Array.isArray(productData.image_urls_thumb)) productData.image_urls_thumb = [];
    } catch (e) {
        productData.image_urls_thumb = [];
        setFieldError(form.querySelector('#product-image-urls-thumb'), "Format JSON invalide pour les miniatures.");
        return;
    }

    const method = editingProductId ? 'PUT' : 'POST';
    const endpoint = editingProductId ? `/products/${editingProductId}` : '/products';

    try {
        showAdminToast("Enregistrement du produit...", "info");
        const result = await adminApiRequest(endpoint, method, productData);
        
        if (result.success && result.product) {
            showAdminToast(result.message || "Produit enregistré avec succès!", "success");
            
            // Display generated asset links if available
            if (result.product.assets && assetsPreviewSection && assetsLinksContainer) {
                let linksHtml = '';
                if (result.product.assets.passport_url) {
                    linksHtml += `<p><strong>Passeport:</strong> <a href="${result.product.assets.passport_url}" target="_blank" class="text-brand-classic-gold hover:underline">${result.product.assets.passport_url}</a></p>`;
                }
                if (result.product.assets.qr_code_file_path) {
                    // Ensure this prefix matches your Flask static URL configuration
                    const qrUrl = `/static_assets/${result.product.assets.qr_code_file_path}`; 
                    linksHtml += `<p><strong>QR Code:</strong> <a href="${qrUrl}" target="_blank" class="text-brand-classic-gold hover:underline">Voir QR Code</a> <img src="${qrUrl}" alt="QR Code Preview" class="h-20 w-20 inline-block ml-2 border"></p>`;
                }
                if (result.product.assets.label_file_path) {
                    const labelUrl = `/static_assets/${result.product.assets.label_file_path}`;
                    linksHtml += `<p><strong>Étiquette:</strong> <a href="${labelUrl}" target="_blank" class="text-brand-classic-gold hover:underline">Voir Étiquette</a></p>`;
                }

                if (linksHtml) {
                    assetsLinksContainer.innerHTML = linksHtml;
                    assetsPreviewSection.style.display = 'block';
                } else {
                    assetsLinksContainer.innerHTML = '<p class="text-brand-warm-taupe">Aucun actif spécifique généré ou retourné par l\'API.</p>';
                    assetsPreviewSection.style.display = 'block';
                }
            }
            
            editingProductId = result.product.id; 
            document.getElementById('product-form-title').textContent = `Modifier le Produit: ${result.product.name}`;
            // Make product ID field readonly after successful creation or if it was an edit
            document.getElementById('product-id').readOnly = true;


            loadAdminProductsList(); 
        }
    } catch (error) {
        console.error("Erreur soumission formulaire produit:", error);
    }
}

/**
 * Validates the product form before submission.
 * @param {HTMLFormElement} form - The product form element.
 * @returns {boolean} True if the form is valid, false otherwise.
 */
function validateProductForm(form) {
    let isValid = true;
    const requiredFields = [
        { id: 'product-name', message: "Le nom du produit est requis." },
        { id: 'product-category', message: "La catégorie est requise." },
        { id: 'product-short-description', message: "Une description courte est requise." },
        { id: 'product-image-url-main', message: "L'URL de l'image principale est requise." }
    ];
    
    if (!editingProductId) {
        requiredFields.unshift({ id: 'product-id', message: "L'ID du produit est requis." });
    }

    requiredFields.forEach(fieldInfo => {
        const field = form.querySelector(`#${fieldInfo.id}`);
        if (field && !field.value.trim()) {
            setFieldError(field, fieldInfo.message);
            isValid = false;
        }
    });

    const basePriceField = form.querySelector('#product-base-price');
    const weightOptionsRows = form.querySelectorAll('#weight-options-container .weight-option-row');
    if (!basePriceField.value.trim() && weightOptionsRows.length === 0) {
        setFieldError(basePriceField, "Un prix de base ou au moins une option de poids est requis.");
        isValid = false;
    }
    if (basePriceField.value.trim() && weightOptionsRows.length > 0) {
        setFieldError(basePriceField, "Ne pas spécifier de prix de base si des options de poids sont définies.");
        isValid = false;
    }
    if (basePriceField.value.trim() && parseFloat(basePriceField.value) < 0) {
        setFieldError(basePriceField, "Le prix de base ne peut pas être négatif.");
        isValid = false;
    }
    
    weightOptionsRows.forEach(row => {
        const weightField = row.querySelector('input[name*="[weight_grams]"]');
        const priceField = row.querySelector('input[name*="[price]"]');
        const stockField = row.querySelector('input[name*="[initial_stock]"]');

        if (!weightField.value.trim() || parseInt(weightField.value) <= 0) {
            setFieldError(weightField, "Poids invalide."); isValid = false;
        }
        if (!priceField.value.trim() || parseFloat(priceField.value) < 0) {
            setFieldError(priceField, "Prix invalide."); isValid = false;
        }
        if (!stockField.value.trim() || parseInt(stockField.value) < 0) {
            setFieldError(stockField, "Stock invalide."); isValid = false;
        }
    });

    const mainImageUrlField = form.querySelector('#product-image-url-main');
    if (mainImageUrlField.value.trim() && !isValidUrl(mainImageUrlField.value)) {
        setFieldError(mainImageUrlField, "URL de l'image principale invalide.");
        isValid = false;
    }
    
    const thumbInput = form.querySelector('#product-image-urls-thumb');
    if (thumbInput.value.trim()) {
        try {
            const thumbs = JSON.parse(thumbInput.value.trim());
            if (!Array.isArray(thumbs) || !thumbs.every(url => typeof url === 'string' && isValidUrl(url))) {
                 setFieldError(thumbInput, "Doit être un tableau JSON d'URLs valides. Ex: [\"url1\", \"url2\"]");
                 isValid = false;
            }
        } catch (e) {
            setFieldError(thumbInput, "Format JSON invalide pour les miniatures. Ex: [\"url1\", \"url2\"]");
            isValid = false;
        }
    }

    if (!isValid) showAdminToast("Veuillez corriger les erreurs dans le formulaire.", "error");
    return isValid;
}

/**
 * Loads the list of products from the API and displays them in the admin table.
 */
async function loadAdminProductsList() {
    const tableBody = document.getElementById('products-table-body');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4">Chargement des produits...</td></tr>';

    try {
        productsForAdmin = await adminApiRequest('/products'); 
        if (productsForAdmin.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4">Aucun produit trouvé.</td></tr>';
            return;
        }
        
        let rowsHtml = '';
        productsForAdmin.forEach(product => {
            let priceDisplay = product.base_price !== null ? `${parseFloat(product.base_price).toFixed(2)} €` : 'Variantes';
            let stockDisplay = product.stock_quantity;
            // Backend's /api/admin/products GET route now calculates total_variant_stock and sets stock_quantity correctly for variant products.
            // So, no special frontend calculation needed here if backend is up-to-date.

            rowsHtml += `
                <tr>
                    <td class="px-6 py-3 text-xs">${product.id}</td>
                    <td class="px-6 py-3 font-medium text-brand-near-black">${product.name}</td>
                    <td class="px-6 py-3">${product.category}</td>
                    <td class="px-6 py-3">${priceDisplay}</td>
                    <td class="px-6 py-3">${stockDisplay !== undefined ? stockDisplay : 'N/A'}</td>
                    <td class="px-6 py-3">${product.is_published ? '<span class="text-green-600 font-semibold">Oui</span>' : '<span class="text-red-600">Non</span>'}</td>
                    <td class="px-6 py-3 space-x-2 whitespace-nowrap">
                        <button onclick="editProduct('${product.id}')" class="btn-admin-secondary text-xs p-1.5">Éditer</button>
                    </td>
                </tr>
            `;
        });
        tableBody.innerHTML = rowsHtml;
    } catch (error) {
        tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-red-600">Erreur de chargement des produits.</td></tr>';
    }
}

/**
 * Populates the product form with data for editing an existing product.
 * @param {string} productId - The ID of the product to edit.
 */
async function editProduct(productId) {
    editingProductId = productId;
    let productToEdit;
    const assetsPreviewSection = document.getElementById('product-assets-preview-section');
    const assetsLinksContainer = document.getElementById('product-assets-links');
    if(assetsPreviewSection) assetsPreviewSection.style.display = 'none';
    if(assetsLinksContainer) assetsLinksContainer.innerHTML = '';


    try {
        productToEdit = await adminApiRequest(`/products/${productId}`); 
        if (!productToEdit) throw new Error("Produit non trouvé pour l'édition.");
    } catch (e) {
        showAdminToast("Impossible de charger les détails du produit pour l'édition.", "error");
        return;
    }

    const form = document.getElementById('product-form');
    if (!form) return;
    form.reset(); 
    clearFormErrors(form); 
    
    document.getElementById('product-form-title').textContent = `Modifier le Produit: ${productToEdit.name}`;
    document.getElementById('product-id').value = productToEdit.id;
    document.getElementById('product-id').readOnly = true; 
    
    document.getElementById('product-name').value = productToEdit.name;
    document.getElementById('product-category').value = productToEdit.category;
    document.getElementById('product-short-description').value = productToEdit.short_description || '';
    document.getElementById('product-long-description').value = productToEdit.long_description || '';
    document.getElementById('product-image-url-main').value = productToEdit.image_url_main || '';
    
    // Corrected handling for image_urls_thumb
    let thumbUrlsStringInput = '[]'; // Default for the input field
    if (productToEdit.image_urls_thumb) {
        // API response for product details should provide image_urls_thumb as an array
        if (Array.isArray(productToEdit.image_urls_thumb)) {
            thumbUrlsStringInput = JSON.stringify(productToEdit.image_urls_thumb);
        } else if (typeof productToEdit.image_urls_thumb === 'string') {
            // If it's a string (e.g. from older data or direct DB read not parsed by API)
            // For safety, try to parse and re-stringify to ensure it's a valid array format for the input
            try {
                const parsed = JSON.parse(productToEdit.image_urls_thumb);
                if (Array.isArray(parsed)) {
                    thumbUrlsStringInput = JSON.stringify(parsed);
                }
            } catch(e) {
                console.warn("Impossible de parser image_urls_thumb (string) pendant l'édition:", productToEdit.image_urls_thumb);
                // Keep default '[]' if parsing fails
            }
        }
    }
    document.getElementById('product-image-urls-thumb').value = thumbUrlsStringInput;
    
    document.getElementById('product-species').value = productToEdit.species || '';
    document.getElementById('product-origin').value = productToEdit.origin || '';
    document.getElementById('product-seasonality').value = productToEdit.seasonality || '';
    document.getElementById('product-ideal-uses').value = productToEdit.ideal_uses || '';
    document.getElementById('product-sensory-description').value = productToEdit.sensory_description || '';
    document.getElementById('product-pairing-suggestions').value = productToEdit.pairing_suggestions || '';
    document.getElementById('product-is-published').checked = productToEdit.is_published;

    const weightOptionsContainer = document.getElementById('weight-options-container');
    weightOptionsContainer.innerHTML = ''; 

    if (productToEdit.weight_options && productToEdit.weight_options.length > 0) {
        productToEdit.weight_options.forEach(opt => addWeightOptionRow({
            option_id: opt.option_id,
            weight_grams: opt.weight_grams,
            price: opt.price,
            initial_stock: opt.stock_quantity 
        }));
        document.getElementById('product-base-price').value = '';
        document.getElementById('product-initial-stock-quantity').value = '';
        document.getElementById('simple-product-stock-section').style.display = 'none';
    } else {
        document.getElementById('product-base-price').value = productToEdit.base_price !== null ? productToEdit.base_price : '';
        document.getElementById('product-initial-stock-quantity').value = productToEdit.stock_quantity || 0;
        document.getElementById('simple-product-stock-section').style.display = 'block';
    }

    // Display existing asset links if available from the product data (fetched from DB)
    // The backend /api/admin/products/:id should now return an 'assets' object if paths are stored.
    if (productToEdit.assets && assetsPreviewSection && assetsLinksContainer) {
        let linksHtml = '';
        if (productToEdit.assets.passport_url) {
            linksHtml += `<p><strong>Passeport:</strong> <a href="${productToEdit.assets.passport_url}" target="_blank" class="text-brand-classic-gold hover:underline">${productToEdit.assets.passport_url}</a></p>`;
        }
        if (productToEdit.assets.qr_code_file_path) {
            const qrUrl = `/static_assets/${productToEdit.assets.qr_code_file_path}`;
            linksHtml += `<p><strong>QR Code:</strong> <a href="${qrUrl}" target="_blank" class="text-brand-classic-gold hover:underline">Voir QR Code</a> <img src="${qrUrl}" alt="QR Code Preview" class="h-20 w-20 inline-block ml-2 border"></p>`;
        }
        if (productToEdit.assets.label_file_path) {
            const labelUrl = `/static_assets/${productToEdit.assets.label_file_path}`;
            linksHtml += `<p><strong>Étiquette:</strong> <a href="${labelUrl}" target="_blank" class="text-brand-classic-gold hover:underline">Voir Étiquette</a></p>`;
        }
        if (linksHtml) {
            assetsLinksContainer.innerHTML = linksHtml;
            assetsPreviewSection.style.display = 'block';
        }
    }


    document.getElementById('add-edit-product-section').style.display = 'block';
    document.getElementById('show-add-product-form-button').style.display = 'none';
    window.scrollTo(0, 0);
}
