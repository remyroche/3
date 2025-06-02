// website/js/api.js
// Handles API communication for the frontend application

/**
 * Makes an API request to the backend.
 * @param {string} endpoint - The API endpoint (e.g., '/products', '/auth/login').
 * @param {string} [method='GET'] - The HTTP method.
 * @param {object|null} [body=null] - The request body for POST/PUT requests.
 * @param {boolean} [requiresAuth=false] - Whether the request requires an authentication token.
 * @returns {Promise<object>} - A promise that resolves with the JSON response from the API.
 * @throws {Error} - Throws an error if the API request fails or authentication is required but missing.
 */
async function makeApiRequest(endpoint, method = 'GET', body = null, requiresAuth = false) {
    // Ensure API_BASE_URL is available (should be from js/config.js)
    if (typeof API_BASE_URL === 'undefined') {
        console.error("API_BASE_URL is not defined. Ensure config.js is loaded before api.js.");
        throw new Error("API configuration error.");
    }

    const headers = { 'Content-Type': 'application/json' };
    if (requiresAuth) {
        const token = typeof getAuthToken === 'function' ? getAuthToken() : sessionStorage.getItem('authToken'); 
        if (!token) {
            // Do not throw error here directly, let backend handle unauthorized if endpoint is protected.
            // showGlobalMessage might be called by the caller if a 401 is received.
            console.warn(`API request to ${endpoint} requires auth, but no token found.`);
        } else {
            headers['Authorization'] = `Bearer ${token}`;
        }
    }

    const config = {
        method: method,
        headers: headers,
    };

    if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
        config.body = JSON.stringify(body);
    }

    const fullUrl = `${API_BASE_URL}${endpoint}`; // Prepend API_BASE_URL
    console.log(`Making API request: ${method} ${fullUrl}`); // For debugging

    try {
        const response = await fetch(fullUrl, config); 
        
        if (!response.ok) {
            let errorResult = { message: `API Error: ${response.status} ${response.statusText}` };
            try {
                errorResult = await response.json(); // Try to get structured error from backend
            } catch (e) {
                // If backend error is not JSON, use the status text
                console.warn("API error response was not JSON.", e);
                try {
                    errorResult.details = await response.text();
                } catch (textErr) { /* ignore */ }
            }
            // Construct a new error object to include status and backend message
            const error = new Error(errorResult.message || `HTTP error! Status: ${response.status}`);
            error.status = response.status;
            error.data = errorResult; // Attach full error data from backend
            throw error;
        }

        if (response.status === 204) { // No Content
            return { success: true, message: "Operation successful (no content)." }; // Provide a success object
        }
        return await response.json(); // For 200, 201 etc.
    } catch (error) {
        console.error(`API Error for ${method} ${fullUrl}:`, error.data || error.message, error);
        // Do not showGlobalMessage here, let the caller handle UI feedback.
        // This allows more specific error messages based on context.
        throw error; // Re-throw the error to be handled by the calling function
    }
}
