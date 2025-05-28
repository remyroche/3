// Maison Trüvra - Admin API Interaction Layer
// This file centralizes API calls for the admin panel.

// Configuration for API endpoints
// Ensure these URLs match your backend Flask application's running host and port.
// Standardizing to port 5001 to match backend default and public site config.
const ADMIN_API_BASE_URL = 'http://127.0.0.1:5001/api/admin'; // Corrected port
const ADMIN_AUTH_BASE_URL = 'http://127.0.0.1:5001/auth';     // Corrected port

/**
 * A generic function to make API requests for the admin panel.
 * Handles adding the JWT token to headers and basic error handling.
 * @param {string} endpoint - The API endpoint (e.g., '/users', '/products/1').
 * @param {string} method - HTTP method (e.g., 'GET', 'POST', 'PUT', 'DELETE').
 * @param {object} [body=null] - The request body for POST/PUT requests.
 * @param {boolean} [isFormData=false] - Set to true if the body is FormData.
 * @returns {Promise<object>} - A promise that resolves with the JSON response.
 * @throws {Error} - Throws an error if the request fails or returns an error status.
 */
async function makeAdminApiRequest(endpoint, method = 'GET', body = null, isFormData = false) {
    const url = endpoint.startsWith('/auth/') ? `${ADMIN_AUTH_BASE_URL}${endpoint.substring(5)}` : `${ADMIN_API_BASE_URL}${endpoint}`;
    const token = getAdminAuthToken(); // Assumes getAdminAuthToken() is available from admin_auth.js

    const headers = {};
    if (!isFormData) {
        headers['Content-Type'] = 'application/json';
    }
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const config = {
        method: method,
        headers: headers,
    };

    if (body) {
        config.body = isFormData ? body : JSON.stringify(body);
    }

    try {
        const response = await fetch(url, config);

        if (response.status === 401) { // Unauthorized
            console.warn('Admin API request unauthorized. Token might be expired or invalid.');
            // Attempt to refresh token or redirect to login is handled by ensureAdminAuthenticated in admin_auth.js
            // For direct API calls that fail this way, ensureAdminAuthenticated should be called by the page logic.
            // Or, this function could trigger a logout/redirect.
            showGlobalMessage('Session expirée ou invalide. Veuillez vous reconnecter.', 'error');
            redirectToAdminLogin(); // From admin_auth.js
            throw new Error('Unauthorized: Token expired or invalid.');
        }
        
        const responseData = await response.json();

        if (!response.ok) {
            // Log more detailed error from backend if available
            const errorMessage = responseData.message || `Error ${response.status}: ${response.statusText}`;
            console.error(`Admin API Error: ${method} ${url} - ${errorMessage}`, responseData);
            throw new Error(errorMessage);
        }
        
        return responseData; // Contains 'message' and other data from backend
    } catch (error) {
        console.error(`Failed to make admin API request to ${url}:`, error);
        // Show a generic error message to the user, specific error is in console.
        // The calling function should ideally handle displaying specific messages.
        showGlobalMessage(error.message || 'Une erreur est survenue lors de la communication avec le serveur.', 'error');
        throw error; // Re-throw to allow specific error handling by the caller
    }
}

// --- Specific Admin API functions ---

const adminApi = {
    // Dashboard
    getDashboardStats: () => makeAdminApiRequest('/dashboard/stats', 'GET'),

    // Categories
    getCategories: () => makeAdminApiRequest('/categories', 'GET'),
    createCategory: (categoryData) => makeAdminApiRequest('/categories', 'POST', categoryData, true), // FormData
    updateCategory: (categoryId, categoryData) => makeAdminApiRequest(`/categories/${categoryId}`, 'PUT', categoryData, true), // FormData
    deleteCategory: (categoryId) => makeAdminApiRequest(`/categories/${categoryId}`, 'DELETE'),
    getCategoryDetails: (categoryId) => makeAdminApiRequest(`/categories/${categoryId}`, 'GET'),


    // Products
    getProducts: (params = {}) => { // params for filtering, sorting, pagination
        const queryParams = new URLSearchParams(params).toString();
        return makeAdminApiRequest(`/products${queryParams ? '?' + queryParams : ''}`, 'GET');
    },
    getProductDetails: (productId) => makeAdminApiRequest(`/products/${productId}`, 'GET'),
    createProduct: (productData) => makeAdminApiRequest('/products', 'POST', productData, true), // FormData
    updateProduct: (productId, productData) => makeAdminApiRequest(`/products/${productId}`, 'PUT', productData, true), // FormData
    deleteProduct: (productId) => makeAdminApiRequest(`/products/${productId}`, 'DELETE'),
    addProductImage: (productId, imageData) => makeAdminApiRequest(`/products/${productId}/images`, 'POST', imageData, true), // FormData
    deleteProductImage: (productId, imageId) => makeAdminApiRequest(`/products/${productId}/images/${imageId}`, 'DELETE'),


    // Users
    getUsers: (params = {}) => {
        const queryParams = new URLSearchParams(params).toString();
        return makeAdminApiRequest(`/users${queryParams ? '?' + queryParams : ''}`, 'GET');
    },
    getUserDetails: (userId) => makeAdminApiRequest(`/users/${userId}`, 'GET'), // Assuming this endpoint exists or will be created
    updateUser: (userId, userData) => makeAdminApiRequest(`/users/${userId}`, 'PUT', userData), // JSON body

    // Orders
    getOrders: (params = {}) => {
        const queryParams = new URLSearchParams(params).toString();
        return makeAdminApiRequest(`/orders${queryParams ? '?' + queryParams : ''}`, 'GET');
    },
    getOrderDetails: (orderId) => makeAdminApiRequest(`/orders/${orderId}`, 'GET'), // Assuming this endpoint exists
    updateOrderStatus: (orderId, statusData) => makeAdminApiRequest(`/orders/${orderId}/status`, 'PUT', statusData), // JSON body { status: "new_status" }

    // Reviews
    getReviews: (params = {}) => {
        const queryParams = new URLSearchParams(params).toString();
        return makeAdminApiRequest(`/reviews${queryParams ? '?' + queryParams : ''}`, 'GET');
    },
    approveReview: (reviewId) => makeAdminApiRequest(`/reviews/${reviewId}/approve`, 'PUT'),
    unapproveReview: (reviewId) => makeAdminApiRequest(`/reviews/${reviewId}/unapprove`, 'PUT'),
    deleteReview: (reviewId) => makeAdminApiRequest(`/reviews/${reviewId}`, 'DELETE'),

    // Inventory (Serialized Items)
    receiveSerializedStock: (stockData) => makeAdminApiRequest('/inventory/serialized/receive', 'POST', stockData), // JSON
    getSerializedItems: (params = {}) => {
        const queryParams = new URLSearchParams(params).toString();
        return makeAdminApiRequest(`/inventory/serialized/items${queryParams ? '?' + queryParams : ''}`, 'GET');
    },
    updateSerializedItemStatus: (itemUid, statusData) => makeAdminApiRequest(`/inventory/serialized/items/${itemUid}/status`, 'PUT', statusData), // JSON

    // Inventory (Aggregate Stock Adjustments)
    adjustAggregateStock: (adjustmentData) => makeAdminApiRequest('/inventory/stock/adjust', 'POST', adjustmentData), // JSON

    // B2B Professional Applications & Invoices (from professional_routes.py)
    getProfessionalApplications: (status = 'pending') => makeAdminApiRequest(`/professional/applications?status=${status}`, 'GET'),
    updateProfessionalApplicationStatus: (userId, statusData) => makeAdminApiRequest(`/professional/applications/${userId}/status`, 'PUT', statusData), // JSON { status: "new_status" }
    
    generateB2BInvoice: (invoiceData) => makeAdminApiRequest('/professional/invoices/generate', 'POST', invoiceData), // JSON
    getB2BInvoices: (params = {}) => { // e.g., { b2b_user_id: 1, status: 'issued' }
        const queryParams = new URLSearchParams(params).toString();
        return makeAdminApiRequest(`/professional/invoices${queryParams ? '?' + queryParams : ''}`, 'GET');
    },
    // updateB2BInvoiceStatus: (invoiceId, statusData) => makeAdminApiRequest(`/professional/invoices/${invoiceId}/status`, 'PUT', statusData), // Example

    // Settings
    getSettings: () => makeAdminApiRequest('/settings', 'GET'),
    updateSettings: (settingsData) => makeAdminApiRequest('/settings', 'POST', settingsData), // JSON

    // Asset serving is done via direct GET, not this request function.
    // Example: GET /api/admin/assets/categories/image.jpg
};

// Ensure admin_auth.js provides getAdminAuthToken, redirectToAdminLogin, and showGlobalMessage
// or these need to be implemented/imported here.
// Assuming showGlobalMessage is available globally or imported.
function showGlobalMessage(message, type = 'info') {
    // This is a placeholder. Actual implementation might be in admin_main.js or a UI utility.
    console.log(`Global Message (${type}): ${message}`);
    const messageDiv = document.getElementById('global-message');
    const messageText = document.getElementById('global-message-text');
    const messageCloseButton = document.getElementById('global-message-close');

    if (messageDiv && messageText && messageCloseButton) {
        messageText.textContent = message;
        messageDiv.classList.remove('hidden', 'bg-green-500', 'bg-red-500', 'bg-blue-500');
        if (type === 'success') {
            messageDiv.classList.add('bg-green-500');
        } else if (type === 'error') {
            messageDiv.classList.add('bg-red-500');
        } else {
            messageDiv.classList.add('bg-blue-500'); // Default info
        }
        messageDiv.classList.remove('hidden');
        
        // Auto-hide after some time
        setTimeout(() => {
            messageDiv.classList.add('hidden');
        }, 5000);

        messageCloseButton.onclick = () => {
            messageDiv.classList.add('hidden');
        };
    }
}
