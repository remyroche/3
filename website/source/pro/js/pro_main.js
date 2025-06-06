<script>
document.addEventListener('DOMContentLoaded', () => {
    // --- Secure Fetch Wrapper ---
    // This wrapper automatically includes credentials for every fetch call.
    const secureFetch = (url, options = {}) => {
        const defaultOptions = {
            credentials: 'include', // This is the key change!
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        };
        return fetch(url, { ...options, ...defaultOptions });
    };


    // --- Logout Logic ---
    const logoutButton = document.getElementById('logout-pro');
    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            secureFetch('/api/b2b/logout', { method: 'POST' })
                .then(() => {
                    const lang = document.documentElement.lang || 'fr';
                    window.location.href = `/${lang}/professionnels.html`;
                })
                .catch(err => console.error("Logout failed", err));
        });
    }

    // --- Profile Page Logic ---
    if (document.getElementById('profile-form')) {
        const profileForm = document.getElementById('profile-form');
        const messageDiv = document.getElementById('profile-message');

        // Fetch and populate profile data
        secureFetch('/api/b2b/profile')
            .then(response => response.json())
            .then(data => {
                if (data) {
                    document.getElementById('companyName').value = data.company_name || '';
                    document.getElementById('siret').value = data.siret || '';
                    document.getElementById('email').value = data.email || '';
                    document.getElementById('phone').value = data.phone_number || '';
                    document.getElementById('address').value = data.address ? data.address.street : '';
                    document.getElementById('city').value = data.address ? data.address.city : '';
                    document.getElementById('zipCode').value = data.address ? data.address.postal_code : '';
                }
            })
            .catch(error => console.error('Error fetching profile:', error));

        // Handle profile update
        profileForm.addEventListener('submit', function(e) {
            e.preventDefault();
            // (Client-side validation will be added here in the next step)
            const formData = new FormData(this);
            const data = {
                company_name: formData.get('companyName'),
                email: formData.get('email'),
                phone_number: formData.get('phone'),
                address: {
                    street: formData.get('address'),
                    city: formData.get('city'),
                    postal_code: formData.get('zipCode'),
                    country: 'France'
                }
            };

            secureFetch('/api/b2b/profile', {
                method: 'PUT',
                body: JSON.stringify(data)
            })
            .then(response => {
                if (response.ok) return response.json();
                throw new Error('Failed to update profile');
            })
            .then(() => {
                messageDiv.textContent = window.i18n.profile_update_success;
                messageDiv.className = 'mt-4 text-center text-green-600';
            })
            .catch(error => {
                console.error('Error updating profile:', error);
                messageDiv.textContent = window.i18n.profile_update_error;
                messageDiv.className = 'mt-4 text-center text-red-600';
            });
        });
    }
    
    // --- B2B Newsletter Subscription ---
    const b2bNewsletterForm = document.getElementById('b2b-newsletter-form');
    if (b2bNewsletterForm) {
        b2bNewsletterForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const emailInput = document.getElementById('b2b-newsletter-email');
            const message = document.getElementById('b2b-newsletter-message');
            
            if (!emailInput || !message || !window.i18n) return;

            try {
                // Use secureFetch for this public endpoint as well for consistency.
                const response = await secureFetch('/api/b2b/newsletter/subscribe', {
                    method: 'POST',
                    body: JSON.stringify({ email: emailInput.value })
                });

                if (response.ok) {
                    message.textContent = window.i18n.b2b_newsletter_success;
                    message.className = 'mt-2 text-sm h-4 text-green-400';
                    emailInput.value = '';
                } else {
                    const errorData = await response.json();
                    message.textContent = window.i18n.b2b_newsletter_error || errorData.message;
                    message.className = 'mt-2 text-sm h-4 text-red-400';
                }
            } catch (error) {
                console.error('B2B Newsletter subscription error:', error);
                message.textContent = window.i18n.b2b_newsletter_error;
                message.className = 'mt-2 text-sm h-4 text-red-400';
            }

            setTimeout(() => { message.textContent = ''; }, 3000);
        });
    }
});
</script>
</script>
</body>
</html>
