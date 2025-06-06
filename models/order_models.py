# backend/models/order_models.py
from .base import db
from .enums import OrderStatusEnum, InvoiceStatusEnum, QuoteRequestStatusEnum
from datetime import datetime, timezone

class Order(db.Model):
    __tablename__ = 'orders'
    # ... (full Order model definition as provided)
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(OrderStatusEnum, name="order_status_enum_v3"), nullable=False, default=OrderStatusEnum.PENDING_PAYMENT, index=True)
    # ...
    customer = db.relationship('User', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', lazy='dynamic', cascade="all, delete-orphan")
    # ...

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    # ... (full OrderItem model definition as provided)
    id = db.Column(db.Integer, primary_key=True)
    order = db.relationship('Order', back_populates='items')
    # ...

class QuoteRequest(db.Model):
    __tablename__ = 'quote_requests'
    # ... (full QuoteRequest model definition as provided)
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(QuoteRequestStatusEnum, name="quote_request_status_enum_v2"), nullable=False, default=QuoteRequestStatusEnum.PENDING, index=True)
    # ...

class QuoteRequestItem(db.Model):
    __tablename__ = 'quote_request_items'
    # ... (full QuoteRequestItem model definition as provided)
    id = db.Column(db.Integer, primary_key=True)
    quote_request = db.relationship('QuoteRequest', back_populates='items')
    # ...

class Invoice(db.Model):
    __tablename__ = 'invoices'
    # ... (full Invoice model definition as provided)
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(InvoiceStatusEnum, name="invoice_status_enum_v2"), nullable=False, default=InvoiceStatusEnum.DRAFT, index=True)
    # ...

class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    # ... (full InvoiceItem model definition as provided)
    id = db.Column(db.Integer, primary_key=True)
    invoice = db.relationship('Invoice', back_populates='items')
