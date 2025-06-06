<script>
document.addEventListener('DOMContentLoaded', () => {
    const proLoginForm = document.getElementById('pro-login-form');
    const proLoginError = document.getElementById('pro-login-error');

    if (proLoginForm) {
        proLoginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email-pro').value;
            const password = document.getElementById('password-pro').value;

            try {
                const response = await fetch('/api/b2b/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ email, password })
                });

                const data = await response.json();

                if (response.ok) {
                    localStorage.setItem('proToken', data.token);
                    window.location.href = 'pro/marchedespros.html';
                } else {
                    proLoginError.textContent = window.i18n.login_error || (data.message || 'Login failed');
                }
            } catch (error) {
                console.error('Login error:', error);
                proLoginError.textContent = window.i18n.login_error || 'An unexpected error occurred.';
            }
        });
    }
});
</script>
