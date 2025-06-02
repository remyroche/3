import sqlite3
from flask import Blueprint, request, jsonify, current_app, g, send_from_directory, abort
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from datetime import datetime, timezone # Added timezone
import os

from ..database import get_db_connection, query_db, record_stock_movement
from ..utils import is_valid_email, format_datetime_for_display, format_datetime_for_storage
from ..services.invoice_service import InvoiceService

orders_bp = Blueprint('orders_bp', __name__, url_prefix='/api/orders')

@orders_bp.route('/create', methods=['POST'])
@jwt_required(optional=True) 
def create_order():
    data = request.get_json()
    current_app.logger.info(f"Order creation request received: {data}")

    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() # Get cursor for transaction

    user_id = get_jwt_identity()
    customer_email = data.get('customer_email')
    
    if user_id:
        user_db_info_row = query_db("SELECT email, is_verified FROM users WHERE id = ?", [user_id], db_conn=db, one=True)
        if user_db_info_row:
            user_db_info = dict(user_db_info_row)
            if user_db_info['is_verified'] and (not customer_email or customer_email != user_db_info['email']):
                customer_email = user_db_info['email']
    
    shipping_address_data = data.get('shipping_address') 
    billing_address_data = data.get('billing_address', shipping_address_data)
    cart_items_from_payload = data.get('items')
    payment_details = data.get('payment_details', {})
    
    # --- Validations ---
    if not customer_email or not is_valid_email(customer_email):
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail', details="Invalid or missing customer email.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Adresse e-mail du client invalide ou manquante.", success=False), 400
    
    required_address_keys = ['first_name', 'last_name', 'address_line1', 'city', 'postal_code', 'country']
    if not shipping_address_data or not all(k in shipping_address_data for k in required_address_keys):
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail', details="Incomplete shipping address.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Adresse de livraison incomplète.", success=False), 400
    if billing_address_data is not shipping_address_data and (not billing_address_data or not all(k in billing_address_data for k in required_address_keys)):
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail', details="Incomplete billing address.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Adresse de facturation incomplète.", success=False), 400

    if not cart_items_from_payload or not isinstance(cart_items_from_payload, list) or len(cart_items_from_payload) == 0:
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail', details="Empty or invalid cart items.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Panier vide ou invalide.", success=False), 400

    try:
        total_amount_calculated = 0
        validated_order_items = []

        for item_payload in cart_items_from_payload:
            product_id = item_payload.get('product_id')
            variant_id = item_payload.get('variant_id')
            quantity_ordered = int(item_payload.get('quantity', 0))
            
            if quantity_ordered <= 0:
                raise ValueError(f"Quantité invalide pour produit ID {product_id}.")

            product_info_row = query_db("SELECT name, sku_prefix, type, base_price, aggregate_stock_quantity FROM products WHERE id = ? AND is_active = TRUE", [product_id], db_conn=db, one=True)
            if not product_info_row: raise ValueError(f"Produit ID {product_id} non trouvé ou inactif.")
            product_info = dict(product_info_row)

            item_price_db = 0
            current_stock_db = 0
            variant_description_db = None

            if product_info['type'] == 'variable_weight' and variant_id:
                variant_info_row = query_db("SELECT price, aggregate_stock_quantity, weight_grams, sku_suffix FROM product_weight_options WHERE id = ? AND product_id = ? AND is_active = TRUE", [variant_id, product_id], db_conn=db, one=True)
                if not variant_info_row: raise ValueError(f"Variante ID {variant_id} pour produit {product_id} non trouvée ou inactive.")
                variant_info = dict(variant_info_row)
                item_price_db = variant_info['price']
                current_stock_db = variant_info['aggregate_stock_quantity']
                variant_description_db = f"{variant_info['weight_grams']}g ({variant_info['sku_suffix']})"
            elif product_info['type'] == 'simple':
                if product_info['base_price'] is None: raise ValueError(f"Prix manquant pour produit simple ID {product_id}.")
                item_price_db = product_info['base_price']
                current_stock_db = product_info['aggregate_stock_quantity']
            else: # Should not happen if product types are well-defined
                 raise ValueError(f"Type de produit non géré pour la commande: {product_info['type']}")


            if current_stock_db < quantity_ordered:
                raise ValueError(f"Stock insuffisant pour {product_info['name']} {variant_description_db or ''}. Demandé: {quantity_ordered}, Disponible: {current_stock_db}")

            total_amount_calculated += item_price_db * quantity_ordered
            validated_order_items.append({
                "product_id": product_id, "variant_id": variant_id, "serialized_item_id": None,
                "quantity": quantity_ordered, "unit_price": item_price_db,
                "total_price": item_price_db * quantity_ordered,
                "product_name": product_info['name'], "variant_description": variant_description_db
            })
        
        if payment_details.get('status') != 'succeeded':
            audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail_payment', details=f"Payment not successful. Status: {payment_details.get('status')}", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Le paiement a échoué ou n'a pas été complété.", success=False), 402

        # Insert Order
        order_date_db = format_datetime_for_storage(datetime.now(timezone.utc))
        cursor.execute(
            """INSERT INTO orders (user_id, order_date, status, total_amount, currency, 
                                 shipping_address_line1, shipping_address_line2, shipping_city, shipping_postal_code, shipping_country,
                                 billing_address_line1, billing_address_line2, billing_city, billing_postal_code, billing_country,
                                 payment_method, payment_transaction_id, notes_customer)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, order_date_db, 'paid', total_amount_calculated, 'EUR',
             shipping_address_data['address_line1'], shipping_address_data.get('address_line2'), shipping_address_data['city'], shipping_address_data['postal_code'], shipping_address_data['country'],
             billing_address_data['address_line1'], billing_address_data.get('address_line2'), billing_address_data['city'], billing_address_data['postal_code'], billing_address_data['country'],
             payment_details.get('method'), payment_details.get('transaction_id'), data.get('customer_notes'))
        )
        order_id = cursor.lastrowid

        for item in validated_order_items:
            cursor.execute(
                """INSERT INTO order_items (order_id, product_id, variant_id, serialized_item_id, quantity, unit_price, total_price, product_name, variant_description) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (order_id, item['product_id'], item['variant_id'], item['serialized_item_id'], 
                 item['quantity'], item['unit_price'], item['total_price'], item['product_name'], item['variant_description'])
            )
            record_stock_movement(db, item['product_id'], 'sale', quantity_change=-item['quantity'], variant_id=item['variant_id'], related_order_id=order_id, reason=f"Sale for order #{order_id}")

        db.commit() # Commit transaction
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_success', target_type='order', target_id=order_id, details=f"Order created. Total: {total_amount_calculated}", status='success', ip_address=request.remote_addr)
        
        # Placeholder for email sending
        current_app.logger.info(f"Simulated order confirmation email for order #{order_id} to {customer_email}")

        return jsonify(message="Commande passée avec succès !", success=True, order_id=order_id, total_amount=round(total_amount_calculated, 2)), 201

    except ValueError as ve:
        if db: db.rollback()
        current_app.logger.warning(f"Validation error during order creation: {ve}")
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail_validation', details=str(ve), status='failure', ip_address=request.remote_addr)
        return jsonify(message=str(ve), success=False), 400
    except sqlite3.Error as dbe:
        if db: db.rollback()
        current_app.logger.error(f"Database error during order creation: {dbe}", exc_info=True)
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail_db_error', details=str(dbe), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Erreur de base de données lors de la création de la commande.", success=False), 500
    except Exception as e:
        if db: db.rollback()
        current_app.logger.error(f"Unexpected error during order creation: {e}", exc_info=True)
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail_server_error', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Une erreur interne est survenue lors de la création de la commande.", success=False), 500

@orders_bp.route('/history', methods=['GET'])
@jwt_required()
def get_order_history():
    current_user_id = get_jwt_identity()
    db = get_db_connection()
    audit_logger = current_app.audit_log_service

    try:
        orders_data = query_db(
            "SELECT id, order_date, status, total_amount, currency FROM orders WHERE user_id = ? ORDER BY order_date DESC",
            [current_user_id], db_conn=db
        )
        orders = [dict(row) for row in orders_data] if orders_data else []
        for order in orders:
            order['order_date'] = format_datetime_for_display(order['order_date'])
        
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
    db = get_db_connection()
    audit_logger = current_app.audit_log_service

    try:
        order_data_row = query_db(
            """SELECT o.*, u.email as customer_email 
               FROM orders o 
               JOIN users u ON o.user_id = u.id 
               WHERE o.id = ? AND o.user_id = ?""",
            [order_id, current_user_id], 
            db_conn=db, 
            one=True
        )
        
        if not order_data_row:
            audit_logger.log_action(user_id=current_user_id, action='get_order_detail_fail_not_found_or_unauthorized', target_type='order', target_id=order_id, status='failure', ip_address=request.remote_addr)
            return jsonify(message="Order not found or access denied.", success=False), 404
        order = dict(order_data_row)
            
        order['order_date'] = format_datetime_for_display(order['order_date'])
        order['created_at'] = format_datetime_for_display(order['created_at'])
        order['updated_at'] = format_datetime_for_display(order['updated_at'])
        
        items_data = query_db(
            """SELECT oi.id as item_id, oi.product_id, oi.product_name, oi.quantity, 
                      oi.unit_price, oi.total_price, oi.variant_description, oi.variant_id
               FROM order_items oi
               WHERE oi.order_id = ?""", [order_id], db_conn=db)
        order['items'] = [dict(row) for row in items_data] if items_data else []
        
        audit_logger.log_action(user_id=current_user_id, action='get_order_detail_success', target_type='order', target_id=order_id, status='success', ip_address=request.remote_addr)
        return jsonify(order=order, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching public order details for order {order_id}, user {current_user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='get_order_detail_fail_server_error', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to fetch order details.", success=False), 500


# Add this new route to your orders blueprint to TRIGGER invoice generation
@orders_bp.route('/<int:order_id>/generate-invoice', methods=['POST'])
@jwt_required()
def generate_invoice_for_order(order_id):
    """
    Endpoint for an admin to generate an invoice for a specific order.
    """
    claims = get_jwt()
    # Ensure only admins can perform this action
    if claims.get('role') != 'admin':
        return jsonify(message="Forbidden: Admins only"), 403

    try:
        invoice_service = InvoiceService()
        invoice_id = invoice_service.create_invoice_from_order(order_id)
        if invoice_id:
            return jsonify(success=True, message="Invoice generated successfully.", invoice_id=invoice_id), 201
        else:
            return jsonify(success=False, message="Invoice might already exist or failed to generate."), 409
    except ValueError as ve:
        return jsonify(message=str(ve)), 404
    except Exception as e:
        current_app.logger.error(f"API error generating invoice for order {order_id}: {e}")
        return jsonify(message="An internal error occurred during invoice generation."), 500


# Add this new route to download an invoice
@orders_bp.route('/invoices/download/<int:invoice_id>', methods=['GET'])
@jwt_required()
def download_invoice(invoice_id):
    """
    Allows a user to download their own invoice, or an admin to download any.
    """
    user_id = get_jwt_identity()
    claims = get_jwt()
    is_admin = claims.get('role') == 'admin'

    db = get_db_connection()
    invoice = query_db("SELECT * FROM invoices WHERE id = ?", [invoice_id], db_conn=db, one=True)

    if not invoice:
        abort(404, "Invoice not found.")

    # Security Check: User can only access their own invoices, unless they are an admin
    if not is_admin and invoice['b2b_user_id'] != user_id:
        abort(403, "You do not have permission to access this invoice.")

    pdf_path = invoice.get('pdf_path')
    if not pdf_path or not os.path.exists(pdf_path):
        abort(404, "Invoice file not found on server. It may need to be regenerated.")
    
    directory = os.path.dirname(pdf_path)
    filename = os.path.basename(pdf_path)

    try:
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        current_app.logger.error(f"Error sending invoice file {filename}: {e}")
        abort(500)

