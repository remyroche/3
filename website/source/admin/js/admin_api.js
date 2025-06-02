// website/source/admin/js/admin_api.js
// This script handles all API communication for the admin panel.

// API_BASE_URL should be defined globally by admin_config.js
// e.g., const API_BASE_URL = 'http://localhost:5001/api/admin';

const adminApi = {
    // Use the API_BASE_URL from admin_config.js
    BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '/api/admin', // Fallback for safety

    async _request(method, endpoint, data = null, isFormData = false) {
        if (typeof this.BASE_URL === 'undefined') {
            console.error("Admin API_BASE_URL is not defined. Ensure admin_config.js is loaded and defines API_BASE_URL.");
            throw new Error("Admin API configuration error.");
        }

        // If endpoint starts with http, assume it's a full URL (e.g. for a different service if ever needed)
        // Otherwise, prepend BASE_URL. Most admin endpoints will be relative.
        const url = endpoint.startsWith('http') ? endpoint : `${this.BASE_URL}${endpoint}`;
        
        const headers = {};
        if (!isFormData) {
            headers['Content-Type'] = 'application/json';
        }
        
        const storedToken = typeof getAdminAuthToken === 'function' ? getAdminAuthToken() : sessionStorage.getItem('adminAuthToken');
        if (storedToken) {
            headers['Authorization'] = `Bearer ${storedToken}`;
        } else {
            // For login endpoint, token won't exist yet.
            // For other endpoints, Flask's @admin_required decorator will handle unauthorized access.
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
        
        console.log(`Making Admin API request: ${method} ${url}`); // For debugging

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
                return null; // Or { success: true } if callers expect an object
            }
            return await response.json(); 
        } catch (error) {
            console.error(`Admin API ${method} request to ${url} failed:`, error.data || error.message, error);
            // Let admin_ui.js (showAdminToast) handle displaying the error to the user.
            // The error is re-thrown so the calling function can also react if needed.
            if (typeof showAdminToast === 'function') {
                showAdminToast(error.data?.message || error.message || 'An unexpected Admin API error occurred.', 'error');
            }
            throw error; 
        }
    },

    loginAdmin: function(email, password) {
        // Endpoint is relative to this.BASE_URL (which is /api/admin)
        // So, Flask route is /api/admin/login
        return this._request('POST', '/login', { email, password });
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
    updateUser: function(userId, userData) { // Renamed from updateUserAdmin to just updateUser for consistency
        return this._request('PUT', `/users/${userId}`, userData);
    },

    // --- Order Management ---
    getOrders: function(filters = {}) { // Renamed from getOrdersAdmin
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/orders${queryParams ? '?' + queryParams : ''}`);
    },
    getOrderDetail: function(orderId) { // Renamed from getOrderAdminDetail
        return this._request('GET', `/orders/${orderId}`);
    },
    updateOrderStatus: function(orderId, statusData) { // Renamed from updateOrderStatusAdmin
        return this._request('PUT', `/orders/${orderId}/status`, statusData);
    },
    addOrderNote: function(orderId, noteData) { // Renamed from addOrderNoteAdmin
        return this._request('POST', `/orders/${orderId}/notes`, noteData);
    },

    // --- Review Management ---
    getReviews: function(filters = {}) { // Renamed from getReviewsAdmin
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/reviews${queryParams ? '?' + queryParams : ''}`);
    },
    approveReview: function(reviewId) { // Renamed from approveReviewAdmin
        return this._request('PUT', `/reviews/${reviewId}/approve`);
    },
    unapproveReview: function(reviewId) { // Renamed from unapproveReviewAdmin
        return this._request('PUT', `/reviews/${reviewId}/unapprove`);
    },
    deleteReview: function(reviewId) { // Renamed from deleteReviewAdmin
        return this._request('DELETE', `/reviews/${reviewId}`);
    },
    
    // --- Settings Management ---
    getSettings: function() { // Renamed from getSettingsAdmin
        return this._request('GET', '/settings');
    },
    updateSettings: function(settingsData) { // Renamed from updateSettingsAdmin
        return this._request('POST', '/settings', settingsData);
    },

    // --- Dashboard Stats ---
    getDashboardStats: function() {
        return this._request('GET', '/dashboard/stats');
    },

    // --- Inventory ---
    getDetailedInventoryItems: function(filters = {}) { // Renamed from getDetailedInventoryItemsAdmin
        const queryParams = new URLSearchParams(filters).toString();
        // This endpoint in Flask is /api/admin/inventory/items/detailed
        return this._request('GET', `/inventory/items/detailed${queryParams ? '?' + queryParams : ''}`);
    },
    receiveSerializedStock: function(stockData) {
        return this._request('POST', '/inventory/serialized/receive', stockData); // isFormData might be needed if file uploads are part of this
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
                    // Try to get error message from response if possible
                    return response.text().then(text => {
                        let errorMsg = `CSV Export failed: ${response.status} ${response.statusText}`;
                        try {
                            const jsonError = JSON.parse(text);
                            if (jsonError && jsonError.message) {
                                errorMsg = jsonError.message;
                            }
                        } catch (e) { /* Not a JSON error, use text or default */ 
                            if(text) errorMsg = text;
                        }
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
    adjustAggregatedStock: function(adjustmentData) {
        return this._request('POST', '/inventory/stock/adjust', adjustmentData);
    },
    getAdminProductInventoryDetails: function(productCode, variantSkuSuffix = null) {
        let endpoint = `/inventory/product/${productCode}`;
        if (variantSkuSuffix) {
            endpoint += `?variant_sku_suffix=${encodeURIComponent(variantSkuSuffix)}`;
        }
        return this._request('GET', endpoint);
    },
    regenerateStaticJson: function() {
        return this._request('POST', '/regenerate-static-json');
    }
};
