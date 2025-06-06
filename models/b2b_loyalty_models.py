from .base import BaseModel
from database import db
from datetime import datetime, timedelta

class LoyaltyPointTransaction(BaseModel):
    """
    Records each instance of a B2B user earning loyalty points.
    This allows for tracking points and their expiration dates individually.
    """
    __tablename__ = 'loyalty_point_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('b2b_users.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    points_earned = db.Column(db.Integer, nullable=False)
    expiry_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(days=365))

    user = db.relationship('B2BUser', backref=db.backref('loyalty_transactions', lazy='dynamic'))
    order = db.relationship('Order')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'order_id': self.order_id,
            'points_earned': self.points_earned,
            'earned_at': self.created_at.isoformat(),
            'expiry_date': self.expiry_date.isoformat()
        }
