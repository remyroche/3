// website/source/admin/js/admin_dashboard.js
// This script will handle the logic for the main admin_dashboard.html page.

document.addEventListener('DOMContentLoaded', function() {
    console.log('Admin Dashboard script loaded.');

    // --- DOM Element References for Summary Cards ---
    const totalProductsCardP = document.querySelector('#totalProductsCard p');
    const totalCategoriesCardP = document.querySelector('#totalCategoriesCard p');
    const pendingOrdersCardP = document.querySelector('#pendingOrdersCard p');
    const totalUsersCardP = document.querySelector('#totalUsersCard p');
    // Add new card for B2B applications if it exists in HTML
    const pendingB2BAppsCardP = document.querySelector('#pendingB2BAppsCard p'); // Example ID

    /**
     * Fetches and displays summary data for the dashboard using the single stats endpoint.
     */
    async function loadDashboardSummaries() {
        // Set loading text for all cards
        if (totalProductsCardP) totalProductsCardP.textContent = 'Loading...';
        if (totalCategoriesCardP) totalCategoriesCardP.textContent = 'Loading...';
        if (pendingOrdersCardP) pendingOrdersCardP.textContent = 'Loading...';
        if (totalUsersCardP) totalUsersCardP.textContent = 'Loading...';
        if (pendingB2BAppsCardP) pendingB2BAppsCardP.textContent = 'Loading...';

        try {
            // adminApi.getDashboardStats() is defined in admin_api.js
            const response = await adminApi.getDashboardStats(); 
            
            if (response && response.success && response.stats) {
                const stats = response.stats;
                if (totalProductsCardP) totalProductsCardP.textContent = stats.total_products !== undefined ? stats.total_products : 'N/A';
                if (totalCategoriesCardP) totalCategoriesCardP.textContent = stats.total_categories !== undefined ? stats.total_categories : 'N/A';
                if (pendingOrdersCardP) pendingOrdersCardP.textContent = stats.pending_orders !== undefined ? stats.pending_orders : 'N/A';
                if (totalUsersCardP) totalUsersCardP.textContent = stats.total_users !== undefined ? stats.total_users : 'N/A';
                if (pendingB2BAppsCardP) pendingB2BAppsCardP.textContent = stats.pending_b2b_applications !== undefined ? stats.pending_b2b_applications : 'N/A';
                
                // Update links if needed, e.g., if count is 0, link might be disabled or text changed
                const pendingOrdersLink = document.querySelector('#pendingOrdersCard a');
                if (pendingOrdersLink && stats.pending_orders === 0) {
                    // Example: pendingOrdersLink.textContent = "No Pending Orders";
                    // pendingOrdersLink.href = "#"; // Or disable
                }

            } else {
                const errorMsg = response?.message || 'Failed to load dashboard data.';
                showAdminToast(errorMsg, 'error');
                if (totalProductsCardP) totalProductsCardP.textContent = 'Error';
                if (totalCategoriesCardP) totalCategoriesCardP.textContent = 'Error';
                if (pendingOrdersCardP) pendingOrdersCardP.textContent = 'Error';
                if (totalUsersCardP) totalUsersCardP.textContent = 'Error';
                if (pendingB2BAppsCardP) pendingB2BAppsCardP.textContent = 'Error';
            }
        } catch (error) {
            console.error('Failed to load dashboard summaries:', error);
            showAdminToast(error.message || 'Error fetching dashboard data.', 'error');
            if (totalProductsCardP) totalProductsCardP.textContent = 'API Error';
            if (totalCategoriesCardP) totalCategoriesCardP.textContent = 'API Error';
            if (pendingOrdersCardP) pendingOrdersCardP.textContent = 'API Error';
            if (totalUsersCardP) totalUsersCardP.textContent = 'API Error';
            if (pendingB2BAppsCardP) pendingB2BAppsCardP.textContent = 'API Error';
        }
    }

    // --- Initialization ---
    if (typeof adminApi !== 'undefined' && typeof adminApi.getDashboardStats === 'function') {
        loadDashboardSummaries();
    } else {
        console.error('adminApi or adminApi.getDashboardStats is not defined. Ensure admin_api.js is loaded correctly.');
        // Display error on all cards if API object is missing
        const errorText = 'API Error';
        if (totalProductsCardP) totalProductsCardP.textContent = errorText;
        if (totalCategoriesCardP) totalCategoriesCardP.textContent = errorText;
        if (pendingOrdersCardP) pendingOrdersCardP.textContent = errorText;
        if (totalUsersCardP) totalUsersCardP.textContent = errorText;
        if (pendingB2BAppsCardP) pendingB2BAppsCardP.textContent = errorText;
    }

    // Add any other dashboard-specific JavaScript logic here,
    // e.g., chart initializations, real-time updates, etc.
    
    // Ensure admin user greeting is populated (if admin_main.js doesn't handle it early enough for this specific element)
    const adminUserForGreetingMain = typeof getAdminUser === 'function' ? getAdminUser() : null;
    const greetingMainElement = document.getElementById('admin-user-greeting-main');
    if (greetingMainElement && adminUserForGreetingMain) {
        greetingMainElement.textContent = `${adminUserForGreetingMain.prenom || 'Admin'}`;
    } else if (greetingMainElement) {
        greetingMainElement.textContent = 'Admin'; // Fallback
    }
});
