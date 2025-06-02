document.addEventListener('DOMContentLoaded', async () => {
    console.log('Admin View Inventory JS Initialized');

    // Check login status
    if (typeof checkAdminLogin !== 'function' || !checkAdminLogin()) {
        console.warn('Admin not logged in or checkAdminLogin function not available.');
        // checkAdminLogin will redirect if not logged in.
        return;
    }

    const tableBody = document.getElementById('detailed-inventory-table-body');
    const filterProductNameInput = document.getElementById('filter-view-product-name');
    const filterItemStatusSelect = document.getElementById('filter-view-item-status');
    const filterProductCodeInput = document.getElementById('filter-view-product-code'); // New filter
    const searchItemUidInput = document.getElementById('search-view-item-uid');
    const exportCsvButton = document.getElementById('export-inventory-csv-button'); // New button
    const importCsvButton = document.getElementById('import-inventory-csv-button'); // New button
    const importCsvFileInput = document.getElementById('import-inventory-csv-file'); // New file input

    const currentLocale = document.documentElement.lang || 'fr-FR'; // Default to fr-FR if lang not set
    const notApplicable = t('common.notApplicable'); // For N/A text

    let allInventoryItems = []; // To store all fetched items for client-side filtering

    async function fetchDetailedInventory() {
        if (!tableBody) {
            console.error('Table body for detailed inventory not found.');
            return;
        }
        tableBody.innerHTML = `<tr><td colspan="9" class="text-center p-4">${t('admin.inventory.loadingDetailed')}</td></tr>`; // Colspan updated

        try {
            // Use adminApiRequest directly as per admin_api.js
            const response = await adminApiRequest('/inventory/items/detailed', 'GET'); 
            // The backend for /inventory/items/detailed returns an array directly, not nested under .data or .success
            if (Array.isArray(response)) {
                allInventoryItems = response;
                renderInventoryTable(allInventoryItems);
            } else {
                const errorMessage = response?.message || t('admin.inventory.cannotLoadData');
                tableBody.innerHTML = `<tr><td colspan="9" class="text-center p-4">${t('admin.inventory.errorPrefix')}${errorMessage}</td></tr>`; // Colspan updated
                showAdminToast(t('admin.inventory.errorLoadingInventory') + (response?.message || t('admin.inventory.invalidServerResponse')), 'error');
            }
        } catch (error) {
            console.error('Error fetching detailed inventory:', error);
            tableBody.innerHTML = `<tr><td colspan="8" class="text-center p-4">${t('admin.inventory.serverConnectionError')}</td></tr>`;
            showToast(t('admin.inventory.connectionErrorLoading'), 'error');
        }
    }

    function renderInventoryTable(items) {
        if (!tableBody) return;
        tableBody.innerHTML = ''; // Clear existing rows
        const naText = notApplicable; // Use translated "N/A"

        if (items.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="9" class="text-center p-4">${t('admin.inventory.noItemsFound')}</td></tr>`; // Colspan updated
            return;
        }

        items.forEach(item => {
            // Prepare bilingual product name
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
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${displayProductName}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${item.variant_name || naText}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono">${item.product_code || naText}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono">${item.item_uid || naText}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${item.status || naText}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${item.batch_number || naText}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${item.production_date ? new Date(item.production_date).toLocaleDateString(currentLocale) : naText}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${item.expiry_date ? new Date(item.expiry_date).toLocaleDateString(currentLocale) : naText}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${item.received_at ? new Date(item.received_at).toLocaleString(currentLocale) : naText}</td>
            `;
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
            
            return !!(productNameMatch && itemStatusMatch && productCodeMatch && itemUidMatch); // Ensure boolean
        });

        renderInventoryTable(filteredItems);
    }

    // Event Listeners for filters
    if (filterProductNameInput) {
        filterProductNameInput.addEventListener('input', applyFilters);
    }
    if (filterItemStatusSelect) {
        filterItemStatusSelect.addEventListener('change', applyFilters);
    }
    if (filterProductCodeInput) {
        filterProductCodeInput.addEventListener('input', applyFilters);
    }
    if (searchItemUidInput) {
        searchItemUidInput.addEventListener('input', applyFilters);
    }

    // Event Listener for Export Button
    if (exportCsvButton) {
        exportCsvButton.addEventListener('click', async () => {
            showAdminToast(t('admin.inventory.export.generatingCsv'), "info");
            try {
                const exportUrl = `${API_BASE_URL}/inventory/export/serialized_items`; // API_BASE_URL from admin_config.js
                
                // For file downloads, directly navigating or using a link is common.
                // adminApiRequest is designed for JSON responses.
                window.location.href = exportUrl; // This will trigger the download
                // Or, create a temporary link:
                // const link = document.createElement('a');
                // link.href = exportUrl;
                // document.body.appendChild(link);
                // link.click();
                // document.body.removeChild(link);
                showAdminToast(t('admin.inventory.export.requestSent'), "success", 3000);
            } catch (error) {
                console.error("Erreur lors de la tentative d'export CSV:", error);
                showAdminToast(t('admin.inventory.export.generationFailed'), "error");
            }
        });
    }

    // Event Listener for Import Button
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

    // Initial load
    fetchDetailedInventory();

    // Setup common UI elements like user greeting and logout button
    if (typeof setupAdminUIGlobals === 'function') {
        setupAdminUIGlobals();
    } else {
        console.warn('setupAdminUIGlobals function is not defined. Ensure admin_main.js is loaded correctly.');
        // Fallback or minimal setup if admin_main.js parts are not available
        const adminUser = getAdminUser();
        const userGreeting = document.getElementById('admin-user-greeting');
        if (userGreeting && adminUser) {
            userGreeting.textContent = `Bonjour, ${adminUser.email}`;
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
                // Optionally display failed rows in a modal or a dedicated section
            }
            showAdminToast(message, "success", 8000);
            fetchDetailedInventory(); // Refresh the table
            if (importCsvFileInput) importCsvFileInput.value = ''; // Clear file input
        } else {
            const errorMsg = response?.message || t('admin.inventory.import.unknownError');
            showAdminToast(t('admin.inventory.import.failed') + errorMsg, "error", 8000);
            if (response?.failed_rows) {
                 console.error("Import failures details:", response.failed_rows);
            }
        }
    }


    // --- Product Overview Tooltip Logic ---
    const tooltip = document.getElementById('product-overview-tooltip');

    if (!tableBody || !tooltip) {
        console.warn('Inventory table body or tooltip element not found for admin_view_inventory. Product overview feature will not be available.');
        return;
    }

    // Helper function to find item data from the stored list
    function getInventoryItemByUid(uid) {
        // allInventoryItems is from the outer scope of DOMContentLoaded
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
            const naText = notApplicable; // Use translated "N/A"
            const productionDateStr = itemData.production_date ? new Date(itemData.production_date).toLocaleDateString(currentLocale) : naText;
            const expiryDateStr = itemData.expiry_date ? new Date(itemData.expiry_date).toLocaleDateString(currentLocale) : naText;
            const receivedDateStr = itemData.received_at ? new Date(itemData.received_at).toLocaleDateString(currentLocale) : naText;

            // Prepare bilingual product name for tooltip
            let tooltipProductName = itemData.product_name || naText;
            if (itemData.product_name_fr && itemData.product_name_en) {
                tooltipProductName = itemData.product_name_fr.toLowerCase() === itemData.product_name_en.toLowerCase() ? itemData.product_name_fr : `${itemData.product_name_fr} / ${itemData.product_name_en}`;
            } else if (itemData.product_name_fr) {
                tooltipProductName = itemData.product_name_fr;
            } else if (itemData.product_name_en) {
                tooltipProductName = itemData.product_name_en;
            }

            tooltip.innerHTML = `
                <div class="text-base font-semibold mb-2">${tooltipProductName} ${itemData.variant_name ? `(${itemData.variant_name})` : ''}</div>
                <div class="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-xs">
                    <span class="font-medium">${t('admin.inventory.tooltip.uid')}</span><span>${itemData.item_uid || naText}</span>
                    <span class="font-medium">${t('admin.inventory.tooltip.productCode')}</span><span>${itemData.product_code || naText}</span>
                    <span class="font-medium">${t('admin.inventory.tooltip.status')}</span><span>${itemData.status || naText}</span>
                    <span class="font-medium">${t('admin.inventory.tooltip.batch')}</span><span>${itemData.batch_number || naText}</span>
                    <span class="font-medium">${t('admin.inventory.tooltip.prodDate')}</span><span>${productionDateStr}</span>
                    <span class="font-medium">${t('admin.inventory.tooltip.expDate')}</span><span>${expiryDateStr}</span>
                    <span class="font-medium">${t('admin.inventory.tooltip.receivedOn')}</span><span>${receivedDateStr}</span>
                </div>
            `;

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
            if (finalLeft < window.scrollX) {
                finalLeft = window.scrollX + 5;
            }
            if (finalTop < window.scrollY) {
                finalTop = window.scrollY + 5;
            }

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
    // --- End of Product Overview Tooltip Logic ---

});