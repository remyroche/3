// website/source/admin/js/admin_dashboard.js
// This script will handle the logic for the main admin_dashboard.html page.

document.addEventListener('DOMContentLoaded', function() {
    console.log('Admin Dashboard script loaded.');

    // --- DOM Element References for Summary Cards ---
    const totalProductsCardP = document.querySelector('#totalProductsCard p');
    const totalCategoriesCardP = document.querySelector('#totalCategoriesCard p');
    const pendingOrdersCardP = document.querySelector('#pendingOrdersCard p');
    const totalUsersCardP = document.querySelector('#totalUsersCard p');

    /**
     * Fetches and displays summary data for the dashboard.
     */
    async function loadDashboardSummaries() {
        // Fetch Total Products
        try {
            if (totalProductsCardP) {
                const products = await adminApi.getProducts(); // Assuming getProducts returns all products
                totalProductsCardP.textContent = products.length;
            }
        } catch (error) {
            console.error('Failed to load total products:', error);
            if (totalProductsCardP) totalProductsCardP.textContent = 'Error';
        }

        // Fetch Total Categories
        try {
            if (totalCategoriesCardP) {
                const categories = await adminApi.getCategories();
                totalCategoriesCardP.textContent = categories.length;
            }
        } catch (error) {
            console.error('Failed to load total categories:', error);
            if (totalCategoriesCardP) totalCategoriesCardP.textContent = 'Error';
        }

        // Fetch Pending Orders
        try {
            if (pendingOrdersCardP) {
                // Assuming getOrders can be filtered by status, or you filter client-side
                // For this example, let's say getOrders returns all and we filter here (less efficient for large datasets)
                const orders = await adminApi.getOrders({ status: 'pending' }); // Or fetch all and filter
                // If your API directly supports ?status=pending and returns a count or filtered list:
                // const pendingOrdersResult = await adminApi.getOrders({ status: 'pending' });
                // pendingOrdersCardP.textContent = pendingOrdersResult.total_count || pendingOrdersResult.length;
                
                // Placeholder if API doesn't directly filter by count:
                // This count might be inaccurate if getOrders doesn't filter by status in the backend for this call.
                // A dedicated API endpoint /api/admin/orders/summary or /api/admin/orders/count?status=pending would be better.
                pendingOrdersCardP.textContent = orders.length > 0 ? orders.length : '0'; // Example if orders is the filtered list
                 if (orders.length === 0 && !error) pendingOrdersCardP.textContent = '0';


            }
        } catch (error) {
            console.error('Failed to load pending orders:', error);
             if (pendingOrdersCardP) pendingOrdersCardP.textContent = 'Error';
        }

        // Fetch Total Users
        try {
            if (totalUsersCardP) {
                const users = await adminApi.getUsers();
                totalUsersCardP.textContent = users.length;
            }
        } catch (error) {
            console.error('Failed to load total users:', error);
            if (totalUsersCardP) totalUsersCardP.textContent = 'Error';
        }
    }

    // --- Initialization ---
    if (typeof adminApi !== 'undefined') { // Check if adminApi is loaded
        loadDashboardSummaries();
    } else {
        console.error('adminApi is not defined. Ensure admin_api.js is loaded before admin_dashboard.js');
        if (totalProductsCardP) totalProductsCardP.textContent = 'API Error';
        if (totalCategoriesCardP) totalCategoriesCardP.textContent = 'API Error';
        if (pendingOrdersCardP) pendingOrdersCardP.textContent = 'API Error';
        if (totalUsersCardP) totalUsersCardP.textContent = 'API Error';
    }

    // Add any other dashboard-specific JavaScript logic here,
    // e.g., chart initializations, real-time updates, etc.
});