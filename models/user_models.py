# backend/models/user_models.py
from .base import db
from .enums import UserRoleEnum, ProfessionalStatusEnum, B2BPricingTierEnum
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import pyotp 
import re 
import uuid
from flask import current_app

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=True) 
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    phone_number = db.Column(db.String(50), nullable=True)
    role = db.Column(db.Enum(UserRoleEnum, name="user_role_enum_v3"), nullable=False, default=UserRoleEnum.B2C_CUSTOMER, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False, index=True) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    company_name = db.Column(db.String(120), nullable=True)
    vat_number = db.Column(db.String(50), nullable=True)
    siret_number = db.Column(db.String(50), nullable=True)
    professional_status = db.Column(db.Enum(ProfessionalStatusEnum, name="professional_status_enum_v3"), nullable=True, index=True)
    b2b_tier = db.Column(db.Enum(B2BPricingTierEnum, name="b2b_pricing_tier_enum_v2"), nullable=True, default=B2BPricingTierEnum.STANDARD, index=True)

    referral_code = db.Column(db.String(50), unique=True, nullable=True, index=True) 
    referred_by_code = db.Column(db.String(50), nullable=True, index=True) 
    referral_credit_balance = db.Column(db.Float, default=0.0, nullable=False)
    is_restaurant_branding_partner = db.Column(db.Boolean, default=False, nullable=False)

    reset_token = db.Column(db.String(100), index=True, nullable=True)
    reset_token_expires_at = db.Column(db.DateTime, nullable=True)
    verification_token = db.Column(db.String(100), index=True, nullable=True)
    verification_token_expires_at = db.Column(db.DateTime, nullable=True)
    magic_link_token = db.Column(db.String(100), index=True, nullable=True)
    magic_link_expires_at = db.Column(db.DateTime, nullable=True)
    
    totp_secret = db.Column(db.String(100), nullable=True) 
    is_totp_enabled = db.Column(db.Boolean, default=False, nullable=False)
    simplelogin_user_id = db.Column(db.String(255), unique=True, nullable=True, index=True) 
    
    shipping_address_line1 = db.Column(db.String(255), nullable=True)
    shipping_address_line2 = db.Column(db.String(255), nullable=True)
    shipping_city = db.Column(db.String(100), nullable=True)
    shipping_postal_code = db.Column(db.String(20), nullable=True)
    shipping_country = db.Column(db.String(100), nullable=True)
    shipping_phone = db.Column(db.String(50), nullable=True)

    billing_address_line1 = db.Column(db.String(255), nullable=True)
    billing_address_line2 = db.Column(db.String(255), nullable=True)
    billing_city = db.Column(db.String(100), nullable=True)
    billing_postal_code = db.Column(db.String(20), nullable=True)
    billing_country = db.Column(db.String(100), nullable=True)
    
    company_address_line1 = db.Column(db.String(255), nullable=True)
    company_address_line2 = db.Column(db.String(255), nullable=True)
    company_city = db.Column(db.String(100), nullable=True)
    company_postal_code = db.Column(db.String(20), nullable=True)
    company_country = db.Column(db.String(100), nullable=True)

    currency = db.Column(db.String(3), default='EUR')

    newsletter_b2c_opt_in = db.Column(db.Boolean, default=False)
    newsletter_b2b_opt_in = db.Column(db.Boolean, default=False)
    preferred_language = db.Column(db.String(5), default='fr')

    orders = db.relationship('Order', back_populates='customer', lazy='dynamic')
    reviews = db.relationship('Review', back_populates='user', lazy='dynamic')
    cart = db.relationship('Cart', back_populates='user', uselist=False, lazy='joined') 
    professional_documents = db.relationship('ProfessionalDocument', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")
    b2b_invoices = db.relationship('Invoice', foreign_keys='Invoice.b2b_user_id', back_populates='b2b_customer', lazy='dynamic')
    audit_logs_initiated = db.relationship('AuditLog', foreign_keys='AuditLog.user_id', back_populates='acting_user', lazy='dynamic')
    quote_requests = db.relationship('QuoteRequest', back_populates='user', lazy='dynamic')

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password) if self.password_hash else False
    
    @staticmethod
    def validate_password(password):
        if not password or len(password) < 8: return "auth.error.password_too_short"
        if not re.search(r"[A-Z]", password): return "auth.error.password_no_uppercase"
        if not re.search(r"[a-z]", password): return "auth.error.password_no_lowercase"
        if not re.search(r"[0-9]", password): return "auth.error.password_no_digit"
        return None

    def generate_referral_code(self):
        if not self.referral_code:
            for _ in range(5): 
                potential_code = f"TRV-{'U' if not self.id else self.id}-{uuid.uuid4().hex[:6].upper()}"
                if not User.query.filter_by(referral_code=potential_code).first():
                    self.referral_code = potential_code
                    return self.referral_code
            self.referral_code = f"TRV-{uuid.uuid4().hex[:10].upper()}"
        return self.referral_code

    def generate_totp_secret(self): self.totp_secret = pyotp.random_base32(); return self.totp_secret
    
    def get_totp_uri(self, issuer_name=None):
        if not self.totp_secret: self.generate_totp_secret() 
        issuer = issuer_name or current_app.config.get('TOTP_ISSUER_NAME', 'Maison Truvra')
        if not self.totp_secret: raise ValueError("TOTP secret missing.")
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(name=self.email, issuer_name=issuer)
    
    def verify_totp(self, code, for_time=None, window=1): return pyotp.TOTP(self.totp_secret).verify(code, for_time=for_time, window=window) if self.totp_secret else False
    
    def to_dict(self):
        return {
            "id": self.id, "email": self.email, "first_name": self.first_name, 
            "last_name": self.last_name, "role": self.role.value if self.role else None, 
            "is_active": self.is_active, "is_verified": self.is_verified, 
            "company_name": self.company_name, "vat_number": self.vat_number, "siret_number": self.siret_number,
            "professional_status": self.professional_status.value if self.professional_status else None, 
            "b2b_tier": self.b2b_tier.value if self.b2b_tier else None,
            "is_totp_enabled": self.is_totp_enabled, 
            "is_admin": self.role == UserRoleEnum.ADMIN,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "shipping_address_line1": self.shipping_address_line1,
            "currency": self.currency,
            "newsletter_b2c_opt_in": self.newsletter_b2c_opt_in,
            "newsletter_b2b_opt_in": self.newsletter_b2b_opt_in,
            "preferred_language": self.preferred_language,
            "referral_code": self.referral_code,
            "referred_by_code": self.referred_by_code,
            "referral_credit_balance": self.referral_credit_balance,
            "is_restaurant_branding_partner": self.is_restaurant_branding_partner
        }
    def __repr__(self): return f'<User {self.email}>'

class ProfessionalDocument(db.Model):
    __tablename__ = 'professional_documents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    document_type = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=False) 
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.Enum(ProfessionalStatusEnum, name="prof_doc_status_enum_v2"), default=ProfessionalStatusEnum.PENDING_REVIEW, index=True)
    reviewed_by_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) 
    reviewed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    user = db.relationship('User', back_populates='professional_documents')
    reviewed_by_admin = db.relationship('User', foreign_keys=[reviewed_by_admin_id])

class TokenBlocklist(db.Model):
    __tablename__ = 'token_blocklist'
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False, index=True) 
    def __repr__(self): return f"<TokenBlocklist {self.jti}>"

class ReferralAwardLog(db.Model):
    __tablename__ = 'referral_award_logs'
    id = db.Column(db.Integer, primary_key=True)
    referrer_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    referred_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    award_type = db.Column(db.String(100), nullable=False)
    credit_amount_awarded = db.Column(db.Float, nullable=False)
    related_order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='SET NULL'), nullable=True)
    awarded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    referrer = db.relationship('User', foreign_keys=[referrer_user_id])
    referred = db.relationship('User', foreign_keys=[referred_user_id])
    __table_args__ = (db.UniqueConstraint('referrer_user_id', 'referred_user_id', 'award_type', name='uq_referral_award'),)
