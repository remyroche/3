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
    const searchItemUidInput = document.getElementById('search-view-item-uid');

    let allInventoryItems = []; // To store all fetched items for client-side filtering

    async function fetchDetailedInventory() {
        if (!tableBody) {
            console.error('Table body for detailed inventory not found.');
            return;
        }
        tableBody.innerHTML = '<tr><td colspan="8" class="text-center p-4">Chargement de l\'inventaire détaillé...</td></tr>';

        try {
            const response = await adminAPI.get('/inventory/items/detailed'); // Assuming this endpoint provides all necessary details
            if (response.success && Array.isArray(response.data)) {
                allInventoryItems = response.data;
                renderInventoryTable(allInventoryItems);
            } else {
                tableBody.innerHTML = `<tr><td colspan="8" class="text-center p-4">Erreur: ${response.message || 'Impossible de charger les données.'}</td></tr>`;
                adminUI.showToast('Erreur lors du chargement de l\'inventaire: ' + (response.message || 'Réponse invalide du serveur'), 'error');
            }
        } catch (error) {
            console.error('Error fetching detailed inventory:', error);
            tableBody.innerHTML = '<tr><td colspan="8" class="text-center p-4">Erreur de connexion au serveur.</td></tr>';
            adminUI.showToast('Erreur de connexion pour charger l\'inventaire.', 'error');
        }
    }

    function renderInventoryTable(items) {
        if (!tableBody) return;
        tableBody.innerHTML = ''; // Clear existing rows

        if (items.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="8" class="text-center p-4">Aucun article d\'inventaire trouvé.</td></tr>';
            return;
        }

        items.forEach(item => {
            const row = tableBody.insertRow();
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${item.product_name || 'N/A'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${item.variant_name || 'N/A'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono">${item.item_uid}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${item.status || 'N/A'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${item.batch_number || 'N/A'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${item.production_date ? new Date(item.production_date).toLocaleDateString() : 'N/A'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${item.expiry_date ? new Date(item.expiry_date).toLocaleDateString() : 'N/A'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${item.received_at ? new Date(item.received_at).toLocaleString() : 'N/A'}</td>
            `;
        });
    }

    function applyFilters() {
        const productNameFilter = filterProductNameInput.value.toLowerCase();
        const itemStatusFilter = filterItemStatusSelect.value;
        const itemUidFilter = searchItemUidInput.value.toLowerCase();

        const filteredItems = allInventoryItems.filter(item => {
            const productNameMatch = !productNameFilter || (item.product_name && item.product_name.toLowerCase().includes(productNameFilter));
            const itemStatusMatch = !itemStatusFilter || item.status === itemStatusFilter;
            const itemUidMatch = !itemUidFilter || (item.item_uid && item.item_uid.toLowerCase().includes(itemUidFilter));
            
            return productNameMatch && itemStatusMatch && itemUidMatch;
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
    if (searchItemUidInput) {
        searchItemUidInput.addEventListener('input', applyFilters);
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
});