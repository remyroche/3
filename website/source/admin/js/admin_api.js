// website/source/admin/js/admin_api.js
// This script handles all API communication for the admin panel.

const adminApi = {
    BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '/api/admin',

    async _request(method, endpoint, data = null, isFormData = false) {
        if (typeof this.BASE_URL === 'undefined') {
            console.error("Admin API_BASE_URL is not defined. Ensure admin_config.js is loaded and defines API_BASE_URL.");
            throw new Error("Admin API configuration error.");
        }
        const url = endpoint.startsWith('http') ? endpoint : `${this.BASE_URL}${endpoint}`;
        
        const headers = {};
        if (!isFormData) {
            headers['Content-Type'] = 'application/json';
        }
        
        const storedToken = typeof getAdminAuthToken === 'function' ? getAdminAuthToken() : sessionStorage.getItem('adminAuthToken');
        if (storedToken) {
            headers['Authorization'] = `Bearer ${storedToken}`;
        } else {
            if (!url.endsWith('/login')) { 
                 console.warn(`Admin API request to ${url} without token.`);
            }
        }

        const config = {
            method: method,
            headers: headers,
        };

        if (data) {
            if (isFormData) {
                config.body = data; 
            } else if (method === 'POST' || method === 'PUT' || method === 'PATCH') {
                config.body = JSON.stringify(data);
            }
        }
        
        console.log(`Making Admin API request: ${method} ${url}`);

        try {
            const response = await fetch(url, config);
            if (!response.ok) {
                let errorData = { message: `API Error: ${response.status} ${response.statusText}` };
                try {
                    const errorJson = await response.json();
                    errorData = { ...errorData, ...errorJson }; 
                } catch (e) {
                    console.warn("Admin API error response was not JSON.", e);
                    try { errorData.details = await response.text(); } catch (textErr) { /* ignore */ }
                }
                const error = new Error(errorData.message || `API request failed with status ${response.status}`);
                error.status = response.status;
                error.data = errorData; 
                throw error; 
            }
            if (response.status === 204) { 
                return { success: true, message: "Operation successful (no content)." };
            }
            // Ensure all successful JSON responses are parsed
            const responseData = await response.json();
            // Add success: true if not present, for consistency, unless it's explicitly false
            if (responseData.success === undefined) {
                responseData.success = true;
            }
            return responseData;
        } catch (error) {
            console.error(`Admin API ${method} request to ${url} failed:`, error.data || error.message, error);
            if (typeof showAdminToast === 'function') {
                showAdminToast(error.data?.message || error.message || 'An unexpected Admin API error occurred.', 'error');
            }
            throw error; 
        }
    },

    loginAdmin: function(email, password) {
        return this._request('POST', '/login', { email, password });
    },

    getDashboardStats: function() { // New method for dashboard stats
        return this._request('GET', '/dashboard/stats');
    },

    // --- Product Management ---
    addProduct: function(productData) { 
        return this._request('POST', '/products', productData, true); 
    },
    getProducts: function() {
        return this._request('GET', '/products');
    },
    getProductDetail: function(productId) { 
        return this._request('GET', `/products/${productId}`);
    },
    updateProduct: function(productId, productData) { 
        return this._request('PUT', `/products/${productId}`, productData, true); 
    },
    deleteProduct: function(productId) { 
        return this._request('DELETE', `/products/${productId}`);
    },

    // --- Category Management ---
    addCategory: function(categoryData) { 
        return this._request('POST', '/categories', categoryData, true);
    },
    getCategories: function() {
        return this._request('GET', '/categories');
    },
    getCategoryDetail: function(categoryId) {
        return this._request('GET', `/categories/${categoryId}`);
    },
    updateCategory: function(categoryId, categoryData) { 
        return this._request('PUT', `/categories/${categoryId}`, categoryData, true);
    },
    deleteCategory: function(categoryId) { 
        return this._request('DELETE', `/categories/${categoryId}`);
    },

    // --- User Management ---
    getUsers: function(filters = {}) {
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/users${queryParams ? '?' + queryParams : ''}`);
    },
    getUserDetail: function(userId) {
        return this._request('GET', `/users/${userId}`);
    },
    updateUser: function(userId, userData) {
        return this._request('PUT', `/users/${userId}`, userData);
    },
     getProfessionalUsers: function() { // Added for invoice creation form
        return this._request('GET', '/users/professionals');
    },

    // --- Order Management ---
    getOrders: function(filters = {}) {
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/orders${queryParams ? '?' + queryParams : ''}`);
    },
    getOrderDetail: function(orderId) {
        return this._request('GET', `/orders/${orderId}`);
    },
    updateOrderStatus: function(orderId, statusData) {
        return this._request('PUT', `/orders/${orderId}/status`, statusData);
    },
    addOrderNote: function(orderId, noteData) {
        return this._request('POST', `/orders/${orderId}/notes`, noteData);
    },

    // --- Review Management ---
    getReviews: function(filters = {}) {
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/reviews${queryParams ? '?' + queryParams : ''}`);
    },
    approveReview: function(reviewId) {
        return this._request('PUT', `/reviews/${reviewId}/approve`);
    },
    unapproveReview: function(reviewId) {
        return this._request('PUT', `/reviews/${reviewId}/unapprove`);
    },
    deleteReview: function(reviewId) {
        return this._request('DELETE', `/reviews/${reviewId}`);
    },
    
    // --- Settings Management ---
    getSettings: function() {
        return this._request('GET', '/settings');
    },
    updateSettings: function(settingsData) {
        return this._request('POST', '/settings', settingsData);
    },

    // --- Inventory ---
    getDetailedInventoryItems: function(filters = {}) {
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/inventory/items/detailed${queryParams ? '?' + queryParams : ''}`);
    },
    receiveSerializedStock: function(stockData) {
        return this._request('POST', '/inventory/serialized/receive', stockData); 
    },
    updateSerializedItemStatus: function(itemUid, statusData) {
        return this._request('PUT', `/inventory/serialized/items/${itemUid}/status`, statusData);
    },
    exportSerializedItemsCsv: function() { 
        const url = `${this.BASE_URL}/inventory/export/serialized_items`;
        const storedToken = typeof getAdminAuthToken === 'function' ? getAdminAuthToken() : sessionStorage.getItem('adminAuthToken');
        
        return fetch(url, { headers: { 'Authorization': `Bearer ${storedToken}` } })
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        let errorMsg = `CSV Export failed: ${response.status} ${response.statusText}`;
                        try {
                            const jsonError = JSON.parse(text);
                            if (jsonError && jsonError.message) errorMsg = jsonError.message;
                        } catch (e) { if(text) errorMsg = text; }
                        throw new Error(errorMsg);
                    });
                }
                return response.blob();
            })
            .then(blob => {
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                a.download = `maison_truvra_serialized_inventory_${timestamp}.csv`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(downloadUrl);
                return { success: true, message: "CSV export started."};
            });
    },
    importSerializedItemsCsv: function(formData) { 
        return this._request('POST', '/inventory/import/serialized_items', formData, true);
    },
    adjustStock: function(adjustmentData) { // Renamed from adjustAggregatedStock for simplicity
        return this._request('POST', '/inventory/stock/adjust', adjustmentData);
    },
    getProductInventoryDetails: function(productCode, variantSkuSuffix = null) { // Renamed
        let endpoint = `/inventory/product/${productCode}`;
        if (variantSkuSuffix) {
            endpoint += `?variant_sku_suffix=${encodeURIComponent(variantSkuSuffix)}`;
        }
        return this._request('GET', endpoint);
    },
    // --- Invoice Management (Admin) ---
    createManualInvoice: function(invoiceData) { // New method for admin creating manual invoice
        return this._request('POST', '/invoices/create', invoiceData);
    },
    getAdminInvoices: function(filters = {}) { // New method to get all invoices (admin)
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/invoices${queryParams ? '?' + queryParams : ''}`);
    },
    updateAdminInvoiceStatus: function(invoiceId, statusData) { // New method to update any invoice status (admin)
        return this._request('PUT', `/invoices/${invoiceId}/status`, statusData);
    },

    regenerateStaticJson: function() {
        return this._request('POST', '/regenerate-static-json');
    }
};
