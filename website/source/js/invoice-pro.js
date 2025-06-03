// website/source/js/invoices-pro.js

document.addEventListener('DOMContentLoaded', () => {
    // Ensure this script only runs on the B2B invoices page
    if (document.body.id !== 'page-invoices-pro') {
        return;
    }

    // Check if user is logged in and is a B2B professional
    if (typeof isUserLoggedIn !== 'function' || !isUserLoggedIn()) {
        showGlobalMessage(t('public.cart.login_prompt'), 'error'); // Using a generic login prompt key
        // Redirect to login or professionals page after a delay
        setTimeout(() => { window.location.href = 'professionnels.html'; }, 3000);
        return;
    }
    
    const currentUser = typeof getCurrentUser === 'function' ? getCurrentUser() : null;
    if (!currentUser || currentUser.role !== 'b2b_professional') {
        showGlobalMessage(t('professionnels.erreurProduite'), 'error'); // Or a more specific "access denied" message
        setTimeout(() => { window.location.href = 'index.html'; }, 3000);
        return;
    }

    loadInvoices(1); // Load the first page initially
});

let currentPage = 1;
const invoicesPerPage = 10; // Or get from config, or let backend decide and use its per_page

async function loadInvoices(page = 1) {
    currentPage = page;
    const tableBody = document.getElementById('invoices-table-body');
    const noInvoicesMessage = document.getElementById('no-invoices-message');
    const paginationContainer = document.getElementById('pagination-controls-container');

    if (!tableBody || !noInvoicesMessage || !paginationContainer) {
        console.error("Required elements for invoice display or pagination not found.");
        return;
    }

    tableBody.innerHTML = `<tr><td colspan="5" class="text-center p-8">${t('invoicesPro.table.chargement')}</td></tr>`;
    noInvoicesMessage.classList.add('hidden');
    paginationContainer.innerHTML = ''; // Clear old pagination

    try {
        // API call to the paginated endpoint
        const response = await makeApiRequest(`/professional/invoices?page=${page}&per_page=${invoicesPerPage}`, 'GET', null, true);
        
        if (response.success && response.invoices) {
            const { invoices, total_invoices, total_pages } = response;

            if (invoices.length > 0) {
                tableBody.innerHTML = ''; // Clear loading message
                invoices.forEach(invoice => {
                    const row = tableBody.insertRow();
                    row.innerHTML = `
                        <td class="py-3 px-4 whitespace-nowrap">${invoice.invoice_number || 'N/A'}</td>
                        <td class="py-3 px-4 whitespace-nowrap">${invoice.issue_date || 'N/A'}</td>
                        <td class="py-3 px-4 whitespace-nowrap text-right">${invoice.total_amount !== null ? parseFloat(invoice.total_amount).toFixed(2) : 'N/A'} ${invoice.currency || ''}</td>
                        <td class="py-3 px-4 whitespace-nowrap">
                            <span class="status-${(invoice.status || 'unknown').toLowerCase().replace(/\s+/g, '_')}">
                                ${t(`invoiceStatus.${(invoice.status || 'unknown').toLowerCase().replace(/\s+/g, '_')}`) || invoice.status || 'Unknown'}
                            </span>
                        </td>
                        <td class="py-3 px-4 whitespace-nowrap text-center">
                            ${invoice.pdf_download_url ? `<a href="${invoice.pdf_download_url}" class="btn-secondary text-xs py-1 px-2" target="_blank" rel="noopener noreferrer">${t('invoicesPro.table.telecharger')}</a>` : t('common.notApplicable')}
                        </td>
                    `;
                });
                renderInvoicePaginationControls(total_invoices, total_pages, page, invoicesPerPage);
            } else {
                tableBody.innerHTML = '';
                noInvoicesMessage.classList.remove('hidden');
            }
        } else {
            tableBody.innerHTML = `<tr><td colspan="5" class="text-center p-8 text-red-600">${response.message || t('invoicesPro.erreurChargement')}</td></tr>`;
            noInvoicesMessage.classList.remove('hidden');
            noInvoicesMessage.querySelector('p').textContent = response.message || t('invoicesPro.erreurChargement');
        }
    } catch (error) {
        console.error('Failed to load invoices:', error);
        const errorMsg = error.data?.message || error.message || t('invoicesPro.erreurChargement');
        tableBody.innerHTML = `<tr><td colspan="5" class="text-center p-8 text-red-500">${errorMsg}</td></tr>`;
        noInvoicesMessage.classList.remove('hidden');
        noInvoicesMessage.querySelector('p').textContent = errorMsg;
        if (error.status === 401 || error.status === 403) { // Unauthorized or Forbidden
            setTimeout(() => { window.location.href = 'professionnels.html'; }, 3000);
        }
    }
}

function renderInvoicePaginationControls(totalItems, totalPages, currentPage, itemsPerPage) {
    const paginationContainer = document.getElementById('pagination-controls-container');
    if (!paginationContainer || totalPages <= 1) {
        if (paginationContainer) paginationContainer.innerHTML = '';
        return;
    }

    let paginationHTML = '';

    // Previous Button
    paginationHTML += `<button onclick="loadInvoices(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>&laquo; ${t('public.pagination.previous') || 'Previous'}</button>`;

    // Page Numbers (simplified version)
    // For a more complex pagination (e.g., with ellipses for many pages), more logic is needed.
    const maxPagesToShow = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxPagesToShow / 2));
    let endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);

    if (endPage - startPage + 1 < maxPagesToShow) {
        startPage = Math.max(1, endPage - maxPagesToShow + 1);
    }
    
    if (startPage > 1) {
        paginationHTML += `<button onclick="loadInvoices(1)">1</button>`;
        if (startPage > 2) {
            paginationHTML += `<span>...</span>`;
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        if (i === currentPage) {
            paginationHTML += `<button class="active-page" disabled>${i}</button>`;
        } else {
            paginationHTML += `<button onclick="loadInvoices(${i})">${i}</button>`;
        }
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            paginationHTML += `<span>...</span>`;
        }
        paginationHTML += `<button onclick="loadInvoices(${totalPages})">${totalPages}</button>`;
    }

    // Next Button
    paginationHTML += `<button onclick="loadInvoices(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>${t('public.pagination.next') || 'Next'} &raquo;</button>`;

    paginationContainer.innerHTML = paginationHTML;

    // Add translation keys for pagination:
    // "public.pagination.previous": "Précédent" / "Previous"
    // "public.pagination.next": "Suivant" / "Next"
}

// Helper to get translated status text (if not already handled by t() and CSS classes)
// This is an example, your t() function and CSS classes for status might be enough.
// function getInvoiceStatusText(statusKey) {
//    return t(`invoiceStatus.${statusKey.toLowerCase().replace(/\s+/g, '_')}`) || statusKey;
// }
