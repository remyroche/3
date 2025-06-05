he Admin Panel.

document.addEventListener('DOMContentLoaded', () => {
    if (document.body.id !== 'page-admin-manage-users') return;
    initializeUserManagement();
});


function initializeUserManagement() {
    loadAdminUsersList(); // Load initial list

    // Modal close button
    const closeModalButton = document.getElementById('close-user-edit-modal-button');
    if(closeModalButton) {
        closeModalButton.addEventListener('click', () => closeAdminModal('user-edit-modal'));
    }

    // Filters
    const applyFiltersButton = document.getElementById('apply-user-filters-button');
    if (applyFiltersButton) {
        applyFiltersButton.addEventListener('click', applyUserFilters);
    }
    const resetFiltersButton = document.getElementById('reset-user-filters-button');
    if (resetFiltersButton) {
        resetFiltersButton.addEventListener('click', resetUserFiltersAndLoad);
    }


    // User Edit Form
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
    console.log("User management initialized.");
}

/**
 * Loads the list of users from the API and displays them in the admin table.
 * @param {object} [filters={}] - An object containing filter parameters.
 * @param {number} [page=1] - The page number to fetch.
 */
async function loadAdminUsersList(filters = {}, page = 1) {
    const tableBody = document.getElementById('users-table-body');
    const paginationControls = document.getElementById('user-pagination-controls');
    if (!tableBody || !paginationControls) {
        console.error("User table body or pagination controls not found.");
        return;
    }

    tableBody.innerHTML = `<tr><td colspan="9" class="text-center py-4">${t('admin.users.loading', 'Chargement des utilisateurs...')}</td></tr>`;
    paginationControls.innerHTML = '';


    try {
        // Add pagination parameters to filters
        filters.page = page;
        filters.per_page = 15; // Or a configurable value

        const response = await adminApi.getUsers(filters); // adminApi.getUsers should handle query param stringification
        const users = response.users;
        const pagination = response.pagination; // Expecting pagination info from backend

        tableBody.innerHTML = ''; // Clear loading message

        if (!users || users.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="9" class="text-center py-4">${t('admin.users.table.no_users_found', 'Aucun utilisateur trouvé.')}</td></tr>`;
            return;
        }

        users.forEach(user => {
            const row = tableBody.insertRow();
            row.insertCell().textContent = user.id;
            row.insertCell().textContent = user.email;

            const nameCell = row.insertCell();
            nameCell.textContent = `${user.first_name || ''} ${user.last_name || ''}`.trim() || '-';

            row.insertCell().textContent = user.role ? t(`admin.users.filter.role_${user.role.replace('-', '_')}`, user.role) : '-';
            
            const b2bTierCell = row.insertCell();
            b2bTierCell.textContent = (user.role === 'b2b_professional' && user.b2b_tier) ? t(`admin.users.modal.b2b_tier_${user.b2b_tier}`, user.b2b_tier) : '-';


            const activeCell = row.insertCell();
            activeCell.innerHTML = `<span class="status-indicator ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? t('admin.users.filter.active_true', 'Actif') : t('admin.users.filter.active_false', 'Inactif')}</span>`;

            const verifiedCell = row.insertCell();
            verifiedCell.innerHTML = `<span class="status-indicator ${user.is_verified ? 'verified' : 'unverified'}">${user.is_verified ? t('admin.users.modal.active_yes', 'Oui') : t('admin.users.modal.active_no', 'Non')}</span>`;
            
            const b2bStatusCell = row.insertCell();
            b2bStatusCell.textContent = user.role === 'b2b_professional' ? (user.professional_status ? t(`admin.users.modal.status_${user.professional_status.replace('-', '_')}`, user.professional_status) : t('admin.users.modal.status_pending', 'En attente')) : '-';


            const actionsCell = row.insertCell();
            actionsCell.className = "text-right actions"; 
            const editButton = document.createElement('button');
            editButton.innerHTML = `<i class="fas fa-edit mr-1"></i> ${t('common.edit', 'Éditer')}`;
            editButton.className = "btn btn-admin-secondary btn-sm";
            editButton.onclick = () => openUserEditModal(user.id);
            actionsCell.appendChild(editButton);
        });

        renderPagination(paginationControls, pagination, (newPage) => loadAdminUsersList(filters, newPage));

    } catch (error) {
        console.error('Error loading users list:', error);
        tableBody.innerHTML = `<tr><td colspan="9" class="text-center py-4 text-red-600">${t('admin.users.table.load_error', 'Erreur de chargement des utilisateurs.')}</td></tr>`;
        if(typeof showAdminToast === 'function') showAdminToast(t('admin.users.toast.load_failed', 'Erreur chargement utilisateurs.'), 'error');
    }
}

function renderPagination(container, paginationData, pageChangeCallback) {
    if (!container || !paginationData || paginationData.total_pages <= 1) {
        if(container) container.innerHTML = '';
        return;
    }

    let html = '<div class="pagination-controls space-x-1">';
    html += `<button class="btn btn-admin-secondary btn-sm ${paginationData.current_page === 1 ? 'opacity-50 cursor-not-allowed' : ''}" 
                     onclick="if(${paginationData.current_page !== 1}) pageChangeCallback(${paginationData.current_page - 1})"
                     ${paginationData.current_page === 1 ? 'disabled' : ''}>
                     <i class="fas fa-chevron-left"></i>
             </button>`;

    const maxPagesToShow = 5;
    let startPage = Math.max(1, paginationData.current_page - Math.floor(maxPagesToShow / 2));
    let endPage = Math.min(paginationData.total_pages, startPage + maxPagesToShow - 1);
    if (endPage - startPage + 1 < maxPagesToShow && startPage > 1) {
        startPage = Math.max(1, endPage - maxPagesToShow + 1);
    }

    if (startPage > 1) {
        html += `<button class="btn btn-admin-outline-gold btn-sm" onclick="pageChangeCallback(1)">1</button>`;
        if (startPage > 2) html += `<span class="px-2 py-1">...</span>`;
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="btn btn-sm ${i === paginationData.current_page ? 'btn-admin-primary' : 'btn-admin-outline-gold'}" 
                         onclick="if(${i !== paginationData.current_page}) pageChangeCallback(${i})"
                         ${i === paginationData.current_page ? 'disabled' : ''}>
                         ${i}
                 </button>`;
    }

    if (endPage < paginationData.total_pages) {
        if (endPage < paginationData.total_pages - 1) html += `<span class="px-2 py-1">...</span>`;
        html += `<button class="btn btn-admin-outline-gold btn-sm" onclick="pageChangeCallback(${paginationData.total_pages})">${paginationData.total_pages}</button>`;
    }

    html += `<button class="btn btn-admin-secondary btn-sm ${paginationData.current_page === paginationData.total_pages ? 'opacity-50 cursor-not-allowed' : ''}" 
                     onclick="if(${paginationData.current_page !== paginationData.total_pages}) pageChangeCallback(${paginationData.current_page + 1})"
                     ${paginationData.current_page === paginationData.total_pages ? 'disabled' : ''}>
                     <i class="fas fa-chevron-right"></i>
             </button>`;
    html += '</div>';
    container.innerHTML = html;
    window.pageChangeCallback = pageChangeCallback;
}


function applyUserFilters() {
    const role = document.getElementById('filter-user-role').value;
    const isActive = document.getElementById('filter-user-is-active').value;
    const professionalStatus = document.getElementById('filter-user-professional-status').value;
    const search = document.getElementById('search-user-email').value.trim();

    const filters = {};
    if (role) filters.role = role;
    if (isActive !== "") filters.is_active = isActive;
    if (professionalStatus) filters.professional_status = professionalStatus;
    if (search) filters.search = search;

    loadAdminUsersList(filters, 1);
}

function resetUserFiltersAndLoad() {
    document.getElementById('filter-user-role').value = '';
    document.getElementById('filter-user-is-active').value = '';
    document.getElementById('filter-user-professional-status').value = '';
    document.getElementById('search-user-email').value = '';
    loadAdminUsersList({}, 1); 
}


async function openUserEditModal(userId) {
    try {
        if(typeof showAdminToast === 'function') showAdminToast(t('admin.users.toast.loading_details', 'Chargement des détails...'), "info");
        const response = await adminApi.getUserDetail(userId); // From admin_api.js
        const userDetails = response.user;

        if (userDetails) {
            document.getElementById('edit-user-id').value = userDetails.id;
            document.getElementById('user-edit-modal-title').textContent = `${t('admin.users.modal.title', 'Modifier Utilisateur')}: ${userDetails.email}`;
            document.getElementById('edit-user-first-name').value = userDetails.first_name || '';
            document.getElementById('edit-user-last-name').value = userDetails.last_name || '';
            document.getElementById('edit-user-email').value = userDetails.email || '';
            document.getElementById('edit-user-email').readOnly = true; 
            document.getElementById('edit-user-role').value = userDetails.role || 'b2c_customer';
            document.getElementById('edit-user-is-active').value = userDetails.is_active ? 'true' : 'false';
            document.getElementById('edit-user-is-verified').value = userDetails.is_verified ? 'true' : 'false';

            // Newsletter fields
            document.getElementById('edit-user-newsletter-b2c').checked = userDetails.newsletter_b2c_opt_in || false;
            document.getElementById('edit-user-newsletter-b2b').checked = userDetails.newsletter_b2b_opt_in || false;


            // B2B Fields
            document.getElementById('edit-user-company-name').value = userDetails.company_name || '';
            document.getElementById('edit-user-vat-number').value = userDetails.vat_number || '';
            document.getElementById('edit-user-siret-number').value = userDetails.siret_number || '';
            document.getElementById('edit-user-professional-status').value = userDetails.professional_status || 'pending_review';
            
            const b2bTierSelect = document.getElementById('edit-user-b2b-tier');
            if (b2bTierSelect) {
                b2bTierSelect.value = userDetails.b2b_tier || 'standard'; 
            }

            const documentsListEl = document.getElementById('user-documents-list');
            if (documentsListEl) {
                documentsListEl.innerHTML = ''; 
                if (userDetails.professional_documents && userDetails.professional_documents.length > 0) {
                    const ul = document.createElement('ul');
                    ul.className = 'list-disc pl-5';
                    userDetails.professional_documents.forEach(doc => {
                        const li = document.createElement('li');
                        let docText = `${doc.document_type} (${t('admin.users.doc_status.'+doc.status, doc.status)}) - ${doc.upload_date}`;
                        if (doc.download_url) {
                            li.innerHTML = `<a href="${doc.download_url}" target="_blank" class="text-indigo-600 hover:underline">${docText} <i class="fas fa-download fa-xs"></i></a>`;
                        } else {
                            li.textContent = docText;
                        }
                        ul.appendChild(li);
                    });
                    documentsListEl.appendChild(ul);
                } else {
                    documentsListEl.innerHTML = `<p class="italic text-mt-warm-taupe">${t('admin.users.no_documents_submitted', 'Aucun document soumis.')}</p>`;
                }
            }


            toggleB2BFieldsInModal();
            if(typeof openAdminModal === 'function') openAdminModal('user-edit-modal');
        } else {
            if(typeof showAdminToast === 'function') showAdminToast(response.message || t('admin.users.toast.details_not_found', "Détails utilisateur non trouvés."), "error");
        }
    } catch (error) {
        console.error(`Error fetching user details for ID ${userId}:`, error);
        if(typeof showAdminToast === 'function') showAdminToast(t('admin.users.toast.load_details_error', 'Erreur chargement détails utilisateur.'), 'error');
    }
}

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

async function handleUserEditFormSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const userId = form.querySelector('#edit-user-id').value;
    
    const userData = {
        first_name: form.querySelector('#edit-user-first-name').value.trim(),
        last_name: form.querySelector('#edit-user-last-name').value.trim(),
        role: form.querySelector('#edit-user-role').value,
        is_active: form.querySelector('#edit-user-is-active').value === 'true',
        is_verified: form.querySelector('#edit-user-is-verified').value === 'true',
        newsletter_b2c_opt_in: form.querySelector('#edit-user-newsletter-b2c').checked, // Get checkbox state
        newsletter_b2b_opt_in: form.querySelector('#edit-user-newsletter-b2b').checked  // Get checkbox state
    };

    if (userData.role === 'b2b_professional') {
        userData.company_name = form.querySelector('#edit-user-company-name').value.trim();
        userData.vat_number = form.querySelector('#edit-user-vat-number').value.trim();
        userData.siret_number = form.querySelector('#edit-user-siret-number').value.trim();
        userData.professional_status = form.querySelector('#edit-user-professional-status').value;
        userData.b2b_tier = form.querySelector('#edit-user-b2b-tier').value;
    } else {
        userData.company_name = null;
        userData.vat_number = null;
        userData.siret_number = null;
        userData.professional_status = null;
        userData.b2b_tier = null;
        // userData.newsletter_b2b_opt_in = false; // Optionally ensure B2B newsletter is off if not a B2B role
    }

    const saveButton = form.querySelector('#save-user-changes-button');
    const originalButtonText = saveButton.textContent;
    saveButton.disabled = true;
    saveButton.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> ${t('common.saving', 'Enregistrement...')}`;


    try {
        const response = await adminApi.updateUser(userId, userData); // from admin_api.js
        if (response.success) {
            if(typeof showAdminToast === 'function') showAdminToast(response.message || t('admin.users.toast.update_success', "Utilisateur mis à jour !"), "success");
            if(typeof closeAdminModal === 'function') closeAdminModal('user-edit-modal');
            const currentFilters = getCurrentFilters(); 
            loadAdminUsersList(currentFilters, currentFilters.page || 1);
        } else {
             if(typeof showAdminToast === 'function') showAdminToast(response.message || t('admin.users.toast.update_failed', "Échec MAJ utilisateur."), "error");
        }
    } catch (error) {
        console.error(`Error updating user ${userId}:`, error);
        if(typeof showAdminToast === 'function' && error.data && error.data.message) {
            showAdminToast(error.data.message, "error");
        } else if(typeof showAdminToast === 'function') {
            showAdminToast(t('admin.users.toast.update_failed_server', 'Erreur serveur lors de la MAJ.'), 'error');
        }
    } finally {
        saveButton.disabled = false;
        saveButton.textContent = originalButtonText;
    }
}

function getCurrentFilters() {
    const role = document.getElementById('filter-user-role').value;
    const isActive = document.getElementById('filter-user-is-active').value;
    const professionalStatus = document.getElementById('filter-user-professional-status').value;
    const search = document.getElementById('search-user-email').value.trim();
    const paginationControls = document.getElementById('user-pagination-controls');
    const currentPageButton = paginationControls.querySelector('button.btn-admin-primary');
    const currentPage = currentPageButton ? parseInt(currentPageButton.textContent) : 1;


    const filters = {};
    if (role) filters.role = role;
    if (isActive !== "") filters.is_active = isActive;
    if (professionalStatus) filters.professional_status = professionalStatus;
    if (search) filters.search = search;
    filters.page = currentPage;

    return filters;
}
