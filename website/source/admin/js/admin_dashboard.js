document.addEventListener('DOMContentLoaded', function() {
    console.log('Admin Dashboard JS Initialized');

    // Populate admin user email in the welcome message
    const adminUserEmailSpan = document.getElementById('adminUserEmail');
    if (adminUserEmailSpan) {
        // Assuming getAdminUser() is globally available from admin_auth.js
        // and returns an object like { email: 'admin@example.com', ... }
        // or null/undefined if not logged in or data is missing.
        if (typeof getAdminUser === 'function') {
            const adminUser = getAdminUser();
            if (adminUser && adminUser.email) {
                adminUserEmailSpan.textContent = adminUser.email;
            } else {
                console.warn('Admin user email not found in session storage for dashboard welcome message.');
                // The default "Admin" text from HTML will remain.
            }
        } else {
            console.error('getAdminUser function is not defined. Ensure admin_auth.js is loaded before admin_dashboard.js and getAdminUser is accessible.');
        }
    }

    // Populate current year in the footer
    const currentYearSpan = document.getElementById('currentYear');
    if (currentYearSpan) {
        currentYearSpan.textContent = new Date().getFullYear();
    }

    // Future dashboard-specific logic can go here (e.g., fetching stats, recent activity)
});
