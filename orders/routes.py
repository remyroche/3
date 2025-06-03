# backend/orders/routes.py
import os
from flask import Blueprint, request, jsonify, current_app, url_for, abort, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone

from .. import db
from ..models import Order, OrderItem, Product, ProductWeightOption, User, Invoice # Assuming Enums are used
from ..models import OrderStatusEnum, ProductTypeEnum # Import necessary Enums
from ..utils import is_valid_email, format_datetime_for_display, format_datetime_for_storage
from ..services.invoice_service import InvoiceService
from ..database import record_stock_movement

orders_bp = Blueprint('orders_bp', __name__, url_prefix='/api/orders')

# --- Helper Functions for create_order ---
def _validate_order_payload(data, user_id, customer_email):
    """Validates basic order payload data."""
    audit_logger = current_app.audit_log_service
    if not customer_email or not is_valid_email(customer_email):
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail_validation', details="Invalid or missing customer email.", status='failure', ip_address=request.remote_addr)
        raise ValueError("Adresse e-mail du client invalide ou manquante.")
    
    shipping_address_data = data.get('shipping_address')
    required_address_keys = ['first_name', 'last_name', 'address_line1', 'city', 'postal_code', 'country']
    if not shipping_address_data or not all(k in shipping_address_data for k in required_address_keys):
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail_validation', details="Incomplete shipping address.", status='failure', ip_address=request.remote_addr)
        raise ValueError("Adresse de livraison incomplète.")
    
    cart_items_from_payload = data.get('items')
    if not cart_items_from_payload or not isinstance(cart_items_from_payload, list) or len(cart_items_from_payload) == 0:
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail_validation', details="Empty or invalid cart items.", status='failure', ip_address=request.remote_addr)
        raise ValueError("Panier vide ou invalide.")
    
    payment_details = data.get('payment_details', {})
    if payment_details.get('status') != 'succeeded':
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail_payment', details=f"Payment not successful. Status: {payment_details.get('status')}", status='failure', ip_address=request.remote_addr)
        raise ValueError("Le paiement a échoué ou n'a pas été complété.")
    return shipping_address_data, data.get('billing_address', shipping_address_data), cart_items_from_payload, payment_details

def _process_cart_items_for_order(cart_items_payload):
    """Validates cart items, checks stock, and calculates total."""
    total_amount_calculated = 0
    validated_order_items_data = []
    items_for_stock_update = []

    for item_payload in cart_items_payload:
        product_id = item_payload.get('product_id')
        variant_id = item_payload.get('variant_id')
        quantity_ordered = int(item_payload.get('quantity', 0))
        
        if quantity_ordered <= 0: raise ValueError(f"Quantité invalide pour produit ID {product_id}.")

        product_info = Product.query.filter_by(id=product_id, is_active=True).first()
        if not product_info: raise ValueError(f"Produit ID {product_id} non trouvé ou inactif.")

        item_price_db = 0; current_stock_db = 0; variant_description_db = None

        if product_info.type == ProductTypeEnum.VARIABLE_WEIGHT and variant_id:
            variant_info = ProductWeightOption.query.filter_by(id=variant_id, product_id=product_id, is_active=True).first()
            if not variant_info: raise ValueError(f"Variante ID {variant_id} pour produit {product_id} non trouvée ou inactive.")
            item_price_db = variant_info.price
            current_stock_db = variant_info.aggregate_stock_quantity
            variant_description_db = f"{variant_info.weight_grams}g ({variant_info.sku_suffix})"
        elif product_info.type == ProductTypeEnum.SIMPLE:
            if product_info.base_price is None: raise ValueError(f"Prix manquant pour produit simple ID {product_id}.")
            item_price_db = product_info.base_price
            current_stock_db = product_info.aggregate_stock_quantity
        else: raise ValueError(f"Type de produit non géré pour la commande: {product_info.type.value}")

        if current_stock_db < quantity_ordered:
            raise ValueError(f"Stock insuffisant pour {product_info.name} {variant_description_db or ''}. Demandé: {quantity_ordered}, Disponible: {current_stock_db}")

        total_amount_calculated += item_price_db * quantity_ordered
        validated_order_items_data.append({
            "product_id": product_id, "variant_id": variant_id, "quantity": quantity_ordered, 
            "unit_price": item_price_db, "total_price": item_price_db * quantity_ordered,
            "product_name": product_info.name, "variant_description": variant_description_db
        })
        items_for_stock_update.append({
            "product_id": product_id, "variant_id": variant_id, "quantity_change": -quantity_ordered
        })
    return total_amount_calculated, validated_order_items_data, items_for_stock_update

def _create_order_in_db(user_id, customer_email, shipping_address, billing_address, payment_details, total_amount, validated_items, customer_notes):
    """Creates Order and OrderItem records in the database."""
    new_order = Order(
        user_id=user_id, 
        order_date=datetime.now(timezone.utc),
        status=OrderStatusEnum.PAID, # Or PROCESSING
        total_amount=total_amount,
        currency='EUR',
        shipping_address_line1=shipping_address['address_line1'],
        shipping_address_line2=shipping_address.get('address_line2'),
        shipping_city=shipping_address['city'],
        shipping_postal_code=shipping_address['postal_code'],
        shipping_country=shipping_address['country'],
        billing_address_line1=billing_address['address_line1'],
        billing_address_line2=billing_address.get('address_line2'),
        billing_city=billing_address['city'],
        billing_postal_code=billing_address['postal_code'],
        billing_country=billing_address['country'],
        payment_method=payment_details.get('method'),
        payment_transaction_id=payment_details.get('transaction_id'),
        notes_customer=customer_notes
    )
    db.session.add(new_order)
    db.session.flush() 

    for item_data in validated_items:
        order_item = OrderItem(order_id=new_order.id, **item_data) # Unpack relevant fields
        db.session.add(order_item)
    return new_order
# --- End Helper Functions ---

@orders_bp.route('/create', methods=['POST'])
@jwt_required(optional=True)
def create_order():
    data = request.get_json()
    current_app.logger.info(f"Order creation request received (SQLAlchemy): {data}")
    audit_logger = current_app.audit_log_service
    
    user_id = get_jwt_identity()
    customer_email = data.get('customer_email')
    
    if user_id: # If logged in, use their verified email if available
        user_db_info = User.query.get(user_id)
        if user_db_info and user_db_info.is_verified:
            customer_email = user_db_info.email # Override/ensure with logged-in user's email
    
    try:
        shipping_address, billing_address, cart_items_payload, payment_details = _validate_order_payload(data, user_id, customer_email)
        total_amount, validated_items_data, items_for_stock_update = _process_cart_items_for_order(cart_items_payload)
        
        new_order = _create_order_in_db(user_id, customer_email, shipping_address, billing_address, payment_details, total_amount, validated_items_data, data.get('customer_notes'))

        for stock_item in items_for_stock_update:
            record_stock_movement(db.session, stock_item['product_id'], 'sale', 
                                  quantity_change=stock_item['quantity_change'], 
                                  variant_id=stock_item['variant_id'], 
                                  related_order_id=new_order.id, 
                                  reason=f"Sale for order #{new_order.id}")
        
        # Attempt to generate invoice automatically for B2C customer after successful order creation
        # This assumes the InvoiceService is robust and handles its own errors.
        invoice_id = None
        invoice_number = None
        if new_order.customer and new_order.customer.role == UserRoleEnum.B2C_CUSTOMER: # Check if customer is B2C
            try:
                invoice_service = InvoiceService()
                inv_id, inv_num = invoice_service.create_invoice_from_order(new_order.id)
                invoice_id = inv_id
                invoice_number = inv_num
                new_order.invoice_id = invoice_id # Link invoice to order
                current_app.logger.info(f"Invoice {invoice_number} automatically generated for B2C order {new_order.id}.")
            except Exception as e_inv:
                current_app.logger.error(f"Failed to auto-generate invoice for B2C order {new_order.id}: {e_inv}", exc_info=True)
                # Continue with order creation even if invoice fails, but log it.

        db.session.commit()
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_success', target_type='order', target_id=new_order.id, details=f"Order created. Total: {total_amount}", status='success', ip_address=request.remote_addr)
        
        return jsonify(message="Commande passée avec succès !", success=True, order_id=new_order.id, total_amount=round(total_amount, 2), invoice_id=invoice_id, invoice_number=invoice_number), 201

    except ValueError as ve:
        db.session.rollback()
        current_app.logger.warning(f"Validation error during order creation: {ve}")
        # Audit log for validation failure is handled within _validate_order_payload or _process_cart_items_for_order
        return jsonify(message=str(ve), success=False), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error during order creation: {e}", exc_info=True)
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail_server_error', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Une erreur interne est survenue lors de la création de la commande.", success=False), 500

@orders_bp.route('/<int:order_id>/generate-invoice', methods=['POST'])
@jwt_required() 
def generate_invoice_for_order(order_id):
    current_user_id = get_jwt_identity()
    order = Order.query.filter_by(id=order_id, user_id=current_user_id).first()

    if not order:
        return jsonify(message="Order not found or you are not authorized to access it.", success=False), 404
    
    # This endpoint is now primarily for B2C users to trigger invoice generation if it wasn't done,
    # or for an admin to re-trigger. The main auto-generation happens in create_order.
    # If an invoice already exists, we can just return its details.
    if order.invoice_id:
        existing_invoice = Invoice.query.get(order.invoice_id)
        if existing_invoice:
             return jsonify(success=True, message="Invoice already exists for this order.", invoice_id=existing_invoice.id, invoice_number=existing_invoice.invoice_number), 200


    # Only allow B2C customers to trigger this for their own orders if not already generated.
    # Admins would use a separate, admin-protected endpoint if they need to manually generate.
    if order.customer.role != UserRoleEnum.B2C_CUSTOMER:
         return jsonify(message="Invoice generation via this endpoint is for B2C customer orders.", success=False), 403

    try:
        invoice_service = InvoiceService()
        invoice_id, invoice_number = invoice_service.create_invoice_from_order(order_id)
        if invoice_id:
            order.invoice_id = invoice_id # Link invoice to order if not already
            db.session.commit()
            current_app.audit_log_service.log_action(user_id=current_user_id, action='user_triggered_invoice_generation', target_type='order', target_id=order_id, details=f"Invoice {invoice_number} generated.", status='success', ip_address=request.remote_addr)
            return jsonify(success=True, message="Invoice generated successfully.", invoice_id=invoice_id, invoice_number=invoice_number), 201
        else: # Should not happen if create_invoice_from_order throws error or returns existing
            return jsonify(success=False, message="Failed to generate invoice or it might already exist."), 409
    except ValueError as ve: # From InvoiceService if order not found, etc.
        return jsonify(message=str(ve), success=False), 400 
    except Exception as e:
        current_app.logger.error(f"API error generating invoice for order {order_id}: {e}", exc_info=True)
        return jsonify(message="An internal error occurred during invoice generation.", success=False), 500


@orders_bp.route('/invoices/download/<int:invoice_id>', methods=['GET'])
@jwt_required()
def download_invoice(invoice_id):
    user_id = get_jwt_identity()
    claims = get_jwt()
    is_admin = claims.get('role') == UserRoleEnum.ADMIN.value # Check against Enum value

    invoice = db.session.get(Invoice, invoice_id)

    if not invoice: abort(404, description="Invoice not found.")

    # Authorization check
    is_b2b_owner = invoice.b2b_user_id == user_id
    is_order_owner = invoice.order and invoice.order.user_id == user_id
    
    if not (is_admin or is_b2b_owner or is_order_owner):
         abort(403, description="You do not have permission to access this invoice.")

    if not invoice.pdf_path:
        current_app.logger.error(f"Invoice PDF path missing for invoice ID {invoice_id}")
        abort(404, description="Invoice file path not found on server. It may need to be (re)generated.")

    # Construct the absolute path to the directory containing the 'invoices' subfolder
    # ASSET_STORAGE_PATH should be like '/abs/path/to/instance/generated_assets'
    # invoice.pdf_path should be like 'invoices/INV-XYZ.pdf'
    asset_storage_directory = current_app.config['ASSET_STORAGE_PATH']
    
    # The filename for send_from_directory is the path relative to the directory provided.
    # So, if invoice.pdf_path is 'invoices/INV-XYZ.pdf', and asset_storage_directory is the root
    # of where 'invoices' folder is located, then invoice.pdf_path is correct.
    
    # Ensure invoice.pdf_path is a relative path from asset_storage_directory
    # Example: if ASSET_STORAGE_PATH = '/var/www/app/instance/generated_assets'
    # and invoice.pdf_path = 'invoices/INV-001.pdf'
    # then send_from_directory(directory='/var/www/app/instance/generated_assets', path='invoices/INV-001.pdf')
    
    # Security check: prevent path traversal if invoice.pdf_path is somehow manipulated
    if ".." in invoice.pdf_path or invoice.pdf_path.startswith("/"):
        current_app.logger.error(f"Invalid PDF path for invoice {invoice_id}: {invoice.pdf_path}")
        abort(400, description="Invalid invoice file path.")

    full_file_path = os.path.join(asset_storage_directory, invoice.pdf_path)
    if not os.path.exists(full_file_path) or not os.path.isfile(full_file_path):
        current_app.logger.error(f"Invoice PDF file not found at absolute path: {full_file_path} (derived from {asset_storage_directory} and {invoice.pdf_path}) for invoice ID {invoice_id}")
        abort(404, description="Invoice file not found on server. It may need to be (re)generated.")

    try:
        # send_from_directory expects the directory and then the filename (or relative path within that directory)
        # If invoice.pdf_path is 'invoices/filename.pdf', then asset_storage_directory is the base.
        return send_from_directory(asset_storage_directory, invoice.pdf_path, as_attachment=True)
    except Exception as e:
        current_app.logger.error(f"Error sending invoice file {invoice.pdf_path}: {e}", exc_info=True)
        abort(500, description="Error serving invoice file.")

# (Other order routes: get_order_history, get_order_details_public remain largely the same,
# ensure they use .value for Enums in responses if applicable)
@orders_bp.route('/history', methods=['GET'])
@jwt_required()
def get_order_history():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        orders_models = Order.query.filter_by(user_id=current_user_id).order_by(Order.order_date.desc()).all()
        orders = []
        for o_model in orders_models:
            orders.append({
                'id': o_model.id,
                'order_date': format_datetime_for_display(o_model.order_date),
                'status': o_model.status.value if o_model.status else None, # Use .value for Enum
                'total_amount': o_model.total_amount,
                'currency': o_model.currency
            })
        audit_logger.log_action(user_id=current_user_id, action='get_order_history', status='success', ip_address=request.remote_addr)
        return jsonify(orders=orders, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching order history for user {current_user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='get_order_history_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Erreur serveur lors de la récupération de l'historique.", success=False), 500

@orders_bp.route('/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order_details_public(order_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        order_model = Order.query.filter_by(id=order_id, user_id=current_user_id).first()
        if not order_model:
            audit_logger.log_action(user_id=current_user_id, action='get_order_detail_fail_not_found_or_unauthorized', target_type='order', target_id=order_id, status='failure', ip_address=request.remote_addr)
            return jsonify(message="Order not found or access denied.", success=False), 404
            
        order_details = order_model.to_dict() if hasattr(order_model, 'to_dict') else {
            'id': order_model.id, 'user_id': order_model.user_id,
            'customer_email': order_model.customer.email if order_model.customer else None,
            'order_date': format_datetime_for_display(order_model.order_date),
            'status': order_model.status.value if order_model.status else None, # Use .value for Enum
            'total_amount': order_model.total_amount,
            'shipping_address_line1': order_model.shipping_address_line1, # etc.
            'created_at': format_datetime_for_display(order_model.created_at),
            'updated_at': format_datetime_for_display(order_model.updated_at),
            'items': []
        }
        if not hasattr(order_model, 'to_dict'): # Manual population if no to_dict
             order_details['items'] = [] # Ensure items is initialized
             for item_model in order_model.items:
                order_details['items'].append({
                    'item_id': item_model.id, 'product_id': item_model.product_id,
                    'product_name': item_model.product_name, 'quantity': item_model.quantity,
                    'unit_price': item_model.unit_price, 'total_price': item_model.total_price,
                    'variant_description': item_model.variant_description, 'variant_id': item_model.variant_id
                })
        
        audit_logger.log_action(user_id=current_user_id, action='get_order_detail_success', target_type='order', target_id=order_id, status='success', ip_address=request.remote_addr)
        return jsonify(order=order_details, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching public order details for order {order_id}, user {current_user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='get_order_detail_fail_server_error', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to fetch order details.", success=False), 500
