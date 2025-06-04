// js/admin_categories.js
document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const addCategoryBtn = document.getElementById('add-new-category-btn');
    const categoryFormSection = document.getElementById('add-category-form-section');
    const cancelCategoryFormBtn = document.getElementById('cancel-category-form-btn');
    const categoryForm = document.getElementById('category-form');
    const categoriesTableBody = document.querySelector('#categories-table tbody');
    const categoryParentSelect = document.getElementById('category-parent');
    const categoryIdInput = document.getElementById('category-id');
    const categoryNameInput = document.getElementById('category-name');
    const categoryDescriptionInput = document.getElementById('category-description');

    const API_BASE_URL = '/api/admin/categories'; // Adjust if your API endpoint is different

    // --- Function to display messages (replace with a more robust notification system if you have one) ---
    function showMessage(message, type = 'info') {
        // Example: use a dedicated message area or a simple alert
        // For now, using alert for simplicity. In a real app, use a non-blocking notification.
        alert(`${type.toUpperCase()}: ${message}`);
        console.log(`Notification (${type}): ${message}`);
    }

    // --- Fetch and Display Categories ---
    async function fetchCategories() {
        try {
            const response = await fetchAPIData(API_BASE_URL, {}, 'GET'); // Assuming fetchAPIData is globally available from admin_api.js
            if (response && Array.isArray(response.categories)) {
                renderCategoriesTable(response.categories);
                populateParentCategorySelect(response.categories);
            } else {
                showMessage('Failed to load categories or invalid format.', 'error');
                categoriesTableBody.innerHTML = '<tr><td colspan="4" class="text-center">Erreur de chargement des catégories.</td></tr>';
            }
        } catch (error) {
            console.error('Error fetching categories:', error);
            showMessage('Error fetching categories from server.', 'error');
            categoriesTableBody.innerHTML = '<tr><td colspan="4" class="text-center">Erreur de connexion au serveur.</td></tr>';
        }
    }

    function renderCategoriesTable(categories, parentId = null, level = 0) {
        if (level === 0) { // Clear table only on initial full render
            categoriesTableBody.innerHTML = '';
        }
        const prefix = '&nbsp;&nbsp;&nbsp;'.repeat(level) + (level > 0 ? '↳ ' : '');

        categories.filter(category => category.parent_id === parentId).forEach(category => {
            const row = categoriesTableBody.insertRow();
            row.innerHTML = `
                <td class="font-weight-medium">${prefix}${category.name}</td>
                <td>${category.description || 'N/A'}</td>
                <td>${category.product_count || 0}</td>
                <td class="actions text-right">
                    <button type="button" class="btn-link edit-category" data-id="${category.id}">Modifier</button>
                    <button type="button" class="btn-link danger delete-category" data-id="${category.id}">Supprimer</button>
                </td>
            `;
            // Recursively render child categories
            renderCategoriesTable(categories, category.id, level + 1);
        });

        if (categoriesTableBody.rows.length === 0 && level === 0) {
             categoriesTableBody.innerHTML = '<tr><td colspan="4" class="text-center">Aucune catégorie trouvée.</td></tr>';
        }
    }

    function populateParentCategorySelect(categories, currentCategoryId = null, parentId = null, level = 0) {
        if (level === 0) { // Clear select only on initial full populate
            categoryParentSelect.innerHTML = '<option value="">Aucune (Catégorie Principale)</option>';
        }
        const prefix = '—'.repeat(level) + (level > 0 ? ' ' : '');

        categories.filter(category => category.parent_id === parentId).forEach(category => {
            // Prevent a category from being its own parent or child of its children (simple check)
            if (category.id === currentCategoryId) return;

            const option = document.createElement('option');
            option.value = category.id;
            option.textContent = `${prefix}${category.name}`;
            categoryParentSelect.appendChild(option);
            // Recursively populate for sub-categories
            populateParentCategorySelect(categories, currentCategoryId, category.id, level + 1);
        });
    }

    // --- Form Handling ---
    function openCategoryForm(category = null) {
        categoryForm.reset();
        categoryIdInput.value = '';
        if (category) {
            // Editing existing category
            categoryIdInput.value = category.id;
            categoryNameInput.value = category.name;
            categoryDescriptionInput.value = category.description || '';
            // Repopulate parent select, excluding current category and its descendants
            populateParentCategorySelect(allCategoriesCache, category.id); // Assuming allCategoriesCache is available
            categoryParentSelect.value = category.parent_id || '';
            categoryFormSection.querySelector('h2.section-heading').textContent = 'Modifier la Catégorie';
        } else {
            // Adding new category
            populateParentCategorySelect(allCategoriesCache); // Populate with all categories
            categoryFormSection.querySelector('h2.section-heading').textContent = 'Ajouter une Catégorie';
        }
        categoryFormSection.style.display = 'block';
        categoryNameInput.focus();
    }

    function closeCategoryForm() {
        categoryFormSection.style.display = 'none';
        categoryForm.reset();
        categoryIdInput.value = '';
    }

    async function handleFormSubmit(event) {
        event.preventDefault();
        const id = categoryIdInput.value;
        const parentIdValue = categoryParentSelect.value;
        const data = {
            name: categoryNameInput.value.trim(),
            description: categoryDescriptionInput.value.trim(),
            parent_id: parentIdValue ? parseInt(parentIdValue) : null
        };

        if (!data.name) {
            showMessage('Le nom de la catégorie est requis.', 'error');
            return;
        }

        const method = id ? 'PUT' : 'POST';
        const url = id ? `${API_BASE_URL}/${id}` : API_BASE_URL;

        try {
            const result = await fetchAPIData(url, data, method);
            if (result && (result.id || result.success || result.message)) {
                showMessage(`Catégorie ${id ? 'mise à jour' : 'créée'} avec succès.`, 'success');
                closeCategoryForm();
                fetchCategories(); // Refresh the table and select
            } else {
                showMessage(result.error || `Erreur lors de la ${id ? 'mise à jour' : 'création'} de la catégorie.`, 'error');
            }
        } catch (error) {
            console.error('Error submitting category form:', error);
            showMessage('Erreur de communication avec le serveur.', 'error');
        }
    }

    // --- Edit and Delete ---
    async function handleEditCategory(categoryId) {
        try {
            const category = await fetchAPIData(`${API_BASE_URL}/${categoryId}`, {}, 'GET');
            if (category && category.id) {
                openCategoryForm(category);
            } else {
                showMessage('Impossible de récupérer les détails de la catégorie.', 'error');
            }
        } catch (error) {
            console.error('Error fetching category for edit:', error);
            showMessage('Erreur de communication avec le serveur.', 'error');
        }
    }

    async function handleDeleteCategory(categoryId) {
        // Replace with a custom modal confirmation for better UX
        if (!confirm('Êtes-vous sûr de vouloir supprimer cette catégorie ? Cette action peut être irréversible.')) {
            return;
        }

        try {
            const result = await fetchAPIData(`${API_BASE_URL}/${categoryId}`, {}, 'DELETE');
            if (result && (result.success || result.message)) {
                showMessage('Catégorie supprimée avec succès.', 'success');
                fetchCategories(); // Refresh the table and select
            } else {
                showMessage(result.error || 'Erreur lors de la suppression de la catégorie.', 'error');
            }
        } catch (error) {
            console.error('Error deleting category:', error);
            showMessage('Erreur de communication avec le serveur.', 'error');
        }
    }


    // --- Event Listeners ---
    if (addCategoryBtn) {
        addCategoryBtn.addEventListener('click', () => openCategoryForm());
    }
    if (cancelCategoryFormBtn) {
        cancelCategoryFormBtn.addEventListener('click', closeCategoryForm);
    }
    if (categoryForm) {
        categoryForm.addEventListener('submit', handleFormSubmit);
    }

    if (categoriesTableBody) {
        categoriesTableBody.addEventListener('click', (event) => {
            const target = event.target;
            if (target.classList.contains('edit-category') || target.closest('.edit-category')) {
                const button = target.classList.contains('edit-category') ? target : target.closest('.edit-category');
                const categoryId = button.dataset.id;
                if (categoryId) handleEditCategory(categoryId);
            } else if (target.classList.contains('delete-category') || target.closest('.delete-category')) {
                const button = target.classList.contains('delete-category') ? target : target.closest('.delete-category');
                const categoryId = button.dataset.id;
                if (categoryId) handleDeleteCategory(categoryId);
            }
        });
    }

    // --- Initial Load ---
    let allCategoriesCache = []; // Cache for populating parent select quickly
    async function initializePage() {
        try {
            const response = await fetchAPIData(API_BASE_URL, {}, 'GET');
            if (response && Array.isArray(response.categories)) {
                allCategoriesCache = response.categories; // Store for later use
                renderCategoriesTable(allCategoriesCache);
                populateParentCategorySelect(allCategoriesCache); // Initial population for the form
            } else {
                showMessage('Failed to load categories or invalid format.', 'error');
                categoriesTableBody.innerHTML = '<tr><td colspan="4" class="text-center">Erreur de chargement des catégories.</td></tr>';
            }
        } catch (error) {
            console.error('Error initializing categories page:', error);
            showMessage('Error fetching categories from server.', 'error');
            categoriesTableBody.innerHTML = '<tr><td colspan="4" class="text-center">Erreur de connexion au serveur.</td></tr>';
        }
    }

    initializePage();
});
