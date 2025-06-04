// admin_create_invoice_js.js
document.addEventListener('DOMContentLoaded', () => {
    const professionalUserSelect = document.getElementById('professional-user-select');
    const invoiceItemsTbody = document.getElementById('invoice-items-tbody');
    const addInvoiceItemBtn = document.getElementById('add-invoice-item-btn');
    const invoiceItemTemplate = document.getElementById('invoice-item-template');
    
    const invoiceDateInput = document.getElementById('invoice-date');
    const invoiceDueDateInput = document.getElementById('invoice-due-date');
    const invoiceNumberDisplay = document.getElementById('invoice-number-display');

    // Company info display elements (from config, could be dynamic if needed)
    const companyNameDisplay = document.getElementById('company-name');
    const companyAddress1Display = document.getElementById('company-address1');
    // const companyAddress2Display = document.getElementById('company-address2'); // If you have this field
    const companyCityPostalCountryDisplay = document.getElementById('company-city-postal-country');
    const companySiretDisplay = document.getElementById('company-siret'); // Assuming this is your company's SIRET
    const companyVatDisplay = document.getElementById('company-vat'); // Assuming this is your company's VAT
    // Hypothetical element for a tagline, if you add one to your HTML:
    // const companyTaglineDisplay = document.getElementById('company-tagline'); 


    // Customer billing info display elements
    const customerCompanyNameDisplay = document.getElementById('customer-company-name');
    const customerContactNameDisplay = document.getElementById('customer-contact-name');
    const customerBillingAddressDisplay = document.getElementById('customer-billing-address');
    const customerSiretDisplay = document.getElementById('customer-siret-display');
    const customerVatDisplay = document.getElementById('customer-vat-display');

    // Customer delivery info display elements
    const deliveryCompanyNameDisplay = document.getElementById('delivery-company-name');
    const customerDeliveryAddressDisplay = document.getElementById('customer-delivery-address');

    // Totals display
    const subtotalHTDisplay = document.getElementById('subtotal-ht');
    const vatSummaryContainer = document.getElementById('vat-summary-container');
    const totalVATDisplay = document.getElementById('total-vat');
    const grandTotalTTCDisplay = document.getElementById('grand-total-ttc');
    const netToPayDisplay = document.getElementById('net-to-pay');
    const paymentDueDaysDisplay = document.getElementById('payment-due-days'); // From config

    const saveInvoiceBtn = document.getElementById('save-invoice-btn');
    const previewInvoiceBtn = document.getElementById('preview-invoice-btn');

    let professionalUsersData = []; // To store fetched professional users with their details

    // --- Initialize Page ---

    // 1. Load company info (from config or a dedicated endpoint)
    // This section demonstrates how Maison Trüvra's specific branding details
    // would be fetched and applied if provided by a backend API.
    // The HTML already contains "Maison Trüvra SARL" as a placeholder.
    // This fetch would update it with authoritative data from the backend.
    /*
    fetchAPIData('/api/admin/company-info', {}, 'GET')
        .then(data => {
            if (data) {
                companyNameDisplay.textContent = data.name || "Maison Trüvra"; // Default to brand name
                companyAddress1Display.textContent = data.address_line1 || "1 Rue de la Truffe";
                companyCityPostalCountryDisplay.textContent = data.city_postal_country || "75001 Paris, France";
                companySiretDisplay.textContent = data.siret || "Votre SIRET"; 
                companyVatDisplay.textContent = data.vat_number || "Votre N° TVA"; 
                
                // Populate other company details from backend
                document.getElementById('company-iban').textContent = data.iban || 'FRXX XXXX XXXX XXXX XXXX XXX';
                document.getElementById('company-swift').textContent = data.swift || 'XXXXXXX';
                paymentDueDaysDisplay.textContent = data.invoice_due_days || 30;

                // Example of setting a tagline if the element and data exist
                // if (companyTaglineDisplay && data.tagline) {
                //    companyTaglineDisplay.textContent = data.tagline; // e.g., "L’avenir de la truffe, cultivé avec art."
                // }

                // Update any other brand-specific elements here
            } else {
                console.warn("Company info could not be loaded from API. Using HTML placeholders.");
                // Fallback to ensure essential brand name is displayed if API fails or data is incomplete
                if (!companyNameDisplay.textContent) {
                    companyNameDisplay.textContent = "Maison Trüvra";
                }
            }
        })
        .catch(error => {
            console.error('Error fetching company info:', error);
            // Fallback to ensure essential brand name is displayed on error
            if (!companyNameDisplay.textContent) {
                companyNameDisplay.textContent = "Maison Trüvra";
            }
        });
    */
    // If the above API call is not used, the values in the HTML will be used.
    // Ensure HTML placeholders reflect Maison Trüvra branding.


    // 2. Set default dates
    const today = new Date();
    invoiceDateInput.valueAsDate = today;
    const dueDate = new Date(today);
    const dueDays = parseInt(paymentDueDaysDisplay.textContent || "30", 10);
    dueDate.setDate(today.getDate() + dueDays);
    invoiceDueDateInput.valueAsDate = dueDate;

    invoiceDateInput.addEventListener('change', () => {
        const newInvoiceDate = new Date(invoiceDateInput.value);
        const newDueDate = new Date(newInvoiceDate);
        newDueDate.setDate(newInvoiceDate.getDate() + (parseInt(paymentDueDaysDisplay.textContent, 10) || 30));
        invoiceDueDateInput.valueAsDate = newDueDate;
    });
    

    // 3. Fetch professional users for the select dropdown
    // Replace with your actual API endpoint for fetching professional users
    fetchAPIData('/api/admin/users?role=professional', {}, 'GET')
        .then(response => {
            if (response && response.users && Array.isArray(response.users)) {
                professionalUsersData = response.users; // Store for later use
                professionalUserSelect.innerHTML = '<option value="">Sélectionnez un client</option>'; // Clear existing
                response.users.forEach(user => {
                    const option = document.createElement('option');
                    option.value = user.id;
                    // Display company name if available, otherwise full name
                    option.textContent = user.company_name || `${user.first_name || ''} ${user.last_name || ''}`.trim() || `Utilisateur ID: ${user.id}`;
                    professionalUserSelect.appendChild(option);
                });
            } else {
                console.error('Failed to load professional users or invalid format:', response);
                professionalUserSelect.innerHTML = '<option value="">Erreur de chargement</option>';
            }
        })
        .catch(error => {
            console.error('Error fetching professional users:', error);
            professionalUserSelect.innerHTML = '<option value="">Erreur de chargement</option>';
        });

    // --- Event Listeners ---

    professionalUserSelect.addEventListener('change', (event) => {
        const selectedUserId = event.target.value;
        if (selectedUserId) {
            const selectedUser = professionalUsersData.find(user => user.id.toString() === selectedUserId);
            if (selectedUser) {
                populateCustomerInfo(selectedUser);
                generateInvoiceNumber(selectedUser.company_name || 'Client');
            } else {
                clearCustomerInfo();
                invoiceNumberDisplay.textContent = 'En attente de sélection client';
            }
        } else {
            clearCustomerInfo();
            invoiceNumberDisplay.textContent = 'En attente de sélection client';
        }
    });

    addInvoiceItemBtn.addEventListener('click', addInvoiceItemRow);

    invoiceItemsTbody.addEventListener('click', (event) => {
        if (event.target.classList.contains('remove-item-btn')) {
            event.target.closest('tr').remove();
            calculateTotals();
        }
    });

    invoiceItemsTbody.addEventListener('input', (event) => {
        if (event.target.classList.contains('item-quantity') || 
            event.target.classList.contains('item-unit-price-ht') ||
            event.target.classList.contains('item-vat-rate')) {
            const row = event.target.closest('tr');
            updateLineItemTotals(row);
            calculateTotals();
        }
    });

    saveInvoiceBtn.addEventListener('click', handleSaveInvoice);
    previewInvoiceBtn.addEventListener('click', handlePreviewInvoice);


    // --- Functions ---

    function populateCustomerInfo(userData) {
        customerCompanyNameDisplay.textContent = userData.company_name || 'N/A';
        customerContactNameDisplay.textContent = `${userData.first_name || ''} ${userData.last_name || ''}`.trim() || 'N/A';
        
        // Billing Address (assuming address fields like street, city, postal_code, country exist)
        const billingAddress = [
            userData.billing_address_line1,
            userData.billing_address_line2,
            `${userData.billing_city || ''} ${userData.billing_postal_code || ''}`,
            userData.billing_country
        ].filter(Boolean).join('<br>');
        customerBillingAddressDisplay.innerHTML = billingAddress || 'N/A';

        customerSiretDisplay.textContent = userData.siret_number || 'N/A';
        customerVatDisplay.textContent = userData.vat_number || 'N/A';

        // Delivery Address (can be same as billing or different fields)
        deliveryCompanyNameDisplay.textContent = userData.delivery_company_name || userData.company_name || 'N/A';
        const deliveryAddress = [
            userData.delivery_address_line1,
            userData.delivery_address_line2,
            `${userData.delivery_city || ''} ${userData.delivery_postal_code || ''}`,
            userData.delivery_country
        ].filter(Boolean).join('<br>');
        customerDeliveryAddressDisplay.innerHTML = deliveryAddress || 'N/A';
    }

    function clearCustomerInfo() {
        customerCompanyNameDisplay.textContent = 'Nom de l\'Entreprise Cliente';
        customerContactNameDisplay.textContent = 'Prénom Nom (Contact)';
        customerBillingAddressDisplay.innerHTML = 'Adresse de facturation';
        customerSiretDisplay.textContent = '';
        customerVatDisplay.textContent = '';
        deliveryCompanyNameDisplay.textContent = 'Nom de l\'Entreprise Cliente (Livraison)';
        customerDeliveryAddressDisplay.innerHTML = 'Adresse de livraison';
    }

    function generateInvoiceNumber(customerIdentifier) {
        const date = new Date(invoiceDateInput.value || Date.now());
        const year = date.getFullYear();
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        const yyyymmdd = `${year}${month}${day}`;
        
        // Sanitize customerIdentifier for use in filename/ID (basic example)
        const safeCustomerName = customerIdentifier.replace(/[^a-zA-Z0-9]/g, '').substring(0, 10);
        
        // XXX part: For frontend, can be a timestamp or random. Backend should ensure uniqueness.
        const xxx = Math.floor(Math.random() * 900) + 100; // Example: 3 random digits
        
        invoiceNumberDisplay.textContent = `${safeCustomerName.toUpperCase()}-${yyyymmdd}-${xxx}`;
    }

    function addInvoiceItemRow() {
        const newRow = invoiceItemTemplate.content.cloneNode(true);
        invoiceItemsTbody.appendChild(newRow);
        // Attach event listeners or re-calculate if needed for the new row specifically
        // For simplicity, global tbody listener handles inputs.
    }

    function updateLineItemTotals(row) {
        const quantityInput = row.querySelector('.item-quantity');
        const unitPriceInput = row.querySelector('.item-unit-price-ht');
        const vatRateSelect = row.querySelector('.item-vat-rate');
        const totalHTSpan = row.querySelector('.item-total-ht');
        const totalTTCSpan = row.querySelector('.item-total-ttc');

        const quantity = parseFloat(quantityInput.value) || 0;
        const unitPriceHT = parseFloat(unitPriceInput.value) || 0;
        const vatRate = parseFloat(vatRateSelect.value) || 0;

        const totalHT = quantity * unitPriceHT;
        const totalTTC = totalHT * (1 + vatRate / 100);

        totalHTSpan.textContent = totalHT.toFixed(2);
        totalTTCSpan.textContent = totalTTC.toFixed(2);
    }

    function calculateTotals() {
        let overallSubtotalHT = 0;
        const vatDetails = {}; // To store VAT amounts per rate: { '20': 100, '5.5': 20 }

        invoiceItemsTbody.querySelectorAll('tr').forEach(row => {
            const quantity = parseFloat(row.querySelector('.item-quantity').value) || 0;
            const unitPriceHT = parseFloat(row.querySelector('.item-unit-price-ht').value) || 0;
            const vatRate = parseFloat(row.querySelector('.item-vat-rate').value); // Keep as string for key

            const lineTotalHT = quantity * unitPriceHT;
            overallSubtotalHT += lineTotalHT;

            if (!isNaN(vatRate)) { // Ensure vatRate is a number before using it in calculations
                const vatAmount = lineTotalHT * (vatRate / 100);
                const vatRateStr = vatRate.toString(); // Use string for object key
                if (vatDetails[vatRateStr]) {
                    vatDetails[vatRateStr] += vatAmount;
                } else {
                    vatDetails[vatRateStr] = vatAmount;
                }
            }
        });

        subtotalHTDisplay.textContent = overallSubtotalHT.toFixed(2);

        vatSummaryContainer.innerHTML = ''; // Clear previous VAT summary
        let overallTotalVAT = 0;
        for (const rate in vatDetails) {
            if (vatDetails.hasOwnProperty(rate) && vatDetails[rate] > 0) {
                const vatAmount = vatDetails[rate];
                overallTotalVAT += vatAmount;
                const div = document.createElement('div');
                div.innerHTML = `<span>TVA (${rate}%) :</span> <span>${vatAmount.toFixed(2)} €</span>`;
                vatSummaryContainer.appendChild(div);
            }
        }
        
        totalVATDisplay.textContent = overallTotalVAT.toFixed(2);
        const grandTotalTTC = overallSubtotalHT + overallTotalVAT;
        grandTotalTTCDisplay.textContent = grandTotalTTC.toFixed(2);
        netToPayDisplay.textContent = grandTotalTTC.toFixed(2); // Assuming net to pay is same as grand total
    }
    
    function getInvoiceData() {
        const items = [];
        invoiceItemsTbody.querySelectorAll('tr').forEach(row => {
            const description = row.querySelector('.item-description').value;
            const quantity = parseFloat(row.querySelector('.item-quantity').value);
            const unitPriceHT = parseFloat(row.querySelector('.item-unit-price-ht').value);
            const vatRate = parseFloat(row.querySelector('.item-vat-rate').value);
            const totalHT = parseFloat(row.querySelector('.item-total-ht').textContent);
            const totalTTC = parseFloat(row.querySelector('.item-total-ttc').textContent);

            if (description && !isNaN(quantity) && !isNaN(unitPriceHT)) { // Basic validation
                 items.push({
                    description,
                    quantity,
                    unit_price_ht: unitPriceHT,
                    vat_rate: vatRate,
                    total_ht: totalHT,
                    total_ttc: totalTTC
                });
            }
        });

        const invoiceData = {
            professional_user_id: professionalUserSelect.value,
            invoice_number: invoiceNumberDisplay.textContent,
            invoice_date: invoiceDateInput.value,
            due_date: invoiceDueDateInput.value,
            // Customer details (can be re-fetched on backend or taken from display for confirmation)
            customer_details: {
                company_name: customerCompanyNameDisplay.textContent,
                contact_name: customerContactNameDisplay.textContent,
                billing_address: customerBillingAddressDisplay.innerHTML.replace(/<br\s*[\/]?>/gi, "\n"), // Convert <br> to newlines
                siret: customerSiretDisplay.textContent,
                vat_number: customerVatDisplay.textContent,
                delivery_address: customerDeliveryAddressDisplay.innerHTML.replace(/<br\s*[\/]?>/gi, "\n")
            },
            items: items,
            subtotal_ht: parseFloat(subtotalHTDisplay.textContent),
            total_vat: parseFloat(totalVATDisplay.textContent),
            vat_details: (() => { // Reconstruct vat_details from summary
                const details = {};
                vatSummaryContainer.querySelectorAll('div').forEach(div => {
                    const text = div.children[0].textContent; // "TVA (20%) :"
                    const rateMatch = text.match(/\((.*?)\%\)/);
                    if (rateMatch && rateMatch[1]) {
                        const rate = rateMatch[1];
                        const amount = parseFloat(div.children[1].textContent);
                        details[rate] = amount;
                    }
                });
                return details;
            })(),
            grand_total_ttc: parseFloat(grandTotalTTCDisplay.textContent),
            net_to_pay: parseFloat(netToPayDisplay.textContent),
            payment_terms: `Paiement à réception de facture, au plus tard sous ${paymentDueDaysDisplay.textContent} jours.`,
            // Company details (can be added by backend or included here)
            // company_info: { 
            //    name: companyNameDisplay.textContent, // Example
            //    address_line1: companyAddress1Display.textContent,
            //    // ... other details from your company for the invoice
            // } 
        };
        return invoiceData;
    }

    async function handleSaveInvoice() {
        const invoiceData = getInvoiceData();
        if (!invoiceData.professional_user_id) {
            // Consider a more refined UI notification than alert()
            console.warn("Attempted to save invoice without selecting a professional client.");
            alert("Veuillez sélectionner un client professionnel.");
            return;
        }
        if (invoiceData.items.length === 0) {
            console.warn("Attempted to save invoice with no items.");
            alert("Veuillez ajouter au moins un article à la facture.");
            return;
        }

        console.log("Invoice data to save:", invoiceData);

        try {
            // Replace with your actual API endpoint for saving invoices
            const response = await fetchAPIData('/api/admin/invoices', invoiceData, 'POST');
            if (response && (response.id || response.invoice_id || response.success)) {
                alert('Facture enregistrée avec succès !');
                // Optionally redirect or clear form
                // window.location.href = `/admin/invoices/${response.id || response.invoice_id}`;
            } else {
                alert('Erreur lors de l\'enregistrement de la facture: ' + (response.message || response.error || 'Réponse invalide du serveur.'));
            }
        } catch (error) {
            console.error('Error saving invoice:', error);
            alert('Erreur lors de la connexion au serveur pour enregistrer la facture.');
        }
    }
    
    async function handlePreviewInvoice() {
        const invoiceData = getInvoiceData();
         if (!invoiceData.professional_user_id) {
            alert("Veuillez sélectionner un client professionnel pour l'aperçu.");
            return;
        }
        console.log("Invoice data for preview:", invoiceData);
        // This would typically send the data to a backend endpoint that generates a PDF preview
        // For now, it just logs the data.
        // Example:
        // try {
        //     const response = await fetchAPIData('/api/admin/invoices/preview', invoiceData, 'POST', 'blob'); // Expect a blob (PDF)
        //     if (response) {
        //         const fileURL = URL.createObjectURL(response);
        //         window.open(fileURL, '_blank'); // Open PDF in new tab
        //     } else {
        //         alert('Erreur lors de la génération de l\'aperçu.');
        //     }
        // } catch (error) {
        //     console.error('Error generating preview:', error);
        //     alert('Erreur serveur lors de la génération de l\'aperçu.');
        // }
        alert("La fonctionnalité d'aperçu PDF n'est pas encore implémentée. Les données de la facture ont été consignées dans la console.");
    }


    // Initial call to add one empty item row
    addInvoiceItemRow();
});
