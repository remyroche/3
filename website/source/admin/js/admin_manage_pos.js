// website/admin/js/admin_manage_pos.js
document.addEventListener('DOMContentLoaded', () => {
    if (document.body.id !== 'page-admin-manage-pos') return;
    initializePOManagement();
});

let currentAdminPOsCache = [];

function initializePOManagement() {
    loadAdminPurchaseOrders(); // Initial load

    const applyFiltersBtn = document.getElementById('apply-po-filters-button');
    if (applyFiltersBtn) applyFiltersBtn.addEventListener('click', applyPOFilters);
    
    const resetFiltersBtn = document.getElementById('reset-po-filters-button');
    if (resetFiltersBtn) resetFiltersBtn.addEventListener('click', resetPOFiltersAndLoad);

    const closeModalBtn = document.getElementById('close-po-detail-modal-button');
    if (closeModalBtn) closeModalBtn.addEventListener('click', () => closeAdminModal('po-detail-modal'));

    const poUpdateForm = document.getElementById('po-update-form');
    if (poUpdateForm) poUpdateForm.addEventListener('submit', handleUpdatePOOrderStatus);
    
    const generateInvoiceBtn = document.getElementById('generate-b2b-invoice-from-po-button');
    if(generateInvoiceBtn) generateInvoiceBtn.addEventListener('click', handleGenerateInvoiceFromPO);


    console.log("B2B Purchase Order management initialized.");
}

async function loadAdminPurchaseOrders(filters = {}, page = 1) {
    const tableBody = document.getElementById('pos-table-body');
    const paginationControls = document.getElementById('po-pagination-controls');
    if (!tableBody || !paginationControls) return;

    tableBody.innerHTML = `<tr><td colspan="7" class="text-center py-4">${t('admin.pos.loading', 'Chargement des POs...')}</td></tr>`;
    paginationControls.innerHTML = '';
    
    filters.page = page;
    filters.per_page = 15;
    filters.is_b2b_order = true; // Always filter for B2B orders
    filters.has_po_reference = true; // Filter for orders that originated from a PO

    try {
        // Use the existing adminApi.getOrders endpoint, but filter for B2B orders with POs
        const response = await adminApi.getOrders(filters);
        currentAdminPOsCache = response.orders || []; // Orders that are B2B and have POs
        const pagination = response.pagination;

        tableBody.innerHTML = '';
        if (currentAdminPOsCache.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="7" class="text-center py-4">${t('admin.pos.no_pos_found', 'Aucun bon de commande trouvé.')}</td></tr>`;
            return;
        }

        currentAdminPOsCache.forEach(order => {
            const row = tableBody.insertRow();
            row.insertCell().textContent = order.order_id; // Internal Order ID
            
            const clientCell = row.insertCell();
            clientCell.innerHTML = `${sanitizeHTML(order.customer_company_name || 'N/A')} <br><small class="text-gray-500">${sanitizeHTML(order.customer_email)}</small>`;
            
            row.insertCell().textContent = order.purchase_order_reference || 'N/A'; // PO Ref from Client
            row.insertCell().textContent = order.order_date ? formatDateTimeForDisplay(order.order_date) : 'N/A'; // Using order_date as submission date
            
            const totalCell = row.insertCell();
            totalCell.classList.add('text-right');
            totalCell.textContent = `€${parseFloat(order.total_amount || 0).toFixed(2)}`;
            
            const statusCell = row.insertCell();
            statusCell.innerHTML = `<span class="status-indicator status-order-${order.status || 'unknown'}">${t('admin.orders.status.' + (order.status || 'unknown'), order.status || 'Unknown')}</span>`;

            const actionsCell = row.insertCell();
            actionsCell.className = 'text-right actions';
            const viewButton = document.createElement('button');
            viewButton.innerHTML = `<i class="fas fa-eye mr-1"></i> ${t('common.view_details', 'Détails')}`;
            viewButton.className = 'btn btn-admin-secondary btn-sm';
            viewButton.onclick = () => openPODetailModal(order.order_id); // order.order_id is the internal ID
            actionsCell.appendChild(viewButton);
        });
        
        renderPagination(paginationControls, pagination, (newPage) => loadAdminPurchaseOrders(filters, newPage));


    } catch (error) {
        console.error('Error loading B2B Purchase Orders:', error);
        tableBody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-red-500">${t('admin.pos.load_error', 'Erreur chargement POs.')}</td></tr>`;
        if(typeof showAdminToast === 'function') showAdminToast(t('admin.pos.toast.load_failed', 'Erreur chargement POs.'), 'error');
    }
}

function applyPOFilters() {
    const status = document.getElementById('filter-po-status').value;
    const customer = document.getElementById('filter-po-customer').value.trim();
    const date = document.getElementById('filter-po-date').value;
    const filters = {};
    if (status) filters.status = status; // This filters by Order.status
    if (customer) filters.customer_search = customer; // Search on Order's customer
    if (date) filters.date = date; // Search on Order.order_date
    loadAdminPurchaseOrders(filters, 1);
}

function resetPOFiltersAndLoad() {
    document.getElementById('filter-po-status').value = '';
    document.getElementById('filter-po-customer').value = '';
    document.getElementById('filter-po-date').value = '';
    loadAdminPurchaseOrders({}, 1);
}

// Re-using formatDateTimeForDisplay and sanitizeHTML from admin_manage_quotes.js if they are global
// or copy them here. For brevity, assuming they are available or will be moved to a shared admin_utils.js

async function openPODetailModal(orderId) {
    // Fetch the full order details, which now includes PO info if it's a PO-originated order
    try {
        const response = await adminApi.getOrderDetail(orderId); // Existing endpoint
        const order = response.order;
        if (!order) {
            if(typeof showAdminToast === 'function') showAdminToast(t('admin.pos.toast.not_found', 'Commande PO non trouvée.'), 'error');
            return;
        }

        document.getElementById('modal-po-order-id').textContent = order.id;
        document.getElementById('modal-po-order-id-hidden').value = order.id;
        document.getElementById('modal-po-customer-name').textContent = order.customer_name || 'N/A';
        document.getElementById('modal-po-customer-email').textContent = order.customer_email || 'N/A';
        document.getElementById('modal-po-customer-company').textContent = order.customer_company_name || order.shipping_address?.company_name || 'N/A';
        document.getElementById('modal-po-submission-date').textContent = formatDateTimeForDisplay(order.order_date);
        document.getElementById('modal-po-current-status').textContent = t('admin.orders.status.' + (order.status || 'unknown'), order.status || 'Unknown');
        document.getElementById('modal-po-client-ref').textContent = order.purchase_order_reference || 'N/A';

        const poDownloadLink = document.getElementById('modal-po-download-link');
        if (order.po_file_path_stored) { // Assuming Order model has po_file_path_stored
            // Ensure this URL points to an endpoint that can serve the PO file with auth
            poDownloadLink.href = adminApi.BASE_URL + `/assets/${order.po_file_path_stored}`; // Uses admin serve_asset
            poDownloadLink.classList.remove('hidden');
            poDownloadLink.innerHTML = `<i class="fas fa-download mr-1"></i> ${t('admin.pos.download_po_file', 'Télécharger PO Original')}`;
        } else {
            poDownloadLink.classList.add('hidden');
            poDownloadLink.innerHTML = t('admin.pos.no_po_file_attached', 'Aucun fichier PO joint.');
        }

        const itemsTableBody = document.getElementById('modal-po-items-table-body');
        itemsTableBody.innerHTML = '';
        let estimatedTotalHT = 0;
        if (order.items && order.items.length > 0) {
            order.items.forEach(item => {
                const row = itemsTableBody.insertRow();
                row.insertCell().textContent = `${item.product_name || 'Produit ID: '+item.product_id}`;
                row.insertCell().textContent = item.variant_description || '-';
                row.insertCell().classList.add('text-center');
                row.insertCell().textContent = item.quantity;
                
                const unitPriceCell = row.insertCell();
                unitPriceCell.classList.add('text-right');
                unitPriceCell.textContent = `€${parseFloat(item.unit_price || 0).toFixed(2)}`;
                
                const totalCell = row.insertCell();
                totalCell.classList.add('text-right');
                const lineTotal = parseFloat(item.total_price || 0);
                totalCell.textContent = `€${lineTotal.toFixed(2)}`;
                estimatedTotalHT += lineTotal;
            });
        } else {
            itemsTableBody.innerHTML = `<tr><td colspan="5" class="text-center italic py-2">${t('admin.pos.no_items_in_po_order', 'Aucun article dans cette commande PO.')}</td></tr>`;
        }
        document.getElementById('modal-po-total-ht-estimate').textContent = `€${estimatedTotalHT.toFixed(2)}`;
        document.getElementById('modal-po-new-order-status').value = order.status || 'pending_po_review';
        document.getElementById('modal-po-admin-notes').value = order.notes_internal || '';

        // Show/Hide "Generate Invoice" button
        const generateInvoiceBtn = document.getElementById('generate-b2b-invoice-from-po-button');
        // Allow invoice generation if PO is approved (e.g., status is processing, awaiting_shipment) AND no invoice exists yet
        if (['processing', 'awaiting_shipment', 'shipped', 'delivered', 'completed'].includes(order.status) && !order.invoice_id) {
            generateInvoiceBtn.classList.remove('hidden');
        } else {
            generateInvoiceBtn.classList.add('hidden');
        }


        if(typeof openAdminModal === 'function') openAdminModal('po-detail-modal');

    } catch (error) {
        console.error("Error opening PO Detail Modal:", error);
        if(typeof showAdminToast === 'function') showAdminToast(t('admin.pos.toast.error_opening_modal', 'Erreur ouverture détails PO.'), 'error');
    }
}

async function handleUpdatePOOrderStatus(event) {
    event.preventDefault();
    const form = event.target;
    const orderId = form.querySelector('#modal-po-order-id-hidden').value;
    const newStatus = form.querySelector('#modal-po-new-order-status').value;
    const adminNotes = form.querySelector('#modal-po-admin-notes').value;

    const payload = {
        status: newStatus,
        // No tracking/carrier here as this is for PO review stage, shipping status is separate
    };

    const updateButton = form.querySelector('#update-po-order-status-button');
    const originalButtonText = updateButton.textContent;
    updateButton.disabled = true;
    updateButton.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> ${t('common.saving', 'Enregistrement...')}`;

    try {
        // Use the existing adminApi.updateOrderStatus but this endpoint primarily updates status
        // and might need extension if more PO-specific fields are to be updated.
        const response = await adminApi.updateOrderStatus(orderId, payload);
        if (response.success) {
            if(typeof showAdminToast === 'function') showAdminToast(response.message || t('admin.pos.toast.status_updated', 'Statut commande PO mis à jour.'), 'success');
            
            // If admin notes were provided and the API doesn't handle them with status update, make a separate call
            if (adminNotes && adminNotes.trim() !== "") {
                await adminApi.addOrderNote(orderId, { note: `[PO Review] ${adminNotes}` });
            }

            if(typeof closeAdminModal === 'function') closeAdminModal('po-detail-modal');
            const currentFilters = getCurrentPOFilters();
            loadAdminPurchaseOrders(currentFilters, currentFilters.page || 1);
        } else {
            if(typeof showAdminToast === 'function') showAdminToast(response.message || t('admin.pos.toast.status_update_failed', 'Échec MAJ statut PO.'), 'error');
        }
    } catch (error) {
        console.error(`Error updating PO Order ${orderId} status:`, error);
    } finally {
        updateButton.disabled = false;
        updateButton.innerHTML = originalButtonText;
    }
}

async function handleGenerateInvoiceFromPO() {
    const orderId = document.getElementById('modal-po-order-id-hidden').value;
    if (!orderId) {
        if(typeof showAdminToast === 'function') showAdminToast('Order ID manquant pour la génération de facture.', 'error');
        return;
    }

    if(typeof showAdminConfirm !== 'function') {
        alert("Confirmation dialog function not found.");
        return;
    }

    showAdminConfirm(
        'Confirmer Génération Facture B2B',
        `Êtes-vous sûr de vouloir générer une facture B2B pour la commande #${orderId} ? Ceci est basé sur les informations actuelles de la commande.`,
        async () => {
            const generateBtn = document.getElementById('generate-b2b-invoice-from-po-button');
            const originalBtnText = generateBtn.textContent;
            generateBtn.disabled = true;
            generateBtn.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> Génération...`;

            try {
                // This new API endpoint will trigger InvoiceService.create_invoice_from_order(orderId, is_b2b_order=True)
                const response = await adminApi.generateB2BInvoiceForOrder(orderId);
                if(response.success) {
                    showAdminToast(response.message || `Facture B2B ${response.invoice_number || ''} générée pour la commande ${orderId}.`, 'success');
                    openPODetailModal(orderId); // Refresh modal to show invoice info or hide button
                } else {
                    showAdminToast(response.message || 'Échec de la génération de la facture B2B.', 'error');
                }
            } catch (error) {
                console.error("Error generating B2B invoice from PO:", error);
                showAdminToast(error.data?.message || 'Erreur serveur lors de la génération de facture.', 'error');
            } finally {
                generateBtn.disabled = false;
                generateBtn.innerHTML = originalBtnText;
            }
        },
        'Générer Facture',
        'Annuler'
    );
}


function getCurrentPOFilters() {
    const status = document.getElementById('filter-po-status').value;
    const customer = document.getElementById('filter-po-customer').value.trim();
    const date = document.getElementById('filter-po-date').value;
    const paginationControls = document.getElementById('po-pagination-controls');
    const currentPageButton = paginationControls.querySelector('button.btn-admin-primary');
    const currentPage = currentPageButton ? parseInt(currentPageButton.textContent) : 1;

    const filters = {};
    if (status) filters.status = status;
    if (customer) filters.customer_search = customer; // Backend getOrders uses 'search' for this
    if (date) filters.date = date;
    filters.page = currentPage;
    return filters;
}

// Add translation keys for admin.pos.*, common.view_details, etc.
// Translation keys like 'admin.orders.status.pending_po_review' for display.
