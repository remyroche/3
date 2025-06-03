// website/source/admin/js/admin_dashboard.js
// This script will handle the logic for the main admin_dashboard.html page.

document.addEventListener('DOMContentLoaded', function() {
    console.log('Admin Dashboard script loaded.');

    // --- DOM Element References for Summary Cards ---
    const totalProductsCardP = document.querySelector('#totalProductsCard p');
    const totalCategoriesCardP = document.querySelector('#totalCategoriesCard p');
    const pendingOrdersCardP = document.querySelector('#pendingOrdersCard p');
    const totalUsersCardP = document.querySelector('#totalUsersCard p');// website/source/admin/js/admin_dashboard.js
// This script will handle the logic for the main admin_dashboard.html page.

document.addEventListener('DOMContentLoaded', function() {
    console.log('Admin Dashboard script loaded.');

    // --- DOM Element References for Summary Cards ---
    const totalProductsCardP = document.querySelector('#totalProductsCard p');
    const totalCategoriesCardP = document.querySelector('#totalCategoriesCard p');
    const pendingOrdersCardP = document.querySelector('#pendingOrdersCard p');
    const totalUsersCardP = document.querySelector('#totalUsersCard p');
    const pendingB2BAppsCardP = document.querySelector('#pendingB2BAppsCard p'); 

    /**
     * Fetches and displays summary data for the dashboard using the single stats endpoint.
     */
    async function loadDashboardSummaries() {
        const loadingText = 'Loading...'; // XSS: static text
        if (totalProductsCardP) totalProductsCardP.textContent = loadingText;
        if (totalCategoriesCardP) totalCategoriesCardP.textContent = loadingText;
        if (pendingOrdersCardP) pendingOrdersCardP.textContent = loadingText;
        if (totalUsersCardP) totalUsersCardP.textContent = loadingText;
        if (pendingB2BAppsCardP) pendingB2BAppsCardP.textContent = loadingText;

        try {
            const response = await adminApi.getDashboardStats(); 
            
            if (response && response.success && response.stats) {
                const stats = response.stats;
                // XSS: All these are numbers or N/A, safe for textContent
                if (totalProductsCardP) totalProductsCardP.textContent = stats.total_products !== undefined ? stats.total_products : 'N/A';
                if (totalCategoriesCardP) totalCategoriesCardP.textContent = stats.total_categories !== undefined ? stats.total_categories : 'N/A';
                if (pendingOrdersCardP) pendingOrdersCardP.textContent = stats.pending_orders !== undefined ? stats.pending_orders : 'N/A';
                if (totalUsersCardP) totalUsersCardP.textContent = stats.total_users !== undefined ? stats.total_users : 'N/A';
                if (pendingB2BAppsCardP) pendingB2BAppsCardP.textContent = stats.pending_b2b_applications !== undefined ? stats.pending_b2b_applications : 'N/A';
                
                const pendingOrdersLink = document.querySelector('#pendingOrdersCard a');
                if (pendingOrdersLink && stats.pending_orders === 0) {
                    // Example: pendingOrdersLink.textContent = "No Pending Orders"; // XSS: static text
                }

            } else {
                // Error toast handled by adminApi
                const errorText = 'Error'; // XSS: static text
                if (totalProductsCardP) totalProductsCardP.textContent = errorText;
                if (totalCategoriesCardP) totalCategoriesCardP.textContent = errorText;
                if (pendingOrdersCardP) pendingOrdersCardP.textContent = errorText;
                if (totalUsersCardP) totalUsersCardP.textContent = errorText;
                if (pendingB2BAppsCardP) pendingB2BAppsCardP.textContent = errorText;
            }
        } catch (error) {
            console.error('Failed to load dashboard summaries:', error);
            // Error toast handled by adminApi
            const apiErrorText = 'API Error'; // XSS: static text
            if (totalProductsCardP) totalProductsCardP.textContent = apiErrorText;
            if (totalCategoriesCardP) totalCategoriesCardP.textContent = apiErrorText;
            if (pendingOrdersCardP) pendingOrdersCardP.textContent = apiErrorText;
            if (totalUsersCardP) totalUsersCardP.textContent = apiErrorText;
            if (pendingB2BAppsCardP) pendingB2BAppsCardP.textContent = apiErrorText;
        }
    }

    // --- Initialization ---
    if (typeof adminApi !== 'undefined' && typeof adminApi.getDashboardStats === 'function') {
        loadDashboardSummaries();
    } else {
        console.error('adminApi or adminApi.getDashboardStats is not defined. Ensure admin_api.js is loaded correctly.');
        const errorText = 'API Error'; // XSS: static text
        if (totalProductsCardP) totalProductsCardP.textContent = errorText;
        if (totalCategoriesCardP) totalCategoriesCardP.textContent = errorText;
        if (pendingOrdersCardP) pendingOrdersCardP.textContent = errorText;
        if (totalUsersCardP) totalUsersCardP.textContent = errorText;
        if (pendingB2BAppsCardP) pendingB2BAppsCardP.textContent = errorText;
    }
    
    const adminUserForGreetingMain = typeof getAdminUser === 'function' ? getAdminUser() : null;
    const greetingMainElement = document.getElementById('admin-user-greeting-main');
    if (greetingMainElement && adminUserForGreetingMain) {
        greetingMainElement.textContent = `${adminUserForGreetingMain.prenom || 'Admin'}`; // XSS: name/email is generally safe
    } else if (greetingMainElement) {
        greetingMainElement.textContent = 'Admin'; // XSS: static text
    }
});
