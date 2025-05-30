// website/js/newsletter.js
// Handles newsletter subscription form.

/**
 * Initializes the newsletter subscription form.
 * Sets up event listener for submission and handles API call.
 */
function initializeNewsletterForm() {
    const newsletterForm = document.getElementById('newsletter-form');
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', async function (event) {
            event.preventDefault();
            const newsletterEmailInput = document.getElementById('email-newsletter');
            if (!newsletterEmailInput) {
                console.error("Champ e-mail de la newsletter non trouvé.");
                return;
            }
            clearFormErrors(newsletterForm); // Assumes clearFormErrors is in ui.js

            const email = newsletterEmailInput.value;

            if (!email || !validateEmail(email)) { // Assumes validateEmail is in ui.js
                setFieldError(newsletterEmailInput, "Veuillez entrer une adresse e-mail valide."); // Assumes setFieldError is in ui.js
                showGlobalMessage("Veuillez entrer une adresse e-mail valide.", "error"); // Assumes showGlobalMessage is in ui.js
                return;
            }
            showGlobalMessage("Enregistrement en cours...", "info");
            try {
                // Assumes makeApiRequest is in api.js and API_BASE_URL is in config.js
                // Backend expects { email: "...", consentement: "Y" }
                const result = await makeApiRequest('/subscribe-newsletter', 'POST', { email: email, consentement: 'Y' });
                if (result.success) {
                    showGlobalMessage(result.message || "Merci ! Votre adresse a été enregistrée.", "success");
                    newsletterEmailInput.value = ""; // Clear input on success
                } else {
                    setFieldError(newsletterEmailInput, result.message || "Erreur d'inscription.");
                    showGlobalMessage(result.message || "Une erreur s'est produite.", "error");
                }
            } catch (error) {
                // Error message is already shown by makeApiRequest's catch block
                setFieldError(newsletterEmailInput, error.message || "Erreur serveur.");
                console.error("Erreur d'inscription à la newsletter:", error);
            }
        });
    }
}
