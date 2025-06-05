// website/source/admin/js/admin_create_invoice_js.js

document.addEventListener('DOMContentLoaded', () => {
    // Ensure this code runs only on the create invoice page
    if (document.body.id !== 'page-admin-create-invoice') {
        // console.log("Not on admin_create_invoice page, skipping admin_create_invoice_js.js logic.");
        return;
    }
    console.log("admin_create_invoice_js.js: Initializing for page-admin-create-invoice.");


    // --- DOM Elements ---
    const professionalUserSelect = document.getElementById('professional-user-select');
    const invoiceItemsTbody = document.getElementById('invoice-items-tbody');
    const addInvoiceItemBtn = document.getElementById('add-invoice-item-btn');
    const invoiceItemTemplate = document.getElementById('invoice-item-template');
    
    const invoiceDateInput = document.getElementById('invoice-date');
    const invoiceDueDateInput = document.getElementById('invoice-due-date');
    const invoiceNumberDisplay = document.getElementById('invoice-number-display'); // Span in preview
    const adminInvoiceNotesInput = document.getElementById('admin-invoice-notes'); // Textarea for admin notes

    // Company info display elements (in preview)
    const companyNameDisplay = document.getElementById('company-name');
    const companyAddress1Display = document.getElementById('company-address1');
    const companyCityPostalCountryDisplay = document.getElementById('company-city-postal-country');
    const companySiretDisplay = document.getElementById('company-siret');
    const companyVatDisplay = document.getElementById('company-vat');
    const companyIbanDisplay = document.getElementById('company-iban');
    const companySwiftDisplay = document.getElementById('company-swift');
    const paymentDueDaysDisplay = document.getElementById('payment-due-days');

    // Customer billing info display elements (in preview)
    const customerCompanyNameDisplay = document.getElementById('customer-company-name');
    const customerContactNameDisplay = document.getElementById('customer-contact-name');
    const customerBillingAddressDisplay = document.getElementById('customer-billing-address');
    const customerSiretDisplay = document.getElementById('customer-siret-display');
    const customerVatDisplay = document.getElementById('customer-vat-display');

    // Customer delivery info display elements (in preview)
    const deliveryCompanyNameDisplay = document.getElementById('delivery-company-name');
    const customerDeliveryAddressDisplay = document.getElementById('customer-delivery-address');

    // Totals display (in preview)
    const subtotalHTDisplay = document.getElementById('subtotal-ht');
    const vatSummaryContainer = document.getElementById('vat-summary-container');
    const totalVATDisplay = document.getElementById('total-vat');
    const grandTotalTTCDisplay = document.getElementById('grand-total-ttc');
    const netToPayDisplay = document.getElementById('net-to-pay');
    
    const invoiceForm = document.getElementById('create-invoice-form'); // The main form for inputs
    // const saveInvoiceBtn = document.getElementById('save-invoice-btn'); // Replaced by form submit
    const previewPdfBtn = document.getElementById('preview-invoice-pdf-btn');

    // --- State Variables ---
    let professionalUsersData = []; // To store fetched professional users with their details
    let companyInfoData = null; // To store fetched company info

    // --- Initialize Page ---
    async function initializePage() {
        console.log("admin_create_invoice_js.js: initializePage called");
        await loadCompanyInfoForPreview(); // Load and display company info in preview
        await populateProfessionalUsers(); // Populate client dropdown
        setDefaultDates();
        addInvoiceItemRow(); // Add one initial empty line item
        
        // Attach event listeners
        if (professionalUserSelect) {
            professionalUserSelect.addEventListener('change', handleProfessionalUserChange);
        }
        if (addInvoiceItemBtn) {
            addInvoiceItemBtn.addEventListener('click', addInvoiceItemRow);
        }
        if (invoiceItemsTbody) {
            invoiceItemsTbody.addEventListener('click', handleItemTableActions);
            invoiceItemsTbody.addEventListener('input', handleItemTableInput);
        }
        if (invoiceDateInput) {
            invoiceDateInput.addEventListener('change', updateDueDateBasedOnInvoiceDate);
        }
        if (invoiceForm) {
            invoiceForm.addEventListener('submit', handleFormSubmit);
        }
        if (previewPdfBtn) {
            previewPdfBtn.addEventListener('click', handlePreviewInvoiceAsPDF);
        }

        // Initial calculation and preview update
        updateAllPreviewFields(); 
        console.log("admin_create_invoice_js.js: Initialization complete.");
    }

    async function loadCompanyInfoForPreview() {
        try {
            // Assuming adminApi.getSettings() can fetch company details or you have a dedicated endpoint
            // For now, using placeholders or potentially hardcoded values if API doesn't provide this.
            // This part would ideally fetch from backend, e.g., adminApi.getCompanyInfo()
            companyInfoData = { // Placeholder data
                name: "Maison Trüvra SARL",
                tagline: "Propriétaire récoltant",
                address_line1: "1 Rue de la Truffe",
                city_postal_country: "75001 Paris, France",
                siret: "FRXX123456789",
                vat_number: "FRXX123456789",
                iban: "FRXX XXXX XXXX XXXX XXXX XXX",
                swift: "XXXXXXX",
                invoice_due_days: 30,
                logo_url: "../images/maison_truvra_invoice_logo.png" // Relative to HTML, ensure correct path
            };
            // If fetched via API: companyInfoData = await adminApi.getCompanyInfo();

            if (companyInfoData) {
                if (companyNameDisplay) companyNameDisplay.textContent = companyInfoData.name;
                // const companyTaglineDisplay = document.querySelector('.invoice-preview-header .company-tagline');
                // if (companyTaglineDisplay) companyTaglineDisplay.textContent = companyInfoData.tagline;
                if (companyAddress1Display) companyAddress1Display.textContent = companyInfoData.address_line1;
                if (companyCityPostalCountryDisplay) companyCityPostalCountryDisplay.textContent = companyInfoData.city_postal_country;
                if (companySiretDisplay) companySiretDisplay.textContent = companyInfoData.siret;
                if (companyVatDisplay) companyVatDisplay.textContent = companyInfoData.vat_number;
                if (companyIbanDisplay) companyIbanDisplay.textContent = companyInfoData.iban;
                if (companySwiftDisplay) companySwiftDisplay.textContent = companyInfoData.swift;
                if (paymentDueDaysDisplay) paymentDueDaysDisplay.textContent = companyInfoData.invoice_due_days;

                // Update logo in preview
                const logoImg = document.querySelector('.invoice-preview-header .company-logo');
                if (logoImg && companyInfoData.logo_url) {
                    logoImg.src = companyInfoData.logo_url;
                }
            }
        } catch (error) {
            console.error("Error loading company info for preview:", error);
            if(typeof showAdminToast === 'function') showAdminToast("Erreur chargement infos entreprise.", "error");
        }
    }


    function setDefaultDates() {
        const today = new Date();
        if(invoiceDateInput) invoiceDateInput.valueAsDate = today;
        updateDueDateBasedOnInvoiceDate();
    }

    function updateDueDateBasedOnInvoiceDate() {
        if (!invoiceDateInput || !invoiceDueDateInput || !paymentDueDaysDisplay) return;
        try {
            const issueDate = invoiceDateInput.valueAsDate || new Date();
            const dueDays = parseInt(paymentDueDaysDisplay.textContent, 10) || 30;
            const dueDate = new Date(issueDate);
            dueDate.setDate(issueDate.getDate() + dueDays);
            invoiceDueDateInput.valueAsDate = dueDate;
        } catch (e) {
            console.error("Error setting due date:", e);
            invoiceDueDateInput.value = '';
        }
        updateInvoiceNumberPreview(); // Regenerate invoice number if date changes
    }


    async function populateProfessionalUsers() {
        if (!professionalUserSelect) return;
        professionalUserSelect.innerHTML = `<option value="">${t('admin.invoices.loading_users', 'Chargement des professionnels...')}</option>`;
        try {
            const response = await adminApi.getProfessionalUsers(); // from admin_api.js
            const users = response.users || response; 
            professionalUsersData = users; // Cache for later use

            professionalUserSelect.innerHTML = `<option value="">-- ${t('admin.invoices.select_user', 'Sélectionner un Utilisateur')} --</option>`;
            if (users && users.length > 0) {
                users.forEach(user => {
                    const option = document.createElement('option');
                    option.value = user.id;
                    option.textContent = `${user.company_name || (user.first_name || '') + ' ' + (user.last_name || '')} (${user.email})`;
                    professionalUserSelect.appendChild(option);
                });
            } else {
                 professionalUserSelect.innerHTML = `<option value="">-- ${t('admin.invoices.no_pro_users_found', 'Aucun utilisateur B2B trouvé')} --</option>`;
            }
        } catch (error) {
            console.error('Failed to load professional users:', error);
            professionalUserSelect.innerHTML = `<option value="">${t('admin.invoices.error_loading_users', 'Erreur chargement utilisateurs')}</option>`;
            if(typeof showAdminToast === 'function') showAdminToast(t('admin.invoices.error_loading_users_toast', 'Erreur chargement des utilisateurs B2B.'), 'error');
        }
    }

    function handleProfessionalUserChange(event) {
        const selectedUserId = event.target.value;
        updateCustomerInfoPreview(selectedUserId);
        updateInvoiceNumberPreview(selectedUserId);
    }

    function updateCustomerInfoPreview(userId) {
        const defaultText = 'N/A';
        if (userId) {
            const selectedUser = professionalUsersData.find(user => user.id.toString() === userId);
            if (selectedUser) {
                if(customerCompanyNameDisplay) customerCompanyNameDisplay.textContent = selectedUser.company_name || defaultText;
                if(customerContactNameDisplay) customerContactNameDisplay.textContent = `${selectedUser.first_name || ''} ${selectedUser.last_name || ''}`.trim() || defaultText;
                
                // Assuming address fields exist on user object; adjust if nested or different
                const billingAddress = [
                    selectedUser.billing_address_line1 || selectedUser.address_line1, // Fallback to general address
                    selectedUser.billing_address_line2 || selectedUser.address_line2,
                    `${selectedUser.billing_city || selectedUser.city || ''} ${selectedUser.billing_postal_code || selectedUser.postal_code || ''}`,
                    selectedUser.billing_country || selectedUser.country
                ].filter(Boolean).join('<br>');
                if(customerBillingAddressDisplay) customerBillingAddressDisplay.innerHTML = billingAddress || defaultText;

                if(customerSiretDisplay) customerSiretDisplay.textContent = selectedUser.siret_number || defaultText;
                if(customerVatDisplay) customerVatDisplay.textContent = selectedUser.vat_number || defaultText;

                // Delivery Address (could be same or specific fields like delivery_address_line1)
                const deliveryAddr = [
                    selectedUser.delivery_address_line1 || selectedUser.billing_address_line1 || selectedUser.address_line1,
                    selectedUser.delivery_address_line2 || selectedUser.billing_address_line2 || selectedUser.address_line2,
                    `${selectedUser.delivery_city || selectedUser.billing_city || selectedUser.city || ''} ${selectedUser.delivery_postal_code || selectedUser.billing_postal_code || selectedUser.postal_code || ''}`,
                    selectedUser.delivery_country || selectedUser.billing_country || selectedUser.country
                ].filter(Boolean).join('<br>');
                if(deliveryCompanyNameDisplay) deliveryCompanyNameDisplay.textContent = selectedUser.delivery_company_name || selectedUser.company_name || defaultText;
                if(customerDeliveryAddressDisplay) customerDeliveryAddressDisplay.innerHTML = deliveryAddr || defaultText;
                return;
            }
        }
        // Clear if no user selected or found
        if(customerCompanyNameDisplay) customerCompanyNameDisplay.textContent = 'Nom de l\'Entreprise Cliente';
        if(customerContactNameDisplay) customerContactNameDisplay.textContent = 'Prénom Nom (Contact)';
        if(customerBillingAddressDisplay) customerBillingAddressDisplay.innerHTML = 'Adresse de facturation';
        if(customerSiretDisplay) customerSiretDisplay.textContent = 'SIRET Client';
        if(customerVatDisplay) customerVatDisplay.textContent = 'N° TVA Client';
        if(deliveryCompanyNameDisplay) deliveryCompanyNameDisplay.textContent = 'Nom Entreprise (Livraison)';
        if(customerDeliveryAddressDisplay) customerDeliveryAddressDisplay.innerHTML = 'Adresse de livraison';
    }
    
    function updateInvoiceNumberPreview(selectedUserId = null) {
        if (!invoiceNumberDisplay || !invoiceDateInput) return;

        const date = invoiceDateInput.valueAsDate || new Date();
        const year = date.getFullYear();
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        const yyyymmdd = `${year}${month}${day}`;
        
        let customerIdentifier = "CLIENT";
        if (selectedUserId) {
             const selectedUser = professionalUsersData.find(user => user.id.toString() === selectedUserId);
             if (selectedUser && selectedUser.company_name) {
                 customerIdentifier = selectedUser.company_name.replace(/[^a-zA-Z0-9]/g, '').substring(0, 8).toUpperCase();
             } else if (selectedUser && selectedUser.last_name) {
                 customerIdentifier = selectedUser.last_name.replace(/[^a-zA-Z0-9]/g, '').substring(0, 8).toUpperCase();
             }
        }
        
        const randomNumber = Math.floor(Math.random() * 900) + 100; // Example: 3 random digits
        invoiceNumberDisplay.textContent = `${customerIdentifier}-${yyyymmdd}-${randomNumber}`; // Update preview
    }


    function addInvoiceItemRow() {
        if (!invoiceItemTemplate || !invoiceItemsTbody) return;
        const newRowContent = invoiceItemTemplate.content.cloneNode(true);
        invoiceItemsTbody.appendChild(newRowContent);
        // No need to re-attach listeners if using event delegation on tbody
    }

    function handleItemTableActions(event) {
        if (event.target.classList.contains('remove-item-btn') || event.target.closest('.remove-item-btn')) {
            const row = event.target.closest('tr');
            if (row) {
                row.remove();
                updateAllPreviewFields(); // Recalculate totals after removing an item
            }
        }
    }
    
    function handleItemTableInput(event) {
        const target = event.target;
        if (target.classList.contains('item-quantity') || 
            target.classList.contains('item-unit-price-ht') ||
            target.classList.contains('item-vat-rate') ||
            target.classList.contains('item-description') ) { // Also update if description changes for preview
            
            const row = target.closest('tr');
            if (row) {
                updateLineItemTotalsInPreview(row); // Update this specific row in preview
            }
            calculateAndDisplayOverallTotals(); // Recalculate and display overall totals
        }
    }

    function updateLineItemTotalsInPreview(formRow) { // formRow is the <tr> from the input form area
        const quantity = parseFloat(formRow.querySelector('.item-quantity').value) || 0;
        const unitPriceHT = parseFloat(formRow.querySelector('.item-unit-price-ht').value) || 0;
        const vatRate = parseFloat(formRow.querySelector('.item-vat-rate').value); // Keep as selected value string for key

        const totalHT = quantity * unitPriceHT;
        const totalTTC = totalHT * (1 + vatRate / 100); // Calculate TTC for display

        // Update the spans within the form row itself
        const totalHTSpan = formRow.querySelector('.item-total-ht');
        const totalTTCSpan = formRow.querySelector('.item-total-ttc');
        if(totalHTSpan) totalHTSpan.textContent = totalHT.toFixed(2);
        if(totalTTCSpan) totalTTCSpan.textContent = totalTTC.toFixed(2);
    }
    
    function calculateAndDisplayOverallTotals() {
        if (!invoiceItemsTbody || !subtotalHTDisplay || !vatSummaryContainer || !totalVATDisplay || !grandTotalTTCDisplay || !netToPayDisplay) return;

        let overallSubtotalHT = 0;
        const vatDetails = {}; // { '20': amount, '5.5': amount }

        invoiceItemsTbody.querySelectorAll('tr').forEach(row => {
            const quantity = parseFloat(row.querySelector('.item-quantity').value) || 0;
            const unitPriceHT = parseFloat(row.querySelector('.item-unit-price-ht').value) || 0;
            const vatRateInput = row.querySelector('.item-vat-rate');
            const vatRate = vatRateInput ? parseFloat(vatRateInput.value) : 20; // Default VAT if not found

            const lineTotalHT = quantity * unitPriceHT;
            overallSubtotalHT += lineTotalHT;

            if (!isNaN(vatRate)) {
                const vatAmount = lineTotalHT * (vatRate / 100);
                const vatRateStr = vatRate.toString(); 
                vatDetails[vatRateStr] = (vatDetails[vatRateStr] || 0) + vatAmount;
            }
        });

        subtotalHTDisplay.textContent = `${overallSubtotalHT.toFixed(2)} €`;

        vatSummaryContainer.innerHTML = ''; // Clear previous VAT summary
        let overallTotalVAT = 0;
        for (const rate in vatDetails) {
            if (vatDetails.hasOwnProperty(rate) && vatDetails[rate] > 0.005) { // Only display if VAT amount is significant
                const vatAmount = vatDetails[rate];
                overallTotalVAT += vatAmount;
                const div = document.createElement('div');
                // Using textContent for safety, assuming rate is numeric/simple string.
                const rateSpan = document.createElement('span');
                rateSpan.textContent = `TVA (${rate}%) :`;
                const amountSpan = document.createElement('span');
                amountSpan.textContent = `${vatAmount.toFixed(2)} €`;
                div.appendChild(rateSpan);
                div.appendChild(amountSpan);
                vatSummaryContainer.appendChild(div);
            }
        }
        
        totalVATDisplay.textContent = `${overallTotalVAT.toFixed(2)} €`;
        const grandTotalTTC = overallSubtotalHT + overallTotalVAT;
        grandTotalTTCDisplay.textContent = `${grandTotalTTC.toFixed(2)} €`;
        netToPayDisplay.textContent = `${grandTotalTTC.toFixed(2)} €`;
    }

    function updateAllPreviewFields() {
        const selectedUserId = professionalUserSelect ? professionalUserSelect.value : null;
        updateCustomerInfoPreview(selectedUserId);
        updateInvoiceNumberPreview(selectedUserId); 
        
        invoiceItemsTbody.querySelectorAll('tr').forEach(row => {
            updateLineItemTotalsInPreview(row);
        });
        calculateAndDisplayOverallTotals();
    }
    
    // Periodically update the preview if form fields change
    if (invoiceForm) {
         invoiceForm.addEventListener('input', updateAllPreviewFields);
         invoiceForm.addEventListener('change', updateAllPreviewFields); // For select changes
    }


    function getStructuredInvoiceData() {
        const items = [];
        invoiceItemsTbody.querySelectorAll('tr').forEach(row => {
            const descriptionInput = row.querySelector('.item-description');
            const quantityInput = row.querySelector('.item-quantity');
            const unitPriceInput = row.querySelector('.item-unit-price-ht');
            const vatRateSelect = row.querySelector('.item-vat-rate');

            if (descriptionInput && quantityInput && unitPriceInput && vatRateSelect) {
                const description = descriptionInput.value;
                const quantity = parseFloat(quantityInput.value);
                const unitPriceHT = parseFloat(unitPriceInput.value);
                const vatRate = parseFloat(vatRateSelect.value);

                if (description && !isNaN(quantity) && quantity > 0 && !isNaN(unitPriceHT) && unitPriceHT >= 0 && !isNaN(vatRate)) {
                     items.push({
                        description,
                        quantity,
                        unit_price: unitPriceHT, // Backend expects unit_price
                        vat_rate: vatRate // Send VAT rate for backend calculation or record
                    });
                }
            }
        });

        const invoiceData = {
            b2b_user_id: professionalUserSelect ? professionalUserSelect.value : null,
            // invoice_number: invoiceNumberDisplay ? invoiceNumberDisplay.textContent : null, // Backend should generate final number
            invoice_date: invoiceDateInput ? invoiceDateInput.value : null,
            due_date: invoiceDueDateInput ? invoiceDueDateInput.value : null,
            line_items: items,
            notes: adminInvoiceNotesInput ? adminInvoiceNotesInput.value : '',
            currency: 'EUR', // Or from a form field if variable
            // Totals are usually recalculated by the backend for accuracy, but can be sent for validation
            // subtotal_ht: parseFloat(subtotalHTDisplay.textContent),
            // total_vat: parseFloat(totalVATDisplay.textContent),
            // grand_total_ttc: parseFloat(grandTotalTTCDisplay.textContent),
        };
        return invoiceData;
    }

    async function handleFormSubmit(event) {
        event.preventDefault();
        const submitButton = invoiceForm.querySelector('button[type="submit"]');
        
        const structuredData = getStructuredInvoiceData();

        if (!structuredData.b2b_user_id) {
            if(typeof showAdminToast === 'function') showAdminToast(t('admin.invoices.error_select_user_and_items', 'Veuillez sélectionner un client.'), 'error');
            return;
        }
        if (structuredData.line_items.length === 0) {
            if(typeof showAdminToast === 'function') showAdminToast(t('admin.invoices.error_select_user_and_items', 'Veuillez ajouter au moins une ligne valide.'), 'error');
            return;
        }
        if (!structuredData.invoice_date || !structuredData.due_date) {
             if(typeof showAdminToast === 'function') showAdminToast('Veuillez spécifier la date de facture et la date d\'échéance.', 'error');
            return;
        }

        const invoicePreviewElement = document.querySelector('.invoice-preview-container');
        let invoiceHtmlPreviewString = null;
        if (invoicePreviewElement) {
            const clonedPreview = invoicePreviewElement.cloneNode(true);
            // Remove input fields from the cloned preview to send clean HTML
            clonedPreview.querySelectorAll('input, select, textarea, button#add-invoice-item-btn, button.remove-item-btn').forEach(el => {
                // For inputs/textareas, replace with their value as text
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    const textNode = document.createTextNode(el.value);
                    el.parentNode.replaceChild(textNode, el);
                } else if (el.tagName === 'SELECT') {
                     const selectedOption = el.options[el.selectedIndex];
                     const textNode = document.createTextNode(selectedOption ? selectedOption.textContent : '');
                     el.parentNode.replaceChild(textNode, el);
                }
                else {
                    el.remove();
                }
            });
            invoiceHtmlPreviewString = clonedPreview.innerHTML; // Get innerHTML of the preview container
        } else {
            console.warn("Invoice preview element not found.");
            if(typeof showAdminToast === 'function') showAdminToast("Erreur: Aperçu de facture introuvable.", "error");
            return;
        }
        
        // Add the HTML preview to the payload
        structuredData.invoice_html_preview = invoiceHtmlPreviewString;

        if(submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> ${t('admin.invoices.generating_invoice', 'Génération...')}`;
        }

        try {
            const result = await adminApi.createManualInvoice(structuredData); // from admin_api.js
            if (typeof showAdminToast === 'function') {
                 showAdminToast(t('admin.invoices.create_success_toast', `Facture ${result.invoice_number} créée !`), 'success');
            }
            invoiceForm.reset(); // Reset the input form part
            // Clear line items from the table
            if(invoiceItemsTbody) invoiceItemsTbody.innerHTML = '';
            addInvoiceItemRow(); // Add back one empty row
            setDefaultDates();
            if(professionalUserSelect) professionalUserSelect.value = '';
            updateAllPreviewFields(); // Reset preview
        } catch (error) {
            console.error('Failed to create invoice:', error);
            // Error toast likely handled by adminApi directly
        } finally {
            if(submitButton) {
                submitButton.disabled = false;
                submitButton.innerHTML = `<i class="fas fa-file-invoice mr-2"></i> Générer & Enregistrer la Facture`;
            }
        }
    }
    
    async function handlePreviewInvoiceAsPDF() {
        if (typeof showAdminToast === 'function') showAdminToast("La génération d'aperçu PDF direct est en cours de développement. Le PDF final sera créé lors de l'enregistrement.", 'info', 6000);
        // For a true PDF preview, you'd typically send the data (or the captured HTML)
        // to a backend endpoint that returns a PDF blob, then display that blob.
        // Example (conceptual, requires backend endpoint /api/admin/invoices/preview-pdf):
        /*
        const structuredData = getStructuredInvoiceData();
        const invoicePreviewElement = document.querySelector('.invoice-preview-container');
        structuredData.invoice_html_preview = invoicePreviewElement ? invoicePreviewElement.innerHTML : null;

        if (!structuredData.b2b_user_id || structuredData.line_items.length === 0 || !structuredData.invoice_html_preview) {
            showAdminToast("Veuillez sélectionner un client, ajouter des articles et s'assurer que l'aperçu est visible.", "error");
            return;
        }
        
        try {
            const pdfBlob = await adminApi.generateInvoicePreviewPdf(structuredData); // This method would need to be in admin_api.js
            const fileURL = URL.createObjectURL(pdfBlob);
            window.open(fileURL, '_blank');
            URL.revokeObjectURL(fileURL); // Clean up
        } catch (error) {
            showAdminToast("Erreur lors de la génération de l'aperçu PDF.", "error");
            console.error("Preview PDF error:", error);
        }
        */
    }

    // --- Initial Execution ---
    initializePage();
});

