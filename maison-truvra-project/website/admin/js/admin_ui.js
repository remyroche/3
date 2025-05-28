// website/admin/js/admin_ui.js
// UI helper functions for the Admin Panel.

/**
 * Displays a toast message in the admin panel.
 * @param {string} message - The message to display.
 * @param {string} [type='info'] - The type of message ('success', 'error', 'info').
 * @param {number} [duration=4000] - The duration to display the message in milliseconds.
 */
function showAdminToast(message, type = 'info', duration = 4000) {
    const toastContainer = document.getElementById('admin-toast-container'); // Ensure this exists in admin HTML
    const toast = document.getElementById('admin-message-toast');
    const textElement = document.getElementById('admin-message-text');

    if (!toastContainer || !toast || !textElement) {
        console.warn("Admin toast elements not found in HTML. Fallback to alert.");
        alert(message); // Basic fallback
        return;
    }
    textElement.textContent = message;
    toast.className = ''; // Reset classes
    toast.classList.add(type); // Add type class for styling (e.g., 'success', 'error')
    
    toast.style.display = 'block'; // Make it visible

    // Clear any existing timeout to prevent multiple toasts stacking or premature hiding
    if (toast.currentTimeout) clearTimeout(toast.currentTimeout);

    toast.currentTimeout = setTimeout(() => {
        toast.style.display = 'none';
    }, duration);
}

/**
 * Sets an error message for a form field and applies error styling.
 * @param {HTMLElement} field - The form field element.
 * @param {string} message - The error message to display.
 */
function setFieldError(field, message) {
    if (!field) return;
    field.classList.add('border-red-500'); // Example error class
    let errorElement = field.nextElementSibling;
    // Check if the next sibling is already an error message for this field
    if (!errorElement || !errorElement.classList.contains('error-message')) {
        errorElement = document.createElement('p');
        errorElement.classList.add('error-message', 'text-xs', 'text-red-600', 'mt-1');
        // Insert after the field
        field.parentNode.insertBefore(errorElement, field.nextSibling);
    }
    errorElement.textContent = message;
}

/**
 * Clears all error messages and styling from a form.
 * @param {HTMLFormElement} form - The form element.
 */
function clearFormErrors(form) {
    if (!form) return;
    form.querySelectorAll('.border-red-500').forEach(el => el.classList.remove('border-red-500'));
    form.querySelectorAll('.error-message').forEach(el => el.remove());
}

/**
 * Validates if a string is a valid URL.
 * @param {string} string - The string to validate.
 * @returns {boolean} True if valid URL, false otherwise.
 */
function isValidUrl(string) {
    try {
        new URL(string);
        return true;
    } catch (_) {
        return false;
    }
}

/**
 * Opens a modal dialog in the admin panel.
 * @param {string} modalId - The ID of the modal element to open.
 */
function openAdminModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active'); // Ensure 'active' class makes it visible
    }
}

/**
 * Closes a modal dialog in the admin panel.
 * @param {string} modalId - The ID of the modal element to close.
 */
function closeAdminModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

/**
 * Gets the appropriate CSS class for an order status (can be shared with main site ui.js if identical).
 * @param {string} status - The order status.
 * @returns {string} - The CSS class string.
 */
function getOrderStatusClass(status) {
    switch (status) {
        case 'Paid': return 'bg-green-100 text-green-800';
        case 'Shipped': return 'bg-blue-100 text-blue-800';
        case 'Delivered': return 'bg-purple-100 text-purple-800';
        case 'Pending': return 'bg-yellow-100 text-yellow-800';
        case 'Cancelled': return 'bg-red-100 text-red-800';
        default: return 'bg-gray-100 text-gray-800';
    }
}
