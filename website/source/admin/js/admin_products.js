// website/source/admin/js/admin_products.js
// Handles the "Manage Products" page in the admin panel.

document.addEventListener('DOMContentLoaded', function() {
    // --- DOM Element References ---
    const productForm = document.getElementById('productForm');
    const productsTableBody = document.getElementById('productsTableBody');
    const productCategorySelect = document.getElementById('productCategory');
    const formTitle = document.getElementById('formTitle');
    const productCodeInput = document.getElementById('productCode');
    const saveProductButton = document.getElementById('saveProductButton');// website/source/admin/js/admin_products.js
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
    let editingProductId = null; 
    let allProductsCache = []; 

    // --- Initialization ---
    loadInitialData();

    async function loadInitialData() {
        await loadCategoriesForSelect(); 
        await loadProductsTable();       
    }

    async function loadCategoriesForSelect() {
        try {
            const apiResponse = await adminApi.getCategories(); 
            const categories = apiResponse.categories || []; 
            productCategorySelect.innerHTML = '<option value="">-- Select Category --</option>'; 
            categories.forEach(category => {
                if (category.is_active) { 
                    const option = document.createElement('option');
                    option.value = category.id; 
                    option.textContent = `${category.name} (${category.category_code || 'N/A'})`; // XSS: textContent
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
            const emptyRow = productsTableBody.insertRow();
            const cell = emptyRow.insertCell();
            cell.colSpan = 9; // Adjusted colspan
            cell.textContent = "No products found."; // XSS: static text
            return;
        }
        productsToRender.forEach(product => {
            const row = productsTableBody.insertRow();
            row.insertCell().textContent = product.product_code; // XSS
            row.insertCell().textContent = product.name; // XSS
            row.insertCell().textContent = product.category_name ? `${product.category_name} (${product.category_code || 'N/A'})` : 'Uncategorized'; // XSS
            row.insertCell().textContent = product.price !== null ? `€${parseFloat(product.price).toFixed(2)}` : 'N/A (Variable)'; // XSS
            row.insertCell().textContent = product.quantity !== undefined ? product.quantity : 'N/A'; // XSS
            row.insertCell().textContent = product.type || 'simple'; // XSS
            
            const activeCell = row.insertCell();
            const activeSpan = document.createElement('span');
            activeSpan.textContent = product.is_active ? 'Yes' : 'No'; // XSS: static text
            activeSpan.className = product.is_active ? 'text-green-600 font-semibold' : 'text-red-600';
            activeCell.appendChild(activeSpan);

            const featuredCell = row.insertCell();
            const featuredSpan = document.createElement('span');
            featuredSpan.textContent = product.is_featured ? 'Yes' : 'No'; // XSS: static text
            featuredSpan.className = product.is_featured ? 'text-blue-600' : '';
            featuredCell.appendChild(featuredSpan);
            
            const actionsCell = row.insertCell();
            const editButton = document.createElement('button');
            editButton.textContent = 'Edit'; // XSS: static text
            editButton.classList.add('btn', 'btn-admin-secondary', 'small-button'); 
            editButton.onclick = () => populateFormForEdit(product);
            actionsCell.appendChild(editButton);

            const deleteButton = document.createElement('button');
            deleteButton.textContent = 'Delete'; // XSS: static text
            deleteButton.classList.add('btn', 'btn-admin-danger', 'small-button'); 
            deleteButton.onclick = () => confirmDeleteProduct(product.id, product.name, product.product_code);
            actionsCell.appendChild(deleteButton);
        });
    }
    
    async function loadProductsTable() {
        try {
            const loadingRow = productsTableBody.insertRow();
            const cell = loadingRow.insertCell();
            cell.colSpan = 9; // Adjusted colspan
            cell.textContent = "Loading products..."; // XSS: static text
            productsTableBody.innerHTML = ''; // Clear after creating, then replace
            productsTableBody.appendChild(loadingRow);

            const response = await adminApi.getProducts(); 
            allProductsCache = response.products || []; 
            renderProductsTable(allProductsCache); 
        } catch (error) {
            console.error('Failed to load products:', error);
            showAdminToast('Error loading products list. Please try refreshing.', 'error');
            productsTableBody.innerHTML = ''; // Clear loading
            const errorRow = productsTableBody.insertRow();
            const cell = errorRow.insertCell();
            cell.colSpan = 9; // Adjusted colspan
            cell.textContent = "Error loading products."; // XSS: static text
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
        formTitle.textContent = `Edit Product: ${product.name} (${product.product_code})`; // XSS: product data
        saveProductButton.textContent = 'Update Product'; // XSS: static
        cancelEditButton.style.display = 'inline-block'; 
        
        editingProductId = product.id; 
        
        productCodeInput.value = product.product_code;
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
        formTitle.textContent = 'Add New Product'; // XSS: static
        saveProductButton.textContent = 'Save Product'; // XSS: static
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
        saveProductButton.textContent = editingProductId ? 'Updating...' : 'Saving...'; // XSS: static

        try {
            let response;
            if (editingProductId) {
                response = await adminApi.updateProduct(editingProductId, formData); 
            } else {
                response = await adminApi.addProduct(formData); 
            }
            
            if (response.success) {
                showAdminToast(response.message || `Product ${editingProductId ? 'updated' : 'added'} successfully!`, 'success');
                resetForm(); 
                await loadProductsTable(); 
            } // Error toast handled by adminApi
        } catch (error) {
            console.error('Failed to save product:', error);
            // Error toast handled by adminApi
        } finally {
            saveProductButton.disabled = false;
            saveProductButton.textContent = editingProductId ? 'Update Product' : 'Save Product'; // XSS: static
        }
    });

    function confirmDeleteProduct(productId, productName, productCode) {
        // showAdminConfirm uses textContent for title and creates p for message,
        // but message can accept HTML. Ensure it's used safely.
        const messageParagraph = document.createElement('p');
        messageParagraph.textContent = `Are you sure you want to delete the product: `; // XSS: static
        const strongElement = document.createElement('strong');
        strongElement.textContent = `${productName} (${productCode})`; // XSS: product data
        messageParagraph.appendChild(strongElement);
        messageParagraph.append("? This action cannot be undone."); // XSS: static

        showAdminConfirm(
            'Confirm Delete Product', 
            messageParagraph.innerHTML, // Using innerHTML here because we constructed it safely
            async () => {
                try {
                    const response = await adminApi.deleteProduct(productId);
                     if (response.success) {
                        showAdminToast(response.message || `Product "${productName}" deleted successfully!`, 'success');
                        await loadProductsTable(); 
                    } // Error toast handled by adminApi
                } catch (error) {
                    console.error('Failed to delete product:', error);
                    // Error toast handled by adminApi
                }
            },
            'Delete Product', 
            'Cancel'          
        );
    }
});
