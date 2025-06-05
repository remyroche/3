// In website/source/pro/js/pro_main.js
async function loadProHeader() {
    const placeholder = document.getElementById('pro-header-placeholder');
    if (!placeholder) return;
    try {
        const response = await fetch('pro_header.html'); // Adjust path if needed
        if (response.ok) {
            placeholder.innerHTML = await response.text();
            // Add any B2B specific header JS logic here (e.g., active nav, user greeting)
            const proUser = typeof getCurrentUser === 'function' ? getCurrentUser() : null;
            const greetingEl = document.getElementById('pro-user-greeting');
            if (greetingEl && proUser) {
                greetingEl.textContent = `${proUser.company_name || proUser.first_name || 'Pro User'}`;
            }
            const logoutBtn = document.getElementById('pro-logout-button');
            if (logoutBtn && typeof logoutUser === 'function') {
                logoutBtn.addEventListener('click', logoutUser);
            }
            // Active Nav for Pro pages
            const currentPagePro = window.location.pathname.split("/").pop();
            document.querySelectorAll('.pro-nav .nav-link-pro').forEach(link => {
                link.classList.remove('active');
                if (link.getAttribute('href') === currentPagePro) {
                    link.classList.add('active');
                }
            });

        } else { placeholder.innerHTML = '<p>Error loading pro header.</p>'; }
    } catch (error) { console.error('Error loading pro header:', error); placeholder.innerHTML = '<p>Error loading pro header.</p>'; }
}

async function loadProFooter() {
    const placeholder = document.getElementById('pro-footer-placeholder');
    if (!placeholder) return;
    try {
        const response = await fetch('pro_footer.html'); // Adjust path if needed
        if (response.ok) {
            const footerHtml = await response.text();
            placeholder.innerHTML = footerHtml;
             // Execute any script tags within the loaded footer HTML
            const scripts = placeholder.querySelectorAll("script");
            scripts.forEach(script => {
                const newScript = document.createElement("script");
                if (script.src) {
                    newScript.src = script.src;
                } else {
                    newScript.textContent = script.textContent;
                }
                document.body.appendChild(newScript).remove(); // Append and remove to execute
            });
        } else { placeholder.innerHTML = '<p>Error loading pro footer.</p>'; }
    } catch (error) { console.error('Error loading pro footer:', error); placeholder.innerHTML = '<p>Error loading pro footer.</p>'; }
}

document.addEventListener('DOMContentLoaded', () => {
    if (document.body.classList.contains('pro-page')) { // Add 'pro-page' class to B2B page bodies
        loadProHeader();
        loadProFooter();
    }
});
