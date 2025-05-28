// website/admin/js/admin_inventory.js
// Logic for managing product inventory in the Admin Panel.

let productsForInventorySelect = []; // Cache for product select dropdowns

/**
 * Initializes inventory management functionalities:
 * - Populates product select dropdowns.
 * - Sets up event listeners for forms and product selection.
 * - Loads the initial inventory overview.
 */
async function initializeInventoryManagement() {
    await populateProductSelectsForInventory(); 

    const addStockForm = document.getElementById('add-stock-form');
    if (addStockForm) addStockForm.addEventListener('submit', handleAddStockSubmit);

    const manualAdjustForm = document.getElementById('manual-adjust-stock-form');
    if (manualAdjustForm) manualAdjustForm.addEventListener('submit', handleManualAdjustSubmit);
    
    const productSelects = [
        document.getElementById('stock-product-select'),
        document.getElementById('adjust-product-select'),
        document.getElementById('inventory-filter-product') // For filtering the overview table
    ];

    productSelects.forEach(select => {
        if (select) {
            select.addEventListener('change', (event) => {
                if (event.target.id !== 'inventory-filter-product') {
                    handleProductSelectionForVariant(event.target);
                } else {
                    loadInventoryOverview(event.target.value); // Filter overview on change
                }
            });
        }
    });
    
    loadInventoryOverview(); // Initial load of the overview table
}

/**
 * Populates product select dropdowns used in inventory forms.
 * Fetches products from the admin API.
 */
async function populateProductSelectsForInventory() {
    try {
        // adminApiRequest is from admin_api.js
        // Assuming backend can provide products with an indicator if they have variants
        const products = await adminApiRequest('/products?include_variants=true'); 
        productsForInventorySelect = products; 

        const selectsToPopulate = [
            document.getElementById('stock-product-select'),
            document.getElementById('adjust-product-select'),
            document.getElementById('inventory-filter-product')
        ];

        selectsToPopulate.forEach(selectElement => {
            if (selectElement) {
                selectElement.innerHTML = '<option value="">Sélectionner un produit</option>'; 
                products.forEach(p => {
                    const option = document.createElement('option');
                    option.value = p.id;
                    // Indicate if product has variants for clarity in selection
                    let displayText = `${p.name} (ID: ${p.id})`;
                    if (p.variant_count > 0 || p.base_price === null) { // Check if product is variant-based
                        displayText += ' - Variantes multiples';
                    }
                    option.textContent = displayText;
                    selectElement.appendChild(option);
                });
            }
        });
    } catch (error) {
        showAdminToast("Erreur de chargement de la liste des produits pour les stocks.", "error"); // Assumes showAdminToast from admin_ui.js
    }
}

/**
 * Handles changes in product selection to populate/hide variant selection dropdown.
 * @param {HTMLSelectElement} productSelectElement - The product select dropdown that changed.
 */
async function handleProductSelectionForVariant(productSelectElement) {
    const selectedProductId = productSelectElement.value;
    let variantSelectContainerId, variantSelectId;

    // Determine which variant dropdown to update based on the product select ID
    if (productSelectElement.id === 'stock-product-select') {
        variantSelectContainerId = 'stock-variant-select-container';
        variantSelectId = 'stock-variant-select';
    } else if (productSelectElement.id === 'adjust-product-select') {
        variantSelectContainerId = 'adjust-variant-select-container';
        variantSelectId = 'adjust-variant-select';
    } else {
        return; // Not a product select that controls a variant dropdown
    }

    const variantContainer = document.getElementById(variantSelectContainerId);
    const variantSelect = document.getElementById(variantSelectId);

    if (!variantContainer || !variantSelect) return;

    if (!selectedProductId) { // No product selected
        variantContainer.style.display = 'none';
        variantSelect.innerHTML = '<option value="">Sélectionner une variante</option>';
        variantSelect.required = false;
        return;
    }

    try {
        // Fetch full product details to get its weight_options
        // adminApiRequest is from admin_api.js
        const productDetails = await adminApiRequest(`/products/${selectedProductId}`); 
        
        if (productDetails.weight_options && productDetails.weight_options.length > 0) {
            variantSelect.innerHTML = '<option value="">Sélectionner une variante (obligatoire)</option>';
            productDetails.weight_options.forEach(opt => {
                const optionEl = document.createElement('option');
                optionEl.value = opt.option_id;
                optionEl.textContent = `${opt.weight_grams}g (Stock: ${opt.stock_quantity}, Prix: ${parseFloat(opt.price).toFixed(2)}€)`;
                variantSelect.appendChild(optionEl);
            });
            variantContainer.style.display = 'block';
            variantSelect.required = true; // Variant selection is mandatory if options exist
        } else { // Product has no variants
            variantContainer.style.display = 'none';
            variantSelect.innerHTML = '<option value="">Ce produit n\'a pas de variantes</option>';
            variantSelect.required = false;
        }
    } catch (error) {
        showAdminToast(`Erreur chargement variantes pour ${selectedProductId}.`, "error");
        variantContainer.style.display = 'none';
        variantSelect.required = false;
    }
}

/**
 * Handles the submission of the "Add Stock" form.
 * @param {Event} event - The form submission event.
 */
async function handleAddStockSubmit(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form); // Assumes clearFormErrors from admin_ui.js
    if (!validateInventoryForm(form, 'add')) return; // Assumes validateInventoryForm is defined below

    const product_id = form.product_id.value;
    const variant_option_id_field = form.elements['variant_option_id']; // More robust way to get field
    const variant_option_id = variant_option_id_field ? variant_option_id_field.value : null;
    const quantity_add = parseInt(form.quantity_add.value);
    const movement_type_add = form.movement_type_add.value;
    const notes_add = form.notes_add.value;
    
    const payload = {
        product_id: product_id,
        variant_option_id: variant_option_id || null, 
        quantity_change: quantity_add, // Positive for addition
        movement_type: movement_type_add,
        notes: notes_add
    };

    try {
        showAdminToast("Ajout du stock en cours...", "info");
        // adminApiRequest is from admin_api.js
        const result = await adminApiRequest('/inventory/adjust', 'POST', payload);
        if (result.success) {
            showAdminToast(result.message || "Stock ajouté avec succès.", "success");
            form.reset();
            // Reset variant dropdown
            const stockVariantContainer = document.getElementById('stock-variant-select-container');
            const stockVariantSelect = document.getElementById('stock-variant-select');
            if(stockVariantContainer) stockVariantContainer.style.display = 'none';
            if(stockVariantSelect) {
                stockVariantSelect.innerHTML = '<option value="">Sélectionner une variante</option>';
                stockVariantSelect.required = false;
            }
            loadInventoryOverview(); // Refresh inventory table
        }
    } catch (error) {
        // Error toast shown by adminApiRequest
        console.error("Erreur ajout stock:", error);
    }
}

/**
 * Handles the submission of the "Manual Adjust Stock" form.
 * @param {Event} event - The form submission event.
 */
async function handleManualAdjustSubmit(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form);
    if (!validateInventoryForm(form, 'adjust')) return;
    
    const product_id = form.product_id_adjust.value;
    const variant_option_id_field = form.elements['variant_option_id_adjust'];
    const variant_option_id = variant_option_id_field ? variant_option_id_field.value : null;
    const quantity_change = parseInt(form.quantity_change.value); // Can be positive or negative
    const movement_type_adjust = form.movement_type_adjust.value;
    const notes_adjust = form.notes_adjust.value;
    
    const payload = {
        product_id: product_id,
        variant_option_id: variant_option_id || null,
        quantity_change: quantity_change,
        movement_type: movement_type_adjust,
        notes: notes_adjust
    };
    
    try {
        showAdminToast("Ajustement du stock en cours...", "info");
        const result = await adminApiRequest('/inventory/adjust', 'POST', payload);
        if (result.success) {
            showAdminToast(result.message || "Stock ajusté avec succès.", "success");
            form.reset();
            // Reset variant dropdown
            const adjustVariantContainer = document.getElementById('adjust-variant-select-container');
            const adjustVariantSelect = document.getElementById('adjust-variant-select');
            if(adjustVariantContainer) adjustVariantContainer.style.display = 'none';
            if(adjustVariantSelect) {
                adjustVariantSelect.innerHTML = '<option value="">Sélectionner une variante</option>';
                adjustVariantSelect.required = false;
            }
            loadInventoryOverview(); // Refresh inventory table
        }
    } catch (error) {
        console.error("Erreur ajustement manuel stock:", error);
    }
}

/**
 * Validates inventory adjustment forms.
 * @param {HTMLFormElement} form - The form element to validate.
 * @param {string} type - 'add' for add stock form, 'adjust' for manual adjust form.
 * @returns {boolean} True if valid, false otherwise.
 */
function validateInventoryForm(form, type) {
    let isValid = true;
    const productIdField = form.querySelector(type === 'add' ? '#stock-product-select' : '#adjust-product-select');
    const quantityField = form.querySelector(type === 'add' ? '#stock-quantity-add' : '#stock-quantity-change');
    const notesField = form.querySelector(type === 'add' ? '#stock-add-notes' : '#adjust-notes');
    const variantSelect = form.querySelector(type === 'add' ? '#stock-variant-select' : '#adjust-variant-select');

    if (!productIdField.value) {
        setFieldError(productIdField, "Veuillez sélectionner un produit."); // Assumes setFieldError from admin_ui.js
        isValid = false;
    }
    
    // If variant select is visible (meaning product has variants) and no variant is selected
    if (variantSelect && variantSelect.parentElement.style.display !== 'none' && !variantSelect.value) {
        setFieldError(variantSelect, "Veuillez sélectionner une variante.");
        isValid = false;
    }

    if (!quantityField.value || isNaN(parseInt(quantityField.value))) {
        setFieldError(quantityField, "Veuillez entrer une quantité numérique valide.");
        isValid = false;
    } else {
        const quantity = parseInt(quantityField.value);
        if (type === 'add' && quantity <= 0) {
            setFieldError(quantityField, "La quantité à ajouter doit être positive.");
            isValid = false;
        }
        if (type === 'adjust' && quantity === 0) {
            // Allow 0 if it's a 'correction' with notes, but generally disallow for other adjustments.
            // For simplicity, let's say 0 is not allowed for adjustments that imply quantity change.
            const movementTypeField = form.querySelector(type === 'add' ? '#stock-add-movement-type' : '#adjust-movement-type');
            if (movementTypeField && movementTypeField.value !== 'correction') { // Example: allow 0 only for 'correction'
                 setFieldError(quantityField, "Le changement de quantité ne peut pas être zéro pour ce type de mouvement.");
                 isValid = false;
            }
        }
    }

    // Notes are generally good to have, but make them strictly required for certain types.
    if (type === 'adjust' && !notesField.value.trim()) {
        setFieldError(notesField, "Une raison/note est requise pour l'ajustement manuel.");
        isValid = false;
    }
    // Example: if movement_type is 'perte' or 'correction', notes are mandatory
    const movementTypeField = form.querySelector(type === 'add' ? '#stock-add-movement-type' : '#adjust-movement-type');
    if (movementTypeField && (movementTypeField.value === 'perte' || movementTypeField.value === 'correction') && !notesField.value.trim()) {
        setFieldError(notesField, "Des notes sont requises pour ce type de mouvement.");
        isValid = false;
    }

    if (!isValid) showAdminToast("Veuillez corriger les erreurs.", "error");
    return isValid;
}

/**
 * Loads and displays the inventory overview table.
 * Can be filtered by product ID.
 * @param {string} [filterProductId=''] - Optional product ID to filter the overview.
 */
async function loadInventoryOverview(filterProductId = '') {
    const tableBody = document.getElementById('inventory-table-body');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Chargement de l\'inventaire...</td></tr>';

    try {
        // Use the cached productsForInventorySelect or fetch if needed.
        // For simplicity, we'll assume productsForInventorySelect is populated.
        let productsToDisplay = productsForInventorySelect;
        if (filterProductId) {
            productsToDisplay = productsForInventorySelect.filter(p => p.id === filterProductId);
        }

        if (productsToDisplay.length === 0 && !filterProductId && productsForInventorySelect.length > 0) {
             tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Aucun produit correspondant au filtre.</td></tr>';
             return;
        }
        if (productsToDisplay.length === 0 && productsForInventorySelect.length === 0) {
             tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Aucun produit à afficher. Ajoutez des produits d\'abord.</td></tr>';
             return;
        }


        let rowsHtml = '';
        for (const productSummary of productsToDisplay) {
            try {
                // Fetch detailed inventory for each product to get up-to-date stock and variant info
                // adminApiRequest is from admin_api.js
                // Backend endpoint /api/admin/inventory/product/:id needs to be implemented
                const inventoryDetails = await adminApiRequest(`/inventory/product/${productSummary.id}`); 
                
                if (inventoryDetails.current_stock_by_variant && inventoryDetails.current_stock_by_variant.length > 0) {
                    inventoryDetails.current_stock_by_variant.forEach(variant => {
                        rowsHtml += `
                            <tr>
                                <td class="px-6 py-3">${productSummary.name}</td>
                                <td class="px-6 py-3">${variant.weight_grams}g</td>
                                <td class="px-6 py-3 font-semibold">${variant.stock_quantity}</td>
                                <td class="px-6 py-3 text-xs">${inventoryDetails.additions_log && inventoryDetails.additions_log.length > 0 && inventoryDetails.additions_log[0].movement_date ? new Date(inventoryDetails.additions_log[0].movement_date).toLocaleDateString('fr-FR') : 'N/A'}</td>
                                <td class="px-6 py-3"><button class="btn-admin-secondary text-xs p-1" onclick="viewProductInventoryMovementsModal('${productSummary.id}', ${variant.option_id})">Historique</button></td>
                            </tr>
                        `;
                    });
                } else { // Simple product or variant data not structured as expected
                     rowsHtml += `
                        <tr>
                            <td class="px-6 py-3">${productSummary.name}</td>
                            <td class="px-6 py-3">-</td>
                            <td class="px-6 py-3 font-semibold">${inventoryDetails.current_stock !== undefined ? inventoryDetails.current_stock : (productSummary.stock_quantity || 0)}</td>
                            <td class="px-6 py-3 text-xs">${inventoryDetails.additions_log && inventoryDetails.additions_log.length > 0 && inventoryDetails.additions_log[0].movement_date ? new Date(inventoryDetails.additions_log[0].movement_date).toLocaleDateString('fr-FR') : 'N/A'}</td>
                            <td class="px-6 py-3"><button class="btn-admin-secondary text-xs p-1" onclick="viewProductInventoryMovementsModal('${productSummary.id}')">Historique</button></td>
                        </tr>
                    `;
                }
            } catch (invError) {
                 rowsHtml += `
                    <tr class="bg-red-50">
                        <td class="px-6 py-3">${productSummary.name}</td>
                        <td class="px-6 py-3 text-red-700" colspan="3">Erreur chargement stock détaillé</td>
                        <td class="px-6 py-3">-</td>
                    </tr>
                `;
                console.error(`Erreur chargement stock pour ${productSummary.id}:`, invError);
            }
        }
        tableBody.innerHTML = rowsHtml || '<tr><td colspan="5" class="text-center py-4">Aucune donnée de stock à afficher pour la sélection.</td></tr>';

    } catch (error) {
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-red-600">Erreur de chargement de l\'inventaire général.</td></tr>';
    }
}

/**
 * Opens a modal to display inventory movement history for a product/variant.
 * @param {string} productId - The ID of the product.
 * @param {number|null} [variantOptionId=null] - Optional ID of the product variant.
 */
async function viewProductInventoryMovementsModal(productId, variantOptionId = null) {
    try {
        showAdminToast("Chargement de l'historique des mouvements...", "info");
        // Backend endpoint: /api/admin/inventory/product/:id/history or similar
        // For now, using the same endpoint as loadInventoryOverview and extracting logs
        const details = await adminApiRequest(`/inventory/product/${productId}${variantOptionId ? `?variant_id=${variantOptionId}`: ''}`);
        
        let historyHtml = '<ul class="text-xs space-y-1 max-h-60 overflow-y-auto">';
        let hasMovements = false;

        // Filter logs for the specific variant if variantOptionId is provided
        const filterLogByVariant = (log) => !variantOptionId || log.variant_option_id === variantOptionId;

        if (details.additions_log) {
            details.additions_log.filter(filterLogByVariant).forEach(log => {
                 historyHtml += `<li class="text-green-700 p-1 bg-green-50 rounded"><strong>+${log.quantity_change}</strong> (${log.movement_type}) le ${new Date(log.movement_date).toLocaleString('fr-FR')} - ${log.notes || 'N/A'}</li>`;
                 hasMovements = true;
            });
        }
        if(details.subtractions_log){
            details.subtractions_log.filter(filterLogByVariant).forEach(log => {
                 historyHtml += `<li class="text-red-700 p-1 bg-red-50 rounded"><strong>${log.quantity_change}</strong> (${log.movement_type}) le ${new Date(log.movement_date).toLocaleString('fr-FR')} - ${log.notes || 'N/A'} ${log.order_id ? `(Cmd: ${log.order_id})` : ''}</li>`;
                 hasMovements = true;
            });
        }
        historyHtml += '</ul>';
        
        const modalTitle = document.getElementById('generic-modal-title'); // Assuming a generic modal exists in admin HTML
        const modalBody = document.getElementById('generic-modal-body');
        if (modalTitle && modalBody) {
            modalTitle.textContent = `Historique: ${productId} ${variantOptionId ? `(Variante ${variantOptionId})` : ''}`;
            modalBody.innerHTML = hasMovements ? historyHtml : '<p class="italic">Aucun mouvement enregistré pour cette sélection.</p>';
            openAdminModal('generic-modal'); // Assumes openAdminModal from admin_ui.js
        } else {
            showAdminToast(`Historique pour ${productId} chargé (détails en console). Modal non trouvée.`, "info");
            console.log("Détails de l'historique:", details);
        }
    } catch (e) {
        showAdminToast("Impossible de charger l'historique des mouvements.", "error");
    }
}
