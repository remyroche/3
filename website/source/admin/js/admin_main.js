// website/source/admin/js/admin_main.js
// Main script for initializing the Admin Panel and page-specific logic.

document.addEventListener('DOMContentLoaded', () => {
    console.log("admin_main.js: DOMContentLoaded");

    const bodyId = document.body.id;
    const pagePath = window.location.pathname;

    if (bodyId === 'page-admin-login' || pagePath.includes('admin_login.html')) {
        console.log("admin_main.js: On admin_login.html");
        if (typeof checkAdminLogin === 'function') {
            checkAdminLogin(); 
        } else {
            console.error("admin_main.js: checkAdminLogin function not found. Ensure admin_auth.js is loaded.");
        }

        const adminLoginForm = document.getElementById('admin-login-form');
        if (adminLoginForm) {
            if (typeof handleAdminLoginFormSubmit === 'function') {
                adminLoginForm.addEventListener('submit', handleAdminLoginFormSubmit);
                console.log("admin_main.js: Admin login form event listener attached.");

                // Add event listener for TOTP submission button if it exists (it's on login page)
                const submitTotpButton = document.getElementById('submit-totp-button');
                if (submitTotpButton && typeof handleTotpVerification === 'function') { // handleTotpVerification is in admin_auth.js
                    submitTotpButton.addEventListener('click', handleTotpVerification);
                }
                 // Add event listener for pressing Enter in TOTP code input on login page
                const totpCodeInputLogin = document.getElementById('admin-totp-code'); // ID from admin_login.html
                if (totpCodeInputLogin && typeof handleTotpVerification === 'function') {
                    totpCodeInputLogin.addEventListener('keypress', function(event) {
                        if (event.key === 'Enter') {
                            event.preventDefault(); 
                            handleTotpVerification();
                        }
                    });
                }
            } else {
                console.error("admin_main.js: handleAdminLoginFormSubmit function not found. Ensure admin_auth.js is loaded.");
            }
        } else {
            console.warn("admin_main.js: Admin login form not found on this page.");
        }
        // Add event listener for SimpleLogin button on login page
        const simpleLoginButton = document.getElementById('simplelogin-button');
        if (simpleLoginButton) {
            simpleLoginButton.addEventListener('click', () => {
                if (typeof adminApi !== 'undefined' && typeof adminApi.initiateSimpleLogin === 'function') {
                    adminApi.initiateSimpleLogin();
                } else {
                    console.error("adminApi.initiateSimpleLogin is not defined.");
                    if(typeof showAdminToast === 'function') showAdminToast("SimpleLogin integration error. Please contact support.", "error");
                }
            });
        }
        return; 
    }

    if (typeof checkAdminLogin === 'function') {
        if (!checkAdminLogin()) {
            console.log("admin_main.js: Admin not logged in, checkAdminLogin should have redirected.");
            return; 
        }
    } else {
        console.error("admin_main.js: checkAdminLogin function not found. Site protection compromised. Ensure admin_auth.js is loaded.");
        return;
    }

    setupAdminUIGlobals();


    // --- Page-Specific Initializations ---
    if (bodyId === 'page-admin-dashboard' || pagePath.includes('admin_dashboard.html')) {
        console.log("admin_main.js: Initializing Admin Dashboard page.");
        // admin_dashboard.js self-initializes.
    } else if (bodyId === 'page-admin-profile' || pagePath.includes('admin_profile.html')) {
        console.log("admin_main.js: Initializing Admin Profile page.");
        // admin_profile.js self-initializes.
    } else if (bodyId === 'page-admin-manage-products' || pagePath.includes('admin_manage_products.html') || pagePath.includes('admin_panel.html')) { 
        console.log("admin_main.js: Initializing Product Management page.");
        // admin_products.js self-initializes.
    } else if (bodyId === 'page-admin-manage-inventory' || pagePath.includes('admin_manage_inventory.html')) {
        console.log("admin_main.js: Initializing Inventory Management page.");
        // admin_inventory.js self-initializes.
    } else if (bodyId === 'page-admin-view-inventory' || pagePath.includes('admin_view_inventory.html')) {
        console.log("admin_main.js: Initializing View Detailed Inventory page.");
        // admin_view_inventory.js self-initializes.
    } else if (bodyId === 'page-admin-manage-users' || pagePath.includes('admin_manage_users.html')) {
        console.log("admin_main.js: Initializing User Management page.");
        if (typeof initializeUserManagement === 'function') initializeUserManagement();
        else console.error("admin_main.js: initializeUserManagement not found.");
    } else if (bodyId === 'page-admin-manage-orders' || pagePath.includes('admin_manage_orders.html')) {
        console.log("admin_main.js: Initializing Order Management page.");
        if (typeof initializeOrderManagement === 'function') initializeOrderManagement();
        else console.error("admin_main.js: initializeOrderManagement not found.");
    } else if (bodyId === 'page-admin-manage-categories' || pagePath.includes('admin_manage_categories.html')) {
        console.log("admin_main.js: Initializing Category Management page.");
        // admin_categories.js self-initializes.
    } else if (bodyId === 'page-admin-manage-reviews' || pagePath.includes('admin_manage_reviews.html')) {
        console.log("admin_main.js: Initializing Review Management page.");
        // admin_reviews.js self-initializes.
    } else if (bodyId === 'page-admin-invoices' || pagePath.includes('admin_invoices.html') || bodyId === 'page-admin-create-invoice' || pagePath.includes('admin_create_invoice.html')) {
        console.log("admin_main.js: Initializing Invoice Management page.");
        // admin_invoices.js self-initializes.
    }

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
});


function setupAdminUIGlobals() {
    const adminUser = getAdminUser(); 
    const greetingElement = document.getElementById('admin-user-greeting');
    if (greetingElement && adminUser) {
        greetingElement.textContent = `Bonjour, ${adminUser.prenom || adminUser.email}!`;
    } else if (greetingElement) {
        greetingElement.textContent = 'Bonjour, Admin!'; 
    }

    const logoutButton = document.getElementById('admin-logout-button');
    if (logoutButton) {
        if (typeof adminLogout === 'function') { 
            logoutButton.removeEventListener('click', adminLogout); 
            logoutButton.addEventListener('click', adminLogout);
        } else {
            console.error("admin_main.js: adminLogout function not found for logout button.");
        }
    }

    const backToDashboardButton = document.getElementById('back-to-dashboard-button');
    if (backToDashboardButton) {
        const bodyId = document.body.id;
        const pagePath = window.location.pathname;
        if (bodyId === 'page-admin-dashboard' || pagePath.includes('admin_dashboard.html')) {
            backToDashboardButton.style.display = 'none';
        } else {
            backToDashboardButton.classList.remove('hidden'); 
            // Ensure it's styled appropriately to be visible, e.g. display: 'inline-flex' or 'block'
            // This might depend on your Tailwind setup or direct CSS.
            // For the provided HTML, it uses 'flex items-center', so 'inline-flex' or 'flex' is good.
             backToDashboardButton.style.display = 'inline-flex';
        }
    }
    
    // Set active navigation link
    const currentPageFilename = window.location.pathname.split("/").pop();
    document.querySelectorAll('nav.bg-gray-800 .admin-nav-link').forEach(link => {
        link.classList.remove('active', 'bg-gray-900'); 
        const linkHref = link.getAttribute('href');
        if (linkHref && linkHref === currentPageFilename) {
            link.classList.add('active', 'bg-gray-900'); 
        }
    });
    console.log("Admin UI Globals (greeting, logout, nav) setup.");
}
