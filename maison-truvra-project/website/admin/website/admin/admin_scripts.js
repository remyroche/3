// Updated content for remyroche/maison-truvra-project/remyroche-maison-truvra-project-2a648141e4e38704789c3d54982835db943283aa/website/admin/website/admin/admin_scripts.js
// admin_scripts.js
const API_ADMIN_BASE_URL = 'http://127.0.0.1:5001/api/admin'; // Specific admin base
const API_BASE_URL = 'http://127.0.0.1:5001/api'; // For general API calls like products for select

// --- Utility Functions ---
function getAdminAuthToken() {
    return sessionStorage.getItem('adminAuthToken');
}

function getAdminUser() {
    const userString = sessionStorage.getItem('adminUser');
    return userString ? JSON.parse(userString) : null;
}

async function adminApiRequest(endpoint, method = 'GET', body = null) {
    const token = getAdminAuthToken();
    if (!token) {
        showAdminToast("Session expirée ou invalide. Veuillez vous reconnecter.", "error");
        window.location.href = 'admin_login.html';
        throw new Error("Token administrateur manquant.");
    }

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    };

    const config = {
        method: method,
        headers: headers,
    };

    if (body) {
        config.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_ADMIN_BASE_URL}${endpoint}`, config);
        const responseData = await response.json().catch(() => ({})); // Handle empty responses

        if (!response.ok) {
            const errorMessage = responseData.message || `Erreur HTTP: ${response.status}`;
            showAdminToast(errorMessage, "error");
            if (response.status === 401 || response.status === 403) { // Unauthorized or Forbidden
                sessionStorage.removeItem('adminAuthToken');
                sessionStorage.removeItem('adminUser');
                window.location.href = 'admin_login.html';
            }
            throw new Error(errorMessage);
        }
        return responseData;
    } catch (error) {
        console.error(`Erreur API Admin pour ${method} ${endpoint}:`, error);
        if (!error.message.startsWith("Erreur HTTP") && !error.message.includes("Token administrateur manquant")) {
            showAdminToast(error.message || "Une erreur réseau est survenue.", "error");
        }
        throw error;
    }
}

function showAdminToast(message, type = 'info', duration = 4000) {
    const toastContainer = document.getElementById('admin-toast-container');
    const toast = document.getElementById('admin-message-toast');
    const textElement = document.getElementById('admin-message-text');

    if (!toastContainer || !toast || !textElement) {
        console.warn("Admin toast elements not found. Fallback to alert.");
        alert(message);
        return;
    }
    textElement.textContent = message;
    toast.className = ''; // Reset classes
    toast.classList.add(type); 
    toast.style.display = 'block';

    if (toast.currentTimeout) clearTimeout(toast.currentTimeout);

    toast.currentTimeout = setTimeout(() => {
        toast.style.display = 'none';
    }, duration);
}

function checkAdminLogin() {
    const token = getAdminAuthToken();
    const adminUser = getAdminUser();
    if (!token || !adminUser || !adminUser.is_admin) {
        window.location.href = 'admin_login.html';
        return false;
    }
    const greetingElement = document.getElementById('admin-user-greeting');
    if (greetingElement) {
        greetingElement.textContent = `Bonjour, ${adminUser.prenom || adminUser.email}!`;
    }
    return true;
}

function adminLogout() {
    sessionStorage.removeItem('adminAuthToken');
    sessionStorage.removeItem('adminUser');
    showAdminToast("Vous avez été déconnecté.", "info");
    window.location.href = 'admin_login.html';
}

// --- Common Admin Page Setup ---
document.addEventListener('DOMContentLoaded', () => {
    if (window.location.pathname.includes('admin_login.html')) {
        return;
    }

    if (!checkAdminLogin()) {
        return; 
    }

    const logoutButton = document.getElementById('admin-logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', adminLogout);
    }
    
    const currentPage = window.location.pathname.split("/").pop();
    document.querySelectorAll('.admin-nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === currentPage) {
            link.classList.add('active');
        }
    });

    if (document.body.id === 'page-admin-dashboard' || window.location.pathname.endsWith('admin_dashboard.html')) {
        loadDashboardStats();
    } else if (window.location.pathname.endsWith('admin_manage_products.html')) {
        initializeProductManagement();
    } else if (window.location.pathname.endsWith('admin_manage_inventory.html')) {
        initializeInventoryManagement();
    } else if (window.location.pathname.endsWith('admin_manage_users.html')) {
        initializeUserManagement();
    } else if (window.location.pathname.endsWith('admin_manage_orders.html')) {
        initializeOrderManagement(); 
    }
});

// --- Dashboard Specific ---
async function loadDashboardStats() {
    try {
        const products = await adminApiRequest('/products');
        document.getElementById('stats-total-products').textContent = products.length || 0;
        // Mock other stats until backend endpoints are ready
        // const orders = await adminApiRequest('/orders?limit=5&status=Paid'); // Example
        // document.getElementById('stats-recent-orders').textContent = orders.length || 0; // Placeholder
        // const users = await adminApiRequest('/users?period=week'); // Example
        // document.getElementById('stats-new-users').textContent = users.length || 0; // Placeholder
        document.getElementById('stats-recent-orders').textContent = 'N/A'; 
        document.getElementById('stats-new-users').textContent = 'N/A';

    } catch (error) {
        console.error("Erreur chargement stats dashboard:", error);
        showAdminToast("Impossible de charger les statistiques du tableau de bord.", "error");
    }
}

// --- Product Management (admin_manage_products.html) ---
let productsForAdmin = [];
let editingProductId = null;

function initializeProductManagement() {
    const showFormButton = document.getElementById('show-add-product-form-button');
    const productFormSection = document.getElementById('add-edit-product-section');
    const productForm = document.getElementById('product-form');
    const cancelFormButton = document.getElementById('cancel-product-form-button');
    const addWeightOptionButton = document.getElementById('add-weight-option-button');

    if (showFormButton) {
        showFormButton.addEventListener('click', () => {
            editingProductId = null; 
            productForm.reset();
            clearFormErrors(productForm);
            document.getElementById('product-form-title').textContent = "Ajouter un Nouveau Produit";
            document.getElementById('product-id').readOnly = false;
            document.getElementById('weight-options-container').innerHTML = ''; 
            productFormSection.style.display = 'block';
            showFormButton.style.display = 'none';
        });
    }
    if (cancelFormButton) {
        cancelFormButton.addEventListener('click', () => {
            productFormSection.style.display = 'none';
            showFormButton.style.display = 'inline-flex';
            productForm.reset();
            clearFormErrors(productForm);
            editingProductId = null;
        });
    }
    if (productForm) {
        productForm.addEventListener('submit', handleProductFormSubmit);
    }
    if (addWeightOptionButton) {
        addWeightOptionButton.addEventListener('click', addWeightOptionRow);
    }

    loadAdminProductsList();
}

function addWeightOptionRow(option = { option_id: null, weight_grams: '', price: '', initial_stock: '' }) { // Added option_id for editing
    const container = document.getElementById('weight-options-container');
    const optionIndex = container.children.length;
    // Store option_id in a hidden input if it exists (for editing)
    const optionIdInput = option.option_id ? `<input type="hidden" name="weight_options[${optionIndex}][option_id]" value="${option.option_id}">` : '';

    const rowHtml = `
        <div class="weight-option-row grid grid-cols-1 md:grid-cols-4 gap-3 items-center border p-3 rounded-md">
            ${optionIdInput}
            <div>
                <label class="text-xs">Poids (g) <span class="text-red-500">*</span></label>
                <input type="number" name="weight_options[${optionIndex}][weight_grams]" class="form-input-admin text-sm p-2" value="${option.weight_grams}" placeholder="Ex: 20" required>
            </div>
            <div>
                <label class="text-xs">Prix (€) <span class="text-red-500">*</span></label>
                <input type="number" name="weight_options[${optionIndex}][price]" step="0.01" class="form-input-admin text-sm p-2" value="${option.price}" placeholder="Ex: 75.00" required>
            </div>
            <div>
                <label class="text-xs">Stock Initial <span class="text-red-500">*</span></label>
                <input type="number" name="weight_options[${optionIndex}][initial_stock]" step="1" min="0" class="form-input-admin text-sm p-2" value="${option.initial_stock}" placeholder="Ex: 10" required>
            </div>
            <button type="button" class="btn-admin-danger text-xs py-1 px-2 self-end" onclick="this.parentElement.remove()">Retirer</button>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', rowHtml);
}

async function handleProductFormSubmit(event) {
    event.preventDefault();
    const form = event.target;
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
            } 
            else {
                productData[key] = value;
            }
        }
    }
    productData.is_published = form.querySelector('#product-is-published').checked;

    const weightOptions = [];
    document.querySelectorAll('.weight-option-row').forEach(row => {
        const option_id_el = row.querySelector('input[name*="[option_id]"]'); // For editing existing variants
        const option_id = option_id_el ? option_id_el.value : null;
        const weight_grams = row.querySelector('input[name*="[weight_grams]"]').value;
        const price = row.querySelector('input[name*="[price]"]').value;
        const initial_stock_val = row.querySelector('input[name*="[initial_stock]"]').value; // Named 'initial_stock' but means current stock on edit
        
        if (weight_grams && price && initial_stock_val) {
            const opt = {
                weight_grams: parseInt(weight_grams),
                price: parseFloat(price),
                initial_stock: parseInt(initial_stock_val) // This is 'current_stock' when editing variants
            };
            if(option_id) opt.option_id = parseInt(option_id);
            weightOptions.push(opt);
        }
    });

    if (weightOptions.length > 0) {
        productData.weight_options = weightOptions;
        productData.base_price = null; 
        productData.initial_stock_quantity = 0; 
    } else {
        if(productData.base_price !== null && productData.initial_stock_quantity === null) productData.initial_stock_quantity = 0;
    }

    try {
        const thumbString = formData.get('image_urls_thumb');
        productData.image_urls_thumb = thumbString ? JSON.parse(thumbString) : [];
        if (!Array.isArray(productData.image_urls_thumb)) productData.image_urls_thumb = [];
    } catch (e) {
        productData.image_urls_thumb = [];
        setFieldError(form.querySelector('#product-image-urls-thumb'), "Format JSON invalide.");
        return; // Stop submission if JSON is invalid
    }

    const method = editingProductId ? 'PUT' : 'POST';
    const endpoint = editingProductId ? `/products/${editingProductId}` : '/products';

    try {
        showAdminToast("Enregistrement du produit...", "info");
        const result = await adminApiRequest(endpoint, method, productData);
        if (result.success) {
            showAdminToast(result.message, "success");
            form.reset();
            document.getElementById('weight-options-container').innerHTML = '';
            document.getElementById('add-edit-product-section').style.display = 'none';
            document.getElementById('show-add-product-form-button').style.display = 'inline-flex';
            editingProductId = null;
            loadAdminProductsList(); 
        }
    } catch (error) {
        console.error("Erreur soumission formulaire produit:", error);
    }
}

function validateProductForm(form) {
    let isValid = true;
    const requiredFields = ['product-id', 'product-name', 'product-category', 'product-short-description', 'product-image-url-main'];
    if (editingProductId) requiredFields.shift(); // ID not required for edit (it's readonly)

    requiredFields.forEach(id => {
        const field = form.querySelector(`#${id}`);
        if (!field.value.trim()) {
            setFieldError(field, "Ce champ est requis.");
            isValid = false;
        }
    });

    const basePriceField = form.querySelector('#product-base-price');
    const weightOptionsContainer = form.querySelector('#weight-options-container');
    if (!basePriceField.value && weightOptionsContainer.children.length === 0) {
        setFieldError(basePriceField, "Un prix de base ou des options de poids sont requis.");
        isValid = false;
    }
    if (basePriceField.value && parseFloat(basePriceField.value) < 0) {
        setFieldError(basePriceField, "Le prix de base ne peut pas être négatif.");
        isValid = false;
    }
    
    form.querySelectorAll('.weight-option-row input[type="number"]').forEach(input => {
        if (parseFloat(input.value) < 0) {
            setFieldError(input, "La valeur ne peut pas être négative.");
            isValid = false;
        }
    });

    const mainImageUrl = form.querySelector('#product-image-url-main').value;
    if (mainImageUrl && !isValidUrl(mainImageUrl)) {
        setFieldError(form.querySelector('#product-image-url-main'), "URL de l'image principale invalide.");
        isValid = false;
    }
    
    const thumbInput = form.querySelector('#product-image-urls-thumb');
    if (thumbInput.value.trim()) {
        try {
            const thumbs = JSON.parse(thumbInput.value.trim());
            if (!Array.isArray(thumbs) || !thumbs.every(url => typeof url === 'string' && isValidUrl(url))) {
                 setFieldError(thumbInput, "Doit être un tableau JSON d'URLs valides.");
                 isValid = false;
            }
        } catch (e) {
            setFieldError(thumbInput, "Format JSON invalide pour les miniatures.");
            isValid = false;
        }
    }


    if (!isValid) showAdminToast("Veuillez corriger les erreurs dans le formulaire.", "error");
    return isValid;
}


async function loadAdminProductsList() {
    const tableBody = document.getElementById('products-table-body');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4">Chargement...</td></tr>';

    try {
        productsForAdmin = await adminApiRequest('/products'); 
        if (productsForAdmin.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4">Aucun produit trouvé.</td></tr>';
            return;
        }
        
        let rowsHtml = '';
        productsForAdmin.forEach(product => {
            let priceDisplay = product.base_price ? `${parseFloat(product.base_price).toFixed(2)} €` : 'Variantes';
            rowsHtml += `
                <tr>
                    <td class="px-6 py-3">${product.id}</td>
                    <td class="px-6 py-3 font-medium text-brand-near-black">${product.name}</td>
                    <td class="px-6 py-3">${product.category}</td>
                    <td class="px-6 py-3">${priceDisplay}</td>
                    <td class="px-6 py-3">${product.stock_quantity !== undefined ? product.stock_quantity : (product.variant_count > 0 ? 'N/A (variantes)' : 0)}</td>
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

async function editProduct(productId) { // Modified to fetch full details for variants
    editingProductId = productId;
    // Fetch full product details to ensure weight_options are up-to-date
    let product;
    try {
        product = await adminApiRequest(`/products/${productId}`); // Assume this endpoint exists and returns variants
         if (!product) throw new Error("Produit non trouvé");
    } catch (e) {
        showAdminToast("Impossible de charger les détails du produit pour l'édition.", "error");
        return;
    }


    const form = document.getElementById('product-form');
    form.reset(); 
    clearFormErrors(form);
    document.getElementById('product-form-title').textContent = `Modifier le Produit: ${product.name}`;
    document.getElementById('product-id').value = product.id;
    document.getElementById('product-id').readOnly = true; 
    document.getElementById('product-name').value = product.name;
    document.getElementById('product-category').value = product.category;
    document.getElementById('product-short-description').value = product.short_description || '';
    document.getElementById('product-long-description').value = product.long_description || '';
    document.getElementById('product-image-url-main').value = product.image_url_main || '';
    document.getElementById('product-image-urls-thumb').value = product.image_urls_thumb ? (typeof product.image_urls_thumb === 'string' ? product.image_urls_thumb : JSON.stringify(product.image_urls_thumb)) : '[]';
    document.getElementById('product-species').value = product.species || '';
    document.getElementById('product-origin').value = product.origin || '';
    document.getElementById('product-seasonality').value = product.seasonality || '';
    document.getElementById('product-ideal-uses').value = product.ideal_uses || '';
    document.getElementById('product-sensory-description').value = product.sensory_description || '';
    document.getElementById('product-pairing-suggestions').value = product.pairing_suggestions || '';
    document.getElementById('product-base-price').value = product.base_price !== null ? product.base_price : '';
    document.getElementById('product-initial-stock-quantity').value = product.base_price !== null ? (product.stock_quantity || 0) : ''; 
    document.getElementById('product-is-published').checked = product.is_published;

    const weightOptionsContainer = document.getElementById('weight-options-container');
    weightOptionsContainer.innerHTML = ''; 
    if (product.weight_options && product.weight_options.length > 0) {
        product.weight_options.forEach(opt => addWeightOptionRow({
            option_id: opt.option_id, // Pass option_id for update
            weight_grams: opt.weight_grams,
            price: opt.price,
            initial_stock: opt.stock_quantity 
        }));
        document.getElementById('simple-product-stock-section').style.display = 'none';
         document.getElementById('product-base-price').value = ''; // Clear base price if variants exist
         document.getElementById('product-initial-stock-quantity').value = ''; // Clear simple stock
    } else {
        document.getElementById('simple-product-stock-section').style.display = 'block';
    }


    document.getElementById('add-edit-product-section').style.display = 'block';
    document.getElementById('show-add-product-form-button').style.display = 'none';
    window.scrollTo(0, 0); 
}

// --- Inventory Management (admin_manage_inventory.html) ---
let productsForInventorySelect = [];

async function initializeInventoryManagement() {
    await populateProductSelectsForInventory(); 

    const addStockForm = document.getElementById('add-stock-form');
    if (addStockForm) addStockForm.addEventListener('submit', handleAddStockSubmit);

    const manualAdjustForm = document.getElementById('manual-adjust-stock-form');
    if (manualAdjustForm) manualAdjustForm.addEventListener('submit', handleManualAdjustSubmit);
    
    const productSelects = [
        document.getElementById('stock-product-select'),
        document.getElementById('adjust-product-select'),
        document.getElementById('inventory-filter-product')
    ];
    productSelects.forEach(select => {
        if (select) {
            select.addEventListener('change', (event) => handleProductSelectionForVariant(event.target));
        }
    });
    
    loadInventoryOverview(); 
    const filterProductSelect = document.getElementById('inventory-filter-product');
    if(filterProductSelect) filterProductSelect.addEventListener('change', () => loadInventoryOverview(filterProductSelect.value));
}

async function populateProductSelectsForInventory() {
    try {
        // Fetch products with their variant counts for better display if needed
        const products = await adminApiRequest('/products?include_variants=true'); // Assuming backend can provide this
        productsForInventorySelect = products; 

        const selects = [
            document.getElementById('stock-product-select'),
            document.getElementById('adjust-product-select'),
            document.getElementById('inventory-filter-product')
        ];

        selects.forEach(selectElement => {
            if (selectElement) {
                selectElement.innerHTML = '<option value="">Sélectionner un produit</option>'; 
                products.forEach(p => {
                    const option = document.createElement('option');
                    option.value = p.id;
                    option.textContent = `${p.name} (ID: ${p.id})${p.variant_count > 0 ? ' - Variantes multiples' : (p.base_price === null ? ' - Variantes multiples' : '')}`;
                    selectElement.appendChild(option);
                });
            }
        });
    } catch (error) {
        showAdminToast("Erreur de chargement de la liste des produits pour les stocks.", "error");
    }
}

async function handleProductSelectionForVariant(productSelectElement) {
    const selectedProductId = productSelectElement.value;
    let variantSelectContainerId, variantSelectId;
    if (productSelectElement.id === 'stock-product-select') {
        variantSelectContainerId = 'stock-variant-select-container';
        variantSelectId = 'stock-variant-select';
    } else if (productSelectElement.id === 'adjust-product-select') {
        variantSelectContainerId = 'adjust-variant-select-container';
        variantSelectId = 'adjust-variant-select';
    } else {
        return; 
    }

    const variantContainer = document.getElementById(variantSelectContainerId);
    const variantSelect = document.getElementById(variantSelectId);

    if (!selectedProductId) {
        variantContainer.style.display = 'none';
        variantSelect.innerHTML = '<option value="">Sélectionner une variante</option>';
        variantSelect.required = false; // Not required if no product or no variants
        return;
    }

    try {
        const productDetails = await adminApiRequest(`/products/${selectedProductId}`); // Fetch full product details
        
        if (productDetails.weight_options && productDetails.weight_options.length > 0) {
            variantSelect.innerHTML = '<option value="">Sélectionner une variante (obligatoire)</option>';
            productDetails.weight_options.forEach(opt => {
                const optionEl = document.createElement('option');
                optionEl.value = opt.option_id;
                optionEl.textContent = `${opt.weight_grams}g (Stock: ${opt.stock_quantity}, Prix: ${opt.price.toFixed(2)}€)`;
                variantSelect.appendChild(optionEl);
            });
            variantContainer.style.display = 'block';
            variantSelect.required = true; // Variant is required if options exist
        } else {
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

async function handleAddStockSubmit(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form);
    if (!validateInventoryForm(form, 'add')) return;

    const product_id = form.product_id.value;
    const variant_option_id = form.variant_option_id ? form.variant_option_id.value : null;
    const quantity_add = parseInt(form.quantity_add.value);
    const movement_type_add = form.movement_type_add.value;
    const notes_add = form.notes_add.value;
    
    const payload = {
        product_id: product_id,
        variant_option_id: variant_option_id || null, 
        quantity_change: quantity_add, 
        movement_type: movement_type_add,
        notes: notes_add
    };

    try {
        showAdminToast("Ajout du stock en cours...", "info");
        const result = await adminApiRequest('/inventory/adjust', 'POST', payload);
        if (result.success) {
            showAdminToast(result.message || "Stock ajouté avec succès.", "success");
            form.reset();
            document.getElementById('stock-variant-select-container').style.display = 'none';
            document.getElementById('stock-variant-select').innerHTML = '<option value="">Sélectionner une variante</option>';
            document.getElementById('stock-variant-select').required = false;
            loadInventoryOverview(); 
        }
    } catch (error) {
        // Toast shown by adminApiRequest
    }
}

async function handleManualAdjustSubmit(event) {
    event.preventDefault();
    const form = event.target;
    clearFormErrors(form);
    if (!validateInventoryForm(form, 'adjust')) return;
    
    const product_id = form.product_id_adjust.value;
    const variant_option_id = form.variant_option_id_adjust ? form.variant_option_id_adjust.value : null;
    const quantity_change = parseInt(form.quantity_change.value);
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
            document.getElementById('adjust-variant-select-container').style.display = 'none';
            document.getElementById('adjust-variant-select').innerHTML = '<option value="">Sélectionner une variante</option>';
            document.getElementById('adjust-variant-select').required = false;
            loadInventoryOverview(); 
        }
    } catch (error) {
        // Toast shown by adminApiRequest
    }
}

function validateInventoryForm(form, type) {
    let isValid = true;
    const productIdField = form.querySelector(type === 'add' ? '#stock-product-select' : '#adjust-product-select');
    const quantityField = form.querySelector(type === 'add' ? '#stock-quantity-add' : '#stock-quantity-change');
    const notesField = form.querySelector(type === 'add' ? '#stock-add-notes' : '#adjust-notes');
    const variantSelect = form.querySelector(type === 'add' ? '#stock-variant-select' : '#adjust-variant-select');


    if (!productIdField.value) {
        setFieldError(productIdField, "Veuillez sélectionner un produit.");
        isValid = false;
    }
    
    // If variant select is visible (meaning product has variants) and no variant is selected
    if (variantSelect && variantSelect.parentElement.style.display !== 'none' && !variantSelect.value) {
        setFieldError(variantSelect, "Veuillez sélectionner une variante.");
        isValid = false;
    }


    if (!quantityField.value || isNaN(parseInt(quantityField.value))) {
        setFieldError(quantityField, "Veuillez entrer une quantité valide.");
        isValid = false;
    } else {
        const quantity = parseInt(quantityField.value);
        if (type === 'add' && quantity <= 0) {
            setFieldError(quantityField, "La quantité à ajouter doit être positive.");
            isValid = false;
        }
        if (type === 'adjust' && quantity === 0) {
            setFieldError(quantityField, "Le changement de quantité ne peut pas être zéro.");
            isValid = false;
        }
    }

    if (type === 'adjust' && !notesField.value.trim()) {
        setFieldError(notesField, "Une raison/note est requise pour l'ajustement manuel.");
        isValid = false;
    }
    if (type === 'add' && !notesField.value.trim() && form.movement_type_add.value === 'addition') { // Example: notes required for generic 'addition'
         // setFieldError(notesField, "Notes requises pour ce type de mouvement.");
         // isValid = false;
    }


    if (!isValid) showAdminToast("Veuillez corriger les erreurs.", "error");
    return isValid;
}


async function loadInventoryOverview(filterProductId = '') {
    const tableBody = document.getElementById('inventory-table-body');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Chargement...</td></tr>';

    try {
        let productsToDisplay = productsForInventorySelect; // Use already fetched list
        if (filterProductId) {
            productsToDisplay = productsForInventorySelect.filter(p => p.id === filterProductId);
        }

        if (productsToDisplay.length === 0 && !filterProductId) {
             tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">Aucun produit à afficher. Ajoutez des produits d\'abord.</td></tr>';
             return;
        }
        if (productsToDisplay.length === 0 && filterProductId) {
             tableBody.innerHTML = `<tr><td colspan="5" class="text-center py-4">Produit ID ${filterProductId} non trouvé ou sans stock.</td></tr>`;
             return;
        }

        let rowsHtml = '';
        for (const productSummary of productsToDisplay) {
            // Fetch detailed inventory for each product for up-to-date stock
            try {
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
                } else { 
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
                    <tr>
                        <td class="px-6 py-3">${productSummary.name}</td>
                        <td class="px-6 py-3" colspan="3">Erreur chargement stock</td>
                        <td class="px-6 py-3">-</td>
                    </tr>
                `;
                console.error(`Erreur chargement stock pour ${productSummary.id}:`, invError);
            }
        }
        tableBody.innerHTML = rowsHtml || '<tr><td colspan="5" class="text-center py-4">Aucune donnée de stock à afficher.</td></tr>';

    } catch (error) {
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-red-600">Erreur de chargement de l\'inventaire.</td></tr>';
    }
}

async function viewProductInventoryMovementsModal(productId, variantOptionId = null) {
    // This function would populate a modal with movement history.
    // For now, it just shows a toast.
    try {
        const details = await adminApiRequest(`/inventory/product/${productId}${variantOptionId ? `?variant_id=${variantOptionId}`: ''}`);
        let historyHtml = '<ul class="text-xs space-y-1 max-h-60 overflow-y-auto">';
        if (details.additions_log) {
            details.additions_log.forEach(log => {
                 historyHtml += `<li class="text-green-700 p-1 bg-green-50 rounded"><strong>+${log.quantity_change}</strong> (${log.movement_type}) le ${new Date(log.movement_date).toLocaleString('fr-FR')} - ${log.notes || 'N/A'}</li>`;
            });
        }
        if(details.subtractions_log){
            details.subtractions_log.forEach(log => {
                 historyHtml += `<li class="text-red-700 p-1 bg-red-50 rounded"><strong>${log.quantity_change}</strong> (${log.movement_type}) le ${new Date(log.movement_date).toLocaleString('fr-FR')} - ${log.notes || 'N/A'} ${log.order_id ? `(Cmd: ${log.order_id})` : ''}</li>`;
            });
        }
        historyHtml += '</ul>';
        
        // Assuming a generic modal structure
        const modalTitle = document.getElementById('generic-modal-title');
        const modalBody = document.getElementById('generic-modal-body');
        if (modalTitle && modalBody) {
            modalTitle.textContent = `Historique des mouvements pour ${productId} ${variantOptionId ? `(Variante ${variantOptionId})` : ''}`;
            modalBody.innerHTML = historyHtml || '<p>Aucun mouvement enregistré.</p>';
            openAdminModal('generic-modal'); // You'd need a generic modal in your HTML
        } else {
            showAdminToast(`Historique pour ${productId} chargé (détails en console).`, "info");
            console.log(details);
        }
    } catch (e) {
        showAdminToast("Impossible de charger l'historique des mouvements.", "error");
    }
}


// --- User Management (admin_manage_users.html) ---
function initializeUserManagement() {
    loadAdminUsersList();
    const closeModalButton = document.getElementById('close-user-detail-modal-button');
    if(closeModalButton) closeModalButton.addEventListener('click', () => closeAdminModal('user-detail-modal'));
}

async function loadAdminUsersList() {
    const tableBody = document.getElementById('users-table-body');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4">Chargement...</td></tr>';

    try {
        const users = await adminApiRequest('/users');
        if (users.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4">Aucun utilisateur trouvé.</td></tr>';
            return;
        }
        
        let rowsHtml = '';
        users.forEach(user => {
            rowsHtml += `
                <tr>
                    <td class="px-6 py-3">${user.id}</td>
                    <td class="px-6 py-3">${user.email}</td>
                    <td class="px-6 py-3">${user.nom || '-'}</td>
                    <td class="px-6 py-3">${user.prenom || '-'}</td>
                    <td class="px-6 py-3">${user.is_admin ? '<span class="font-semibold text-brand-classic-gold">Oui</span>' : 'Non'}</td>
                    <td class="px-6 py-3">${new Date(user.created_at).toLocaleDateString('fr-FR')}</td>
                    <td class="px-6 py-3">
                        <button onclick="viewUserDetails(${user.id})" class="btn-admin-secondary text-xs p-1.5">Détails</button>
                    </td>
                </tr>
            `;
        });
        tableBody.innerHTML = rowsHtml;
    } catch (error) {
        tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-red-600">Erreur de chargement des utilisateurs.</td></tr>';
    }
}

async function viewUserDetails(userId) {
    try {
        showAdminToast("Chargement des détails utilisateur...", "info");
        const userDetails = await adminApiRequest(`/users/${userId}`);
        if (userDetails) {
            document.getElementById('detail-user-id').textContent = userDetails.id;
            document.getElementById('detail-user-email').textContent = userDetails.email;
            document.getElementById('detail-user-nom').textContent = userDetails.nom || '-';
            document.getElementById('detail-user-prenom').textContent = userDetails.prenom || '-';
            document.getElementById('detail-user-isadmin').textContent = userDetails.is_admin ? 'Oui' : 'Non';
            document.getElementById('detail-user-createdat').textContent = new Date(userDetails.created_at).toLocaleString('fr-FR');
            
            const ordersList = document.getElementById('detail-user-orders');
            ordersList.innerHTML = '';
            if (userDetails.orders && userDetails.orders.length > 0) {
                userDetails.orders.forEach(order => {
                    const li = document.createElement('li');
                    li.textContent = `Cmd #${order.order_id} - ${parseFloat(order.total_amount).toFixed(2)}€ - Statut: ${order.status} (${new Date(order.order_date).toLocaleDateString('fr-FR')})`;
                    ordersList.appendChild(li);
                });
            } else {
                ordersList.innerHTML = '<li class="text-brand-warm-taupe italic">Aucune commande pour cet utilisateur.</li>';
            }

            openAdminModal('user-detail-modal');
        }
    } catch (error) {
        // Toast shown by adminApiRequest
    }
}

// --- Order Management (admin_manage_orders.html) ---
let currentOrders = []; // To store fetched orders for client-side interactions

function initializeOrderManagement() {
    loadAdminOrders(); // Initial load

    const filterButton = document.getElementById('apply-order-filters-button');
    if (filterButton) filterButton.addEventListener('click', applyOrderFilters);

    const closeModalButton = document.getElementById('close-order-detail-modal-button');
    if (closeModalButton) closeModalButton.addEventListener('click', () => closeAdminModal('order-detail-modal'));
    
    const updateStatusForm = document.getElementById('update-order-status-form');
    if (updateStatusForm) updateStatusForm.addEventListener('submit', handleUpdateOrderStatus);

    const addNoteForm = document.getElementById('add-order-note-form');
    if (addNoteForm) addNoteForm.addEventListener('submit', handleAddOrderNote);

    const newStatusSelect = document.getElementById('modal-order-new-status');
    if (newStatusSelect) newStatusSelect.addEventListener('change', toggleShippingInfoFields);
}

async function loadAdminOrders(filters = {}) {
    const tableBody = document.getElementById('orders-table-body');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="6" class="text-center py-4">Chargement des commandes...</td></tr>';

    let queryParams = new URLSearchParams(filters).toString();
    try {
        // Backend needs to support these filters: /api/admin/orders?search=...&status=...&date=...
        currentOrders = await adminApiRequest(`/orders${queryParams ? '?' + queryParams : ''}`);
        displayAdminOrders(currentOrders);
    } catch (error) {
        tableBody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-red-600">Erreur de chargement des commandes.</td></tr>';
    }
}

function displayAdminOrders(orders) {
    const tableBody = document.getElementById('orders-table-body');
    tableBody.innerHTML = ''; 

    if (!orders || orders.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6" class="text-center py-4">Aucune commande trouvée.</td></tr>';
        return;
    }

    orders.forEach(order => {
        const row = `
            <tr>
                <td class="px-6 py-3">${order.order_id}</td>
                <td class="px-6 py-3">${order.customer_email} <br> <span class="text-xs text-brand-warm-taupe">${order.customer_name || ''}</span></td>
                <td class="px-6 py-3">${new Date(order.order_date).toLocaleDateString('fr-FR')}</td>
                <td class="px-6 py-3">${parseFloat(order.total_amount).toFixed(2)} €</td>
                <td class="px-6 py-3"><span class="px-2 py-1 text-xs font-semibold rounded-full ${getOrderStatusClass(order.status)}">${order.status}</span></td>
                <td class="px-6 py-3">
                    <button onclick="openOrderDetailModal(${order.order_id})" class="btn-admin-secondary text-xs p-1.5">Détails</button>
                </td>
            </tr>
        `;
        tableBody.insertAdjacentHTML('beforeend', row);
    });
}

function getOrderStatusClass(status) {
    switch (status) {
        case 'Paid': return 'bg-green-100 text-green-800';
        case 'Shipped': return 'bg-blue-100 text-blue-800';
        case 'Delivered': return 'bg-purple-100 text-purple-800';
        case 'Pending': return 'bg-yellow-100 text-yellow-800';
        case 'Cancelled': return 'bg-red-100 text-red-800';
        default: return 'bg-gray-100 text-gray-800';
    }
}

function applyOrderFilters() {
    const search = document.getElementById('order-search').value;
    const status = document.getElementById('order-status-filter').value;
    const date = document.getElementById('order-date-filter').value;
    const filters = {};
    if (search) filters.search = search;
    if (status) filters.status = status;
    if (date) filters.date = date;
    loadAdminOrders(filters);
}

async function openOrderDetailModal(orderId) {
    try {
        showAdminToast("Chargement des détails de la commande...", "info");
        const order = await adminApiRequest(`/orders/${orderId}`); // Backend: GET /api/admin/orders/:id
        if (order) {
            document.getElementById('modal-order-id').textContent = order.order_id;
            document.getElementById('update-order-id-hidden').value = order.order_id; // For form submission
            document.getElementById('modal-order-date').textContent = new Date(order.order_date).toLocaleString('fr-FR');
            document.getElementById('modal-order-customer-email').textContent = order.customer_email;
            document.getElementById('modal-order-customer-name').textContent = order.customer_name || 'Non spécifié'; // Assuming backend provides this
            document.getElementById('modal-order-current-status').textContent = order.status;
            document.getElementById('modal-order-total-amount').textContent = `${parseFloat(order.total_amount).toFixed(2)} €`;
            document.getElementById('modal-order-shipping-address').innerHTML = order.shipping_address.replace(/\n/g, '<br>');
            
            const itemsTableBody = document.getElementById('modal-order-items-table-body');
            itemsTableBody.innerHTML = '';
            if (order.items && order.items.length > 0) {
                order.items.forEach(item => {
                    itemsTableBody.innerHTML += `
                        <tr>
                            <td class="p-2">${item.product_name}</td>
                            <td class="p-2">${item.variant || '-'}</td>
                            <td class="p-2 text-center">${item.quantity}</td>
                            <td class="p-2 text-right">${parseFloat(item.price_at_purchase).toFixed(2)} €</td>
                            <td class="p-2 text-right">${(item.price_at_purchase * item.quantity).toFixed(2)} €</td>
                        </tr>
                    `;
                });
            } else {
                itemsTableBody.innerHTML = '<tr><td colspan="5" class="p-2 text-center italic">Aucun article dans cette commande.</td></tr>';
            }
            
            document.getElementById('modal-order-new-status').value = order.status;
            toggleShippingInfoFields(); // Show/hide shipping based on current/new status

            // Notes (assuming backend provides notes array)
            const notesHistory = document.getElementById('modal-order-notes-history');
            notesHistory.innerHTML = '';
            if (order.notes && order.notes.length > 0) {
                 order.notes.forEach(note => {
                    notesHistory.innerHTML += `<p class="mb-1 border-b border-brand-cream pb-1"><strong>${new Date(note.created_at).toLocaleString('fr-FR')} (${note.admin_user || 'Système'}):</strong> ${note.content}</p>`;
                 });
            } else {
                notesHistory.innerHTML = '<p class="italic text-brand-warm-taupe">Aucune note.</p>';
            }

            openAdminModal('order-detail-modal');
        }
    } catch (error) {
        // Error toast shown by adminApiRequest
    }
}

function toggleShippingInfoFields() {
    const statusSelect = document.getElementById('modal-order-new-status');
    const shippingFields = document.getElementById('shipping-info-fields');
    if (statusSelect.value === 'Shipped' || statusSelect.value === 'Delivered') {
        shippingFields.style.display = 'block';
    } else {
        shippingFields.style.display = 'none';
    }
}

async function handleUpdateOrderStatus(event) {
    event.preventDefault();
    const form = event.target;
    const orderId = form.querySelector('#update-order-id-hidden').value;
    const newStatus = form.querySelector('#modal-order-new-status').value;
    const trackingNumber = form.querySelector('#modal-order-tracking-number').value;
    const carrier = form.querySelector('#modal-order-carrier').value;

    if (!orderId || !newStatus) {
        showAdminToast("ID de commande ou nouveau statut manquant.", "error");
        return;
    }
    
    const payload = {
        status: newStatus,
        tracking_number: (newStatus === 'Shipped' || newStatus === 'Delivered') ? trackingNumber : null,
        carrier: (newStatus === 'Shipped' || newStatus === 'Delivered') ? carrier : null,
    };

    try {
        showAdminToast("Mise à jour du statut...", "info");
        // Backend: PUT /api/admin/orders/:id/status
        const result = await adminApiRequest(`/orders/${orderId}/status`, 'PUT', payload);
        if (result.success) {
            showAdminToast(result.message || "Statut de la commande mis à jour.", "success");
            closeAdminModal('order-detail-modal');
            loadAdminOrders(); // Refresh list
        }
    } catch (error) {
        // Toast shown by adminApiRequest
    }
}

async function handleAddOrderNote(event) {
    event.preventDefault();
    const form = event.target;
    const orderId = document.getElementById('update-order-id-hidden').value; // Get orderId from hidden field in status update form
    const noteContent = form.querySelector('#modal-order-new-note').value;

    if (!orderId || !noteContent.trim()) {
        showAdminToast("Contenu de la note manquant.", "error");
        return;
    }
    
    try {
        showAdminToast("Ajout de la note...", "info");
        // Backend: POST /api/admin/orders/:id/notes
        const result = await adminApiRequest(`/orders/${orderId}/notes`, 'POST', { note: noteContent });
        if (result.success) {
            showAdminToast(result.message || "Note ajoutée.", "success");
            form.reset();
            // Refresh notes in modal if still open - requires re-fetching order details or smarter update
            const currentOrderInModal = currentOrders.find(o => o.order_id.toString() === orderId);
            if (currentOrderInModal && document.getElementById('order-detail-modal').classList.contains('active')) {
                 openOrderDetailModal(orderId); // Re-open to refresh notes
            }
        }
    } catch (error) {
        // Toast shown by adminApiRequest
    }
}


// --- Form Validation Helpers ---
function setFieldError(field, message) {
    field.classList.add('border-red-500'); // Add error class for styling
    let errorElement = field.nextElementSibling;
    if (!errorElement || !errorElement.classList.contains('error-message')) {
        errorElement = document.createElement('p');
        errorElement.classList.add('error-message', 'text-xs', 'text-red-600', 'mt-1');
        field.parentNode.insertBefore(errorElement, field.nextSibling);
    }
    errorElement.textContent = message;
}

function clearFormErrors(form) {
    form.querySelectorAll('.border-red-500').forEach(el => el.classList.remove('border-red-500'));
    form.querySelectorAll('.error-message').forEach(el => el.remove());
}

function isValidUrl(string) {
    try {
        new URL(string);
        return true;
    } catch (_) {
        return false;
    }
}

// Basic Modal Open/Close
function openAdminModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('active');
}
function closeAdminModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.admin-modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', function(event) {
            if (event.target === this) { 
                closeAdminModal(this.id);
            }
        });
    });
     // Generic modal close button if you add one
    const genericModalClose = document.getElementById('close-generic-modal-button');
    if (genericModalClose) genericModalClose.addEventListener('click', () => closeAdminModal('generic-modal'));
});
