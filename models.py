from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
import enum
import pyotp 
from flask import current_app 

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256)) 
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    role = db.Column(db.String(50), nullable=False, default='b2c_customer', index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False, index=True) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    company_name = db.Column(db.String(120))
    vat_number = db.Column(db.String(50))
    siret_number = db.Column(db.String(50))
    professional_status = db.Column(db.String(50), index=True) 
    
    reset_token = db.Column(db.String(100), index=True)
    reset_token_expires_at = db.Column(db.DateTime)
    verification_token = db.Column(db.String(100), index=True)
    verification_token_expires_at = db.Column(db.DateTime)
    
    totp_secret = db.Column(db.String(100)) 
    is_totp_enabled = db.Column(db.Boolean, default=False, nullable=False)
    
    simplelogin_user_id = db.Column(db.String(255), unique=True, nullable=True, index=True) 

    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    reviews = db.relationship('Review', backref='user', lazy='dynamic')
    cart = db.relationship('Cart', backref='user', uselist=False, lazy='joined')
    professional_documents = db.relationship('ProfessionalDocument', backref='user', lazy='dynamic')
    b2b_invoices = db.relationship('Invoice', foreign_keys='Invoice.b2b_user_id', backref='b2b_user', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', foreign_keys='AuditLog.user_id', backref='acting_user', lazy='dynamic')


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash: 
            return False
        return check_password_hash(self.password_hash, password)

    def generate_totp_secret(self):
        self.totp_secret = pyotp.random_base32()
        # Do not enable TOTP yet, just generate the secret. Enable upon verification.
        # self.is_totp_enabled = False 
        return self.totp_secret

    def get_totp_uri(self, issuer_name=None):
        if not self.totp_secret:
            # It's good practice to generate it if it doesn't exist when URI is requested for setup
            self.generate_totp_secret() 
            # The caller (e.g., route handler) should ensure this gets saved if it's a new secret.
            
        effective_issuer_name = issuer_name or current_app.config.get('TOTP_ISSUER_NAME', 'Maison Truvra')
        
        # Ensure totp_secret is available after potential generation
        if not self.totp_secret:
             # This case should ideally not be hit if generate_totp_secret works
            raise ValueError("TOTP secret could not be generated or retrieved for URI creation.")

        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.email, 
            issuer_name=effective_issuer_name
        )

    def verify_totp(self, code_attempt, for_time=None, window=1):
        """
        Verifies a TOTP code against the user's secret.
        Allows checking against a specific time and window for flexibility.
        Returns True if valid, False otherwise.
        """
        if not self.totp_secret: # Cannot verify if no secret is set
            return False 
        # is_totp_enabled check should be done by the caller before attempting verification for login,
        # but for setup, we verify against the secret even if not yet enabled.
        
        totp_instance = pyotp.TOTP(self.totp_secret)
        return totp_instance.verify(code_attempt, for_time=for_time, window=window)


    def to_dict(self): 
        return {
            "id": self.id, "email": self.email, "first_name": self.first_name,
            "last_name": self.last_name, "role": self.role, "is_active": self.is_active,
            "is_verified": self.is_verified, "company_name": self.company_name,
            "professional_status": self.professional_status, "is_totp_enabled": self.is_totp_enabled,
            "is_admin": self.role == 'admin' 
        }

    def __repr__(self):
        return f'<User {self.email}>'

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
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

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
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
    name = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), index=True)
    product_code = db.Column(db.String(100), unique=True, nullable=False, index=True)
    sku_prefix = db.Column(db.String(100), unique=True, index=True)
    brand = db.Column(db.String(100), index=True)
    type = db.Column(db.String(50), nullable=False, default='simple', index=True)
    base_price = db.Column(db.Float)
    currency = db.Column(db.String(10), default='EUR')
    main_image_url = db.Column(db.String(255))
    aggregate_stock_quantity = db.Column(db.Integer, default=0)
    aggregate_stock_weight_grams = db.Column(db.Float)
    unit_of_measure = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_featured = db.Column(db.Boolean, default=False, index=True)
    meta_title = db.Column(db.String(255))
    meta_description = db.Column(db.Text)
    slug = db.Column(db.String(170), unique=True, nullable=False, index=True)
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
    def to_dict(self): 
        return {
            "id": self.id, "name": self.name, "product_code": self.product_code,
            "slug": self.slug, "type": self.type, "base_price": self.base_price,
            "is_active": self.is_active, "is_featured": self.is_featured,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "main_image_url": self.main_image_url, 
            "aggregate_stock_quantity": self.aggregate_stock_quantity
        }
    def __repr__(self): return f'<Product {self.name}>'

class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    image_url = db.Column(db.String(255), nullable=False)
    alt_text = db.Column(db.String(255))
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class ProductWeightOption(db.Model):
    __tablename__ = 'product_weight_options'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    weight_grams = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    sku_suffix = db.Column(db.String(50), nullable=False)
    aggregate_stock_quantity = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    serialized_items = db.relationship('SerializedInventoryItem', backref='variant', lazy='dynamic')
    stock_movements = db.relationship('StockMovement', backref='variant', lazy='dynamic')
    order_items = db.relationship('OrderItem', backref='variant', lazy='dynamic')
    cart_items = db.relationship('CartItem', backref='variant', lazy='dynamic')
    __table_args__ = (db.UniqueConstraint('product_id', 'weight_grams', name='uq_product_weight'),
                      db.UniqueConstraint('product_id', 'sku_suffix', name='uq_product_sku_suffix'))

class SerializedInventoryItem(db.Model):
    __tablename__ = 'serialized_inventory_items'
    id = db.Column(db.Integer, primary_key=True)
    item_uid = db.Column(db.String(100), unique=True, nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id'), index=True)
    batch_number = db.Column(db.String(100), index=True)
    production_date = db.Column(db.DateTime)
    expiry_date = db.Column(db.DateTime, index=True)
    actual_weight_grams = db.Column(db.Float)
    cost_price = db.Column(db.Float)
    purchase_price = db.Column(db.Float)
    status = db.Column(db.String(50), nullable=False, default='available', index=True)
    qr_code_url = db.Column(db.String(255))
    passport_url = db.Column(db.String(255))
    label_url = db.Column(db.String(255))
    notes = db.Column(db.Text)
    supplier_id = db.Column(db.Integer)
    received_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sold_at = db.Column(db.DateTime)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id'), unique=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    stock_movements = db.relationship('StockMovement', backref='serialized_item', lazy='dynamic')
    generated_assets = db.relationship('GeneratedAsset', foreign_keys='GeneratedAsset.related_item_uid', backref='inventory_item_asset_owner', lazy='dynamic')
    def to_dict(self):
        return {
            "id": self.id, "item_uid": self.item_uid, "product_id": self.product_id,
            "variant_id": self.variant_id, "batch_number": self.batch_number,
            "production_date": self.production_date.isoformat() if self.production_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "status": self.status, "notes": self.notes,
            "product_name": self.product.name if self.product else None, 
            "variant_sku_suffix": self.variant.sku_suffix if self.variant else None,
        }

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id'), index=True)
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id'), index=True)
    movement_type = db.Column(db.String(50), nullable=False, index=True)
    quantity_change = db.Column(db.Integer)
    weight_change_grams = db.Column(db.Float)
    reason = db.Column(db.Text)
    related_order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), index=True)
    related_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    movement_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    notes = db.Column(db.Text)
    def to_dict(self): 
        return {
            "id": self.id, "product_id": self.product_id, "variant_id": self.variant_id,
            "serialized_item_id": self.serialized_item_id, "movement_type": self.movement_type,
            "quantity_change": self.quantity_change, "reason": self.reason,
            "movement_date": self.movement_date.isoformat(), "notes": self.notes
        }

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.String(50), nullable=False, default='pending_payment', index=True)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='EUR')
    shipping_address_line1 = db.Column(db.String(255))
    shipping_address_line2 = db.Column(db.String(255))
    shipping_city = db.Column(db.String(100))
    shipping_postal_code = db.Column(db.String(20))
    shipping_country = db.Column(db.String(100))
    billing_address_line1 = db.Column(db.String(255))
    billing_address_line2 = db.Column(db.String(255))
    billing_city = db.Column(db.String(100))
    billing_postal_code = db.Column(db.String(20))
    billing_country = db.Column(db.String(100))
    payment_method = db.Column(db.String(50))
    payment_transaction_id = db.Column(db.String(100), index=True)
    shipping_method = db.Column(db.String(100))
    shipping_cost = db.Column(db.Float, default=0.0)
    tracking_number = db.Column(db.String(100))
    notes_customer = db.Column(db.Text)
    notes_internal = db.Column(db.Text)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), unique=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade="all, delete-orphan")
    stock_movements = db.relationship('StockMovement', backref='related_order', lazy='dynamic')
    invoice = db.relationship('Invoice', backref=db.backref('order_link', uselist=False)) 

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id'), index=True)
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id'), unique=True, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False) 
    total_price = db.Column(db.Float, nullable=False)
    product_name = db.Column(db.String(150)) 
    variant_description = db.Column(db.String(100)) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sold_serialized_item = db.relationship('SerializedInventoryItem', backref='order_item_link', foreign_keys=[serialized_item_id], uselist=False)

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False) 
    comment = db.Column(db.Text)
    review_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    is_approved = db.Column(db.Boolean, default=False, index=True)

class Cart(db.Model):
    __tablename__ = 'carts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, index=True) 
    session_id = db.Column(db.String(255), unique=True, index=True) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    items = db.relationship('CartItem', backref='cart', lazy='dynamic', cascade="all, delete-orphan")

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id'), index=True) 
    quantity = db.Column(db.Integer, nullable=False)
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class ProfessionalDocument(db.Model):
    __tablename__ = 'professional_documents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    document_type = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(50), default='pending_review', index=True) 
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id')) 
    reviewed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), unique=True, index=True) 
    b2b_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True) 
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    issue_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    due_date = db.Column(db.DateTime, index=True)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='EUR') 
    status = db.Column(db.String(50), nullable=False, default='draft', index=True) 
    pdf_path = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    items = db.relationship('InvoiceItem', backref='invoice', lazy='dynamic', cascade="all, delete-orphan")

class InvoiceItem(db.Model):
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
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True) 
    username = db.Column(db.String(120)) 
    action = db.Column(db.String(255), nullable=False, index=True)
    target_type = db.Column(db.String(50), index=True) 
    target_id = db.Column(db.Integer, index=True)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.String(20), default='success', index=True) 

class NewsletterSubscription(db.Model):
    __tablename__ = 'newsletter_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    subscribed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True, index=True)
    source = db.Column(db.String(100)) 
    consent = db.Column(db.String(10), nullable=False, default='Y') 

class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ProductLocalization(db.Model):
    __tablename__ = 'product_localizations'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    lang_code = db.Column(db.String(5), nullable=False) 
    name_fr = db.Column(db.String(150))
    name_en = db.Column(db.String(150))
    description_fr = db.Column(db.Text)
    description_en = db.Column(db.Text)
    short_description_fr = db.Column(db.Text)
    short_description_en = db.Column(db.Text)
    ideal_uses_fr = db.Column(db.Text)
    ideal_uses_en = db.Column(db.Text)
    pairing_suggestions_fr = db.Column(db.Text)
    pairing_suggestions_en = db.Column(db.Text)
    sensory_description_fr = db.Column(db.Text)
    sensory_description_en = db.Column(db.Text)
    __table_args__ = (db.UniqueConstraint('product_id', 'lang_code', name='uq_product_lang'),)

class CategoryLocalization(db.Model):
    __tablename__ = 'category_localizations'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    lang_code = db.Column(db.String(5), nullable=False)
    name_fr = db.Column(db.String(100))
    name_en = db.Column(db.String(100))
    description_fr = db.Column(db.Text)
    description_en = db.Column(db.Text)
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
    __tablename__ = 'generated_assets'
    id = db.Column(db.Integer, primary_key=True)
    asset_type = db.Column(db.String(50), nullable=False, index=True) 
    related_item_uid = db.Column(db.String(100), db.ForeignKey('serialized_inventory_items.item_uid'), index=True)
    related_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), index=True)
    file_path = db.Column(db.String(255), nullable=False, unique=True)
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
