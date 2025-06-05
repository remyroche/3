// website/source/admin/js/admin_products.js
// Handles the "Manage Products" page in the admin panel.

document.addEventListener('DOMContentLoaded', function() {
    // --- DOM Element References ---
    const productForm = document.getElementById('productForm');
    const productsTableBody = document.getElementById('productsTableBody');
    const productCategorySelect = document.getElementById('productCategory');
    const productTypeSelect = document.getElementById('productType');
    const basePriceSection = document.getElementById('basePriceSection');
    // Stock quantity related elements are REMOVED from this page's direct management.
    // const baseQuantitySection = document.getElementById('baseQuantitySection');

    const formTitle = document.getElementById('formTitle');
    const productCodeInput = document.getElementById('productCode');
    const productIdInput = document.getElementById('productId'); // Hidden input for editing

    const saveProductButton = document.getElementById('saveProductButton');
    const cancelEditButton = document.getElementById('cancelEditButton');
    const productSearchInput = document.getElementById('productSearchInput');
    const mainAddProductBtn = document.getElementById('add-new-product-btn-main');
    const productFormContainer = document.getElementById('productFormContainer');

    // Modal for product options (variants)
    const productOptionsModal = document.getElementById('product-options-modal');
    const productOptionsForm = document.getElementById('product-options-form');
    const optionsProductIdInput = document.getElementById('options-product-id');
    const modalProductNamePlaceholder = document.getElementById('modal-product-name-placeholder');
    const productOptionsContainer = document.getElementById('product-options-container');
    const addProductOptionButton = document.getElementById('add-product-option-button');
    const closeProductOptionsModalButton = document.getElementById('close-product-options-modal');
    const cancelProductOptionsButton = document.getElementById('cancel-product-options-button');
    const productOptionTemplate = document.getElementById('product-option-template');

    // Image preview elements
    const mainImagePreview = document.getElementById('main-image-preview');
    const mainImagePreviewContainer = document.getElementById('main-image-preview-container');
    const removeMainImageBtn = document.getElementById('remove-main-image-btn');
    const additionalImagesPreviewContainer = document.getElementById('additional-images-preview-container');


    // --- State Variables ---
    let editingProductId = null; 
    let allProductsCache = []; 
    let allCategoriesCache = [];
    let currentEditingProductForOptions = null;

    // --- Initialization ---
    loadInitialData();

    async function loadInitialData() {
        await loadCategoriesForSelect(); 
        await loadProductsTable();       
    }

    async function loadCategoriesForSelect() {
        try {
            const apiResponse = await adminApi.getCategories(); 
            allCategoriesCache = apiResponse.categories || []; 
            productCategorySelect.innerHTML = '<option value="">-- Sélectionnez une catégorie --</option>'; 
            allCategoriesCache.forEach(category => {
                if (category.is_active) { 
                    const option = document.createElement('option');
                    option.value = category.id; 
                    option.textContent = `${category.name} (${category.category_code || 'N/A'})`;
                    productCategorySelect.appendChild(option);
                }
            });
        } catch (error) {
            console.error('Failed to load categories for select:', error);
            showAdminToast('Erreur chargement catégories. Actualisez.', 'error');
        }
    }

    function renderProductsTable(productsToRender) {
        productsTableBody.innerHTML = ''; 
        if (!productsToRender || productsToRender.length === 0) {
            productsTableBody.innerHTML = '<tr><td colspan="9" class="text-center py-4">Aucun produit trouvé.</td></tr>';
            return;
        }
        productsToRender.forEach(product => {
            const row = productsTableBody.insertRow();
            row.insertCell().textContent = product.product_code;
            row.insertCell().textContent = product.name_fr || product.name; // Prefer FR name
            row.insertCell().textContent = product.category_name ? `${product.category_name} (${product.category_code || 'N/A'})` : 'Non catégorisé';
            row.insertCell().textContent = product.base_price !== null ? `€${parseFloat(product.base_price).toFixed(2)}` : (product.type === 'variable_weight' ? 'Variable' : 'N/A');
            row.insertCell().textContent = product.type ? (product.type.value || product.type) : 'simple'; // Handle if type is already a value
            
            const activeCell = row.insertCell();
            activeCell.innerHTML = `<span class="status-indicator ${product.is_active ? 'active' : 'inactive'}">${product.is_active ? 'Oui' : 'Non'}</span>`;

            const featuredCell = row.insertCell();
            featuredCell.innerHTML = `<span class="status-indicator ${product.is_featured ? 'featured' : ''}">${product.is_featured ? 'Oui' : 'Non'}</span>`;
            
            const variantsCell = row.insertCell();
            if (product.type === 'variable_weight' || (product.type && product.type.value === 'variable_weight')) {
                const variantsButton = document.createElement('button');
                variantsButton.textContent = `Options (${product.variant_count || 0})`;
                variantsButton.classList.add('btn', 'btn-admin-secondary', 'btn-sm');
                variantsButton.onclick = () => openProductOptionsModal(product.id);
                variantsCell.appendChild(variantsButton);

                if (product.weight_options && product.weight_options.length > 0) {
                    const skuList = document.createElement('ul');
                    skuList.className = 'text-xs list-disc list-inside ml-2';
                    product.weight_options.slice(0, 2).forEach(opt => { // Show first 2
                        const li = document.createElement('li');
                        li.textContent = opt.sku_suffix || 'N/A';
                        skuList.appendChild(li);
                    });
                    if (product.weight_options.length > 2) {
                        const liMore = document.createElement('li');
                        liMore.textContent = `...et ${product.weight_options.length - 2} autre(s)`;
                        skuList.appendChild(liMore);
                    }
                    variantsCell.appendChild(skuList);
                }


            } else {
                variantsCell.textContent = 'N/A';
            }
            
            const actionsCell = row.insertCell();
            actionsCell.classList.add('text-right', 'actions');
            
            const editButton = document.createElement('button');
            editButton.innerHTML = '<i class="fas fa-edit"></i> Éditer';
            editButton.classList.add('btn', 'btn-admin-secondary', 'btn-sm'); 
            editButton.onclick = () => populateFormForEdit(product);
            actionsCell.appendChild(editButton);

            const deleteButton = document.createElement('button');
            deleteButton.innerHTML = '<i class="fas fa-trash-alt"></i> Suppr.';
            deleteButton.classList.add('btn', 'btn-admin-danger', 'btn-sm'); 
            deleteButton.onclick = () => confirmDeleteProduct(product.id, product.name, product.product_code);
            actionsCell.appendChild(deleteButton);
        });
    }
    
    async function loadProductsTable() {
        try {
            productsTableBody.innerHTML = '<tr><td colspan="9" class="text-center py-4">Chargement des produits...</td></tr>';
            const response = await adminApi.getProducts(true); // Pass true to include variants for table display
            allProductsCache = response.products || []; 
            renderProductsTable(allProductsCache); 
        } catch (error) {
            console.error('Failed to load products:', error);
            showAdminToast('Erreur chargement produits. Actualisez.', 'error');
            productsTableBody.innerHTML = '<tr><td colspan="9" class="text-center py-4">Erreur de chargement des produits.</td></tr>';
        }
    }
    
    if (productSearchInput) {
        productSearchInput.addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase().trim();
            if (!allProductsCache) return;

            const filteredProducts = allProductsCache.filter(product => 
                Object.values(product).some(val => 
                    String(val).toLowerCase().includes(searchTerm)
                ) || (product.category_name && product.category_name.toLowerCase().includes(searchTerm))
            );
            renderProductsTable(filteredProducts);
        });
    }
    
    // Toggle form fields based on product type
    if (productTypeSelect) {
        productTypeSelect.addEventListener('change', function() {
            if (this.value === 'simple') {
                if (basePriceSection) basePriceSection.style.display = 'block';
                // if (baseQuantitySection) baseQuantitySection.style.display = 'block'; // Stock removed
            } else { // variable_weight
                if (basePriceSection) basePriceSection.style.display = 'none';
                // if (baseQuantitySection) baseQuantitySection.style.display = 'none'; // Stock removed
                 document.getElementById('productPrice').value = ''; // Clear base price if switching to variable
                // document.getElementById('productQuantity').value = ''; // Clear base quantity
            }
        });
    }


    function populateFormForEdit(product) {
        formTitle.textContent = `Modifier Produit: ${product.name_fr || product.name} (${product.product_code})`;
        saveProductButton.textContent = 'Mettre à Jour Produit';
        if(cancelEditButton) cancelEditButton.style.display = 'inline-block'; 
        
        editingProductId = product.id; 
        productIdInput.value = product.id; // Set hidden ID field
        
        productCodeInput.value = product.product_code;
        // productCodeInput.readOnly = true; // Product code might need to be editable if no orders exist

        document.getElementById('productName').value = product.name_fr || product.name || '';
        document.getElementById('productNameEn').value = product.name_en || '';
        document.getElementById('productDescription').value = product.description_fr || product.description || '';
        document.getElementById('productDescriptionEn').value = product.description_en || '';
        document.getElementById('productLongDescription').value = product.long_description_fr || product.long_description || '';
        document.getElementById('productLongDescriptionEn').value = product.long_description_en || '';
        
        productCategorySelect.value = product.category_id || '';
        productTypeSelect.value = product.type ? (product.type.value || product.type) : 'simple';
        
        // Manually trigger change event for product type to show/hide price field
        const event = new Event('change');
        productTypeSelect.dispatchEvent(event);
        
        document.getElementById('productPrice').value = product.base_price !== null ? parseFloat(product.base_price).toFixed(2) : '';
        // Stock quantity fields removed from here

        // Populate new informational fields
        document.getElementById('productSensoryEvaluation').value = product.sensory_evaluation_fr || product.sensory_evaluation || '';
        document.getElementById('productSensoryEvaluationEn').value = product.sensory_evaluation_en || '';
        document.getElementById('productFoodPairings').value = product.food_pairings_fr || product.food_pairings || '';
        document.getElementById('productFoodPairingsEn').value = product.food_pairings_en || '';
        document.getElementById('productSpecies').value = product.species_fr || product.species || '';
        document.getElementById('productSpeciesEn').value = product.species_en || '';
        document.getElementById('productPreservationType').value = product.preservation_type || '';
        document.getElementById('productNotesInternal').value = product.notes_internal || '';
        
        document.getElementById('productImageUrlTextMain').value = product.main_image_url || ''; // Assuming backend returns just path
        mainImagePreview.src = product.main_image_full_url || '#';
        mainImagePreview.style.display = product.main_image_full_url ? 'block' : 'none';
        removeMainImageBtn.style.display = product.main_image_full_url ? 'inline-block' : 'none';
        
        // Handle additional images preview (simplified, assumes `product.additional_images` is an array of objects like {image_full_url, alt_text})
        additionalImagesPreviewContainer.innerHTML = '';
        if (product.additional_images && Array.isArray(product.additional_images)) {
             document.getElementById('productAdditionalImagesText').value = JSON.stringify(
                product.additional_images.map(img => ({ image_url: img.image_url, alt_text: img.alt_text }))
            );
            product.additional_images.forEach(imgData => {
                if(imgData.image_full_url) {
                    const img = document.createElement('img');
                    img.src = imgData.image_full_url;
                    img.alt = imgData.alt_text || 'Aperçu';
                    img.style.maxHeight = '70px'; img.style.maxWidth = '70px';
                    img.classList.add('rounded-md', 'border', 'object-cover');
                    additionalImagesPreviewContainer.appendChild(img);
                }
            });
        } else {
            document.getElementById('productAdditionalImagesText').value = '';
        }


        document.getElementById('supplierInfo').value = product.supplier_info || '';
        document.getElementById('productIsActive').checked = product.is_active;
        document.getElementById('productIsFeatured').checked = product.is_featured;

        if (productFormContainer) {
            productFormContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    function resetForm() {
        formTitle.textContent = 'Ajouter un Nouveau Produit';
        saveProductButton.textContent = 'Enregistrer Produit';
        productForm.reset(); 
        productCodeInput.readOnly = false;
        editingProductId = null; 
        productIdInput.value = '';
        if(cancelEditButton) cancelEditButton.style.display = 'none'; 

        document.getElementById('productIsActive').checked = true;
        document.getElementById('productIsFeatured').checked = false;
        productCategorySelect.value = ""; 
        productTypeSelect.value = "simple";
        productTypeSelect.dispatchEvent(new Event('change')); // Trigger change to show/hide relevant fields

        mainImagePreview.src = '#';
        mainImagePreview.style.display = 'none';
        removeMainImageBtn.style.display = 'none';
        additionalImagesPreviewContainer.innerHTML = '';
        document.getElementById('productImageFileMain').value = '';
        document.getElementById('productAdditionalImageFiles').value = '';


        if (productFormContainer) productFormContainer.style.display = 'none'; // Hide form after reset
    }
    
    if (mainAddProductBtn && productFormContainer) {
        mainAddProductBtn.addEventListener('click', () => {
            resetForm(); // Reset before showing
            productFormContainer.style.display = 'block';
            formTitle.textContent = 'Ajouter un Nouveau Produit';
            productCodeInput.focus();
            window.scrollTo({ top: productFormContainer.offsetTop - 80, behavior: 'smooth' });
        });
    }
    if (cancelEditButton) cancelEditButton.addEventListener('click', resetForm);

    productForm.addEventListener('submit', async function(event) {
        event.preventDefault(); 
        const formData = new FormData(productForm);
        
        // Basic client-side validation
        if (!formData.get('product_code').trim()) { showAdminToast('Le code produit est requis.', 'error'); return; }
        if (!formData.get('name').trim()) { showAdminToast('Le nom du produit (FR) est requis.', 'error'); return; }
        if (!formData.get('category_id')) { showAdminToast('La catégorie est requise.', 'error'); return; }
        
        if (formData.get('type') === 'simple' && (formData.get('price').trim() === '' || isNaN(parseFloat(formData.get('price'))) || parseFloat(formData.get('price')) < 0)) {
            showAdminToast('Un prix de base valide est requis pour les produits simples.', 'error'); return;
        }
        // Stock quantity is no longer managed here

        saveProductButton.disabled = true;
        saveProductButton.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> ${editingProductId ? 'Mise à jour...' : 'Enregistrement...'}`;

        try {
            let response;
            if (editingProductId) {
                response = await adminApi.updateProduct(editingProductId, formData); 
            } else {
                response = await adminApi.addProduct(formData); 
            }
            
            if (response.success) {
                showAdminToast(response.message || `Produit ${editingProductId ? 'mis à jour' : 'ajouté'} avec succès !`, 'success');
                resetForm(); 
                await loadProductsTable(); 
            } // Error toast handled by adminApi
        } catch (error) {
            console.error('Failed to save product:', error);
            // Error toast handled by adminApi or directly if needed
            showAdminToast(error.data?.message || error.message || 'Échec de l\'enregistrement du produit.', 'error');
        } finally {
            saveProductButton.disabled = false;
            saveProductButton.innerHTML = `<i class="fas fa-save mr-2"></i> ${editingProductId ? 'Mettre à Jour Produit' : 'Enregistrer Produit'}`;
        }
    });

    // --- Image Preview Logic ---
    if (productImageFileMain && mainImagePreview) {
        productImageFileMain.addEventListener('change', function(event) {
            const file = event.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    mainImagePreview.src = e.target.result;
                    mainImagePreview.style.display = 'block';
                    if(removeMainImageBtn) removeMainImageBtn.style.display = 'inline-block';
                }
                reader.readAsDataURL(file);
            }
        });
    }
    if(removeMainImageBtn && productImageFileMain && mainImagePreview){
        removeMainImageBtn.addEventListener('click', function() {
            productImageFileMain.value = ''; // Clear the file input
            mainImagePreview.src = '#';
            mainImagePreview.style.display = 'none';
            this.style.display = 'none';
            // For edit mode, also set a flag to tell backend to remove existing image
            productForm.elements['remove_main_image_flag'] = 'true'; // Needs backend handling
        });
    }
     const additionalImageFilesInput = document.getElementById('productAdditionalImageFiles');
    if (additionalImageFilesInput && additionalImagesPreviewContainer) {
        additionalImageFilesInput.addEventListener('change', function(event) {
            additionalImagesPreviewContainer.innerHTML = ''; // Clear previous file previews
            const files = event.target.files;
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                if (file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const img = document.createElement('img');
                        img.src = e.target.result;
                        img.alt = `Aperçu ${i+1}`;
                        img.style.maxHeight = '70px'; img.style.maxWidth = '70px';
                        img.classList.add('rounded-md', 'border', 'object-cover', 'mr-2', 'mb-2');
                        additionalImagesPreviewContainer.appendChild(img);
                    }
                    reader.readAsDataURL(file);
                }
            }
        });
    }


    // --- Product Options (Variants) Modal Logic ---
    async function openProductOptionsModal(productId) {
        currentEditingProductForOptions = allProductsCache.find(p => p.id === productId);
        if (!currentEditingProductForOptions) {
            showAdminToast('Produit non trouvé pour gérer les options.', 'error');
            return;
        }
        
        if (currentEditingProductForOptions.type !== 'variable_weight' && currentEditingProductForOptions.type.value !== 'variable_weight') {
            showAdminToast('Les options de poids ne sont applicables qu\'aux produits de type "Poids Variable".', 'warning');
            return;
        }

        optionsProductIdInput.value = productId;
        modalProductNamePlaceholder.textContent = currentEditingProductForOptions.name_fr || currentEditingProductForOptions.name;
        productOptionsContainer.innerHTML = ''; // Clear previous options

        // Fetch full product details if variants aren't in allProductsCache or need fresh data
        try {
            const productDetailResponse = await adminApi.getProductDetail(productId);
            const detailedProduct = productDetailResponse.product;

            if (detailedProduct.weight_options && detailedProduct.weight_options.length > 0) {
                detailedProduct.weight_options.forEach(opt => addOptionRowToModal(opt));
            } else {
                addOptionRowToModal(); // Add one empty row if no options exist
            }
        } catch (error) {
            showAdminToast('Erreur chargement détails options du produit.', 'error');
            addOptionRowToModal(); // Add one empty row on error
        }
        
        openAdminModal('product-options-modal');
    }

    function addOptionRowToModal(optionData = {}) {
        const newRowContent = productOptionTemplate.content.cloneNode(true);
        const newRow = newRowContent.querySelector('.weight-option-row');
        
        if (optionData.option_id) newRow.querySelector('input[name="option_id[]"]').value = optionData.option_id;
        if (optionData.weight_grams) newRow.querySelector('input[name="weight_grams[]"]').value = optionData.weight_grams;
        if (optionData.price) newRow.querySelector('input[name="price[]"]').value = parseFloat(optionData.price).toFixed(2);
        if (optionData.sku_suffix) newRow.querySelector('input[name="sku_suffix[]"]').value = optionData.sku_suffix;
        // Stock quantity is NOT managed here anymore.
        // if (optionData.aggregate_stock_quantity !== undefined) newRow.querySelector('input[name="option_stock[]"]').value = optionData.aggregate_stock_quantity;

        newRow.querySelector('.remove-option-btn').addEventListener('click', function() {
            this.closest('.weight-option-row').remove();
        });
        productOptionsContainer.appendChild(newRow);
    }

    if (addProductOptionButton) {
        addProductOptionButton.addEventListener('click', () => addOptionRowToModal());
    }
    if (closeProductOptionsModalButton) {
        closeProductOptionsModalButton.addEventListener('click', () => closeAdminModal('product-options-modal'));
    }
    if (cancelProductOptionsButton) {
        cancelProductOptionsButton.addEventListener('click', () => closeAdminModal('product-options-modal'));
    }

    if (productOptionsForm) {
        productOptionsForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            const productId = optionsProductIdInput.value;
            const optionsData = [];
            const optionRows = productOptionsContainer.querySelectorAll('.weight-option-row');
            let formIsValid = true;

            optionRows.forEach(row => {
                const option_id = row.querySelector('input[name="option_id[]"]').value || null; // null if new
                const weight_grams = row.querySelector('input[name="weight_grams[]"]').value;
                const price = row.querySelector('input[name="price[]"]').value;
                const sku_suffix = row.querySelector('input[name="sku_suffix[]"]').value.trim().toUpperCase();
                // Stock is not managed here.

                if (!weight_grams || !price || !sku_suffix) {
                    formIsValid = false; return; // Basic validation
                }
                optionsData.push({ option_id, product_id: parseInt(productId), weight_grams: parseFloat(weight_grams), price: parseFloat(price), sku_suffix });
            });

            if (!formIsValid) {
                showAdminToast('Veuillez remplir tous les champs obligatoires pour chaque option de poids.', 'error');
                return;
            }
            if (optionsData.length === 0) {
                 showAdminToast('Veuillez ajouter au moins une option de poids.', 'warning');
                return;
            }

            const saveOptionsButton = document.getElementById('save-product-options-button');
            saveOptionsButton.disabled = true;
            saveOptionsButton.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Sauvegarde...';

            try {
                // This API endpoint will need to handle creating new options and updating/deleting existing ones.
                // It should NOT update stock quantities here.
                const response = await adminApi.updateProductOptions(productId, optionsData);
                if (response.success) {
                    showAdminToast('Options de poids enregistrées avec succès!', 'success');
                    closeAdminModal('product-options-modal');
                    loadProductsTable(); // Refresh table to show updated variant count/SKUs
                }
            } catch (error) {
                console.error('Failed to save product options:', error);
            } finally {
                saveOptionsButton.disabled = false;
                saveOptionsButton.innerHTML = 'Enregistrer les Options';
            }
        });
    }


    // --- Delete Product ---
    function confirmDeleteProduct(productId, productName, productCode) {
        const messageParagraph = document.createElement('p');
        messageParagraph.innerHTML = `Êtes-vous sûr de vouloir supprimer le produit: <strong>${productName} (${productCode})</strong> ? Cette action est irréversible.`;
        showAdminConfirm(
            'Confirmer Suppression Produit', 
            messageParagraph, // Pass the element
            async () => {
                try {
                    const response = await adminApi.deleteProduct(productId);
                     if (response.success) {
                        showAdminToast(response.message || `Produit "${productName}" supprimé avec succès !`, 'success');
                        await loadProductsTable(); 
                    }
                } catch (error) { console.error('Failed to delete product:', error); }
            }, 'Supprimer Produit', 'Annuler'          
        );
    }
});
