// website/admin/js/admin_config.js

// Define the base URL for your backend Admin API.
// This MUST point to your Flask backend's admin-specific API blueprint.
// For development, if Flask runs on port 5001 and the admin API is under /api/admin:
const API_BASE_URL = 'http://localhost:5001/api/admin';

// If your Flask app serves the frontend and backend from the same domain in production,
// you might use a relative path like '/api/admin'.

// This API_BASE_URL will be used by admin_api.js to construct full request URLs.
