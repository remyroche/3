// website/source/admin/js/admin_api.js
// This script handles all API communication for the admin panel.

const adminApi = {
    BASE_URL: '/api/admin', // Ensure this matches admin_bp url_prefix in Python

    /**
     * Generic request handler for admin API calls.
     * @param {string} method - HTTP method (GET, POST, PUT, DELETE).
     * @param {string} endpoint - API endpoint (e.g., '/products').
     * @param {object|null} data - Data to send in the request body (for POST/PUT).
     * @returns {Promise<object|null>} - The JSON response from the API or null for 204.
     * @throws {Error} - Throws an error if the request fails or network issue.
     */
    async _request(method, endpoint, data = null) {
        const url = `${this.BASE_URL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
        };
        // Retrieve the admin authentication token (e.g., JWT) from localStorage or secure storage.
        const storedToken = localStorage.getItem('admin_jwt_token'); 
        if (storedToken) {
            headers['Authorization'] = `Bearer ${storedToken}`;
        } else {
            console.warn('Admin authentication token not found. API requests might be unauthorized.');
            // Optional: Redirect to login if a token is strictly required for all admin endpoints.
            // Example: if (!url.includes('/login')) window.location.href = '/admin/admin_login.html';
        }

        const config = {
            method: method,
            headers: headers,
        };

        if (data && (method === 'POST' || method === 'PUT')) {
            config.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, config);
            if (!response.ok) {
                let errorData;
                try {
                    // Try to parse the error response as JSON
                    errorData = await response.json();
                } catch (e) { 
                    // If response is not JSON (e.g., plain text or HTML error page)
                    errorData = { error: `HTTP error! Status: ${response.status}`, details: await response.text() };
                }
                // Create an error object with details from the response
                const error = new Error(errorData.error || `API request failed with status ${response.status}`);
                error.response = { status: response.status, data: errorData }; // Attach full response data
                throw error; // Throw the error to be caught by the calling function
            }
            // Handle successful responses
            if (response.status === 204) { // No Content (e.g., successful DELETE with no body)
                return null; 
            }
            return await response.json(); // Parse and return JSON response
        } catch (error) {
            // Log the error for debugging
            console.error(`API ${method} request to ${url} failed:`, error.response ? error.response.data : error.message, error);
            // Re-throw the error so it can be handled by the specific UI logic (e.g., show a message to the user)
            throw error; 
        }
    },

    // --- Product Management ---
    /**
     * Adds a new product.
     * @param {object} productData - Data for the new product.
     * @returns {Promise<object>} - The newly added product details.
     */
    addProduct: function(productData) {
        return this._request('POST', '/products', productData);
    },
    /**
     * Fetches all products for the admin panel.
     * @returns {Promise<Array<object>>} - A list of products.
     */
    getProducts: function() {
        return this._request('GET', '/products');
    },
    /**
     * Updates an existing product.
     * @param {string} productCode - The unique code of the product to update.
     * @param {object} productData - The updated product data.
     * @returns {Promise<object>} - The updated product details.
     */
    updateProduct: function(productCode, productData) {
        return this._request('PUT', `/products/${productCode}`, productData);
    },
    /**
     * Deletes a product.
     * @param {string} productCode - The unique code of the product to delete.
     * @returns {Promise<null|object>} - Null on success (204) or error object.
     */
    deleteProduct: function(productCode) {
        return this._request('DELETE', `/products/${productCode}`);
    },

    // --- Category Management ---
    /**
     * Adds a new category.
     * @param {object} categoryData - Data for the new category.
     * @returns {Promise<object>} - The newly added category details.
     */
    addCategory: function(categoryData) {
        return this._request('POST', '/categories', categoryData);
    },
    /**
     * Fetches all categories for the admin panel.
     * @returns {Promise<Array<object>>} - A list of categories.
     */
    getCategories: function() {
        return this._request('GET', '/categories');
    },
    /**
     * Updates an existing category.
     * @param {string} categoryCode - The unique code of the category to update.
     * @param {object} categoryData - The updated category data.
     * @returns {Promise<object>} - The updated category details.
     */
    updateCategory: function(categoryCode, categoryData) {
        return this._request('PUT', `/categories/${categoryCode}`, categoryData);
    },
    /**
     * Deletes a category.
     * @param {string} categoryCode - The unique code of the category to delete.
     * @returns {Promise<null|object>} - Null on success (204) or error object.
     */
    deleteCategory: function(categoryCode) {
        return this._request('DELETE', `/categories/${categoryCode}`);
    },

    // --- Inventory Management ---
    /**
     * Fetches the current inventory overview.
     * @returns {Promise<Array<object>>} - A list of inventory items.
     */
    getInventory: function() {
        return this._request('GET', '/inventory');
    },
    /**
     * Updates a specific inventory item (e.g., stock quantity, supplier).
     * @param {string} productCode - The product code for which to update inventory.
     * @param {object} inventoryData - Data to update (e.g., { quantity: 50 }).
     * @returns {Promise<object>} - The updated inventory item details.
     */
    updateInventoryItem: function(productCode, inventoryData) { 
        return this._request('PUT', `/inventory/${productCode}`, inventoryData);
    },
    
    // --- User Management (Example Stubs - Implement as needed) ---
    /**
     * Fetches all users.
     * @returns {Promise<Array<object>>} - A list of users.
     */
    getUsers: function() { return this._request('GET', '/users'); },
    // TODO: Add functions for updateUser, deleteUser, etc.

    // --- Order Management (Example Stubs - Implement as needed) ---
    /**
     * Fetches orders, optionally with filters.
     * @param {object} filters - Key-value pairs for filtering orders (e.g., { status: 'pending' }).
     * @returns {Promise<Array<object>>} - A list of orders.
     */
    getOrders: function(filters = {}) {
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/orders${queryParams ? '?' + queryParams : ''}`);
    },
    // TODO: Add functions for updateOrderStatus, getOrderDetails, etc.
};