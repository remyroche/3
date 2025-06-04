// admin_create_invoice.js - Handle manual invoice creation

class InvoiceCreator {
    constructor() {
        this.lineItemCounter = 0;
        this.vatRate = 0.055; // 5.5% TVA
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setTodayDate();
        this.addInitialLineItem();
        this.updateInvoiceNumber();
    }

    setupEventListeners() {
        // Add line item button
        const addLineBtn = document.getElementById('add-line-item-btn');
        if (addLineBtn) {
            addLineBtn.addEventListener('click', () => this.addLineItem());
        }

        // Form submission
        const form = document.getElementById('create-invoice-form');
        if (form) {
            form.addEventListener('submit', (e) => this.handleSubmit(e));
        }

        // Preview button
        const previewBtn = document.getElementById('preview-invoice-btn');
        if (previewBtn) {
            previewBtn.addEventListener('click', () => this.showPreview());
        }

        // Close preview modal
        const closePreviewBtn = document.getElementById('close-preview-btn');
        if (closePreviewBtn) {
            closePreviewBtn.addEventListener('click', () => this.closePreview());
        }

        // Update invoice number when manual number changes
        const manualNumberInput = document.getElementById('manual-number');
        if (manualNumberInput) {
            manualNumberInput.addEventListener('input', () => this.updateInvoiceNumber());
        }

        // Update totals when discount rate changes
        const discountInput = document.getElementById('discount-rate');
        if (discountInput) {
            discountInput.addEventListener('input', () => this.calculateTotals());
        }
    }

    setTodayDate() {
        const today = new Date().toISOString().split('T')[0];
        const dateInput = document.getElementById('invoice-date');
        if (dateInput) {
            dateInput.value = today;
        }
    }

    updateInvoiceNumber() {
        const today = new Date();
        const dateStr = today.toISOString().split('T')[0].replace(/-/g, '');
        const manualNumber = document.getElementById('manual-number').value || '001';
        const invoiceNumber = `TRUVRA-${dateStr}-${manualNumber.padStart(3, '0')}`;
        
        const invoiceNumberInput = document.getElementById('invoice-number');
        if (invoiceNumberInput) {
            invoiceNumberInput.value = invoiceNumber;
        }
    }

    addLineItem() {
        this.lineItemCounter++;
        const container = document.getElementById('line-items-container');
        
        const lineItemDiv = document.createElement('div');
        lineItemDiv.className = 'line-item';
        lineItemDiv.dataset.lineId = this.lineItemCounter;
        
        lineItemDiv.innerHTML = `
            <div class="line-item-grid">
                <div>
                    <label class="form-label text-sm">Article</label>
                    <input 
                        type="text" 
                        name="line_items[${this.lineItemCounter}][product_name]" 
                        class="form-input-admin"
                        required
                        placeholder="Nom du produit"
                    >
                </div>
                <div>
                    <label class="form-label text-sm">Quantité</label>
                    <input 
                        type="number" 
                        name="line_items[${this.lineItemCounter}][quantity]" 
                        class="form-input-admin line-quantity"
                        min="1" 
                        step="1"
                        required
                        placeholder="1"
                    >
                </div>
                <div>
                    <label class="form-label text-sm">N° Identification</label>
                    <input 
                        type="text" 
                        name="line_items[${this.lineItemCounter}][product_id]" 
                        class="form-input-admin"
                        required
                        placeholder="ID produit"
                    >
                </div>
                <div>
                    <label class="form-label text-sm">Prix unitaire HT (€)</label>
                    <input 
                        type="number" 
                        name="line_items[${this.lineItemCounter}][unit_price]" 
                        class="form-input-admin line-price"
                        min="0" 
                        step="0.01"
                        required
                        placeholder="0.00"
                    >
                </div>
                <div class="flex flex-col">
                    <label class="form-label text-sm">Montant HT</label>
                    <div class="flex items-center space-x-2">
                        <span class="line-total font-semibold">0,00 €</span>
                        <button type="button" class="remove-line-btn" onclick="invoiceCreator.removeLineItem(${this.lineItemCounter})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        container.appendChild(lineItemDiv);
        
        // Add event listeners for calculation
        const quantityInput = lineItemDiv.querySelector('.line-quantity');
        const priceInput = lineItemDiv.querySelector('.line-price');
        
        [quantityInput, priceInput].forEach(input => {
            input.addEventListener('input', () => {
                this.updateLineTotal(this.lineItemCounter);
                this.calculateTotals();
            });
        });
    }

    addInitialLineItem() {
        this.addLineItem();
    }

    removeLineItem(lineId) {
        const lineItem = document.querySelector(`[data-line-id="${lineId}"]`);
        if (lineItem) {
            lineItem.remove();
            this.calculateTotals();
        }
        
        // Ensure at least one line item exists
        const remainingItems = document.querySelectorAll('.line-item');
        if (remainingItems.length === 0) {
            this.addLineItem();
        }
    }

    updateLineTotal(lineId) {
        const lineItem = document.querySelector(`[data-line-id="${lineId}"]`);
        if (!lineItem) return;
        
        const quantity = parseFloat(lineItem.querySelector('.line-quantity').value) || 0;
        const price = parseFloat(lineItem.querySelector('.line-price').value) || 0;
        const total = quantity * price;
        
        const totalSpan = lineItem.querySelector('.line-total');
        totalSpan.textContent = this.formatCurrency(total);
    }

    calculateTotals() {
        const lineItems = document.querySelectorAll('.line-item');
        let totalHT = 0;
        
        lineItems.forEach(item => {
            const quantity = parseFloat(item.querySelector('.line-quantity').value) || 0;
            const price = parseFloat(item.querySelector('.line-price').value) || 0;
            totalHT += quantity * price;
        });
        
        const discountRate = parseFloat(document.getElementById('discount-rate').value) || 0;
        const discountAmount = totalHT * (discountRate / 100);
        const totalAfterDiscount = totalHT - discountAmount;
        const tvaAmount = totalAfterDiscount * this.vatRate;
        const totalNet = totalAfterDiscount + tvaAmount;
        
        // Update display
        document.getElementById('total-ht').textContent = this.formatCurrency(totalHT);
        document.getElementById('total-tva').textContent = this.formatCurrency(tvaAmount);
        document.getElementById('total-discount').textContent = this.formatCurrency(discountAmount);
        document.getElementById('total-net').textContent = this.formatCurrency(totalNet);
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: 'EUR'
        }).format(amount);
    }

    generateInvoiceHTML(formData) {
        const lineItems = this.getLineItemsData();
        const totals = this.calculateTotalsData();
        
        return `
            <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6;">
                <div style="text-align: center; margin-bottom: 40px;">
                    <h1 style="font-size: 24px; margin-bottom: 20px;">Facture B2B</h1>
                    <div style="font-size: 18px; font-weight: bold; margin-bottom: 20px;">LOGO</div>
                    <div style="font-weight: bold;">
                        Maison Trüvra,<br>
                        Producteur récoltant
                    </div>
                </div>
                
                <div style="margin-bottom: 30px;">
                    <div style="font-weight: bold; margin-bottom: 5px;">
                        ${formData.client_first_name} ${formData.client_last_name.toUpperCase()} - ${formData.client_company}
                    </div>
                    <div style="margin-bottom: 5px;"><strong>SIRET :</strong> ${formData.client_siret}</div>
                    <div style="margin-bottom: 5px;"><strong>Adresse de facturation :</strong> ${formData.billing_address.replace(/\n/g, ', ')}</div>
                    <div style="margin-bottom: 5px;"><strong>Adresse de livraison :</strong> ${formData.delivery_address.replace(/\n/g, ', ')}</div>
                    <div style="margin-top: 20px;">
                        <div style="margin-bottom: 5px;"><strong>Facture #${formData.invoice_number}</strong></div>
                        <div><strong>Date d'émission de la facture :</strong> ${new Date(formData.invoice_date).toLocaleDateString('fr-FR')}</div>
                    </div>
                </div>
                
                <div style="margin-bottom: 40px;">
                    <div style="display: grid; grid-template-columns: 2fr 1fr 2fr 1fr 1fr; gap: 10px; font-weight: bold; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px;">
                        <div>Article</div>
                        <div>Quantité</div>
                        <div>Numéro d'identification<br>+ hyperlien vers le passeport du produit</div>
                        <div>Prix unitaire HT</div>
                        <div>Montant HT</div>
                    </div>
                    
                    ${lineItems.map(item => `
                        <div style="display: grid; grid-template-columns: 2fr 1fr 2fr 1fr 1fr; gap: 10px; padding: 10px 0; border-bottom: 1px solid #ccc;">
                            <div>${item.product_name}</div>
                            <div>${item.quantity}</div>
                            <div><a href="#" style="color: #2d5a27; text-decoration: underline;">${item.product_id}</a></div>
                            <div>${this.formatCurrency(item.unit_price)}</div>
                            <div>${this.formatCurrency(item.quantity * item.unit_price)}</div>
                        </div>
                    `).join('')}
                    
                    <div style="height: 200px;"></div>
                </div>
                
                <div style="text-align: right; margin-bottom: 40px; font-size: 16px;">
                    <div style="margin-bottom: 10px;"><strong>Total HT :</strong> ${this.formatCurrency(totals.totalHT)}</div>
                    <div style="margin-bottom: 10px;"><strong>TVA 5.5% :</strong> ${this.formatCurrency(totals.tvaAmount)}</div>
                    <div style="margin-bottom: 10px;"><strong>Remise ${formData.discount_rate}% :</strong> ${this.formatCurrency(totals.discountAmount)}</div>
                    <div style="font-size: 20px; font-weight: bold; margin-top: 15px;">
                        <strong>Montant net à payer en € :</strong> ${this.formatCurrency(totals.totalNet)}
                    </div>
                </div>
                
                <div style="margin-bottom: 40px;">
                    <h3 style="font-size: 18px; margin-bottom: 20px;">Modalités de règlement :</h3>
                    <div style="margin-bottom: 10px;"><strong>BIC :</strong></div>
                    <div style="margin-bottom: 20px;"><strong>IBAN :</strong></div>
                    <p style="font-size: 12px; line-height: 1.5; text-align: justify;">
                        La présente facture est payable sous 30 jours. Passé ce délai, sans obligation d'envoi d'une relance, 
                        conformément à l'article L441-30 II du Code de Commerce, il sera appliqué une pénalité calculée à un taux 
                        annuel de 100%. Une indemnité forfaitaire pour frais de recouvrement de 40€ sera aussi exigible.
                    </p>
                </div>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 30px;">
                    <p style="font-size: 12px; line-height: 1.5; text-align: justify; margin: 0;">
                        Chez Maison Trüvra, la fraîcheur, l'authentificité et la traçabilité de nos produits est primordiale. 
                        C'est dans cet esprit que chaque produit a son propre numéro d'identification. En cliquant sur ce numéro, 
                        vous serez redirigé vers une page web unique associée à votre produit. Vous trouverez sur cette page la date 
                        de récolte et de traitement associées à votre achat.
                    </p>
                </div>
                
                <div style="border-top: 1px solid #ccc; padding-top: 20px; font-size: 11px; text-align: center; line-height: 1.4;">
                    <p style="margin-bottom: 10px;">
                        [statut juridique de la société] Maison Trüvra - SIRET xxxxx - Capital social de xx € - 
                        Siège social 14 rue de la Libération, 933330 Neuilly-sur-Marne - Numéro d'Identification à la TVA FRxx
                    </p>
                    <p style="margin: 0;">
                        Contactez-nous à xx@.... ou sur Instagram @maisontruvra
                    </p>
                </div>
            </div>
        `;
    }

    getLineItemsData() {
        const lineItems = document.querySelectorAll('.line-item');
        const data = [];
        
        lineItems.forEach(item => {
            const productName = item.querySelector('input[name*="[product_name]"]').value;
            const quantity = parseFloat(item.querySelector('input[name*="[quantity]"]').value) || 0;
            const productId = item.querySelector('input[name*="[product_id]"]').value;
            const unitPrice = parseFloat(item.querySelector('input[name*="[unit_price]"]').value) || 0;
            
            if (productName && quantity > 0 && productId && unitPrice > 0) {
                data.push({
                    product_name: productName,
                    quantity: quantity,
                    product_id: productId,
                    unit_price: unitPrice
                });
            }
        });
        
        return data;
    }

    calculateTotalsData() {
        const lineItems = this.getLineItemsData();
        let totalHT = 0;
        
        lineItems.forEach(item => {
            totalHT += item.quantity * item.unit_price;
        });
        
        const discountRate = parseFloat(document.getElementById('discount-rate').value) || 0;
        const discountAmount = totalHT * (discountRate / 100);
        const totalAfterDiscount = totalHT - discountAmount;
        const tvaAmount = totalAfterDiscount * this.vatRate;
        const totalNet = totalAfterDiscount + tvaAmount;
        
        return {
            totalHT: totalHT,
            discountAmount: discountAmount,
            tvaAmount: tvaAmount,
            totalNet: totalNet
        };
    }

    getFormData() {
        const form = document.getElementById('create-invoice-form');
        const formData = new FormData(form);
        const data = {};
        
        // Get basic form data
        for (let [key, value] of formData.entries()) {
            data[key] = value;
        }
        
        // Get line items
        data.line_items = this.getLineItemsData();
        
        return data;
    }

    showPreview() {
        const formData = this.getFormData();
        
        // Validate required fields
        if (!this.validateForm(formData)) {
            return;
        }
        
        const previewContent = this.generateInvoiceHTML(formData);
        document.getElementById('invoice-preview-content').innerHTML = previewContent;
        document.getElementById('invoice-preview-modal').classList.remove('hidden');
    }

    closePreview() {
        document.getElementById('invoice-preview-modal').classList.add('hidden');
    }

    validateForm(formData) {
        const requiredFields = [
            'client_first_name', 'client_last_name', 'client_company', 
            'client_siret', 'billing_address', 'delivery_address', 
            'invoice_date', 'manual_number'
        ];
        
        for (let field of requiredFields) {
            if (!formData[field]) {
                this.showToast(`Le champ ${field} est requis`, 'error');
                return false;
            }
        }
        
        if (!formData.line_items || formData.line_items.length === 0) {
            this.showToast('Au moins une ligne de facture est requise', 'error');
            return false;
        }
        
        return true;
    }

    async handleSubmit(e) {
        e.preventDefault();
        
        const formData = this.getFormData();
        
        if (!this.validateForm(formData)) {
            return;
        }
        
        try {
            // Here you would typically send the data to your backend
            console.log('Invoice data:', formData);
            
            // For now, just show a success message and the preview
            this.showToast('Facture générée avec succès!', 'success');
            this.showPreview();
            
            // You can add API call here:
            // const response = await fetch('/api/invoices', {
            //     method: 'POST',
            //     headers: { 'Content-Type': 'application/json' },
            //     body: JSON.stringify(formData)
            // });
            
        } catch (error) {
            console.error('Error creating invoice:', error);
            this.showToast('Erreur lors de la création de la facture', 'error');
        }
    }

    showToast(message, type = 'info') {
        // Simple toast notification - you can enhance this
        const toast = document.createElement('div');
        toast.className = `fixed top-4 right-4 p-4 rounded shadow-lg z-50 ${
            type === 'success' ? 'bg-green-500' : 
            type === 'error' ? 'bg-red-500' : 'bg-blue-500'
        } text-white`;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.invoiceCreator = new InvoiceCreator();
}); page web unique associée à votre produit. Vous trouverez sur cette page la date 
                        de récolte et de traitement associées à votre achat.
                    </p>
                </div>
                
                <div style="border-top: 1px solid #ccc; padding-top: 20px; font-size: 11px; text-align: center; line-height: 1.4;">
                    <p style="margin-bottom: 10px;">
                        [statut juridique de la société] Maison Trüvra - SIRET xxxxx - Capital social de xx € - 
                        Siège social 14 rue de la Libération, 933330 Neuilly-sur-Marne - Numéro d'Identification à la TVA FRxx
                    </p>
                    <p style="margin: 0;">
                        Contactez-nous à xx@.... ou sur Instagram @maisontruvra
                    </p>
                </div>
            </div>
        `;