# backend/b2b/routes.py
from flask import Blueprint, request, jsonify, current_app, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os

from .. import db
from ..models import (User, Product, ProductWeightOption, ProductB2BTierPrice,
                    Order, OrderItem, QuoteRequest, QuoteRequestItem, Invoice,
                    UserRoleEnum, ProfessionalStatusEnum, B2BPricingTierEnum,
                    OrderStatusEnum, QuoteRequestStatusEnum)
from ..utils import is_valid_email, allowed_file, get_file_extension # Add other utils as needed
# from ..services.invoice_service import InvoiceService # If B2B invoice generation is complex

b2b_bp = Blueprint('b2b_bp', __name__, url_prefix='/api/b2b')

# --- Product Catalog for B2B (Illustrative - you might modify existing product routes) ---
@b2b_bp.route('/products', methods=['GET'])
@jwt_required()
def get_b2b_products():
    """
    Fetches products with B2B tiered pricing for the authenticated professional user.
    This could also be a modification of your existing /api/products endpoint
    to check user role and apply B2B pricing if applicable.
    """
    current_user_id = get_jwt_identity()
    b2b_user = User.query.get(current_user_id)

    if not b2b_user or b2b_user.role != UserRoleEnum.B2B_PROFESSIONAL or b2b_user.professional_status != ProfessionalStatusEnum.APPROVED:
        return jsonify(message="Access denied. B2B professional account required and approved.", success=False), 403

    user_tier = b2b_user.b2b_tier # e.g., B2BPricingTierEnum.GOLD

    # --- Pagination and Filtering (similar to your public product list) ---
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    category_slug = request.args.get('category_slug')
    search_term = request.args.get('search')
    # ... (add sorting if needed) ...

    query = Product.query.filter_by(is_active=True) # Base query

    if category_slug:
        query = query.join(Product.category).filter(Category.slug == category_slug, Category.is_active == True)
    if search_term:
        term_like = f"%{search_term.lower()}%"
        query = query.filter(Product.name.ilike(term_like)) # Simplified search

    paginated_products = query.paginate(page=page, per_page=per_page, error_out=False)
    products_data = []

    for product in paginated_products.items:
        # Determine B2B price
        b2b_price = product.base_price # Default to base price (B2C retail)
        
        # Check for specific B2B tier price for the product itself (if it's simple)
        tier_price_entry = ProductB2BTierPrice.query.filter_by(
            product_id=product.id, 
            variant_id=None, # For simple product pricing
            b2b_tier=user_tier
        ).first()
        if tier_price_entry:
            b2b_price = tier_price_entry.price
        
        # Note: If product is 'variable_weight', the main b2b_price might be "Starting from..."
        # and individual variant options would also need tiered pricing lookup.
        
        product_dict = product.to_dict() # Use your existing to_dict
        product_dict['b2b_price'] = b2b_price # Add the determined B2B price
        product_dict['retail_price'] = product.base_price # Assuming base_price is RRP

        if product.type == ProductTypeEnum.VARIABLE_WEIGHT:
            options_list = []
            for option in product.weight_options.filter_by(is_active=True).all():
                option_b2b_price = option.price # Default to variant's B2C price
                option_tier_price_entry = ProductB2BTierPrice.query.filter_by(
                    variant_id=option.id,
                    b2b_tier=user_tier
                ).first()
                if option_tier_price_entry:
                    option_b2b_price = option_tier_price_entry.price
                
                options_list.append({
                    "option_id": option.id,
                    "weight_grams": option.weight_grams,
                    "sku_suffix": option.sku_suffix,
                    "b2b_price": option_b2b_price,
                    "retail_price": option.price, # Original B2C price of variant
                    "aggregate_stock_quantity": option.aggregate_stock_quantity
                })
            product_dict['weight_options_b2b'] = options_list


        products_data.append(product_dict)

    return jsonify({
        "products": products_data,
        "page": paginated_products.page,
        "per_page": paginated_products.per_page,
        "total_products": paginated_products.total,
        "total_pages": paginated_products.pages,
        "success": True
    }), 200

# --- Quote Request Routes ---
@b2b_bp.route('/quote-requests', methods=['POST'])
@jwt_required()
def create_quote_request():
    current_user_id = get_jwt_identity()
    b2b_user = User.query.get(current_user_id)
    if not b2b_user or b2b_user.role != UserRoleEnum.B2B_PROFESSIONAL:
        return jsonify(message="B2B professional account required.", success=False), 403

    data = request.json
    items_data = data.get('items')
    notes = data.get('notes')
    contact_person = data.get('contact_person', b2b_user.first_name + " " + b2b_user.last_name)
    contact_phone = data.get('contact_phone') # Assuming phone might be on user model or provided

    if not items_data or not isinstance(items_data, list) or len(items_data) == 0:
        return jsonify(message="At least one item is required for a quote request.", success=False), 400

    try:
        new_quote = QuoteRequest(
            user_id=current_user_id,
            notes=notes,
            contact_person=contact_person,
            contact_phone=contact_phone,
            status=QuoteRequestStatusEnum.PENDING
        )
        db.session.add(new_quote)
        db.session.flush() # To get new_quote.id

        for item_data in items_data:
            # Validate item_data (product_id exists, quantity is valid etc.)
            product = Product.query.get(item_data.get('product_id'))
            if not product:
                db.session.rollback()
                return jsonify(message=f"Invalid product ID: {item_data.get('product_id')}", success=False), 400
            
            variant = None
            if item_data.get('variant_id'):
                variant = ProductWeightOption.query.get(item_data.get('variant_id'))
                if not variant or variant.product_id != product.id:
                    db.session.rollback()
                    return jsonify(message=f"Invalid variant ID for product.", success=False), 400

            quote_item = QuoteRequestItem(
                quote_request_id=new_quote.id,
                product_id=item_data.get('product_id'),
                variant_id=item_data.get('variant_id'),
                quantity=item_data.get('quantity'),
                requested_price_ht=item_data.get('price_at_request') # Price user saw
            )
            db.session.add(quote_item)
        
        db.session.commit()
        # TODO: Notify admin of new quote request
        current_app.logger.info(f"New B2B Quote Request {new_quote.id} submitted by user {current_user_id}.")
        # Example: send_admin_notification(f"New Quote Request #{new_quote.id}", f"User {b2b_user.email} submitted a new quote.")
        
        return jsonify(message="Quote request submitted successfully.", quote_id=new_quote.id, success=True), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating quote request for user {current_user_id}: {e}", exc_info=True)
        return jsonify(message="Failed to submit quote request.", error=str(e), success=False), 500


# --- Purchase Order Routes ---
@b2b_bp.route('/purchase-orders', methods=['POST'])
@jwt_required()
def upload_purchase_order():
    current_user_id = get_jwt_identity()
    b2b_user = User.query.get(current_user_id)
    if not b2b_user or b2b_user.role != UserRoleEnum.B2B_PROFESSIONAL:
        return jsonify(message="B2B professional account required.", success=False), 403

    if 'purchase_order_file' not in request.files:
        return jsonify(message="No purchase order file provided.", success=False), 400
    
    po_file = request.files['purchase_order_file']
    cart_items_json = request.form.get('cart_items') # Cart items as JSON string

    if po_file.filename == '':
        return jsonify(message="No selected file for purchase order.", success=False), 400
    
    if not cart_items_json:
        return jsonify(message="Cart items are required with PO submission.", success=False), 400

    try:
        cart_items = json.loads(cart_items_json)
        if not isinstance(cart_items, list) or len(cart_items) == 0:
            raise ValueError("Invalid cart items format or empty cart.")
    except (json.JSONDecodeError, ValueError) as e:
        return jsonify(message=f"Invalid cart items data: {str(e)}", success=False), 400

    upload_folder_pos = os.path.join(current_app.config['UPLOAD_FOLDER'], 'purchase_orders')
    os.makedirs(upload_folder_pos, exist_ok=True)

    if po_file and allowed_file(po_file.filename, 'ALLOWED_DOCUMENT_EXTENSIONS'): # Assuming a different set of allowed extensions
        filename_base = secure_filename(f"user_{current_user_id}_po_{uuid.uuid4().hex[:8]}")
        extension = get_file_extension(po_file.filename)
        filename = f"{filename_base}.{extension}"
        file_path_full = os.path.join(upload_folder_pos, filename)
        file_path_relative_for_db = os.path.join('purchase_orders', filename) # Relative path for DB

        try:
            po_file.save(file_path_full)

            # Create an Order with status PENDING_PO_REVIEW
            # You'll need to calculate total amount based on cart_items and B2B pricing.
            # This example simplifies and assumes total might be adjusted by admin later.
            calculated_total = 0
            order_items_to_create = []

            for item_data in cart_items:
                product_id = item_data.get('product_id')
                variant_id = item_data.get('variant_id')
                quantity = item_data.get('quantity')
                price_at_request = item_data.get('price_at_request') # Price client saw/added

                if not product_id or not quantity or price_at_request is None:
                    # Rollback potential file save if data is bad.
                    if os.path.exists(file_path_full): os.remove(file_path_full)
                    return jsonify(message="Invalid item data in PO submission.", success=False), 400
                
                calculated_total += float(price_at_request) * int(quantity)
                order_items_to_create.append({
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "quantity": quantity,
                    "unit_price": price_at_request, # Store the price they submitted with
                    "total_price": float(price_at_request) * int(quantity),
                    # You'll need to fetch product_name, variant_description if not in item_data
                    "product_name": Product.query.get(product_id).name if Product.query.get(product_id) else "Unknown Product",
                    "variant_description": ProductWeightOption.query.get(variant_id).sku_suffix if variant_id and ProductWeightOption.query.get(variant_id) else None
                })


            new_order = Order(
                user_id=current_user_id,
                is_b2b_order=True,
                status=OrderStatusEnum.PENDING_PO_REVIEW,
                total_amount=calculated_total, # This might be preliminary
                currency=b2b_user.currency or 'EUR',
                purchase_order_reference=filename, # Or a number from the PO itself if parsed
                # Populate shipping/billing from B2B user's profile or allow override
                shipping_address_line1=b2b_user.shipping_address_line1 or b2b_user.company_address_line1, # Example
                # ... other address fields ...
            )
            db.session.add(new_order)
            db.session.flush()

            for oi_data in order_items_to_create:
                db.session.add(OrderItem(order_id=new_order.id, **oi_data))

            # Link the uploaded PO file as a GeneratedAsset or a dedicated POFile model
            # For simplicity, let's assume Order model has a `po_file_path_stored`
            new_order.po_file_path_stored = file_path_relative_for_db # Add this field to Order model

            db.session.commit()
            # TODO: Notify admin of new PO submission
            current_app.logger.info(f"New B2B Purchase Order {new_order.id} submitted by user {current_user_id} with file {filename}.")

            return jsonify(message="Purchase Order submitted successfully. Awaiting review.", order_id=new_order.id, success=True), 201

        except Exception as e:
            db.session.rollback()
            # Clean up saved file if DB transaction failed
            if os.path.exists(file_path_full):
                try: os.remove(file_path_full)
                except OSError as e_clean: current_app.logger.error(f"Error cleaning up PO file {filename}: {e_clean}")
            current_app.logger.error(f"Error processing PO for user {current_user_id}: {e}", exc_info=True)
            return jsonify(message="Failed to submit Purchase Order.", error=str(e), success=False), 500
    else:
        return jsonify(message="Invalid file type for Purchase Order.", success=False), 400


# --- B2B Order Creation (for direct CC payment) - (modify existing /api/orders/create or make new) ---
# Example: Modifying /api/orders/create in backend/orders/routes.py
# You would add a check:
# if current_user and current_user.role == UserRoleEnum.B2B_PROFESSIONAL:
#     new_order.is_b2b_order = True
#     # ... potentially different tax logic ...
#     # ... call invoice_service.create_b2b_invoice_from_order(new_order.id) ...
# else:
#     # ... existing B2C logic ...
#     # ... call invoice_service.create_invoice_from_order(new_order.id) ...
