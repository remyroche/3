// website/source/pro/js/programme-fidelite.js

document.addEventListener('DOMContentLoaded', async () => {
    // Ensure this script runs only on the loyalty program page
    if (!document.body.classList.contains('pro-page') || !document.getElementById('user-loyalty-status')) {
        // Check for a specific element unique to programme-fidelite.html if body class is too general
        return;
    }

    // Authentication check (using functions from auth.js assumed to be loaded)
    if (typeof isUserLoggedIn !== 'function' || !isUserLoggedIn()) {
        if (typeof showGlobalMessage === 'function') showGlobalMessage(t('public.cart.login_prompt', 'Veuillez vous connecter pour accéder à cette page.'), 'error');
        setTimeout(() => { window.location.href = 'professionnels.html'; }, 3000); // Redirect to B2B login/landing
        return;
    }

    const currentUser = typeof getCurrentUser === 'function' ? getCurrentUser() : null;
    if (!currentUser || currentUser.role !== 'b2b_professional' || currentUser.professional_status !== 'approved') {
        if (typeof showGlobalMessage === 'function') showGlobalMessage(t('pro_loyalty.auth_error', 'Accès réservé aux professionnels approuvés.'), 'error');
        setTimeout(() => { window.location.href = 'professionnels.html'; }, 3000);
        return;
    }

    // DOM Elements
    const userTierNameEl = document.getElementById('user-tier-name');
    const userAnnualSpendEl = document.getElementById('user-annual-spend');
    const userReferralCreditEl = document.getElementById('user-referral-credit');
    const userReferralCodeEl = document.getElementById('user-referral-code');
    const copyReferralCodeBtn = document.getElementById('copy-referral-code');

    const progressBarEl = document.getElementById('loyalty-progress-bar');
    const nextTierNameProgressEl = document.getElementById('next-tier-name-progress');
    const spendToNextTierEl = document.getElementById('spend-to-next-tier');
    const nextTierProgressSectionEl = document.getElementById('next-tier-progress-section');

    const tierCards = {
        1000: document.getElementById('tier-1000'), // Silver
        5000: document.getElementById('tier-5000'), // Sapphire
        15000: document.getElementById('tier-15000'), // Gold
        25000: document.getElementById('tier-25000')  // Diamond
        // Restaurant branding is a special tier/overlay
    };

    // Tier definitions (could also be fetched from backend if they become very dynamic)
    const loyaltyTiers = [
        { name: "Bronze", minSpend: 0, nextSpendThreshold: 1000, perksKey: "pro_loyalty.tier0_name", discount: 0 }, // Base, no explicit card
        { name: "Argent", minSpend: 1000, nextSpendThreshold: 5000, perksKey: "pro_loyalty.tier1_name", discount: 2, cardId: 1000 },
        { name: "Saphir", minSpend: 5000, nextSpendThreshold: 15000, perksKey: "pro_loyalty.tier2_name", discount: 5, cardId: 5000 },
        { name: "Or", minSpend: 15000, nextSpendThreshold: 25000, perksKey: "pro_loyalty.tier3_name", discount: 8, cardId: 15000 },
        { name: "Diamant", minSpend: 25000, nextSpendThreshold: Infinity, perksKey: "pro_loyalty.tier4_name", discount: 10, cardId: 25000 }
        // Restaurant Branding is a special status that adds 30% discount on top.
    ];


    async function fetchLoyaltyStatus() {
        try {
            // Ensure makeApiRequest is available (from api.js)
            if (typeof makeApiRequest !== 'function') {
                console.error("makeApiRequest function is not defined. Ensure api.js is loaded.");
                if (userTierNameEl) userTierNameEl.textContent = t('common.error', 'Erreur');
                return;
            }

            const response = await makeApiRequest('/api/b2b/loyalty-status', 'GET', null, true); // true for auth
            if (response.success && response.data) {
                updateLoyaltyDisplay(response.data);
            } else {
                if (typeof showGlobalMessage === 'function') showGlobalMessage(response.message || t('pro_loyalty.error_fetch_status', 'Erreur de chargement du statut de fidélité.'), 'error');
                if (userTierNameEl) userTierNameEl.textContent = t('common.unavailable', 'Indisponible');
            }
        } catch (error) {
            console.error("Error fetching loyalty status:", error);
            if (typeof showGlobalMessage === 'function') showGlobalMessage(t('pro_loyalty.error_fetch_status_network', 'Erreur réseau lors du chargement du statut.'), 'error');
            if (userTierNameEl) userTierNameEl.textContent = t('common.error', 'Erreur');
        }
    }

    function updateLoyaltyDisplay(data) {
        if (userTierNameEl) userTierNameEl.textContent = data.current_tier_name || t('common.not_available', 'N/A');
        if (userAnnualSpendEl) userAnnualSpendEl.textContent = `€${parseFloat(data.annual_spend || 0).toFixed(2)}`;
        if (userReferralCreditEl) userReferralCreditEl.textContent = `€${parseFloat(data.referral_credit_balance || 0).toFixed(2)}`;
        if (userReferralCodeEl) userReferralCodeEl.textContent = data.referral_code || t('common.unavailable', 'Indisponible');

        // Highlight current tier card
        Object.values(tierCards).forEach(card => card?.classList.remove('border-mt-classic-gold', 'border-4', 'shadow-2xl', 'scale-105'));
        
        const currentTierInfo = loyaltyTiers.find(tier => tier.name.toLowerCase() === (data.current_tier_name || '').toLowerCase());
        if (currentTierInfo && tierCards[currentTierInfo.cardId]) {
            tierCards[currentTierInfo.cardId].classList.add('border-mt-classic-gold', 'border-4', 'shadow-2xl', 'scale-105');
        }
         // Handle restaurant branding overlay (if applicable)
        if (data.is_restaurant_branding_partner) {
            // Could add a specific visual indicator near the tier name or on the branding section.
            const brandingTitleEl = document.querySelector('[data-translate-key="pro_loyalty.branding_title"]');
            if (brandingTitleEl) {
                brandingTitleEl.innerHTML += ` <span class="text-sm font-normal text-mt-deep-sage-green">(${t('pro_loyalty.branding_active_badge', 'Actif pour vous!')})</span>`;
            }
        }


        // Progress bar
        if (progressBarEl && nextTierNameProgressEl && spendToNextTierEl && nextTierProgressSectionEl) {
            if (data.next_tier_name && data.spend_needed_for_next_tier > 0 && data.current_tier_min_spend !== undefined && data.next_tier_min_spend !== undefined) {
                nextTierProgressSectionEl.classList.remove('hidden');
                nextTierNameProgressEl.textContent = data.next_tier_name;
                spendToNextTierEl.textContent = `€${parseFloat(data.spend_needed_for_next_tier).toFixed(2)}`;
                
                const spendInCurrentTier = Math.max(0, data.annual_spend - data.current_tier_min_spend);
                const rangeForCurrentTier = data.next_tier_min_spend - data.current_tier_min_spend;
                const progressPercentage = rangeForCurrentTier > 0 ? (spendInCurrentTier / rangeForCurrentTier) * 100 : 0;
                progressBarEl.style.width = `${Math.min(100, Math.max(0, progressPercentage))}%`;
            } else {
                nextTierProgressSectionEl.classList.add('hidden'); // Hide if at top tier or data missing
                 if (data.current_tier_name.toLowerCase() === loyaltyTiers[loyaltyTiers.length -1].name.toLowerCase()) {
                     nextTierProgressSectionEl.classList.remove('hidden');
                     nextTierNameProgressEl.textContent = t('pro_loyalty.top_tier_reached', 'Niveau maximal atteint!');
                     spendToNextTierEl.textContent = '';
                     progressBarEl.style.width = '100%';

                 }
            }
        }
    }

    if (copyReferralCodeBtn && userReferralCodeEl) {
        copyReferralCodeBtn.addEventListener('click', () => {
            const code = userReferralCodeEl.textContent;
            if (code && code !== t('common.unavailable', 'Indisponible') && code !== 'CHARGEMENT') {
                navigator.clipboard.writeText(code).then(() => {
                    if (typeof showGlobalMessage === 'function') showGlobalMessage(t('pro_loyalty.referral_code_copied', 'Code de parrainage copié !'), 'success');
                }).catch(err => {
                    console.error('Failed to copy referral code: ', err);
                    if (typeof showGlobalMessage === 'function') showGlobalMessage(t('pro_loyalty.error_copy_code', 'Erreur de copie du code.'), 'error');
                });
            }
        });
    }

    // Initial fetch of loyalty status
    await fetchLoyaltyStatus();

    // Placeholder for fetching and displaying referrals (optional for now)
    const referralsSection = document.getElementById('user-referrals-section');
    if (referralsSection) {
        // Example: referralsSection.classList.remove('hidden'); 
        // Call a function like fetchAndDisplayReferrals();
    }
});

// Translation keys to add:
// pro_loyalty.title: "Loyalty Program - Maison Trüvra Pro"
// pro_loyalty.main_title: "Exclusive Trüvra Partner Program"
// pro_loyalty.subtitle: "Discover benefits and rewards designed for our valued professional partners."
// pro_loyalty.your_status_title: "Your Partner Status"
// pro_loyalty.current_tier: "Current Tier"
// pro_loyalty.annual_spend: "Spend (365d)"
// pro_loyalty.referral_credit: "Referral Credit"
// pro_loyalty.referral_code: "Your Referral Code"
// common.copy: "Copy"
// pro_loyalty.next_tier_progress: "Progress to next tier ({nextTierName}):"
// pro_loyalty.spend_perks_title: "Annual Spend-Based Perks"
// pro_loyalty.tier0_name: "Bronze" (or similar for base tier if needed for progress)
// pro_loyalty.tier1_name: "Silver Tier (€1,000+)"
// pro_loyalty.tier1_perk1: "2% discount"
// pro_loyalty.tier1_perk2: "Express shipping"
// pro_loyalty.tier2_name: "Sapphire Tier (€5,000+)"
// pro_loyalty.tier2_perk1: "5% discount"
// pro_loyalty.tier2_perk2: "Express shipping"
// pro_loyalty.tier2_perk3: "Special product access"
// pro_loyalty.tier3_name: "Gold Tier (€15,000+)"
// pro_loyalty.tier3_perk1: "8% discount"
// pro_loyalty.tier3_perk2: "Priority stock allocation"
// pro_loyalty.tier3_perk3: "Dedicated WhatsApp support"
// pro_loyalty.tier3_perk_all_previous: "& all previous perks"
// pro_loyalty.tier4_name: "Diamond Tier (€25,000+)"
// pro_loyalty.tier4_perk1: "10% discount"
// pro_loyalty.tier4_perk2: "Private seasonal previews"
// pro_loyalty.tier4_perk3: "Access to limited harvests"
// pro_loyalty.tier4_perk_all_previous: "& all previous perks"
// pro_loyalty.branding_title: "Restaurant Branding Incentive"
// pro_loyalty.branding_desc: "Approved participants displaying “Maison Trüvra” on menus receive:"
// pro_loyalty.branding_reward: "30% discount + all perks of the highest tier achieved."
// pro_loyalty.branding_condition: "Conditions and approval required. Contact us to participate."
// pro_loyalty.referral_title: "Referral Program"
// pro_loyalty.referral_col_category: "Category"
// pro_loyalty.referral_col_criteria: "Criteria"
// pro_loyalty.referral_col_reward: "Reward / Perk"
// pro_loyalty.referral_type_branding: "Referral – Restaurant Branding Incentive"
// pro_loyalty.referral_criteria_branding: "Referred business joins Restaurant Branding Incentive"
// pro_loyalty.referral_reward_branding: "€500 credit to referrer"
// pro_loyalty.referral_type_purchase: "Referral – Based on Referred Purchase"
// pro_loyalty.referral_criteria_purchase1: "Referred business reaches €5,000/year spend"
// pro_loyalty.referral_reward_purchase1: "€250 credit to referrer"
// pro_loyalty.referral_criteria_purchase2: "Referred business reaches €10,000/year spend"
// pro_loyalty.referral_reward_purchase2: "+ €500 additional credit to referrer"
// pro_loyalty.referral_criteria_purchase3: "Referred business reaches €20,000/year spend"
// pro_loyalty.referral_reward_purchase3: "+ €1,000 additional credit to referrer"
// pro_loyalty.referral_note: "Use your unique referral code (see above) when referring new partners. Credits applied after verification."
// pro_loyalty.your_referrals_title: "Your Active Referrals"
// pro_loyalty.no_referrals_yet: "You do not have any active referrals yet."
// pro_loyalty.auth_error: "Access restricted to approved B2B professionals."
// pro_loyalty.error_fetch_status: "Error loading loyalty status."
// pro_loyalty.error_fetch_status_network: "Network error while loading status."
// common.error: "Error"
// common.unavailable: "Unavailable"
// pro_loyalty.referral_code_copied: "Referral code copied!"
// pro_loyalty.error_copy_code: "Error copying code."
// pro_loyalty.top_tier_reached: "Maximum tier achieved!"
// pro_loyalty.branding_active_badge: "Active for you!"
