// website/admin/js/admin_main.js
// Main script for initializing the Admin Panel and page-specific logic.

document.addEventListener('DOMContentLoaded', () => {
    console.log("admin_main.js: DOMContentLoaded");

    // --- Global Admin Initializations ---
    const bodyId = document.body.id;
    const pagePath = window.location.pathname;

    // If on login page, attach login handler and skip other initializations
    
// website/admin/js/admin_main.js
// Main script for initializing the Admin Panel and page-specific logic.
document.addEventListener('DOMContentLoaded', () => {
    console.log("admin_main.js: DOMContentLoaded");

    // --- Global Admin Initializations ---
    const bodyId = document.body.id;
    const pagePath = window.location.pathname;

    // If on login page, attach login handler and skip other initializations
    if (bodyId === 'page-admin-login' || pagePath.includes('admin_login.html')) {
        console.log("admin_main.js: On admin_login.html");
        
        // Check if already logged in as admin; if so, redirect to dashboard.
        // This check is now primarily handled by checkAdminLogin.
        if (typeof checkAdminLogin === 'function') {
            checkAdminLogin(); // This will redirect if already logged in.
        } else {
            console.error("admin_main.js: checkAdminLogin function not found. Ensure admin_auth.js is loaded.");
        }

        const adminLoginForm = document.getElementById('admin-login-form');
        if (adminLoginForm) {
            if (typeof handleAdminLoginFormSubmit === 'function') {
                adminLoginForm.addEventListener('submit', handleAdminLoginFormSubmit);
                console.log("admin_main.js: Admin login form event listener attached.");
            } else {
                console.error("admin_main.js: handleAdminLoginFormSubmit function not found. Ensure admin_auth.js is loaded.");
            }
        } else {
            console.warn("admin_main.js: Admin login form not found on this page.");
        }
        return; // Stop further execution for login page
    }

    // For all other admin pages, check login status first
    // This will redirect to admin_login.html if not authenticated.
    if (typeof checkAdminLogin === 'function') {
        if (!checkAdminLogin()) {
            console.log("admin_main.js: Admin not logged in, checkAdminLogin should have redirected.");
            return; 
        }
    } else {
        console.error("admin_main.js: checkAdminLogin function not found. Site protection compromised. Ensure admin_auth.js is loaded.");
        // Fallback redirect if checkAdminLogin is missing, though it shouldn't be.
        // window.location.href = 'admin_login.html'; 
        return;
    }

    // --- Common UI Setup for Authenticated Admin Pages ---
    setupAdminUIGlobals();


    // --- Page-Specific Initializations ---
    // Ensure each admin page has a unique body ID like id="page-admin-manage-products".

    if (bodyId === 'page-admin-dashboard' || pagePath.includes('admin_dashboard.html')) {
        console.log("admin_main.js: Initializing Admin Dashboard page.");
        if (typeof initializeAdminDashboard === 'function') initializeAdminDashboard(); // Assuming a specific init function
        else console.log("admin_main.js: initializeAdminDashboard not found, assuming admin_dashboard.js handles its own init within its DOMContentLoaded.");
    } else if (bodyId === 'page-admin-manage-products' || pagePath.includes('admin_manage_products.html') || pagePath.includes('admin_panel.html')) { // admin_panel.html seems to be product management too
        console.log("admin_main.js: Initializing Product Management page.");
        // The script admin_products.js is already loaded and its DOMContentLoaded will run.
        // No specific function call needed here if admin_products.js self-initializes.
    } else if (bodyId === 'page-admin-manage-inventory' || pagePath.includes('admin_manage_inventory.html')) {
        console.log("admin_main.js: Initializing Inventory Management page.");
        // admin_inventory.js self-initializes.
    } else if (bodyId === 'page-admin-view-inventory' || pagePath.includes('admin_view_inventory.html')) {
        console.log("admin_main.js: Initializing View Detailed Inventory page.");
        // admin_view_inventory.js self-initializes.
    } else if (bodyId === 'page-admin-manage-users' || pagePath.includes('admin_manage_users.html')) {
        console.log("admin_main.js: Initializing User Management page.");
        if (typeof initializeUserManagement === 'function') initializeUserManagement();
        else console.error("admin_main.js: initializeUserManagement not found. Ensure admin_users.js is loaded and defines it.");
    } else if (bodyId === 'page-admin-manage-orders' || pagePath.includes('admin_manage_orders.html')) {
        console.log("admin_main.js: Initializing Order Management page.");
        if (typeof initializeOrderManagement === 'function') initializeOrderManagement();
        else console.error("admin_main.js: initializeOrderManagement not found. Ensure admin_orders.js is loaded and defines it.");
    } else if (bodyId === 'page-admin-manage-categories' || pagePath.includes('admin_manage_categories.html')) {
        console.log("admin_main.js: Initializing Category Management page.");
        // admin_categories.js self-initializes.
    } else if (bodyId === 'page-admin-manage-reviews' || pagePath.includes('admin_manage_reviews.html')) {
        console.log("admin_main.js: Initializing Review Management page.");
        // admin_reviews.js self-initializes.
    } else if (bodyId === 'page-admin-invoices' || pagePath.includes('admin_invoices.html')) {
        console.log("admin_main.js: Initializing Invoice Management page.");
        // admin_invoices.js self-initializes.
    }


    // --- Admin Modal Global Event Listeners (if using generic modals not handled by specific page scripts) ---
    // This can be simplified if modals are always opened/closed by specific functions like openAdminModal/closeAdminModal from admin_ui.js
    document.querySelectorAll('.admin-modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', function(event) {
            if (event.target === this) { 
                if (typeof closeAdminModal === 'function') {
                    const modalId = this.id || this.dataset.modalId; 
                    if(modalId) closeAdminModal(modalId); 
                }
            }
        });
    });
    
    // Example for a generic close button if you have one not tied to specific modal logic
    // const genericModalCloseButton = document.getElementById('close-generic-modal-button');
    // if (genericModalCloseButton && typeof closeAdminModal === 'function') {
    //     genericModalCloseButton.addEventListener('click', () => closeAdminModal('generic-modal')); // Replace 'generic-modal' with actual ID
    // }
});


/**
 * Sets up global UI elements common to authenticated admin pages.
 */
function setupAdminUIGlobals() {
    // Admin user greeting
    const adminUser = getAdminUser(); // From admin_auth.js
    const greetingElement = document.getElementById('admin-user-greeting');
    if (greetingElement && adminUser) {
        greetingElement.textContent = `Bonjour, ${adminUser.prenom || adminUser.email}!`;
    } else if (greetingElement) {
        greetingElement.textContent = 'Bonjour, Admin!'; // Fallback
    }

    // Logout button
    const logoutButton = document.getElementById('admin-logout-button');
    if (logoutButton) {
        if (typeof adminLogout === 'function') { // From admin_auth.js
            logoutButton.removeEventListener('click', adminLogout); // Remove if already attached
            logoutButton.addEventListener('click', adminLogout);
        } else {
            console.error("admin_main.js: adminLogout function not found for logout button.");
        }
    }

    // Handle "Back to Dashboard" button visibility
    const backToDashboardButton = document.getElementById('back-to-dashboard-button');
    if (backToDashboardButton) {
        const bodyId = document.body.id;
        const pagePath = window.location.pathname;
        if (bodyId === 'page-admin-dashboard' || pagePath.includes('admin_dashboard.html')) {
            backToDashboardButton.style.display = 'none';
        } else {
            // Ensure it's visible, Tailwind might use 'hidden' class, so remove it.
            // Or set display directly. Default is often inline-flex for these buttons.
            backToDashboardButton.classList.remove('hidden'); 
            // backToDashboardButton.style.display = 'inline-flex'; 
        }
    }
    
    // Set active navigation link
    const currentPageFilename = window.location.pathname.split("/").pop();
    document.querySelectorAll('nav.bg-gray-800 .admin-nav-link').forEach(link => { // More specific selector for admin nav
        link.classList.remove('active', 'bg-gray-900'); // Remove active and potential hover/focus style if needed
        const linkHref = link.getAttribute('href');
        if (linkHref && linkHref === currentPageFilename) {
            link.classList.add('active', 'bg-gray-900'); // Add classes for active state
        }
    });
    console.log("Admin UI Globals (greeting, logout, nav) setup.");
}
```
