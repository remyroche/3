// website/admin/js/admin_users.js
// Logic for managing users in the Admin Panel.

/**
 * Initializes user management functionalities:
 * - Loads the list of users.
 * - Sets up event listener for closing the user detail modal.
 */
function initializeUserManagement() {
    loadAdminUsersList();
    const closeModalButton = document.getElementById('close-user-detail-modal-button'); 
    if(closeModalButton) {
        closeModalButton.addEventListener('click', () => closeAdminModal('user-detail-modal')); 
    }
    // Event listener for the "Apply Filters" button
    const applyFiltersButton = document.getElementById('apply-user-filters-button');
    if (applyFiltersButton) {
        applyFiltersButton.addEventListener('click', applyUserFilters);
    }

    // Event listener for the user edit form
    const userEditForm = document.getElementById('user-edit-form');
    if (userEditForm) {
        userEditForm.addEventListener('submit', handleUserEditFormSubmit);
    }
    const cancelUserEditButton = document.getElementById('cancel-user-edit-button');
    if (cancelUserEditButton) {
        cancelUserEditButton.addEventListener('click', () => closeAdminModal('user-edit-modal'));
    }

    // Toggle B2B fields in modal based on role selection
    const roleSelectModal = document.getElementById('edit-user-role');
    if (roleSelectModal) {
        roleSelectModal.addEventListener('change', toggleB2BFieldsInModal);
    }
}

/**
 * Loads the list of users from the API and displays them in the admin table.
 * @param {object} [filters={}] - An object containing filter parameters.
 */
async function loadAdminUsersList(filters = {}) {
    const tableBody = document.getElementById('users-table-body');
    if (!tableBody) return;
    
    const loadingRow = tableBody.insertRow();
    const loadingCell = loadingRow.insertCell();
    loadingCell.colSpan = 8; // Adjusted colspan
    loadingCell.className = "text-center py-4";
    loadingCell.textContent = t('admin.users.loading'); // XSS: translated text
    tableBody.innerHTML = ''; // Clear after creating, then replace
    tableBody.appendChild(loadingRow);


    try {
        const users = await adminApi.getUsers(filters); // adminApi.getUsers should handle query param stringification
        tableBody.innerHTML = ''; // Clear loading message

        if (!users || users.length === 0) {
            const emptyRow = tableBody.insertRow();
            const cell = emptyRow.insertCell();
            cell.colSpan = 8; // Adjusted colspan
            cell.className = "text-center py-4";
            cell.textContent = "Aucun utilisateur trouvé."; // XSS: static text
            return;
        }
        
        users.forEach(user => {
            const row = tableBody.insertRow();
            
            row.insertCell().textContent = user.id; // XSS
            row.insertCell().textContent = user.email; // XSS
            
            const nameCell = row.insertCell();
            nameCell.textContent = `${user.first_name || ''} ${user.last_name || ''}`.trim() || '-'; // XSS

            row.insertCell().textContent = user.role ? t(`admin.users.filter.role_${user.role.replace('b2b_', 'b2b_')}`) || user.role : '-'; // XSS: translated text or role value
            
            const activeCell = row.insertCell();
            const activeSpan = document.createElement('span');
            activeSpan.textContent = user.is_active ? t('admin.users.filter.active_true') : t('admin.users.filter.active_false'); // XSS
            activeSpan.className = user.is_active ? 'text-green-600 font-semibold' : 'text-red-600';
            activeCell.appendChild(activeSpan);

            const verifiedCell = row.insertCell();
            const verifiedSpan = document.createElement('span');
            verifiedSpan.textContent = user.is_verified ? t('admin.users.modal.active_yes') : t('admin.users.modal.active_no'); // XSS
            verifiedSpan.className = user.is_verified ? 'text-green-600' : 'text-gray-500';
            verifiedCell.appendChild(verifiedSpan);

            const b2bStatusCell = row.insertCell();
            b2bStatusCell.textContent = user.role === 'b2b_professional' ? (user.professional_status ? t(`admin.users.modal.status_${user.professional_status}`) || user.professional_status : t('admin.users.modal.status_pending')) : '-'; // XSS

            const actionsCell = row.insertCell();
            actionsCell.className = "px-6 py-3";
            const editButton = document.createElement('button');
            editButton.textContent = "Éditer"; // XSS: static text
            editButton.className = "btn-admin-secondary text-xs p-1.5";
            editButton.onclick = () => openUserEditModal(user.id);
            actionsCell.appendChild(editButton);
        });
    } catch (error) {
        tableBody.innerHTML = ''; // Clear loading
        const errorRow = tableBody.insertRow();
        const errorCell = errorRow.insertCell();
        errorCell.colSpan = 8; // Adjusted colspan
        errorCell.className = "text-center py-4 text-red-600";
        errorCell.textContent = "Erreur de chargement des utilisateurs."; // XSS: static text
    }
}

/**
 * Applies filters from the UI and reloads the users list.
 */
function applyUserFilters() {
    const role = document.getElementById('filter-user-role').value;
    const isActive = document.getElementById('filter-user-is-active').value;
    const search = document.getElementById('search-user-email').value;
    const filters = {};
    if (role) filters.role = role;
    if (isActive !== "") filters.is_active = isActive; // Send 'true' or 'false' as strings
    if (search) filters.search = search;
    loadAdminUsersList(filters);
}


/**
 * Opens the modal and populates it with user details for editing.
 * @param {number} userId - The ID of the user to edit.
 */
async function openUserEditModal(userId) {
    try {
        showAdminToast("Chargement des détails utilisateur...", "info");
        const response = await adminApi.getUserDetail(userId); // adminApi.getUserDetail from admin_api.js
        const userDetails = response.user;

        if (userDetails) {
            document.getElementById('edit-user-id').value = userDetails.id;
            document.getElementById('user-edit-modal-title').textContent = `Modifier Utilisateur: ${userDetails.email}`; // XSS
            document.getElementById('edit-user-first-name').value = userDetails.first_name || '';
            document.getElementById('edit-user-last-name').value = userDetails.last_name || '';
            document.getElementById('edit-user-email').value = userDetails.email || '';
            document.getElementById('edit-user-role').value = userDetails.role || 'b2c_customer';
            document.getElementById('edit-user-is-active').value = userDetails.is_active ? 'true' : 'false';
            document.getElementById('edit-user-is-verified').value = userDetails.is_verified ? 'true' : 'false';

            // B2B Fields
            document.getElementById('edit-user-company-name').value = userDetails.company_name || '';
            document.getElementById('edit-user-vat-number').value = userDetails.vat_number || '';
            document.getElementById('edit-user-siret-number').value = userDetails.siret_number || '';
            document.getElementById('edit-user-professional-status').value = userDetails.professional_status || 'pending';
            
            toggleB2BFieldsInModal(); // Show/hide B2B fields based on current role
            openAdminModal('user-edit-modal');
        } else {
            showAdminToast(response.message || "Détails utilisateur non trouvés.", "error");
        }
    } catch (error) {
        // Error toast shown by adminApiRequest or admin_ui.js
        console.error(`Erreur vue détails utilisateur ${userId}:`, error);
    }
}

/**
 * Toggles the visibility of B2B specific fields in the user edit modal.
 */
function toggleB2BFieldsInModal() {
    const roleSelect = document.getElementById('edit-user-role');
    const b2bFieldsDiv = document.querySelector('#user-edit-modal .b2b-fields');
    if (roleSelect && b2bFieldsDiv) {
        if (roleSelect.value === 'b2b_professional') {
            b2bFieldsDiv.classList.remove('hidden');
        } else {
            b2bFieldsDiv.classList.add('hidden');
        }
    }
}

/**
 * Handles the submission of the user edit form.
 * @param {Event} event - The form submission event.
 */
async function handleUserEditFormSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const userId = form.querySelector('#edit-user-id').value;
    
    const userData = {
        first_name: form.querySelector('#edit-user-first-name').value,
        last_name: form.querySelector('#edit-user-last-name').value,
        role: form.querySelector('#edit-user-role').value,
        is_active: form.querySelector('#edit-user-is-active').value === 'true',
        is_verified: form.querySelector('#edit-user-is-verified').value === 'true',
    };

    if (userData.role === 'b2b_professional') {
        userData.company_name = form.querySelector('#edit-user-company-name').value;
        userData.vat_number = form.querySelector('#edit-user-vat-number').value;
        userData.siret_number = form.querySelector('#edit-user-siret-number').value;
        userData.professional_status = form.querySelector('#edit-user-professional-status').value;
    }

    const saveButton = form.querySelector('#save-user-changes-button');
    saveButton.disabled = true;
    saveButton.textContent = "Enregistrement...";

    try {
        const response = await adminApi.updateUser(userId, userData);
        if (response.success) {
            showAdminToast(response.message || "Utilisateur mis à jour avec succès!", "success");
            closeAdminModal('user-edit-modal');
            loadAdminUsersList(); // Refresh the list
        } else {
            showAdminToast(response.message || "Échec de la mise à jour de l'utilisateur.", "error");
        }
    } catch (error) {
        // Error toast handled by adminApiRequest
        console.error(`Erreur mise à jour utilisateur ${userId}:`, error);
    } finally {
        saveButton.disabled = false;
        saveButton.textContent = "Enregistrer Modifications";
    }
}


// Initialize when DOM is ready (if not called by admin_main.js)
// document.addEventListener('DOMContentLoaded', initializeUserManagement);
