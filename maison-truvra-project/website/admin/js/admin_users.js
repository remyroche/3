// website/admin/js/admin_users.js
// Logic for managing users in the Admin Panel.

/**
 * Initializes user management functionalities:
 * - Loads the list of users.
 * - Sets up event listener for closing the user detail modal.
 */
function initializeUserManagement() {
    loadAdminUsersList();
    const closeModalButton = document.getElementById('close-user-detail-modal-button'); // Ensure this ID exists in admin_manage_users.html
    if(closeModalButton) {
        closeModalButton.addEventListener('click', () => closeAdminModal('user-detail-modal')); // Assumes closeAdminModal from admin_ui.js
    }
}

/**
 * Loads the list of users from the API and displays them in the admin table.
 */
async function loadAdminUsersList() {
    const tableBody = document.getElementById('users-table-body');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4">Chargement des utilisateurs...</td></tr>';

    try {
        // adminApiRequest is from admin_api.js
        const users = await adminApiRequest('/users'); 
        if (users.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4">Aucun utilisateur trouvé.</td></tr>';
            return;
        }
        
        let rowsHtml = '';
        users.forEach(user => {
            rowsHtml += `
                <tr>
                    <td class="px-6 py-3 text-xs">${user.id}</td>
                    <td class="px-6 py-3">${user.email}</td>
                    <td class="px-6 py-3">${user.nom || '-'}</td>
                    <td class="px-6 py-3">${user.prenom || '-'}</td>
                    <td class="px-6 py-3">${user.is_admin ? '<span class="font-semibold text-brand-classic-gold">Oui</span>' : 'Non'}</td>
                    <td class="px-6 py-3 text-xs">${new Date(user.created_at).toLocaleDateString('fr-FR')}</td>
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

/**
 * Fetches and displays detailed information for a specific user in a modal.
 * @param {number} userId - The ID of the user to view.
 */
async function viewUserDetails(userId) {
    try {
        showAdminToast("Chargement des détails utilisateur...", "info"); // Assumes showAdminToast from admin_ui.js
        // adminApiRequest is from admin_api.js
        const userDetails = await adminApiRequest(`/users/${userId}`); 
        if (userDetails) {
            document.getElementById('detail-user-id').textContent = userDetails.id;
            document.getElementById('detail-user-email').textContent = userDetails.email;
            document.getElementById('detail-user-nom').textContent = userDetails.nom || '-';
            document.getElementById('detail-user-prenom').textContent = userDetails.prenom || '-';
            document.getElementById('detail-user-isadmin').textContent = userDetails.is_admin ? 'Oui' : 'Non';
            document.getElementById('detail-user-createdat').textContent = new Date(userDetails.created_at).toLocaleString('fr-FR');
            
            const ordersList = document.getElementById('detail-user-orders'); // Ensure this ul exists in the modal
            ordersList.innerHTML = ''; // Clear previous
            if (userDetails.orders && userDetails.orders.length > 0) {
                userDetails.orders.forEach(order => {
                    const li = document.createElement('li');
                    li.className = 'text-xs py-1 border-b border-brand-cream last:border-b-0';
                    li.textContent = `Cmd #${order.order_id} - ${parseFloat(order.total_amount).toFixed(2)}€ - Statut: ${order.status} (${new Date(order.order_date).toLocaleDateString('fr-FR')})`;
                    ordersList.appendChild(li);
                });
            } else {
                ordersList.innerHTML = '<li class="text-brand-warm-taupe italic text-xs">Aucune commande pour cet utilisateur.</li>';
            }

            openAdminModal('user-detail-modal'); // Assumes openAdminModal from admin_ui.js
        }
    } catch (error) {
        // Error toast shown by adminApiRequest
        console.error(`Erreur vue détails utilisateur ${userId}:`, error);
    }
}
