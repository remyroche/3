from models import db, User, Order, B2BUser
from models.enums import PartnershipLevel
from sqlalchemy import func
from datetime import datetime, timedelta

# Define the partnership tiers and their rules
PARTNERSHIP_TIERS = {
    # Spend threshold and discount percentage
    PartnershipLevel.AMBASSADOR: {'spend': float('inf'), 'discount': 30},
    PartnershipLevel.DIAMOND: {'spend': 25000, 'discount': 10},
    PartnershipLevel.PLATINUM: {'spend': 15000, 'discount': 8},
    PartnershipLevel.GOLD: {'spend': 5000, 'discount': 5},
    PartnershipLevel.SILVER: {'spend': 1000, 'discount': 2},
    PartnershipLevel.BRONZE: {'spend': 0, 'discount': 0},
}

def get_annual_spend(user_id):
    """
    Calculates a user's total spending on completed orders over the last 365 days.
    """
    one_year_ago = datetime.utcnow() - timedelta(days=365)
    total_spend = db.session.query(
        func.sum(Order.total_amount)
    ).filter(
        Order.user_id == user_id,
        Order.status == 'COMPLETED', # Only count completed orders
        Order.created_at >= one_year_ago
    ).scalar() or 0
    return total_spend

def get_level_from_spend(spend, is_ambassador=False):
    """Determines a partnership level based on spend and ambassador status."""
    if is_ambassador:
        return PartnershipLevel.AMBASSADOR
    
    for level, rules in PARTNERSHIP_TIERS.items():
        if spend >= rules['spend']:
            return level
    return PartnershipLevel.BRONZE

def update_user_partnership_level(user_id):
    """
    Recalculates and updates a user's partnership level.
    Returns the user's new level and their annual spend.
    """
    user = User.query.get(user_id)
    if not user or not user.b2b_profile:
        return None, 0

    annual_spend = get_annual_spend(user_id)
    is_ambassador = user.b2b_profile.is_restaurant_branding_partner
    
    new_level = get_level_from_spend(annual_spend, is_ambassador)
    
    user.b2b_profile.partnership_level = new_level
    db.session.commit()
    
    return new_level, annual_spend

def get_discount_for_user(user_id):
    """Gets the discount percentage for a user based on their current level."""
    user = User.query.get(user_id)
    if user and user.b2b_profile:
        level = user.b2b_profile.partnership_level
        return PARTNERSHIP_TIERS.get(level, {}).get('discount', 0)
    return 0

def get_user_dashboard_info(user_id):
    """
    Gathers all necessary info for the B2B dashboard.
    """
    user = User.query.get(user_id)
    if not user or not user.b2b_profile:
        return None
        
    level, annual_spend = update_user_partnership_level(user_id) # Recalculate on every dashboard view
    
    return {
        "partnership_level": level.value,
        "annual_spend": annual_spend,
        "discount_percent": PARTNERSHIP_TIERS[level]['discount'],
        "referral_code": user.referral_code,
        "referral_credit_balance": user.referral_credit_balance
    }
