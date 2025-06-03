document.addEventListener('DOMContentLoaded', async () => {
    console.log('Admin View Inventory JS Initialized');

    // Check login status
    if (typeof checkAdminLogin !== 'function' || !checkAdminLogin()) {
        console.warn('Admin not logged in or checkAdminLogin function not available.');
        // checkAdminLogin will redirect if not logged in.
        return;
    }document.addEventListener('DOMContentLoaded', async () => {
    console.log('Admin View Inventory JS Initialized');

    if (typeof checkAdminLogin !== 'function' || !checkAdminLogin()) {
        console.warn('Admin not logged in or checkAdminLogin function not available.');
        return;
    }

    const tableBody = document.getElementById('detailed-inventory-table-body');
    const filterProductNameInput = document.getElementById('filter-view-product-name');
    const filterItemStatusSelect = document.getElementById('filter-view-item-status');
    const filterProductCodeInput = document.getElementById('filter-view-product-code'); 
    const searchItemUidInput = document.getElementById('search-view-item-uid');
    const exportCsvButton = document.getElementById('export-inventory-csv-button'); 
    const importCsvButton = document.getElementById('import-inventory-csv-button'); 
    const importCsvFileInput = document.getElementById('import-inventory-csv-file'); 

    const currentLocale = document.documentElement.lang || 'fr-FR'; 
    const notApplicable = t('common.notApplicable'); 

    let allInventoryItems = []; 

    async function fetchDetailedInventory() {
        if (!tableBody) {
            console.error('Table body for detailed inventory not found.');
            return;
        }
        const loadingRow = tableBody.insertRow();
        const loadingCell = loadingRow.insertCell();
        loadingCell.colSpan = 9; // Adjusted colspan
        loadingCell.className = "text-center p-4";
        loadingCell.textContent = t('admin.inventory.loadingDetailed'); // XSS: translated text
        tableBody.innerHTML = ''; // Clear after creating, then replace
        tableBody.appendChild(loadingRow);


        try {
            const response = await adminApiRequest('/inventory/items/detailed', 'GET'); 
            if (Array.isArray(response)) {
                allInventoryItems = response;
                renderInventoryTable(allInventoryItems);
            } else {
                const errorMessage = response?.message || t('admin.inventory.cannotLoadData');
                tableBody.innerHTML = ''; // Clear loading
                const errorRow = tableBody.insertRow();
                const errorCell = errorRow.insertCell();
                errorCell.colSpan = 9; // Adjusted colspan
                errorCell.className = "text-center p-4";
                errorCell.textContent = `${t('admin.inventory.errorPrefix')}${errorMessage}`; // XSS: translated text
                showAdminToast(t('admin.inventory.errorLoadingInventory') + (response?.message || t('admin.inventory.invalidServerResponse')), 'error');
            }
        } catch (error) {
            console.error('Error fetching detailed inventory:', error);
            tableBody.innerHTML = ''; // Clear loading
            const errorRow = tableBody.insertRow();
            const errorCell = errorRow.insertCell();
            errorCell.colSpan = 8; // Original colspan, check if 9 is needed
            errorCell.className = "text-center p-4";
            errorCell.textContent = t('admin.inventory.serverConnectionError'); // XSS: translated text
            showAdminToast(t('admin.inventory.connectionErrorLoading'), 'error');
        }
    }

    function renderInventoryTable(items) {
        if (!tableBody) return;
        tableBody.innerHTML = ''; 
        const naText = notApplicable; 

        if (items.length === 0) {
            const emptyRow = tableBody.insertRow();
            const cell = emptyRow.insertCell();
            cell.colSpan = 9; // Adjusted colspan
            cell.className = "text-center p-4";
            cell.textContent = t('admin.inventory.noItemsFound'); // XSS: translated text
            return;
        }

        items.forEach(item => {
            let displayProductName = item.product_name || naText;
            if (item.product_name_fr && item.product_name_en) {
                displayProductName = item.product_name_fr.toLowerCase() === item.product_name_en.toLowerCase() ? item.product_name_fr : `${item.product_name_fr} / ${item.product_name_en}`;
            } else if (item.product_name_fr) {
                displayProductName = item.product_name_fr;
            } else if (item.product_name_en) {
                displayProductName = item.product_name_en;
            }

            const row = tableBody.insertRow();
            row.setAttribute('data-item-uid', item.item_uid);
            row.classList.add('hover:bg-slate-50', 'cursor-default'); 
            
            row.insertCell().textContent = displayProductName; // XSS
            row.insertCell().textContent = item.variant_name || naText; // XSS
            row.insertCell().textContent = item.product_code || naText; // XSS
            row.insertCell().textContent = item.item_uid || naText; // XSS
            row.insertCell().textContent = item.status || naText; // XSS
            row.insertCell().textContent = item.batch_number || naText; // XSS
            row.insertCell().textContent = item.production_date ? new Date(item.production_date).toLocaleDateString(currentLocale) : naText; // XSS
            row.insertCell().textContent = item.expiry_date ? new Date(item.expiry_date).toLocaleDateString(currentLocale) : naText; // XSS
            row.insertCell().textContent = item.received_at ? new Date(item.received_at).toLocaleString(currentLocale) : naText; // XSS
        });
    }

    function applyFilters() {
        const productNameFilter = filterProductNameInput.value.toLowerCase();
        const itemStatusFilter = filterItemStatusSelect.value;
        const productCodeFilter = filterProductCodeInput ? filterProductCodeInput.value.toLowerCase() : '';
        const itemUidFilter = searchItemUidInput.value.toLowerCase();

        const filteredItems = allInventoryItems.filter(item => {
            const productNameMatch = !productNameFilter ||
                (item.product_name && item.product_name.toLowerCase().includes(productNameFilter)) ||
                (item.product_name_fr && item.product_name_fr.toLowerCase().includes(productNameFilter)) ||
                (item.product_name_en && item.product_name_en.toLowerCase().includes(productNameFilter));
            const itemStatusMatch = !itemStatusFilter || item.status === itemStatusFilter;
            const productCodeMatch = !productCodeFilter || (item.product_code && item.product_code.toLowerCase().includes(productCodeFilter));
            const itemUidMatch = !itemUidFilter || (item.item_uid && item.item_uid.toLowerCase().includes(itemUidFilter));
            
            return !!(productNameMatch && itemStatusMatch && productCodeMatch && itemUidMatch); 
        });

        renderInventoryTable(filteredItems);
    }

    if (filterProductNameInput) filterProductNameInput.addEventListener('input', applyFilters);
    if (filterItemStatusSelect) filterItemStatusSelect.addEventListener('change', applyFilters);
    if (filterProductCodeInput) filterProductCodeInput.addEventListener('input', applyFilters);
    if (searchItemUidInput) searchItemUidInput.addEventListener('input', applyFilters);

    if (exportCsvButton) {
        exportCsvButton.addEventListener('click', async () => {
            showAdminToast(t('admin.inventory.export.generatingCsv'), "info");
            try {
                const exportUrl = `${API_BASE_URL}/inventory/export/serialized_items`; 
                window.location.href = exportUrl; 
                showAdminToast(t('admin.inventory.export.requestSent'), "success", 3000);
            } catch (error) {
                console.error("Erreur lors de la tentative d'export CSV:", error);
                showAdminToast(t('admin.inventory.export.generationFailed'), "error");
            }
        });
    }

    if (importCsvButton && importCsvFileInput) {
        importCsvButton.addEventListener('click', async () => {
            const file = importCsvFileInput.files[0];
            if (!file) {
                showAdminToast(t('admin.inventory.import.noFileSelected'), "warning");
                return;
            }
            if (!file.name.endsWith('.csv')) {
                showAdminToast(t('admin.inventory.import.invalidFileType'), "error");
                return;
            }

            const formData = new FormData();
            formData.append('file', file);

            showAdminToast(t('admin.inventory.import.processing'), "info");
            handleImportResponse(await adminApiRequest('/inventory/import/serialized_items', 'POST', formData, true));
        });
    }

    fetchDetailedInventory();

    if (typeof setupAdminUIGlobals === 'function') {
        setupAdminUIGlobals();
    } else {
        console.warn('setupAdminUIGlobals function is not defined. Ensure admin_main.js is loaded correctly.');
        const adminUser = getAdminUser();
        const userGreeting = document.getElementById('admin-user-greeting');
        if (userGreeting && adminUser) {
            userGreeting.textContent = `Bonjour, ${adminUser.email}`; // XSS: email is generally safe
        }
        const logoutButton = document.getElementById('admin-logout-button');
        if (logoutButton && typeof adminLogout === 'function') {
            logoutButton.addEventListener('click', adminLogout);
        }
    }

    function handleImportResponse(response) {
        if (response && response.success) {
            let message = t('admin.inventory.import.processedSuccess', { imported: response.imported, updated: response.updated, total: response.total_processed });
            if (response.failed_rows && response.failed_rows.length > 0) {
                message += ` ${t('admin.inventory.import.failuresCount', { count: response.failed_rows.length })}`;
                console.warn("Import failures:", response.failed_rows);
            }
            showAdminToast(message, "success", 8000);
            fetchDetailedInventory(); 
            if (importCsvFileInput) importCsvFileInput.value = ''; 
        } else {
            const errorMsg = response?.message || t('admin.inventory.import.unknownError');
            showAdminToast(t('admin.inventory.import.failed') + errorMsg, "error", 8000);
            if (response?.failed_rows) {
                 console.error("Import failures details:", response.failed_rows);
            }
        }
    }

    const tooltip = document.getElementById('product-overview-tooltip');

    if (!tableBody || !tooltip) {
        console.warn('Inventory table body or tooltip element not found for admin_view_inventory. Product overview feature will not be available.');
        return;
    }

    function getInventoryItemByUid(uid) {
        if (allInventoryItems && Array.isArray(allInventoryItems)) {
            return allInventoryItems.find(item => String(item.item_uid) === String(uid));
        }
        console.warn(`allInventoryItems is not available or not an array. Cannot fetch item UID: ${uid}`);
        return null;
    }

    tableBody.addEventListener('mouseover', (event) => {
        const row = event.target.closest('tr[data-item-uid]');
        if (!row) return;

        const itemUid = row.dataset.itemUid;
        const itemData = getInventoryItemByUid(itemUid);

        if (itemData) {
            const naText = notApplicable; 
            const productionDateStr = itemData.production_date ? new Date(itemData.production_date).toLocaleDateString(currentLocale) : naText;
            const expiryDateStr = itemData.expiry_date ? new Date(itemData.expiry_date).toLocaleDateString(currentLocale) : naText;
            const receivedDateStr = itemData.received_at ? new Date(itemData.received_at).toLocaleDateString(currentLocale) : naText;

            let tooltipProductName = itemData.product_name || naText;
            if (itemData.product_name_fr && itemData.product_name_en) {
                tooltipProductName = itemData.product_name_fr.toLowerCase() === itemData.product_name_en.toLowerCase() ? itemData.product_name_fr : `${itemData.product_name_fr} / ${itemData.product_name_en}`;
            } else if (itemData.product_name_fr) {
                tooltipProductName = itemData.product_name_fr;
            } else if (itemData.product_name_en) {
                tooltipProductName = itemData.product_name_en;
            }
            
            // XSS: Building tooltip content safely using textContent
            tooltip.innerHTML = ''; // Clear previous content

            const titleDiv = document.createElement('div');
            titleDiv.className = 'text-base font-semibold mb-2';
            titleDiv.textContent = `${tooltipProductName} ${itemData.variant_name ? `(${itemData.variant_name})` : ''}`;
            tooltip.appendChild(titleDiv);

            const gridDiv = document.createElement('div');
            gridDiv.className = 'grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-xs';

            function addTooltipRow(labelKey, value) {
                const labelSpan = document.createElement('span');
                labelSpan.className = 'font-medium';
                labelSpan.textContent = t(labelKey);
                gridDiv.appendChild(labelSpan);

                const valueSpan = document.createElement('span');
                valueSpan.textContent = value;
                gridDiv.appendChild(valueSpan);
            }

            addTooltipRow('admin.inventory.tooltip.uid', itemData.item_uid || naText);
            addTooltipRow('admin.inventory.tooltip.productCode', itemData.product_code || naText);
            addTooltipRow('admin.inventory.tooltip.status', itemData.status || naText);
            addTooltipRow('admin.inventory.tooltip.batch', itemData.batch_number || naText);
            addTooltipRow('admin.inventory.tooltip.prodDate', productionDateStr);
            addTooltipRow('admin.inventory.tooltip.expDate', expiryDateStr);
            addTooltipRow('admin.inventory.tooltip.receivedOn', receivedDateStr);
            
            tooltip.appendChild(gridDiv);
            tooltip.classList.remove('hidden');

            const tooltipRect = tooltip.getBoundingClientRect();
            let finalLeft = event.pageX + 15;
            let finalTop = event.pageY + 15;

            if (event.clientX + 15 + tooltipRect.width > window.innerWidth) {
                finalLeft = event.pageX - tooltipRect.width - 15;
            }
            if (event.clientY + 15 + tooltipRect.height > window.innerHeight) {
                finalTop = event.pageY - tooltipRect.height - 15;
            }
            if (finalLeft < window.scrollX) finalLeft = window.scrollX + 5;
            if (finalTop < window.scrollY) finalTop = window.scrollY + 5;

            tooltip.style.left = `${finalLeft}px`;
            tooltip.style.top = `${finalTop}px`;
        }
    });

    tableBody.addEventListener('mouseout', (event) => {
        const currentRow = event.target.closest('tr[data-item-uid]');
        if (currentRow) {
            if (!event.relatedTarget || !currentRow.contains(event.relatedTarget)) {
                tooltip.classList.add('hidden');
            }
        } else if (tableBody.contains(event.target) && (!event.relatedTarget || !tableBody.contains(event.relatedTarget))) {
            tooltip.classList.add('hidden');
        }
    });
});
