// website/source/admin/js/admin_categories.js
// This script handles the "Manage Categories" page in the admin panel.

document.addEventListener('DOMContentLoaded', function() {
    // --- DOM Element References ---
    const categoryForm = document.getElementById('categoryForm');
    const categoriesTableBody = document.getElementById('categoriesTableBody');
    const categoryFormTitle = document.getElementById('categoryFormTitle');
    const categoryCodeInput = document.getElementById('categoryCode'); // For category_code field// website/source/admin/js/admin_categories.js
// This script handles the "Manage Categories" page in the admin panel.

document.addEventListener('DOMContentLoaded', function() {
    // --- DOM Element References ---
    const categoryForm = document.getElementById('categoryForm');
    const categoriesTableBody = document.getElementById('categoriesTableBody');
    const categoryFormTitle = document.getElementById('categoryFormTitle');
    const categoryCodeInput = document.getElementById('categoryCode'); 
    const saveCategoryButton = document.getElementById('saveCategoryButton');
    const cancelCategoryEditButton = document.getElementById('cancelCategoryEditButton');

    // --- State Variables ---
    let editingCategoryOriginalCode = null; 

    // --- Initialization ---
    loadCategoriesTable(); 

    /**
     * Renders the list of categories into the table.
     * @param {Array<object>} categoriesToRender - The array of category objects to display.
     */
    function renderCategoriesTable(categoriesToRender) {
        categoriesTableBody.innerHTML = ''; 
        if (!categoriesToRender || categoriesToRender.length === 0) {
            const emptyRow = categoriesTableBody.insertRow();
            const cell = emptyRow.insertCell();
            cell.colSpan = 6;
            cell.textContent = "No categories found."; // XSS: static text
            return;
        }
        categoriesToRender.forEach(category => {
            const row = categoriesTableBody.insertRow();
            row.insertCell().textContent = category.category_code; // XSS
            row.insertCell().textContent = category.name; // XSS
            row.insertCell().textContent = category.description || 'N/A'; // XSS
            
            const activeCell = row.insertCell();
            const activeSpan = document.createElement('span');
            activeSpan.textContent = category.is_active ? 'Yes' : 'No'; // XSS: static text
            activeSpan.style.color = category.is_active ? 'green' : 'red';
            activeCell.appendChild(activeSpan);
            
            const productCountCell = row.insertCell();
            productCountCell.textContent = category.product_count !== undefined ? category.product_count : 'N/A'; // XSS

            const actionsCell = row.insertCell();
            const editButton = document.createElement('button');
            editButton.textContent = 'Edit'; // XSS: static text
            editButton.classList.add('small-button', 'btn', 'btn-admin-secondary'); // Added btn classes
            editButton.onclick = () => populateCategoryFormForEdit(category);
            actionsCell.appendChild(editButton);

            const deleteButton = document.createElement('button');
            deleteButton.textContent = 'Delete'; // XSS: static text
            deleteButton.classList.add('small-button', 'delete', 'btn', 'btn-admin-danger'); // Added btn classes
            if (category.product_count > 0) {
                deleteButton.disabled = true;
                deleteButton.title = "Cannot delete: This category is associated with existing products.";
            }
            deleteButton.onclick = () => confirmDeleteCategory(category.category_code, category.name);
            actionsCell.appendChild(deleteButton);
        });
    }
    
    /**
     * Fetches all categories from the API and renders them in the table.
     */
    async function loadCategoriesTable() {
        try {
            const loadingRow = categoriesTableBody.insertRow();
            const cell = loadingRow.insertCell();
            cell.colSpan = 6;
            cell.textContent = "Loading categories..."; // XSS: static text
            categoriesTableBody.innerHTML = ''; // Clear after creating, then replace
            categoriesTableBody.appendChild(loadingRow);

            const response = await adminApi.getCategories(); // Expects { categories: [...] }
            const categories = response.categories || []; // Defensive
            renderCategoriesTable(categories);
        } catch (error) {
            console.error('Failed to load categories:', error);
            showAdminToast('Error loading categories list. Please try refreshing.', 'error'); // Using showAdminToast
            categoriesTableBody.innerHTML = ''; // Clear loading
            const errorRow = categoriesTableBody.insertRow();
            const cell = errorRow.insertCell();
            cell.colSpan = 6;
            cell.textContent = "Error loading categories."; // XSS: static text
        }
    }
    
    /**
     * Populates the category form with data for editing an existing category.
     * @param {object} category - The category object to edit.
     */
    function populateCategoryFormForEdit(category) {
        categoryFormTitle.textContent = `Edit Category: ${category.name} (${category.category_code})`; // XSS: category data
        saveCategoryButton.textContent = 'Update Category'; // XSS: static
        cancelCategoryEditButton.style.display = 'inline-block'; 
        
        editingCategoryOriginalCode = category.category_code; 
        
        categoryCodeInput.value = category.category_code;
        document.getElementById('categoryName').value = category.name;
        document.getElementById('categoryDescription').value = category.description || '';
        document.getElementById('categoryImageUrl').value = category.image_url || '';
        document.getElementById('categoryIsActive').checked = category.is_active;
        
        const categoryFormContainer = document.getElementById('categoryFormContainer');
        if (categoryFormContainer) {
            categoryFormContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    /**
     * Resets the category form to its default state for adding a new category.
     */
    function resetCategoryForm() {
        categoryFormTitle.textContent = 'Add New Category'; // XSS: static
        saveCategoryButton.textContent = 'Save Category'; // XSS: static
        categoryForm.reset(); 
        categoryCodeInput.readOnly = false; 
        editingCategoryOriginalCode = null; 
        cancelCategoryEditButton.style.display = 'none'; 
        document.getElementById('categoryIsActive').checked = true;
    }

    cancelCategoryEditButton.addEventListener('click', resetCategoryForm);

    /**
     * Handles the submission of the category form (for both add and update).
     */
    categoryForm.addEventListener('submit', async function(event) {
        event.preventDefault(); 
        const formData = new FormData(categoryForm);
        // No need to convert to plain object if adminApi.updateCategory/addCategory handles FormData
        
        if (!formData.get('category_code').trim()) {
            showAdminToast('Category Code is required.', 'error'); // Using showAdminToast
            return;
        }
        if (!formData.get('name').trim()) {
            showAdminToast('Category Name is required.', 'error'); // Using showAdminToast
            return;
        }
        
        saveCategoryButton.disabled = true;
        saveCategoryButton.textContent = editingCategoryOriginalCode ? 'Updating...' : 'Saving...'; // XSS: static

        try {
            let response;
            if (editingCategoryOriginalCode) {
                // Pass FormData directly to the API method
                response = await adminApi.updateCategory(editingCategoryOriginalCode, formData);
            } else {
                response = await adminApi.addCategory(formData);
            }
            // Assuming adminApi methods return { success: true/false, message: "...", category: {...} (optional) }
            if (response.success) {
                showAdminToast(response.message || `Category ${editingCategoryOriginalCode ? 'updated' : 'added'} successfully!`, 'success');
                resetCategoryForm(); 
                await loadCategoriesTable(); 
            } else {
                 showAdminToast(response.message || 'Failed to save category.', 'error');
            }
        } catch (error) {
            console.error('Failed to save category:', error);
            // Error toast is likely handled by adminApi itself now.
            // If not, uncomment:
            // const errorMessage = error.data?.message || error.message || 'An unknown error occurred.';
            // showAdminToast(errorMessage, 'error');
        } finally {
            saveCategoryButton.disabled = false;
            saveCategoryButton.textContent = editingCategoryOriginalCode ? 'Update Category' : 'Save Category'; // XSS: static
        }
    });

    /**
     * Confirms and handles the deletion of a category.
     * @param {string} categoryCode - The code of the category to delete.
     * @param {string} categoryName - The name of the category (for confirmation message).
     */
    function confirmDeleteCategory(categoryCode, categoryName) {
        const messageParagraph = document.createElement('p');
        messageParagraph.textContent = `Are you sure you want to delete the category: `; // XSS: static
        const strongElement = document.createElement('strong');
        strongElement.textContent = `${categoryName} (${categoryCode})`; // XSS: category data
        messageParagraph.appendChild(strongElement);
        messageParagraph.append("? This action cannot be undone. Ensure no products are associated with this category."); // XSS: static

        showAdminConfirm(
            'Confirm Delete Category',
            messageParagraph.innerHTML, // Using innerHTML as it was safely constructed
            async () => { 
                try {
                    const response = await adminApi.deleteCategory(categoryCode);
                    if(response.success) {
                        showAdminToast(response.message || `Category "${categoryName}" (${categoryCode}) deleted successfully!`, 'success');
                        await loadCategoriesTable(); 
                    } // Error toast handled by adminApi
                } catch (error) {
                    console.error('Failed to delete category:', error);
                     // Error toast handled by adminApi
                }
            },
            'Delete Category', 
            'Cancel'           
        );
    }
});
