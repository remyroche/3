from models import db, User, Order, B2BUser
from models.referral_models import ReferralAwardLog
from sqlalchemy import func
from datetime import datetime, timedelta

# Define referral award rules
REFERRAL_SPEND_TIERS = {
    'SPEND_5K': {'threshold': 5000, 'credit': 250},
    'SPEND_10K': {'threshold': 10000, 'credit': 500},
    'SPEND_20K': {'threshold': 20000, 'credit': 1000},
}
BRANDING_INCENTIVE_CREDIT = 500

def award_credit(user_id, amount, referred_user_id, award_type):
    """
    Awards credit to a user and logs the transaction to prevent duplicates.
    """
    # Check if this award has already been given
    existing_log = ReferralAwardLog.query.filter_by(
        referrer_user_id=user_id,
        referred_user_id=referred_user_id,
        award_type=award_type
    ).first()

    if existing_log:
        return False # Award already given

    referrer = User.query.get(user_id)
    if referrer:
        referrer.referral_credit_balance += amount
        
        new_log = ReferralAwardLog(
            referrer_user_id=user_id,
            referred_user_id=referred_user_id,
            award_type=award_type,
            credit_amount=amount
        )
        db.session.add(new_log)
        return True
    return False

def award_branding_referral_credit(referred_b2b_user_id):
    """
    Awards credit for the Restaurant Branding Incentive.
    """
    referred_user = B2BUser.query.get(referred_b2b_user_id)
    if not referred_user or not referred_user.user.referred_by_id:
        return False
    
    referrer_id = referred_user.user.referred_by_id
    award_credit(
        referrer_id,
        BRANDING_INCENTIVE_CREDIT,
        referred_user.user_id,
        'BRANDING_INCENTIVE'
    )
    db.session.commit()
    return True

def check_and_award_purchase_referrals():
    """
    Main function to check all referred users' spending and award credits.
    This should be run periodically by a scheduled task or admin trigger.
    """
    # Find all users who were referred by someone
    referred_users = User.query.filter(User.referred_by_id.isnot(None)).all()
    
    for referred_user in referred_users:
        # Calculate total spend in the last 365 days
        one_year_ago = datetime.utcnow() - timedelta(days=365)
        total_spend = db.session.query(
            func.sum(Order.total_amount)
        ).filter(
            Order.user_id == referred_user.id,
            Order.created_at >= one_year_ago
        ).scalar() or 0

        referrer_id = referred_user.referred_by_id
        
        # Check each spending tier
        for tier_name, tier_info in REFERRAL_SPEND_TIERS.items():
            if total_spend >= tier_info['threshold']:
                award_credit(
                    referrer_id,
                    tier_info['credit'],
                    referred_user.id,
                    tier_name
                )
    
    db.session.commit()
    return {'status': 'completed', 'checked_users': len(referred_users)}

