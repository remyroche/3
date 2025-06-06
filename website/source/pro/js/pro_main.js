<!DOCTYPE html>
<html>
<head>
    <title>Professional Main JS</title>
</head>
<body>
<script>
document.addEventListener('DOMContentLoaded', () => {
    // Handles the logout functionality for professional users.
    const logoutButton = document.getElementById('logout-pro');
    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            localStorage.removeItem('proToken');
            // Redirect to the language-specific professionals login page.
            const lang = document.documentElement.lang || 'fr';
            window.location.href = `/${lang}/professionnels.html`;
        });
    }

    // --- Profile Page Logic ---
    if (document.getElementById('profile-form')) {
        const profileForm = document.getElementById('profile-form');
        const messageDiv = document.getElementById('profile-message');
        const token = localStorage.getItem('proToken');

        // Fetch and populate profile data on page load.
        fetch('/api/b2b/profile', {
            headers: { 'Authorization': `Bearer ${token}` }
        })
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

        // Handle profile update form submission.
        profileForm.addEventListener('submit', function(e) {
            e.preventDefault();
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

            fetch('/api/b2b/profile', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(data)
            })
            .then(response => {
                if (response.ok) {
                    return response.json();
                }
                throw new Error('Failed to update profile');
            })
            .then(data => {
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
    
    // --- B2B Newsletter subscription logic (in the footer) ---
    const b2bNewsletterForm = document.getElementById('b2b-newsletter-form');
    if (b2bNewsletterForm) {
        b2bNewsletterForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const emailInput = document.getElementById('b2b-newsletter-email');
            const message = document.getElementById('b2b-newsletter-message');
            
            // Check if all required elements are available.
            if (!emailInput || !message || !window.i18n) return;

            try {
                // Call the B2B newsletter subscription endpoint.
                const response = await fetch('/api/b2b/newsletter/subscribe', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
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

            // Clear the message after a few seconds.
            setTimeout(() => { message.textContent = ''; }, 3000);
        });
    }
});
</script>
</body>
</html>
