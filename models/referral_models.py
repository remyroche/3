from .base import db, BaseModel
from datetime import datetime, timezone

class ReferralAwardLog(BaseModel):
    """
    Logs when a referral credit is awarded to prevent duplicate payouts.
    """
    __tablename__ = 'referral_award_logs'
    id = db.Column(db.Integer, primary_key=True)
    
    # The user who gets the credit
    referrer_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # The user whose actions triggered the award
    referred_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # The reason for the award (e.g., 'BRANDING_INCENTIVE', 'SPEND_5K', 'SPEND_10K')
    award_type = db.Column(db.String(100), nullable=False)
    
    credit_amount = db.Column(db.Float, nullable=False)
    
    awarded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    referrer = db.relationship('User', foreign_keys=[referrer_user_id])
    referred = db.relationship('User', foreign_keys=[referred_user_id])

    __table_args__ = (
        db.UniqueConstraint('referrer_user_id', 'referred_user_id', 'award_type', name='uq_referral_award'),
    )
