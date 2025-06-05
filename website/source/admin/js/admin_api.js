// website/source/admin/js/admin_api.js
const adminApi = {
    BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '/api/admin',

    async _request(method, endpoint, data = null, isFormData = false, timeout = 20000) {
        // ... (existing _request method - no changes needed here from previous versions) ...
        if (typeof this.BASE_URL === 'undefined') {
            console.error("Admin API_BASE_URL is not defined. Ensure admin_config.js is loaded.");
            throw new Error("Admin API configuration error.");
        }
        const url = endpoint.startsWith('http') ? endpoint : `${this.BASE_URL}${endpoint}`;
        
        const controller = new AbortController();
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
            signal: signal
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
            if (responseData.success === undefined && response.status >= 200 && response.status < 300) {
                responseData.success = true;
            }
            return responseData;
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                const timeoutError = new Error(`Request to ${url} timed out.`);
                timeoutError.status = 408;
                timeoutError.data = { message: `Request timed out after ${timeout/1000} seconds.`};
                console.error(`Admin API Error for ${method} ${url}:`, timeoutError.data.message, error);
                if (typeof showAdminToast === 'function') {
                    showAdminToast(timeoutError.data.message || 'Request timed out.', 'error');
                }
                throw timeoutError;
            }
            console.error(`Admin API ${method} request to ${url} failed:`, error.data || error.message, error);
            if (typeof showAdminToast === 'function') {
                showAdminToast(error.data?.message || error.message || 'An unexpected Admin API error occurred.', 'error');
            }
            throw error; 
        }
    },

    // ... (existing auth, dashboard, product, category, user, order, review, settings, inventory methods) ...
    loginAdminStep1Password: function(email, password) { /* ... */ },
    loginAdminStep2VerifyTotp: function(email, totp_code) { /* ... */ },
    initiateSimpleLogin: function() { /* ... */ },
    getAdminUserSelf: function() { return this._request('GET', '/users/me'); },
    updateAdminUserProfile: function(userId, profileData) { return this._request('PUT', `/users/${userId}/profile`, profileData); },
    updateAdminPassword: function(userId, passwordData) { return this._request('PUT', `/users/${userId}/password`, passwordData); },
    initiateTotpSetup: function(currentPassword) { return this._request('POST', '/totp/setup-initiate', { password: currentPassword }); },
    verifyAndEnableTotp: function(totpCode) { return this._request('POST', '/totp/setup-verify', { totp_code: totpCode }); },
    disableTotp: function(currentPassword, totpCode) { return this._request('POST', '/totp/disable', { password: currentPassword, totp_code: totpCode }); },
    getDashboardStats: function() { return this._request('GET', '/dashboard/stats'); },
    getCategories: function() { return this._request('GET', '/categories');},
    addCategory: function(categoryData) { return this._request('POST', '/categories', categoryData, true); /* isFormData = true */},
    getCategoryDetail: function(categoryId) { return this._request('GET', `/categories/${categoryId}`); },
    updateCategory: function(categoryId, categoryData) { return this._request('PUT', `/categories/${categoryId}`, categoryData, true); /* isFormData = true */},
    deleteCategory: function(categoryId) { return this._request('DELETE', `/categories/${categoryId}`); },
    getProducts: function(includeVariants = false) {
        let endpoint = '/products';
        if (includeVariants) {
            endpoint += '?include_variants=true';
        }
        return this._request('GET', endpoint);
    },
    getProductDetail: function(productId) { return this._request('GET', `/products/${productId}`); },
    addProduct: function(productFormData) { return this._request('POST', '/products', productFormData, true); },
    updateProduct: function(productId, productFormData) { return this._request('PUT', `/products/${productId}`, productFormData, true);},
    deleteProduct: function(productId) { return this._request('DELETE', `/products/${productId}`); },
    updateProductOptions: function(productId, optionsData) { return this._request('PUT', `/products/${productId}/options`, { options: optionsData }); },
    getUsers: function(filters = {}) {
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/users${queryParams ? '?' + queryParams : ''}`);
    },
    getUserDetail: function(userId) { return this._request('GET', `/users/${userId}`); },
    updateUser: function(userId, userData) { return this._request('PUT', `/users/${userId}`, userData); },
    getProfessionalUsers: function() { return this._request('GET', '/users/professionals'); }, // For create invoice dropdown
    getOrders: function(filters = {}) {
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/orders${queryParams ? '?' + queryParams : ''}`);
    },
    getOrderDetail: function(orderId) { return this._request('GET', `/orders/${orderId}`); },
    updateOrderStatus: function(orderId, statusData) { return this._request('PUT', `/orders/${orderId}/status`, statusData); },
    addOrderNote: function(orderId, noteData) { return this._request('POST', `/orders/${orderId}/notes`, noteData); },
    getReviews: function(filters = {}) { /* ... */ },
    approveReview: function(reviewId) { /* ... */ },
    unapproveReview: function(reviewId) { /* ... */ },
    deleteReview: function(reviewId) { /* ... */ },
    getSettings: function() { /* ... */ },
    updateSettings: function(settingsData) { /* ... */ },
    getInventoryOffers: function(filters = {}) {
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/inventory/offers${queryParams ? '?' + queryParams : ''}`);
    },
    getInventoryOfferDetail: function(offerId) { return this._request('GET', `/inventory/offers/${offerId}`); },
    createInventoryOffer: function(offerData) { return this._request('POST', '/inventory/offers', offerData); },
    updateInventoryOffer: function(offerId, offerData) { return this._request('PUT', `/inventory/offers/${offerId}`, offerData); },
    deleteInventoryOffer: function(offerId) { return this._request('DELETE', `/inventory/offers/${offerId}`); },
    getDetailedInventoryItems: function(filters = {}) { /* ... */ },
    receiveSerializedStock: function(stockData) { return this._request('POST', '/inventory/serialized/receive', stockData); },
    updateSerializedItemStatus: function(itemUid, statusData) { /* ... */ },
    exportSerializedItemsCsv: function() { /* ... (may need special handling for blob response if not GET) ... */ },
    importSerializedItemsCsv: function(formData) { return this._request('POST', '/inventory/import/serialized_items', formData, true); },
    adjustStock: function(adjustmentData) { return this._request('POST', '/inventory/stock/adjust', adjustmentData); },
    getProductInventoryDetails: function(productCode, variantSkuSuffix = null) { /* ... */ },
    createManualInvoice: function(invoiceData) { return this._request('POST', '/invoices/create-manual', invoiceData); },
    getAdminInvoices: function(filters = {}) { /* ... */ },
    updateAdminInvoiceStatus: function(invoiceId, statusData) { /* ... */ },
    regenerateStaticJson: function() { return this._request('POST', '/site-data/regenerate-static-json'); },


    // --- New B2B Quote and PO Admin API Methods ---
    getB2BQuoteRequests: function(filters = {}) {
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/b2b/quote-requests${queryParams ? '?' + queryParams : ''}`);
    },

    getB2BQuoteRequestDetail: function(quoteId) {
        return this._request('GET', `/b2b/quote-requests/${quoteId}`);
    },

    updateB2BQuoteRequest: function(quoteId, quoteData) {
        // quoteData includes { status, admin_notes, valid_until, items: [{item_id, proposed_price_ht}] }
        return this._request('PUT', `/b2b/quote-requests/${quoteId}`, quoteData);
    },

    convertB2BQuoteToOrder: function(quoteId) {
        return this._request('POST', `/b2b/quote-requests/${quoteId}/convert-to-order`);
    },

    // getB2BPurchaseOrders is covered by getOrders with filters like is_b2b_order=true, has_po_reference=true
    // getB2BPODetail is covered by getOrderDetail

    generateB2BInvoiceForOrder: function(orderId) { // Used for PO-originated orders primarily
        return this._request('POST', `/orders/${orderId}/generate-b2b-invoice`);
    }
};
