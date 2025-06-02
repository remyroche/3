// website/source/admin/js/admin_api.js
// This script handles all API communication for the admin panel.

// Assuming API_BASE_URL is defined globally by admin_config.js
// For example: const API_BASE_URL = 'http://localhost:5001/api/admin';

const adminApi = {
    // BASE_URL should be set from admin_config.js
    // If admin_config.js defines API_BASE_URL = 'http://localhost:5001/api/admin', then:
    BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '/api/admin', // Fallback if not defined

    /**
     * Generic request handler for admin API calls.
     * @param {string} method - HTTP method (GET, POST, PUT, DELETE).
     * @param {string} endpoint - API endpoint (e.g., '/products', or an empty string if BASE_URL includes full path).
     * @param {object|null} data - Data to send in the request body (for POST/PUT).
     * @param {boolean} isFormData - Set to true if data is FormData.
     * @returns {Promise<object|null>} - The JSON response from the API or null for 204.
     * @throws {Error} - Throws an error if the request fails or network issue.
     */
    async _request(method, endpoint, data = null, isFormData = false) {
        // If endpoint starts with http, assume it's a full URL (e.g. for login if it's on a different base)
        // Otherwise, prepend BASE_URL.
        const url = endpoint.startsWith('http') ? endpoint : `${this.BASE_URL}${endpoint}`;
        
        const headers = {};
        if (!isFormData) {
            headers['Content-Type'] = 'application/json';
        }
        // Retrieve the admin authentication token
        const storedToken = typeof getAdminAuthToken === 'function' ? getAdminAuthToken() : sessionStorage.getItem('adminAuthToken');
        if (storedToken) {
            headers['Authorization'] = `Bearer ${storedToken}`;
        } else {
            // For login endpoint, token won't exist yet. For others, Flask @admin_required handles it.
            if (!url.endsWith('/login')) { // Avoid warning for the login attempt itself
                 console.warn(`Admin API request to ${url} without token.`);
            }
        }

        const config = {
            method: method,
            headers: headers,
        };

        if (data) {
            if (isFormData) {
                config.body = data; // FormData is sent as is
            } else if (method === 'POST' || method === 'PUT' || method === 'PATCH') {
                config.body = JSON.stringify(data);
            }
        }
        
        // Optional: Add loading indicator logic here or in calling functions
        // if (typeof showAdminLoading === 'function') showAdminLoading(true);

        try {
            const response = await fetch(url, config);
            if (!response.ok) {
                let errorData = { message: `API Error: ${response.status} ${response.statusText}` };
                try {
                    const errorJson = await response.json();
                    errorData = { ...errorData, ...errorJson }; 
                } catch (e) {
                    console.warn("API error response was not JSON.", e);
                    // Attempt to get text if not JSON, useful for HTML error pages from proxies etc.
                    try {
                        errorData.details = await response.text();
                    } catch (textErr) {
                        // Ignore if text cannot be read
                    }
                }
                const error = new Error(errorData.message || `API request failed with status ${response.status}`);
                error.status = response.status;
                error.data = errorData; 
                throw error; 
            }
            if (response.status === 204) { 
                return null; 
            }
            return await response.json(); 
        } catch (error) {
            console.error(`Admin API ${method} request to ${url} failed:`, error.data || error.message, error);
            if (typeof showAdminToast === 'function') {
                showAdminToast(error.data?.message || error.message || 'An unexpected API error occurred.', 'error');
            }
            throw error; 
        } finally {
            // if (typeof showAdminLoading === 'function') showAdminLoading(false);
        }
    },

    /**
     * Admin Login.
     * @param {string} email - Admin's email.
     * @param {string} password - Admin's password.
     * @returns {Promise<object>} - Login response including token and user info.
     */
    loginAdmin: function(email, password) {
        // The login endpoint is /api/admin/login, so endpoint is just '/login' relative to BASE_URL
        return this._request('POST', '/login', { email, password });
    },

    // --- Product Management ---
    addProduct: function(productData) { // productData is expected to be FormData
        return this._request('POST', '/products', productData, true); // Pass true for isFormData
    },
    getProducts: function() {
        return this._request('GET', '/products');
    },
    getProductDetail: function(productId) { // Added for fetching single product detail
        return this._request('GET', `/products/${productId}`);
    },
    updateProduct: function(productId, productData) { // productData is expected to be FormData
        return this._request('PUT', `/products/${productId}`, productData, true); // Pass true for isFormData
    },
    deleteProduct: function(productId) { // Changed from productCode to productId for consistency
        return this._request('DELETE', `/products/${productId}`);
    },

    // --- Category Management ---
    addCategory: function(categoryData) { // categoryData is FormData
        return this._request('POST', '/categories', categoryData, true);
    },
    getCategories: function() {
        return this._request('GET', '/categories');
    },
    getCategoryDetail: function(categoryId) {
        return this._request('GET', `/categories/${categoryId}`);
    },
    updateCategory: function(categoryId, categoryData) { // categoryData is FormData
        return this._request('PUT', `/categories/${categoryId}`, categoryData, true);
    },
    deleteCategory: function(categoryId) { // Changed from categoryCode to categoryId
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
    // deleteUser: function(userId) { ... }

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

    // --- Dashboard Stats ---
    getDashboardStats: function() {
        return this._request('GET', '/dashboard/stats');
    },

    // --- Inventory (Serialized Items & Aggregated Stock) ---
    // Detailed Serialized Items (for admin_view_inventory.html)
    getDetailedInventoryItems: function(filters = {}) { // Matches Flask route
        const queryParams = new URLSearchParams(filters).toString();
        return this._request('GET', `/inventory/items/detailed${queryParams ? '?' + queryParams : ''}`);
    },
    // Receive Serialized Stock (for admin_manage_inventory.html)
    receiveSerializedStock: function(stockData) {
        return this._request('POST', '/inventory/serialized/receive', stockData);
    },
    // Update Serialized Item Status (for admin_manage_inventory.html)
    updateSerializedItemStatus: function(itemUid, statusData) {
        return this._request('PUT', `/inventory/serialized/items/${itemUid}/status`, statusData);
    },
    // Export Serialized Items CSV
    exportSerializedItemsCsv: function() { // This will trigger a download, not a JSON response
        const url = `${this.BASE_URL}/inventory/export/serialized_items`;
        const storedToken = typeof getAdminAuthToken === 'function' ? getAdminAuthToken() : sessionStorage.getItem('adminAuthToken');
        // For file downloads, it's often easier to construct a URL and navigate or use an anchor tag.
        // If headers are needed (like Auth), then fetch is required, but handling blob downloads is more complex.
        // Assuming the backend will allow GET with token in query param for simplicity if direct fetch is hard,
        // OR the browser session for the admin panel is sufficient if cookies are used for JWT.
        // For now, let's try a direct window.location approach if token is not strictly in header for GET downloads.
        // This might need adjustment based on how Flask handles auth for file downloads.
        if (storedToken) {
            // If your server supports token in query for GET downloads (less secure but sometimes practical)
            // window.location.href = `${url}?token=${storedToken}`;
            // Or use fetch to handle the blob (more secure, more complex client-side)
            return fetch(url, { headers: { 'Authorization': `Bearer ${storedToken}` } })
                .then(response => {
                    if (!response.ok) throw new Error(`CSV Export failed: ${response.statusText}`);
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
        } else {
            // No token, direct navigation (might fail if endpoint is protected)
            window.location.href = url;
            return Promise.resolve({ success: true, message: "CSV export initiated (no token)." });
        }
    },
    // Import Serialized Items CSV
    importSerializedItemsCsv: function(formData) { // formData should be a FormData object
        return this._request('POST', '/inventory/import/serialized_items', formData, true); // isFormData = true
    },
    // Adjust Aggregated Stock (for non-serialized items or overall adjustments)
    adjustAggregatedStock: function(adjustmentData) {
        return this._request('POST', '/inventory/stock/adjust', adjustmentData);
    },
    // Get Product Inventory Details (including variants and movements)
    getAdminProductInventoryDetails: function(productCode, variantSkuSuffix = null) {
        let endpoint = `/inventory/product/${productCode}`;
        if (variantSkuSuffix) {
            endpoint += `?variant_sku_suffix=${encodeURIComponent(variantSkuSuffix)}`;
        }
        return this._request('GET', endpoint);
    },
    // Regenerate Static JSON files
    regenerateStaticJson: function() {
        return this._request('POST', '/regenerate-static-json');
    }
};
```
**Key changes in `admin_api.js`:**
* Added `loginAdmin` method. It POSTs to `/login` (relative to `this.BASE_URL`, which should be `/api/admin`).
* The `_request` method was slightly adjusted to handle cases where `endpoint` might be a full URL (though for admin login, it'll be relative to `API_BASE_URL`).
* Added `isFormData` parameter to `_request` and used it for `addProduct`, `updateProduct`, `addCategory`, `updateCategory`, and `importSerializedItemsCsv` as these might involve file uploads or complex form data.
* Corrected `deleteProduct` and `deleteCategory` to use `productId` and `categoryId` respectively, if that's the intended identifier from the admin panel UI. The current `admin_products.js` uses `productCode` for deletion, so I've kept that for now, but it's something to ensure consistency on. *Self-correction: The Flask routes for delete use `product_id` and `category_id` (integers). The JS `admin_products.js` uses `product.product_code` for deletion, and `admin_categories.js` uses `category.category_code`. This needs to be reconciled. For now, I'll assume the JS will be updated to pass IDs, or the Flask routes will be updated to accept codes. I will stick to the current JS implementation which uses codes for deletion for now, and the Flask routes accept codes.*
    * *Further self-correction:* The Flask routes for product and category deletion in `admin_api/routes.py` are defined with `<int:product_id>` and `<int:category_id>`. This means they expect integer IDs. The `admin_products.js` and `admin_categories.js` need to be updated to call `adminApi.deleteProduct(product.id)` and `adminApi.deleteCategory(category.id)`. I will modify the `adminApi` methods to reflect this expectation of IDs.
        * `deleteProduct: function(productId)`
        * `deleteCategory: function(categoryId)`
* Adjusted `exportSerializedItemsCsv` to use `fetch` with Authorization header for better security and to handle blob response for download.

Now, for `website/source/admin/js/admin_auth.js`:

```javascript
// website/admin/js/admin_auth.js
// Handles admin authentication, session management.

const ADMIN_TOKEN_KEY = 'adminAuthToken';
const ADMIN_USER_KEY = 'adminUser';

/**
 * Retrieves the admin authentication token from session storage.
 * @returns {string|null} The admin auth token or null if not found.
 */
function getAdminAuthToken() {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}

/**
 * Sets the admin authentication token in session storage.
 * @param {string} token - The admin auth token.
 */
function setAdminAuthToken(token) {
    if (token) {
        sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
    } else {
        sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    }
}

/**
 * Retrieves the admin user data from session storage.
 * @returns {object|null} The admin user object or null if not found/invalid.
 */
function getAdminUser() {
    const userString = sessionStorage.getItem(ADMIN_USER_KEY);
    if (userString) {
        try {
            return JSON.parse(userString);
        } catch (e) {
            console.error("Error parsing admin user data from session storage:", e);
            sessionStorage.removeItem(ADMIN_USER_KEY);
            sessionStorage.removeItem(ADMIN_TOKEN_KEY); // Clear token if user data is corrupt
            return null;
        }
    }
    return null;
}

/**
 * Sets the admin user data and token in session storage.
 * @param {object|null} userData - The admin user object.
 * @param {string|null} token - The admin auth token.
 */
function setAdminUserSession(userData, token) {
    if (userData && token) {
        sessionStorage.setItem(ADMIN_USER_KEY, JSON.stringify(userData));
        setAdminAuthToken(token);
    } else {
        sessionStorage.removeItem(ADMIN_USER_KEY);
        sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    }
    // Optionally, dispatch an event or call a UI update function here
    // updateAdminHeaderDisplay(); // Example
}


/**
 * Checks if an admin is logged in. Redirects to login page if not.
 * Updates the admin user greeting if logged in.
 * @returns {boolean} True if admin is logged in, false otherwise.
 */
function checkAdminLogin() {
    const token = getAdminAuthToken();
    const adminUser = getAdminUser();

    const onLoginPage = window.location.pathname.includes('admin_login.html');

    if (token && adminUser && adminUser.is_admin) {
        if (onLoginPage) {
            // Already logged in and on login page, redirect to dashboard
            window.location.href = 'admin_dashboard.html';
            return false; // Prevent login page from fully rendering
        }
        // Update greeting if element exists (moved to setupAdminUIGlobals in admin_main.js)
        return true; // Logged in and not on login page
    } else {
        if (!onLoginPage) {
            // Not logged in and not on login page, redirect to login
            window.location.href = 'admin_login.html';
            return false;
        }
        return true; // Allow login page to load if not logged in
    }
}

/**
 * Logs out the current admin user.
 * Clears admin data and token from session storage, shows a toast, and redirects to login.
 */
function adminLogout() {
    const adminUser = getAdminUser(); // Get user before clearing session for logging
    const adminEmailForLog = adminUser ? adminUser.email : 'Unknown';

    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    sessionStorage.removeItem(ADMIN_USER_KEY);
    
    if (typeof showAdminToast === 'function') {
        showAdminToast("You have been logged out.", "info");
    } else {
        alert("You have been logged out."); // Fallback
    }
    console.log(`Admin ${adminEmailForLog} logged out.`);
    window.location.href = 'admin_login.html';
}

/**
 * Handles the admin login form submission.
 * @param {Event} event - The form submission event.
 */
async function handleAdminLoginFormSubmit(event) {
    event.preventDefault();
    const emailInput = document.getElementById('admin-email');
    const passwordInput = document.getElementById('admin-password');
    const errorDisplayElement = document.getElementById('login-error-message');
    const loginButton = event.target.querySelector('button[type="submit"]');

    if (errorDisplayElement) {
        errorDisplayElement.textContent = '';
        errorDisplayElement.classList.add('hidden');
    }
    if(loginButton) loginButton.disabled = true;


    const email = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email || !password) {
        const msg = 'Please fill in all fields.';
        if (errorDisplayElement) {
            errorDisplayElement.textContent = msg;
            errorDisplayElement.classList.remove('hidden');
        }
        if (typeof showAdminToast === 'function') showAdminToast(msg, 'error');
        else alert(msg);
        if(loginButton) loginButton.disabled = false;
        return;
    }

    try {
        // adminApi.loginAdmin is defined in admin_api.js
        const result = await adminApi.loginAdmin(email, password);

        if (result.success && result.token && result.user) {
            setAdminUserSession(result.user, result.token); // Store user and token
            
            if (typeof showAdminToast === 'function') {
                showAdminToast('Login successful. Redirecting...', 'success');
            }
            console.log('Admin login successful for:', result.user.email);
            window.location.href = 'admin_dashboard.html';
        } else {
            // Error message should come from result.message (from Flask)
            const errorMessage = result.message || 'Invalid email or password.';
            if (errorDisplayElement) {
                errorDisplayElement.textContent = errorMessage;
                errorDisplayElement.classList.remove('hidden');
            }
            if (typeof showAdminToast === 'function') {
                showAdminToast(errorMessage, 'error');
            } else {
                alert(errorMessage);
            }
            if(loginButton) loginButton.disabled = false;
        }
    } catch (error) {
        console.error('Admin login error:', error);
        const errorMessage = error.data?.message || error.message || 'Login failed due to a server error.';
        if (errorDisplayElement) {
            errorDisplayElement.textContent = errorMessage;
            errorDisplayElement.classList.remove('hidden');
        }
        if (typeof showAdminToast === 'function') {
            showAdminToast(errorMessage, 'error');
        } else {
            alert(errorMessage);
        }
        if(loginButton) loginButton.disabled = false;
    }
}

// Make functions globally accessible if not using modules, or export if using modules.
// For this project structure, they are likely used as globals after script inclusion.
```
**Key changes in `admin_auth.js`:**
* Added `ADMIN_TOKEN_KEY` and `ADMIN_USER_KEY` constants.
* `setAdminAuthToken` and `getAdminUser` are refined.
* `setAdminUserSession` is a new helper to store both user data and token.
* `checkAdminLogin` is updated to redirect to dashboard if already logged in on login page.
* `handleAdminLoginFormSubmit` is the new function to manage admin login:
    * It calls `adminApi.loginAdmin`.
    * Uses `setAdminUserSession` to store token and user data.
    * Redirects to `admin_dashboard.html` on success.
    * Displays errors using `showAdminToast` or the `login-error-message` div.
* `adminLogout` logs out the user and clears session storage.
