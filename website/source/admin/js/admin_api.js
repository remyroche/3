// Maison Trüvra - Admin API Interaction Layer
// This file centralizes API calls for the admin panel.
// It now uses constants from admin_config.js

/**
 * A generic function to make API requests for the admin panel.
 * Handles adding the JWT token to headers and basic error handling.
 * @param {string} endpoint - The API endpoint (e.g., '/users', '/products/1').
 * This should be relative to ADMIN_API_BASE_URL or ADMIN_AUTH_BASE_URL.
 * @param {string} method - HTTP method (e.g., 'GET', 'POST', 'PUT', 'DELETE').
 * @param {object} [body=null] - The request body for POST/PUT requests.
 * @param {boolean} [isFormData=false] - Set to true if the body is FormData.
 * @returns {Promise<object>} - A promise that resolves with the JSON response.
 * @throws {Error} - Throws an error if the request fails or returns an error status.
 */
async function adminApiRequest(endpoint, method = 'GET', body = null, isFormData = false) {
    // Ensure admin_config.js is loaded first and these constants are available globally.
    if (typeof API_BASE_URL === 'undefined') {
        console.error("API_BASE_URL not defined. Ensure admin_config.js is loaded.");
        showAdminToast("Configuration error: API URLs missing.", "error"); // Uses showAdminToast from admin_ui.js
        throw new Error("API configuration error.");
    }

    const url = `${API_BASE_URL}${endpoint}`;
    console.log(`Admin API Request: ${method} ${url}`); // Log the full URL
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

        if (response.status === 401) { 
            console.warn('Admin API request unauthorized. Token might be expired or invalid.');
            showAdminToast('Session expirée ou invalide. Veuillez vous reconnecter.', 'error'); // From admin_ui.js
            if (typeof adminLogout === 'function') {
                adminLogout(); // Clears session storage and then redirects
            } else {
                window.location.href = 'admin_login.html'; // Fallback redirect
            }
            throw new Error('Unauthorized: Token expired or invalid.');
        }
        
        // Try to parse JSON, but handle cases where response might be empty (e.g., 204 No Content)
        let responseData;
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
            responseData = await response.json();
        } else if (response.status === 204) {
            responseData = { success: true, message: "Operation successful (No Content)" }; // Create a success object for 204
        }
         else {
            // Handle non-JSON responses if necessary, or assume error if not JSON and not 204
            if (!response.ok) {
                throw new Error(`Error ${response.status}: ${response.statusText} (Non-JSON response)`);
            }
            responseData = { success: true, message: "Operation successful (Non-JSON response)"}; // Or handle as text
        }


        if (!response.ok) {
            const errorMessage = responseData.message || `Error ${response.status}: ${response.statusText}`;
            console.error(`Admin API Error: ${method} ${url} - ${errorMessage}`, responseData);
            // Throw an error object that might contain more details if parsed from JSON
            const errorToThrow = new Error(errorMessage);
            if (responseData && responseData.errors) { // For structured validation errors
                errorToThrow.errors = responseData.errors;
            }
            throw errorToThrow;
        }
        
        return responseData; 
    } catch (error) {
        console.error(`Failed to make admin API request to ${url}:`, error);
        // showAdminToast is now preferred for UI feedback, called by the function that calls adminApiRequest
        // However, a general network error could be caught here.
        if (!error.errors) { // If it's not a structured error from the server already shown
             showAdminToast(error.message || 'Une erreur est survenue lors de la communication avec le serveur.', 'error');
        }
        throw error; 
    }
}

// --- Specific Admin API functions (simplified for brevity, assuming they call makeAdminApiRequest) ---
// These function definitions (getDashboardStats, getCategories, etc.) remain the same as in your original file,
// but they will now internally use the updated makeAdminApiRequest defined above.
// Example:
// const adminApi = {
//     getDashboardStats: () => makeAdminApiRequest('/dashboard/stats', 'GET'),
//     getCategories: () => makeAdminApiRequest('/categories', 'GET'),
//     // ... other specific API functions ...
// };

// Note: The placeholder showGlobalMessage at the end of the original admin_api.js
// should be removed as UI notifications are handled by showAdminToast in admin_ui.js
// and called by the functions that consume adminApiRequest.

// Inside admin_api.js (or called by admin_auth.js)
/**
 * Logs in an admin user.
 * @param {string} email - The admin's email.
 * @param {string} password - The admin's password.
 * @returns {Promise<object>} - A promise that resolves with the login response.
 *                              Expected structure on success: { success: true, message: '...', token: '...' }
 *                              Expected structure on failure: { success: false, message: '...' }
 */
async function loginAdmin(email, password) {
    try {
        // adminApiRequest will handle JSON stringification and Content-Type header.
        // It also handles the base URL.
        const result = await adminApiRequest('/api/admin/login', 'POST', { email, password });
        // adminApiRequest already returns the parsed JSON data or throws an error.
        // The structure of 'result' should match what the backend sends.
        return result; // This will include { success: boolean, message: string, token?: string }
    } catch (error) {
        // adminApiRequest already logs the error and can show a toast.
        // We return a standardized error object for the calling function (handleAdminLoginFormSubmit) to process.
        const errorMessage = error.message || 'An unexpected error occurred during login. Please try again.';
        console.error('Login failed via loginAdmin wrapper:', errorMessage);
        return { success: false, message: errorMessage };
    }
}
