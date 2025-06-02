// website/js/api.js
// Handles API communication for the frontend application

/**
 * Makes an API request to the backend.
 * @param {string} endpoint - The API endpoint (e.g., '/products').
 * @param {string} [method='GET'] - The HTTP method.
 * @param {object|null} [body=null] - The request body for POST/PUT requests.
 * @param {boolean} [requiresAuth=false] - Whether the request requires an authentication token.
 * @returns {Promise<object>} - A promise that resolves with the JSON response from the API.
 * @throws {Error} - Throws an error if the API request fails or authentication is required but missing.
 */// website/js/api.js
// Handles API communication for the frontend application

async function makeApiRequest(endpoint, method = 'GET', body = null, requiresAuth = false) {
    const headers = { 'Content-Type': 'application/json' };
    if (requiresAuth) {
        const token = getAuthToken(); 
        if (!token) {
            showGlobalMessage(t('public.js.logged_out'), "error"); // "You are not authenticated."
            throw new Error("Authentification requise."); // Keep French for internal error unless t() is used here too
        }
        headers['Authorization'] = `Bearer ${token}`;
    }

    const config = {
        method: method,
        headers: headers,
    };

    if (body) {
        config.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config); 
        if (!response.ok) {
            const errorResult = await response.json().catch(() => ({ message: t('global.error_generic') }));
            throw new Error(errorResult.message || `Erreur HTTP: ${response.status}`);
        }
        if (response.status === 204) { 
            return { success: true, message: "Opération réussie (pas de contenu)." };
        }
        return await response.json();
    } catch (error) {
        console.error(`API Error for ${method} ${API_BASE_URL}${endpoint}:`, error);
        showGlobalMessage(error.message || t('global.error_generic'), "error");
        throw error;
    }
}
