# B2B service
# backend/services/loyalty_service.py
from flask import current_app
from sqlalchemy import func
from datetime import datetime, timezone

from .. import db
from ..models import User, Order, ReferralAwardLog, OrderStatusEnum, UserRoleEnum, ProfessionalStatusEnum

class LoyaltyService:
    """
    Handles the business logic for the B2B Loyalty and Referral Program.
    """

    def __init__(self):
        self.audit_logger = current_app.audit_log_service
        self.config = current_app.config
        
        # Define referral award rules. Should be moved to config for flexibility.
        self.REFERRAL_RULES = {
            "restaurant_branding": {
                "award_type": "restaurant_branding_signup",
                "credit": 500.00
            },
            "spend_thresholds": [
                {"threshold": 5000, "award_type": "spend_5k", "credit": 250.00},
                {"threshold": 10000, "award_type": "spend_10k", "credit": 500.00},
                {"threshold": 20000, "award_type": "spend_20k", "credit": 1000.00},
            ]
        }

    def _has_award_been_granted(self, referrer_id, referred_id, award_type):
        """Checks if a specific award has already been granted for a referral pair."""
        return db.session.query(ReferralAwardLog.id).filter_by(
            referrer_user_id=referrer_id,
            referred_user_id=referred_id,
            award_type=award_type
        ).first() is not None

    def process_order_completion_for_referral(self, completed_order):
        """
        To be called when a B2B order is marked as completed/paid.
        Checks the referred user's total spend and awards credit to the referrer if thresholds are met.
        """
        if not completed_order or not completed_order.is_b2b_order:
            return

        referred_user = completed_order.customer
        if not referred_user or not referred_user.referred_by_code:
            return # This user was not referred.

        referrer = User.query.filter_by(referral_code=referred_user.referred_by_code).first()
        if not referrer:
            self.audit_logger.log_action(action='process_referral_award_fail', details=f"Referrer with code {referred_user.referred_by_code} not found for referred user {referred_user.id}.", status='failure')
            return
            
        # Calculate total spend for the referred user
        total_spend_result = db.session.query(func.sum(Order.total_amount)).filter(
            Order.user_id == referred_user.id,
            Order.is_b2b_order == True,
            Order.status.in_([OrderStatusEnum.COMPLETED, OrderStatusEnum.DELIVERED, OrderStatusEnum.SHIPPED]) # Confirmed spend states
        ).scalar()
        total_spend = total_spend_result or 0.0

        # Check spend thresholds
        for rule in sorted(self.REFERRAL_RULES['spend_thresholds'], key=lambda x: x['threshold']):
            if total_spend >= rule['threshold']:
                if not self._has_award_been_granted(referrer.id, referred_user.id, rule['award_type']):
                    # Grant the award
                    referrer.referral_credit_balance = (referrer.referral_credit_balance or 0.0) + rule['credit']
                    
                    award_log = ReferralAwardLog(
                        referrer_user_id=referrer.id,
                        referred_user_id=referred_user.id,
                        award_type=rule['award_type'],
                        credit_amount_awarded=rule['credit'],
                        related_order_id=completed_order.id # Link to the order that triggered the threshold
                    )
                    db.session.add(referrer)
                    db.session.add(award_log)
                    
                    self.audit_logger.log_action(user_id=referrer.id, action='referral_credit_awarded', target_type='user', target_id=referred_user.id, details=f"Awarded {rule['credit']} credit for referred user reaching {rule['threshold']} spend threshold. Triggered by order {completed_order.id}.", status='success')
                    # Don't break, so if they cross multiple thresholds with one big order, they get all applicable rewards
            else:
                # Since thresholds are sorted, we can stop checking if one is not met.
                break 

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.audit_logger.log_action(action='process_referral_award_db_error', details=str(e), status='failure')
            current_app.logger.error(f"Error committing referral award for referrer {referrer.id} / referred {referred_user.id}: {e}", exc_info=True)


    def process_branding_partner_update(self, b2b_user):
        """
        To be called when a B2B user's `is_restaurant_branding_partner` is set to True.
        Awards the one-time branding signup credit to the referrer.
        """
        if not b2b_user or not b2b_user.is_restaurant_branding_partner or not b2b_user.referred_by_code:
            return

        referrer = User.query.filter_by(referral_code=b2b_user.referred_by_code).first()
        if not referrer:
            self.audit_logger.log_action(action='process_branding_award_fail', details=f"Referrer with code {b2b_user.referred_by_code} not found for user {b2b_user.id}.", status='failure')
            return

        rule = self.REFERRAL_RULES['restaurant_branding']
        if not self._has_award_been_granted(referrer.id, b2b_user.id, rule['award_type']):
            referrer.referral_credit_balance = (referrer.referral_credit_balance or 0.0) + rule['credit']
            
            award_log = ReferralAwardLog(
                referrer_user_id=referrer.id,
                referred_user_id=b2b_user.id,
                award_type=rule['award_type'],
                credit_amount_awarded=rule['credit']
            )
            db.session.add(referrer)
            db.session.add(award_log)
            
            try:
                db.session.commit()
                self.audit_logger.log_action(user_id=referrer.id, action='referral_credit_awarded_branding', target_type='user', target_id=b2b_user.id, details=f"Awarded {rule['credit']} credit for referred user '{b2b_user.email}' joining branding incentive.", status='success')
            except Exception as e:
                db.session.rollback()
                self.audit_logger.log_action(action='process_branding_award_db_error', details=str(e), status='failure')
                current_app.logger.error(f"Error committing branding referral award for referrer {referrer.id} / referred {b2b_user.id}: {e}", exc_info=True)

