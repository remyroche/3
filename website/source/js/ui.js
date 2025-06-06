<script>
document.addEventListener('DOMContentLoaded', () => {
    // Mobile menu toggle
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');
    if (mobileMenuButton && mobileMenu) {
        mobileMenuButton.addEventListener('click', () => {
            mobileMenu.classList.toggle('hidden');
        });
    }

    // Function to update authentication links based on user status
    function updateAuthLinks(user) {
        const authLinks = document.getElementById('auth-links');
        if (!authLinks || !window.i18n) return;

        if (user) {
            // User is logged in
            authLinks.innerHTML = `
                <a href="compte.html" class="text-gray-600 hover:text-blue-500">${window.i18n.nav_account}</a>
                <a href="#" id="logout-link" class="text-gray-600 hover:text-blue-500">${window.i18n.nav_logout}</a>
            `;
            const logoutLink = document.getElementById('logout-link');
            if (logoutLink) {
                logoutLink.addEventListener('click', (e) => {
                    e.preventDefault();
                    logout();
                });
            }
        } else {
            // User is not logged in
            authLinks.innerHTML = `<a href="#" id="login-modal-trigger" class="text-gray-600 hover:text-blue-500">${window.i18n.nav_login}</a>`;
            // Note: The logic for opening the login modal would need to be implemented here or in auth.js
        }
    }
    
    // Initial check for user status
    checkAuthStatus(updateAuthLinks);
});
</script>
