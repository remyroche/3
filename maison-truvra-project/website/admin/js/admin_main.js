// website/admin/js/admin_main.js
// Main script for initializing the Admin Panel and page-specific logic.

document.addEventListener('DOMContentLoaded', () => {
    // --- Global Admin Initializations ---
    
    // If on login page, attach login handler and skip other initializations
    if (window.location.pathname.includes('admin_login.html')) {
        const adminLoginForm = document.getElementById('admin-login-form');
        if (adminLoginForm) {
            adminLoginForm.addEventListener('submit', handleAdminLoginFormSubmit); // from admin_auth.js
        }
        // Redirect if already logged in as admin and trying to access login page
        const token = sessionStorage.getItem('adminAuthToken');
        const adminUser = token ? JSON.parse(sessionStorage.getItem('adminUser')) : null;
        if (token && adminUser && adminUser.is_admin) {
            window.location.href = 'admin_dashboard.html';
        }
        return; // Stop further execution for login page
    }

    // For all other admin pages, check login status first
    if (!checkAdminLogin()) { // from admin_auth.js
        return; // checkAdminLogin will redirect if not logged in
    }

    // Common elements for all admin pages (except login)
    const logoutButton = document.getElementById('admin-logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', adminLogout); // from admin_auth.js
    }
    
    // Set active navigation link
    const currentPage = window.location.pathname.split("/").pop();
    document.querySelectorAll('.admin-nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === currentPage) {
            link.classList.add('active');
        }
    });

    // --- Page-Specific Initializations ---
    const bodyId = document.body.id; // Assuming body IDs are set e.g. <body id="page-admin-dashboard">

    if (bodyId === 'page-admin-dashboard' || window.location.pathname.endsWith('admin_dashboard.html')) {
        initializeAdminDashboard(); // New function to encapsulate dashboard specific setup
    } else if (bodyId === 'page-admin-manage-products' || window.location.pathname.endsWith('admin_manage_products.html')) {
        initializeProductManagement(); // from admin_products.js
    } else if (bodyId === 'page-admin-manage-inventory' || window.location.pathname.endsWith('admin_manage_inventory.html')) {
        initializeInventoryManagement(); // from admin_inventory.js
    } else if (bodyId === 'page-admin-manage-users' || window.location.pathname.endsWith('admin_manage_users.html')) {
        initializeUserManagement(); // from admin_users.js
    } else if (bodyId === 'page-admin-manage-orders' || window.location.pathname.endsWith('admin_manage_orders.html')) {
        initializeOrderManagement(); // from admin_orders.js
    }

    // --- Admin Modal Global Event Listeners ---
    document.querySelectorAll('.admin-modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', function(event) {
            if (event.target === this) { // Clicked on overlay, not content
                closeAdminModal(this.id); // from admin_ui.js
            }
        });
    });
    
    // Close button for the generic modal (if one exists with this ID)
    const genericModalCloseButton = document.getElementById('close-generic-modal-button');
    if (genericModalCloseButton) {
        genericModalCloseButton.addEventListener('click', () => closeAdminModal('generic-modal'));
    }
});

/**
 * Initializes the admin dashboard page.
 */
function initializeAdminDashboard() {
    loadDashboardStats(); // from admin_dashboard.js
    // Add any other dashboard-specific event listeners or setup here
}
