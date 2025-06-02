-- Schema for Maison Trüvra Database

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    role TEXT NOT NULL DEFAULT 'b2c_customer' CHECK(role IN ('b2c_customer', 'b2b_professional', 'admin', 'staff')), -- Added 'staff' role
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    company_name TEXT, 
    vat_number TEXT, 
    siret_number TEXT, 
    professional_status TEXT, 
    reset_token TEXT,
    reset_token_expires_at TIMESTAMP,
    verification_token TEXT,
    verification_token_expires_at TIMESTAMP,
    totp_secret TEXT, -- For MFA/TOTP
    is_totp_enabled BOOLEAN DEFAULT FALSE -- For MFA/TOTP
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_professional_status ON users(professional_status);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_is_verified ON users(is_verified);

-- Trigger to update 'updated_at' timestamp on users table
CREATE TRIGGER IF NOT EXISTS trigger_users_updated_at
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- Categories Table
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    image_url TEXT, 
    category_code TEXT UNIQUE NOT NULL, 
    parent_id INTEGER, 
    slug TEXT UNIQUE NOT NULL, 
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_categories_category_code ON categories(category_code);
CREATE INDEX IF NOT EXISTS idx_categories_parent_id ON categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_categories_is_active ON categories(is_active);

CREATE TRIGGER IF NOT EXISTS trigger_categories_updated_at
AFTER UPDATE ON categories
FOR EACH ROW
BEGIN
    UPDATE categories SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- Products Table
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    category_id INTEGER,
    product_code TEXT UNIQUE NOT NULL,
    brand TEXT, 
    type TEXT NOT NULL DEFAULT 'simple' CHECK(type IN ('simple', 'variable_weight')),
    base_price REAL, 
    currency TEXT DEFAULT 'EUR',
    main_image_url TEXT,
    aggregate_stock_quantity INTEGER DEFAULT 0,
    aggregate_stock_weight_grams REAL,
    unit_of_measure TEXT, 
    is_active BOOLEAN DEFAULT TRUE, 
    is_featured BOOLEAN DEFAULT FALSE,
    meta_title TEXT,
    meta_description TEXT,
    slug TEXT UNIQUE NOT NULL, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_products_product_code ON products(product_code);
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);
CREATE INDEX IF NOT EXISTS idx_products_type ON products(type);
CREATE INDEX IF NOT EXISTS idx_products_is_active_is_featured ON products(is_active, is_featured);
CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at DESC);

CREATE TRIGGER IF NOT EXISTS trigger_products_updated_at
AFTER UPDATE ON products
FOR EACH ROW
BEGIN
    UPDATE products SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- Product Images Table
CREATE TABLE IF NOT EXISTS product_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    image_url TEXT NOT NULL,
    alt_text TEXT,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_product_images_product_id_is_primary ON product_images(product_id, is_primary);

-- Product Weight Options
CREATE TABLE IF NOT EXISTS product_weight_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    weight_grams REAL NOT NULL, 
    price REAL NOT NULL, 
    sku_suffix TEXT NOT NULL, 
    aggregate_stock_quantity INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (product_id, weight_grams),
    UNIQUE (product_id, sku_suffix),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_product_weight_options_product_id ON product_weight_options(product_id);
CREATE INDEX IF NOT EXISTS idx_product_weight_options_is_active ON product_weight_options(is_active);

CREATE TRIGGER IF NOT EXISTS trigger_product_weight_options_updated_at
AFTER UPDATE ON product_weight_options
FOR EACH ROW
BEGIN
    UPDATE product_weight_options SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- Serialized Inventory Items
CREATE TABLE IF NOT EXISTS serialized_inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_uid TEXT UNIQUE NOT NULL, 
    product_id INTEGER NOT NULL,
    variant_id INTEGER, 
    batch_number TEXT, 
    production_date TIMESTAMP,
    expiry_date TIMESTAMP,
    actual_weight_grams REAL, 
    cost_price REAL, 
    purchase_price REAL,    
    status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'allocated', 'sold', 'damaged', 'returned', 'recalled', 'reserved_internal', 'missing')),
    qr_code_url TEXT, 
    passport_url TEXT, 
    label_url TEXT, 
    notes TEXT, 
    supplier_id INTEGER, 
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sold_at TIMESTAMP,
    order_item_id INTEGER, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT, 
    FOREIGN KEY (variant_id) REFERENCES product_weight_options(id) ON DELETE RESTRICT,
    FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_serialized_inventory_items_status ON serialized_inventory_items(status);
CREATE INDEX IF NOT EXISTS idx_serialized_inventory_items_product_id ON serialized_inventory_items(product_id);
CREATE INDEX IF NOT EXISTS idx_serialized_inventory_items_variant_id ON serialized_inventory_items(variant_id);
CREATE INDEX IF NOT EXISTS idx_serialized_inventory_items_batch_number ON serialized_inventory_items(batch_number);
CREATE INDEX IF NOT EXISTS idx_serialized_inventory_items_expiry_date ON serialized_inventory_items(expiry_date);

CREATE TRIGGER IF NOT EXISTS trigger_serialized_inventory_items_updated_at
AFTER UPDATE ON serialized_inventory_items
FOR EACH ROW
BEGIN
    UPDATE serialized_inventory_items SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- Stock Movements
CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    variant_id INTEGER, 
    serialized_item_id INTEGER, 
    movement_type TEXT NOT NULL CHECK(movement_type IN ('initial_stock', 'sale', 'return', 'adjustment_in', 'adjustment_out', 'damage', 'production', 'recall', 'transfer_in', 'transfer_out', 'receive_serialized', 'import_csv_new')),
    quantity_change INTEGER, 
    weight_change_grams REAL, 
    reason TEXT,
    related_order_id INTEGER,
    related_user_id INTEGER, 
    movement_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES product_weight_options(id) ON DELETE CASCADE,
    FOREIGN KEY (serialized_item_id) REFERENCES serialized_inventory_items(id) ON DELETE SET NULL,
    FOREIGN KEY (related_order_id) REFERENCES orders(id) ON DELETE SET NULL,
    FOREIGN KEY (related_user_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_stock_movements_product_id ON stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_variant_id ON stock_movements(variant_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_serialized_item_id ON stock_movements(serialized_item_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_movement_type ON stock_movements(movement_type);
CREATE INDEX IF NOT EXISTS idx_stock_movements_movement_date ON stock_movements(movement_date);

-- Orders Table
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending_payment' CHECK(status IN ('pending_payment', 'paid', 'processing', 'awaiting_shipment', 'shipped', 'delivered', 'completed', 'cancelled', 'refunded', 'partially_refunded', 'on_hold', 'failed')),
    total_amount REAL NOT NULL,
    currency TEXT DEFAULT 'EUR',
    shipping_address_line1 TEXT,
    shipping_address_line2 TEXT,
    shipping_city TEXT,
    shipping_postal_code TEXT,
    shipping_country TEXT,
    billing_address_line1 TEXT,
    billing_address_line2 TEXT,
    billing_city TEXT,
    billing_postal_code TEXT,
    billing_country TEXT,
    payment_method TEXT, 
    payment_transaction_id TEXT,
    shipping_method TEXT,
    shipping_cost REAL DEFAULT 0,
    tracking_number TEXT,
    notes_customer TEXT, 
    notes_internal TEXT, 
    invoice_id INTEGER UNIQUE, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT, 
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(order_date DESC);
CREATE INDEX IF NOT EXISTS idx_orders_payment_transaction_id ON orders(payment_transaction_id);

CREATE TRIGGER IF NOT EXISTS trigger_orders_updated_at
AFTER UPDATE ON orders
FOR EACH ROW
BEGIN
    UPDATE orders SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- Order Items Table
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    variant_id INTEGER, 
    serialized_item_id INTEGER UNIQUE, 
    quantity INTEGER NOT NULL, 
    unit_price REAL NOT NULL, 
    total_price REAL NOT NULL, 
    product_name TEXT, 
    variant_description TEXT, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT, 
    FOREIGN KEY (variant_id) REFERENCES product_weight_options(id) ON DELETE SET NULL,
    FOREIGN KEY (serialized_item_id) REFERENCES serialized_inventory_items(id) ON DELETE SET NULL 
);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_variant_id ON order_items(variant_id);

-- Reviews Table
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_approved BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON reviews(product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_is_approved_review_date ON reviews(is_approved, review_date DESC);

-- Carts Table
CREATE TABLE IF NOT EXISTS carts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE, 
    session_id TEXT UNIQUE, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_carts_updated_at ON carts(updated_at);

CREATE TRIGGER IF NOT EXISTS trigger_carts_updated_at
AFTER UPDATE ON carts
FOR EACH ROW
BEGIN
    UPDATE carts SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    variant_id INTEGER, 
    quantity INTEGER NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cart_id) REFERENCES carts(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES product_weight_options(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_cart_items_cart_id ON cart_items(cart_id);
CREATE INDEX IF NOT EXISTS idx_cart_items_product_id ON cart_items(product_id);

-- Professional Validation Documents
CREATE TABLE IF NOT EXISTS professional_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    document_type TEXT NOT NULL, 
    file_path TEXT NOT NULL, 
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    status TEXT DEFAULT 'pending_review', 
    reviewed_by INTEGER, 
    reviewed_at TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_professional_documents_user_id ON professional_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_professional_documents_status ON professional_documents(status);

-- Invoices Table
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER UNIQUE, 
    b2b_user_id INTEGER, 
    invoice_number TEXT UNIQUE NOT NULL,
    issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date TIMESTAMP,
    total_amount REAL NOT NULL,
    currency TEXT DEFAULT 'EUR' CHECK(currency IN ('EUR', 'USD', 'GBP')), 
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'issued', 'sent', 'paid', 'partially_paid', 'overdue', 'cancelled', 'voided')),
    pdf_path TEXT, 
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    FOREIGN KEY (b2b_user_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_invoices_b2b_user_id ON invoices(b2b_user_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_issue_date ON invoices(issue_date DESC);
CREATE INDEX IF NOT EXISTS idx_invoices_due_date ON invoices(due_date);

CREATE TRIGGER IF NOT EXISTS trigger_invoices_updated_at
AFTER UPDATE ON invoices
FOR EACH ROW
BEGIN
    UPDATE invoices SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- Invoice Items Table
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    product_id INTEGER, 
    serialized_item_id INTEGER, 
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
    FOREIGN KEY (serialized_item_id) REFERENCES serialized_inventory_items(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice_id ON invoice_items(invoice_id);

-- Audit Log Table
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, 
    username TEXT, 
    action TEXT NOT NULL, 
    target_type TEXT, 
    target_id INTEGER,
    details TEXT, 
    ip_address TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'success' CHECK(status IN ('success', 'failure', 'pending', 'info')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_target_type_target_id ON audit_log(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);

-- Newsletter Subscriptions
CREATE TABLE IF NOT EXISTS newsletter_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    source TEXT, 
    consent TEXT NOT NULL DEFAULT 'Y'
);
CREATE INDEX IF NOT EXISTS idx_newsletter_subscriptions_is_active ON newsletter_subscriptions(is_active);

-- Settings Table
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER IF NOT EXISTS trigger_settings_updated_at
AFTER UPDATE ON settings
FOR EACH ROW
BEGIN
    UPDATE settings SET updated_at = CURRENT_TIMESTAMP WHERE key = OLD.key;
END;

-- Product Localizations Table
CREATE TABLE IF NOT EXISTS product_localizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    lang_code TEXT NOT NULL CHECK(lang_code IN ('fr', 'en')), 
    name_fr TEXT, 
    name_en TEXT, 
    description_fr TEXT,
    description_en TEXT,
    short_description_fr TEXT,
    short_description_en TEXT,
    ideal_uses_fr TEXT,
    ideal_uses_en TEXT,
    pairing_suggestions_fr TEXT,
    pairing_suggestions_en TEXT,
    sensory_description_fr TEXT,
    sensory_description_en TEXT,
    UNIQUE (product_id, lang_code),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_product_localizations_product_id_lang ON product_localizations(product_id, lang_code);

-- Category Localizations Table
CREATE TABLE IF NOT EXISTS category_localizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    lang_code TEXT NOT NULL CHECK(lang_code IN ('fr', 'en')),
    name_fr TEXT,
    name_en TEXT,
    description_fr TEXT,
    description_en TEXT,
    species_fr TEXT,
    species_en TEXT,
    main_ingredients_fr TEXT,
    main_ingredients_en TEXT,
    ingredients_notes_fr TEXT,
    ingredients_notes_en TEXT,
    fresh_vs_preserved_fr TEXT,
    fresh_vs_preserved_en TEXT,
    size_details_fr TEXT,
    size_details_en TEXT,
    pairings_fr TEXT,
    pairings_en TEXT,
    weight_info_fr TEXT,
    weight_info_en TEXT,
    category_notes_fr TEXT,
    category_notes_en TEXT,
    UNIQUE (category_id, lang_code),
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_category_localizations_category_id_lang ON category_localizations(category_id, lang_code);

-- Generated Assets Table
CREATE TABLE IF NOT EXISTS generated_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    asset_type TEXT NOT NULL, 
    related_item_uid TEXT, 
    related_product_id INTEGER, 
    file_path TEXT NOT NULL UNIQUE,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (related_item_uid) REFERENCES serialized_inventory_items(item_uid) ON DELETE CASCADE,
    FOREIGN KEY (related_product_id) REFERENCES products(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_generated_assets_related_item_uid ON generated_assets(related_item_uid);
CREATE INDEX IF NOT EXISTS idx_generated_assets_asset_type ON generated_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_generated_assets_related_product_id ON generated_assets(related_product_id);
