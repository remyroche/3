# backend/models/order_models.py
from .base import db, BaseModel
from .enums import OrderStatusEnum, InvoiceStatusEnum, QuoteRequestStatusEnum
from datetime import datetime, timezone
from .enums import OrderStatus, PaymentStatus, QuoteStatus

class Quote(BaseModel):
    __tablename__ = 'quotes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('b2b_users.id'), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(QuoteStatus), default=QuoteStatus.PENDING)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    
    # Add a comment field
    comment = db.Column(db.Text, nullable=True)

    items = db.relationship('QuoteItem', backref='quote', lazy=True, cascade="all, delete-orphan")
    user = db.relationship('B2BUser', backref='quotes')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'total_price': self.total_price,
            'status': self.status.value,
            'order_id': self.order_id,
            'comment': self.comment, # Include comment in serialization
            'created_at': self.created_at.isoformat(),
            'items': [item.to_dict() for item in self.items]
            
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.Enum(OrderStatusEnum, name="order_status_enum_v3"), nullable=False, default=OrderStatusEnum.PENDING_PAYMENT, index=True)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='EUR')
    shipping_address_line1 = db.Column(db.String(255), nullable=True)
    shipping_address_line2 = db.Column(db.String(255), nullable=True)
    shipping_city = db.Column(db.String(100), nullable=True)
    shipping_postal_code = db.Column(db.String(20), nullable=True)
    shipping_country = db.Column(db.String(100), nullable=True)
    shipping_phone_snapshot = db.Column(db.String(50), nullable=True)
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
    notes_customer = db.Column(db.Text, nullable=True)
    notes_internal = db.Column(db.Text, nullable=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_b2b_order = db.Column(db.Boolean, default=False, nullable=False, index=True)
    purchase_order_reference = db.Column(db.String(100), nullable=True)
    quote_request_id = db.Column(db.Integer, db.ForeignKey('quote_requests.id', name='fk_order_quote_request_id'), nullable=True, index=True)
    po_file_path_stored = db.Column(db.String(255), nullable=True)

    customer = db.relationship('User', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', lazy='dynamic', cascade="all, delete-orphan")
    stock_movements = db.relationship('StockMovement', back_populates='related_order', lazy='dynamic')
    invoice = db.relationship('Invoice', back_populates='order_link', uselist=False)
    originating_quote_request = db.relationship('QuoteRequest', back_populates='related_order', foreign_keys=[quote_request_id])

    def to_dict(self):
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
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    product_name = db.Column(db.String(150), nullable=True)
    variant_description = db.Column(db.String(100), nullable=True)
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

class QuoteRequest(db.Model):
    __tablename__ = 'quote_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    request_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.Enum(QuoteRequestStatusEnum, name="quote_request_status_enum_v2"), nullable=False, default=QuoteRequestStatusEnum.PENDING, index=True)
    notes = db.Column(db.Text, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    contact_person = db.Column(db.String(150), nullable=True)
    contact_phone = db.Column(db.String(50), nullable=True)
    valid_until = db.Column(db.DateTime, nullable=True)
    admin_assigned_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    related_order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)

    user = db.relationship('User', back_populates='quote_requests')
    items = db.relationship('QuoteRequestItem', back_populates='quote_request', lazy='dynamic', cascade="all, delete-orphan")
    related_order = db.relationship('Order', back_populates='originating_quote_request', uselist=False, foreign_keys=[related_order_id])
    assigned_admin = db.relationship('User', foreign_keys=[admin_assigned_id])

class QuoteRequestItem(db.Model):
    __tablename__ = 'quote_request_items'
    id = db.Column(db.Integer, primary_key=True)
    quote_request_id = db.Column(db.Integer, db.ForeignKey('quote_requests.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id', ondelete='SET NULL'), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    requested_price_ht = db.Column(db.Float, nullable=True)
    quoted_price_ht = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    product_name_snapshot = db.Column(db.String(255), nullable=True)
    variant_description_snapshot = db.Column(db.String(255), nullable=True)
    product_code_snapshot = db.Column(db.String(100), nullable=True)

    quote_request = db.relationship('QuoteRequest', back_populates='items')
    product = db.relationship('Product')
    variant = db.relationship('ProductWeightOption')

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='SET NULL'), unique=True, index=True, nullable=True) 
    b2b_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True, nullable=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    issue_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    due_date = db.Column(db.DateTime, index=True, nullable=True)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='EUR') 
    status = db.Column(db.Enum(InvoiceStatusEnum, name="invoice_status_enum_v2"), nullable=False, default=InvoiceStatusEnum.DRAFT, index=True)
    pdf_path = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    payment_date = db.Column(db.DateTime, nullable=True)
    subtotal_ht = db.Column(db.Float, nullable=True)
    total_vat_amount = db.Column(db.Float, nullable=True)
    grand_total_ttc = db.Column(db.Float, nullable=True)
    net_to_pay = db.Column(db.Float, nullable=True)
    vat_breakdown = db.Column(db.JSON, nullable=True)
    client_company_name_snapshot = db.Column(db.String(255), nullable=True)
    client_vat_number_snapshot = db.Column(db.String(50), nullable=True)
    client_siret_number_snapshot = db.Column(db.String(50), nullable=True)
    po_reference_snapshot = db.Column(db.String(100), nullable=True)

    items = db.relationship('InvoiceItem', back_populates='invoice', lazy='dynamic', cascade="all, delete-orphan")
    b2b_customer = db.relationship('User', foreign_keys=[b2b_user_id], back_populates='b2b_invoices')
    order_link = db.relationship('Order', back_populates='invoice', foreign_keys=[order_id])

class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    vat_rate = db.Column(db.Float, nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True) 
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id', ondelete='SET NULL'), nullable=True) 
    invoice = db.relationship('Invoice', back_populates='items')
