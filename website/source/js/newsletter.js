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
                console.error("Newsletter email field not found."); // Dev console
                return;
            }
            clearFormErrors(newsletterForm); 

            const email = newsletterEmailInput.value;

            if (!email || !validateEmail(email)) { 
                setFieldError(newsletterEmailInput, t('public.js.newsletter_invalid_email')); 
                showGlobalMessage(t('public.js.newsletter_invalid_email'), "error"); 
                return;
            }
            showGlobalMessage(t('public.js.newsletter_subscribing'), "info");
            try {
                const result = await makeApiRequest('/subscribe-newsletter', 'POST', { email: email, consentement: 'Y' });
                if (result.success) {
                    showGlobalMessage(result.message || t('public.js.newsletter_success'), "success");
                    newsletterEmailInput.value = ""; 
                } else {
                    setFieldError(newsletterEmailInput, result.message || t('public.js.newsletter_error'));
                    showGlobalMessage(result.message || t('public.js.newsletter_error'), "error");
                }
            } catch (error) {
                setFieldError(newsletterEmailInput, error.message || t('global.error_generic'));
                console.error("Error subscribing to newsletter:", error);
            }
        });
    }
}
