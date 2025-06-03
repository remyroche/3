// website/source/admin/js/admin_api.js
const adminApi = {
    BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '/api/admin',

    async _request(method, endpoint, data = null, isFormData = false, timeout = 20000) { // Added timeout parameter
        if (typeof this.BASE_URL === 'undefined') {
            console.error("Admin API_BASE_URL is not defined. Ensure admin_config.js is loaded.");
            throw new Error("Admin API configuration error.");
        }
        const url = endpoint.startsWith('http') ? endpoint : `${this.BASE_URL}${endpoint}`;
        
        const controller = new AbortController(); // For timeout
        const signal = controller.signal;
        let timeoutId;

        const headers = {};
        if (!isFormData) {
            headers['Content-Type'] = 'application/json';
        }
        
        const storedToken = typeof getAdminAuthToken === 'function' ? getAdminAuthToken() : sessionStorage.getItem('adminAuthToken');
        if (storedToken) {
            headers['Authorization'] = `Bearer ${storedToken}`;
        } else {
            const noTokenEndpoints = ['/login', '/login/verify-totp', '/login/simplelogin/initiate', '/login/simplelogin/callback'];
            if (!noTokenEndpoints.some(ep => url.endsWith(ep))) { 
                 console.warn(`Admin API request to ${url} without token.`);
            }
        }

        const config = {
            method: method,
            headers: headers,
            signal: signal // Add signal to fetch config
        };

        if (data) {
            if (isFormData) {
                config.body = data; 
            } else if (method === 'POST' || method === 'PUT' || method === 'PATCH') {
                config.body = JSON.stringify(data);
            }
        }
        
        console.log(`Making Admin API request: ${method} ${url}`);

        timeoutId = setTimeout(() => {
            controller.abort();
            console.error(`Admin API request to ${url} timed out after ${timeout}ms.`);
        }, timeout);

        try {
            const response = await fetch(url, config); 
            clearTimeout(timeoutId);
            
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
            const responseData = await response.json();
            // Ensure a 'success' field is present if backend doesn't always send it for 2xx
            if (responseData.success === undefined && response.status >= 200 && response.status < 300) {
                responseData.success = true;
            }
            return responseData;
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                const timeoutError = new Error(`Request to ${url} timed out.`);
                timeoutError.status = 408; // Request Timeout
                timeoutError.data = { message: `Request timed out after ${timeout/1000} seconds.`};
                console.error(`Admin API Error for ${method} ${url}:`, timeoutError.data.message, error);
                if (typeof showAdminToast === 'function') { // Added check
                    showAdminToast(timeoutError.data.message || 'Request timed out.', 'error');
                }
                throw timeoutError;
            }
            console.error(`Admin API ${method} request to ${url} failed:`, error.data || error.message, error);
            if (typeof showAdminToast === 'function') { // Added check
                showAdminToast(error.data?.message || error.message || 'An unexpected Admin API error occurred.', 'error');
            }
            throw error; 
        }
    },

    loginAdminStep1Password: function(email, password) {
        return this._request('POST', '/login', { email, password });
    },
    getDashboardStats: function() { 
        return this._request('GET', '/dashboard/stats');

    loginAdminStep2VerifyTotp: function(email, totp_code) { // New method for TOTP verification
        return this._request('POST', '/login/verify-totp', { email, totp_code });
    },
    
    // SimpleLogin SSO initiation - This will be a direct navigation, not an API data request
    initiateSimpleLogin: function() {
        // The actual redirection is handled by navigating the browser
        window.location.href = `${this.BASE_URL}/login/simplelogin/initiate`;
    },

    // ... (rest of the adminApi methods: getDashboardStats, product, category, user, order, review, settings, inventory management)
    // Ensure they remain unchanged unless directly affected by auth flow.
    getDashboardStats: function() { 
        return this._request('GET', '/dashboard/stats');
    },
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
     getProfessionalUsers: function() {
        return this._request('GET', '/users/professionals');
    },
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
    getSettings: function() {
        return this._request('GET', '/settings');
    },
    updateSettings: function(settingsData) {
        return this._request('POST', '/settings', settingsData);
    },
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
    adjustStock: function(adjustmentData) {
        return this._request('POST', '/inventory/stock/adjust', adjustmentData);
    },
    getProductInventoryDetails: function(productCode, variantSkuSuffix = null) {
        let endpoint = `/inventory/product/${productCode}`;
        if (variantSkuSuffix) {
            endpoint += `?variant_sku_suffix=${encodeURIComponent(variantSkuSuffix)}`;
        }
        return this._request('GET', endpoint);
    },
    createManualInvoice: function(invoiceData) {
        return this._request('POST', '/invoices/create', invoiceData);
    },
    getAdminInvoices: function(filters = {}) {
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/invoices${queryParams ? '?' + queryParams : ''}`);
    },
    updateAdminInvoiceStatus: function(invoiceId, statusData) {
        return this._request('PUT', `/invoices/${invoiceId}/status`, statusData);
    },
    regenerateStaticJson: function() {
        return this._request('POST', '/regenerate-static-json');
    }
};
