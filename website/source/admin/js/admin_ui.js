// website/source/admin/js/admin_ui.js
// This script provides UI helper functions, like modals, for the admin panel.

/**
 * Creates the basic HTML structure for a modal.
 * @param {string} id - The ID for the modal overlay element.
 * @param {string} title - The title to display in the modal header.
 * @param {string} message - The message content for the modal body.
 * @param {string} [type='info'] - The type of message (info, success, error, warning) for styling.
 * @returns {object} - Contains references to modalOverlay, modalActions, and closeButton.
 * @private
 */
function _createModalStructure(id, title, message, type = 'info') {
    // Remove any existing modal with the same ID to prevent duplicates
    const existingModal = document.getElementById(id);
    if (existingModal) {
        existingModal.remove();
    }

    const modalOverlay = document.createElement('div');
    modalOverlay.id = id;
    modalOverlay.className = 'admin-modal-overlay'; // For general overlay styling
    
    const modalContent = document.createElement('div');
    // Add type-specific class for header styling (e.g., admin-message-success)
    modalContent.className = `admin-modal-content admin-message-${type}`; 
    
    const modalHeader = document.createElement('div');
    modalHeader.className = 'admin-modal-header';
    const modalTitleElement = document.createElement('h3');
    modalTitleElement.textContent = title;
    const closeButton = document.createElement('span');
    closeButton.className = 'admin-modal-close';
    closeButton.innerHTML = '&times;'; // 'x' character for close
    modalHeader.appendChild(modalTitleElement);
    modalHeader.appendChild(closeButton);
    
    const modalBody = document.createElement('div');
    modalBody.className = 'admin-modal-body';
    const modalMessageElement = document.createElement('p');
    modalMessageElement.innerHTML = message; // Use innerHTML to allow basic HTML like <strong>
    modalBody.appendChild(modalMessageElement);
    
    const modalActions = document.createElement('div');
    modalActions.className = 'admin-modal-actions'; // For styling action buttons
    
    modalContent.appendChild(modalHeader);
    modalContent.appendChild(modalBody);
    modalContent.appendChild(modalActions);
    modalOverlay.appendChild(modalContent);
    
    document.body.appendChild(modalOverlay);
    document.body.classList.add('admin-modal-open'); // To prevent background scroll
    
    return { modalOverlay, modalActions, closeButton };
}

/**
 * Displays a confirmation modal.
 * @param {string} title - The title of the confirmation dialog.
 * @param {string} message - The confirmation message (can include HTML).
 * @param {function} onConfirmCallback - Function to call if the user confirms.
 * @param {string} [confirmText='Confirm'] - Text for the confirm button.
 * @param {string} [cancelText='Cancel'] - Text for the cancel button.
 */
function showAdminConfirm(title, message, onConfirmCallback, confirmText = 'Confirm', cancelText = 'Cancel') {
    const { modalOverlay, modalActions, closeButton } = _createModalStructure('adminConfirmModal', title, message, 'warning'); // Warning style for confirm

    const confirmButton = document.createElement('button');
    confirmButton.id = 'adminModalConfirm';
    confirmButton.className = 'admin-button primary'; // Primary action style
    confirmButton.textContent = confirmText;
    
    const cancelButton = document.createElement('button');
    cancelButton.id = 'adminModalCancel';
    cancelButton.className = 'admin-button secondary'; // Secondary action style
    cancelButton.textContent = cancelText;

    modalActions.appendChild(cancelButton); // Cancel typically on the left
    modalActions.appendChild(confirmButton); // Confirm on the right
    
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
    
    modalOverlay.style.display = 'flex'; // Show the modal
}

/**
 * Displays a message modal (info, success, error).
 * @param {string} message - The message to display (can include HTML).
 * @param {string} [type='info'] - Type of message: 'info', 'success', 'error', 'warning'.
 * @param {string} [title='Notification'] - The title of the message modal.
 */
function showAdminMessage(message, type = 'info', title = 'Notification') {
    // Determine title based on type if not explicitly provided
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
    okButton.className = 'admin-button primary';
    okButton.textContent = 'OK';
    modalActions.appendChild(okButton);

    function closeModal() {
        modalOverlay.remove();
        document.body.classList.remove('admin-modal-open');
    }

    closeButton.onclick = closeModal;
    okButton.onclick = closeModal;
    
    modalOverlay.style.display = 'flex'; // Show the modal

    // Optional: Auto-close for success/info messages after a delay
    // if (type === 'success' || type === 'info') {
    //     setTimeout(closeModal, 3500); 
    // }
}