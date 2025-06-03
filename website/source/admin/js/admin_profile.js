// website/source/admin/js/admin_profile.js

document.addEventListener('DOMContentLoaded', () => {
    // Ensure this script only runs on the admin profile page
    if (document.body.id !== 'page-admin-profile') {
        return;
    }
// website/source/admin/js/admin_profile.js

document.addEventListener('DOMContentLoaded', () => {
    if (document.body.id !== 'page-admin-profile') {
        return;
    }

    const profileEmailEl = document.getElementById('profile-email');
    const profileNameEl = document.getElementById('profile-name');
    const profileRoleEl = document.getElementById('profile-role');
    const totpCurrentStatusEl = document.getElementById('totp-current-status');
    const manageTotpButton = document.getElementById('manage-totp-button');

    const totpInitiateSection = document.getElementById('totp-initiate-section');
    const currentPasswordForTotpInput = document.getElementById('current-password-for-totp');
    const initiateTotpSetupButton = document.getElementById('initiate-totp-setup-button');
    const cancelTotpInitiateButton = document.getElementById('cancel-totp-initiate-button');

    const totpQrCodeSection = document.getElementById('totp-qr-code-section');
    const totpQrCodeContainer = document.getElementById('totp-qr-code-container');
    const totpManualKeyEl = document.getElementById('totp-manual-key');
    const totpVerificationCodeInput = document.getElementById('totp-verification-code');
    const verifyEnableTotpButton = document.getElementById('verify-enable-totp-button');
    const cancelTotpQrButton = document.getElementById('cancel-totp-qr-button');
    
    const totpDisableSection = document.getElementById('totp-disable-section');
    const currentPasswordForDisableInput = document.getElementById('current-password-for-disable');
    const currentTotpForDisableInput = document.getElementById('current-totp-for-disable');
    const disableTotpButton = document.getElementById('disable-totp-button');
    const cancelTotpDisableButton = document.getElementById('cancel-totp-disable-button');

    const totpMessageArea = document.getElementById('totp-message-area');

    let currentUserData = null; 
    let qrCodeInstance = null; 

    function showTotpMessage(message, isError = false) {
        if (totpMessageArea) {
            totpMessageArea.textContent = message; // XSS: Message is from system/translation, assumed safe
            totpMessageArea.className = `text-sm mt-3 ${isError ? 'text-red-600' : 'text-green-600'}`;
        }
        if(typeof showAdminToast === 'function') {
            showAdminToast(message, isError ? 'error' : 'success', 5000); 
        }
    }

    function resetTotpSections() {
        totpInitiateSection.classList.add('hidden');
        currentPasswordForTotpInput.value = '';
        totpQrCodeSection.classList.add('hidden');
        if (qrCodeInstance) {
            totpQrCodeContainer.innerHTML = ''; 
            qrCodeInstance = null;
        }
        totpManualKeyEl.textContent = ''; // XSS: Key is alphanumeric, safe
        totpVerificationCodeInput.value = '';
        totpDisableSection.classList.add('hidden');
        currentPasswordForDisableInput.value = '';
        currentTotpForDisableInput.value = '';
        if(totpMessageArea) totpMessageArea.textContent = ''; // Safe
        
        if(initiateTotpSetupButton) {
            initiateTotpSetupButton.disabled = false;
            initiateTotpSetupButton.textContent = "Continuer la configuration 2FA"; // XSS: static
        }
        if(verifyEnableTotpButton) {
            verifyEnableTotpButton.disabled = false;
            verifyEnableTotpButton.textContent = "Vérifier et Activer 2FA"; // XSS: static
        }
        if(disableTotpButton) {
            disableTotpButton.disabled = false;
            disableTotpButton.textContent = "Désactiver 2FA"; // XSS: static
        }
    }

    function updateTotpDisplay() {
        if (!currentUserData || !totpCurrentStatusEl || !manageTotpButton) return;

        if (currentUserData.is_totp_enabled) {
            totpCurrentStatusEl.textContent = 'Activée'; // XSS: static
            totpCurrentStatusEl.className = 'font-semibold text-green-600';
            manageTotpButton.textContent = 'Désactiver 2FA'; // XSS: static
            manageTotpButton.classList.remove('btn-admin-primary', 'btn-admin-secondary');
            manageTotpButton.classList.add('btn-admin-danger');
        } else {
            totpCurrentStatusEl.textContent = 'Désactivée'; // XSS: static
            totpCurrentStatusEl.className = 'font-semibold text-red-600';
            manageTotpButton.textContent = 'Activer 2FA'; // XSS: static
            manageTotpButton.classList.remove('btn-admin-danger');
            manageTotpButton.classList.add('btn-admin-primary'); 
        }
        resetTotpSections();
    }

    async function loadAdminProfile() {
        const adminUser = getAdminUser(); 
        if (adminUser) {
            currentUserData = adminUser; 
            if (profileEmailEl) profileEmailEl.textContent = adminUser.email; // XSS: email, generally safe
            if (profileNameEl) profileNameEl.textContent = `${adminUser.prenom || ''} ${adminUser.nom || ''}`.trim() || 'N/A'; // XSS: names
            if (profileRoleEl) profileRoleEl.textContent = adminUser.role; // XSS: role
            updateTotpDisplay();
        } else {
            if (profileEmailEl) profileEmailEl.textContent = 'Erreur de chargement'; // XSS: static
            if (totpCurrentStatusEl) totpCurrentStatusEl.textContent = 'Erreur'; // XSS: static
            console.error("Admin user data not found in session.");
            showAdminToast("Impossible de charger les informations du profil.", "error");
        }
    }

    if (manageTotpButton) {
        manageTotpButton.addEventListener('click', () => {
            resetTotpSections(); 
            if (currentUserData && currentUserData.is_totp_enabled) {
                totpDisableSection.classList.remove('hidden');
            } else {
                totpInitiateSection.classList.remove('hidden');
            }
        });
    }

    if (initiateTotpSetupButton) {
        initiateTotpSetupButton.addEventListener('click', async () => {
            const password = currentPasswordForTotpInput.value;
            if (!password) {
                showTotpMessage("Veuillez entrer votre mot de passe actuel.", true);
                return;
            }
            initiateTotpSetupButton.disabled = true;
            initiateTotpSetupButton.textContent = "Chargement..."; // XSS: static
            try {
                const response = await adminApi.initiateTotpSetup(password);
                if (response.success) {
                    totpInitiateSection.classList.add('hidden');
                    totpQrCodeSection.classList.remove('hidden');
                    totpQrCodeContainer.innerHTML = ''; 
                    if (typeof QRCode !== 'undefined') {
                        qrCodeInstance = new QRCode(totpQrCodeContainer, {
                            text: response.totp_provisioning_uri, // URI is data, not HTML
                            width: 180, height: 180, colorDark : "#000000",
                            colorLight : "#ffffff", correctLevel : QRCode.CorrectLevel.H
                        });
                    } else {
                        totpQrCodeContainer.textContent = "Erreur: Librairie QRCode non chargée."; // XSS: static
                        console.error("QRCode library is not loaded.");
                    }
                    totpManualKeyEl.textContent = response.totp_manual_secret; // XSS: key is alphanumeric
                    totpVerificationCodeInput.value = '';
                    totpVerificationCodeInput.focus();
                    showTotpMessage("Scannez le QR code ou entrez la clé manuellement, puis entrez le code de vérification.", false);
                } else {
                    showTotpMessage(response.message || "Échec de l'initialisation de la 2FA.", true);
                }
            } catch (error) {
                showTotpMessage(error.data?.message || "Une erreur est survenue lors de l'initialisation de la 2FA.", true);
            } finally {
                initiateTotpSetupButton.disabled = false;
                initiateTotpSetupButton.textContent = "Continuer la configuration 2FA"; // XSS: static
            }
        });
    }
    
    if (cancelTotpInitiateButton) cancelTotpInitiateButton.addEventListener('click', resetTotpSections);
    if (cancelTotpQrButton) cancelTotpQrButton.addEventListener('click', resetTotpSections);
    if (cancelTotpDisableButton) cancelTotpDisableButton.addEventListener('click', resetTotpSections);

    if (verifyEnableTotpButton) {
        verifyEnableTotpButton.addEventListener('click', async () => {
            const totpCode = totpVerificationCodeInput.value;
            if (!totpCode || totpCode.length !== 6 || !/^\d+$/.test(totpCode)) {
                showTotpMessage("Veuillez entrer un code TOTP à 6 chiffres valide.", true);
                return;
            }
            verifyEnableTotpButton.disabled = true;
            verifyEnableTotpButton.textContent = "Vérification..."; // XSS: static
            try {
                const response = await adminApi.verifyAndEnableTotp(totpCode);
                if (response.success) {
                    showTotpMessage("Authentification à Deux Facteurs (2FA) activée avec succès!", false);
                    const updatedAdminUser = await adminApi.getAdminUserSelf(); 
                    if (updatedAdminUser && updatedAdminUser.success && updatedAdminUser.user) {
                         setAdminUserSession(updatedAdminUser.user, getAdminAuthToken()); 
                         currentUserData = updatedAdminUser.user;
                    }
                    updateTotpDisplay(); 
                } else {
                    showTotpMessage(response.message || "Code TOTP invalide. Veuillez réessayer.", true);
                }
            } catch (error) {
                showTotpMessage(error.data?.message || "Une erreur est survenue lors de la vérification du code TOTP.", true);
            } finally {
                verifyEnableTotpButton.disabled = false;
                verifyEnableTotpButton.textContent = "Vérifier et Activer 2FA"; // XSS: static
            }
        });
    }

    if (disableTotpButton) {
        disableTotpButton.addEventListener('click', async () => {
            const password = currentPasswordForDisableInput.value;
            const totpCode = currentTotpForDisableInput.value;

            if (!password) {
                showTotpMessage("Veuillez entrer votre mot de passe actuel.", true);
                return;
            }
            if (!totpCode || totpCode.length !== 6 || !/^\d+$/.test(totpCode)) {
                showTotpMessage("Veuillez entrer un code TOTP à 6 chiffres valide.", true);
                return;
            }
            disableTotpButton.disabled = true;
            disableTotpButton.textContent = "Désactivation..."; // XSS: static
            try {
                const response = await adminApi.disableTotp(password, totpCode);
                if (response.success) {
                    showTotpMessage("Authentification à Deux Facteurs (2FA) désactivée avec succès.", false);
                     const updatedAdminUser = await adminApi.getAdminUserSelf(); 
                    if (updatedAdminUser && updatedAdminUser.success && updatedAdminUser.user) {
                         setAdminUserSession(updatedAdminUser.user, getAdminAuthToken());
                         currentUserData = updatedAdminUser.user;
                    }
                    updateTotpDisplay();
                } else {
                    showTotpMessage(response.message || "Échec de la désactivation de la 2FA.", true);
                }
            } catch (error) {
                 showTotpMessage(error.data?.message || "Une erreur est survenue lors de la désactivation de la 2FA.", true);
            } finally {
                disableTotpButton.disabled = false;
                disableTotpButton.textContent = "Désactiver 2FA"; // XSS: static
            }
        });
    }

    loadAdminProfile();
});
