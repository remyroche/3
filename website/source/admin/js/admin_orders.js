// website/admin/js/admin_orders.js
// Logic for managing orders in the Admin Panel.

let currentOrders = []; // Cache for fetched orders, useful for client-side interactions if needed

// Assuming t() is globally available from your build process
const currentLocale = document.documentElement.lang || 'fr-FR';

/**
 * Initializes order management functionalities:
 * - Loads initial orders.// website/admin/js/admin_orders.js
// Logic for managing orders in the Admin Panel.

let currentOrders = []; 
const currentLocale = document.documentElement.lang || 'fr-FR';

function initializeOrderManagement() {
    loadAdminOrders(); 

    const filterButton = document.getElementById('apply-order-filters-button');
    if (filterButton) filterButton.addEventListener('click', applyOrderFilters);

    const closeModalButton = document.getElementById('close-order-detail-modal-button'); 
    if (closeModalButton) {
        closeModalButton.addEventListener('click', () => closeAdminModal('order-detail-modal')); 
    }
    
    const updateStatusForm = document.getElementById('update-order-status-form');
    if (updateStatusForm) updateStatusForm.addEventListener('submit', handleUpdateOrderStatus);

    const addNoteForm = document.getElementById('add-order-note-form');
    if (addNoteForm) addNoteForm.addEventListener('submit', handleAddOrderNote);

    const newStatusSelect = document.getElementById('modal-order-new-status');
    if (newStatusSelect) newStatusSelect.addEventListener('change', toggleShippingInfoFields);
}

async function loadAdminOrders(filters = {}) {
    const tableBody = document.getElementById('orders-table-body');
    if (!tableBody) return;
    const loadingRow = tableBody.insertRow();
    const loadingCell = loadingRow.insertCell();
    loadingCell.colSpan = 6;
    loadingCell.className = "text-center py-4";
    loadingCell.textContent = t('admin.orders.table.loading'); // XSS: translated text
    tableBody.innerHTML = ''; // Clear after creating, then replace
    tableBody.appendChild(loadingRow);


    let queryParams = new URLSearchParams(filters).toString();
    try {
        currentOrders = await adminApiRequest(`/orders${queryParams ? '?' + queryParams : ''}`);
        displayAdminOrders(currentOrders);
    } catch (error) {
        tableBody.innerHTML = ''; // Clear loading
        const errorRow = tableBody.insertRow();
        const errorCell = errorRow.insertCell();
        errorCell.colSpan = 6;
        errorCell.className = "text-center py-4 text-red-600";
        errorCell.textContent = t('admin.orders.table.loadError'); // XSS: translated text
    }
}

function displayAdminOrders(orders) {
    const tableBody = document.getElementById('orders-table-body');
    tableBody.innerHTML = ''; 

    if (!orders || orders.length === 0) {
        const emptyRow = tableBody.insertRow();
        const emptyCell = emptyRow.insertCell();
        emptyCell.colSpan = 6;
        emptyCell.className = "text-center py-4";
        emptyCell.textContent = t('admin.orders.table.noOrdersFound'); // XSS: translated text
        return;
    }

    orders.forEach(order => {
        const row = tableBody.insertRow();
        
        row.insertCell().textContent = order.order_id; // XSS
        
        const customerCell = row.insertCell();
        customerCell.className = "px-6 py-3 text-sm";
        customerCell.textContent = order.customer_email; // XSS
        const br = document.createElement('br');
        customerCell.appendChild(br);
        const customerNameSpan = document.createElement('span');
        customerNameSpan.className = "text-xs text-brand-warm-taupe";
        customerNameSpan.textContent = order.customer_name || ''; // XSS
        customerCell.appendChild(customerNameSpan);

        row.insertCell().textContent = new Date(order.order_date).toLocaleDateString(currentLocale); // XSS
        row.insertCell().textContent = `${parseFloat(order.total_amount).toFixed(2)} €`; // XSS
        
        const statusCell = row.insertCell();
        const statusSpan = document.createElement('span');
        statusSpan.className = `px-2 py-1 text-xs font-semibold rounded-full ${getOrderStatusClass(order.status)}`;
        statusSpan.textContent = order.status; // XSS
        statusCell.appendChild(statusSpan);
        
        const actionsCell = row.insertCell();
        const detailsButton = document.createElement('button');
        detailsButton.className = "btn-admin-secondary text-xs p-1.5";
        detailsButton.textContent = t('admin.orders.table.detailsButton'); // XSS
        detailsButton.onclick = () => openOrderDetailModal(order.order_id);
        actionsCell.appendChild(detailsButton);
    });
}

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

async function openOrderDetailModal(orderId) {
    try {
        showAdminToast(t('admin.orders.toast.loadingDetails'), "info"); 
        const order = await adminApiRequest(`/orders/${orderId}`); 
        if (order) {
            document.getElementById('modal-order-id').textContent = order.order_id; // XSS
            document.getElementById('update-order-id-hidden').value = order.order_id;
            document.getElementById('modal-order-date').textContent = new Date(order.order_date).toLocaleString(currentLocale); // XSS
            document.getElementById('modal-order-customer-email').textContent = order.customer_email; // XSS
            document.getElementById('modal-order-customer-name').textContent = order.customer_name || t('admin.orders.modal.notSpecified'); // XSS
            document.getElementById('modal-order-current-status').textContent = order.status; // XSS
            document.getElementById('modal-order-total-amount').textContent = `${parseFloat(order.total_amount).toFixed(2)} €`; // XSS

            const notesHistoryEl = document.getElementById('modal-order-notes-history');
            const naText = t('common.notApplicable');
            if (notesHistoryEl) {
                notesHistoryEl.innerHTML = ''; 
                if (order.notes && order.notes.length > 0) {
                    order.notes.forEach(note => {
                        const p = document.createElement('p');
                        p.className = "text-xs mb-1 p-1 bg-gray-100 rounded";
                        const strong = document.createElement('strong');
                        const noteDate = new Date(note.created_at).toLocaleString(currentLocale);
                        const adminUserDisplay = note.admin_user || (note.admin_user_id ? t('admin.orders.modal.adminIdLabel', {id: note.admin_user_id}) : t('admin.orders.modal.systemUserLabel'));
                        strong.textContent = `${noteDate} (${adminUserDisplay}): `; // XSS
                        p.appendChild(strong);
                        p.append(note.content); // XSS: Note content directly appended, assuming backend sanitizes if notes can contain HTML. If not, this should be p.textContent = strong.textContent + note.content;
                        notesHistoryEl.appendChild(p);
                    });
                } else {
                    const pNoNotes = document.createElement('p');
                    pNoNotes.className = "italic text-xs text-brand-warm-taupe";
                    pNoNotes.textContent = t('admin.orders.modal.noNotes'); // XSS
                    notesHistoryEl.appendChild(pNoNotes);
                }
            }
                        
            const shippingAddressEl = document.getElementById('modal-order-shipping-address'); 
            if (shippingAddressEl) {
                // Assuming address is plain text or pre-sanitized if it could contain HTML.
                // Using textContent for multi-line display might require replacing \n with <br> and setting innerHTML,
                // OR, better, use CSS white-space: pre-wrap with textContent.
                shippingAddressEl.style.whiteSpace = 'pre-wrap';
                shippingAddressEl.textContent = order.shipping_address ? order.shipping_address : t('admin.orders.modal.shippingAddressNotProvided'); // XSS
            }
            
            const itemsTableBody = document.getElementById('modal-order-items-table-body'); 
            itemsTableBody.innerHTML = '';
            if (order.items && order.items.length > 0) {
                order.items.forEach(item => {
                    const row = itemsTableBody.insertRow();
                    let displayItemProductName = item.product_name || naText;
                    if (item.product_name_fr && item.product_name_en) {
                        displayItemProductName = item.product_name_fr.toLowerCase() === item.product_name_en.toLowerCase() ? item.product_name_fr : `${item.product_name_fr} / ${item.product_name_en}`;
                    } else if (item.product_name_fr) { displayItemProductName = item.product_name_fr;
                    } else if (item.product_name_en) { displayItemProductName = item.product_name_en; }
                    
                    row.insertCell().textContent = displayItemProductName; // XSS
                    row.insertCell().textContent = item.variant || '-'; // XSS
                    row.insertCell().textContent = item.quantity; // XSS
                    const unitPriceCell = row.insertCell();
                    unitPriceCell.className = "text-right";
                    unitPriceCell.textContent = `${parseFloat(item.price_at_purchase).toFixed(2)} €`; // XSS
                    const totalPriceCell = row.insertCell();
                    totalPriceCell.className = "text-right";
                    totalPriceCell.textContent = `${(item.price_at_purchase * item.quantity).toFixed(2)} €`; // XSS

                    // Style cells
                    Array.from(row.cells).forEach(cell => {
                        cell.className += " p-2 border-b border-brand-cream";
                        if (cell === row.cells[2]) cell.classList.add("text-center");
                    });
                });
            } else {
                const emptyRow = itemsTableBody.insertRow();
                const cell = emptyRow.insertCell();
                cell.colSpan = 5;
                cell.className = "p-2 text-center italic border-b border-brand-cream";
                cell.textContent = t('admin.orders.modal.noItemsInOrder'); // XSS
            }
            
            document.getElementById('modal-order-new-status').value = order.status;
            toggleShippingInfoFields(); 

            openAdminModal('order-detail-modal'); 
        }
    } catch (error) {
        console.error(t('admin.orders.error.openingDetails', { orderId: orderId }), error);
    }
}

function toggleShippingInfoFields() {
    const statusSelect = document.getElementById('modal-order-new-status');
    const shippingFields = document.getElementById('shipping-info-fields'); 
    if (!statusSelect || !shippingFields) return;

    if (statusSelect.value === 'Shipped' || statusSelect.value === 'Delivered') {
        shippingFields.style.display = 'block';
    } else {
        shippingFields.style.display = 'none';
    }
}

async function handleUpdateOrderStatus(event) {
    event.preventDefault();
    const form = event.target;
    const orderId = form.querySelector('#update-order-id-hidden').value;
    const newStatus = form.querySelector('#modal-order-new-status').value;
    const trackingNumber = form.querySelector('#modal-order-tracking-number').value;
    const carrier = form.querySelector('#modal-order-carrier').value;

    if (!orderId || !newStatus) {
        showAdminToast(t('admin.orders.toast.missingIdOrStatus'), "error");
        return;
    }
    
    const payload = {
        status: newStatus,
        tracking_number: (newStatus === 'Shipped' || newStatus === 'Delivered') ? trackingNumber : null,
        carrier: (newStatus === 'Shipped' || newStatus === 'Delivered') ? carrier : null,
    };

    try {
        showAdminToast(t('admin.orders.toast.updatingStatus'), "info");
        const result = await adminApiRequest(`/orders/${orderId}/status`, 'PUT', payload);
        if (result.success) {
            showAdminToast(result.message || t('admin.orders.toast.statusUpdateSuccess'), "success");
            closeAdminModal('order-detail-modal');
            loadAdminOrders(); 
        } // Error toast handled by adminApiRequest
    } catch (error) {
        console.error(t('admin.orders.error.statusUpdate', { orderId: orderId }), error);
        // Error toast likely already shown by adminApiRequest
    }
}

async function handleAddOrderNote(event) {
    event.preventDefault();
    const form = event.target;
    const orderId = document.getElementById('update-order-id-hidden').value; 
    const noteContentField = form.querySelector('#modal-order-new-note');
    const noteContent = noteContentField.value;

    if (!orderId || !noteContent.trim()) {
        showAdminToast(t('admin.orders.toast.missingNoteContent'), "error");
        return;
    }
    
    try {
        showAdminToast(t('admin.orders.toast.addingNote'), "info");
        const result = await adminApiRequest(`/orders/${orderId}/notes`, 'POST', { note: noteContent });
        if (result.success) {
            showAdminToast(result.message || t('admin.orders.toast.noteAddedSuccess'), "success");
            noteContentField.value = ''; 
            if (document.getElementById('order-detail-modal').classList.contains('active')) { // Check if modal is open before refreshing
                 openOrderDetailModal(orderId); 
            }
        } // Error toast handled by adminApiRequest
    } catch (error) {
        console.error(t('admin.orders.error.addNote', { orderId: orderId }), error);
        // Error toast likely already shown by adminApiRequest
    }
}

// Helper to get status class (styling, not directly user-facing text)
function getOrderStatusClass(status) {
    // This mapping is for Tailwind CSS classes, ensure they exist in your admin_style.css or Tailwind config
    const statusClassMap = {
        'pending_payment': 'bg-yellow-100 text-yellow-800',
        'paid': 'bg-green-100 text-green-800',
        'processing': 'bg-blue-100 text-blue-800',
        'awaiting_shipment': 'bg-indigo-100 text-indigo-800',
        'shipped': 'bg-purple-100 text-purple-800',
        'delivered': 'bg-teal-100 text-teal-800',
        'completed': 'bg-green-200 text-green-900', // Slightly different for completed
        'cancelled': 'bg-red-100 text-red-800',
        'refunded': 'bg-pink-100 text-pink-800',
        'partially_refunded': 'bg-pink-50 text-pink-700',
        'on_hold': 'bg-gray-100 text-gray-800',
        'failed': 'bg-red-200 text-red-900',
        'default': 'bg-gray-200 text-gray-700'
    };
    return statusClassMap[status ? status.toLowerCase() : 'default'] || statusClassMap['default'];
}


// Initialize on DOMContentLoaded if admin_main.js doesn't call initializeOrderManagement
// For now, assuming admin_main.js handles the call.
// document.addEventListener('DOMContentLoaded', initializeOrderManagement);
