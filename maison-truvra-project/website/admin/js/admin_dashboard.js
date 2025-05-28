// website/admin/js/admin_dashboard.js
// Logic specific to the Admin Dashboard page.

/**
 * Loads and displays statistics on the admin dashboard.
 */
async function loadDashboardStats() {
    try {
        // adminApiRequest is from admin_api.js
        const products = await adminApiRequest('/products'); // Assuming this endpoint lists all products for admin
        const totalProductsEl = document.getElementById('stats-total-products');
        if (totalProductsEl) totalProductsEl.textContent = products.length || 0;

        // Mock other stats until backend endpoints are fully ready or specified for dashboard
        const recentOrdersEl = document.getElementById('stats-recent-orders');
        if (recentOrdersEl) recentOrdersEl.textContent = 'N/A'; // Placeholder - needs specific endpoint

        const newUsersEl = document.getElementById('stats-new-users');
        if (newUsersEl) newUsersEl.textContent = 'N/A'; // Placeholder - needs specific endpoint

        // Example: Fetch recent orders (if endpoint exists)
        // const orders = await adminApiRequest('/orders?limit=5&status=Paid&days=1');
        // if (recentOrdersEl && orders) recentOrdersEl.textContent = orders.length || 0;

    } catch (error) {
        console.error("Erreur chargement stats dashboard:", error);
        showAdminToast("Impossible de charger les statistiques du tableau de bord.", "error"); // Assumes showAdminToast from admin_ui.js
    }
}
