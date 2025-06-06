<script>
document.addEventListener('DOMContentLoaded', () => {
    const registerForm = document.getElementById('pro-register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const messageDiv = document.getElementById('pro-register-message');
            messageDiv.textContent = ''; // Clear previous messages

            // Basic client-side validation
            const password = document.getElementById('password').value;
            if (password.length < 8) {
                messageDiv.textContent = 'Password must be at least 8 characters long.';
                messageDiv.className = 'text-center mt-4 h-4 text-red-500';
                return;
            }

            const formData = new FormData(registerForm);
            const data = Object.fromEntries(formData.entries());

            try {
                const response = await fetch('/api/b2b/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (response.ok) {
                    messageDiv.textContent = window.i18n.register_success || "Registration successful! You can now log in.";
                    messageDiv.className = 'text-center mt-4 h-4 text-green-600';
                    setTimeout(() => {
                        window.location.href = 'professionnels.html';
                    }, 2000);
                } else {
                    messageDiv.textContent = result.message || window.i18n.register_error;
                    messageDiv.className = 'text-center mt-4 h-4 text-red-500';
                }
            } catch (error) {
                console.error('Registration error:', error);
                messageDiv.textContent = window.i18n.register_error;
                messageDiv.className = 'text-center mt-4 h-4 text-red-500';
            }
        });
    }
});
</script>
