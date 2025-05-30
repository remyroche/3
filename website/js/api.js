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
 */
async function makeApiRequest(endpoint, method = 'GET', body = null, requiresAuth = false) {
    const headers = { 'Content-Type': 'application/json' };
    if (requiresAuth) {
        const token = getAuthToken(); // Assumes getAuthToken is available (from auth.js)
        if (!token) {
            // Assumes showGlobalMessage is available (from ui.js)
            showGlobalMessage("Vous n'êtes pas authentifié.", "error");
            throw new Error("Authentification requise.");
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
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config); // Assumes API_BASE_URL is available (from config.js)
        if (!response.ok) {
            const errorResult = await response.json().catch(() => ({ message: "Erreur de communication avec le serveur." }));
            throw new Error(errorResult.message || `Erreur HTTP: ${response.status}`);
        }
        if (response.status === 204) { // No Content
            return { success: true, message: "Opération réussie (pas de contenu)." };
        }
        return await response.json();
    } catch (error) {
        console.error(`Erreur API pour ${method} ${API_BASE_URL}${endpoint}:`, error);
        // Assumes showGlobalMessage is available (from ui.js)
        showGlobalMessage(error.message || "Une erreur réseau est survenue.", "error");
        throw error;
    }
}
