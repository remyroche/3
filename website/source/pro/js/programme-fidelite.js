// website/source/pro/js/programme-fidelite.js

document.addEventListener('DOMContentLoaded', async () => {
    // Ensure this script runs only on the loyalty program page
    if (!document.body.classList.contains('pro-page') || !document.getElementById('user-loyalty-status')) {
        // Check for a specific element unique to programme-fidelite.html if body class is too generaldocument.addEventListener('DOMContentLoaded', () => {
    fetchLoyaltyInfo();
});

async function fetchLoyaltyInfo() {
    const token = localStorage.getItem('token');
    const loadingDiv = document.getElementById('loyalty-status-loading');
    const contentDiv = document.getElementById('loyalty-status-content');
    
    try {
        const response = await fetch('/pro/get_loyalty_info', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error('Could not fetch loyalty info.');
        }

        const data = await response.json();
        
        document.getElementById('loyalty-points').textContent = data.points;
        document.getElementById('loyalty-tier').textContent = data.tier;
        document.getElementById('loyalty-discount').textContent = `${data.discount_percent}%`;

        loadingDiv.classList.add('hidden');
        contentDiv.classList.remove('hidden');

    } catch (error) {
        console.error('Error fetching loyalty info:', error);
        loadingDiv.textContent = 'Erreur lors du chargement des données.';
    }
}


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
