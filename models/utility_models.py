# backend/models/product_models.py
from .base import db
from .enums import ProductTypeEnum, PreservationTypeEnum, B2BPricingTierEnum
from datetime import datetime, timezone

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
    type = db.Column(db.Enum(ProductTypeEnum, name="product_type_enum_v2"), nullable=False, default=ProductTypeEnum.SIMPLE, index=True)
    base_price = db.Column(db.Float, nullable=True) 
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
        from .inventory_models import SerializedInventoryItem, SerializedInventoryItemStatusEnum
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
        long_description_display = self.long_description
        meta_title_display = self.meta_title
        meta_description_display = self.meta_description
        sensory_evaluation_display = None
        food_pairings_display = None
        species_display = None
        ideal_uses_display = None 
        pairing_suggestions_display = None 

        if lang_code == 'fr':
            if loc and loc.name_fr: name_display = loc.name_fr
            if loc and loc.description_fr: description_display = loc.description_fr
            # ... (rest of fr localization logic)
        elif lang_code == 'en':
            if loc and loc.name_en: name_display = loc.name_en
            if loc and loc.description_en: description_display = loc.description_en
            # ... (rest of en localization logic)
        
        loc_fr_specific = self.localizations.filter_by(lang_code='fr').first()
        loc_en_specific = self.localizations.filter_by(lang_code='en').first()

        return {
            "id": self.id, "name": name_display, 
            "name_fr": loc_fr_specific.name_fr if loc_fr_specific and loc_fr_specific.name_fr else self.name,
            "name_en": loc_en_specific.name_en if loc_en_specific and loc_en_specific.name_en else None,
            "product_code": self.product_code, "slug": self.slug, 
            "type": self.type.value if self.type else None, 
            "base_price": self.base_price, 
            "is_active": self.is_active, "is_featured": self.is_featured, 
            "category_id": self.category_id, 
            "category_name": self.category.name if self.category else None,
            "category_code": self.category.category_code if self.category else None,
            "main_image_url": self.main_image_url,
            "unit_of_measure": self.unit_of_measure, "brand": self.brand, "currency": self.currency,
            "description": description_display,
            "long_description": long_description_display, 
            "sensory_evaluation": sensory_evaluation_display,
            "food_pairings": food_pairings_display,
            "species": species_display,
            "preservation_type": self.preservation_type.value if self.preservation_type else None,
            "notes_internal": self.notes_internal, "supplier_info": self.supplier_info,
            "meta_title": meta_title_display, "meta_description": meta_description_display,
            "variant_count": self.weight_options.filter_by(is_active=True).count() if self.type == ProductTypeEnum.VARIABLE_WEIGHT else 0,
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
    price = db.Column(db.Float, nullable=False)
    sku_suffix = db.Column(db.String(50), nullable=False) 
    aggregate_stock_quantity = db.Column(db.Integer, default=0, nullable=False) 
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    product = db.relationship('Product', back_populates='weight_options')
    serialized_items = db.relationship('SerializedInventoryItem', back_populates='variant', lazy='dynamic')
    stock_movements = db.relationship('StockMovement', back_populates='variant', lazy='dynamic')
    order_items = db.relationship('OrderItem', back_populates='variant', lazy='dynamic')
    cart_items = db.relationship('CartItem', back_populates='variant', lazy='dynamic')
    b2b_tier_prices_variant = db.relationship('ProductB2BTierPrice', back_populates='variant', lazy='dynamic', cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint('product_id', 'weight_grams', name='uq_product_weight_v2'),
                      db.UniqueConstraint('product_id', 'sku_suffix', name='uq_product_sku_suffix_v2'))

class ProductB2BTierPrice(db.Model):
    __tablename__ = 'product_b2b_tier_prices'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=True, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id', ondelete='CASCADE'), nullable=True, index=True)
    b2b_tier = db.Column(db.Enum(B2BPricingTierEnum, name="b2b_pricing_tier_enum_v2"), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    product = db.relationship('Product', back_populates='b2b_tier_prices')
    variant = db.relationship('ProductWeightOption', back_populates='b2b_tier_prices_variant')
    __table_args__ = (db.UniqueConstraint('product_id', 'variant_id', 'b2b_tier', name='uq_product_variant_tier_price'),)

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
