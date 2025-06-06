# backend/models/__init__.py
# This file makes the 'models' directory a Python package and imports all model classes
# into the package's namespace, so they can be easily imported elsewhere.
# e.g., from ..models import User, Product, Order

from .base import db
from .enums import (
    UserRoleEnum, ProfessionalStatusEnum, B2BPricingTierEnum, ProductTypeEnum, 
    PreservationTypeEnum, SerializedInventoryItemStatusEnum, StockMovementTypeEnum, 
    OrderStatusEnum, InvoiceStatusEnum, AuditLogStatusEnum, AssetTypeEnum, 
    NewsletterTypeEnum, QuoteRequestStatusEnum
)
from .user_models import User, ProfessionalDocument, TokenBlocklist, ReferralAwardLog
from .product_models import (
    Category, Product, ProductImage, ProductWeightOption, 
    ProductB2BTierPrice, ProductLocalization, CategoryLocalization
)
from .order_models import Order, OrderItem, QuoteRequest, QuoteRequestItem, Invoice, InvoiceItem
from .inventory_models import SerializedInventoryItem, StockMovement
from .utility_models import Review, Cart, CartItem, NewsletterSubscription, Setting, GeneratedAsset, AuditLog


# You can optionally create an __all__ variable to define the public API of this package
__all__ = [
    'db', 
    'User', 'ProfessionalDocument', 'TokenBlocklist', 'ReferralAwardLog',
    'Category', 'Product', 'ProductImage', 'ProductWeightOption', 'ProductB2BTierPrice',
    'ProductLocalization', 'CategoryLocalization',
    'Order', 'OrderItem', 'QuoteRequest', 'QuoteRequestItem', 'Invoice', 'InvoiceItem',
    'SerializedInventoryItem', 'StockMovement',
    'Review', 'Cart', 'CartItem', 'NewsletterSubscription', 'Setting', 'GeneratedAsset', 'AuditLog',
    'UserRoleEnum', 'ProfessionalStatusEnum', 'B2BPricingTierEnum', 'ProductTypeEnum',
    'PreservationTypeEnum', 'SerializedInventoryItemStatusEnum', 'StockMovementTypeEnum',
    'OrderStatusEnum', 'InvoiceStatusEnum', 'AuditLogStatusEnum', 'AssetTypeEnum',
    'NewsletterTypeEnum', 'QuoteRequestStatusEnum'
]
