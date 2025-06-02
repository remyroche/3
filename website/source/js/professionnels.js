document.addEventListener('DOMContentLoaded', () => {
    if (document.body.id !== 'page-professionnels') return;

    const loggedOutView = document.getElementById('logged-out-view');
    const loggedInView = document.getElementById('logged-in-view');
    const userNamePlaceholder = document.getElementById('user-name-placeholder');
    const magicLinkForm = document.getElementById('magic-link-form');
    const proLogoutBtn = document.getElementById('pro-logout-btn');
    const emailInput = document.getElementById('email-pro'); // For placeholder

    // Set placeholder from translations
    if(emailInput) emailInput.placeholder = t('professionnels.emailPlaceholder');


    handleMagicTokenVerification();
    updateProfessionalView();

    if (magicLinkForm) {
        magicLinkForm.addEventListener('submit', handleMagicLinkRequest);
    }
    if (proLogoutBtn) {
        proLogoutBtn.addEventListener('click', () => {
            logout(); 
            updateProfessionalView();
            showGlobalMessage(t('professionnels.deconnecteMessage'), 'success');
        });
    }


    function updateProfessionalView() {
        const user = getUser(); // from auth.js
        if (isLoggedIn() && user && user.role === 'b2b_professional') { // Ensure it's a B2B user
            userNamePlaceholder.textContent = user.prenom || user.company_name || t('professionnels.bienvenue');
            loggedInView.style.display = 'block';
            loggedOutView.style.display = 'none';
        } else {
            loggedInView.style.display = 'none';
            loggedOutView.style.display = 'block';
        }
    }

    async function handleMagicLinkRequest(e) {
        e.preventDefault();
        const email = document.getElementById('email-pro').value;
        const submitButton = e.target.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.textContent; // Store original text
        submitButton.disabled = true;
        submitButton.textContent = t('professionnels.messageEnvoiEnCours');

        try {
            const response = await makeApiRequest('/auth/request-magic-link', 'POST', { email });
            showGlobalMessage(t(response.message) || t('professionnels.messageLienEnvoye'), 'success'); // Attempt to translate backend message
            handleResendCountdown();
        } catch (error) {
            showGlobalMessage(t(error.data?.message) || t('professionnels.erreurProduite'), 'error');
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText; // Restore original text
        }
    }

    async function handleMagicTokenVerification() {
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('magic_token');

        if (token) {
            window.history.replaceState({}, document.title, window.location.pathname);
            showGlobalMessage(t('professionnels.verificationLienMagique'), 'info');
            try {
                const response = await makeApiRequest('/auth/verify-magic-link', 'POST', { token });
                saveAuthData(response);
                showGlobalMessage(t('professionnels.connexionReussie'), 'success');
                updateProfessionalView();
            } catch (error) {
                showGlobalMessage(t(error.data?.message) || t('professionnels.lienInvalideOuExpire'), 'error');
            }
        }
    }

    function handleResendCountdown() {
        const resendContainer = document.getElementById('resend-container');
        const resendBtn = document.getElementById('resend-link-btn');
        const countdownSpan = document.getElementById('resend-countdown');
        let countdown = 30;

        if (!resendContainer || !resendBtn || !countdownSpan) return; // Elements might not exist if user is logged in

        resendContainer.style.display = 'inline';
        resendBtn.disabled = true;
        resendBtn.textContent = t('professionnels.magicLinkRenvoyer'); // Ensure button text is set

        const intervalId = `magicLinkInterval_${Date.now()}`; // Unique ID for this interval
        window[intervalId] = setInterval(() => { // Store interval ID on window to clear it if needed
            countdown--;
            countdownSpan.textContent = countdown;
            if (countdown <= 0) {
                clearInterval(window[intervalId]);
                resendBtn.disabled = false;
                // resendBtn.textContent = t('professionnels.magicLinkRenvoyer'); // Already set
                resendBtn.onclick = () => {
                    const email = document.getElementById('email-pro').value;
                    if (email) {
                        if (magicLinkForm) magicLinkForm.requestSubmit();
                    } else {
                        showGlobalMessage(t('professionnels.emailRequis'), 'error');
                    }
                };
            }
        }, 1000);
    }
});
