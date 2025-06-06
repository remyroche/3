<!--------------------------------------------------------------------------------
-- File: website/source/pro/js/pro_main.js
-- Change: Added client-side validation and sanitization for the profile form.
--------------------------------------------------------------------------------->
<script>
// You must include the DOMPurify library in your HTML for this to work.
// <script src="[https://cdn.jsdelivr.net/npm/dompurify@2.3.6/dist/purify.min.js](https://cdn.jsdelivr.net/npm/dompurify@2.3.6/dist/purify.min.js)"></script>

document.addEventListener('DOMContentLoaded', () => {
    const secureFetch = (url, options = {}) => {
        const defaultOptions = {
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', ...options.headers },
        };
        return fetch(url, { ...options, ...defaultOptions });
    };

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

    if (document.getElementById('profile-form')) {
        const profileForm = document.getElementById('profile-form');
        const messageDiv = document.getElementById('profile-message');

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

        profileForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (!validateProfileForm()) {
                return; // Stop submission if validation fails
            }

            const formData = new FormData(this);
            // Sanitize input with DOMPurify before sending to the backend
            const data = {
                company_name: DOMPurify.sanitize(formData.get('companyName')),
                email: DOMPurify.sanitize(formData.get('email')),
                phone_number: DOMPurify.sanitize(formData.get('phone')),
                address: {
                    street: DOMPurify.sanitize(formData.get('address')),
                    city: DOMPurify.sanitize(formData.get('city')),
                    postal_code: DOMPurify.sanitize(formData.get('zipCode')),
                    country: 'France'
                }
            };

            secureFetch('/api/b2b/profile', {
                method: 'PUT',
                body: JSON.stringify(data)
            })
            .then(response => {
                if (response.ok) return response.json();
                // Handle server-side validation errors
                return response.json().then(err => { throw err; });
            })
            .then(() => {
                messageDiv.textContent = window.i18n.profile_update_success;
                messageDiv.className = 'mt-4 text-center text-green-600';
            })
            .catch(error => {
                console.error('Error updating profile:', error);
                // Display server-side error message if available
                const errorMessage = error.message || window.i18n.profile_update_error;
                messageDiv.textContent = errorMessage;
                messageDiv.className = 'mt-4 text-center text-red-600';
            });
        });

        function validateProfileForm() {
            let isValid = true;
            clearErrors();

            const email = document.getElementById('email').value;
            if (!/^\S+@\S+\.\S+$/.test(email)) {
                showError('email', 'Invalid email format.');
                isValid = false;
            }

            const companyName = document.getElementById('companyName').value;
            if (companyName.trim() === '') {
                showError('companyName', 'Company name is required.');
                isValid = false;
            }
            
            return isValid;
        }

        function showError(fieldId, message) {
            const field = document.getElementById(fieldId);
            field.classList.add('border-red-500');
            const errorElement = document.createElement('p');
            errorElement.className = 'text-red-500 text-xs italic error-message';
            errorElement.textContent = message;
            field.parentNode.appendChild(errorElement);
        }

        function clearErrors() {
            document.querySelectorAll('.error-message').forEach(el => el.remove());
            document.querySelectorAll('.border-red-500').forEach(el => el.classList.remove('border-red-500'));
        }
    }

    const b2bNewsletterForm = document.getElementById('b2b-newsletter-form');
    if (b2bNewsletterForm) {
        b2bNewsletterForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const emailInput = document.getElementById('b2b-newsletter-email');
            const message = document.getElementById('b2b-newsletter-message');
            
            if (!emailInput || !message || !window.i18n) return;
            
            try {
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
