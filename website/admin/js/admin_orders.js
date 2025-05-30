// website/admin/js/admin_orders.js
// Logic for managing orders in the Admin Panel.

let currentOrders = []; // Cache for fetched orders, useful for client-side interactions if needed

/**
 * Initializes order management functionalities:
 * - Loads initial orders.
 * - Sets up event listeners for filters and modal interactions.
 */
function initializeOrderManagement() {
    loadAdminOrders(); // Initial load of all orders

    const filterButton = document.getElementById('apply-order-filters-button');
    if (filterButton) filterButton.addEventListener('click', applyOrderFilters);

    const closeModalButton = document.getElementById('close-order-detail-modal-button'); // Ensure ID exists in admin_manage_orders.html
    if (closeModalButton) {
        closeModalButton.addEventListener('click', () => closeAdminModal('order-detail-modal')); // Assumes closeAdminModal from admin_ui.js
    }
    
    const updateStatusForm = document.getElementById('update-order-status-form');
    if (updateStatusForm) updateStatusForm.addEventListener('submit', handleUpdateOrderStatus);

    const addNoteForm = document.getElementById('add-order-note-form');
    if (addNoteForm) addNoteForm.addEventListener('submit', handleAddOrderNote);

    const newStatusSelect = document.getElementById('modal-order-new-status');
    if (newStatusSelect) newStatusSelect.addEventListener('change', toggleShippingInfoFields);
}

/**
 * Loads orders from the API based on filters and displays them.
 * @param {object} [filters={}] - An object containing filter parameters (search, status, date).
 */
async function loadAdminOrders(filters = {}) {
    const tableBody = document.getElementById('orders-table-body');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="6" class="text-center py-4">Chargement des commandes...</td></tr>';

    let queryParams = new URLSearchParams(filters).toString();
    try {
        // adminApiRequest is from admin_api.js
        // Backend needs to support these filters: /api/admin/orders?search=...&status=...&date=...
        currentOrders = await adminApiRequest(`/orders${queryParams ? '?' + queryParams : ''}`);
        displayAdminOrders(currentOrders);
    } catch (error) {
        tableBody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-red-600">Erreur de chargement des commandes.</td></tr>';
    }
}

/**
 * Displays a list of orders in the admin table.
 * @param {Array<object>} orders - The array of order objects to display.
 */
function displayAdminOrders(orders) {
    const tableBody = document.getElementById('orders-table-body');
    tableBody.innerHTML = ''; // Clear previous orders

    if (!orders || orders.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6" class="text-center py-4">Aucune commande trouvée.</td></tr>';
        return;
    }

    orders.forEach(order => {
        const row = `
            <tr>
                <td class="px-6 py-3 text-xs">${order.order_id}</td>
                <td class="px-6 py-3 text-sm">
                    ${order.customer_email} <br> 
                    <span class="text-xs text-brand-warm-taupe">${order.customer_name || ''}</span>
                </td>
                <td class="px-6 py-3 text-xs">${new Date(order.order_date).toLocaleDateString('fr-FR')}</td>
                <td class="px-6 py-3 text-sm">${parseFloat(order.total_amount).toFixed(2)} €</td>
                <td class="px-6 py-3"><span class="px-2 py-1 text-xs font-semibold rounded-full ${getOrderStatusClass(order.status)}">${order.status}</span></td>
                <td class="px-6 py-3">
                    <button onclick="openOrderDetailModal('${order.order_id}')" class="btn-admin-secondary text-xs p-1.5">Détails</button>
                </td>
            </tr>
        `;
        tableBody.insertAdjacentHTML('beforeend', row);
    });
}

/**
 * Applies filters from the UI and reloads the orders list.
 */
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


/**
 * Fetches and displays detailed information for a specific order in a modal.
 * @param {string|number} orderId - The ID of the order to view.
 */
async function openOrderDetailModal(orderId) {
    try {
        showAdminToast("Chargement des détails de la commande...", "info"); // Assumes showAdminToast from admin_ui.js
        // Backend: GET /api/admin/orders/:id
        // adminApiRequest is from admin_api.js
        const order = await adminApiRequest(`/orders/${orderId}`); 
        if (order) {
            document.getElementById('modal-order-id').textContent = order.order_id;
            document.getElementById('update-order-id-hidden').value = order.order_id; // For form submissions
            document.getElementById('modal-order-date').textContent = new Date(order.order_date).toLocaleString('fr-FR');
            document.getElementById('modal-order-customer-email').textContent = order.customer_email;
            document.getElementById('modal-order-customer-name').textContent = order.customer_name || 'Non spécifié';
            document.getElementById('modal-order-current-status').textContent = order.status;
            document.getElementById('modal-order-total-amount').textContent = `${parseFloat(order.total_amount).toFixed(2)} €`;

            // Inside openOrderDetailModal, after fetching order details:
            const notesHistoryEl = document.getElementById('modal-order-notes-history');
            if (notesHistoryEl) {
                notesHistoryEl.innerHTML = ''; // Clear previous notes
                if (order.notes && order.notes.length > 0) {
                    order.notes.forEach(note => {
                        const noteDate = new Date(note.created_at).toLocaleString('fr-FR');
                        const adminUserDisplay = note.admin_user || (note.admin_user_id ? `Admin ID ${note.admin_user_id}` : 'Système');
                        notesHistoryEl.innerHTML += `<p class="text-xs mb-1 p-1 bg-gray-100 rounded"><strong>${noteDate} (${adminUserDisplay}):</strong> ${note.content}</p>`;                    });
                } else {
                    notesHistoryEl.innerHTML = '<p class="italic text-xs text-brand-warm-taupe">Aucune note pour cette commande.</p>';
                }
            }
                        
            const shippingAddressEl = document.getElementById('modal-order-shipping-address');
            if (shippingAddressEl) shippingAddressEl.innerHTML = order.shipping_address ? order.shipping_address.replace(/\n/g, '<br>') : 'Non fournie';
            
            const itemsTableBody = document.getElementById('modal-order-items-table-body'); // Ensure this tbody ID exists
            itemsTableBody.innerHTML = '';
            if (order.items && order.items.length > 0) {
                order.items.forEach(item => {
                    itemsTableBody.innerHTML += `
                        <tr>
                            <td class="p-2 border-b border-brand-cream">${item.product_name}</td>
                            <td class="p-2 border-b border-brand-cream">${item.variant || '-'}</td>
                            <td class="p-2 border-b border-brand-cream text-center">${item.quantity}</td>
                            <td class="p-2 border-b border-brand-cream text-right">${parseFloat(item.price_at_purchase).toFixed(2)} €</td>
                            <td class="p-2 border-b border-brand-cream text-right">${(item.price_at_purchase * item.quantity).toFixed(2)} €</td>
                        </tr>
                    `;
                });
            } else {
                itemsTableBody.innerHTML = '<tr><td colspan="5" class="p-2 text-center italic border-b border-brand-cream">Aucun article dans cette commande.</td></tr>';
            }
            
            document.getElementById('modal-order-new-status').value = order.status;
            toggleShippingInfoFields(); // Show/hide shipping fields based on current/new status

            const notesHistory = document.getElementById('modal-order-notes-history'); // Ensure this ID exists
            notesHistory.innerHTML = '';
            if (order.notes && order.notes.length > 0) {
                 order.notes.forEach(note => {
                    notesHistory.innerHTML += `<p class="mb-1 border-b border-brand-cream pb-1"><strong>${new Date(note.created_at).toLocaleString('fr-FR')} (${note.admin_user || 'Système'}):</strong> ${note.content}</p>`;
                 });
            } else {
                notesHistory.innerHTML = '<p class="italic text-brand-warm-taupe">Aucune note.</p>';
            }

            openAdminModal('order-detail-modal'); // Assumes openAdminModal from admin_ui.js
        }
    } catch (error) {
        console.error(`Erreur ouverture détails commande ${orderId}:`, error);
    }
}

/**
 * Toggles the visibility of shipping information fields based on the selected order status.
 */
function toggleShippingInfoFields() {
    const statusSelect = document.getElementById('modal-order-new-status');
    const shippingFields = document.getElementById('shipping-info-fields'); // Ensure this div ID exists
    if (!statusSelect || !shippingFields) return;

    if (statusSelect.value === 'Shipped' || statusSelect.value === 'Delivered') {
        shippingFields.style.display = 'block';
    } else {
        shippingFields.style.display = 'none';
    }
}

/**
 * Handles the submission of the update order status form.
 * @param {Event} event - The form submission event.
 */
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
        // Only include tracking info if relevant to the status
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
            loadAdminOrders(); // Refresh the orders list
        }
    } catch (error) {
        console.error(`Erreur MAJ statut commande ${orderId}:`, error);
    }
}

/**
 * Handles the submission of the add order note form.
 * @param {Event} event - The form submission event.
 */
async function handleAddOrderNote(event) {
    event.preventDefault();
    const form = event.target;
    const orderId = document.getElementById('update-order-id-hidden').value; // Get orderId from status update form's hidden field
    const noteContentField = form.querySelector('#modal-order-new-note');
    const noteContent = noteContentField.value;

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
            noteContentField.value = ''; // Clear the textarea
            // Refresh notes in the modal by re-fetching and re-opening, or by dynamically adding the note
            if (document.getElementById('order-detail-modal').classList.contains('active')) {
                 openOrderDetailModal(orderId); // Re-open to refresh all details including notes
            }
        }
    } catch (error) {
        console.error(`Erreur ajout note commande ${orderId}:`, error);
    }
}
