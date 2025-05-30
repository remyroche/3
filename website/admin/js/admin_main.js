// website/admin/js/admin_main.js
// Main script for initializing the Admin Panel and page-specific logic.

document.addEventListener('DOMContentLoaded', () => {
    console.log("admin_main.js: DOMContentLoaded");

    // --- Global Admin Initializations ---
    const bodyId = document.body.id;
    const pagePath = window.location.pathname;

    // If on login page, attach login handler and skip other initializations
    if (bodyId === 'page-admin-login' || pagePath.endsWith('admin_login.html')) {
        console.log("admin_main.js: On admin_login.html");
        // Ensure body of admin_login.html has id="page-admin-login" for consistency
        const adminLoginForm = document.getElementById('admin-login-form');
        if (adminLoginForm) {
            if (typeof handleAdminLoginFormSubmit === 'function') {
                adminLoginForm.addEventListener('submit', handleAdminLoginFormSubmit);
            } else {
                console.error("admin_main.js: handleAdminLoginFormSubmit function not found. Ensure admin_auth.js is loaded.");
            }
        }
        // Redirect if already logged in as admin and trying to access login page
        if (typeof getAdminAuthToken === 'function' && typeof getAdminUser === 'function') {
            const token = getAdminAuthToken();
            const adminUser = getAdminUser();
            if (token && adminUser && adminUser.is_admin) {
                console.log("admin_main.js: Admin already logged in, redirecting to dashboard.");
                window.location.href = 'admin_dashboard.html';
            }
        } else {
            console.error("admin_main.js: getAdminAuthToken or getAdminUser functions not found. Ensure admin_auth.js is loaded.");
        }
        return; // Stop further execution for login page
    }

    // For all other admin pages, check login status first
    if (typeof checkAdminLogin === 'function') {
        if (!checkAdminLogin()) {
            console.log("admin_main.js: Admin not logged in, checkAdminLogin will redirect.");
            return; // checkAdminLogin will redirect if not logged in
        }
    } else {
        console.error("admin_main.js: checkAdminLogin function not found. Site protection compromised. Ensure admin_auth.js is loaded.");
        // Potentially redirect to login manually as a fallback, or show an error
        // window.location.href = 'admin_login.html'; 
        return;
    }

    // Common elements for all admin pages (except login)
    const logoutButton = document.getElementById('admin-logout-button');
    if (logoutButton) {
        if (typeof adminLogout === 'function') {
            logoutButton.addEventListener('click', adminLogout);
        } else {
            console.error("admin_main.js: adminLogout function not found. Ensure admin_auth.js is loaded.");
        }
    }

    // Handle "Back to Dashboard" button visibility
    const backToDashboardButton = document.getElementById('back-to-dashboard-button');
    if (backToDashboardButton) { // Assumes admin_dashboard.html has body id="page-admin-dashboard"
        if (bodyId === 'page-admin-dashboard' || pagePath.endsWith('admin_dashboard.html')) {
            backToDashboardButton.style.display = 'none'; // Hide on dashboard page
        } else {
            backToDashboardButton.style.display = 'inline-flex'; // Or 'inline-block' based on your styling
        }
    }
    
    // Set active navigation link
    const currentPage = window.location.pathname.split("/").pop();
    document.querySelectorAll('.admin-nav-link').forEach(link => {
        link.classList.remove('active');
        // Ensure href attribute exists before comparing
        const linkHref = link.getAttribute('href');
        if (linkHref && linkHref === currentPage) {
            link.classList.add('active');
        }
    });

    // --- Page-Specific Initializations ---
    // Prefer bodyId for page identification. Fallback to pagePath.endsWith for pages not yet updated with body IDs.
    // For this to work consistently, ensure each admin page has a unique body ID like id="page-admin-manage-products".

    if (bodyId === 'page-admin-dashboard' || pagePath.endsWith('admin_dashboard.html')) {
        console.log("admin_main.js: Admin Dashboard page. Initialization handled by admin_dashboard.js.");
        // No specific function call needed here as admin_dashboard.js handles its own init.
    } else if (bodyId === 'page-admin-manage-products' || pagePath.endsWith('admin_manage_products.html')) {
        console.log("admin_main.js: Initializing Product Management page.");
        if (typeof initializeProductManagement === 'function') initializeProductManagement();
        else console.error("admin_main.js: initializeProductManagement not found. Ensure admin_products.js is loaded.");
    } else if (bodyId === 'page-admin-manage-inventory' || pagePath.endsWith('admin_manage_inventory.html')) {
        console.log("admin_main.js: Initializing Inventory Management page.");
        if (typeof initializeInventoryManagement === 'function') initializeInventoryManagement();
        else console.error("admin_main.js: initializeInventoryManagement not found. Ensure admin_inventory.js is loaded.");
    } else if (bodyId === 'page-admin-manage-users' || pagePath.endsWith('admin_manage_users.html')) {
        console.log("admin_main.js: Initializing User Management page.");
        if (typeof initializeUserManagement === 'function') initializeUserManagement();
        else console.error("admin_main.js: initializeUserManagement not found. Ensure admin_users.js is loaded.");
    } else if (bodyId === 'page-admin-manage-orders' || pagePath.endsWith('admin_manage_orders.html')) {
        console.log("admin_main.js: Initializing Order Management page.");
        if (typeof initializeOrderManagement === 'function') initializeOrderManagement();
        else console.error("admin_main.js: initializeOrderManagement not found. Ensure admin_orders.js is loaded.");
    } else if (bodyId === 'page-admin-panel' || pagePath.endsWith('admin_panel.html')) {
        console.log("admin_main.js: Admin Panel main page.");
        // Any specific initializations for admin_panel.html itself
    }

    // --- Admin Modal Global Event Listeners ---
    document.querySelectorAll('.admin-modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', function(event) {
            if (event.target === this) { // Clicked on overlay, not content
                if (typeof closeAdminModal === 'function') {
                    // Assuming the modal itself has the ID, not just the overlay
                    // This might need adjustment based on your modal structure.
                    // If the overlay's ID is the modal's ID, this is fine.
                    // If the modal is a child, you might need to find its ID.
                    const modalId = this.dataset.modalId || this.id; // Prefer a data attribute if overlay ID is different
                    closeAdminModal(modalId); 
                } else {
                    console.error("admin_main.js: closeAdminModal function not found. Ensure admin_ui.js is loaded.");
                }
            }
        });
    });
    
    // Close button for the generic modal (if one exists with this ID)
    const genericModalCloseButton = document.getElementById('close-generic-modal-button');
    if (genericModalCloseButton && typeof closeAdminModal === 'function') {
        genericModalCloseButton.addEventListener('click', () => closeAdminModal('generic-modal'));
    }
});
