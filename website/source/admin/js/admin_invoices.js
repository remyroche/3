document.addEventListener('DOMContentLoaded', () => {
    // Ensure this code runs only on the create invoice page
    if (document.getElementById('create-invoice-form')) {
        populateProfessionalUsers();
        setupInvoiceFormListeners();
    }
});

async function populateProfessionalUsers() {
    const selectElement = document.getElementById('professional-user-select');
    try {// website/source/admin/js/admin_invoices.js

document.addEventListener('DOMContentLoaded', () => {
    if (document.body.id === 'page-admin-create-invoice') { // Specific to create invoice page
        populateProfessionalUsers();
        setupInvoiceFormListeners();
    } else if (document.body.id === 'page-admin-invoices') { // Specific to manage invoices page
        initializeManageInvoicesPage();
    }
});

async function populateProfessionalUsers() {
    const selectElement = document.getElementById('professional-user-select');
    if (!selectElement) return;
    selectElement.innerHTML = `<option value="">${t('admin.invoices.loading_users', 'Chargement des professionnels...')}</option>`; // XSS: translated text

    try {
        // Assuming adminApi.getProfessionalUsers() is defined in admin_api.js
        // and returns an array of user objects like { id: 1, company_name: "XYZ", first_name: "John", last_name: "Doe", email: "..." }
        const response = await adminApi.getProfessionalUsers(); 
        const users = response.users || response; // Adapt based on actual API response structure

        selectElement.innerHTML = `<option value="">-- ${t('admin.invoices.select_user', 'Sélectionner un Utilisateur')} --</option>`; // XSS: translated text
        if (users && users.length > 0) {
            users.forEach(user => {
                const option = document.createElement('option');
                option.value = user.id;
                // XSS: User data set with textContent
                option.textContent = `${user.company_name || (user.first_name || '') + ' ' + (user.last_name || '')} (${user.email})`;
                selectElement.appendChild(option);
            });
        } else {
             selectElement.innerHTML = `<option value="">-- ${t('admin.invoices.no_pro_users_found', 'Aucun utilisateur professionnel trouvé')} --</option>`; // XSS: translated text
        }
    } catch (error) {
        console.error('Failed to load professional users:', error);
        selectElement.innerHTML = `<option value="">${t('admin.invoices.error_loading_users', 'Erreur chargement utilisateurs')}</option>`; // XSS: translated text
        showAdminToast(t('admin.invoices.error_loading_users_toast', 'Error loading professional users.'), 'error');
    }
}

function setupInvoiceFormListeners() {
    const addLineItemBtn = document.getElementById('add-line-item-btn');
    const lineItemsContainer = document.getElementById('line-items-container');
    const form = document.getElementById('create-invoice-form');
    let lineItemIndex = 0;

    if (!addLineItemBtn || !lineItemsContainer || !form) return;

    addLineItemRow(lineItemIndex++);

    addLineItemBtn.addEventListener('click', () => {
        addLineItemRow(lineItemIndex++);
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const data = {
            b2b_user_id: formData.get('b2b_user_id'),
            notes: formData.get('notes'), // Backend should sanitize this if stored and displayed as HTML
            line_items: []
        };

        const lineItemRows = lineItemsContainer.querySelectorAll('.line-item-row');
        for (const row of lineItemRows) {
            const description = row.querySelector('input[name="description"]').value;
            const quantity = row.querySelector('input[name="quantity"]').value;
            const unit_price = row.querySelector('input[name="unit_price"]').value;

            if (description && quantity && unit_price) {
                data.line_items.push({
                    description, // Backend should sanitize
                    quantity: parseInt(quantity, 10),
                    unit_price: parseFloat(unit_price)
                });
            }
        }
        
        if (!data.b2b_user_id || data.line_items.length === 0) {
            showAdminToast(t('admin.invoices.error_select_user_and_items', 'Please select a user and add at least one valid line item.'), 'error');
            return;
        }

        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.disabled = true;
        submitButton.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> ${t('admin.invoices.generating_invoice', 'Génération en cours...')}`; // XSS: translated text, icon is safe

        try {
            const result = await adminApi.createManualInvoice(data); // adminApi.createManualInvoice from admin_api.js
            showAdminToast(t('admin.invoices.create_success_toast', `Invoice ${result.invoice_number} created successfully!`), 'success');
            form.reset();
            lineItemsContainer.innerHTML = ''; 
            lineItemIndex = 0; // Reset index
            addLineItemRow(lineItemIndex++); 
            populateProfessionalUsers(); // Repopulate user list in case it changed or to reset selection
        } catch (error) {
            console.error('Failed to create invoice:', error);
            // Error toast handled by adminApi
        } finally {
            submitButton.disabled = false;
            submitButton.innerHTML = `<i class="fas fa-file-invoice mr-2"></i> ${t('admin.invoices.generate_invoice_btn', 'Générer la Facture')}`; // XSS: translated text
        }
    });

    function addLineItemRow(index) {
        const row = document.createElement('div');
        row.className = 'grid grid-cols-12 gap-4 mb-2 line-item-row';
        // Using textContent for placeholders where possible, or ensuring they are static strings
        row.innerHTML = `
            <div class="col-span-6">
                <input type="text" name="description" placeholder="${t('admin.invoices.item_desc_placeholder', 'Item Description')}" class="form-input-admin w-full" required>
            </div>
            <div class="col-span-2">
                <input type="number" name="quantity" placeholder="${t('admin.invoices.qty_placeholder', 'Qty')}" min="1" class="form-input-admin w-full" required>
            </div>
            <div class="col-span-3">
                <input type="number" name="unit_price" placeholder="${t('admin.invoices.unit_price_placeholder', 'Unit Price')}" min="0" step="0.01" class="form-input-admin w-full" required>
            </div>
            <div class="col-span-1 flex items-center">
                <button type="button" class="text-red-500 hover:text-red-700" aria-label="${t('admin.invoices.remove_item_label', 'Remove line item')}">X</button>
            </div>
        `;
        const removeButton = row.querySelector('button[type="button"]');
        removeButton.addEventListener('click', function() {
            this.parentElement.parentElement.remove();
        });
        lineItemsContainer.appendChild(row);
    }
}


// --- Manage Invoices Page Specific Logic ---
function initializeManageInvoicesPage() {
    loadAdminInvoices(); // Initial load

    const filterButton = document.getElementById('apply-invoice-filters-button');
    if (filterButton) {
        filterButton.addEventListener('click', applyInvoiceFilters);
    }
    // Add listeners for modal if one is added for invoice details/status update
}

async function loadAdminInvoices(filters = {}) {
    const tableBody = document.getElementById('manage-invoices-table-body');
    if (!tableBody) return;
    
    const loadingRow = tableBody.insertRow();
    const loadingCell = loadingRow.insertCell();
    loadingCell.colSpan = 6; // Adjust if more columns
    loadingCell.className = "text-center py-4";
    loadingCell.textContent = t('admin.invoices.table.loading'); // XSS: translated text
    tableBody.innerHTML = ''; // Clear after creating
    tableBody.appendChild(loadingRow);

    try {
        const response = await adminApi.getAdminInvoices(filters); // adminApi.getAdminInvoices from admin_api.js
        const invoices = response.invoices || []; // Adapt to actual API response

        tableBody.innerHTML = ''; // Clear loading message

        if (invoices.length === 0) {
            const emptyRow = tableBody.insertRow();
            const cell = emptyRow.insertCell();
            cell.colSpan = 6;
            cell.className = "text-center py-4";
            cell.textContent = t('admin.invoices.table.no_invoices_found', 'Aucune facture trouvée.'); // XSS: translated text
            return;
        }

        invoices.forEach(invoice => {
            const row = tableBody.insertRow();
            row.insertCell().textContent = invoice.invoice_number; // XSS
            row.insertCell().textContent = invoice.b2b_user_email || (invoice.b2b_user_id ? `ID: ${invoice.b2b_user_id}` : 'N/A'); // XSS
            row.insertCell().textContent = invoice.issue_date ? new Date(invoice.issue_date).toLocaleDateString(currentLocale) : 'N/A'; // XSS
            row.insertCell().textContent = `${parseFloat(invoice.total_amount).toFixed(2)} ${invoice.currency || 'EUR'}`; // XSS
            
            const statusCell = row.insertCell();
            const statusSpan = document.createElement('span');
            // Assuming getStatusClass returns CSS classes, and translated status text is used.
            statusSpan.className = `px-2 py-1 text-xs font-semibold rounded-full ${getStatusClass(invoice.status) || 'bg-gray-200 text-gray-800'}`;
            statusSpan.textContent = t(`invoiceStatus.${invoice.status.toLowerCase()}`, invoice.status) || invoice.status; // XSS
            statusCell.appendChild(statusSpan);

            const actionsCell = row.insertCell();
            if (invoice.pdf_download_url) {
                const downloadLink = document.createElement('a');
                downloadLink.href = invoice.pdf_download_url;
                downloadLink.target = "_blank";
                downloadLink.rel = "noopener noreferrer";
                downloadLink.className = "btn btn-admin-secondary text-xs p-1.5";
                downloadLink.innerHTML = `<i class="fas fa-download mr-1"></i> ${t('admin.invoices.table.download_btn', 'PDF')}`; // XSS: translated text, icon safe
                actionsCell.appendChild(downloadLink);
            }
            // Add more actions like 'View Details', 'Update Status' if needed
        });
    } catch (error) {
        console.error('Failed to load admin invoices:', error);
        tableBody.innerHTML = ''; // Clear loading
        const errorRow = tableBody.insertRow();
        const errorCell = errorRow.insertCell();
        errorCell.colSpan = 6;
        errorCell.className = "text-center py-4 text-red-600";
        errorCell.textContent = t('admin.invoices.table.load_error', 'Erreur de chargement des factures.'); // XSS: translated text
    }
}

function applyInvoiceFilters() {
    const userFilter = document.getElementById('filter-manage-invoice-user').value;
    const statusFilter = document.getElementById('filter-manage-invoice-status').value;
    const filters = {};
    if (userFilter) filters.user = userFilter;
    if (statusFilter) filters.status = statusFilter;
    loadAdminInvoices(filters);
}

// Helper for invoice status styling (if not already in admin_ui.js or similar)
function getStatusClass(status) {
    const statusKey = status ? status.toLowerCase() : 'default';
    const statusClasses = {
        'draft': 'bg-gray-200 text-gray-700',
        'issued': 'bg-blue-100 text-blue-700',
        'sent': 'bg-blue-200 text-blue-800',
        'paid': 'bg-green-100 text-green-700',
        'partially_paid': 'bg-yellow-100 text-yellow-700',
        'overdue': 'bg-red-100 text-red-700',
        'cancelled': 'bg-orange-100 text-orange-700',
        'voided': 'bg-red-200 text-red-800',
        'default': 'bg-gray-300 text-gray-800'
    };
    return statusClasses[statusKey] || statusClasses['default'];
}
