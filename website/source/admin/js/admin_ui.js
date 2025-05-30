// website/admin/js/admin_ui.js
// UI helper functions for the Admin Panel.

/**
 * Displays a toast message in the admin panel.
 * @param {string} message - The message to display.
 * @param {string} [type='info'] - The type of message ('success', 'error', 'info', 'warning').
 * @param {number} [duration=4000] - The duration to display the message in milliseconds.
 */
function showAdminToast(message, type = 'info', duration = 4000) {
    const toastContainer = document.getElementById('admin-toast-container'); // Ensure this exists in admin HTML base/template
    
    if (!toastContainer) {
        console.warn("Admin toast container not found. Fallback to alert.");
        alert(`${type.toUpperCase()}: ${message}`);
        return;
    }

    const toast = document.createElement('div');
    toast.className = `admin-toast toast-${type}`; // Base class + type-specific class
    toast.textContent = message;

    // Styling for the toast (can be moved to admin_style.css)
    // Basic inline styles for demonstration if not in CSS:
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.right = '20px';
    toast.style.padding = '15px';
    toast.style.borderRadius = '5px';
    toast.style.color = 'white';
    toast.style.zIndex = '1050'; // Ensure it's above other elements
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(20px)';
    toast.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
    
    // Type-specific background colors
    switch (type) {
        case 'success':
            toast.style.backgroundColor = '#4CAF50'; // Green
            break;
        case 'error':
            toast.style.backgroundColor = '#f44336'; // Red
            break;
        case 'warning':
            toast.style.backgroundColor = '#ff9800'; // Orange
            break;
        case 'info':
        default:
            toast.style.backgroundColor = '#2196F3'; // Blue
            break;
    }

    toastContainer.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
    });

    // Auto-hide
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        toast.addEventListener('transitionend', () => {
            if (toast.parentNode) { // Check if still in DOM before removing
                toast.parentNode.removeChild(toast);
            }
        }, { once: true });
    }, duration);
}

/**
 * Sets an error message for a form field and applies error styling.
 * @param {HTMLElement} field - The form field element.
 * @param {string} message - The error message to display.
 */
function setFieldError(field, message) {
    if (!field) return;
    // Add a more specific error class for styling via CSS
    field.classList.add('input-error', 'border-red-500'); 
    
    // Remove existing error message for this field to prevent duplicates
    let existingErrorElement = field.parentElement.querySelector(`.error-message[data-field-for="${field.id || field.name}"]`);
    if (existingErrorElement) existingErrorElement.remove();

    let errorElement = document.createElement('p');
    errorElement.classList.add('error-message', 'text-xs', 'text-red-600', 'mt-1');
    errorElement.dataset.fieldFor = field.id || field.name; // Link message to field
    errorElement.textContent = message;
    
    // Insert after the field, or at the end of parent if structure is complex
    if (field.nextSibling) {
        field.parentElement.insertBefore(errorElement, field.nextSibling);
    } else {
        field.parentElement.appendChild(errorElement);
    }
}

/**
 * Clears all error messages and styling from a form.
 * @param {HTMLFormElement} form - The form element.
 */
function clearFormErrors(form) {
    if (!form) return;
    form.querySelectorAll('.input-error, .border-red-500').forEach(el => {
        el.classList.remove('input-error', 'border-red-500');
    });
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
        modal.classList.remove('hidden'); // Assuming 'hidden' class controls visibility
        modal.classList.add('active'); // Or use 'active' if that's your primary visibility class
        // Add class to body to prevent scrolling if modal is full-screen overlay
        document.body.classList.add('modal-open');
    }
}

/**
 * Closes a modal dialog in the admin panel.
 * @param {string} modalId - The ID of the modal element to close.
 */
function closeAdminModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('active');
        document.body.classList.remove('modal-open');
    }
}

/**
 * Gets the appropriate CSS class for an order status.
 * @param {string} status - The order status.
 * @returns {string} - The CSS class string (Tailwind classes).
 */
function getOrderStatusClass(status) {
    // Ensure these classes are defined in your admin_style.css or Tailwind config
    switch (status ? status.toLowerCase() : '') {
        case 'paid':
        case 'delivered':
            return 'bg-green-100 text-green-700 border-green-300';
        case 'shipped':
        case 'processing':
            return 'bg-blue-100 text-blue-700 border-blue-300';
        case 'pending_payment':
        case 'pending': // General pending for B2B apps
            return 'bg-yellow-100 text-yellow-700 border-yellow-300';
        case 'cancelled':
        case 'rejected': // For B2B apps
        case 'refunded':
            return 'bg-red-100 text-red-700 border-red-300';
        case 'approved': // For B2B apps
             return 'bg-teal-100 text-teal-700 border-teal-300';
        default:
            return 'bg-gray-100 text-gray-700 border-gray-300';
    }
}

// Ensure the admin toast container exists in your main admin HTML layout
// Example: <div id="admin-toast-container" class="fixed bottom-0 right-0 p-4 space-y-2 z-[1000]"></div>
// The toasts will be appended to this container.