# backend/models/enums.py
# Contains all Enum definitions for the models.
import enum


class B2BLoyaltyTier(enum.Enum):
    BRONZE = "Bronze"
    SILVER = "Silver"
    GOLD = "Gold"

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

class B2BPricingTierEnum(enum.Enum):
    STANDARD = "standard"
    GOLD = "gold"
    PLATINUM = "platinum"

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

class NewsletterTypeEnum(enum.Enum):
    B2C = "b2c"
    B2B = "b2b"
    GENERAL = "general"

class QuoteRequestStatusEnum(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT_TO_CLIENT = "sent_to_client"
    ACCEPTED_BY_CLIENT = "accepted_by_client"
    CONVERTED_TO_ORDER = "converted_to_order"
    DECLINED_BY_CLIENT = "declined_by_client"
    EXPIRED = "expired"
