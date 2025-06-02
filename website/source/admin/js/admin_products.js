// website/source/admin/js/admin_products.js
// This script handles the "Manage Products & Inventory" page in the admin panel.

document.addEventListener('DOMContentLoaded', function() {
    // --- DOM Element References ---
    const productForm = document.getElementById('productForm');
    const productsTableBody = document.getElementById('productsTableBody');
    const productCategorySelect = document.getElementById('productCategory');
    const formTitle = document.getElementById('formTitle');
    const productCodeInput = document.getElementById('productCode'); // Product Code (SKU) field
    const saveProductButton = document.getElementById('saveProductButton');
    const cancelEditButton = document.getElementById('cancelEditButton');
    const productSearchInput = document.getElementById('productSearchInput');

    // --- State Variables ---
    let editingProductOriginalCode = null; // Stores the original product_code when editing
    let allProductsCache = []; // Cache for all fetched products to enable client-side search

    // --- Initialization ---
    loadInitialData();

    /**
     * Loads initial data required for the page (categories and products).
     */
    async function loadInitialData() {
        await loadCategoriesForSelect(); // Load categories first for the dropdown
        await loadProductsTable();       // Then load products
    }

    /**
     * Fetches categories from the API and populates the category select dropdown.
     */
    async function loadCategoriesForSelect() {
        try {
            const categories = await adminApi.getCategories();
            productCategorySelect.innerHTML = '<option value="">-- Select Category --</option>'; // Default option
            categories.forEach(category => {
                if (category.is_active) { // Only show active categories in the dropdown
                    const option = document.createElement('option');
                    option.value = category.id; // Backend expects category_id (integer FK)
                    option.textContent = `${category.name} (${category.category_code})`;
                    option.dataset.categoryCode = category.category_code; // Store code for reference if needed
                    productCategorySelect.appendChild(option);
                }
            });
        } catch (error) {
            console.error('Failed to load categories for select:', error);
            showAdminMessage('Error loading categories for the dropdown. Please try refreshing.', 'error');
        }
    }

    /**
     * Renders the list of products into the table.
     * @param {Array<object>} productsToRender - The array of product objects to display.
     */
    function renderProductsTable(productsToRender) {
        productsTableBody.innerHTML = ''; // Clear existing rows
        if (!productsToRender || productsToRender.length === 0) {
            productsTableBody.innerHTML = '<tr><td colspan="8">No products found.</td></tr>';
            return;
        }
        productsToRender.forEach(product => {
            const row = productsTableBody.insertRow();
            // Populate cells, using product_code as the main identifier
            row.insertCell().textContent = product.product_code;
            row.insertCell().textContent = product.name;
            row.insertCell().textContent = product.category_name ? `${product.category_name} (${product.category_code || 'N/A'})` : 'Uncategorized';
            row.insertCell().textContent = `€${parseFloat(product.price).toFixed(2)}`;
            row.insertCell().textContent = product.quantity !== undefined ? product.quantity : 'N/A'; // Inventory quantity
            row.insertCell().innerHTML = product.is_active ? '<span style="color: green;">Yes</span>' : '<span style="color: red;">No</span>';
            row.insertCell().innerHTML = product.is_featured ? '<span style="color: blue;">Yes</span>' : 'No';
            
            // Actions cell (Edit, Delete)
            const actionsCell = row.insertCell();
            const editButton = document.createElement('button');
            editButton.textContent = 'Edit';
            editButton.classList.add('small-button');
            editButton.onclick = () => populateFormForEdit(product);
            actionsCell.appendChild(editButton);

            const deleteButton = document.createElement('button');
            deleteButton.textContent = 'Delete';
            deleteButton.classList.add('small-button', 'delete');
            deleteButton.onclick = () => confirmDeleteProduct(product.product_code, product.name);
            actionsCell.appendChild(deleteButton);
        });
    }
    
    /**
     * Fetches all products from the API and renders them in the table.
     */
    async function loadProductsTable() {
        try {
            productsTableBody.innerHTML = '<tr><td colspan="8">Loading products...</td></tr>';
            allProductsCache = await adminApi.getProducts(); // Fetch and cache
            renderProductsTable(allProductsCache); // Render from cache
        } catch (error) {
            console.error('Failed to load products:', error);
            showAdminMessage('Error loading products list. Please try refreshing.', 'error');
            productsTableBody.innerHTML = '<tr><td colspan="8">Error loading products.</td></tr>';
        }
    }
    
    // --- Event Listeners ---
    /**
     * Handles product search input to filter the displayed products.
     */
    productSearchInput.addEventListener('input', function(e) {
        const searchTerm = e.target.value.toLowerCase().trim();
        if (!allProductsCache) return; // Guard if cache isn't populated

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

    /**
     * Populates the product form with data for editing an existing product.
     * @param {object} product - The product object to edit.
     */
    function populateFormForEdit(product) {
        formTitle.textContent = `Edit Product: ${product.name} (${product.product_code})`;
        saveProductButton.textContent = 'Update Product';
        cancelEditButton.style.display = 'inline-block'; // Show cancel button
        
        editingProductOriginalCode = product.product_code; // Store original code for the PUT request
        
        // Populate form fields
        productCodeInput.value = product.product_code;
        // productCodeInput.readOnly = true; // Product code can be updatable based on backend logic
                                          // If not updatable, set to true. Current backend allows it.

        document.getElementById('productName').value = product.name;
        document.getElementById('productDescription').value = product.description || '';
        document.getElementById('productPrice').value = parseFloat(product.price).toFixed(2);
        productCategorySelect.value = product.category_id || ''; // category_id is the integer FK

        // Inventory fields
        document.getElementById('productQuantity').value = product.quantity !== undefined ? product.quantity : 0;
        document.getElementById('lowStockThreshold').value = product.low_stock_threshold !== undefined ? product.low_stock_threshold : 10;
        document.getElementById('supplierInfo').value = product.supplier_info || '';
        
        document.getElementById('productImageUrl').value = product.image_url || '';
        document.getElementById('productIsActive').checked = product.is_active;
        document.getElementById('productIsFeatured').checked = product.is_featured;

        // Scroll to the form for better UX
        const productFormContainer = document.getElementById('productFormContainer');
        if (productFormContainer) {
            productFormContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    /**
     * Resets the product form to its default state for adding a new product.
     */
    function resetForm() {
        formTitle.textContent = 'Add New Product';
        saveProductButton.textContent = 'Save Product';
        productForm.reset(); // Resets all form fields
        productCodeInput.readOnly = false; // Ensure product code is editable for new products
        editingProductOriginalCode = null; // Clear editing state
        cancelEditButton.style.display = 'none'; // Hide cancel button

        // Explicitly set defaults for checkboxes if `reset()` doesn't handle them as expected
        document.getElementById('productIsActive').checked = true;
        document.getElementById('productIsFeatured').checked = false;
        productCategorySelect.value = ""; // Reset category dropdown to default
    }
    
    cancelEditButton.addEventListener('click', resetForm);

    /**
     * Handles the submission of the product form (for both add and update).
     */
    productForm.addEventListener('submit', async function(event) {
        event.preventDefault(); // Prevent default form submission
        const formData = new FormData(productForm);
        const productData = {};
        
        // Convert FormData to a plain object, handling types
        for (const [key, value] of formData.entries()) {
            if (key === 'price' || key === 'quantity' || key === 'low_stock_threshold') {
                // Convert to number, or null if empty (backend should handle nulls appropriately)
                productData[key] = value.trim() === '' ? null : Number(value);
            } else if (key === 'category_id') {
                 productData[key] = value.trim() === '' ? null : parseInt(value, 10); 
                 if (isNaN(productData[key])) productData[key] = null; 
            } else if (key === 'is_active' || key === 'is_featured') {
                // Checkbox values are handled by their 'checked' property
                productData[key] = document.getElementById(key === 'is_active' ? 'productIsActive' : 'productIsFeatured').checked;
            } else {
                productData[key] = value.trim(); // Trim whitespace for string fields
            }
        }
        
        // --- Basic Client-Side Validation ---
        if (!productData.product_code) {
            showAdminMessage('Product Code (SKU) is required.', 'error', 'Validation Error');
            return;
        }
        if (!productData.name) {
            showAdminMessage('Product Name is required.', 'error', 'Validation Error');
            return;
        }
        if (productData.category_id === null || productData.category_id === "") {
            showAdminMessage('Category is required.', 'error', 'Validation Error');
            return;
        }
        if (productData.price === null || isNaN(productData.price) || productData.price < 0) {
            showAdminMessage('A valid Price (non-negative number) is required.', 'error', 'Validation Error');
            return;
        }
        if (productData.quantity === null || isNaN(productData.quantity) || productData.quantity < 0) {
            showAdminMessage('A valid Stock Quantity (non-negative number) is required.', 'error', 'Validation Error');
            return;
        }
        // Low stock threshold validation (optional, can be 0 or null)
        if (productData.low_stock_threshold !== null && (isNaN(productData.low_stock_threshold) || productData.low_stock_threshold < 0)) {
            showAdminMessage('Low Stock Threshold must be a non-negative number if provided.', 'error', 'Validation Error');
            return;
        }


        // Disable button to prevent multiple submissions
        saveProductButton.disabled = true;
        saveProductButton.textContent = editingProductOriginalCode ? 'Updating...' : 'Saving...';

        try {
            let response;
            if (editingProductOriginalCode) {
                // Update existing product
                response = await adminApi.updateProduct(editingProductOriginalCode, productData);
            } else {
                // Add new product
                response = await adminApi.addProduct(productData);
            }
            showAdminMessage(response.message || `Product ${editingProductOriginalCode ? 'updated' : 'added'} successfully!`, 'success');
            resetForm(); // Clear form and editing state
            await loadProductsTable(); // Refresh the products list
        } catch (error) {
            console.error('Failed to save product:', error);
            // Display a user-friendly error message from the API response if available
            const errorMessage = error.response?.data?.error || error.message || 'An unknown error occurred while saving the product.';
            showAdminMessage(errorMessage, 'error', 'Save Product Error');
        } finally {
            // Re-enable button
            saveProductButton.disabled = false;
            // Restore button text based on whether it was an edit or add
            saveProductButton.textContent = editingProductOriginalCode ? 'Update Product' : 'Save Product';
        }
    });

    /**
     * Confirms and handles the deletion of a product.
     * @param {string} productCode - The code of the product to delete.
     * @param {string} productName - The name of the product (for confirmation message).
     */
    function confirmDeleteProduct(productCode, productName) {
        showAdminConfirm(
            'Confirm Delete Product', 
            `Are you sure you want to delete the product: <strong>${productName} (${productCode})</strong>? This action cannot be undone. Associated inventory will also be removed.`, 
            async () => { // This is the onConfirmCallback
                try {
                    await adminApi.deleteProduct(productCode);
                    showAdminMessage(`Product "${productName}" (${productCode}) deleted successfully!`, 'success');
                    await loadProductsTable(); // Refresh the products list
                } catch (error) {
                    console.error('Failed to delete product:', error);
                    const errorMessage = error.response?.data?.error || 'Failed to delete product. Please try again.';
                    showAdminMessage(errorMessage, 'error', 'Delete Product Error');
                }
            },
            'Delete Product', // Confirm button text
            'Cancel'          // Cancel button text
        );
    }
});