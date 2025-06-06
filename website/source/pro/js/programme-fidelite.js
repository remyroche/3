<script>
document.addEventListener('DOMContentLoaded', function() {
    const token = localStorage.getItem('proToken');
    if (!token) {
        window.location.href = 'professionnels.html';
        return;
    }

    const loyaltyPointsEl = document.getElementById('loyalty-points');
    const historyListEl = document.getElementById('loyalty-history-list');

    // Fetch loyalty data
    fetch('/api/b2b/loyalty', {
        headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(response => response.json())
    .then(data => {
        loyaltyPointsEl.textContent = data.total_points || 0;
        displayHistory(data.history);
    })
    .catch(error => {
        console.error('Error fetching loyalty data:', error);
        loyaltyPointsEl.textContent = 'Error';
    });

    function displayHistory(history) {
        if (!history || history.length === 0) {
            historyListEl.innerHTML = `<p>${window.i18n.history_no_entries}</p>`;
            return;
        }

        const table = `
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${window.i18n.history_header_date}</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${window.i18n.history_header_description}</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${window.i18n.history_header_points}</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    ${history.map(entry => `
                        <tr>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${new Date(entry.date).toLocaleDateString()}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${entry.description}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-semibold ${entry.points > 0 ? 'text-green-600' : 'text-red-600'}">${entry.points > 0 ? '+' : ''}${entry.points}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        historyListEl.innerHTML = table;
    }
});
</script>
