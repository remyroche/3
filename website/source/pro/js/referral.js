document.addEventListener('DOMContentLoaded', () => {
    const user = JSON.parse(localStorage.getItem('user'));
    if (!user) {
        window.location.href = '/professionnels.html';
        return;
    }

    const referralCodeInput = document.getElementById('referral-code');
    const creditBalanceEl = document.getElementById('credit-balance');
    const copyBtn = document.getElementById('copy-btn');

    // Populate user's data
    if (user.referral_code) {
        referralCodeInput.value = user.referral_code;
    }
    if (user.referral_credit_balance) {
        creditBalanceEl.textContent = `${user.referral_credit_balance.toFixed(2)} €`;
    }

    // Copy to clipboard functionality
    copyBtn.addEventListener('click', () => {
        referralCodeInput.select();
        document.execCommand('copy');
        copyBtn.textContent = 'Copié !';
        setTimeout(() => {
            copyBtn.textContent = 'Copier';
        }, 2000);
    });
});
