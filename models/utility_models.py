# backend/models/utility_models.py
from .base import db
from .enums import AuditLogStatusEnum, AssetTypeEnum, NewsletterTypeEnum
from datetime import datetime, timezone

class Review(db.Model):
    __tablename__ = 'reviews'
    # ... (full Review model definition as provided)
    id = db.Column(db.Integer, primary_key=True)

class Cart(db.Model):
    __tablename__ = 'carts'
    # ... (full Cart model definition as provided)
    id = db.Column(db.Integer, primary_key=True)

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    # ... (full CartItem model definition as provided)
    id = db.Column(db.Integer, primary_key=True)

class NewsletterSubscription(db.Model):
    __tablename__ = 'newsletter_subscriptions'
    # ... (full NewsletterSubscription model definition as provided)
    id = db.Column(db.Integer, primary_key=True)
    newsletter_type = db.Column(db.Enum(NewsletterTypeEnum, name="newsletter_type_enum_v1"), default=NewsletterTypeEnum.GENERAL, nullable=False)

class Setting(db.Model):
    __tablename__ = 'settings'
    # ... (full Setting model definition as provided)
    key = db.Column(db.String(100), primary_key=True)

class GeneratedAsset(db.Model):
    __tablename__ = 'generated_assets'
    # ... (full GeneratedAsset model definition as provided)
    id = db.Column(db.Integer, primary_key=True)
    asset_type = db.Column(db.Enum(AssetTypeEnum, name="asset_type_enum_v2"), nullable=False, index=True)

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    # ... (full AuditLog model definition as provided)
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(AuditLogStatusEnum, name="audit_log_status_enum_v2"), default=AuditLogStatusEnum.SUCCESS, index=True)
