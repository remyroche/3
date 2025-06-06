// website/source/admin/js/admin_ui.js
// This script provides UI helper functions, like modals, for the admin panel.

/**
 * Creates the basic HTML structure for a modal.
 * @param {string} id - The ID for the modal overlay element.
 * @param {string} title - The title to display in the modal header.
 * @param {string} message - The message content for the modal body.
 * @param {string} [type='info'] - The type of message (info, success, error, warning) for styling.// website/source/admin/js/admin_ui.js
// This script provides UI helper functions, like modals and toasts, for the admin panel.

/**
 * Creates the basic HTML structure for a modal.
 * @param {string} id - The ID for the modal overlay element.
 * @param {string} title - The title to display in the modal header.
 * @param {string | HTMLElement} messageOrContent - The message content (string or HTML element) for the modal body.
 * @param {string} [type='info'] - The type of message (info, success, error, warning) for styling.
 * @returns {object} - Contains references to modalOverlay, modalActions, and closeButton.
 * @private
 */
function _createModalStructure(id, title, messageOrContent, type = 'info') {
    const existingModal = document.getElementById(id);
    if (existingModal) {
        existingModal.remove();
    }

    const modalOverlay = document.createElement('div');
    modalOverlay.id = id;
    modalOverlay.className = 'admin-modal-overlay'; 
    
    const modalContent = document.createElement('div');
    modalContent.className = `admin-modal-content admin-message-${type}`; 
    
    const modalHeader = document.createElement('div');
    modalHeader.className = 'admin-modal-header';
    const modalTitleElement = document.createElement('h3');
    modalTitleElement.textContent = title; // XSS: Title set with textContent
    const closeButton = document.createElement('span');
    closeButton.className = 'admin-modal-close';
    closeButton.innerHTML = '&times;'; // Safe static HTML
    closeButton.setAttribute('aria-label', 'Close modal');
    modalHeader.appendChild(modalTitleElement);
    modalHeader.appendChild(closeButton);
    
    const modalBody = document.createElement('div');
    modalBody.className = 'admin-modal-body';
    
    if (typeof messageOrContent === 'string') {
        // If messageOrContent is a string, assume it might contain simple HTML for formatting (e.g. <strong>).
        // This is a known point where sanitization would be needed if the string source is untrusted.
        // For admin-generated messages, this might be acceptable, but for user-input, it's a risk.
        // For now, we allow HTML here, but it's a good place for future DOMPurify if messages become complex or user-influenced.
        const modalMessageElement = document.createElement('p'); // Default to a paragraph
        modalMessageElement.innerHTML = messageOrContent; // XSS: Potential risk if messageOrContent is untrusted HTML
        modalBody.appendChild(modalMessageElement);
    } else if (messageOrContent instanceof HTMLElement) {
        // If it's already an HTMLElement, append it directly. Assumed to be safely constructed.
        modalBody.appendChild(messageOrContent);
    } else {
        const modalMessageElement = document.createElement('p');
        modalMessageElement.textContent = String(messageOrContent); // Fallback to textContent
        modalBody.appendChild(modalMessageElement);
    }
    
    const modalActions = document.createElement('div');
    modalActions.className = 'admin-modal-actions'; 
    
    modalContent.appendChild(modalHeader);
    modalContent.appendChild(modalBody);
    modalContent.appendChild(modalActions);
    modalOverlay.appendChild(modalContent);
    
    document.body.appendChild(modalOverlay);
    document.body.classList.add('admin-modal-open'); 
    
    return { modalOverlay, modalActions, closeButton };
}

/**
 * Displays a confirmation modal.
 * @param {string} title - The title of the confirmation dialog.
 * @param {string | HTMLElement} message - The confirmation message (can include safe HTML or be an HTMLElement).
 * @param {function} onConfirmCallback - Function to call if the user confirms.
 * @param {string} [confirmText='Confirm'] - Text for the confirm button.
 * @param {string} [cancelText='Cancel'] - Text for the cancel button.
 */
function showAdminConfirm(title, message, onConfirmCallback, confirmText = 'Confirm', cancelText = 'Cancel') {
    const { modalOverlay, modalActions, closeButton } = _createModalStructure('adminConfirmModal', title, message, 'warning');

    const confirmButton = document.createElement('button');
    confirmButton.id = 'adminModalConfirm';
    confirmButton.className = 'btn btn-admin-danger';
    confirmButton.textContent = confirmText; // XSS Safe
    
    const cancelButton = document.createElement('button');
    cancelButton.id = 'adminModalCancel';
    cancelButton.className = 'btn btn-admin-secondary'; 
    cancelButton.textContent = cancelText; // XSS Safe

    modalActions.appendChild(cancelButton); 
    modalActions.appendChild(confirmButton); 

    
    function closeModal() {
        modalOverlay.remove();
        document.body.classList.remove('admin-modal-open');
    }

    closeButton.onclick = closeModal;
    cancelButton.onclick = closeModal;
    confirmButton.onclick = () => {
        closeModal();
        if (onConfirmCallback && typeof onConfirmCallback === 'function') {
            onConfirmCallback();
        }
    };
    
    modalOverlay.classList.add('active'); // Show the modal using the 'active' class
}

/**
 * Displays a message modal (info, success, error).
 * @param {string} message - The message to display (assumed to be safe text or simple HTML).
 * @param {string} [type='info'] - Type of message: 'info', 'success', 'error', 'warning'.
 * @param {string} [title='Notification'] - The title of the message modal.
 */
function showAdminMessage(message, type = 'info', title = 'Notification') {
    if (title === 'Notification') {
        switch(type) {
            case 'success': title = 'Success!'; break;
            case 'error': title = 'Error'; break;
            case 'warning': title = 'Warning'; break;
            default: title = 'Information';
        }
    }

    const { modalOverlay, modalActions, closeButton } = _createModalStructure('adminMessageModal', title, message, type);

    const okButton = document.createElement('button');
    okButton.id = 'adminMessageOk';
    okButton.className = 'btn btn-admin-primary';
    okButton.textContent = 'OK'; // XSS: static text
    modalActions.appendChild(okButton);

    function closeModal() {
        modalOverlay.remove();
        document.body.classList.remove('admin-modal-open');
    }

    closeButton.onclick = closeModal;
    okButton.onclick = closeModal;
    
    modalOverlay.classList.add('active'); // Show the modal using the 'active' class
}


/**
 * Displays a toast message.
 * @param {string} message - The message to display in the toast.
 * @param {string} [type='info'] - Type of toast: 'info', 'success', 'error', 'warning'.
 * @param {number} [duration=5000] - Duration in milliseconds before the toast auto-hides.
 */
function showAdminToast(message, type = 'info', duration = 5000) {
    let toastContainer = document.getElementById('admin-toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'admin-toast-container';
        // Styles for toastContainer are in admin_style.css
        // (fixed, bottom, right, z-index, flex, flex-col-reverse, gap)
        document.body.appendChild(toastContainer);
    }

    const toast = document.createElement('div');
    toast.className = `admin-toast ${type}`; // CSS classes handle background color
    toast.textContent = message; // XSS: message is set with textContent, safe.

    toastContainer.appendChild(toast);

    // Trigger fade-in animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 10); // Small delay to ensure transition takes effect

    // Auto-hide
    setTimeout(() => {
        toast.classList.remove('show');
        // Remove from DOM after fade-out animation
        toast.addEventListener('transitionend', () => {
            if (toast.parentElement) { // Check if still in DOM before removing
                toast.remove();
            }
            // Optional: remove container if empty
            // if (toastContainer.children.length === 0) {
            //     toastContainer.remove();
            // }
        }, { once: true });
    }, duration);
}

/**
 * Opens a modal dialog by its ID.
 * @param {string} modalId - The ID of the modal overlay to open.
 */
function openAdminModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active'); // Use 'active' class to show
        document.body.classList.add('admin-modal-open'); // Prevent background scroll
    } else {
        console.warn(`Modal with ID '${modalId}' not found.`);
    }
}

/**
 * Closes a modal dialog by its ID.
 * @param {string} modalId - The ID of the modal overlay to close.
 */
function closeAdminModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active'); // Use 'active' class to hide
        // Check if any other modals are open before removing the body class
        const anyActiveModals = document.querySelector('.admin-modal-overlay.active');
        if (!anyActiveModals) {
            document.body.classList.remove('admin-modal-open');
        }
    } else {
        console.warn(`Modal with ID '${modalId}' not found for closing.`);
    }
}
