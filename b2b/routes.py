# backend/models.py
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
import enum
import pyotp
import re
from flask import current_app

# backend/b2b/routes.py
from flask import Blueprint, request, jsonify, current_app, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
import uuid
import json # For parsing cart_items from form data

from .. import db
from ..models import (User, Product, Category, ProductWeightOption, ProductB2BTierPrice,
                    Order, OrderItem, QuoteRequest, QuoteRequestItem, GeneratedAsset,
                    UserRoleEnum, ProfessionalStatusEnum, B2BPricingTierEnum,
                    OrderStatusEnum, QuoteRequestStatusEnum, AssetTypeEnum, ProductTypeEnum)
from ..utils import allowed_file, get_file_extension, sanitize_input # Add other utils as needed
from ..services.email_service import EmailService # Assuming you have an email service

b2b_bp = Blueprint('b2b_bp', __name__, url_prefix='/api/b2b')

db = SQLAlchemy()

# --- Enum Definitions ---
class UserRoleEnum(enum.Enum):
    B2C_CUSTOMER = "b2c_customer"
    B2B_PROFESSIONAL = "b2b_professional"
    ADMIN = "admin"
    STAFF = "staff"

class ProfessionalStatusEnum(enum.Enum):
    PENDING_REVIEW = "pending_review"
    PENDING_DOCUMENTS = "pending_documents"
    APPROVED = "approved"
    REJECTED = "rejected"
    ON_HOLD = "on_hold"

class ProductTypeEnum(enum.Enum):
    SIMPLE = "simple"
    VARIABLE_WEIGHT = "variable_weight"

class PreservationTypeEnum(enum.Enum):
    FRESH = "frais"
    PRESERVED_CANNED = "conserve"
    DRY = "sec"
    FROZEN = "surgele"
    VACUUM_PACKED = "sous_vide"
    OTHER = "autre"
    NOT_SPECIFIED = "non_specifie"

class SerializedInventoryItemStatusEnum(enum.Enum):
    AVAILABLE = "available"
    ALLOCATED = "allocated"
    SOLD = "sold"
    DAMAGED = "damaged"
    RETURNED = "returned"
    RECALLED = "recalled"
    RESERVED_INTERNAL = "reserved_internal"
    MISSING = "missing"

class StockMovementTypeEnum(enum.Enum):
    INITIAL_STOCK = "initial_stock"
    SALE = "sale"
    RETURN = "return"
    ADJUSTMENT_IN = "adjustment_in"
    ADJUSTMENT_OUT = "adjustment_out"
    DAMAGE = "damage"
    PRODUCTION = "production"
    RECALL = "recall"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    RECEIVE_SERIALIZED = "receive_serialized"
    IMPORT_CSV_NEW = "import_csv_new"

class OrderStatusEnum(enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    PENDING_PO_REVIEW = "pending_po_review"
    QUOTE_REQUESTED = "quote_requested"
    QUOTE_SENT = "quote_sent"
    ORDER_PENDING_APPROVAL = "order_pending_approval"
    PAID = "paid"
    PROCESSING = "processing"
    AWAITING_SHIPMENT = "awaiting_shipment"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    ON_HOLD = "on_hold"
    FAILED = "failed"

class InvoiceStatusEnum(enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    SENT = "sent"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    VOIDED = "voided"

class AuditLogStatusEnum(enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    INFO = "info"

class AssetTypeEnum(enum.Enum):
    QR_CODE = "qr_code"
    PASSPORT_HTML = "passport_html"
    LABEL_PDF = "label_pdf"
    PRODUCT_IMAGE = "product_image"
    CATEGORY_IMAGE = "category_image"
    PROFESSIONAL_DOCUMENT = "professional_document"
    PURCHASE_ORDER_FILE = "purchase_order_file"

class B2BPricingTierEnum(enum.Enum):
    STANDARD = "standard"
    GOLD = "gold"
    PLATINUM = "platinum"

class QuoteRequestStatusEnum(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT_TO_CLIENT = "sent_to_client"
    ACCEPTED_BY_CLIENT = "accepted_by_client"
    CONVERTED_TO_ORDER = "converted_to_order"
    DECLINED_BY_CLIENT = "declined_by_client"
    EXPIRED = "expired"


# --- Model Definitions ---

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=True) # Allow null for SSO-only users initially
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    role = db.Column(db.Enum(UserRoleEnum, name="user_role_enum_v3"), nullable=False, default=UserRoleEnum.B2C_CUSTOMER, index=True) # Updated enum name
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company_name = db.Column(db.String(120), nullable=True)
    vat_number = db.Column(db.String(50), nullable=True)
    siret_number = db.Column(db.String(50), nullable=True)
    professional_status = db.Column(db.Enum(ProfessionalStatusEnum, name="professional_status_enum_v3"), nullable=True, index=True) # Updated enum name
    b2b_tier = db.Column(db.Enum(B2BPricingTierEnum, name="b2b_pricing_tier_enum_v2"), nullable=True, default=B2BPricingTierEnum.STANDARD, index=True)

    reset_token = db.Column(db.String(100), index=True, nullable=True)
    reset_token_expires_at = db.Column(db.DateTime, nullable=True)
    verification_token = db.Column(db.String(100), index=True, nullable=True)
    verification_token_expires_at = db.Column(db.DateTime, nullable=True)
    magic_link_token = db.Column(db.String(100), index=True, nullable=True)
    magic_link_expires_at = db.Column(db.DateTime, nullable=True)
    totp_secret = db.Column(db.String(100), nullable=True)
    is_totp_enabled = db.Column(db.Boolean, default=False, nullable=False)
    simplelogin_user_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    
    # B2B Address fields (can be different from general user if needed, or use a separate Address model)
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
    
    currency = db.Column(db.String(3), default='EUR') # Default currency for B2B user


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

    def generate_totp_secret(self): self.totp_secret = pyotp.random_base32(); return self.totp_secret
    def get_totp_uri(self, issuer_name=None):
        if not self.totp_secret: self.generate_totp_secret()
        issuer = issuer_name or current_app.config.get('TOTP_ISSUER_NAME', 'Maison Truvra')
        if not self.totp_secret: raise ValueError("TOTP secret missing.")
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(name=self.email, issuer_name=issuer)
    def verify_totp(self, code, for_time=None, window=1): return pyotp.TOTP(self.totp_secret).verify(code, for_time=for_time, window=window) if self.totp_secret else False

    def to_dict(self): # Ensure this is comprehensive for admin needs too
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
            # Add address fields if needed directly in user object for admin display
            "shipping_address_line1": self.shipping_address_line1,
            "currency": self.currency
        }
    def __repr__(self): return f'<User {self.email}>'


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    category_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), index=True, nullable=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    products = db.relationship('Product', back_populates='category', lazy='dynamic')
    children = db.relationship('Category', back_populates='parent_category', remote_side='Category.id', lazy='dynamic', cascade="all, delete-orphan")
    parent_category = db.relationship('Category', back_populates='children', remote_side=[id])
    localizations = db.relationship('CategoryLocalization', back_populates='category', lazy='dynamic', cascade="all, delete-orphan")

    def to_dict(self): 
        return {
            "id": self.id, "name": self.name, "description": self.description, 
            "image_url": self.image_url, "category_code": self.category_code, 
            "parent_id": self.parent_id, "slug": self.slug, "is_active": self.is_active,
            "product_count": self.products.filter_by(is_active=True).count()
        }
    def __repr__(self): return f'<Category {self.name}>'


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True) 
    description = db.Column(db.Text, nullable=True) 
    long_description = db.Column(db.Text, nullable=True) 
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False, index=True)
    product_code = db.Column(db.String(100), unique=True, nullable=False, index=True) 
    brand = db.Column(db.String(100), index=True, nullable=True)
    type = db.Column(db.Enum(ProductTypeEnum, name="product_type_enum_v2"), nullable=False, default=ProductTypeEnum.SIMPLE, index=True) # Updated enum name
    base_price = db.Column(db.Float, nullable=True) # B2C retail price for simple, or fallback for variants
    currency = db.Column(db.String(10), default='EUR')
    main_image_url = db.Column(db.String(255), nullable=True)
    unit_of_measure = db.Column(db.String(50), nullable=True) 
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_featured = db.Column(db.Boolean, default=False, index=True)
    meta_title = db.Column(db.String(255), nullable=True) 
    meta_description = db.Column(db.Text, nullable=True) 
    slug = db.Column(db.String(170), unique=True, nullable=False, index=True)
    preservation_type = db.Column(db.Enum(PreservationTypeEnum, name="preservation_type_enum_v2"), nullable=True, default=PreservationTypeEnum.NOT_SPECIFIED) # Updated enum name
    notes_internal = db.Column(db.Text, nullable=True) 
    supplier_info = db.Column(db.String(255), nullable=True) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    category = db.relationship('Category', back_populates='products')
    images = db.relationship('ProductImage', back_populates='product', lazy='dynamic', cascade="all, delete-orphan")
    weight_options = db.relationship('ProductWeightOption', back_populates='product', lazy='dynamic', cascade="all, delete-orphan")
    serialized_items = db.relationship('SerializedInventoryItem', back_populates='product', lazy='dynamic')
    stock_movements = db.relationship('StockMovement', back_populates='product', lazy='dynamic')
    order_items = db.relationship('OrderItem', back_populates='product', lazy='dynamic')
    reviews = db.relationship('Review', back_populates='product', lazy='dynamic')
    cart_items = db.relationship('CartItem', back_populates='product', lazy='dynamic')
    localizations = db.relationship('ProductLocalization', back_populates='product', lazy='dynamic', cascade="all, delete-orphan")
    generated_assets = db.relationship('GeneratedAsset', foreign_keys='GeneratedAsset.related_product_id', back_populates='product_asset_owner', lazy='dynamic')
    b2b_tier_prices = db.relationship('ProductB2BTierPrice', back_populates='product', lazy='dynamic', cascade="all, delete-orphan")

    @property
    def aggregate_stock_quantity(self):
        if self.type == ProductTypeEnum.VARIABLE_WEIGHT:
            total_variant_stock = db.session.query(
                db.func.sum(ProductWeightOption.aggregate_stock_quantity)
            ).filter(
                ProductWeightOption.product_id == self.id,
                ProductWeightOption.is_active == True
            ).scalar()
            return total_variant_stock or 0
        elif self.type == ProductTypeEnum.SIMPLE:
            simple_serialized_stock = db.session.query(
                db.func.count(SerializedInventoryItem.id)
            ).filter(
                SerializedInventoryItem.product_id == self.id,
                SerializedInventoryItem.variant_id == None,
                SerializedInventoryItem.status == SerializedInventoryItemStatusEnum.AVAILABLE
            ).scalar()
            return simple_serialized_stock or 0
        return 0
        
    def to_dict(self, lang_code='fr'):
        loc = self.localizations.filter_by(lang_code=lang_code).first()
        name_display = self.name 
        description_display = self.description
        # ... (rest of your existing to_dict localization logic for other fields) ...
        loc_fr_specific = self.localizations.filter_by(lang_code='fr').first()
        loc_en_specific = self.localizations.filter_by(lang_code='en').first()

        return {
            "id": self.id, "name": name_display,
            "name_fr": loc_fr_specific.name_fr if loc_fr_specific and loc_fr_specific.name_fr else self.name,
            "name_en": loc_en_specific.name_en if loc_en_specific and loc_en_specific.name_en else None,
            "product_code": self.product_code, "slug": self.slug, 
            "type": self.type.value if self.type else None, 
            "base_price": self.base_price, "currency": self.currency,
            "is_active": self.is_active, "is_featured": self.is_featured, 
            "category_id": self.category_id, 
            "category_name": self.category.name if self.category else None,
            "category_code": self.category.category_code if self.category else None,
            "main_image_url": self.main_image_url,
            "unit_of_measure": self.unit_of_measure, "brand": self.brand,
            "description": description_display,
            "description_fr": loc_fr_specific.description_fr if loc_fr_specific and loc_fr_specific.description_fr else self.description,
            "description_en": loc_en_specific.description_en if loc_en_specific and loc_en_specific.description_en else None,
            # ... (include all other relevant fields for admin product forms and public display) ...
            "aggregate_stock_quantity": self.aggregate_stock_quantity
        }
    def __repr__(self): return f'<Product {self.name}>'


class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    image_url = db.Column(db.String(255), nullable=False) 
    alt_text = db.Column(db.String(255), nullable=True)
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    product = db.relationship('Product', back_populates='images')

class ProductWeightOption(db.Model):
    __tablename__ = 'product_weight_options'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    weight_grams = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False) # B2C retail price for this option
    sku_suffix = db.Column(db.String(50), nullable=False) 
    aggregate_stock_quantity = db.Column(db.Integer, default=0, nullable=False) 
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    product = db.relationship('Product', back_populates='weight_options')
    serialized_items = db.relationship('SerializedInventoryItem', back_populates='variant', lazy='dynamic') # Updated back_populates
    stock_movements = db.relationship('StockMovement', back_populates='variant', lazy='dynamic') # Updated back_populates
    order_items = db.relationship('OrderItem', back_populates='variant', lazy='dynamic') # Updated back_populates
    cart_items = db.relationship('CartItem', back_populates='variant', lazy='dynamic') # Updated back_populates
    b2b_tier_prices_variant = db.relationship('ProductB2BTierPrice', back_populates='variant', lazy='dynamic', cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint('product_id', 'weight_grams', name='uq_product_weight_v2'),
                      db.UniqueConstraint('product_id', 'sku_suffix', name='uq_product_sku_suffix_v2'))


class SerializedInventoryItem(db.Model):
    __tablename__ = 'serialized_inventory_items'
    id = db.Column(db.Integer, primary_key=True)
    item_uid = db.Column(db.String(100), unique=True, nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id', ondelete='SET NULL'), index=True, nullable=True)
    batch_number = db.Column(db.String(100), index=True, nullable=True)
    production_date = db.Column(db.DateTime, nullable=True)
    expiry_date = db.Column(db.DateTime, index=True, nullable=True)
    actual_weight_grams = db.Column(db.Float, nullable=True) 
    cost_price = db.Column(db.Float, nullable=True)
    purchase_price = db.Column(db.Float, nullable=True) # Deprecated or ensure clarity with cost_price
    status = db.Column(db.Enum(SerializedInventoryItemStatusEnum, name="sii_status_enum_v2"), nullable=False, default=SerializedInventoryItemStatusEnum.AVAILABLE, index=True) # Updated enum name
    qr_code_url = db.Column(db.String(255), nullable=True) 
    passport_url = db.Column(db.String(255), nullable=True) 
    label_url = db.Column(db.String(255), nullable=True) 
    notes = db.Column(db.Text, nullable=True)
    supplier_id = db.Column(db.Integer, nullable=True) # Potentially FK to a Supplier model
    received_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sold_at = db.Column(db.DateTime, nullable=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id', ondelete='SET NULL'), unique=True, index=True, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    product = db.relationship('Product', back_populates='serialized_items')
    variant = db.relationship('ProductWeightOption', back_populates='serialized_items')
    stock_movements = db.relationship('StockMovement', back_populates='serialized_item', lazy='dynamic', cascade="all, delete-orphan")
    generated_assets = db.relationship('GeneratedAsset', primaryjoin="SerializedInventoryItem.item_uid == GeneratedAsset.related_item_uid", foreign_keys='GeneratedAsset.related_item_uid', back_populates='inventory_item_asset_owner', lazy='dynamic', cascade="all, delete-orphan")
    order_item_link = db.relationship('OrderItem', back_populates='sold_serialized_item', foreign_keys=[order_item_id]) # Explicit name for this side

    def to_dict(self): return {"id": self.id, "item_uid": self.item_uid, "product_id": self.product_id, "variant_id": self.variant_id, "batch_number": self.batch_number, "production_date": self.production_date.isoformat() if self.production_date else None, "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None, "status": self.status.value if self.status else None, "notes": self.notes, "product_name": self.product.name if self.product else None,  "variant_sku_suffix": self.variant.sku_suffix if self.variant else None}


class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id', ondelete='SET NULL'), index=True, nullable=True) 
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id', ondelete='SET NULL'), index=True, nullable=True) 
    movement_type = db.Column(db.Enum(StockMovementTypeEnum, name="stock_movement_type_enum_v2"), nullable=False, index=True) # Updated enum name
    quantity_change = db.Column(db.Integer, nullable=True) # For aggregated stock
    weight_change_grams = db.Column(db.Float, nullable=True) # For variable weight aggregated stock
    reason = db.Column(db.Text, nullable=True) 
    related_order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='SET NULL'), index=True, nullable=True) 
    related_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True, nullable=True) # Admin or user causing change
    movement_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    notes = db.Column(db.Text, nullable=True)
    
    product = db.relationship('Product', back_populates='stock_movements')
    variant = db.relationship('ProductWeightOption', back_populates='stock_movements')
    serialized_item = db.relationship('SerializedInventoryItem', back_populates='stock_movements')
    related_order = db.relationship('Order', back_populates='stock_movements') # New backref for order

    def to_dict(self): return {"id": self.id, "product_id": self.product_id, "variant_id": self.variant_id, "serialized_item_id": self.serialized_item_id, "movement_type": self.movement_type.value if self.movement_type else None, "quantity_change": self.quantity_change, "weight_change_grams": self.weight_change_grams, "reason": self.reason, "movement_date": self.movement_date.isoformat(), "notes": self.notes}


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.Enum(OrderStatusEnum, name="order_status_enum_v3"), nullable=False, default=OrderStatusEnum.PENDING_PAYMENT, index=True) # Updated enum name
    total_amount = db.Column(db.Float, nullable=False) # For B2B this might be HT, for B2C TTC
    currency = db.Column(db.String(10), default='EUR')
    
    # Shipping Address snapshot at time of order
    shipping_address_line1 = db.Column(db.String(255), nullable=True)
    shipping_address_line2 = db.Column(db.String(255), nullable=True)
    shipping_city = db.Column(db.String(100), nullable=True)
    shipping_postal_code = db.Column(db.String(20), nullable=True)
    shipping_country = db.Column(db.String(100), nullable=True)
    shipping_phone_snapshot = db.Column(db.String(50), nullable=True)


    # Billing Address snapshot
    billing_address_line1 = db.Column(db.String(255), nullable=True)
    billing_address_line2 = db.Column(db.String(255), nullable=True)
    billing_city = db.Column(db.String(100), nullable=True)
    billing_postal_code = db.Column(db.String(20), nullable=True)
    billing_country = db.Column(db.String(100), nullable=True)
    
    payment_method = db.Column(db.String(50), nullable=True)
    payment_transaction_id = db.Column(db.String(100), index=True, nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    
    shipping_method = db.Column(db.String(100), nullable=True)
    shipping_cost = db.Column(db.Float, default=0.0)
    tracking_number = db.Column(db.String(100), nullable=True)
    
    notes_customer = db.Column(db.Text, nullable=True) # Notes from customer during checkout
    notes_internal = db.Column(db.Text, nullable=True) # Notes by admin
    
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    is_b2b_order = db.Column(db.Boolean, default=False, nullable=False, index=True)
    purchase_order_reference = db.Column(db.String(100), nullable=True)
    quote_request_id = db.Column(db.Integer, db.ForeignKey('quote_requests.id', name='fk_order_quote_request_id'), nullable=True, index=True) # Added name
    po_file_path_stored = db.Column(db.String(255), nullable=True) # Path to stored PO file

    customer = db.relationship('User', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', lazy='dynamic', cascade="all, delete-orphan")
    stock_movements = db.relationship('StockMovement', back_populates='related_order', lazy='dynamic') # Updated backref
    invoice = db.relationship('Invoice', back_populates='order_link', uselist=False) # Updated backref
    originating_quote_request = db.relationship('QuoteRequest', back_populates='related_order', foreign_keys=[quote_request_id])

    def to_dict(self): # For API responses, especially admin views
        return {
            "id": self.id, "user_id": self.user_id,
            "customer_email": self.customer.email if self.customer else None,
            "customer_name": f"{self.customer.first_name or ''} {self.customer.last_name or ''}".strip() if self.customer else None,
            "company_name": self.customer.company_name if self.customer and self.customer.company_name else None,
            "order_date": self.order_date.isoformat() if self.order_date else None,
            "status": self.status.value if self.status else None,
            "total_amount": self.total_amount, "currency": self.currency,
            "is_b2b_order": self.is_b2b_order,
            "purchase_order_reference": self.purchase_order_reference,
            "shipping_address": {
                "line1": self.shipping_address_line1, "line2": self.shipping_address_line2,
                "city": self.shipping_city, "postal_code": self.shipping_postal_code,
                "country": self.shipping_country, "phone": self.shipping_phone_snapshot
            },
            # ... other fields ...
            "invoice_id": self.invoice_id,
            "notes_internal": self.notes_internal,
            "tracking_number": self.tracking_number,
            "items": [item.to_dict() for item in self.items] if self.items else []
        }

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id', ondelete='SET NULL'), index=True, nullable=True)
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id', ondelete='SET NULL'), unique=True, index=True, nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False) # Price at time of order (HT for B2B, TTC for B2C if simple)
    total_price = db.Column(db.Float, nullable=False) # quantity * unit_price
    product_name = db.Column(db.String(150), nullable=True) # Snapshot
    variant_description = db.Column(db.String(100), nullable=True) # Snapshot
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    order = db.relationship('Order', back_populates='items')
    product = db.relationship('Product', back_populates='order_items')
    variant = db.relationship('ProductWeightOption', back_populates='order_items')
    sold_serialized_item = db.relationship('SerializedInventoryItem', back_populates='order_item_link', foreign_keys=[serialized_item_id])
    
    def to_dict(self):
        return {
            "id": self.id, "product_id": self.product_id, "variant_id": self.variant_id,
            "product_name": self.product_name, "variant_description": self.variant_description,
            "quantity": self.quantity, "unit_price": self.unit_price, "total_price": self.total_price,
            "serialized_item_uid": self.sold_serialized_item.item_uid if self.sold_serialized_item else None
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


class ProfessionalDocument(db.Model):
    __tablename__ = 'professional_documents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    document_type = db.Column(db.String(100), nullable=False) # e.g., "kbis", "vat_certificate"
    file_path = db.Column(db.String(255), nullable=False) 
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.Enum(ProfessionalStatusEnum, name="prof_doc_status_enum_v2"), default=ProfessionalStatusEnum.PENDING_REVIEW, index=True) # Updated enum name
    reviewed_by_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) 
    reviewed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True) # Admin notes on the document
    
    user = db.relationship('User', back_populates='professional_documents')
    reviewed_by_admin = db.relationship('User', foreign_keys=[reviewed_by_admin_id])


class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='SET NULL'), unique=True, index=True, nullable=True) 
    b2b_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True, nullable=True) 
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    issue_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    due_date = db.Column(db.DateTime, index=True, nullable=True)
    total_amount = db.Column(db.Float, nullable=False) # For B2C, this is TTC. For B2B, this is typically Subtotal HT.
    currency = db.Column(db.String(10), default='EUR') 
    status = db.Column(db.Enum(InvoiceStatusEnum, name="invoice_status_enum_v2"), nullable=False, default=InvoiceStatusEnum.DRAFT, index=True) # Updated enum name
    pdf_path = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True) # General notes for the invoice
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    payment_date = db.Column(db.DateTime, nullable=True) # For B2C, often same as order_date
    # For B2B VAT breakdown:
    subtotal_ht = db.Column(db.Float, nullable=True)
    total_vat_amount = db.Column(db.Float, nullable=True)
    grand_total_ttc = db.Column(db.Float, nullable=True)
    vat_breakdown = db.Column(db.JSON, nullable=True) # Store as {"rate": "amount", ...} e.g. {"20.0": 10.50}
    client_company_name_snapshot = db.Column(db.String(255), nullable=True)
    client_vat_number_snapshot = db.Column(db.String(50), nullable=True)
    client_siret_number_snapshot = db.Column(db.String(50), nullable=True)
    po_reference_snapshot = db.Column(db.String(100), nullable=True)

    items = db.relationship('InvoiceItem', back_populates='invoice', lazy='dynamic', cascade="all, delete-orphan")
    b2b_customer = db.relationship('User', foreign_keys=[b2b_user_id], back_populates='b2b_invoices')
    order_link = db.relationship('Order', back_populates='invoice', foreign_keys=[order_id]) # Updated back_populates


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False) # Snapshot of product/service description
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False) # Price per unit (HT for B2B, TTC for B2C item if itemized)
    total_price = db.Column(db.Float, nullable=False) # quantity * unit_price (HT or TTC based on context)
    vat_rate = db.Column(db.Float, nullable=True) # Applicable VAT rate for this item (e.g., 20.0 for 20%)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True) 
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id', ondelete='SET NULL'), nullable=True) 
    invoice = db.relationship('Invoice', back_populates='items')


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
    status = db.Column(db.Enum(AuditLogStatusEnum, name="audit_log_status_enum_v2"), default=AuditLogStatusEnum.SUCCESS, index=True) # Updated enum name
    acting_user = db.relationship('User', foreign_keys=[user_id], back_populates='audit_logs_initiated')


class NewsletterSubscription(db.Model):
    __tablename__ = 'newsletter_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    subscribed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True, index=True)
    source = db.Column(db.String(100), nullable=True) 
    consent = db.Column(db.String(10), nullable=False, default='Y') # 'Y', 'N'
    language_code = db.Column(db.String(5), nullable=True) 


class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ProductLocalization(db.Model):
    __tablename__ = 'product_localizations'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    lang_code = db.Column(db.String(5), nullable=False, index=True) 
    name_fr = db.Column(db.String(150), nullable=True) 
    name_en = db.Column(db.String(150), nullable=True) 
    description_fr = db.Column(db.Text, nullable=True) 
    description_en = db.Column(db.Text, nullable=True) 
    long_description_fr = db.Column(db.Text, nullable=True) 
    long_description_en = db.Column(db.Text, nullable=True) 
    sensory_evaluation_fr = db.Column(db.Text, nullable=True)
    sensory_evaluation_en = db.Column(db.Text, nullable=True)
    food_pairings_fr = db.Column(db.Text, nullable=True)
    food_pairings_en = db.Column(db.Text, nullable=True)
    species_fr = db.Column(db.String(255), nullable=True) 
    species_en = db.Column(db.String(255), nullable=True)
    ideal_uses_fr = db.Column(db.Text, nullable=True) 
    ideal_uses_en = db.Column(db.Text, nullable=True)
    pairing_suggestions_fr = db.Column(db.Text, nullable=True)
    pairing_suggestions_en = db.Column(db.Text, nullable=True)
    meta_title_fr = db.Column(db.String(255), nullable=True)
    meta_title_en = db.Column(db.String(255), nullable=True)
    meta_description_fr = db.Column(db.Text, nullable=True)
    meta_description_en = db.Column(db.Text, nullable=True)
    
    product = db.relationship('Product', back_populates='localizations')
    __table_args__ = (db.UniqueConstraint('product_id', 'lang_code', name='uq_product_lang_v2'),)


class CategoryLocalization(db.Model):
    __tablename__ = 'category_localizations'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False, index=True)
    lang_code = db.Column(db.String(5), nullable=False, index=True)
    name_fr = db.Column(db.String(100), nullable=True)
    name_en = db.Column(db.String(100), nullable=True)
    description_fr = db.Column(db.Text, nullable=True)
    description_en = db.Column(db.Text, nullable=True)
    species_fr = db.Column(db.Text, nullable=True) 
    species_en = db.Column(db.Text, nullable=True)
    main_ingredients_fr = db.Column(db.Text, nullable=True) 
    main_ingredients_en = db.Column(db.Text, nullable=True)
    ingredients_notes_fr = db.Column(db.Text, nullable=True) 
    ingredients_notes_en = db.Column(db.Text, nullable=True)
    fresh_vs_preserved_fr = db.Column(db.Text, nullable=True) 
    fresh_vs_preserved_en = db.Column(db.Text, nullable=True)
    size_details_fr = db.Column(db.Text, nullable=True) 
    size_details_en = db.Column(db.Text, nullable=True)
    pairings_fr = db.Column(db.Text, nullable=True) 
    pairings_en = db.Column(db.Text, nullable=True)
    weight_info_fr = db.Column(db.Text, nullable=True) 
    weight_info_en = db.Column(db.Text, nullable=True)
    category_notes_fr = db.Column(db.Text, nullable=True) 
    category_notes_en = db.Column(db.Text, nullable=True)
    
    category = db.relationship('Category', back_populates='localizations')
    __table_args__ = (db.UniqueConstraint('category_id', 'lang_code', name='uq_category_lang_v2'),)


class GeneratedAsset(db.Model):
    __tablename__ = 'generated_assets'
    id = db.Column(db.Integer, primary_key=True)
    asset_type = db.Column(db.Enum(AssetTypeEnum, name="asset_type_enum_v2"), nullable=False, index=True) # Updated enum name
    related_item_uid = db.Column(db.String(100), db.ForeignKey('serialized_inventory_items.item_uid', ondelete='SET NULL'), index=True, nullable=True) 
    related_product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), index=True, nullable=True) 
    file_path = db.Column(db.String(255), nullable=False, unique=True) 
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    inventory_item_asset_owner = db.relationship('SerializedInventoryItem', back_populates='generated_assets', foreign_keys=[related_item_uid])
    product_asset_owner = db.relationship('Product', back_populates='generated_assets', foreign_keys=[related_product_id])


class TokenBlocklist(db.Model):
    __tablename__ = 'token_blocklist'
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False, index=True) # Store expiry of the original token
    def __repr__(self): return f"<TokenBlocklist {self.jti}>"


# New B2B Quote Models
class QuoteRequest(db.Model):
    __tablename__ = 'quote_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    request_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.Enum(QuoteRequestStatusEnum, name="quote_request_status_enum_v2"), nullable=False, default=QuoteRequestStatusEnum.PENDING, index=True) # Updated enum name
    notes = db.Column(db.Text, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    contact_person = db.Column(db.String(150), nullable=True)
    contact_phone = db.Column(db.String(50), nullable=True)
    valid_until = db.Column(db.DateTime, nullable=True)
    admin_assigned_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', back_populates='quote_requests')
    items = db.relationship('QuoteRequestItem', back_populates='quote_request', lazy='dynamic', cascade="all, delete-orphan")
    related_order = db.relationship('Order', back_populates='originating_quote_request', uselist=False, foreign_keys='Order.quote_request_id')
    assigned_admin = db.relationship('User', foreign_keys=[admin_assigned_id])

class QuoteRequestItem(db.Model):
    __tablename__ = 'quote_request_items'
    id = db.Column(db.Integer, primary_key=True)
    quote_request_id = db.Column(db.Integer, db.ForeignKey('quote_requests.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id', ondelete='SET NULL'), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    requested_price_ht = db.Column(db.Float, nullable=True) # Price client saw/requested
    quoted_price_ht = db.Column(db.Float, nullable=True) # Price admin quotes
    notes = db.Column(db.Text, nullable=True)

    quote_request = db.relationship('QuoteRequest', back_populates='items')
    product = db.relationship('Product') # Direct relationship for easy access
    variant = db.relationship('ProductWeightOption') # Direct relationship



@b2b_bp.route('/products', methods=['GET'])
@jwt_required()
def get_b2b_products():
    b2b_user = get_b2b_user_from_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    if not b2b_user:
        audit_logger.log_action(user_id=get_jwt_identity(), action='get_b2b_products_fail_auth', details="B2B Professional account approved required.", status='failure', ip_address=ip_address)
        return jsonify(message="Access denied. Approved B2B professional account required.", success=False), 403

    user_tier_enum = b2b_user.b2b_tier

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    category_slug_filter = request.args.get('category_slug')
    search_term_filter = request.args.get('search')
    sort_by_filter = request.args.get('sort', 'name_asc') # Default sort

    # 1. Initial Query Construction (without price sort or pagination yet)
    query = Product.query.join(Category, Product.category_id == Category.id)\
                         .filter(Product.is_active == True, Category.is_active == True)

    if category_slug_filter:
        query = query.filter(Category.slug == category_slug_filter)
    if search_term_filter:
        term_like = f"%{search_term_filter.lower()}%"
        # Consider joining with ProductLocalization and searching localized names too if applicable
        query = query.filter(Product.name.ilike(term_like)) # Basic name search

    # Fetch all products matching filters
    all_filtered_products = query.all()

    # 2. Efficiently Pre-fetch Pricing Data
    all_product_ids = [p.id for p in all_filtered_products]

    # Pre-fetch active weight options for all variable products
    active_options_query = ProductWeightOption.query.filter(
        ProductWeightOption.product_id.in_(all_product_ids),
        ProductWeightOption.is_active == True
    )
    options_by_product_id_map = {}
    all_active_variant_ids = []
    for opt in active_options_query.all():
        if opt.product_id not in options_by_product_id_map:
            options_by_product_id_map[opt.product_id] = []
        options_by_product_id_map[opt.product_id].append(opt)
        all_active_variant_ids.append(opt.id)

    # Pre-fetch B2B tier prices for simple products
    tier_prices_for_products_query = ProductB2BTierPrice.query.filter(
        ProductB2BTierPrice.product_id.in_(all_product_ids),
        ProductB2BTierPrice.variant_id == None, # Simple products
        ProductB2BTierPrice.b2b_tier == user_tier_enum
    )
    product_tier_price_map = {tp.product_id: tp.price for tp in tier_prices_for_products_query.all()}

    # Pre-fetch B2B tier prices for variants
    tier_prices_for_variants_query = ProductB2BTierPrice.query.filter(
        ProductB2BTierPrice.variant_id.in_(all_active_variant_ids),
        ProductB2BTierPrice.b2b_tier == user_tier_enum
    )
    variant_tier_price_map = {tp.variant_id: tp.price for tp in tier_prices_for_variants_query.all()}

    # 3. Calculate Actual B2B Price for Sorting & Augment Product Info
    temp_products_for_sorting = []
    for product in all_filtered_products:
        actual_b2b_price_for_sort = None # Default to None if not determinable

        if product.type == ProductTypeEnum.SIMPLE:
            actual_b2b_price_for_sort = product_tier_price_map.get(product.id, product.base_price)
        
        elif product.type == ProductTypeEnum.VARIABLE_WEIGHT:
            current_product_options = options_by_product_id_map.get(product.id, [])
            if current_product_options:
                min_variant_price = float('inf')
                has_any_option_price = False
                for option in current_product_options:
                    variant_b2b_price = variant_tier_price_map.get(option.id, option.price)
                    if variant_b2b_price is not None: # Ensure price is not None before comparison
                        min_variant_price = min(min_variant_price, variant_b2b_price)
                        has_any_option_price = True
                
                if has_any_option_price and min_variant_price != float('inf'):
                    actual_b2b_price_for_sort = min_variant_price
                elif not has_any_option_price and current_product_options: # Options exist but no prices
                     actual_b2b_price_for_sort = current_product_options[0].price # Fallback to first option's B2C if no B2B price found for any
                # If no options, actual_b2b_price_for_sort remains None or product.base_price could be a fallback
            else: # No active options
                 actual_b2b_price_for_sort = product.base_price # Fallback for variable products with no active options


        # Define sortable_price to handle Nones for sorting
        sortable_value = actual_b2b_price_for_sort
        if sort_by_filter == 'price_asc':
            sortable_value = actual_b2b_price_for_sort if actual_b2b_price_for_sort is not None else float('inf')
        elif sort_by_filter == 'price_desc':
            sortable_value = actual_b2b_price_for_sort if actual_b2b_price_for_sort is not None else float('-inf')
            
        temp_products_for_sorting.append({
            "product_obj": product, # Store the actual product object
            "sort_key_price": sortable_value,
            "sort_key_name": product.name.lower() # For case-insensitive name sort
        })

    # 4. Sort in Python
    if sort_by_filter == 'price_asc':
        temp_products_for_sorting.sort(key=lambda x: x['sort_key_price'])
    elif sort_by_filter == 'price_desc':
        temp_products_for_sorting.sort(key=lambda x: x['sort_key_price'], reverse=True)
    elif sort_by_filter == 'name_desc':
        temp_products_for_sorting.sort(key=lambda x: x['sort_key_name'], reverse=True)
    else: # Default 'name_asc'
        temp_products_for_sorting.sort(key=lambda x: x['sort_key_name'])

    # 5. Manual Pagination
    total_products_count = len(temp_products_for_sorting)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    paginated_entries = temp_products_for_sorting[start_index:end_index]
    total_pages_count = (total_products_count + per_page - 1) // per_page if per_page > 0 else 0


    # 6. Prepare Response Data (using the sorted and paginated product objects)
    products_data = []
    for entry in paginated_entries:
        product = entry['product_obj'] # Get the original Product object
        product_dict = product.to_dict() # Use existing to_dict for base structure

        # Populate 'b2b_price' and 'weight_options_b2b' accurately for display
        # This re-uses the pre-fetched price maps for efficiency
        
        display_b2b_price = product.base_price # Fallback to B2C price
        if product.type == ProductTypeEnum.SIMPLE:
            display_b2b_price = product_tier_price_map.get(product.id, product.base_price)
        
        product_dict['b2b_price'] = display_b2b_price
        product_dict['retail_price'] = product.base_price # RRP is the B2C price

        if product.type == ProductTypeEnum.VARIABLE_WEIGHT:
            options_list_b2b_display = []
            # Use sorted options from map to maintain order
            current_product_options_display = sorted(options_by_product_id_map.get(product.id, []), key=lambda o: o.weight_grams)
            
            min_b2b_variant_price_display = float('inf') if current_product_options_display else None

            for option_display in current_product_options_display:
                option_b2b_price = variant_tier_price_map.get(option_display.id, option_display.price)
                
                if option_b2b_price is not None and (min_b2b_variant_price_display is None or option_b2b_price < min_b2b_variant_price_display):
                     min_b2b_variant_price_display = option_b2b_price

                options_list_b2b_display.append({
                    "option_id": option_display.id,
                    "weight_grams": option_display.weight_grams,
                    "sku_suffix": option_display.sku_suffix,
                    "b2b_price": option_b2b_price, # Tiered price for this variant for display
                    "retail_price": option_display.price, # B2C retail price for this variant
                    "aggregate_stock_quantity": option_display.aggregate_stock_quantity # Ensure this is accurate
                })
            product_dict['weight_options_b2b'] = options_list_b2b_display
            
            if min_b2b_variant_price_display is not None and min_b2b_variant_price_display != float('inf'):
                product_dict['b2b_price'] = min_b2b_variant_price_display 
            elif not current_product_options_display:
                 product_dict['b2b_price'] = None # Or some indicator it's unavailable/no B2B price
            # If min_b2b_variant_price_display is inf but options existed, it means no B2B tier price found, default to base or variant B2C price was used
            # The product_dict['b2b_price'] might already be set to product.base_price if it fell through.

        products_data.append(product_dict)
    
    audit_logger.log_action(user_id=b2b_user.id, action='get_b2b_products_success', details=f"Page: {page}, Filters: category_slug={category_slug_filter}, search={search_term_filter}, sort={sort_by_filter}", status='success', ip_address=ip_address)
    return jsonify({
        "products": products_data,
        "page": page,
        "per_page": per_page,
        "total_products": total_products_count,
        "total_pages": total_pages_count,
        "success": True
    }), 200


def get_b2b_user_from_identity():
    """Helper to get the authenticated B2B user."""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user or user.role != UserRoleEnum.B2B_PROFESSIONAL or user.professional_status != ProfessionalStatusEnum.APPROVED:
        return None
    return user

@b2b_bp.route('/loyalty-status', methods=['GET'])
@jwt_required()
def get_loyalty_status():
    b2b_user = get_b2b_user_from_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    if not b2b_user:
        audit_logger.log_action(user_id=get_jwt_identity(), action='get_loyalty_status_fail_auth', details="B2B Professional account approved required.", status='failure', ip_address=ip_address)
        return jsonify(message="Access denied. Approved B2B professional account required.", success=False), 403

    # 1. Calculate Annual Spend (completed orders in the last 365 days)
    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    annual_spend_result = db.session.query(func.sum(Order.total_amount))\
        .filter(Order.user_id == b2b_user.id,
                Order.is_b2b_order == True,
                Order.order_date >= one_year_ago,
                Order.status.in_([OrderStatusEnum.COMPLETED, OrderStatusEnum.DELIVERED, OrderStatusEnum.SHIPPED])) # Consider only completed/shipped orders for spend
    annual_spend = annual_spend_result.scalar() or 0.0

    # 2. Determine Current Tier
    current_tier_name = "Bronze" # Default/fallback
    current_tier_min_spend = 0
    next_tier_name = None
    next_tier_min_spend = float('inf')
    spend_needed_for_next_tier = float('inf')
    
    # Iterate in reverse to find the highest achieved tier
    for i in range(len(LOYALTY_TIERS_CONFIG) - 1, -1, -1):
        tier_config = LOYALTY_TIERS_CONFIG[i]
        if annual_spend >= tier_config["min_spend"]:
            current_tier_name = tier_config["name"]
            current_tier_min_spend = tier_config["min_spend"]
            if i + 1 < len(LOYALTY_TIERS_CONFIG): # If not the highest tier
                next_tier_config = LOYALTY_TIERS_CONFIG[i+1]
                next_tier_name = next_tier_config["name"]
                next_tier_min_spend = next_tier_config["min_spend"]
                spend_needed_for_next_tier = max(0, next_tier_config["min_spend"] - annual_spend)
            else: # Highest tier reached
                next_tier_name = "Maximum"
                spend_needed_for_next_tier = 0
                next_tier_min_spend = annual_spend # Or current tier's min_spend for progress bar logic
            break
            
    # Update user's B2B tier in the database if it has changed (optional, or do this via a nightly job)
    # For simplicity, we'll assume the frontend displays based on this dynamic calculation.
    # If User model has b2b_tier, you could update it:
    # new_tier_enum = B2BPricingTierEnum[current_tier_name.upper()] # Map name to Enum
    # if b2b_user.b2b_tier != new_tier_enum:
    #     b2b_user.b2b_tier = new_tier_enum
    #     db.session.commit()


    # 3. Get Referral Code (generate if not exists)
    if not b2b_user.referral_code:
        b2b_user.referral_code = f"TRUVRA-{b2b_user.id}-{uuid.uuid4().hex[:6].upper()}"
        try:
            db.session.commit()
        except Exception as e: # Handle potential race condition if two requests try to generate
            db.session.rollback()
            current_app.logger.warning(f"Could not assign referral code to user {b2b_user.id}: {e}")
            # Re-fetch user to get code if another request just set it
            b2b_user = User.query.get(b2b_user.id)


    # 4. Get Referral Credit Balance (assuming a field on User model)
    referral_credit_balance = b2b_user.referral_credit_balance or 0.0

    # 5. Restaurant Branding Partner status
    is_restaurant_branding_partner = b2b_user.is_restaurant_branding_partner or False


    loyalty_data = {
        "current_tier_name": current_tier_name,
        "current_tier_min_spend": current_tier_min_spend, # For progress bar calculation
        "annual_spend": round(annual_spend, 2),
        "referral_code": b2b_user.referral_code,
        "referral_credit_balance": round(referral_credit_balance, 2),
        "next_tier_name": next_tier_name,
        "next_tier_min_spend": next_tier_min_spend if next_tier_min_spend != float('inf') else None, # For progress bar
        "spend_needed_for_next_tier": round(spend_needed_for_next_tier, 2) if spend_needed_for_next_tier != float('inf') else 0,
        "is_restaurant_branding_partner": is_restaurant_branding_partner
    }
    audit_logger.log_action(user_id=b2b_user.id, action='get_loyalty_status_success', details=f"Tier: {current_tier_name}, Spend: {annual_spend}", status='success', ip_address=ip_address)
    return jsonify(success=True, data=loyalty_data), 200


@b2b_bp.route('/products', methods=['GET'])
@jwt_required()
def get_b2b_products():
    b2b_user = get_b2b_user_from_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    if not b2b_user:
        audit_logger.log_action(user_id=get_jwt_identity(), action='get_b2b_products_fail_auth', details="B2B Professional account approved required.", status='failure', ip_address=ip_address)
        return jsonify(message="Access denied. Approved B2B professional account required.", success=False), 403

    user_tier_enum = b2b_user.b2b_tier # This is B2BPricingTierEnum

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    category_slug_filter = request.args.get('category_slug')
    search_term_filter = request.args.get('search')
    sort_by_filter = request.args.get('sort', 'name_asc')

    query = Product.query.join(Category, Product.category_id == Category.id)\
                         .filter(Product.is_active == True, Category.is_active == True)

    if category_slug_filter:
        query = query.filter(Category.slug == category_slug_filter)
    if search_term_filter:
        term_like = f"%{search_term_filter.lower()}%"
        query = query.filter(Product.name.ilike(term_like))

    if sort_by_filter == 'price_asc': query = query.order_by(Product.base_price.asc())
    elif sort_by_filter == 'price_desc': query = query.order_by(Product.base_price.desc())
    elif sort_by_filter == 'name_desc': query = query.order_by(Product.name.desc())
    else: query = query.order_by(Product.name.asc())

    paginated_products = query.paginate(page=page, per_page=per_page, error_out=False)
    products_data = []

    for product in paginated_products.items:
        product_dict = product.to_dict()
        b2b_price_to_display = product.base_price 

        if product.type == ProductTypeEnum.SIMPLE:
            tier_price_entry = ProductB2BTierPrice.query.filter_by(
                product_id=product.id, variant_id=None, b2b_tier=user_tier_enum
            ).first()
            if tier_price_entry:
                b2b_price_to_display = tier_price_entry.price
        
        product_dict['b2b_price'] = b2b_price_to_display
        product_dict['retail_price'] = product.base_price

        if product.type == ProductTypeEnum.VARIABLE_WEIGHT:
            options_list_b2b = []
            active_options = product.weight_options.filter_by(is_active=True).order_by(ProductWeightOption.weight_grams).all()
            min_b2b_variant_price = float('inf') if active_options else None

            for option in active_options:
                option_b2b_price = option.price
                option_tier_price_entry = ProductB2BTierPrice.query.filter_by(
                    variant_id=option.id, b2b_tier=user_tier_enum
                ).first()
                if option_tier_price_entry:
                    option_b2b_price = option_tier_price_entry.price
                
                if option_b2b_price < min_b2b_variant_price :
                    min_b2b_variant_price = option_b2b_price

                options_list_b2b.append({
                    "option_id": option.id, "weight_grams": option.weight_grams,
                    "sku_suffix": option.sku_suffix, "b2b_price": option_b2b_price,
                    "retail_price": option.price, "aggregate_stock_quantity": option.aggregate_stock_quantity
                })
            product_dict['weight_options_b2b'] = options_list_b2b
            if min_b2b_variant_price is not None and min_b2b_variant_price != float('inf'):
                product_dict['b2b_price'] = min_b2b_variant_price
            elif not active_options:
                 product_dict['b2b_price'] = None

        products_data.append(product_dict)
    
    audit_logger.log_action(user_id=b2b_user.id, action='get_b2b_products_success', status='success', ip_address=ip_address)
    return jsonify({
        "products": products_data, "page": paginated_products.page,
        "per_page": paginated_products.per_page, "total_products": paginated_products.total,
        "total_pages": paginated_products.pages, "success": True
    }), 200


@b2b_bp.route('/quote-requests', methods=['POST'])
@jwt_required()
def create_quote_request():
    b2b_user = get_b2b_user_from_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    if not b2b_user:
        audit_logger.log_action(user_id=get_jwt_identity(), action='create_quote_fail_auth', details="B2B Professional account required.", status='failure', ip_address=ip_address)
        return jsonify(message="B2B professional account required.", success=False), 403

    data = request.json
    items_data = data.get('items'); notes = sanitize_input(data.get('notes'))
    contact_person = sanitize_input(data.get('contact_person', f"{b2b_user.first_name or ''} {b2b_user.last_name or ''}".strip()))
    contact_phone = sanitize_input(data.get('contact_phone'))

    if not items_data or not isinstance(items_data, list) or len(items_data) == 0:
        audit_logger.log_action(user_id=b2b_user.id, action='create_quote_fail_validation', details="Empty item list for quote.", status='failure', ip_address=ip_address)
        return jsonify(message="At least one item is required for a quote request.", success=False), 400

    try:
        new_quote = QuoteRequest(user_id=b2b_user.id, notes=notes, contact_person=contact_person, contact_phone=contact_phone, status=QuoteRequestStatusEnum.PENDING)
        db.session.add(new_quote); db.session.flush()

        for item_data in items_data:
            product_id = item_data.get('product_id'); variant_id = item_data.get('variant_id')
            quantity = item_data.get('quantity'); price_at_request = item_data.get('price_at_request')

            if not product_id or not quantity or price_at_request is None:
                 db.session.rollback()
                 return jsonify(message=f"Invalid data for item {product_id}.", success=False), 400
            
            product = Product.query.get(product_id)
            if not product: db.session.rollback(); return jsonify(message=f"Product ID {product_id} not found.", success=False), 404
            
            db.session.add(QuoteRequestItem(quote_request_id=new_quote.id, product_id=product_id, variant_id=variant_id, quantity=int(quantity), requested_price_ht=float(price_at_request)))
        
        db.session.commit()
        audit_logger.log_action(user_id=b2b_user.id, action='create_quote_success', target_type='quote_request', target_id=new_quote.id, status='success', ip_address=ip_address)
        return jsonify(message="Quote request submitted successfully.", quote_id=new_quote.id, success=True), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating quote request for user {b2b_user.id}: {e}", exc_info=True)
        return jsonify(message="Failed to submit quote request.", error=str(e), success=False), 500


@b2b_bp.route('/purchase-orders', methods=['POST'])
@jwt_required()
def upload_purchase_order():
    b2b_user = get_b2b_user_from_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    if not b2b_user:
        audit_logger.log_action(user_id=get_jwt_identity(), action='upload_po_fail_auth', details="B2B Professional account required.", status='failure', ip_address=ip_address)
        return jsonify(message="B2B professional account required.", success=False), 403

    if 'purchase_order_file' not in request.files: return jsonify(message="No PO file provided.", success=False), 400
    po_file = request.files['purchase_order_file']; cart_items_json = request.form.get('cart_items')
    client_po_number = sanitize_input(request.form.get('client_po_number'))


    if po_file.filename == '': return jsonify(message="No selected PO file.", success=False), 400
    if not cart_items_json: return jsonify(message="Cart items data required with PO.", success=False), 400

    try:
        cart_items = json.loads(cart_items_json)
        if not isinstance(cart_items, list) or len(cart_items) == 0: raise ValueError("Invalid cart items.")
    except (json.JSONDecodeError, ValueError) as e:
        return jsonify(message=f"Invalid cart items data: {str(e)}", success=False), 400

    upload_folder_pos = os.path.join(current_app.config['UPLOAD_FOLDER'], 'b2b_purchase_orders')
    os.makedirs(upload_folder_pos, exist_ok=True)

    if po_file and allowed_file(po_file.filename, 'ALLOWED_DOCUMENT_EXTENSIONS'):
        filename_base = secure_filename(f"user_{b2b_user.id}_po_{uuid.uuid4().hex[:8]}")
        extension = get_file_extension(po_file.filename)
        filename = f"{filename_base}.{extension}"
        file_path_full = os.path.join(upload_folder_pos, filename)
        file_path_relative_for_db = os.path.join('b2b_purchase_orders', filename)

        try:
            po_file.save(file_path_full)
            calculated_total = 0; order_items_to_create = []
            # Use user's stored addresses as default for the order
            shipping_addr_payload = {
                "line1": b2b_user.shipping_address_line1 or b2b_user.company_address_line1,
                "line2": b2b_user.shipping_address_line2 or b2b_user.company_address_line2,
                "city": b2b_user.shipping_city or b2b_user.company_city,
                "postal_code": b2b_user.shipping_postal_code or b2b_user.company_postal_code,
                "country": b2b_user.shipping_country or b2b_user.company_country
            } # Simplified, add more fields as needed from User model


            for item_data in cart_items:
                product_id = item_data.get('product_id'); variant_id = item_data.get('variant_id')
                quantity = int(item_data.get('quantity', 0)); price_at_request = float(item_data.get('price')) # Assume price from cart is B2B HT
                if not product_id or quantity <= 0 or price_at_request is None:
                    if os.path.exists(file_path_full): os.remove(file_path_full)
                    return jsonify(message="Invalid item data in PO.", success=False), 400
                
                product_db = Product.query.get(product_id)
                if not product_db: if os.path.exists(file_path_full): os.remove(file_path_full); return jsonify(message=f"Product ID {product_id} not found.", success=False), 404
                
                calculated_total += price_at_request * quantity
                order_items_to_create.append({"product_id": product_id, "variant_id": variant_id, "quantity": quantity, "unit_price": price_at_request, "total_price": price_at_request * quantity, "product_name": product_db.name, "variant_description": ProductWeightOption.query.get(variant_id).sku_suffix if variant_id else None})

            new_order = Order(
                user_id=b2b_user.id, is_b2b_order=True, status=OrderStatusEnum.PENDING_PO_REVIEW,
                total_amount=calculated_total, currency=b2b_user.currency or 'EUR',
                purchase_order_reference=client_po_number or po_file.filename, # Use client's PO number if provided
                po_file_path_stored=file_path_relative_for_db,
                shipping_address_line1=shipping_addr_payload['line1'], shipping_city=shipping_addr_payload['city'], 
                shipping_postal_code=shipping_addr_payload['postal_code'], shipping_country=shipping_addr_payload['country'],
                # Populate billing similarly
                billing_address_line1=b2b_user.billing_address_line1 or shipping_addr_payload['line1'], # Example
            )
            db.session.add(new_order); db.session.flush()
            for oi_data in order_items_to_create: db.session.add(OrderItem(order_id=new_order.id, **oi_data))
            db.session.commit()
            audit_logger.log_action(user_id=b2b_user.id, action='upload_po_success', target_type='order', target_id=new_order.id, details=f"PO {po_file.filename} uploaded, client ref: {client_po_number}.", status='success', ip_address=ip_address)
            return jsonify(message="PO submitted, order created for review.", order_id=new_order.id, success=True), 201
        except Exception as e:
            db.session.rollback();
            if os.path.exists(file_path_full): try: os.remove(file_path_full) catch OSError: pass
            current_app.logger.error(f"Error processing PO for user {b2b_user.id}: {e}", exc_info=True)
            return jsonify(message="Failed to submit PO.", error=str(e), success=False), 500
    else: return jsonify(message="Invalid PO file type.", success=False), 400
      
@b2b_bp.route('/quote-requests', methods=['POST'])
@jwt_required()
def create_quote_request():
    current_user_id = get_jwt_identity()
    b2b_user = User.query.get(current_user_id)
    audit_logger = current_app.audit_log_service

    if not b2b_user or b2b_user.role != UserRoleEnum.B2B_PROFESSIONAL:
        audit_logger.log_action(user_id=current_user_id, action='create_quote_fail_auth', details="B2B Professional account required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="B2B professional account required.", success=False), 403

    data = request.json
    items_data = data.get('items')
    notes = sanitize_input(data.get('notes'))
    contact_person = sanitize_input(data.get('contact_person', f"{b2b_user.first_name or ''} {b2b_user.last_name or ''}".strip()))
    contact_phone = sanitize_input(data.get('contact_phone')) # Assuming phone is on User model or client provides

    if not items_data or not isinstance(items_data, list) or len(items_data) == 0:
        audit_logger.log_action(user_id=current_user_id, action='create_quote_fail_validation', details="Empty item list for quote.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="At least one item is required for a quote request.", success=False), 400

    try:
        new_quote = QuoteRequest(
            user_id=current_user_id,
            notes=notes,
            contact_person=contact_person,
            contact_phone=contact_phone, # Store directly, validation can be added
            status=QuoteRequestStatusEnum.PENDING # Default status for new quote
        )
        db.session.add(new_quote)
        db.session.flush() # To get new_quote.id for items

        for item_data in items_data:
            product_id = item_data.get('product_id')
            variant_id = item_data.get('variant_id') # Can be None for simple products
            quantity = item_data.get('quantity')
            price_at_request = item_data.get('price_at_request') # B2B price shown to user

            if not product_id or not quantity or price_at_request is None:
                 audit_logger.log_action(user_id=current_user_id, action='create_quote_fail_item_validation',quote_id=new_quote.id, details=f"Invalid item data: {item_data}", status='failure', ip_address=request.remote_addr)
                 db.session.rollback() # Important: rollback if any item is invalid
                 return jsonify(message=f"Invalid data for item with product ID {product_id}.", success=False), 400

            product = Product.query.get(product_id)
            if not product:
                db.session.rollback()
                return jsonify(message=f"Product ID {product_id} not found.", success=False), 404
            
            variant = None
            if variant_id:
                variant = ProductWeightOption.query.get(variant_id)
                if not variant or variant.product_id != product.id: # Ensure variant belongs to product
                    db.session.rollback()
                    return jsonify(message=f"Invalid variant ID {variant_id} for product {product_id}.", success=False), 400


            quote_item = QuoteRequestItem(
                quote_request_id=new_quote.id,
                product_id=product_id,
                variant_id=variant_id, # Store None if simple product
                quantity=int(quantity),
                requested_price_ht=float(price_at_request) # Store the price user saw
            )
            db.session.add(quote_item)
        
        db.session.commit()
        
        # Notify Admin
        email_service = EmailService(current_app)
        admin_email = current_app.config.get('ADMIN_EMAIL', 'admin@example.com') # Fallback
        subject = f"Nouvelle Demande de Devis B2B #{new_quote.id} de {b2b_user.company_name or b2b_user.email}"
        body = f"""
        Une nouvelle demande de devis B2B a été soumise :
        ID Devis: {new_quote.id}
        Client: {b2b_user.company_name or b2b_user.email} (ID Utilisateur: {current_user_id})
        Contact Fourni: {contact_person} {f'({contact_phone})' if contact_phone else ''}
        Notes Client: {notes or 'Aucune'}

        Consultez le panneau d'administration pour examiner et traiter cette demande.
        """
        try:
            email_service.send_email(to_email=admin_email, subject=subject, body_text=body)
            current_app.logger.info(f"Admin notification email sent for new B2B Quote Request {new_quote.id}.")
        except Exception as e_mail:
            current_app.logger.error(f"Failed to send admin email for quote {new_quote.id}: {e_mail}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='create_quote_success', target_type='quote_request', target_id=new_quote.id, status='success', ip_address=request.remote_addr)
        
        return jsonify(message="Quote request submitted successfully.", quote_id=new_quote.id, success=True), 201
    except ValueError as ve: # Catch specific ValueErrors from int/float conversions
        db.session.rollback()
        return jsonify(message=str(ve), success=False), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating quote request for user {current_user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='create_quote_fail_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to submit quote request due to a server error.", error=str(e), success=False), 500


@b2b_bp.route('/purchase-orders', methods=['POST'])
@jwt_required()
def upload_purchase_order():
    current_user_id = get_jwt_identity()
    b2b_user = User.query.get(current_user_id)
    audit_logger = current_app.audit_log_service

    if not b2b_user or b2b_user.role != UserRoleEnum.B2B_PROFESSIONAL:
        audit_logger.log_action(user_id=current_user_id, action='upload_po_fail_auth', details="B2B Professional account required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="B2B professional account required.", success=False), 403

    if 'purchase_order_file' not in request.files:
        return jsonify(message="No purchase order file provided ('purchase_order_file' part missing).", success=False), 400
    
    po_file = request.files['purchase_order_file']
    # Cart items should be sent as a JSON string in a form field, e.g., 'cart_items_json'
    cart_items_json_str = request.form.get('cart_items') 

    if po_file.filename == '':
        return jsonify(message="No selected file for purchase order.", success=False), 400
    if not cart_items_json_str:
        return jsonify(message="Cart items data (JSON string in 'cart_items' field) is required with PO submission.", success=False), 400

    try:
        cart_items = json.loads(cart_items_json_str)
        if not isinstance(cart_items, list) or len(cart_items) == 0:
            raise ValueError("Invalid cart items format or empty cart for PO.")
    except (json.JSONDecodeError, ValueError) as e:
        audit_logger.log_action(user_id=current_user_id, action='upload_po_fail_cart_format', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Invalid cart items data format: {str(e)}", success=False), 400

    # Define where to save POs - should be secure and ideally outside web root if not served directly
    upload_folder_pos = os.path.join(current_app.config['UPLOAD_FOLDER'], 'b2b_purchase_orders')
    os.makedirs(upload_folder_pos, exist_ok=True)

    if po_file and allowed_file(po_file.filename, 'ALLOWED_DOCUMENT_EXTENSIONS'):
        filename_base = secure_filename(f"user_{current_user_id}_po_{uuid.uuid4().hex[:8]}")
        extension = get_file_extension(po_file.filename)
        filename_on_disk = f"{filename_base}.{extension}"
        file_path_full = os.path.join(upload_folder_pos, filename_on_disk)
        
        # Path to store in DB, relative to a configured assets root if served later by admin
        # For GeneratedAsset, it might be 'b2b_purchase_orders/filename_on_disk'
        file_path_for_db = os.path.join('b2b_purchase_orders', filename_on_disk)


        try:
            po_file.save(file_path_full)

            # Create an Order with status PENDING_PO_REVIEW
            calculated_total_ht = 0 # B2B orders often based on HT
            order_items_to_create = []

            # Fetch B2B user's shipping/billing info as default
            # These could also be part of the PO form if user can override
            shipping_addr = {
                'line1': b2b_user.shipping_address_line1 or b2b_user.company_address_line1 or "N/A",
                'line2': b2b_user.shipping_address_line2 or b2b_user.company_address_line2,
                'city': b2b_user.shipping_city or b2b_user.company_city or "N/A",
                'postal_code': b2b_user.shipping_postal_code or b2b_user.company_postal_code or "N/A",
                'country': b2b_user.shipping_country or b2b_user.company_country or "N/A",
            }
            billing_addr = { # Similar logic for billing
                'line1': b2b_user.billing_address_line1 or shipping_addr['line1'],
                'line2': b2b_user.billing_address_line2 or shipping_addr['line2'],
                'city': b2b_user.billing_city or shipping_addr['city'],
                'postal_code': b2b_user.billing_postal_code or shipping_addr['postal_code'],
                'country': b2b_user.billing_country or shipping_addr['country'],
            }


            for item_data in cart_items:
                product_id = item_data.get('product_id')
                variant_id = item_data.get('variant_id')
                quantity = int(item_data.get('quantity', 0))
                # IMPORTANT: Use the B2B price that was displayed and added to cart.
                # This price should reflect the user's tier.
                price_at_request_ht = float(item_data.get('price')) # Assuming 'price' from B2B cart is HT

                if not product_id or quantity <= 0 or price_at_request_ht is None:
                    if os.path.exists(file_path_full): os.remove(file_path_full) # Cleanup partial upload
                    audit_logger.log_action(user_id=current_user_id, action='upload_po_fail_item_data_validation', details=f"Invalid item data in PO: {item_data}", status='failure', ip_address=request.remote_addr)
                    return jsonify(message="Invalid item data in PO submission.", success=False), 400
                
                product_db = Product.query.get(product_id)
                if not product_db:
                     if os.path.exists(file_path_full): os.remove(file_path_full)
                     return jsonify(message=f"Product with ID {product_id} not found.", success=False), 404

                variant_db = None
                if variant_id:
                    variant_db = ProductWeightOption.query.get(variant_id)
                    if not variant_db or variant_db.product_id != product_id:
                        if os.path.exists(file_path_full): os.remove(file_path_full)
                        return jsonify(message=f"Invalid variant ID {variant_id} for product {product_id}.", success=False), 400


                calculated_total_ht += price_at_request_ht * quantity
                order_items_to_create.append({
                    "product_id": product_id, "variant_id": variant_id,
                    "quantity": quantity, "unit_price": price_at_request_ht, # This is HT
                    "total_price": price_at_request_ht * quantity, # Line total HT
                    "product_name": product_db.name, # Storing name at time of order
                    "variant_description": variant_db.sku_suffix if variant_db else None
                })

            new_order = Order(
                user_id=current_user_id, is_b2b_order=True,
                status=OrderStatusEnum.PENDING_PO_REVIEW,
                total_amount=calculated_total_ht, # Store HT total
                currency=b2b_user.currency or current_app.config.get('DEFAULT_CURRENCY', 'EUR'),
                purchase_order_reference=po_file.filename, # Store original filename as reference
                # Fill shipping/billing from b2b_user profile or allow overrides from form
                shipping_address_line1=shipping_addr['line1'], shipping_address_line2=shipping_addr.get('line2'),
                shipping_city=shipping_addr['city'], shipping_postal_code=shipping_addr['postal_code'],
                shipping_country=shipping_addr['country'],
                billing_address_line1=billing_addr['line1'], billing_address_line2=billing_addr.get('line2'),
                billing_city=billing_addr['city'], billing_postal_code=billing_addr['postal_code'],
                billing_country=billing_addr['country'],
            )
            db.session.add(new_order)
            db.session.flush() # Get new_order.id

            for oi_data in order_items_to_create:
                db.session.add(OrderItem(order_id=new_order.id, **oi_data))

            # Store PO file path using GeneratedAsset model
            po_asset = GeneratedAsset(
                asset_type=AssetTypeEnum.PURCHASE_ORDER_FILE,
                related_order_id=new_order.id, # Link to the order
                file_path=file_path_relative_for_db
            )
            db.session.add(po_asset)
            # If Order model has a direct field for po_file_path, set it too
            # new_order.po_file_path_stored = file_path_relative_for_db


            db.session.commit()
            
            # Notify Admin
            email_service = EmailService(current_app)
            admin_email = current_app.config.get('ADMIN_EMAIL', 'admin@example.com')
            subject_po = f"Nouveau Bon de Commande B2B soumis par {b2b_user.company_name or b2b_user.email} - Commande #{new_order.id}"
            body_po = f"""
            Un nouveau bon de commande a été soumis et une commande préliminaire a été créée :
            ID Commande: {new_order.id}
            Client: {b2b_user.company_name or b2b_user.email} (ID Utilisateur: {current_user_id})
            Fichier Bon de Commande: {po_file.filename} (stocké comme {file_path_relative_for_db})
            Montant Total Estimé (HT): {calculated_total_ht:.2f} {new_order.currency}

            Veuillez examiner le bon de commande et la commande dans le panneau d'administration.
            """
            try:
                email_service.send_email(to_email=admin_email, subject=subject_po, body_text=body_po)
                current_app.logger.info(f"Admin notification sent for new B2B PO for order {new_order.id}.")
            except Exception as e_mail_po:
                 current_app.logger.error(f"Failed to send admin email for PO of order {new_order.id}: {e_mail_po}", exc_info=True)

            audit_logger.log_action(user_id=current_user_id, action='upload_po_success', target_type='order', target_id=new_order.id, details=f"PO {po_file.filename} uploaded.", status='success', ip_address=request.remote_addr)
            return jsonify(message="Purchase Order submitted successfully. It will be reviewed by our team.", order_id=new_order.id, success=True), 201

        except Exception as e:
            db.session.rollback()
            if os.path.exists(file_path_full): # Cleanup saved file if DB transaction failed
                try: os.remove(file_path_full)
                except OSError as e_clean: current_app.logger.error(f"Error cleaning up PO file {filename_on_disk}: {e_clean}")
            current_app.logger.error(f"Error processing PO for user {current_user_id}: {e}", exc_info=True)
            audit_logger.log_action(user_id=current_user_id, action='upload_po_fail_exception', details=str(e), status='failure', ip_address=request.remote_addr)
            return jsonify(message="Failed to submit Purchase Order due to a server error.", error=str(e), success=False), 500
    else:
        return jsonify(message="Invalid file type for Purchase Order. Allowed: PDF, DOC, DOCX, XLS, XLSX, PNG, JPG.", success=False), 400
