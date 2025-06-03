// website/js/api.js
// Handles API communication for the frontend application

async function makeApiRequest(endpoint, method = 'GET', body = null, requiresAuth = false, timeout = 15000) { // Added timeout parameter
    if (typeof API_BASE_URL === 'undefined') {
        console.error("API_BASE_URL is not defined. Ensure config.js is loaded before api.js.");
        throw new Error("API configuration error.");
    }

    const controller = new AbortController(); // For timeout
    const signal = controller.signal;
    let timeoutId;

    const headers = { 'Content-Type': 'application/json' };
    if (requiresAuth) {
        const token = typeof getAuthToken === 'function' ? getAuthToken() : sessionStorage.getItem('authToken'); 
        if (!token) {
            console.warn(`API request to ${endpoint} requires auth, but no token found.`);
            // Note: The backend should ultimately deny access if auth is required and token is missing/invalid.
        } else {
            headers['Authorization'] = `Bearer ${token}`;
        }
    }

    const config = {
        method: method,
        headers: headers,
        signal: signal // Add signal to fetch config
    };

    if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
        config.body = JSON.stringify(body);
    }

    const fullUrl = `${API_BASE_URL}${endpoint}`;
    console.log(`Making API request: ${method} ${fullUrl}`); 

    timeoutId = setTimeout(() => {
        controller.abort();
        console.error(`API request to ${fullUrl} timed out after ${timeout}ms.`);
    }, timeout);

    try {
        const response = await fetch(fullUrl, config); 
        clearTimeout(timeoutId); // Clear timeout if fetch completes
        
        if (!response.ok) {
            let errorResult = { message: `API Error: ${response.status} ${response.statusText}` };
            try {
                errorResult = await response.json(); 
            } catch (e) {
                console.warn("API error response was not JSON.", e);
                try {
                    errorResult.details = await response.text();
                } catch (textErr) { /* ignore */ }
            }
            const error = new Error(errorResult.message || `HTTP error! Status: ${response.status}`);
            error.status = response.status;
            error.data = errorResult; 
            throw error;
        }

        if (response.status === 204) { 
            return { success: true, message: "Operation successful (no content)." };
        }
        return await response.json(); 
    } catch (error) {
        clearTimeout(timeoutId); // Clear timeout on error as well
        if (error.name === 'AbortError') {
            // This specific error is thrown by controller.abort() on timeout
            const timeoutError = new Error(`Request to ${fullUrl} timed out.`);
            timeoutError.status = 408; // Request Timeout
            timeoutError.data = { message: `Request timed out after ${timeout/1000} seconds.`};
            console.error(`API Error for ${method} ${fullUrl}:`, timeoutError.data.message, error);
            throw timeoutError;
        }
        console.error(`API Error for ${method} ${fullUrl}:`, error.data || error.message, error);
        throw error; 
    }
}
