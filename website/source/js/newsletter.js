<script>
document.addEventListener('DOMContentLoaded', () => {
    const newsletterForm = document.getElementById('newsletter-form');
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const emailInput = document.getElementById('newsletter-email');
            const message = document.getElementById('newsletter-message');
            
            if (!emailInput || !message || !window.i18n) return;

            try {
                const response = await fetch('/api/newsletter/subscribe', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: emailInput.value })
                });

                if (response.ok) {
                    message.textContent = window.i18n.newsletter_success;
                    message.className = 'mt-2 text-sm h-4 text-green-400';
                    emailInput.value = '';
                } else {
                    message.textContent = window.i18n.newsletter_error;
                    message.className = 'mt-2 text-sm h-4 text-red-400';
                }
            } catch (error) {
                console.error('Newsletter subscription error:', error);
                message.textContent = window.i18n.newsletter_error;
                message.className = 'mt-2 text-sm h-4 text-red-400';
            }

            setTimeout(() => { message.textContent = ''; }, 3000);
        });
    }
});
</script>
