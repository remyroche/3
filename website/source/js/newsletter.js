// website/js/newsletter.js
// Handles newsletter subscription form.

function initializeNewsletterForm() {
    const newsletterForm = document.getElementById('newsletter-form');
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', async function (event) {
            event.preventDefault();
            const newsletterEmailInput = document.getElementById('email-newsletter');
            if (!newsletterEmailInput) {
                console.error(t('public.js.newsletter_email_field_not_found')); // New key: public.js.newsletter_email_field_not_found
                return;
            }
            clearFormErrors(newsletterForm); 

            const email = newsletterEmailInput.value;

            if (!email || !validateEmail(email)) { 
                setFieldError(newsletterEmailInput, t('public.js.newsletter_invalid_email')); // Key: public.js.newsletter_invalid_email
                showGlobalMessage(t('public.js.newsletter_invalid_email'), "error"); 
                return;
            }
            showGlobalMessage(t('public.js.newsletter_subscribing'), "info"); // Key: public.js.newsletter_subscribing
            try {
                const result = await makeApiRequest('/subscribe-newsletter', 'POST', { email: email, consentement: 'Y' }); // Assuming API endpoint is /api/subscribe-newsletter
                if (result.success) {
                    showGlobalMessage(result.message || t('public.js.newsletter_success'), "success"); // Key: public.js.newsletter_success
                    newsletterEmailInput.value = ""; 
                } else {
                    setFieldError(newsletterEmailInput, result.message || t('public.js.newsletter_error')); // Key: public.js.newsletter_error
                    showGlobalMessage(result.message || t('public.js.newsletter_error'), "error");
                }
            } catch (error) {
                const errorMessage = error.data?.message || t('global.error_generic'); // Key: global.error_generic
                setFieldError(newsletterEmailInput, errorMessage);
                showGlobalMessage(errorMessage, "error");
                console.error("Error subscribing to newsletter:", error); // Dev-facing
            }
        });
    }
}
// No DOMContentLoaded listener needed here if initializeNewsletterForm is called from main.js after footer load.
