document.addEventListener('DOMContentLoaded', () => {
    if (document.body.id !== 'page-professionnels') return;

    const loggedOutView = document.getElementById('logged-out-view');
    const loggedInView = document.getElementById('logged-in-view');
    const userNamePlaceholder = document.getElementById('user-name-placeholder');
    const magicLinkForm = document.getElementById('magic-link-form');
    const proLogoutBtn = document.getElementById('pro-logout-btn');
    const emailInput = document.getElementById('email-pro');

    if(emailInput) emailInput.placeholder = t('professionnels.emailPlaceholder'); // Key: professionnels.emailPlaceholder

    handleMagicTokenVerification(); // Handles verification on page load if token in URL
    updateProfessionalView(); // Initial view update

    if (magicLinkForm) {
        magicLinkForm.addEventListener('submit', handleMagicLinkRequest);
    }
    if (proLogoutBtn) {
        proLogoutBtn.addEventListener('click', () => {
            logoutUser(); // Using global logout from auth.js which calls setCurrentUser(null)
            // updateProfessionalView will be called by 'authStateChanged' event listener in main.js
            // showGlobalMessage(t('professionnels.deconnecteMessage'), 'success'); // This is also in auth.js logoutUser
        });
    }

    function updateProfessionalView() {
        const user = getCurrentUser(); 
        if (isUserLoggedIn() && user && user.role === 'b2b_professional') {
            if(userNamePlaceholder) userNamePlaceholder.textContent = user.prenom || user.company_name || t('professionnels.bienvenue_pro_fallback'); // New key: professionnels.bienvenue_pro_fallback (e.g., "Professional")
            if(loggedInView) loggedInView.style.display = 'block';
            if(loggedOutView) loggedOutView.style.display = 'none';
        } else {
            if(loggedInView) loggedInView.style.display = 'none';
            if(loggedOutView) loggedOutView.style.display = 'block';
        }
    }
    window.updateProfessionalView = updateProfessionalView; // Expose if needed by authStateChanged directly

    async function handleMagicLinkRequest(e) {
        e.preventDefault();
        const email = document.getElementById('email-pro').value;
        const submitButton = e.target.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.textContent; 
        submitButton.disabled = true;
        submitButton.textContent = t('professionnels.messageEnvoiEnCours'); // Key: professionnels.messageEnvoiEnCours

        try {
            // Backend might send a key or a pre-translated message.
            // If backend sends key, t(response.message) works. If pre-translated, just response.message.
            const response = await makeApiRequest('/auth/request-magic-link', 'POST', { email });
            showGlobalMessage(response.message || t('professionnels.messageLienEnvoye'), 'success'); // Key: professionnels.messageLienEnvoye
            handleResendCountdown();
        } catch (error) {
            const errorMessage = error.data?.message || t('professionnels.erreurProduite'); // Key: professionnels.erreurProduite
            showGlobalMessage(errorMessage, 'error');
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText; 
        }
    }

    async function handleMagicTokenVerification() {
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('magic_token');

        if (token) {
            window.history.replaceState({}, document.title, window.location.pathname); // Clean URL
            showGlobalMessage(t('professionnels.verificationLienMagique'), 'info'); // Key: professionnels.verificationLienMagique
            try {
                const response = await makeApiRequest('/auth/verify-magic-link', 'POST', { token });
                // Assuming response contains user data and token, handled by saveAuthData or similar
                if (response.success && response.user && response.token) {
                    setCurrentUser(response.user, response.token); // From auth.js
                    showGlobalMessage(response.message || t('professionnels.connexionReussie'), 'success'); // Key: professionnels.connexionReussie
                    // updateProfessionalView(); // Will be handled by authStateChanged event
                } else {
                    throw new Error(response.message || t('professionnels.lienInvalideOuExpire')); // Key: professionnels.lienInvalideOuExpire
                }
            } catch (error) {
                const errorMessage = error.data?.message || error.message || t('professionnels.lienInvalideOuExpire');
                showGlobalMessage(errorMessage, 'error');
            }
        }
    }

    function handleResendCountdown() {
        const resendContainer = document.getElementById('resend-container');
        const resendBtn = document.getElementById('resend-link-btn');
        const countdownSpan = document.getElementById('resend-countdown');
        let countdown = 30;

        if (!resendContainer || !resendBtn || !countdownSpan) return;

        resendContainer.style.display = 'inline';
        resendBtn.disabled = true;
        // The button text 'Renvoyer le lien' is already in HTML via {{ professionnels.magicLinkRenvoyer }}
        // If not, it should be: resendBtn.textContent = t('professionnels.magicLinkRenvoyer');

        const intervalId = `magicLinkInterval_${Date.now()}`; 
        window[intervalId] = setInterval(() => { 
            countdown--;
            countdownSpan.textContent = countdown;
            if (countdown <= 0) {
                clearInterval(window[intervalId]);
                resendBtn.disabled = false;
                resendBtn.onclick = () => {
                    const email = document.getElementById('email-pro').value;
                    if (email) {
                        if (magicLinkForm) magicLinkForm.requestSubmit(); // Resubmit the form
                    } else {
                        showGlobalMessage(t('professionnels.emailRequis'), 'error'); // Key: professionnels.emailRequis
                    }
                };
            }
        }, 1000);
    }
});
