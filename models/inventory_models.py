# backend/models/inventory_models.py
from .base import db
from .enums import SerializedInventoryItemStatusEnum, StockMovementTypeEnum
from datetime import datetime, timezone

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
    purchase_price = db.Column(db.Float, nullable=True)
    status = db.Column(db.Enum(SerializedInventoryItemStatusEnum, name="sii_status_enum_v2"), nullable=False, default=SerializedInventoryItemStatusEnum.AVAILABLE, index=True)
    qr_code_url = db.Column(db.String(255), nullable=True)
    passport_url = db.Column(db.String(255), nullable=True)
    label_url = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    supplier_id = db.Column(db.Integer, nullable=True)
    received_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sold_at = db.Column(db.DateTime, nullable=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id', ondelete='SET NULL'), unique=True, index=True, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    product = db.relationship('Product', back_populates='serialized_items')
    variant = db.relationship('ProductWeightOption', back_populates='serialized_items')
    stock_movements = db.relationship('StockMovement', back_populates='serialized_item', lazy='dynamic', cascade="all, delete-orphan")
    generated_assets = db.relationship('GeneratedAsset', primaryjoin="SerializedInventoryItem.item_uid == GeneratedAsset.related_item_uid", foreign_keys='GeneratedAsset.related_item_uid', back_populates='inventory_item_asset_owner', lazy='dynamic', cascade="all, delete-orphan")
    order_item_link = db.relationship('OrderItem', back_populates='sold_serialized_item', foreign_keys=[order_item_id])

    def to_dict(self):
        return {
            "id": self.id, "item_uid": self.item_uid, "product_id": self.product_id,
            "variant_id": self.variant_id, "batch_number": self.batch_number,
            "production_date": self.production_date.isoformat() if self.production_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "status": self.status.value if self.status else None, "notes": self.notes,
            "product_name": self.product.name if self.product else None, 
            "variant_sku_suffix": self.variant.sku_suffix if self.variant else None,
        }

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id', ondelete='SET NULL'), index=True, nullable=True)
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id', ondelete='SET NULL'), index=True, nullable=True)
    movement_type = db.Column(db.Enum(StockMovementTypeEnum, name="stock_movement_type_enum_v2"), nullable=False, index=True)
    quantity_change = db.Column(db.Integer, nullable=True)
    weight_change_grams = db.Column(db.Float, nullable=True)
    reason = db.Column(db.Text, nullable=True)
    related_order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='SET NULL'), index=True, nullable=True)
    related_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True, nullable=True)
    movement_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    notes = db.Column(db.Text, nullable=True)

    product = db.relationship('Product', back_populates='stock_movements')
    variant = db.relationship('ProductWeightOption', back_populates='stock_movements')
    serialized_item = db.relationship('SerializedInventoryItem', back_populates='stock_movements')
    related_order = db.relationship('Order', back_populates='stock_movements')

    def to_dict(self):
        return {
            "id": self.id, "product_id": self.product_id, "variant_id": self.variant_id,
            "serialized_item_id": self.serialized_item_id,
            "movement_type": self.movement_type.value if self.movement_type else None,
            "quantity_change": self.quantity_change, "weight_change_grams": self.weight_change_grams,
            "reason": self.reason, "movement_date": self.movement_date.isoformat(), "notes": self.notes
        }
