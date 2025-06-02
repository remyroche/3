// website/js/ui.js
// UI helper functions for the frontend application

function initializeMobileMenu() {
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenuDropdown = document.getElementById('mobile-menu-dropdown');
    if (mobileMenuButton && mobileMenuDropdown) {
        mobileMenuButton.addEventListener('click', () => {
            mobileMenuDropdown.classList.toggle('hidden');
        });
    }
}

function closeMobileMenu() {
    const mobileMenuDropdown = document.getElementById('mobile-menu-dropdown');
    if (mobileMenuDropdown && !mobileMenuDropdown.classList.contains('hidden')) {
        mobileMenuDropdown.classList.add('hidden');
    }
}

function showGlobalMessage(message, type = 'success', duration = 4000) {
    const toast = document.getElementById('global-message-toast');
    const textElement = document.getElementById('global-message-text');
    if (!toast || !textElement) {
        console.warn(t('public.js.toast_elements_not_found')); // Key: public.js.toast_elements_not_found (For dev console)
        alert(message); 
        return;
    }

    textElement.textContent = message;
    toast.className = 'modal-message'; 

    if (type === 'error') {
        toast.classList.add('bg-brand-truffle-burgundy', 'text-brand-cream');
    } else if (type === 'info') {
        toast.classList.add('bg-brand-slate-blue-grey', 'text-brand-cream');
    } else { 
        toast.classList.add('bg-brand-deep-sage-green', 'text-brand-cream');
    }
    
    toast.style.display = 'block';
    void toast.offsetWidth; 
    toast.classList.add('show');

    if (toast.currentTimeout) clearTimeout(toast.currentTimeout);
    if (toast.hideTimeout) clearTimeout(toast.hideTimeout);

    toast.currentTimeout = setTimeout(() => {
        toast.classList.remove('show');
        toast.hideTimeout = setTimeout(() => {
            toast.style.display = 'none';
        }, 500); 
    }, duration);
}

function openModal(modalId, productName = '', quantity = 1) {
    const modal = document.getElementById(modalId);
    if (modal) {
        if (modalId === 'add-to-cart-modal' && productName) {
            const modalProductName = modal.querySelector('#modal-product-name');
            if (modalProductName) {
                // Assuming t('public.js.added_to_cart_toast_template') is like "%qty% x %name% added!"
                let messageTemplate = t('public.js.added_to_cart_toast_template'); // Key: public.js.added_to_cart_toast_template
                const finalMessage = messageTemplate.replace('%qty%', quantity).replace('%name%', productName);
                modalProductName.textContent = finalMessage;
            }
        }
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

function setActiveNavLink() {
    const currentPage = window.location.pathname.split("/").pop() || "index.html";
    const navLinks = document.querySelectorAll('header nav .nav-link, #mobile-menu-dropdown .nav-link');
    
    navLinks.forEach(link => {
        link.classList.remove('active'); // Ensure 'active' class is defined in your CSS
        const linkHref = link.getAttribute('href');
        if (linkHref) {
            const linkPage = linkHref.split("/").pop() || "index.html";
            if (linkPage === currentPage) {
                link.classList.add('active');
            }
        }
    });
}

function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
}

function setFieldError(field, message) {
    if (!field) return;
    field.classList.add('border-red-500', 'ring-red-500'); // Example error styling classes
    let errorElement = field.parentElement.querySelector('.error-message');
    if (!errorElement) {
        errorElement = document.createElement('p');
        errorElement.classList.add('error-message', 'text-xs', 'text-red-600', 'mt-1'); // Example error message classes
        if (field.nextSibling) {
            field.parentElement.insertBefore(errorElement, field.nextSibling);
        } else {
            field.parentElement.appendChild(errorElement);
        }
    }
    errorElement.textContent = message; // Message should be a translated string
}

function clearFormErrors(form) {
    if (!form) return;
    form.querySelectorAll('.border-red-500, .ring-red-500').forEach(el => {
        el.classList.remove('border-red-500', 'ring-red-500');
    });
    form.querySelectorAll('.error-message').forEach(el => el.remove());
}

function getOrderStatusClass(status) { // For styling, not direct text output
    switch (status ? status.toLowerCase() : '') { // Add null check for status
        case 'paid': return 'bg-green-100 text-green-800';
        case 'shipped': return 'bg-blue-100 text-blue-800';
        case 'delivered': return 'bg-purple-100 text-purple-800';
        case 'pending': case 'pending_payment': return 'bg-yellow-100 text-yellow-800';
        case 'cancelled': case 'failed': return 'bg-red-100 text-red-800';
        default: return 'bg-gray-100 text-gray-800';
    }
}

function updateCartIcon() {
    const cartItemCount = typeof getCartItemCount === 'function' ? getCartItemCount() : 0; // From cart.js
    const desktopCountEl = document.getElementById('cart-item-count');
    const mobileCountEl = document.getElementById('mobile-cart-item-count');

    if (desktopCountEl) {
        desktopCountEl.textContent = cartItemCount;
        desktopCountEl.style.display = cartItemCount > 0 ? 'flex' : 'none';
    }
    if (mobileCountEl) {
        mobileCountEl.textContent = cartItemCount;
        mobileCountEl.style.display = cartItemCount > 0 ? 'flex' : 'none';
    }
}

// Ensure this is also called if cart.js might not be loaded yet when header is parsed
// or if updateCartDisplay from cart.js is preferred.
// document.addEventListener('DOMContentLoaded', updateCartIcon);
