<script>
document.addEventListener('DOMContentLoaded', function() {
    const token = localStorage.getItem('proToken');
    if (!token) {
        window.location.href = 'professionnels.html';<script>
document.addEventListener('DOMContentLoaded', function() {
    const token = localStorage.getItem('proToken');
    if (!token) {
        window.location.href = 'professionnels.html';
        return;
    }

    const referralCodeEl = document.getElementById('referral-code');
    const copyBtn = document.getElementById('copy-code-btn');
    const copyMessageEl = document.getElementById('copy-message');
    const historyListEl = document.getElementById('referral-history-list');

    fetch('/api/b2b/referral', {
        headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(response => {
        if (!response.ok) throw new Error('Could not load referral data.');
        return response.json();
    })
    .then(data => {
        referralCodeEl.textContent = data.referral_code || 'N/A';
        displayHistory(data.referrals);
    })
    .catch(error => {
        console.error('Error fetching referral data:', error);
        if(referralCodeEl) referralCodeEl.textContent = 'Error';
        if(historyListEl) historyListEl.innerHTML = `<p class="text-red-500">${window.i18n.history_error}</p>`;
    });

    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(referralCodeEl.textContent).then(() => {
                copyMessageEl.textContent = window.i18n.copy_success_message;
                setTimeout(() => {
                    copyMessageEl.textContent = '';
                }, 2000);
            });
        });
    }

    function displayHistory(referrals) {
        if (!historyListEl) return;
        if (!referrals || referrals.length === 0) {
            historyListEl.innerHTML = `<p>${window.i18n.history_no_entries}</p>`;
            return;
        }

        const table = `
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${window.i18n.history_header_date}</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${window.i18n.history_header_email}</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${window.i18n.history_header_status}</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    ${referrals.map(ref => `
                        <tr>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${new Date(ref.date).toLocaleDateString()}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${ref.referred_email}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm">
                               <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${ref.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}">
                                    ${ref.status === 'completed' ? window.i18n.history_status_completed : window.i18n.history_status_pending}
                                </span>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        historyListEl.innerHTML = table;
    }
});
</script>
