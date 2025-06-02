document.addEventListener('DOMContentLoaded', () => {
    // Ensure this code runs only on the create invoice page
    if (document.getElementById('create-invoice-form')) {
        populateProfessionalUsers();
        setupInvoiceFormListeners();
    }
});

async function populateProfessionalUsers() {
    const selectElement = document.getElementById('professional-user-select');
    try {
        const users = await makeAdminApiRequest('/users/professionals'); // This new admin endpoint needs to be created
        selectElement.innerHTML = '<option value="">-- Select a User --</option>'; // Clear loading text
        users.forEach(user => {
            const option = document.createElement('option');
            option.value = user.id;
            option.textContent = `${user.company_name || user.first_name + ' ' + user.last_name} (${user.email})`;
            selectElement.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load professional users:', error);
        selectElement.innerHTML = '<option value="">Error loading users</option>';
        showGlobalMessage('Error loading professional users.', 'error');
    }
}

function setupInvoiceFormListeners() {
    const addLineItemBtn = document.getElementById('add-line-item-btn');
    const lineItemsContainer = document.getElementById('line-items-container');
    const form = document.getElementById('create-invoice-form');
    let lineItemIndex = 0;

    // Add initial line item
    addLineItemRow(lineItemIndex++);

    addLineItemBtn.addEventListener('click', () => {
        addLineItemRow(lineItemIndex++);
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const data = {
            b2b_user_id: formData.get('b2b_user_id'),
            notes: formData.get('notes'),
            line_items: []
        };

        // Collect line items
        const lineItemRows = lineItemsContainer.querySelectorAll('.line-item-row');
        for (const row of lineItemRows) {
            const description = row.querySelector('input[name="description"]').value;
            const quantity = row.querySelector('input[name="quantity"]').value;
            const unit_price = row.querySelector('input[name="unit_price"]').value;

            if (description && quantity && unit_price) {
                data.line_items.push({
                    description,
                    quantity: parseInt(quantity, 10),
                    unit_price: parseFloat(unit_price)
                });
            }
        }
        
        if (!data.b2b_user_id || data.line_items.length === 0) {
            showGlobalMessage('Please select a user and add at least one valid line item.', 'error');
            return;
        }

        try {
            // This new admin endpoint needs to be created
            const result = await makeAdminApiRequest('/invoices/create', 'POST', data); 
            showGlobalMessage(`Invoice ${result.invoice_number} created successfully!`, 'success');
            form.reset();
            lineItemsContainer.innerHTML = ''; // Clear line items
            addLineItemRow(0); // Add one back
        } catch (error) {
            console.error('Failed to create invoice:', error);
            showGlobalMessage(error.data?.message || 'Failed to create invoice.', 'error');
        }
    });

    function addLineItemRow(index) {
        const row = document.createElement('div');
        row.className = 'grid grid-cols-12 gap-4 mb-2 line-item-row';
        row.innerHTML = `
            <div class="col-span-6">
                <input type="text" name="description" placeholder="Item Description" class="form-input w-full" required>
            </div>
            <div class="col-span-2">
                <input type="number" name="quantity" placeholder="Qty" min="1" class="form-input w-full" required>
            </div>
            <div class="col-span-3">
                <input type="number" name="unit_price" placeholder="Unit Price" min="0" step="0.01" class="form-input w-full" required>
            </div>
            <div class="col-span-1 flex items-center">
                <button type="button" class="text-red-500 hover:text-red-700" onclick="this.parentElement.parentElement.remove()">X</button>
            </div>
        `;
        lineItemsContainer.appendChild(row);
    }
}
