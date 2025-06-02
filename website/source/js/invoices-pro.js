// Assuming `t` function is available globally or via import, similar to professionnels.js
// Assuming `showGlobalMessage` from ui.js is already i18n-aware or you pass translated strings to it.

document.addEventListener('DOMContentLoaded', () => {
    if (document.body.id !== 'page-invoices-pro') return;

    if (!isLoggedIn()) {
        window.location.href = 'professionnels.html'; // Redirect if not logged in
        return;
    }
    // Also ensure the user is a professional
    const user = getUser();
    if (!user || user.role !== 'b2b_professional') {
        showGlobalMessage(t('professionnels.erreurProduite'), 'error'); // Or a more specific message
        window.location.href = 'index.html'; // Redirect to home or login
        return;
    }


    loadInvoices();
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
