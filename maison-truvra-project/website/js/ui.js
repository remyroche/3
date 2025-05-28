// website/js/ui.js
// UI helper functions for the frontend application

/**
 * Initializes the mobile menu toggle functionality.
 */
function initializeMobileMenu() {
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenuDropdown = document.getElementById('mobile-menu-dropdown');
    if (mobileMenuButton && mobileMenuDropdown) {
        mobileMenuButton.addEventListener('click', () => {
            mobileMenuDropdown.classList.toggle('hidden');
        });
    }
}

/**
 * Closes the mobile menu if it's open.
 */
function closeMobileMenu() {
    const mobileMenuDropdown = document.getElementById('mobile-menu-dropdown');
    if (mobileMenuDropdown && !mobileMenuDropdown.classList.contains('hidden')) {
        mobileMenuDropdown.classList.add('hidden');
    }
}

/**
 * Displays a global message toast.
 * @param {string} message - The message to display.
 * @param {string} [type='success'] - The type of message ('success', 'error', 'info').
 * @param {number} [duration=4000] - The duration to display the message in milliseconds.
 */
function showGlobalMessage(message, type = 'success', duration = 4000) {
    const toast = document.getElementById('global-message-toast');
    const textElement = document.getElementById('global-message-text');
    if (!toast || !textElement) {
        console.warn("Global message toast elements not found. Fallback to alert.");
        alert(message); // Fallback if toast elements are not in the HTML
        return;
    }

    textElement.textContent = message;
    toast.className = 'modal-message'; // Reset classes, then add specific ones

    if (type === 'error') {
        toast.classList.add('bg-brand-truffle-burgundy', 'text-brand-cream');
    } else if (type === 'info') {
        toast.classList.add('bg-brand-slate-blue-grey', 'text-brand-cream');
    } else { // success
        toast.classList.add('bg-brand-deep-sage-green', 'text-brand-cream');
    }
    
    toast.style.display = 'block';
    // Force reflow before adding 'show' class for transition to work
    void toast.offsetWidth; 
    toast.classList.add('show');

    // Clear existing timeouts to prevent conflicts
    if (toast.currentTimeout) clearTimeout(toast.currentTimeout);
    if (toast.hideTimeout) clearTimeout(toast.hideTimeout);

    toast.currentTimeout = setTimeout(() => {
        toast.classList.remove('show');
        // Wait for fade out transition to complete before hiding
        toast.hideTimeout = setTimeout(() => {
            toast.style.display = 'none';
        }, 500); // Match this duration with CSS transition duration
    }, duration);
}

/**
 * Opens a modal dialog.
 * @param {string} modalId - The ID of the modal element to open.
 * @param {string} [productName=''] - Optional product name for the add-to-cart modal.
 */
function openModal(modalId, productName = '') {
    const modal = document.getElementById(modalId);
    if (modal) {
        if (modalId === 'add-to-cart-modal' && productName) {
            const modalProductName = modal.querySelector('#modal-product-name');
            if (modalProductName) modalProductName.textContent = `${productName} ajouté au panier !`;
        }
        modal.classList.add('active');
    }
}

/**
 * Closes a modal dialog.
 * @param {string} modalId - The ID of the modal element to close.
 */
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

/**
 * Sets the active state for the current navigation link.
 */
function setActiveNavLink() {
    const currentPage = window.location.pathname.split("/").pop() || "index.html";
    const navLinks = document.querySelectorAll('header nav .nav-link, #mobile-menu-dropdown .nav-link');
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        // Ensure href is not null or empty before trying to split
        const linkHref = link.getAttribute('href');
        if (linkHref) {
            const linkPage = linkHref.split("/").pop() || "index.html";
            if (linkPage === currentPage) {
                link.classList.add('active');
            }
        }
    });
}

/**
 * Validates an email address format.
 * @param {string} email - The email address to validate.
 * @returns {boolean} - True if the email is valid, false otherwise.
 */
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
}

/**
 * Sets an error message for a form field and applies error styling.
 * @param {HTMLElement} field - The form field element.
 * @param {string} message - The error message to display.
 */
function setFieldError(field, message) {
    if (!field) return;
    field.classList.add('border-red-500', 'ring-red-500');
    let errorElement = field.parentElement.querySelector('.error-message');
    if (!errorElement) {
        errorElement = document.createElement('p');
        errorElement.classList.add('error-message', 'text-xs', 'text-red-600', 'mt-1');
        // Insert after the field, or at the end of parent if structure is complex
        if (field.nextSibling) {
            field.parentElement.insertBefore(errorElement, field.nextSibling);
        } else {
            field.parentElement.appendChild(errorElement);
        }
    }
    errorElement.textContent = message;
}

/**
 * Clears all error messages and styling from a form.
 * @param {HTMLFormElement} form - The form element.
 */
function clearFormErrors(form) {
    if (!form) return;
    form.querySelectorAll('.border-red-500, .ring-red-500').forEach(el => {
        el.classList.remove('border-red-500', 'ring-red-500');
    });
    form.querySelectorAll('.error-message').forEach(el => el.remove());
}

/**
 * Gets the appropriate CSS class for an order status.
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
