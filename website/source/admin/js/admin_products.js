// website/source/admin/js/admin_products.js
// Handles the "Manage Products" page in the admin panel.

document.addEventListener('DOMContentLoaded', function() {
    // --- DOM Element References ---
    const productForm = document.getElementById('productForm');
    const productsTableBody = document.getElementById('productsTableBody');
    const productCategorySelect = document.getElementById('productCategory');
    const formTitle = document.getElementById('formTitle');
    const productCodeInput = document.getElementById('productCode');
    const saveProductButton = document.getElementById('saveProductButton');
    const cancelEditButton = document.getElementById('cancelEditButton');
    const productSearchInput = document.getElementById('productSearchInput');
    const productTypeSelect = document.getElementById('productType');


    // --- State Variables ---
    let editingProductId = null; // Use product ID for editing
    let allProductsCache = []; 

    // --- Initialization ---
    loadInitialData();

    async function loadInitialData() {
        await loadCategoriesForSelect(); 
        await loadProductsTable();       
    }

    async function loadCategoriesForSelect() {
        try {
            const apiResponse = await adminApi.getCategories(); // Expects { categories: [...] }
            const categories = apiResponse.categories || []; // Defensive coding
            productCategorySelect.innerHTML = '<option value="">-- Select Category --</option>'; 
            categories.forEach(category => {
                if (category.is_active) { 
                    const option = document.createElement('option');
                    option.value = category.id; 
                    option.textContent = `${category.name} (${category.category_code})`;
                    productCategorySelect.appendChild(option);
                }
            });
        } catch (error) {
            console.error('Failed to load categories for select:', error);
            showAdminToast('Error loading categories for the dropdown. Please try refreshing.', 'error');
        }
    }

    function renderProductsTable(productsToRender) {
        productsTableBody.innerHTML = ''; 
        if (!productsToRender || productsToRender.length === 0) {
            productsTableBody.innerHTML = '<tr><td colspan="9">No products found.</td></tr>';
            return;
        }
        productsToRender.forEach(product => {
            const row = productsTableBody.insertRow();
            row.insertCell().textContent = product.product_code;
            row.insertCell().textContent = product.name;
            row.insertCell().textContent = product.category_name ? `${product.category_name} (${product.category_code || 'N/A'})` : 'Uncategorized';
            row.insertCell().textContent = product.price !== null ? `€${parseFloat(product.price).toFixed(2)}` : 'N/A (Variable)';
            row.insertCell().textContent = product.quantity !== undefined ? product.quantity : 'N/A'; // Aggregate stock
            row.insertCell().textContent = product.type || 'simple';
            row.insertCell().innerHTML = product.is_active ? '<span class="text-green-600 font-semibold">Yes</span>' : '<span class="text-red-600">No</span>';
            row.insertCell().innerHTML = product.is_featured ? '<span class="text-blue-600">Yes</span>' : 'No';
            
            const actionsCell = row.insertCell();
            const editButton = document.createElement('button');
            editButton.textContent = 'Edit';
            editButton.classList.add('btn', 'btn-admin-secondary', 'small-button'); // Use new CSS classes
            editButton.onclick = () => populateFormForEdit(product);
            actionsCell.appendChild(editButton);

            const deleteButton = document.createElement('button');
            deleteButton.textContent = 'Delete';
            deleteButton.classList.add('btn', 'btn-admin-danger', 'small-button'); // Use new CSS classes
            deleteButton.onclick = () => confirmDeleteProduct(product.id, product.name, product.product_code);
            actionsCell.appendChild(deleteButton);
        });
    }
    
    async function loadProductsTable() {
        try {
            productsTableBody.innerHTML = '<tr><td colspan="9">Loading products...</td></tr>'; // Updated colspan
            const response = await adminApi.getProducts(); // Expects { products: [...] }
            allProductsCache = response.products || []; 
            renderProductsTable(allProductsCache); 
        } catch (error) {
            console.error('Failed to load products:', error);
            showAdminToast('Error loading products list. Please try refreshing.', 'error');
            productsTableBody.innerHTML = '<tr><td colspan="9">Error loading products.</td></tr>'; // Updated colspan
        }
    }
    
    productSearchInput.addEventListener('input', function(e) {
        const searchTerm = e.target.value.toLowerCase().trim();
        if (!allProductsCache) return;

        const filteredProducts = allProductsCache.filter(product => {
            return (
                product.name.toLowerCase().includes(searchTerm) ||
                product.product_code.toLowerCase().includes(searchTerm) ||
                (product.category_name && product.category_name.toLowerCase().includes(searchTerm)) ||
                (product.description && product.description.toLowerCase().includes(searchTerm))
            );
        });
        renderProductsTable(filteredProducts);
    });

    function populateFormForEdit(product) {
        formTitle.textContent = `Edit Product: ${product.name} (${product.product_code})`;
        saveProductButton.textContent = 'Update Product';
        cancelEditButton.style.display = 'inline-block'; 
        
        editingProductId = product.id; // Store product ID for update
        
        productCodeInput.value = product.product_code;
        // productCodeInput.readOnly = true; // Product code generally should not be changed once set, or handled carefully.
                                          // For this refactor, we'll assume it's editable if needed.

        document.getElementById('productName').value = product.name;
        document.getElementById('productDescription').value = product.description || '';
        document.getElementById('productPrice').value = product.base_price !== null ? parseFloat(product.base_price).toFixed(2) : '';
        productCategorySelect.value = product.category_id || '';
        productTypeSelect.value = product.type || 'simple';

        document.getElementById('productQuantity').value = product.aggregate_stock_quantity !== undefined ? product.aggregate_stock_quantity : 0;
        document.getElementById('lowStockThreshold').value = product.low_stock_threshold !== undefined ? product.low_stock_threshold : 10;
        document.getElementById('supplierInfo').value = product.supplier_info || '';
        
        document.getElementById('productImageUrl').value = product.main_image_url || '';
        document.getElementById('productIsActive').checked = product.is_active;
        document.getElementById('productIsFeatured').checked = product.is_featured;

        const productFormContainer = document.getElementById('productFormContainer');
        if (productFormContainer) {
            productFormContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    function resetForm() {
        formTitle.textContent = 'Add New Product';
        saveProductButton.textContent = 'Save Product';
        productForm.reset(); 
        productCodeInput.readOnly = false;
        editingProductId = null; 
        cancelEditButton.style.display = 'none'; 

        document.getElementById('productIsActive').checked = true;
        document.getElementById('productIsFeatured').checked = false;
        productCategorySelect.value = ""; 
        productTypeSelect.value = "simple";
    }
    
    cancelEditButton.addEventListener('click', resetForm);

    productForm.addEventListener('submit', async function(event) {
        event.preventDefault(); 
        const formData = new FormData(productForm);
        // No 'sku_prefix' to send, product_code serves this role now.

        // Client-side validation (can be enhanced)
        if (!formData.get('product_code').trim()) {
            showAdminToast('Product Code (SKU) is required.', 'error'); return;
        }
        if (!formData.get('name').trim()) {
            showAdminToast('Product Name is required.', 'error'); return;
        }
        if (!formData.get('category_id')) {
            showAdminToast('Category is required.', 'error'); return;
        }
        if (formData.get('type') === 'simple' && (formData.get('price').trim() === '' || isNaN(parseFloat(formData.get('price'))) || parseFloat(formData.get('price')) < 0)) {
            showAdminToast('A valid Base Price is required for simple products.', 'error'); return;
        }
         if (formData.get('type') === 'simple' && (formData.get('quantity').trim() === '' || isNaN(parseInt(formData.get('quantity'))) || parseInt(formData.get('quantity')) < 0)) {
            showAdminToast('A valid Stock Quantity is required for simple products.', 'error'); return;
        }


        saveProductButton.disabled = true;
        saveProductButton.textContent = editingProductId ? 'Updating...' : 'Saving...';

        try {
            let response;
            if (editingProductId) {
                response = await adminApi.updateProduct(editingProductId, formData); // Pass FormData directly
            } else {
                response = await adminApi.addProduct(formData); // Pass FormData directly
            }
            
            if (response.success) {
                showAdminToast(response.message || `Product ${editingProductId ? 'updated' : 'added'} successfully!`, 'success');
                resetForm(); 
                await loadProductsTable(); 
            } else {
                showAdminToast(response.message || 'Failed to save product.', 'error');
            }
        } catch (error) {
            console.error('Failed to save product:', error);
            const errorMessage = error.data?.message || error.message || 'An unknown error occurred.';
            showAdminToast(errorMessage, 'error');
        } finally {
            saveProductButton.disabled = false;
            saveProductButton.textContent = editingProductId ? 'Update Product' : 'Save Product';
        }
    });

    function confirmDeleteProduct(productId, productName, productCode) {
        showAdminConfirm(
            'Confirm Delete Product', 
            `Are you sure you want to delete the product: <strong>${productName} (${productCode})</strong>? This action cannot be undone.`, 
            async () => {
                try {
                    const response = await adminApi.deleteProduct(productId);
                     if (response.success) {
                        showAdminToast(response.message || `Product "${productName}" deleted successfully!`, 'success');
                        await loadProductsTable(); 
                    } else {
                        showAdminToast(response.message || 'Failed to delete product.', 'error');
                    }
                } catch (error) {
                    console.error('Failed to delete product:', error);
                    const errorMessage = error.data?.message || 'Failed to delete product. Please try again.';
                    showAdminToast(errorMessage, 'error');
                }
            },
            'Delete Product', 
            'Cancel'          
        );
    }
});
