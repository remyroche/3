// website/source/admin/js/admin_categories.js
// This script handles the "Manage Categories" page in the admin panel.

document.addEventListener('DOMContentLoaded', function() {
    // --- DOM Element References ---
    const categoryForm = document.getElementById('categoryForm');
    const categoriesTableBody = document.getElementById('categoriesTableBody');
    const categoryFormTitle = document.getElementById('categoryFormTitle');
    const categoryCodeInput = document.getElementById('categoryCode'); // For category_code field
    const saveCategoryButton = document.getElementById('saveCategoryButton');
    const cancelCategoryEditButton = document.getElementById('cancelCategoryEditButton');

    // --- State Variables ---
    let editingCategoryOriginalCode = null; // Stores the original category_code when editing

    // --- Initialization ---
    loadCategoriesTable(); // Load categories when the page loads

    /**
     * Renders the list of categories into the table.
     * @param {Array<object>} categoriesToRender - The array of category objects to display.
     */
    function renderCategoriesTable(categoriesToRender) {
        categoriesTableBody.innerHTML = ''; // Clear existing rows
        if (!categoriesToRender || categoriesToRender.length === 0) {
            categoriesTableBody.innerHTML = '<tr><td colspan="6">No categories found.</td></tr>';
            return;
        }
        categoriesToRender.forEach(category => {
            const row = categoriesTableBody.insertRow();
            // Populate cells, using category_code as the main identifier
            row.insertCell().textContent = category.category_code;
            row.insertCell().textContent = category.name;
            row.insertCell().textContent = category.description || 'N/A'; // Display N/A if no description
            row.insertCell().innerHTML = category.is_active ? '<span style="color: green;">Yes</span>' : '<span style="color: red;">No</span>';
            
            // Display product count (assuming backend provides 'product_count')
            const productCountCell = row.insertCell();
            productCountCell.textContent = category.product_count !== undefined ? category.product_count : 'N/A';

            // Actions cell (Edit, Delete)
            const actionsCell = row.insertCell();
            const editButton = document.createElement('button');
            editButton.textContent = 'Edit';
            editButton.classList.add('small-button');
            editButton.onclick = () => populateCategoryFormForEdit(category);
            actionsCell.appendChild(editButton);

            const deleteButton = document.createElement('button');
            deleteButton.textContent = 'Delete';
            deleteButton.classList.add('small-button', 'delete');
             // Disable delete if product_count > 0, as per backend constraint
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
            categoriesTableBody.innerHTML = '<tr><td colspan="6">Loading categories...</td></tr>';
            const categories = await adminApi.getCategories();
            renderCategoriesTable(categories);
        } catch (error) {
            console.error('Failed to load categories:', error);
            showAdminMessage('Error loading categories list. Please try refreshing.', 'error');
            categoriesTableBody.innerHTML = '<tr><td colspan="6">Error loading categories.</td></tr>';
        }
    }
    
    /**
     * Populates the category form with data for editing an existing category.
     * @param {object} category - The category object to edit.
     */
    function populateCategoryFormForEdit(category) {
        categoryFormTitle.textContent = `Edit Category: ${category.name} (${category.category_code})`;
        saveCategoryButton.textContent = 'Update Category';
        cancelCategoryEditButton.style.display = 'inline-block'; // Show cancel button
        
        editingCategoryOriginalCode = category.category_code; // Store original code for the PUT request
        
        // Populate form fields
        categoryCodeInput.value = category.category_code;
        // categoryCodeInput.readOnly = true; // Category code can be updatable based on backend logic.
                                           // If not updatable, set to true. Current backend allows it.

        document.getElementById('categoryName').value = category.name;
        document.getElementById('categoryDescription').value = category.description || '';
        document.getElementById('categoryImageUrl').value = category.image_url || '';
        document.getElementById('categoryIsActive').checked = category.is_active;
        
        // Scroll to the form for better UX
        const categoryFormContainer = document.getElementById('categoryFormContainer');
        if (categoryFormContainer) {
            categoryFormContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    /**
     * Resets the category form to its default state for adding a new category.
     */
    function resetCategoryForm() {
        categoryFormTitle.textContent = 'Add New Category';
        saveCategoryButton.textContent = 'Save Category';
        categoryForm.reset(); // Resets all form fields
        categoryCodeInput.readOnly = false; // Ensure category code is editable for new categories
        editingCategoryOriginalCode = null; // Clear editing state
        cancelCategoryEditButton.style.display = 'none'; // Hide cancel button

        // Explicitly set default for checkbox if `reset()` doesn't handle it as expected
        document.getElementById('categoryIsActive').checked = true;
    }

    cancelCategoryEditButton.addEventListener('click', resetCategoryForm);

    /**
     * Handles the submission of the category form (for both add and update).
     */
    categoryForm.addEventListener('submit', async function(event) {
        event.preventDefault(); // Prevent default form submission
        const formData = new FormData(categoryForm);
        const categoryData = {};
        
        // Convert FormData to a plain object
        for (const [key, value] of formData.entries()) {
            if (key === 'is_active') {
                // Checkbox value is handled by its 'checked' property
                categoryData[key] = document.getElementById('categoryIsActive').checked;
            } else {
                categoryData[key] = value.trim(); // Trim whitespace for string fields
            }
        }

        // --- Basic Client-Side Validation ---
        if (!categoryData.category_code) {
            showAdminMessage('Category Code is required.', 'error', 'Validation Error');
            return;
        }
        if (!categoryData.name) {
            showAdminMessage('Category Name is required.', 'error', 'Validation Error');
            return;
        }
        
        // Disable button to prevent multiple submissions
        saveCategoryButton.disabled = true;
        saveCategoryButton.textContent = editingCategoryOriginalCode ? 'Updating...' : 'Saving...';

        try {
            let response;
            if (editingCategoryOriginalCode) {
                // Update existing category
                response = await adminApi.updateCategory(editingCategoryOriginalCode, categoryData);
            } else {
                // Add new category
                response = await adminApi.addCategory(categoryData);
            }
            showAdminMessage(response.message || `Category ${editingCategoryOriginalCode ? 'updated' : 'added'} successfully!`, 'success');
            resetCategoryForm(); // Clear form and editing state
            await loadCategoriesTable(); // Refresh the categories list
        } catch (error) {
            console.error('Failed to save category:', error);
            // Display a user-friendly error message from the API response if available
            const errorMessage = error.response?.data?.error || error.message || 'An unknown error occurred while saving the category.';
            showAdminMessage(errorMessage, 'error', 'Save Category Error');
        } finally {
            // Re-enable button
            saveCategoryButton.disabled = false;
            // Restore button text based on whether it was an edit or add
            saveCategoryButton.textContent = editingCategoryOriginalCode ? 'Update Category' : 'Save Category';
        }
    });

    /**
     * Confirms and handles the deletion of a category.
     * @param {string} categoryCode - The code of the category to delete.
     * @param {string} categoryName - The name of the category (for confirmation message).
     */
    function confirmDeleteCategory(categoryCode, categoryName) {
        showAdminConfirm(
            'Confirm Delete Category',
            `Are you sure you want to delete the category: <strong>${categoryName} (${categoryCode})</strong>? This action cannot be undone. Ensure no products are associated with this category.`,
            async () => { // This is the onConfirmCallback
                try {
                    await adminApi.deleteCategory(categoryCode);
                    showAdminMessage(`Category "${categoryName}" (${categoryCode}) deleted successfully!`, 'success');
                    await loadCategoriesTable(); // Refresh the categories list
                } catch (error) {
                    console.error('Failed to delete category:', error);
                    const errorMessage = error.response?.data?.error || 'Failed to delete category. It might still be associated with products or another issue occurred.';
                    showAdminMessage(errorMessage, 'error', 'Delete Category Error');
                }
            },
            'Delete Category', // Confirm button text
            'Cancel'           // Cancel button text
        );
    }
});