// website/source/admin/js/admin_view_inventory.js

document.addEventListener('DOMContentLoaded', async () => {
    console.log('Admin View Detailed Inventory JS Initialized');

    if (typeof checkAdminLogin !== 'function' || !checkAdminLogin()) {
        console.warn('Admin not logged in or checkAdminLogin function not available.');
        // checkAdminLogin in admin_auth.js will redirect if not logged in.
        return;
    }

    // --- DOM Elements ---
    const tableBody = document.getElementById('detailed-inventory-table-body');
    const filterProductNameInput = document.getElementById('filter-view-product-name');
    const filterProductCodeInput = document.getElementById('filter-view-product-code');
    const filterVariantSkuSuffixInput = document.getElementById('filter-view-variant-sku-suffix'); // Added
    const filterItemStatusSelect = document.getElementById('filter-view-item-status');
    const searchItemUidInput = document.getElementById('search-view-item-uid');
    
    const exportCsvButton = document.getElementById('export-inventory-csv-button');
    const importCsvFileInput = document.getElementById('import-inventory-csv-file');
    const importCsvButton = document.getElementById('import-inventory-csv-button');
    // const importInventoryForm = document.getElementById('import-inventory-form'); // If you wrap file input in a form

    const tooltip = document.getElementById('product-overview-tooltip');

    // --- State ---
    let allInventoryItems = [];
    const currentLocale = document.documentElement.lang || 'fr-FR';
    const notApplicable = t('common.notApplicable', 'N/A'); // Assuming t() is available globally

    // --- Functions ---

    /**
     * Fetches the detailed inventory from the backend.
     */
    async function fetchDetailedInventory() {
        if (!tableBody) {
            console.error('Table body for detailed inventory not found.');
            return;
        }
        const loadingRow = tableBody.insertRow();
        const loadingCell = loadingRow.insertCell();
        loadingCell.colSpan = 10; // Adjusted for new SKU Suffix column
        loadingCell.className = "text-center p-4";
        loadingCell.textContent = t('admin.inventory.loadingDetailed', 'Chargement de l\'inventaire détaillé...');
        tableBody.innerHTML = ''; 
        tableBody.appendChild(loadingRow);

        try {
            const response = await adminApi.getDetailedInventoryItems(); // From admin_api.js
            if (response && Array.isArray(response.detailed_items)) { // Assuming API returns { detailed_items: [] }
                allInventoryItems = response.detailed_items;
                renderInventoryTable(allInventoryItems);
            } else if (Array.isArray(response)) { // Fallback if API returns array directly
                allInventoryItems = response;
                renderInventoryTable(allInventoryItems);
            } else {
                const errorMessage = response?.message || t('admin.inventory.cannotLoadData', 'Impossible de charger les données.');
                tableBody.innerHTML = '';
                const errorRow = tableBody.insertRow();
                const errorCell = errorRow.insertCell();
                errorCell.colSpan = 10; // Adjusted
                errorCell.className = "text-center p-4 text-red-600";
                errorCell.textContent = `${t('admin.inventory.errorPrefix', 'Erreur : ')}${errorMessage}`;
                if (typeof showAdminToast === 'function') {
                    showAdminToast(t('admin.inventory.errorLoadingInventory', 'Erreur chargement inventaire : ') + (response?.message || t('admin.inventory.invalidServerResponse', 'Réponse invalide du serveur.')), 'error');
                }
            }
        } catch (error) {
            console.error('Error fetching detailed inventory:', error);
            tableBody.innerHTML = '';
            const errorRow = tableBody.insertRow();
            const errorCell = errorRow.insertCell();
            errorCell.colSpan = 10; // Adjusted
            errorCell.className = "text-center p-4 text-red-500";
            errorCell.textContent = t('admin.inventory.serverConnectionError', 'Erreur de connexion au serveur.');
            if (typeof showAdminToast === 'function') {
                showAdminToast(t('admin.inventory.connectionErrorLoading', 'Erreur de connexion lors du chargement.'), 'error');
            }
        }
    }

    /**
     * Renders the inventory items in the table.
     * @param {Array} items - The array of inventory items to render.
     */
    function renderInventoryTable(items) {
        if (!tableBody) return;
        tableBody.innerHTML = ''; 

        if (!items || items.length === 0) {
            const emptyRow = tableBody.insertRow();
            const cell = emptyRow.insertCell();
            cell.colSpan = 10; // Adjusted for new SKU Suffix column
            cell.className = "text-center p-4";
            cell.textContent = t('admin.inventory.noItemsFound', 'Aucun article d\'inventaire trouvé.');
            return;
        }

        items.forEach(item => {
            let displayProductName = item.product_name_fr || item.product_name || notApplicable;
            // If you want to show both FR/EN when different:
            // if (item.product_name_fr && item.product_name_en && item.product_name_fr.toLowerCase() !== item.product_name_en.toLowerCase()) {
            //     displayProductName = `${item.product_name_fr} / ${item.product_name_en}`;
            // }

            const row = tableBody.insertRow();
            row.setAttribute('data-item-uid', item.item_uid);
            row.classList.add('hover:bg-slate-50', 'cursor-default'); 
            
            row.insertCell().textContent = displayProductName;
            row.insertCell().textContent = item.variant_name || notApplicable; // This likely comes from a join like "250g (250G-FR)"
            row.insertCell().textContent = item.product_code || notApplicable;
            row.insertCell().textContent = item.variant_sku_suffix || notApplicable; // New Column Data
            row.insertCell().textContent = item.item_uid || notApplicable;
            
            const statusCell = row.insertCell();
            const statusEnum = item.status?.value || item.status || 'unknown'; // Handle if status is already enum or string
            statusCell.innerHTML = `<span class="status-indicator status-${statusEnum.replace('_', '-')}">${t('admin.inventory.status.' + statusEnum, statusEnum)}</span>`;


            row.insertCell().textContent = item.batch_number || notApplicable;
            row.insertCell().textContent = item.production_date ? new Date(item.production_date).toLocaleDateString(currentLocale) : notApplicable;
            row.insertCell().textContent = item.expiry_date ? new Date(item.expiry_date).toLocaleDateString(currentLocale) : notApplicable;
            row.insertCell().textContent = item.received_at ? new Date(item.received_at).toLocaleString(currentLocale) : notApplicable;
        });
    }

    /**
     * Applies filters to the inventory table.
     */
    function applyFilters() {
        const productNameFilter = filterProductNameInput.value.toLowerCase();
        const productCodeFilter = filterProductCodeInput.value.toLowerCase();
        const variantSkuSuffixFilter = filterVariantSkuSuffixInput.value.toLowerCase(); // Added
        const itemStatusFilter = filterItemStatusSelect.value;
        const itemUidFilter = searchItemUidInput.value.toLowerCase();

        const filteredItems = allInventoryItems.filter(item => {
            const productNameMatch = !productNameFilter ||
                (item.product_name && item.product_name.toLowerCase().includes(productNameFilter)) ||
                (item.product_name_fr && item.product_name_fr.toLowerCase().includes(productNameFilter)) ||
                (item.product_name_en && item.product_name_en.toLowerCase().includes(productNameFilter));
            const productCodeMatch = !productCodeFilter || (item.product_code && item.product_code.toLowerCase().includes(productCodeFilter));
            const variantSkuSuffixMatch = !variantSkuSuffixFilter || (item.variant_sku_suffix && item.variant_sku_suffix.toLowerCase().includes(variantSkuSuffixFilter)); // Added
            const itemStatusMatch = !itemStatusFilter || (item.status?.value || item.status) === itemStatusFilter; // Handle if status is enum
            const itemUidMatch = !itemUidFilter || (item.item_uid && item.item_uid.toLowerCase().includes(itemUidFilter));
            
            return !!(productNameMatch && productCodeMatch && variantSkuSuffixMatch && itemStatusMatch && itemUidMatch); 
        });
        renderInventoryTable(filteredItems);
    }

    // --- Event Listeners for Filters ---
    if (filterProductNameInput) filterProductNameInput.addEventListener('input', applyFilters);
    if (filterProductCodeInput) filterProductCodeInput.addEventListener('input', applyFilters);
    if (filterVariantSkuSuffixInput) filterVariantSkuSuffixInput.addEventListener('input', applyFilters); // Added
    if (filterItemStatusSelect) filterItemStatusSelect.addEventListener('change', applyFilters);
    if (searchItemUidInput) searchItemUidInput.addEventListener('input', applyFilters);

    // --- Event Listener for Export CSV ---
    if (exportCsvButton) {
        exportCsvButton.addEventListener('click', async () => {
            if (typeof showAdminToast === 'function') showAdminToast(t('admin.inventory.export.generatingCsv', 'Génération du CSV...'), "info");
            try {
                // Using adminApi.js for consistency if it has a method for this,
                // otherwise direct window.location.href is fine for GET requests that trigger download.
                // adminApi.js does not seem to have a direct export method that handles blob response yet.
                const exportUrl = `${API_BASE_URL}/inventory/export/serialized_items`; // API_BASE_URL from admin_config.js
                const token = getAdminAuthToken(); // from admin_auth.js
                
                // Fetch with token if necessary for the endpoint
                const response = await fetch(exportUrl, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ message: 'Unknown export error' }));
                    throw new Error(errorData.message || `Export failed: ${response.status}`);
                }

                const blob = await response.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                a.download = `maison_truvra_serialized_inventory_${timestamp}.csv`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(downloadUrl);

                if (typeof showAdminToast === 'function') showAdminToast(t('admin.inventory.export.requestSent', 'Exportation CSV démarrée.'), "success", 3000);
            } catch (error) {
                console.error("Erreur lors de la tentative d'export CSV:", error);
                if (typeof showAdminToast === 'function') showAdminToast(t('admin.inventory.export.generationFailed', 'Échec génération CSV.') + ` ${error.message}`, "error");
            }
        });
    }

    // --- Event Listener for Import CSV ---
    if (importCsvButton && importCsvFileInput) {
        importCsvButton.addEventListener('click', async () => {
            const file = importCsvFileInput.files[0];
            if (!file) {
                if (typeof showAdminToast === 'function') showAdminToast(t('admin.inventory.import.noFileSelected', 'Aucun fichier sélectionné.'), "warning");
                return;
            }
            if (!file.name.endsWith('.csv')) {
                if (typeof showAdminToast === 'function') showAdminToast(t('admin.inventory.import.invalidFileType', 'Type de fichier invalide. Veuillez sélectionner un CSV.'), "error");
                return;
            }

            const formData = new FormData();
            formData.append('file', file);

            if (typeof showAdminToast === 'function') showAdminToast(t('admin.inventory.import.processing', 'Traitement de l\'importation CSV...'), "info");
            importCsvButton.disabled = true;
            importCsvButton.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> ${t('admin.inventory.import.processing', 'Traitement...')}`;


            try {
                const response = await adminApi.importSerializedItemsCsv(formData); // Assumes adminApi.js has this method
                handleImportResponse(response);
            } catch (error) {
                 console.error("Error during CSV import:", error);
                const errorMsg = error.data?.message || error.message || t('admin.inventory.import.unknownError', 'Erreur inconnue pendant l\'importation.');
                if (typeof showAdminToast === 'function') {
                    showAdminToast(t('admin.inventory.import.failed', 'Échec importation: ') + errorMsg, "error", 8000);
                }
                if (error.data?.failed_rows) {
                     console.error("Import failures details:", error.data.failed_rows);
                }
            } finally {
                importCsvButton.disabled = false;
                importCsvButton.innerHTML = `<i class="fas fa-file-upload mr-2"></i> Importer`;
                if (importCsvFileInput) importCsvFileInput.value = ''; // Clear file input
            }
        });
    }

    /**
     * Handles the response from the CSV import API call.
     * @param {object} response - The API response object.
     */
    function handleImportResponse(response) {
        if (response && response.success) {
            let message = t('admin.inventory.import.processedSuccess', 'Importation réussie: {imported} importés, {updated} mis à jour sur {total} traités.', { 
                imported: response.imported, 
                updated: response.updated, 
                total: response.total_processed 
            });
            if (response.failed_rows && response.failed_rows.length > 0) {
                message += ` ${t('admin.inventory.import.failuresCount', '{count} lignes en échec.', { count: response.failed_rows.length })}`;
                console.warn("Détails des échecs d'importation:", response.failed_rows);
                // Optionally display these failures in a more user-friendly way
            }
            if (typeof showAdminToast === 'function') showAdminToast(message, "success", 8000);
            fetchDetailedInventory(); 
        } else {
            const errorMsg = response?.message || t('admin.inventory.import.unknownError', 'Erreur inconnue pendant l\'importation.');
            if (typeof showAdminToast === 'function') showAdminToast(t('admin.inventory.import.failed', 'Échec importation: ') + errorMsg, "error", 8000);
            if (response?.failed_rows) {
                 console.error("Détails des échecs d'importation:", response.failed_rows);
            }
        }
    }

    // --- Tooltip Logic ---
    if (!tableBody || !tooltip) {
        console.warn('Inventory table body or tooltip element not found. Product overview feature will be limited.');
    } else {
        tableBody.addEventListener('mouseover', (event) => {
            const row = event.target.closest('tr[data-item-uid]');
            if (!row) return;

            const itemUid = row.dataset.itemUid;
            const itemData = allInventoryItems.find(item => String(item.item_uid) === String(itemUid));

            if (itemData) {
                const productionDateStr = itemData.production_date ? new Date(itemData.production_date).toLocaleDateString(currentLocale) : notApplicable;
                const expiryDateStr = itemData.expiry_date ? new Date(itemData.expiry_date).toLocaleDateString(currentLocale) : notApplicable;
                const receivedDateStr = itemData.received_at ? new Date(itemData.received_at).toLocaleDateString(currentLocale) : notApplicable;

                let tooltipProductName = itemData.product_name_fr || itemData.product_name || notApplicable;
                // if (itemData.product_name_fr && itemData.product_name_en && itemData.product_name_fr.toLowerCase() !== itemData.product_name_en.toLowerCase()) {
                //    tooltipProductName = `${itemData.product_name_fr} / ${itemData.product_name_en}`;
                // }
                
                tooltip.innerHTML = ''; 

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

                addTooltipRow('admin.inventory.tooltip.uid', itemData.item_uid || notApplicable);
                addTooltipRow('admin.inventory.tooltip.productCode', itemData.product_code || notApplicable);
                addTooltipRow('admin.inventory.tooltip.status', t('admin.inventory.status.' + (itemData.status?.value || itemData.status || 'unknown'), itemData.status?.value || itemData.status || 'unknown'));
                addTooltipRow('admin.inventory.tooltip.batch', itemData.batch_number || notApplicable);
                addTooltipRow('admin.inventory.tooltip.prodDate', productionDateStr);
                addTooltipRow('admin.inventory.tooltip.expDate', expiryDateStr);
                addTooltipRow('admin.inventory.tooltip.receivedOn', receivedDateStr);
                
                tooltip.appendChild(gridDiv);
                tooltip.classList.remove('hidden');

                // Position tooltip (consider viewport edges)
                const tooltipRect = tooltip.getBoundingClientRect();
                let finalLeft = event.pageX + 15;
                let finalTop = event.pageY + 15;

                if (event.clientX + 15 + tooltipRect.width > window.innerWidth) {
                    finalLeft = event.pageX - tooltipRect.width - 15;
                }
                if (event.clientY + 15 + tooltipRect.height > window.innerHeight) {
                    finalTop = event.pageY - tooltipRect.height - 15;
                }
                tooltip.style.left = `${Math.max(5, finalLeft)}px`;
                tooltip.style.top = `${Math.max(5, finalTop)}px`;
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
    }

    // --- Initial Load ---
    fetchDetailedInventory();

    // If admin_main.js handles common UI setup like header/nav, this might not be needed here
    // or can be page-specific additions. For now, assuming admin_main.js handles common parts.
    if (typeof setupAdminUIGlobals === 'function') {
        // setupAdminUIGlobals(); // Called by admin_main.js after header is loaded
    } else {
        console.warn('setupAdminUIGlobals function is not defined.');
    }
});
