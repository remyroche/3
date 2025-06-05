py
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
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"

class ProductTypeEnum(enum.Enum):
    SIMPLE = "simple"
    VARIABLE_WEIGHT = "variable_weight"

class PreservationTypeEnum(enum.Enum): # New Enum for preservation_type
    FRESH = "frais"
    PRESERVED_CANNED = "conserve" # Appertisé
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


# --- Model Definitions ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256)) 
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    role = db.Column(db.Enum(UserRoleEnum, name="user_role_enum"), nullable=False, default=UserRoleEnum.B2C_CUSTOMER, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False, index=True) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    company_name = db.Column(db.String(120))
    vat_number = db.Column(db.String(50))
    siret_number = db.Column(db.String(50))
    professional_status = db.Column(db.Enum(ProfessionalStatusEnum, name="professional_status_enum"), index=True) 
    reset_token = db.Column(db.String(100), index=True)
    reset_token_expires_at = db.Column(db.DateTime)
    verification_token = db.Column(db.String(100), index=True)
    verification_token_expires_at = db.Column(db.DateTime)
    magic_link_token = db.Column(db.String(100), index=True, nullable=True)
    magic_link_expires_at = db.Column(db.DateTime, nullable=True)
    totp_secret = db.Column(db.String(100)) 
    is_totp_enabled = db.Column(db.Boolean, default=False, nullable=False)
    simplelogin_user_id = db.Column(db.String(255), unique=True, nullable=True, index=True) 
    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    reviews = db.relationship('Review', backref='user', lazy='dynamic')
    cart = db.relationship('Cart', backref='user', uselist=False, lazy='joined') 
    professional_documents = db.relationship('ProfessionalDocument', backref='user', lazy='dynamic')
    b2b_invoices = db.relationship('Invoice', foreign_keys='Invoice.b2b_user_id', backref='b2b_user', lazy='dynamic')
    audit_logs_initiated = db.relationship('AuditLog', foreign_keys='AuditLog.user_id', backref='acting_user', lazy='dynamic')
    
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password) if self.password_hash else False
    
    @staticmethod
    def validate_password(password):
        if not password or len(password) < 8: return "auth.error.password_too_short" # Key for frontend translation
        if not re.search(r"[A-Z]", password): return "auth.error.password_no_uppercase"
        if not re.search(r"[a-z]", password): return "auth.error.password_no_lowercase"
        if not re.search(r"[0-9]", password): return "auth.error.password_no_digit"
        # if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): return "auth.error.password_no_special" # Optional
        return None # Valid

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
            "company_name": self.company_name, 
            "professional_status": self.professional_status.value if self.professional_status else None, 
            "is_totp_enabled": self.is_totp_enabled, 
            "is_admin": self.role == UserRoleEnum.ADMIN
        }
    def __repr__(self): return f'<User {self.email}>'

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False) # Primary name (e.g., French)
    description = db.Column(db.Text) # Primary description
    image_url = db.Column(db.String(255))
    category_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), index=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    products = db.relationship('Product', backref='category', lazy='dynamic')
    children = db.relationship('Category', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    localizations = db.relationship('CategoryLocalization', backref='category', lazy='dynamic', cascade="all, delete-orphan")
    
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
    name = db.Column(db.String(150), nullable=False, index=True) # Primary/default language name
    description = db.Column(db.Text) # Primary/default language short description
    long_description = db.Column(db.Text) # Primary/default language long description
    
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False, index=True)
    product_code = db.Column(db.String(100), unique=True, nullable=False, index=True) 
    brand = db.Column(db.String(100), index=True)
    type = db.Column(db.Enum(ProductTypeEnum, name="product_type_enum"), nullable=False, default=ProductTypeEnum.SIMPLE, index=True)
    base_price = db.Column(db.Float) # Only for 'simple' type products
    currency = db.Column(db.String(10), default='EUR')
    main_image_url = db.Column(db.String(255))
    
    # Stock quantity and low_stock_threshold are REMOVED from Product model.
    # aggregate_stock_quantity will be a calculated property or managed by the inventory system.
    # aggregate_stock_weight_grams = db.Column(db.Float, nullable=True) # This can stay if it represents a standard weight, or it's calculated
    
    unit_of_measure = db.Column(db.String(50)) # e.g., "piece", "kg", "100g"
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_featured = db.Column(db.Boolean, default=False, index=True)
    
    meta_title = db.Column(db.String(255)) # For SEO, can be localized via ProductLocalization
    meta_description = db.Column(db.Text) # For SEO, can be localized

    slug = db.Column(db.String(170), unique=True, nullable=False, index=True)
    
    # New informational fields (non-translatable directly on Product model)
    preservation_type = db.Column(db.Enum(PreservationTypeEnum, name="preservation_type_enum"), nullable=True, default=PreservationTypeEnum.NOT_SPECIFIED)
    notes_internal = db.Column(db.Text) # Admin-only notes
    supplier_info = db.Column(db.String(255)) # If this is a simple text field

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    images = db.relationship('ProductImage', backref='product', lazy='dynamic', cascade="all, delete-orphan")
    weight_options = db.relationship('ProductWeightOption', backref='product', lazy='dynamic', cascade="all, delete-orphan")
    serialized_items = db.relationship('SerializedInventoryItem', backref='product', lazy='dynamic')
    stock_movements = db.relationship('StockMovement', backref='product', lazy='dynamic')
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')
    reviews = db.relationship('Review', backref='product', lazy='dynamic')
    cart_items = db.relationship('CartItem', backref='product', lazy='dynamic')
    localizations = db.relationship('ProductLocalization', backref='product', lazy='dynamic', cascade="all, delete-orphan")
    generated_assets = db.relationship('GeneratedAsset', foreign_keys='GeneratedAsset.related_product_id', backref='product_asset_owner', lazy='dynamic')

    @property
    def aggregate_stock_quantity(self):
        """Calculates total stock quantity across variants or returns direct stock for simple products."""
        if self.type == ProductTypeEnum.VARIABLE_WEIGHT:
            return db.session.query(db.func.sum(ProductWeightOption.aggregate_stock_quantity)).filter_by(product_id=self.id, is_active=True).scalar() or 0
        elif self.type == ProductTypeEnum.SIMPLE:
            # If simple products have stock managed in SerializedInventoryItem directly (unlikely without variants)
            # or if you decide to add a stock field back for non-serialized simple items:
            # For now, assuming stock for 'simple' is also derived from inventory system or is 0 if not explicitly tracked.
            # This property might need to sum from SerializedInventoryItem if simple products also become serialized
            # or from a new `simple_product_stock` table.
            # For this iteration, let's assume it's 0 if not variable, as stock is managed in inventory.
            # The 'admin_manage_inventory.html' page has a section for "Ajuster Stock Agrégé Global (Non-Sérialisé)"
            # which would update a different stock record, perhaps on Product itself if we add `current_stock_simple`
            # or on a dedicated stock table.
            # For now, to avoid adding a direct stock field back yet:
            return 0 # Placeholder - true stock for simple products comes from inventory management
        return 0
        
    def to_dict(self, lang_code='fr'): # Default to French for admin view
        loc = self.localizations.filter_by(lang_code=lang_code).first()
        
        return {
            "id": self.id, 
            "name": self.name, # Default name
            "name_fr": loc.name_fr if loc and loc.name_fr else self.name,
            "name_en": loc.name_en if loc and loc.name_en else self.name, # Fallback to default name if EN not present
            "product_code": self.product_code, 
            "slug": self.slug, 
            "type": self.type.value if self.type else None, 
            "base_price": self.base_price, 
            "is_active": self.is_active, 
            "is_featured": self.is_featured, 
            "category_id": self.category_id, 
            "category_name": self.category.name if self.category else None,
            "category_code": self.category.category_code if self.category else None,
            "main_image_url": self.main_image_url,
            # aggregate_stock_quantity is now a property, not a direct field
            # "aggregate_stock_weight_grams": self.aggregate_stock_weight_grams,
            "unit_of_measure": self.unit_of_measure,
            "brand": self.brand,
            "currency": self.currency,
            "description": self.description, # Default short description
            "description_fr": loc.description_fr if loc and loc.description_fr else self.description,
            "description_en": loc.description_en if loc and loc.description_en else self.description,
            "long_description": self.long_description, # Default long description
            "long_description_fr": loc.long_description_fr if loc and loc.long_description_fr else self.long_description,
            "long_description_en": loc.long_description_en if loc and loc.long_description_en else self.long_description,
            "sensory_evaluation_fr": loc.sensory_evaluation_fr if loc else None,
            "sensory_evaluation_en": loc.sensory_evaluation_en if loc else None,
            "food_pairings_fr": loc.food_pairings_fr if loc else None,
            "food_pairings_en": loc.food_pairings_en if loc else None,
            "species_fr": loc.species_fr if loc else None,
            "species_en": loc.species_en if loc else None,
            "preservation_type": self.preservation_type.value if self.preservation_type else None,
            "notes_internal": self.notes_internal,
            "supplier_info": self.supplier_info,
            "meta_title": loc.meta_title if loc and loc.meta_title else self.meta_title,
            "meta_description": loc.meta_description if loc and loc.meta_description else self.meta_description,
            "variant_count": self.weight_options.count() if self.type == ProductTypeEnum.VARIABLE_WEIGHT else 0
        }
    def __repr__(self): return f'<Product {self.name}>'

class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    image_url = db.Column(db.String(255), nullable=False) # Relative to UPLOAD_FOLDER
    alt_text = db.Column(db.String(255))
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class ProductWeightOption(db.Model): # Represents a variant for variable_weight products
    __tablename__ = 'product_weight_options'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    weight_grams = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    sku_suffix = db.Column(db.String(50), nullable=False) 
    # Stock for variants is managed here (or by sum of serialized items if applicable)
    aggregate_stock_quantity = db.Column(db.Integer, default=0, nullable=False) 
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    serialized_items = db.relationship('SerializedInventoryItem', backref='variant', lazy='dynamic')
    stock_movements = db.relationship('StockMovement', backref='variant', lazy='dynamic')
    order_items = db.relationship('OrderItem', backref='variant', lazy='dynamic')
    cart_items = db.relationship('CartItem', backref='variant', lazy='dynamic')
    __table_args__ = (db.UniqueConstraint('product_id', 'weight_grams', name='uq_product_weight'),
                      db.UniqueConstraint('product_id', 'sku_suffix', name='uq_product_sku_suffix'))

class SerializedInventoryItem(db.Model): # For items with unique tracking
    __tablename__ = 'serialized_inventory_items'
    id = db.Column(db.Integer, primary_key=True)
    item_uid = db.Column(db.String(100), unique=True, nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id'), index=True) # Link to variant if applicable
    batch_number = db.Column(db.String(100), index=True)
    production_date = db.Column(db.DateTime)
    expiry_date = db.Column(db.DateTime, index=True)
    actual_weight_grams = db.Column(db.Float) # For items sold by exact weight
    cost_price = db.Column(db.Float)
    purchase_price = db.Column(db.Float) # If different from cost_price (e.g. landed cost)
    status = db.Column(db.Enum(SerializedInventoryItemStatusEnum, name="sii_status_enum"), nullable=False, default=SerializedInventoryItemStatusEnum.AVAILABLE, index=True)
    qr_code_url = db.Column(db.String(255)) # Path to generated QR code image
    passport_url = db.Column(db.String(255)) # Path to generated HTML passport
    label_url = db.Column(db.String(255)) # Path to generated PDF label
    notes = db.Column(db.Text)
    supplier_id = db.Column(db.Integer) # Could link to a Supplier model if needed
    received_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sold_at = db.Column(db.DateTime)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id'), unique=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    stock_movements = db.relationship('StockMovement', backref='serialized_item', lazy='dynamic')
    generated_assets = db.relationship('GeneratedAsset', primaryjoin="SerializedInventoryItem.item_uid == GeneratedAsset.related_item_uid", foreign_keys='GeneratedAsset.related_item_uid', backref='inventory_item_asset_owner', lazy='dynamic')
    def to_dict(self): return {"id": self.id, "item_uid": self.item_uid, "product_id": self.product_id, "variant_id": self.variant_id, "batch_number": self.batch_number, "production_date": self.production_date.isoformat() if self.production_date else None, "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None, "status": self.status.value if self.status else None, "notes": self.notes, "product_name": self.product.name if self.product else None,  "variant_sku_suffix": self.variant.sku_suffix if self.variant else None}

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id'), index=True) # For variant-level stock
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id'), index=True) # For serialized items
    movement_type = db.Column(db.Enum(StockMovementTypeEnum, name="stock_movement_type_enum"), nullable=False, index=True)
    quantity_change = db.Column(db.Integer) # For count-based stock (can be + or -)
    weight_change_grams = db.Column(db.Float) # For weight-based stock (can be + or -)
    reason = db.Column(db.Text) # E.g., "Sale", "Stock Adjustment", "Damage"
    related_order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), index=True)
    related_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True) # Admin/Staff who made adjustment
    movement_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    notes = db.Column(db.Text)
    def to_dict(self): return {"id": self.id, "product_id": self.product_id, "variant_id": self.variant_id, "serialized_item_id": self.serialized_item_id, "movement_type": self.movement_type.value if self.movement_type else None, "quantity_change": self.quantity_change, "weight_change_grams": self.weight_change_grams, "reason": self.reason, "movement_date": self.movement_date.isoformat(), "notes": self.notes}

class Order(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.Enum(OrderStatusEnum, name="order_status_enum"), nullable=False, default=OrderStatusEnum.PENDING_PAYMENT, index=True)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='EUR')
    shipping_address_line1 = db.Column(db.String(255)); shipping_address_line2 = db.Column(db.String(255)); shipping_city = db.Column(db.String(100)); shipping_postal_code = db.Column(db.String(20)); shipping_country = db.Column(db.String(100))
    billing_address_line1 = db.Column(db.String(255)); billing_address_line2 = db.Column(db.String(255)); billing_city = db.Column(db.String(100)); billing_postal_code = db.Column(db.String(20)); billing_country = db.Column(db.String(100))
    payment_method = db.Column(db.String(50)); payment_transaction_id = db.Column(db.String(100), index=True)
    shipping_method = db.Column(db.String(100)); shipping_cost = db.Column(db.Float, default=0.0); tracking_number = db.Column(db.String(100))
    notes_customer = db.Column(db.Text); notes_internal = db.Column(db.Text)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), unique=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc)); updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade="all, delete-orphan")
    stock_movements = db.relationship('StockMovement', backref='related_order', lazy='dynamic')
    invoice = db.relationship('Invoice', backref=db.backref('order_link', uselist=False)) 


class OrderItem(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id'), index=True)
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id'), unique=True, index=True)
    quantity = db.Column(db.Integer, nullable=False); unit_price = db.Column(db.Float, nullable=False); total_price = db.Column(db.Float, nullable=False)
    product_name = db.Column(db.String(150)); variant_description = db.Column(db.String(100)) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sold_serialized_item = db.relationship('SerializedInventoryItem', backref='order_item_link', foreign_keys=[serialized_item_id], uselist=False)


class Review(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False) 
    comment = db.Column(db.Text)
    review_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    is_approved = db.Column(db.Boolean, default=False, index=True)
    __table_args__ = (
        db.CheckConstraint('rating >= 1 AND rating <= 5', name='ck_review_rating'),
        db.UniqueConstraint('product_id', 'user_id', name='uq_user_product_review') 
    )

class Cart(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'carts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, index=True) 
    session_id = db.Column(db.String(255), unique=True, index=True) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    items = db.relationship('CartItem', backref='cart', lazy='dynamic', cascade="all, delete-orphan")


class CartItem(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id'), index=True) 
    quantity = db.Column(db.Integer, nullable=False)
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class ProfessionalDocument(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'professional_documents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    document_type = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=False) 
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.Enum(ProfessionalStatusEnum, name="prof_doc_status_enum"), default=ProfessionalStatusEnum.PENDING_REVIEW, index=True) 
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id')) 
    reviewed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)


class Invoice(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), unique=True, index=True) 
    b2b_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True) 
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    issue_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    due_date = db.Column(db.DateTime, index=True)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='EUR') 
    status = db.Column(db.Enum(InvoiceStatusEnum, name="invoice_status_enum"), nullable=False, default=InvoiceStatusEnum.DRAFT, index=True) 
    pdf_path = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    items = db.relationship('InvoiceItem', backref='invoice', lazy='dynamic', cascade="all, delete-orphan")


class InvoiceItem(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id')) 
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id')) 


class AuditLog(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True, nullable=True) 
    action = db.Column(db.String(255), nullable=False, index=True)
    target_type = db.Column(db.String(50), index=True) 
    target_id = db.Column(db.Integer, index=True)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.Enum(AuditLogStatusEnum, name="audit_log_status_enum"), default=AuditLogStatusEnum.SUCCESS, index=True) 


class NewsletterSubscription(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'newsletter_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    subscribed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True, index=True)
    source = db.Column(db.String(100)) 
    consent = db.Column(db.String(10), nullable=False, default='Y') 
    language_code = db.Column(db.String(5)) 


class Setting(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'settings'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ProductLocalization(db.Model):
    __tablename__ = 'product_localizations'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    lang_code = db.Column(db.String(5), nullable=False, index=True) 
    
    name_fr = db.Column(db.String(150)) # Retained for direct access if lang_code is 'fr'
    name_en = db.Column(db.String(150)) # Retained for direct access if lang_code is 'en'
    
    description_fr = db.Column(db.Text) # Short description in FR
    description_en = db.Column(db.Text) # Short description in EN
    
    long_description_fr = db.Column(db.Text) # Long description in FR
    long_description_en = db.Column(db.Text) # Long description in EN
    
    # New translatable fields
    sensory_evaluation_fr = db.Column(db.Text)
    sensory_evaluation_en = db.Column(db.Text)
    food_pairings_fr = db.Column(db.Text)
    food_pairings_en = db.Column(db.Text)
    species_fr = db.Column(db.String(255)) # Assuming species is text, can be localized
    species_en = db.Column(db.String(255))
    
    # SEO related fields (can also be localized)
    meta_title_fr = db.Column(db.String(255))
    meta_title_en = db.Column(db.String(255))
    meta_description_fr = db.Column(db.Text)
    meta_description_en = db.Column(db.Text)
    
    # Fields that were in CategoryLocalization and might be better per-product
    ideal_uses_fr = db.Column(db.Text) 
    ideal_uses_en = db.Column(db.Text)
    pairing_suggestions_fr = db.Column(db.Text)
    pairing_suggestions_en = db.Column(db.Text)

    __table_args__ = (db.UniqueConstraint('product_id', 'lang_code', name='uq_product_lang'),)

class CategoryLocalization(db.Model):
    # ... (Consider if any fields moved from here to ProductLocalization should be removed or kept if they are truly category-level generalities) ...
    # For now, keeping structure as is, but note potential redundancy with ProductLocalization for fields like species, pairings if they are product-specific.
    __tablename__ = 'category_localizations'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False, index=True)
    lang_code = db.Column(db.String(5), nullable=False, index=True)
    name_fr = db.Column(db.String(100))
    name_en = db.Column(db.String(100))
    description_fr = db.Column(db.Text)
    description_en = db.Column(db.Text)
    
    # These might be too general if products within a category vary significantly
    species_fr = db.Column(db.Text) 
    species_en = db.Column(db.Text)
    main_ingredients_fr = db.Column(db.Text) 
    main_ingredients_en = db.Column(db.Text)
    ingredients_notes_fr = db.Column(db.Text) 
    ingredients_notes_en = db.Column(db.Text)
    fresh_vs_preserved_fr = db.Column(db.Text) 
    fresh_vs_preserved_en = db.Column(db.Text)
    size_details_fr = db.Column(db.Text) 
    size_details_en = db.Column(db.Text)
    pairings_fr = db.Column(db.Text) 
    pairings_en = db.Column(db.Text)
    weight_info_fr = db.Column(db.Text) 
    weight_info_en = db.Column(db.Text)
    category_notes_fr = db.Column(db.Text) 
    category_notes_en = db.Column(db.Text)
    __table_args__ = (db.UniqueConstraint('category_id', 'lang_code', name='uq_category_lang'),)


class GeneratedAsset(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'generated_assets'
    id = db.Column(db.Integer, primary_key=True)
    asset_type = db.Column(db.Enum(AssetTypeEnum, name="asset_type_enum"), nullable=False, index=True) 
    related_item_uid = db.Column(db.String(100), db.ForeignKey('serialized_inventory_items.item_uid', ondelete='SET NULL'), index=True, nullable=True) # Allow null if item deleted
    related_product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), index=True, nullable=True) # Cascade if product deleted
    file_path = db.Column(db.String(255), nullable=False, unique=True) 
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class TokenBlocklist(db.Model):
    # ... (no changes needed here for this request) ...
    __tablename__ = 'token_blocklist'
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False, index=True)

    def __repr__(self):
        return f"<TokenBlocklist {self.jti}>"
