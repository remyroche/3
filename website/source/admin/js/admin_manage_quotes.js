// website/admin/js/admin_manage_quotes.js
document.addEventListener('DOMContentLoaded', () => {
    if (document.body.id !== 'page-admin-manage-quotes') return;
    initializeQuoteManagement();
});

let currentAdminQuotesCache = []; // Cache for quote requests

function initializeQuoteManagement() {
    loadAdminQuoteRequests(); // Initial load

    const applyFiltersBtn = document.getElementById('apply-quote-filters-button');
    if (applyFiltersBtn) applyFiltersBtn.addEventListener('click', applyQuoteFilters);
    
    const resetFiltersBtn = document.getElementById('reset-quote-filters-button');
    if (resetFiltersBtn) resetFiltersBtn.addEventListener('click', resetQuoteFiltersAndLoad);

    const closeModalBtn = document.getElementById('close-quote-detail-modal-button');
    if (closeModalBtn) closeModalBtn.addEventListener('click', () => closeAdminModal('quote-detail-modal'));

    const quoteUpdateForm = document.getElementById('quote-update-form');
    if (quoteUpdateForm) quoteUpdateForm.addEventListener('submit', handleUpdateQuoteStatus);

    const convertToOrderBtn = document.getElementById('convert-quote-to-order-button');
    if (convertToOrderBtn) convertToOrderBtn.addEventListener('click', handleConvertQuoteToOrder);

    console.log("B2B Quote Request management initialized.");
}

async function loadAdminQuoteRequests(filters = {}, page = 1) {
    const tableBody = document.getElementById('quotes-table-body');
    const paginationControls = document.getElementById('quote-pagination-controls');
    if (!tableBody || !paginationControls) return;

    tableBody.innerHTML = `<tr><td colspan="6" class="text-center py-4">${t('admin.quotes.loading', 'Chargement des devis...')}</td></tr>`;
    paginationControls.innerHTML = '';

    filters.page = page;
    filters.per_page = 15; // Or configurable

    try {
        const response = await adminApi.getB2BQuoteRequests(filters); // New API method in admin_api.js
        currentAdminQuotesCache = response.quotes || [];
        const pagination = response.pagination;

        tableBody.innerHTML = '';
        if (currentAdminQuotesCache.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="6" class="text-center py-4">${t('admin.quotes.no_quotes_found', 'Aucune demande de devis trouvée.')}</td></tr>`;
            return;
        }

        currentAdminQuotesCache.forEach(quote => {
            const row = tableBody.insertRow();
            row.insertCell().textContent = quote.id;
            
            const clientCell = row.insertCell();
            clientCell.innerHTML = `${sanitizeHTML(quote.user_company_name || 'N/A')} <br><small class="text-gray-500">${sanitizeHTML(quote.user_email)}</small>`;
            
            row.insertCell().textContent = quote.request_date ? formatDateTimeForDisplay(quote.request_date) : 'N/A';
            
            const statusCell = row.insertCell();
            statusCell.innerHTML = `<span class="status-indicator status-quote-${quote.status || 'unknown'}">${t('admin.quotes.status.' + (quote.status || 'unknown'), quote.status || 'Unknown')}</span>`;
            
            row.insertCell().textContent = quote.item_count || (quote.items ? quote.items.length : 0);

            const actionsCell = row.insertCell();
            actionsCell.className = 'text-right actions';
            const viewButton = document.createElement('button');
            viewButton.innerHTML = `<i class="fas fa-eye mr-1"></i> ${t('common.view_details', 'Détails')}`;
            viewButton.className = 'btn btn-admin-secondary btn-sm';
            viewButton.onclick = () => openQuoteDetailModal(quote.id);
            actionsCell.appendChild(viewButton);
        });

        renderPagination(paginationControls, pagination, (newPage) => loadAdminQuoteRequests(filters, newPage));

    } catch (error) {
        console.error('Error loading quote requests:', error);
        tableBody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-red-500">${t('admin.quotes.load_error', 'Erreur chargement des devis.')}</td></tr>`;
        if(typeof showAdminToast === 'function') showAdminToast(t('admin.quotes.toast.load_failed', 'Erreur chargement devis.'), 'error');
    }
}

function applyQuoteFilters() {
    const status = document.getElementById('filter-quote-status').value;
    const customer = document.getElementById('filter-quote-customer').value.trim();
    const date = document.getElementById('filter-quote-date').value;
    const filters = {};
    if (status) filters.status = status;
    if (customer) filters.customer_search = customer;
    if (date) filters.date = date;
    loadAdminQuoteRequests(filters, 1);
}

function resetQuoteFiltersAndLoad() {
    document.getElementById('filter-quote-status').value = '';
    document.getElementById('filter-quote-customer').value = '';
    document.getElementById('filter-quote-date').value = '';
    loadAdminQuoteRequests({}, 1);
}

function formatDateTimeForDisplay(isoString) {
    if (!isoString) return 'N/A';
    try {
        return new Date(isoString).toLocaleString(document.documentElement.lang || 'fr-FR', {
            year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });
    } catch (e) { return isoString; }
}
function sanitizeHTML(str) {
    if (str === null || str === undefined) return '';
    const temp = document.createElement('div');
    temp.textContent = str;
    return temp.innerHTML;
}


async function openQuoteDetailModal(quoteId) {
    const quote = currentAdminQuotesCache.find(q => q.id === quoteId);
    if (!quote) {
        if(typeof showAdminToast === 'function') showAdminToast(t('admin.quotes.toast.not_found', 'Devis non trouvé.'), 'error');
        return;
    }

    document.getElementById('modal-quote-id').textContent = quote.id;
    document.getElementById('modal-quote-request-id-hidden').value = quote.id;
    document.getElementById('modal-quote-customer-name').textContent = `${quote.user_first_name || ''} ${quote.user_last_name || ''}`.trim();
    document.getElementById('modal-quote-customer-email').textContent = quote.user_email || 'N/A';
    document.getElementById('modal-quote-customer-company').textContent = quote.user_company_name || 'N/A';
    document.getElementById('modal-quote-contact-person').textContent = quote.contact_person || 'N/A';
    document.getElementById('modal-quote-contact-phone').textContent = quote.contact_phone || 'N/A';
    document.getElementById('modal-quote-request-date').textContent = formatDateTimeForDisplay(quote.request_date);
    document.getElementById('modal-quote-current-status').textContent = t('admin.quotes.status.' + (quote.status || 'unknown'), quote.status || 'Unknown');
    document.getElementById('modal-quote-admin-assigned').textContent = quote.admin_assigned_name || t('common.unassigned', 'Non assigné');
    document.getElementById('modal-quote-valid-until').textContent = quote.valid_until ? formatDateTimeForDisplay(quote.valid_until, {year: 'numeric', month: 'long', day: 'numeric'}) : 'N/A';
    document.getElementById('modal-quote-customer-notes').textContent = quote.notes || t('common.none', 'Aucune');
    document.getElementById('modal-quote-admin-notes').value = quote.admin_notes || '';
    document.getElementById('modal-quote-new-status').value = quote.status || 'pending';
    document.getElementById('modal-quote-valid-until-date').value = quote.valid_until ? quote.valid_until.split('T')[0] : '';


    const itemsTableBody = document.getElementById('modal-quote-items-table-body');
    itemsTableBody.innerHTML = '';
    let estimatedTotalHT = 0;

    if (quote.items && quote.items.length > 0) {
        quote.items.forEach(item => {
            const row = itemsTableBody.insertRow();
            row.insertCell().textContent = `${item.product_name_snapshot || 'Produit ID: '+item.product_id} (${item.product_code_snapshot || 'N/A'})`;
            row.insertCell().textContent = item.variant_description_snapshot || '-';
            row.insertCell().classList.add('text-center');
            row.insertCell().textContent = item.quantity;

            const priceRequestedCell = row.insertCell();
            priceRequestedCell.classList.add('text-right');
            priceRequestedCell.textContent = `€${parseFloat(item.requested_price_ht || 0).toFixed(2)}`;

            // Input for Admin to propose/confirm price for this item in the quote
            const proposedPriceCell = row.insertCell();
            proposedPriceCell.classList.add('text-right');
            const priceInput = document.createElement('input');
            priceInput.type = 'number';
            priceInput.name = `item_proposed_price_${item.id}`; // Unique name for each item
            priceInput.value = parseFloat(item.quoted_price_ht || item.requested_price_ht || 0).toFixed(2);
            priceInput.step = "0.01";
            priceInput.min = "0";
            priceInput.classList.add('form-input-admin', 'form-input-admin-sm', 'text-right', 'w-24', 'item-proposed-price'); // Ensure Tailwind class or custom for size
            priceInput.dataset.itemId = item.id; // Store item ID for submission
            proposedPriceCell.appendChild(priceInput);

            const totalProposedCell = row.insertCell(); // For calculated total
            totalProposedCell.classList.add('text-right', 'item-total-proposed');
            totalProposedCell.textContent = `€${(parseFloat(priceInput.value) * item.quantity).toFixed(2)}`;
            
            estimatedTotalHT += parseFloat(priceInput.value) * item.quantity;

            priceInput.addEventListener('input', () => { // Recalculate line total and grand total on input
                const lineTotal = (parseFloat(priceInput.value) || 0) * item.quantity;
                totalProposedCell.textContent = `€${lineTotal.toFixed(2)}`;
                recalculateModalQuoteTotal();
            });

        });
    } else {
        itemsTableBody.innerHTML = `<tr><td colspan="6" class="text-center italic py-2">${t('admin.quotes.no_items', 'Aucun article dans ce devis.')}</td></tr>`;
    }
    document.getElementById('modal-quote-total-ht-estimate').textContent = `€${estimatedTotalHT.toFixed(2)}`;
    
    const convertBtn = document.getElementById('convert-quote-to-order-button');
    if(quote.status === QuoteRequestStatusEnum.ACCEPTED_BY_CLIENT.value) { // Show convert button if accepted
        convertBtn.classList.remove('hidden');
    } else {
        convertBtn.classList.add('hidden');
    }

    if(typeof openAdminModal === 'function') openAdminModal('quote-detail-modal');
}

function recalculateModalQuoteTotal() {
    let grandTotal = 0;
    document.querySelectorAll('#modal-quote-items-table-body .item-proposed-price').forEach(priceInput => {
        const row = priceInput.closest('tr');
        const quantity = parseInt(row.cells[2].textContent); // Assuming quantity is in 3rd cell
        const itemTotal = (parseFloat(priceInput.value) || 0) * quantity;
        grandTotal += itemTotal;
    });
    document.getElementById('modal-quote-total-ht-estimate').textContent = `€${grandTotal.toFixed(2)}`;
}


async function handleUpdateQuoteStatus(event) {
    event.preventDefault();
    const form = event.target;
    const quoteRequestId = form.querySelector('#modal-quote-request-id-hidden').value;
    const newStatus = form.querySelector('#modal-quote-new-status').value;
    const adminNotes = form.querySelector('#modal-quote-admin-notes').value;
    const validUntil = form.querySelector('#modal-quote-valid-until-date').value || null;

    // Collect proposed item prices
    const itemsProposedPrices = [];
    document.querySelectorAll('#modal-quote-items-table-body .item-proposed-price').forEach(input => {
        itemsProposedPrices.push({
            item_id: input.dataset.itemId, // ID of the QuoteRequestItem
            proposed_price_ht: parseFloat(input.value)
        });
    });

    const payload = {
        status: newStatus,
        admin_notes: adminNotes,
        valid_until: validUntil,
        items: itemsProposedPrices // Send updated item prices
    };

    const updateButton = form.querySelector('#update-quote-status-button');
    const originalButtonText = updateButton.textContent;
    updateButton.disabled = true;
    updateButton.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> ${t('common.saving', 'Enregistrement...')}`;

    try {
        const response = await adminApi.updateB2BQuoteRequest(quoteRequestId, payload); // New API method
        if (response.success) {
            if(typeof showAdminToast === 'function') showAdminToast(response.message || t('admin.quotes.toast.update_success', 'Statut du devis mis à jour.'), 'success');
            if(typeof closeAdminModal === 'function') closeAdminModal('quote-detail-modal');
            const currentFilters = getCurrentQuoteFilters();
            loadAdminQuoteRequests(currentFilters, currentFilters.page || 1);
        } else {
            if(typeof showAdminToast === 'function') showAdminToast(response.message || t('admin.quotes.toast.update_failed', 'Échec MAJ devis.'), 'error');
        }
    } catch (error) {
        console.error(`Error updating quote request ${quoteRequestId}:`, error);
    } finally {
        updateButton.disabled = false;
        updateButton.innerHTML = originalButtonText;
    }
}

async function handleConvertQuoteToOrder() {
    const quoteRequestId = document.getElementById('modal-quote-request-id-hidden').value;
    if (!quoteRequestId) return;

    if(typeof showAdminConfirm !== 'function') {
        console.error("showAdminConfirm not available");
        alert("Confirmation dialog function not found.");
        return;
    }

    showAdminConfirm(
        t('admin.quotes.confirm_convert_title', 'Convertir en Commande?'),
        t('admin.quotes.confirm_convert_msg', 'Êtes-vous sûr de vouloir convertir ce devis en commande? Cette action est irréversible.'),
        async () => {
            const convertButton = document.getElementById('convert-quote-to-order-button');
            const originalButtonText = convertButton.textContent;
            convertButton.disabled = true;
            convertButton.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> ${t('admin.quotes.converting', 'Conversion...')}`;
            try {
                const response = await adminApi.convertB2BQuoteToOrder(quoteRequestId); // New API method
                if (response.success) {
                    if(typeof showAdminToast === 'function') showAdminToast(response.message || t('admin.quotes.toast.convert_success', 'Devis converti en commande!'), 'success');
                    if(typeof closeAdminModal === 'function') closeAdminModal('quote-detail-modal');
                    loadAdminQuoteRequests(getCurrentQuoteFilters(), getCurrentQuoteFilters().page || 1); // Refresh list
                    // Optionally, redirect to the new order's detail page in admin
                    // window.location.href = `admin_manage_orders.html?order_id=${response.order_id}`;
                } else {
                    if(typeof showAdminToast === 'function') showAdminToast(response.message || t('admin.quotes.toast.convert_failed', 'Échec conversion.'), 'error');
                }
            } catch (error) {
                console.error("Error converting quote to order:", error);
            } finally {
                convertButton.disabled = false;
                convertButton.innerHTML = originalButtonText;
            }
        },
        t('admin.quotes.convert_btn', 'Convertir'),
        t('common.cancel', 'Annuler')
    );
}


function getCurrentQuoteFilters() {
    // Similar to getCurrentFilters in admin_users.js
    const status = document.getElementById('filter-quote-status').value;
    const customer = document.getElementById('filter-quote-customer').value.trim();
    const date = document.getElementById('filter-quote-date').value;
    const paginationControls = document.getElementById('quote-pagination-controls');
    const currentPageButton = paginationControls.querySelector('button.btn-admin-primary');
    const currentPage = currentPageButton ? parseInt(currentPageButton.textContent) : 1;

    const filters = {};
    if (status) filters.status = status;
    if (customer) filters.customer_search = customer;
    if (date) filters.date = date;
    filters.page = currentPage;
    return filters;
}


// Add translation keys for admin.quotes.*, common.view_details, common.unassigned, common.none, etc.
