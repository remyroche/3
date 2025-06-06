from .base import db, BaseModel
from .enums import UserRoleEnum, ProfessionalStatusEnum, PartnershipLevel
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from flask_login import UserMixin
import pyotp
import re
import uuid
from flask import current_app

class User(BaseModel, UserMixin):
    """
    Core User model containing common information for all users (B2C, B2B, Admin).
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=True)
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    phone_number = db.Column(db.String(50), nullable=True)
    role = db.Column(db.Enum(UserRoleEnum), nullable=False, default=UserRoleEnum.B2C_CUSTOMER, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False, index=True)

    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    # --- REFERRAL FIELDS ---
    referral_code = db.Column(db.String(50), unique=True, nullable=True, index=True)
    referred_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    referral_credit_balance = db.Column(db.Float, default=0.0, nullable=False)
    
    # --- AUTHENTICATION & SECURITY ---
    reset_token = db.Column(db.String(100), index=True, nullable=True)
    reset_token_expires_at = db.Column(db.DateTime, nullable=True)
    verification_token = db.Column(db.String(100), index=True, nullable=True)
    verification_token_expires_at = db.Column(db.DateTime, nullable=True)
    totp_secret = db.Column(db.String(100), nullable=True)
    is_totp_enabled = db.Column(db.Boolean, default=False, nullable=False)

    # --- GENERIC INFO ---
    preferred_language = db.Column(db.String(5), default='fr')
    newsletter_opt_in = db.Column(db.Boolean, default=False)
    
    # --- RELATIONSHIPS ---
    orders = db.relationship('Order', back_populates='user', lazy='dynamic')
    reviews = db.relationship('Review', back_populates='user', lazy='dynamic')
    cart = db.relationship('Cart', back_populates='user', uselist=False, lazy='joined')
    
    # One-to-one relationship to the B2B-specific profile
    b2b_profile = db.relationship('B2BUser', back_populates='user', uselist=False, cascade="all, delete-orphan")
    
    # Relationship to get the list of users this user has referred
    referrals = db.relationship('User', backref=db.backref('referrer', remote_side='User.id'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password) if self.password_hash else False
    
    @staticmethod
    def validate_password(password):
        if not password or len(password) < 8: return "auth.error.password_too_short"
        if not re.search(r"[A-Z]", password): return "auth.error.password_no_uppercase"
        if not re.search(r"[a-z]", password): return "auth.error.password_no_lowercase"
        if not re.search(r"[0-9]", password): return "auth.error.password_no_digit"
        return None

    def generate_referral_code(self):
        if not self.referral_code:
            self.referral_code = f"TRV-{uuid.uuid4().hex[:8].upper()}"
        return self.referral_code

    def generate_totp_secret(self): 
        self.totp_secret = pyotp.random_base32()
        return self.totp_secret
    
    def get_totp_uri(self, issuer_name=None):
        if not self.totp_secret: self.generate_totp_secret()
        issuer = issuer_name or current_app.config.get('TOTP_ISSUER_NAME', 'Maison Truvra')
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(name=self.email, issuer_name=issuer)
    
    def verify_totp(self, code, for_time=None, window=1): 
        return pyotp.TOTP(self.totp_secret).verify(code, for_time=for_time, window=window) if self.totp_secret else False
    
    def to_dict(self):
        """
        Consolidated method to serialize user data.
        Includes B2B profile information if it exists.
        """
        data = {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "role": self.role.value if self.role else None,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "is_totp_enabled": self.is_totp_enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "preferred_language": self.preferred_language,
            "newsletter_opt_in": self.newsletter_opt_in,
            "referral_code": self.referral_code,
            "referral_credit_balance": self.referral_credit_balance,
        }
        if self.role == UserRoleEnum.B2B_CUSTOMER and self.b2b_profile:
            data.update(self.b2b_profile.to_dict())
        return data

    def __repr__(self):
        return f'<User {self.email}>'


class ProfessionalUser(BaseModel):
    """
    Model containing information specific to Professional (B2B) users.
    """
    __tablename__ = 'b2b_users'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    
    company_name = db.Column(db.String(120), nullable=True)
    siret_number = db.Column(db.String(50), nullable=True, unique=True, index=True)
    vat_number = db.Column(db.String(50), nullable=True, unique=True, index=True)
    contact_name = db.Column(db.String(120))
    address = db.Column(db.Text)
    phone_number = db.Column(db.String(50))
    status = db.Column(db.Enum(ProfessionalStatusEnum), default=ProfessionalStatusEnum.PENDING_REVIEW)
    is_active = db.Column(db.Boolean, nullable=False, default=False)

    # Partnership Program Field
    partnership_level = db.Column(db.Enum(PartnershipLevel), default=PartnershipLevel.BRONZE, nullable=False)
    
    # Restaurant Branding Incentive Field
    is_restaurant_branding_partner = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    user = db.relationship('User', back_populates='b2b_profile')
    invoices = db.relationship('B2BInvoice', back_populates='user', lazy='dynamic')
    
    def to_dict(self):
        """
        Returns a dictionary of B2B-specific fields.
        This is intended to be merged into the main User's to_dict().
        """
        return {
            'b2b_id': self.id,
            'company_name': self.company_name,
            'siret_number': self.siret_number,
            'vat_number': self.vat_number,
            'contact_name': self.contact_name,
            'b2b_status': self.status.value,
            'partnership_level': self.partnership_level.value,
            'is_restaurant_branding_partner': self.is_restaurant_branding_partner
        }


class TokenBlocklist(db.Model):
    """
    Stores revoked JWT tokens.
    """
    __tablename__ = 'token_blocklist'
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

