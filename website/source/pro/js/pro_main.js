<script>
document.addEventListener('DOMContentLoaded', () => {
    const logoutButton = document.getElementById('logout-pro');
    if (logoutButton) {
        logoutButton.addEventListener('click', (e) => {
            e.preventDefault();
            localStorage.removeItem('proToken');
            window.location.href = 'professionnels.html';
        });
    }

    // Profile Page Logic
    if (document.getElementById('profile-form')) {
        const profileForm = document.getElementById('profile-form');
        const messageDiv = document.getElementById('profile-message');
        const token = localStorage.getItem('proToken');

        // Fetch and populate profile data
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

        // Handle profile update
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
                    country: 'France' // Assuming country is fixed for now
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
});
</script>
