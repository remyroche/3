// Assuming `t` function is available globally or via import, similar to professionnels.js
// Assuming `showGlobalMessage` from ui.js is already i18n-aware or you pass translated strings to it.

document.addEventListener('DOMContentLoaded', function() {
    const token = localStorage.getItem('proToken');
    if (!token) {
        window.location.href = 'professionnels.html';
        return;
    }

    const invoicesList = document.getElementById('invoices-list');

    fetch('/api/b2b/invoices', {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to fetch invoices');
        }
        return response.json();
    })
    .then(invoices => {
        displayInvoices(invoices);
    })
    .catch(error => {
        console.error('Error loading invoices:', error);
        invoicesList.innerHTML = `<p class="text-red-500">${window.i18n.error_loading}</p>`;
    });

    function displayInvoices(invoices) {
        if (invoices.length === 0) {
            invoicesList.innerHTML = `<p>${window.i18n.none_found}</p>`;
            return;
        }

        const table = `
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${window.i18n.header_number}</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${window.i18n.header_date}</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${window.i18n.header_amount}</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">${window.i18n.header_status}</th>
                        <th scope="col" class="relative px-6 py-3">
                            <span class="sr-only">Download</span>
                        </th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    ${invoices.map(invoice => `
                        <tr>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${invoice.invoice_number}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${new Date(invoice.date).toLocaleDateString()}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${invoice.amount.toFixed(2)} €</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm">
                                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${invoice.status === 'paid' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                                    ${invoice.status === 'paid' ? window.i18n.status_paid : window.i18n.status_unpaid}
                                </span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                <a href="/api/b2b/invoices/${invoice.id}/download" class="text-indigo-600 hover:text-indigo-900">${window.i18n.download}</a>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        invoicesList.innerHTML = table;
    }
});


async function loadInvoices() {
    const tableBody = document.getElementById('invoices-table-body');
    const noInvoicesMessage = document.getElementById('no-invoices-message');
    tableBody.innerHTML = `<tr><td colspan="5" class="text-center p-8">${t('invoicesPro.table.chargement')}</td></tr>`;

    try {
        const response = await makeApiRequest('/api/professional/invoices', 'GET', null, true);
        const invoices = response.invoices;
        
        if (invoices && invoices.length > 0) {
            tableBody.innerHTML = '';
            invoices.forEach(invoice => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td class="py-4 px-6 whitespace-nowrap">${invoice.invoice_number}</td>
                    <td class="py-4 px-6 whitespace-nowrap">${new Date(invoice.issue_date).toLocaleDateString()}</td>
                    <td class="py-4 px-6 whitespace-nowrap">${invoice.total_amount.toFixed(2)} ${invoice.currency}</td>
                    <td class="py-4 px-6 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusClass(invoice.status)}">
                            ${t(`invoiceStatus.${invoice.status.toLowerCase()}`) || invoice.status}
                        </span>
                    </td>
                    <td class="py-4 px-6 whitespace-nowrap text-right">
                        <a href="${API_BASE_URL}/api/orders/invoices/download/${invoice.id}" class="text-brand-earth-brown hover:underline" target="_blank" rel="noopener noreferrer">${t('invoicesPro.table.telecharger')}</a>
                    </td>
                `;
                tableBody.appendChild(row);
            });
            noInvoicesMessage.style.display = 'none';
        } else {
            tableBody.innerHTML = '';
            noInvoicesMessage.style.display = 'block';
        }
    } catch (error) {
        console.error('Failed to load invoices:', error);
        tableBody.innerHTML = `<tr><td colspan="5" class="text-center p-8 text-red-500">${t('invoicesPro.erreurChargement')}</td></tr>`;
        if (error.status === 401) {
            logout();
            window.location.href = 'professionnels.html';
        }
    }
}

function getStatusClass(status) {
    // This function can remain as is, as it's for styling, not displayed text.
    // However, the text itself inside the span is now translated.
    switch (status.toLowerCase()) {
        case 'paid':
        case 'issued':
            return 'bg-green-100 text-green-800';
        case 'pending_payment':
        case 'draft':
            return 'bg-yellow-100 text-yellow-800';
        case 'cancelled':
        case 'overdue':
            return 'bg-red-100 text-red-800';
        default:
            return 'bg-gray-100 text-gray-800';
    }
}

// Add translations for invoice statuses to your fr.json and en.json, e.g.:
// "invoiceStatus.paid": "Payée", "invoiceStatus.issued": "Émise", etc.
// "invoiceStatus.paid": "Paid", "invoiceStatus.issued": "Issued", etc.
