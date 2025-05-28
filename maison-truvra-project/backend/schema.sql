-- Schema for Maison Trüvra Database

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    role TEXT NOT NULL DEFAULT 'b2c_customer', -- b2c_customer, b2b_professional, admin
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    company_name TEXT, -- For B2B
    vat_number TEXT, -- For B2B
    siret_number TEXT, -- For B2B
    professional_status TEXT, -- pending, approved, rejected (For B2B)
    reset_token TEXT,
    reset_token_expires_at TIMESTAMP,
    verification_token TEXT,
    verification_token_expires_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_professional_status ON users(professional_status);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_is_verified ON users(is_verified);

-- Categories Table
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    image_url TEXT, -- Optional image for the category
    parent_id INTEGER, -- For subcategories, references id of this table
    slug TEXT UNIQUE NOT NULL, -- URL-friendly name
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_categories_parent_id ON categories(parent_id);

-- Products Table
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    category_id INTEGER,
    brand TEXT, -- e.g., "Maison Trüvra" or other artisanal brands
    sku_prefix TEXT UNIQUE, -- Stock Keeping Unit prefix for variants, e.g., "MT-SAVON-"
    type TEXT NOT NULL DEFAULT 'simple', -- 'simple', 'variable_weight'
    base_price REAL, -- Price for simple products or base for variable
    currency TEXT DEFAULT 'EUR',
    main_image_url TEXT,
    -- Aggregate stock for non-serialized or quick overview
    -- For 'simple' products, this is the total quantity.
    -- For 'variable_weight' products, this might be the total weight in grams or number of units.
    aggregate_stock_quantity INTEGER DEFAULT 0,
    -- For 'variable_weight' products, this is the total weight available.
    aggregate_stock_weight_grams REAL,
    unit_of_measure TEXT, -- e.g., 'piece', 'g', 'kg', 'ml', 'l' (relevant for variable_weight)
    is_active BOOLEAN DEFAULT TRUE, -- Whether the product is listed
    is_featured BOOLEAN DEFAULT FALSE,
    meta_title TEXT,
    meta_description TEXT,
    slug TEXT UNIQUE NOT NULL, -- URL-friendly name
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);
CREATE INDEX IF NOT EXISTS idx_products_type ON products(type);
CREATE INDEX IF NOT EXISTS idx_products_is_active_is_featured ON products(is_active, is_featured);
CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at DESC); -- Often queried for newest

-- Product Images Table (for multiple images per product)
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

-- Product Weight Options (for products sold by weight, e.g., cheese, charcuterie)
-- This table defines specific purchasable weight variants for a 'variable_weight' product.
-- For example, a cheese might be offered in 100g, 250g, 500g pre-defined options.
CREATE TABLE IF NOT EXISTS product_weight_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    weight_grams REAL NOT NULL, -- e.g., 100, 250, 500
    price REAL NOT NULL, -- Price for this specific weight option
    sku_suffix TEXT NOT NULL, -- Suffix to be appended to product.sku_prefix (e.g., "100G")
    -- Aggregate stock for this specific weight option, if managed at this level.
    -- This can be used if pre-cut/pre-packaged items of this weight exist.
    -- For items cut to order from a larger piece, serialized_inventory_items would be primary.
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


-- Serialized Inventory Items (Unique instance of a product, especially for artisanal/high-value items)
-- Each item gets a unique ID, QR code, and digital "passport".
CREATE TABLE IF NOT EXISTS serialized_inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_uid TEXT UNIQUE NOT NULL, -- Unique identifier for this specific item (e.g., UUID or custom format)
    product_id INTEGER NOT NULL,
    variant_id INTEGER, -- References product_weight_options.id if it's a pre-defined weight variant
    batch_number TEXT, -- For traceability
    production_date TIMESTAMP,
    expiry_date TIMESTAMP,
    actual_weight_grams REAL, -- For items sold by weight, this is the precise weight of THIS item
    cost_price REAL, -- Cost to acquire/produce this specific item
    purchase_price REAL, -- Price at which this item was sold (can be different from product.base_price or option.price due to sales etc)
    status TEXT NOT NULL DEFAULT 'available', -- available, allocated, sold, damaged, returned, recalled
    qr_code_url TEXT, -- Path to the generated QR code image for this item
    passport_url TEXT, -- Path to the generated digital passport HTML/PDF for this item
    label_url TEXT, -- Path to the generated product label for this item
    notes TEXT, -- Any specific notes about this item
    supplier_id INTEGER, -- If sourced from a specific supplier
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sold_at TIMESTAMP,
    order_item_id INTEGER, -- Link to the order item when sold
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- FOREIGN KEY (supplier_id) REFERENCES suppliers(id), -- Assuming a suppliers table if needed
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT, -- Prevent deleting product if serialized items exist
    FOREIGN KEY (variant_id) REFERENCES product_weight_options(id) ON DELETE RESTRICT, -- Prevent deleting variant if serialized items exist
    FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_serialized_inventory_items_status ON serialized_inventory_items(status);
CREATE INDEX IF NOT EXISTS idx_serialized_inventory_items_product_id ON serialized_inventory_items(product_id);
CREATE INDEX IF NOT EXISTS idx_serialized_inventory_items_variant_id ON serialized_inventory_items(variant_id);
CREATE INDEX IF NOT EXISTS idx_serialized_inventory_items_batch_number ON serialized_inventory_items(batch_number);
CREATE INDEX IF NOT EXISTS idx_serialized_inventory_items_expiry_date ON serialized_inventory_items(expiry_date);


-- Stock Movements (for tracking changes in aggregate stock, less critical for fully serialized items)
CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    variant_id INTEGER, -- References product_weight_options.id if applicable
    serialized_item_id INTEGER, -- References serialized_inventory_items.id if applicable to a specific item
    movement_type TEXT NOT NULL, -- e.g., 'initial_stock', 'sale', 'return', 'adjustment_in', 'adjustment_out', 'damage'
    quantity_change INTEGER, -- For simple products or fixed-weight variants
    weight_change_grams REAL, -- For variable_weight products, if adjusting total weight
    reason TEXT,
    related_order_id INTEGER,
    related_user_id INTEGER, -- User who performed the action, if applicable (admin)
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
    status TEXT NOT NULL DEFAULT 'pending_payment', -- pending_payment, paid, processing, shipped, delivered, cancelled, refunded
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
    payment_method TEXT, -- e.g., 'stripe', 'paypal', 'invoice' (for B2B)
    payment_transaction_id TEXT,
    shipping_method TEXT,
    shipping_cost REAL DEFAULT 0,
    tracking_number TEXT,
    notes_customer TEXT, -- Notes from customer during checkout
    notes_internal TEXT, -- Internal notes for admin
    invoice_id INTEGER UNIQUE, -- Link to the generated invoice for this order
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT, -- Prevent deleting user if they have orders
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(order_date DESC);
CREATE INDEX IF NOT EXISTS idx_orders_payment_transaction_id ON orders(payment_transaction_id);

-- Order Items Table
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    variant_id INTEGER, -- References product_weight_options.id if it's a specific weight option
    serialized_item_id INTEGER UNIQUE, -- References serialized_inventory_items.id if a specific serialized item is sold
    quantity INTEGER NOT NULL, -- Usually 1 for serialized items, or more for simple products
    unit_price REAL NOT NULL, -- Price per unit at the time of sale
    total_price REAL NOT NULL, -- quantity * unit_price
    product_name TEXT, -- Denormalized for historical data, in case product name changes
    variant_description TEXT, -- Denormalized description of the weight option
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT, -- Keep product info even if product deleted (or use SET NULL and denormalize more)
    FOREIGN KEY (variant_id) REFERENCES product_weight_options(id) ON DELETE SET NULL,
    FOREIGN KEY (serialized_item_id) REFERENCES serialized_inventory_items(id) ON DELETE SET NULL -- Item might be unlinked if order is cancelled before processing
);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_variant_id ON order_items(variant_id);
-- serialized_item_id is UNIQUE, so it's already indexed.

-- Reviews Table
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_approved BOOLEAN DEFAULT FALSE, -- Admin can approve reviews
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON reviews(product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_is_approved_review_date ON reviews(is_approved, review_date DESC);

-- Cart Table (Optional, can also be managed client-side with localStorage/sessionStorage)
-- If server-side cart is needed for persistence across devices before login:
CREATE TABLE IF NOT EXISTS carts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE, -- Can be NULL for guest carts, linked on login
    session_id TEXT UNIQUE, -- For guest carts
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
-- user_id and session_id are UNIQUE, so already indexed.
CREATE INDEX IF NOT EXISTS idx_carts_updated_at ON carts(updated_at);


CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    variant_id INTEGER, -- References product_weight_options.id
    quantity INTEGER NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cart_id) REFERENCES carts(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES product_weight_options(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_cart_items_cart_id ON cart_items(cart_id);
CREATE INDEX IF NOT EXISTS idx_cart_items_product_id ON cart_items(product_id);

-- Professional Validation Documents (for B2B user validation)
CREATE TABLE IF NOT EXISTS professional_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    document_type TEXT NOT NULL, -- e.g., 'kbis', 'vat_certificate'
    file_path TEXT NOT NULL, -- Path to the uploaded document
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending_review', -- pending_review, approved, rejected
    reviewed_by INTEGER, -- Admin user_id
    reviewed_at TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_professional_documents_user_id ON professional_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_professional_documents_status ON professional_documents(status);

-- Invoices Table (Primarily for B2B, but can be for B2C too)
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER UNIQUE, -- Associated B2C order
    b2b_user_id INTEGER, -- Associated B2B user, if not tied to a direct web order
    invoice_number TEXT UNIQUE NOT NULL,
    issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date TIMESTAMP,
    total_amount REAL NOT NULL,
    currency TEXT DEFAULT 'EUR',
    status TEXT NOT NULL DEFAULT 'draft', -- draft, issued, paid, overdue, cancelled
    pdf_path TEXT, -- Path to the generated PDF invoice
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
    FOREIGN KEY (b2b_user_id) REFERENCES users(id) ON DELETE SET NULL
);
-- order_id and invoice_number are UNIQUE, so already indexed.
CREATE INDEX IF NOT EXISTS idx_invoices_b2b_user_id ON invoices(b2b_user_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_issue_date ON invoices(issue_date DESC);
CREATE INDEX IF NOT EXISTS idx_invoices_due_date ON invoices(due_date);

-- Invoice Items Table (For B2B invoices not directly from an order, or for more detail)
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    product_id INTEGER, -- Optional link to a product
    serialized_item_id INTEGER, -- Optional link to a specific serialized item
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
    FOREIGN KEY (serialized_item_id) REFERENCES serialized_inventory_items(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice_id ON invoice_items(invoice_id);

-- Audit Log Table
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, -- User who performed the action (can be NULL for system actions)
    username TEXT, -- Denormalized for easier viewing
    action TEXT NOT NULL, -- e.g., 'login', 'create_product', 'update_order_status'
    target_type TEXT, -- e.g., 'product', 'order', 'user'
    target_id INTEGER,
    details TEXT, -- JSON string or text with more details about the action
    ip_address TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'success', -- 'success', 'failure'
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
    source TEXT -- e.g., 'footer_form', 'checkout_opt_in'
);
-- email is UNIQUE, so already indexed.
CREATE INDEX IF NOT EXISTS idx_newsletter_subscriptions_is_active ON newsletter_subscriptions(is_active);

-- Settings Table (for global site settings, feature flags, etc.)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- key is PRIMARY KEY, so already indexed.

-- Example: Default company info for invoices (can be stored in settings or config)
-- INSERT OR REPLACE INTO settings (key, value, description) VALUES
-- ('company_name', 'Maison Trüvra SARL', 'Company Name for Invoices'),
-- ('company_address_line1', '1 Rue de la Truffe', 'Company Address Line 1'),
-- ('company_city', 'Paris', 'Company City'),
-- ('company_postal_code', '75001', 'Company Postal Code'),
-- ('company_country', 'France', 'Company Country'),
-- ('company_vat_number', 'FRXX123456789', 'Company VAT Number'),
-- ('company_logo_url_invoice', '/assets/logos/maison_truvra_invoice_logo.png', 'Path to company logo for invoices');

-- Asset Storage (QR Codes, Passports, Labels - if storing metadata about them)
-- The actual files are stored on the filesystem, this table could track their metadata.
CREATE TABLE IF NOT EXISTS generated_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_type TEXT NOT NULL, -- 'qr_code', 'passport_html', 'product_label'
    related_item_uid TEXT, -- Link to serialized_inventory_items.item_uid
    related_product_id INTEGER, -- Link to products.id (e.g. for a generic product label)
    file_path TEXT NOT NULL UNIQUE,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (related_item_uid) REFERENCES serialized_inventory_items(item_uid) ON DELETE CASCADE,
    FOREIGN KEY (related_product_id) REFERENCES products(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_generated_assets_related_item_uid ON generated_assets(related_item_uid);
CREATE INDEX IF NOT EXISTS idx_generated_assets_asset_type ON generated_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_generated_assets_related_product_id ON generated_assets(related_product_id);

