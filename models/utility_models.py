# backend/models/utility_models.py
from .base import db
from .enums import AuditLogStatusEnum, AssetTypeEnum, NewsletterTypeEnum
from datetime import datetime, timezone

class NewsletterSubscription(BaseModel):
    __tablename__ = 'newsletter_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    user_type = db.Column(db.String(50)) # 'b2c' or 'b2b'

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'is_active': self.is_active,
            'user_type': self.user_type
        }

class SiteConfiguration(BaseModel):
    """
    Model for storing site-wide configuration settings.
    """
    __tablename__ = 'site_configuration'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value
        }


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False) 
    comment = db.Column(db.Text, nullable=True)
    review_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    is_approved = db.Column(db.Boolean, default=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    product = db.relationship('Product', back_populates='reviews')
    user = db.relationship('User', back_populates='reviews')
    __table_args__ = ( db.CheckConstraint('rating >= 1 AND rating <= 5', name='ck_review_rating_v2'), 
                       db.UniqueConstraint('product_id', 'user_id', name='uq_user_product_review_v2') )

class Cart(db.Model):
    __tablename__ = 'carts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, index=True, nullable=True) 
    session_id = db.Column(db.String(255), unique=True, index=True, nullable=True) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', back_populates='cart')
    items = db.relationship('CartItem', back_populates='cart', lazy='dynamic', cascade="all, delete-orphan")

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id', ondelete='CASCADE'), index=True, nullable=True) 
    quantity = db.Column(db.Integer, nullable=False)
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    cart = db.relationship('Cart', back_populates='items')
    product = db.relationship('Product', back_populates='cart_items')
    variant = db.relationship('ProductWeightOption', back_populates='cart_items')

class NewsletterSubscription(db.Model):
    __tablename__ = 'newsletter_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    subscribed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True, index=True)
    source = db.Column(db.String(100), nullable=True)
    consent = db.Column(db.String(10), nullable=False, default='Y')
    language_code = db.Column(db.String(5), nullable=True)
    newsletter_type = db.Column(db.Enum(NewsletterTypeEnum, name="newsletter_type_enum_v1"), default=NewsletterTypeEnum.GENERAL, nullable=False)

class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class GeneratedAsset(db.Model):
    __tablename__ = 'generated_assets'
    id = db.Column(db.Integer, primary_key=True)
    asset_type = db.Column(db.Enum(AssetTypeEnum, name="asset_type_enum_v2"), nullable=False, index=True)
    related_item_uid = db.Column(db.String(100), db.ForeignKey('serialized_inventory_items.item_uid', ondelete='SET NULL'), index=True, nullable=True) 
    related_product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), index=True, nullable=True) 
    file_path = db.Column(db.String(255), nullable=False, unique=True) 
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    inventory_item_asset_owner = db.relationship('SerializedInventoryItem', back_populates='generated_assets', foreign_keys=[related_item_uid])
    product_asset_owner = db.relationship('Product', back_populates='generated_assets', foreign_keys=[related_product_id])

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True, nullable=True) 
    action = db.Column(db.String(255), nullable=False, index=True)
    target_type = db.Column(db.String(50), index=True, nullable=True) 
    target_id = db.Column(db.Integer, index=True, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.Enum(AuditLogStatusEnum, name="audit_log_status_enum_v2"), default=AuditLogStatusEnum.SUCCESS, index=True)
    acting_user = db.relationship('User', foreign_keys=[user_id], back_populates='audit_logs_initiated')
