# backend/models.py
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
import enum 
import pyotp 
import re 
from flask import current_app 

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
    ON_HOLD = "on_hold" # Renamed from PENDING

class ProductTypeEnum(enum.Enum):
    SIMPLE = "simple"
    VARIABLE_WEIGHT = "variable_weight"

class PreservationTypeEnum(enum.Enum):
    FRESH = "frais"
    PRESERVED_CANNED = "conserve" # Renamed from PRESERVED
    DRY = "sec"
    FROZEN = "surgele"
    VACUUM_PACKED = "sous_vide"
    OTHER = "autre" # New
    NOT_SPECIFIED = "non_specifie" # New

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
    PRODUCTION = "production" # New
    RECALL = "recall" # New
    TRANSFER_IN = "transfer_in" # New
    TRANSFER_OUT = "transfer_out" # New
    RECEIVE_SERIALIZED = "receive_serialized" # New
    IMPORT_CSV_NEW = "import_csv_new" # New

class OrderStatusEnum(enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    PENDING_PO_REVIEW = "pending_po_review" # New for B2B PO flow
    QUOTE_REQUESTED = "quote_requested" # New for B2B Quote flow
    QUOTE_SENT = "quote_sent" # New for B2B Quote flow
    ORDER_PENDING_APPROVAL = "order_pending_approval" # New for B2B flow (after quote/PO)
    PAID = "paid"
    PROCESSING = "processing"
    AWAITING_SHIPMENT = "awaiting_shipment" # New
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
    PROFESSIONAL_DOCUMENT = "professional_document" # New
    PURCHASE_ORDER_FILE = "purchase_order_file" # New

class B2BPricingTierEnum(enum.Enum): # New for B2B
    STANDARD = "standard"
    GOLD = "gold"
    PLATINUM = "platinum"
    # Add more tiers as needed

class QuoteRequestStatusEnum(enum.Enum): # New for B2B Quote Requests
    PENDING = "pending" # Client submitted, awaiting admin review
    PROCESSING = "processing" # Admin is working on it
    SENT_TO_CLIENT = "sent_to_client" # Admin sent the quote
    ACCEPTED_BY_CLIENT = "accepted_by_client" # Client agreed
    CONVERTED_TO_ORDER = "converted_to_order" # Admin converted to order
    DECLINED_BY_CLIENT = "declined_by_client" # Client refused
    EXPIRED = "expired" # Quote validity passed

class NewsletterTypeEnum(enum.Enum): # New Enum
    B2C = "b2c"
    B2B = "b2b"
    GENERAL = "general"


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=True) 
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
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


        # --- Added Referral Fields ---
    referral_code = db.Column(db.String(50), unique=True, nullable=True, index=True) # User's own referral code
    referred_by_code = db.Column(db.String(50), nullable=True, index=True) # Code of the user who referred them
    # Consider: db.ForeignKey('users.referral_code') for referred_by_code if strict validation is needed,
    # but this makes referral_code non-nullable or requires careful handling of circular dependencies or deferred constraints.
    # For now, keeping it as a simple string.
    referral_credit_balance = db.Column(db.Float, default=0.0, nullable=False)

    
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
    shipping_phone = db.Column(db.String(50), nullable=True) # Added shipping phone

    billing_address_line1 = db.Column(db.String(255), nullable=True)
    billing_address_line2 = db.Column(db.String(255), nullable=True)
    billing_city = db.Column(db.String(100), nullable=True)
    billing_postal_code = db.Column(db.String(20), nullable=True)
    billing_country = db.Column(db.String(100), nullable=True)
    
    currency = db.Column(db.String(3), default='EUR')

    # Newsletter subscription fields
    newsletter_b2c_subscribed = db.Column(db.Boolean, default=False, nullable=False)
    newsletter_b2b_subscribed = db.Column(db.Boolean, default=False, nullable=False)
    preferred_language = db.Column(db.String(5), default='fr') # Store user's preferred language

    orders = db.relationship('Order', back_populates='customer', lazy='dynamic')
    reviews = db.relationship('Review', back_populates='user', lazy='dynamic')
    cart = db.relationship('Cart', back_populates='user', uselist=False, lazy='joined') 
    professional_documents = db.relationship('ProfessionalDocument', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")
    b2b_invoices = db.relationship('Invoice', foreign_keys='Invoice.b2b_user_id', back_populates='b2b_customer', lazy='dynamic')
    audit_logs_initiated = db.relationship('AuditLog', foreign_keys='AuditLog.user_id', back_populates='acting_user', lazy='dynamic')
    quote_requests = db.relationship('QuoteRequest', back_populates='user', lazy='dynamic') # Added relationship

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password) if self.password_hash else False
    
    @staticmethod
    def validate_password(password):
        if not password or len(password) < 8: return "auth.error.password_too_short"
        if not re.search(r"[A-Z]", password): return "auth.error.password_no_uppercase"
        if not re.search(r"[a-z]", password): return "auth.error.password_no_lowercase"
        if not re.search(r"[0-9]", password): return "auth.error.password_no_digit"
        # if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): return "auth.error.password_no_special" # Optional
        return None

        
    def generate_totp_secret(self): self.totp_secret = pyotp.random_base32(); return self.totp_secret
    
    def get_totp_uri(self, issuer_name=None):
        # ... (TOTP URI logic) ...
        if not self.totp_secret: raise ValueError("TOTP secret missing.")
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(name=self.email, issuer_name=issuer_name or current_app.config.get('TOTP_ISSUER_NAME', 'Maison Truvra'))
    
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
            "newsletter_b2c_subscribed": self.newsletter_b2c_subscribed,
            "newsletter_b2b_subscribed": self.newsletter_b2b_subscribed,
            "preferred_language": self.preferred_language,
            # --- Added Referral Fields to to_dict ---
            "referral_code": self.referral_code,
            "referred_by_code": self.referred_by_code,
            "referral_credit_balance": self.referral_credit_balance
            # --- End Added Referral Fields to to_dict ---
        }
        
    def __repr__(self): return f'<User {self.email}>'



# ... (Category, Product, ProductImage, ProductWeightOption, SerializedInventoryItem, StockMovement, Order, OrderItem, Review, Cart, CartItem models remain the same for now) ...
# ... (ProfessionalDocument, Invoice, InvoiceItem, AuditLog models remain the same) ...
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


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True) 
    description = db.Column(db.Text, nullable=True) 
    long_description = db.Column(db.Text, nullable=True) 
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False, index=True)
    product_code = db.Column(db.String(100), unique=True, nullable=False, index=True) 
    brand = db.Column(db.String(100), index=True, nullable=True)
    type = db.Column(db.Enum(ProductTypeEnum, name="product_type_enum_v2"), nullable=False, default=ProductTypeEnum.SIMPLE, index=True)
    base_price = db.Column(db.Float, nullable=True) # B2C retail price for simple, or fallback for variants
    currency = db.Column(db.String(10), default='EUR')
    main_image_url = db.Column(db.String(255), nullable=True)
    unit_of_measure = db.Column(db.String(50), nullable=True) 
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_featured = db.Column(db.Boolean, default=False, index=True)
    meta_title = db.Column(db.String(255), nullable=True) 
    meta_description = db.Column(db.Text, nullable=True) 
    slug = db.Column(db.String(170), unique=True, nullable=False, index=True)
    preservation_type = db.Column(db.Enum(PreservationTypeEnum, name="preservation_type_enum_v2"), nullable=True, default=PreservationTypeEnum.NOT_SPECIFIED)
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
                ProductWeightOption.is_active == True # Only count stock for active variants
            ).scalar()
            return total_variant_stock or 0
        elif self.type == ProductTypeEnum.SIMPLE:
            # For simple products, stock comes from serialized items without a variant_id
            simple_serialized_stock = db.session.query(
                db.func.count(SerializedInventoryItem.id)
            ).filter(
                SerializedInventoryItem.product_id == self.id,
                SerializedInventoryItem.variant_id == None, # Explicitly no variant
                SerializedInventoryItem.status == SerializedInventoryItemStatusEnum.AVAILABLE
            ).scalar()
            return simple_serialized_stock or 0
        return 0
        
    def to_dict(self, lang_code='fr'): # Default to French for localization
        # Fetch the specific localization or default to None
        loc = self.localizations.filter_by(lang_code=lang_code).first()
        
        # Fallback mechanism for localized fields
        name_display = self.name # Default
        description_display = self.description 
        long_description_display = self.long_description
        meta_title_display = self.meta_title
        meta_description_display = self.meta_description
        
        # New informational fields - ensure they are also localized if needed
        sensory_evaluation_display = None # Placeholder for specific logic
        food_pairings_display = None
        species_display = None
        ideal_uses_display = None # New
        pairing_suggestions_display = None # New


        if lang_code == 'fr':
            if loc and loc.name_fr: name_display = loc.name_fr
            if loc and loc.description_fr: description_display = loc.description_fr
            if loc and loc.long_description_fr: long_description_display = loc.long_description_fr
            if loc and loc.meta_title_fr: meta_title_display = loc.meta_title_fr
            if loc and loc.meta_description_fr: meta_description_display = loc.meta_description_fr
            # Assuming these new fields are also in ProductLocalization
            if loc and loc.sensory_evaluation_fr: sensory_evaluation_display = loc.sensory_evaluation_fr
            if loc and loc.food_pairings_fr: food_pairings_display = loc.food_pairings_fr
            if loc and loc.species_fr: species_display = loc.species_fr
            if loc and loc.ideal_uses_fr: ideal_uses_display = loc.ideal_uses_fr # New
            if loc and loc.pairing_suggestions_fr: pairing_suggestions_display = loc.pairing_suggestions_fr # New
        elif lang_code == 'en':
            if loc and loc.name_en: name_display = loc.name_en
            if loc and loc.description_en: description_display = loc.description_en
            if loc and loc.long_description_en: long_description_display = loc.long_description_en
            if loc and loc.meta_title_en: meta_title_display = loc.meta_title_en
            if loc and loc.meta_description_en: meta_description_display = loc.meta_description_en
            if loc and loc.sensory_evaluation_en: sensory_evaluation_display = loc.sensory_evaluation_en
            if loc and loc.food_pairings_en: food_pairings_display = loc.food_pairings_en
            if loc and loc.species_en: species_display = loc.species_en
            if loc and loc.ideal_uses_en: ideal_uses_display = loc.ideal_uses_en # New
            if loc and loc.pairing_suggestions_en: pairing_suggestions_display = loc.pairing_suggestions_en # New
        
        # Ensure all fields needed by admin form are present, fetching from specific lang attributes
        loc_fr_specific = self.localizations.filter_by(lang_code='fr').first()
        loc_en_specific = self.localizations.filter_by(lang_code='en').first()

        return {
            "id": self.id, 
            "name": name_display, # This will be the localized name based on lang_code for general display
            "name_fr": loc_fr_specific.name_fr if loc_fr_specific and loc_fr_specific.name_fr else self.name,
            "name_en": loc_en_specific.name_en if loc_en_specific and loc_en_specific.name_en else None, # Ensure it sends None if not set
            "product_code": self.product_code, 
            "slug": self.slug, 
            "type": self.type.value if self.type else None, 
            "base_price": self.base_price, # This is the B2C retail price for simple, or fallback for variants
            "is_active": self.is_active, 
            "is_featured": self.is_featured, 
            "category_id": self.category_id, 
            "category_name": self.category.name if self.category else None, # Consider localizing category name here too if needed
            "category_code": self.category.category_code if self.category else None,
            "main_image_url": self.main_image_url, # Path relative to UPLOAD_FOLDER/products/
            "unit_of_measure": self.unit_of_measure,
            "brand": self.brand,
            "currency": self.currency,
            "description": description_display, # Localized short description
            "description_fr": loc_fr_specific.description_fr if loc_fr_specific and loc_fr_specific.description_fr else self.description,
            "description_en": loc_en_specific.description_en if loc_en_specific and loc_en_specific.description_en else None,
            "long_description": long_description_display, # Localized long description
            "long_description_fr": loc_fr_specific.long_description_fr if loc_fr_specific and loc_fr_specific.long_description_fr else self.long_description,
            "long_description_en": loc_en_specific.long_description_en if loc_en_specific and loc_en_specific.long_description_en else None,
            
            "sensory_evaluation": sensory_evaluation_display, # Localized sensory
            "sensory_evaluation_fr": loc_fr_specific.sensory_evaluation_fr if loc_fr_specific else None,
            "sensory_evaluation_en": loc_en_specific.sensory_evaluation_en if loc_en_specific else None,
            
            "food_pairings": food_pairings_display, # Localized pairings
            "food_pairings_fr": loc_fr_specific.food_pairings_fr if loc_fr_specific else None,
            "food_pairings_en": loc_en_specific.food_pairings_en if loc_en_specific else None,
            
            "species": species_display, # Localized species
            "species_fr": loc_fr_specific.species_fr if loc_fr_specific else None,
            "species_en": loc_en_specific.species_en if loc_en_specific else None,
            
            "preservation_type": self.preservation_type.value if self.preservation_type else None,
            "notes_internal": self.notes_internal,
            "supplier_info": self.supplier_info,
            
            "meta_title": meta_title_display, # Localized meta title
            "meta_description": meta_description_display, # Localized meta desc
            
            # For admin display of options and stock:
            "variant_count": self.weight_options.filter_by(is_active=True).count() if self.type == ProductTypeEnum.VARIABLE_WEIGHT else 0,
            "aggregate_stock_quantity": self.aggregate_stock_quantity # Use the property
        }
    def __repr__(self): return f'<Product {self.name}>'


class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    image_url = db.Column(db.String(255), nullable=False) # Path relative to UPLOAD_FOLDER/products/
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
    aggregate_stock_quantity = db.Column(db.Integer, default=0, nullable=False) # Denormalized total stock for this variant
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    product = db.relationship('Product', back_populates='weight_options')
    serialized_items = db.relationship('SerializedInventoryItem', back_populates='variant', lazy='dynamic') # Updated back_populates
    stock_movements = db.relationship('StockMovement', back_populates='variant', lazy='dynamic') # Updated back_populates
    order_items = db.relationship('OrderItem', back_populates='variant', lazy='dynamic') # Updated back_populates
    cart_items = db.relationship('CartItem', back_populates='variant', lazy='dynamic') # Updated back_populates
    b2b_tier_prices_variant = db.relationship('ProductB2BTierPrice', back_populates='variant', lazy='dynamic', cascade="all, delete-orphan")


    __table_args__ = (db.UniqueConstraint('product_id', 'weight_grams', name='uq_product_weight_v2'), # Renamed constraint
                      db.UniqueConstraint('product_id', 'sku_suffix', name='uq_product_sku_suffix_v2')) # Renamed constraint


class SerializedInventoryItem(db.Model):
    __tablename__ = 'serialized_inventory_items'
    id = db.Column(db.Integer, primary_key=True)
    item_uid = db.Column(db.String(100), unique=True, nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id', ondelete='SET NULL'), index=True, nullable=True) # Allow null if variant deleted
    batch_number = db.Column(db.String(100), index=True, nullable=True)
    production_date = db.Column(db.DateTime, nullable=True)
    expiry_date = db.Column(db.DateTime, index=True, nullable=True)
    actual_weight_grams = db.Column(db.Float, nullable=True) 
    cost_price = db.Column(db.Float, nullable=True)
    purchase_price = db.Column(db.Float, nullable=True) # Deprecated or ensure clarity with cost_price
    status = db.Column(db.Enum(SerializedInventoryItemStatusEnum, name="sii_status_enum_v2"), nullable=False, default=SerializedInventoryItemStatusEnum.AVAILABLE, index=True)
    qr_code_url = db.Column(db.String(255), nullable=True) # Relative path to generated QR code PNG
    passport_url = db.Column(db.String(255), nullable=True) # Relative path to generated HTML passport
    label_url = db.Column(db.String(255), nullable=True) # Relative path to generated PDF label
    notes = db.Column(db.Text, nullable=True)
    supplier_id = db.Column(db.Integer, nullable=True) # Potentially FK to a Supplier model
    received_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sold_at = db.Column(db.DateTime, nullable=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id', ondelete='SET NULL'), unique=True, index=True, nullable=True) # Allow null if order item deleted
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
    movement_type = db.Column(db.Enum(StockMovementTypeEnum, name="stock_movement_type_enum_v2"), nullable=False, index=True)
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
    status = db.Column(db.Enum(OrderStatusEnum, name="order_status_enum_v3"), nullable=False, default=OrderStatusEnum.PENDING_PAYMENT, index=True)
    total_amount = db.Column(db.Float, nullable=False) # For B2B this might be HT, for B2C TTC
    currency = db.Column(db.String(10), default='EUR')
    
    shipping_address_line1 = db.Column(db.String(255), nullable=True)
    shipping_address_line2 = db.Column(db.String(255), nullable=True)
    shipping_city = db.Column(db.String(100), nullable=True)
    shipping_postal_code = db.Column(db.String(20), nullable=True)
    shipping_country = db.Column(db.String(100), nullable=True)
    shipping_phone_snapshot = db.Column(db.String(50), nullable=True) # Added for order specific phone


    billing_address_line1 = db.Column(db.String(255), nullable=True)
    billing_address_line2 = db.Column(db.String(255), nullable=True)
    billing_city = db.Column(db.String(100), nullable=True)
    billing_postal_code = db.Column(db.String(20), nullable=True)
    billing_country = db.Column(db.String(100), nullable=True)
    
    payment_method = db.Column(db.String(50), nullable=True)
    payment_transaction_id = db.Column(db.String(100), index=True, nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True) # New
    
    shipping_method = db.Column(db.String(100), nullable=True)
    shipping_cost = db.Column(db.Float, default=0.0)
    tracking_number = db.Column(db.String(100), nullable=True)
    
    notes_customer = db.Column(db.Text, nullable=True) # Notes from customer during checkout
    notes_internal = db.Column(db.Text, nullable=True) # Notes by admin
    
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # B2B specific order fields
    is_b2b_order = db.Column(db.Boolean, default=False, nullable=False, index=True)
    purchase_order_reference = db.Column(db.String(100), nullable=True) # Client's PO number
    quote_request_id = db.Column(db.Integer, db.ForeignKey('quote_requests.id', name='fk_order_quote_request_id'), nullable=True, index=True)
    po_file_path_stored = db.Column(db.String(255), nullable=True) # Path to stored PO file if uploaded

    customer = db.relationship('User', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', lazy='dynamic', cascade="all, delete-orphan")
    stock_movements = db.relationship('StockMovement', back_populates='related_order', lazy='dynamic')
    invoice = db.relationship('Invoice', back_populates='order_link', uselist=False) # Updated backref
    originating_quote_request = db.relationship('QuoteRequest', back_populates='related_order', foreign_keys=[quote_request_id]) # New for B2B quotes

    def to_dict(self): # For API responses, especially admin views
        return {
            "id": self.id, "user_id": self.user_id,
            "customer_email": self.customer.email if self.customer else None,
            "customer_name": f"{self.customer.first_name or ''} {self.customer.last_name or ''}".strip() if self.customer else None,
            "company_name": self.customer.company_name if self.customer and self.customer.company_name else None, # Added company name
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
            "tracking_number": self.tracking_number, # Added tracking number
            "items": [item.to_dict() for item in self.items] if self.items else [] # Use item's to_dict
        }

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True, index=True) # Allow product to be deleted but keep order item
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id', ondelete='SET NULL'), index=True, nullable=True)
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id', ondelete='SET NULL'), unique=True, index=True, nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False) # Price at time of order (HT for B2B, TTC for B2C item if itemized)
    total_price = db.Column(db.Float, nullable=False) # quantity * unit_price
    product_name = db.Column(db.String(150), nullable=True) # Snapshot of product name
    variant_description = db.Column(db.String(100), nullable=True) # Snapshot of variant details
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    order = db.relationship('Order', back_populates='items')
    product = db.relationship('Product', back_populates='order_items')
    variant = db.relationship('ProductWeightOption', back_populates='order_items')
    sold_serialized_item = db.relationship('SerializedInventoryItem', back_populates='order_item_link', foreign_keys=[serialized_item_id])
    
    def to_dict(self): # For API and invoice generation
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
    __table_args__ = ( db.CheckConstraint('rating >= 1 AND rating <= 5', name='ck_review_rating_v2'), # Renamed constraint
                       db.UniqueConstraint('product_id', 'user_id', name='uq_user_product_review_v2') ) # Renamed constraint

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
    file_path = db.Column(db.String(255), nullable=False) # Relative path within configured upload folder
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.Enum(ProfessionalStatusEnum, name="prof_doc_status_enum_v2"), default=ProfessionalStatusEnum.PENDING_REVIEW, index=True)
    reviewed_by_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Admin who reviewed
    reviewed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True) # Admin notes on the document
    
    user = db.relationship('User', back_populates='professional_documents')
    reviewed_by_admin = db.relationship('User', foreign_keys=[reviewed_by_admin_id])


class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='SET NULL'), unique=True, index=True, nullable=True) 
    b2b_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True, nullable=True) # For B2B invoices not directly from an Order
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    issue_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    due_date = db.Column(db.DateTime, index=True, nullable=True) # Due date more relevant for B2B
    total_amount = db.Column(db.Float, nullable=False) # For B2C, this is TTC. For B2B, this is typically Subtotal HT.
    currency = db.Column(db.String(10), default='EUR') 
    status = db.Column(db.Enum(InvoiceStatusEnum, name="invoice_status_enum_v2"), nullable=False, default=InvoiceStatusEnum.DRAFT, index=True)
    pdf_path = db.Column(db.String(255), nullable=True) # Relative path to generated PDF
    notes = db.Column(db.Text, nullable=True) # General notes for the invoice
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # If admin created it manually
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Specific fields for B2C invoices (often paid at order time)
    payment_date = db.Column(db.DateTime, nullable=True) # For B2C, often same as order_date
    # Specific fields for B2B VAT breakdown (more common for B2B)
    subtotal_ht = db.Column(db.Float, nullable=True)
    total_vat_amount = db.Column(db.Float, nullable=True)
    grand_total_ttc = db.Column(db.Float, nullable=True) # For B2B if VAT applied, for B2C this = total_amount
    vat_breakdown = db.Column(db.JSON, nullable=True) # Store as {"rate": "amount", ...} e.g. {"20.0": 10.50}

    # Snapshot of client info for B2B invoices (in case user details change later)
    client_company_name_snapshot = db.Column(db.String(255), nullable=True)
    client_vat_number_snapshot = db.Column(db.String(50), nullable=True)
    client_siret_number_snapshot = db.Column(db.String(50), nullable=True)
    po_reference_snapshot = db.Column(db.String(100), nullable=True) # PO ref for B2B

    items = db.relationship('InvoiceItem', back_populates='invoice', lazy='dynamic', cascade="all, delete-orphan")
    b2b_customer = db.relationship('User', foreign_keys=[b2b_user_id], back_populates='b2b_invoices')
    order_link = db.relationship('Order', back_populates='invoice', foreign_keys=[order_id]) # Updated backref


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False) # Snapshot of product/service description
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False) # Price per unit (HT for B2B, TTC for B2C item if itemized)
    total_price = db.Column(db.Float, nullable=False) # quantity * unit_price (HT or TTC based on context)
    vat_rate = db.Column(db.Float, nullable=True) # Applicable VAT rate for this item (e.g., 20.0 for 20%)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True) # Link to product if applicable
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id', ondelete='SET NULL'), nullable=True) # Link to specific item if applicable
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
    status = db.Column(db.Enum(AuditLogStatusEnum, name="audit_log_status_enum_v2"), default=AuditLogStatusEnum.SUCCESS, index=True)
    acting_user = db.relationship('User', foreign_keys=[user_id], back_populates='audit_logs_initiated')


class NewsletterSubscription(db.Model):
    __tablename__ = 'newsletter_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    subscribed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True, index=True)
    source = db.Column(db.String(100), nullable=True) # e.g., 'footer_form', 'b2b_registration'
    consent = db.Column(db.String(10), nullable=False, default='Y') # 'Y', 'N'
    language_code = db.Column(db.String(5), nullable=True) # Language preference for newsletter
    newsletter_type = db.Column(db.Enum(NewsletterTypeEnum, name="newsletter_type_enum_v1"), default=NewsletterTypeEnum.GENERAL, nullable=False) # Added type

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
    lang_code = db.Column(db.String(5), nullable=False, index=True) # e.g., 'fr', 'en'
    
    name_fr = db.Column(db.String(150), nullable=True) # Changed to nullable if lang_code specific
    name_en = db.Column(db.String(150), nullable=True) # Changed to nullable
    
    description_fr = db.Column(db.Text, nullable=True) # Changed to nullable
    description_en = db.Column(db.Text, nullable=True) # Changed to nullable
    
    long_description_fr = db.Column(db.Text, nullable=True) # Changed to nullable
    long_description_en = db.Column(db.Text, nullable=True) # Changed to nullable
    
    # New informational fields, localized
    sensory_evaluation_fr = db.Column(db.Text, nullable=True)
    sensory_evaluation_en = db.Column(db.Text, nullable=True)
    food_pairings_fr = db.Column(db.Text, nullable=True)
    food_pairings_en = db.Column(db.Text, nullable=True)
    species_fr = db.Column(db.String(255), nullable=True) # Can be text if longer
    species_en = db.Column(db.String(255), nullable=True)
    ideal_uses_fr = db.Column(db.Text, nullable=True) # New
    ideal_uses_en = db.Column(db.Text, nullable=True) # New
    pairing_suggestions_fr = db.Column(db.Text, nullable=True) # New
    pairing_suggestions_en = db.Column(db.Text, nullable=True) # New
    
    meta_title_fr = db.Column(db.String(255), nullable=True)
    meta_title_en = db.Column(db.String(255), nullable=True)
    meta_description_fr = db.Column(db.Text, nullable=True)
    meta_description_en = db.Column(db.Text, nullable=True)
    
    product = db.relationship('Product', back_populates='localizations')
    __table_args__ = (db.UniqueConstraint('product_id', 'lang_code', name='uq_product_lang_v2'),) # Renamed constraint


class CategoryLocalization(db.Model):
    __tablename__ = 'category_localizations'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False, index=True)
    lang_code = db.Column(db.String(5), nullable=False, index=True)
    name_fr = db.Column(db.String(100), nullable=True)
    name_en = db.Column(db.String(100), nullable=True)
    description_fr = db.Column(db.Text, nullable=True)
    description_en = db.Column(db.Text, nullable=True)
    # New informational fields for categories, localized
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
    __table_args__ = (db.UniqueConstraint('category_id', 'lang_code', name='uq_category_lang_v2'),) # Renamed constraint


class GeneratedAsset(db.Model):
    __tablename__ = 'generated_assets'
    id = db.Column(db.Integer, primary_key=True)
    asset_type = db.Column(db.Enum(AssetTypeEnum, name="asset_type_enum_v2"), nullable=False, index=True)
    related_item_uid = db.Column(db.String(100), db.ForeignKey('serialized_inventory_items.item_uid', ondelete='SET NULL'), index=True, nullable=True) 
    related_product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), index=True, nullable=True) # Can be for general product assets not tied to UID
    file_path = db.Column(db.String(255), nullable=False, unique=True) # Relative to ASSET_STORAGE_PATH
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    inventory_item_asset_owner = db.relationship('SerializedInventoryItem', back_populates='generated_assets', foreign_keys=[related_item_uid])
    product_asset_owner = db.relationship('Product', back_populates='generated_assets', foreign_keys=[related_product_id])


class TokenBlocklist(db.Model): # For JWT blocklisting
    __tablename__ = 'token_blocklist'
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False, index=True) # Store expiry of the original token
    def __repr__(self): return f"<TokenBlocklist {self.jti}>"

# New B2B Models
class ProductB2BTierPrice(db.Model):
    __tablename__ = 'product_b2b_tier_prices'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id', ondelete='CASCADE'), nullable=True, index=True) # Null if price is for base simple product
    b2b_tier = db.Column(db.Enum(B2BPricingTierEnum, name="b2b_pricing_tier_enum_v2"), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False) # The specific HT price for this tier and product/variant
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    product = db.relationship('Product', back_populates='b2b_tier_prices')
    variant = db.relationship('ProductWeightOption', back_populates='b2b_tier_prices_variant')
    __table_args__ = (
        db.UniqueConstraint('product_id', 'variant_id', 'b2b_tier', name='uq_product_variant_tier_price'),
    )

class QuoteRequest(db.Model):
    __tablename__ = 'quote_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    request_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.Enum(QuoteRequestStatusEnum, name="quote_request_status_enum_v2"), nullable=False, default=QuoteRequestStatusEnum.PENDING, index=True)
    notes = db.Column(db.Text, nullable=True) # Customer notes
    admin_notes = db.Column(db.Text, nullable=True) # Admin internal notes
    contact_person = db.Column(db.String(150), nullable=True)
    contact_phone = db.Column(db.String(50), nullable=True)
    valid_until = db.Column(db.DateTime, nullable=True) # Expiry date of the quote if sent
    admin_assigned_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Admin handling the quote
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    related_order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True) # Link to order if converted

    user = db.relationship('User', back_populates='quote_requests')
    items = db.relationship('QuoteRequestItem', back_populates='quote_request', lazy='dynamic', cascade="all, delete-orphan")
    related_order = db.relationship('Order', back_populates='originating_quote_request', uselist=False, foreign_keys=[related_order_id]) # Corrected relationship name
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
    notes = db.Column(db.Text, nullable=True) # Item-specific notes
    # Snapshots of product/variant info at time of quote
    product_name_snapshot = db.Column(db.String(255), nullable=True)
    variant_description_snapshot = db.Column(db.String(255), nullable=True)
    product_code_snapshot = db.Column(db.String(100), nullable=True)


    quote_request = db.relationship('QuoteRequest', back_populates='items')
    product = db.relationship('Product') # Direct relationship for easy access
    variant = db.relationship('ProductWeightOption') # Direct relationship

