# backend/orders/routes.py
from flask import Blueprint, request, jsonify, current_app, url_for, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone

from .. import db
from ..models import Order, OrderItem, Product, ProductWeightOption, User
from ..utils import is_valid_email, format_datetime_for_display, format_datetime_for_storage
from ..services.invoice_service import InvoiceService # Assuming this service is also updated or doesn't directly use old DB methods
from ..database import record_stock_movement # Keep this if it's complex and you adapt it for SQLAlchemy session

orders_bp = Blueprint('orders_bp', __name__, url_prefix='/api/orders')

@orders_bp.route('/create', methods=['POST'])
@jwt_required(optional=True)
def create_order():
    data = request.get_json()
    current_app.logger.info(f"Order creation request received (SQLAlchemy): {data}")
    audit_logger = current_app.audit_log_service
    
    user_id = get_jwt_identity()
    customer_email = data.get('customer_email')
    
    if user_id:
        user_db_info = User.query.get(user_id)
        if user_db_info and user_db_info.is_verified and (not customer_email or customer_email != user_db_info.email):
            customer_email = user_db_info.email
    
    shipping_address_data = data.get('shipping_address')
    billing_address_data = data.get('billing_address', shipping_address_data)
    cart_items_from_payload = data.get('items')
    payment_details = data.get('payment_details', {})
    
    if not customer_email or not is_valid_email(customer_email):
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail', details="Invalid or missing customer email.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Adresse e-mail du client invalide ou manquante.", success=False), 400
    
    required_address_keys = ['first_name', 'last_name', 'address_line1', 'city', 'postal_code', 'country']
    if not shipping_address_data or not all(k in shipping_address_data for k in required_address_keys):
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail', details="Incomplete shipping address.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Adresse de livraison incomplète.", success=False), 400
    # ... (similar validation for billing_address_data) ...

    if not cart_items_from_payload or not isinstance(cart_items_from_payload, list) or len(cart_items_from_payload) == 0:
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail', details="Empty or invalid cart items.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Panier vide ou invalide.", success=False), 400

    try:
        total_amount_calculated = 0
        validated_order_items_data = [] # To store data for creating OrderItem models

        for item_payload in cart_items_from_payload:
            product_id = item_payload.get('product_id')
            variant_id = item_payload.get('variant_id') # This is product_weight_options.id
            quantity_ordered = int(item_payload.get('quantity', 0))
            
            if quantity_ordered <= 0:
                raise ValueError(f"Quantité invalide pour produit ID {product_id}.")

            product_info = Product.query.filter_by(id=product_id, is_active=True).first()
            if not product_info: raise ValueError(f"Produit ID {product_id} non trouvé ou inactif.")

            item_price_db = 0
            current_stock_db = 0
            variant_description_db = None

            if product_info.type == 'variable_weight' and variant_id:
                variant_info = ProductWeightOption.query.filter_by(id=variant_id, product_id=product_id, is_active=True).first()
                if not variant_info: raise ValueError(f"Variante ID {variant_id} pour produit {product_id} non trouvée ou inactive.")
                item_price_db = variant_info.price
                current_stock_db = variant_info.aggregate_stock_quantity
                variant_description_db = f"{variant_info.weight_grams}g ({variant_info.sku_suffix})"
            elif product_info.type == 'simple':
                if product_info.base_price is None: raise ValueError(f"Prix manquant pour produit simple ID {product_id}.")
                item_price_db = product_info.base_price
                current_stock_db = product_info.aggregate_stock_quantity
            else:
                 raise ValueError(f"Type de produit non géré pour la commande: {product_info.type}")

            if current_stock_db < quantity_ordered:
                raise ValueError(f"Stock insuffisant pour {product_info.name} {variant_description_db or ''}. Demandé: {quantity_ordered}, Disponible: {current_stock_db}")

            total_amount_calculated += item_price_db * quantity_ordered
            validated_order_items_data.append({
                "product_id": product_id, "variant_id": variant_id, "serialized_item_id": None, # Handle serialized items if applicable
                "quantity": quantity_ordered, "unit_price": item_price_db,
                "total_price": item_price_db * quantity_ordered,
                "product_name": product_info.name, "variant_description": variant_description_db
            })
        
        if payment_details.get('status') != 'succeeded': # Assuming 'succeeded' from Stripe or payment gateway
            audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail_payment', details=f"Payment not successful. Status: {payment_details.get('status')}", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Le paiement a échoué ou n'a pas été complété.", success=False), 402

        # Create Order
        new_order = Order(
            user_id=user_id, # Can be None for guest checkout if schema allows
            order_date=datetime.now(timezone.utc),
            status='paid', # Or 'processing' depending on workflow
            total_amount=total_amount_calculated,
            currency='EUR',
            shipping_address_line1=shipping_address_data['address_line1'],
            shipping_address_line2=shipping_address_data.get('address_line2'),
            shipping_city=shipping_address_data['city'],
            shipping_postal_code=shipping_address_data['postal_code'],
            shipping_country=shipping_address_data['country'],
            billing_address_line1=billing_address_data['address_line1'],
            billing_address_line2=billing_address_data.get('address_line2'),
            billing_city=billing_address_data['city'],
            billing_postal_code=billing_address_data['postal_code'],
            billing_country=billing_address_data['country'],
            payment_method=payment_details.get('method'),
            payment_transaction_id=payment_details.get('transaction_id'),
            notes_customer=data.get('customer_notes')
        )
        db.session.add(new_order)
        db.session.flush() # To get new_order.id before adding items

        for item_data in validated_order_items_data:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item_data['product_id'],
                variant_id=item_data['variant_id'],
                # serialized_item_id logic would go here if applicable
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                total_price=item_data['total_price'],
                product_name=item_data['product_name'],
                variant_description=item_data['variant_description']
            )
            db.session.add(order_item)
            # Stock movement recording needs to be adapted for SQLAlchemy session
            record_stock_movement(db.session, item_data['product_id'], 'sale', 
                                  quantity_change=-item_data['quantity'], 
                                  variant_id=item_data['variant_id'], 
                                  related_order_id=new_order.id, 
                                  reason=f"Sale for order #{new_order.id}")

        db.session.commit()
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_success', target_type='order', target_id=new_order.id, details=f"Order created. Total: {total_amount_calculated}", status='success', ip_address=request.remote_addr)
        
        # current_app.logger.info(f"Simulated order confirmation email for order #{new_order.id} to {customer_email}")

        return jsonify(message="Commande passée avec succès !", success=True, order_id=new_order.id, total_amount=round(total_amount_calculated, 2)), 201

    except ValueError as ve:
        db.session.rollback()
        current_app.logger.warning(f"Validation error during order creation: {ve}")
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail_validation', details=str(ve), status='failure', ip_address=request.remote_addr)
        return jsonify(message=str(ve), success=False), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error during order creation: {e}", exc_info=True)
        audit_logger.log_action(user_id=user_id, email=customer_email, action='create_order_fail_server_error', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Une erreur interne est survenue lors de la création de la commande.", success=False), 500

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
                'status': o_model.status,
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
            
        order_details = {
            'id': order_model.id,
            'user_id': order_model.user_id,
            'customer_email': order_model.customer.email if order_model.customer else None, # Assuming 'customer' is the backref name
            'order_date': format_datetime_for_display(order_model.order_date),
            'status': order_model.status,
            'total_amount': order_model.total_amount,
            # ... (include all necessary fields from Order model) ...
            'shipping_address_line1': order_model.shipping_address_line1,
            # ...
            'created_at': format_datetime_for_display(order_model.created_at),
            'updated_at': format_datetime_for_display(order_model.updated_at),
            'items': []
        }
        
        for item_model in order_model.items: # Assuming 'items' is the relationship name
            order_details['items'].append({
                'item_id': item_model.id,
                'product_id': item_model.product_id,
                'product_name': item_model.product_name,
                'quantity': item_model.quantity,
                'unit_price': item_model.unit_price,
                'total_price': item_model.total_price,
                'variant_description': item_model.variant_description,
                'variant_id': item_model.variant_id
            })
        
        audit_logger.log_action(user_id=current_user_id, action='get_order_detail_success', target_type='order', target_id=order_id, status='success', ip_address=request.remote_addr)
        return jsonify(order=order_details, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching public order details for order {order_id}, user {current_user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='get_order_detail_fail_server_error', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to fetch order details.", success=False), 500

@orders_bp.route('/<int:order_id>/generate-invoice', methods=['POST'])
@jwt_required() # Should be @admin_required if only admins can do this
def generate_invoice_for_order(order_id):
    # claims = get_jwt()
    # if claims.get('role') != 'admin':
    #     return jsonify(message="Forbidden: Admins only"), 403
    # This should ideally be in an admin blueprint or have stronger role checks.
    # For now, assuming any authenticated user can (which is likely not desired).

    try:
        invoice_service = InvoiceService() # InvoiceService needs to be adapted for SQLAlchemy
        invoice_id, invoice_number = invoice_service.create_invoice_from_order(order_id) # Pass order_id
        if invoice_id:
            return jsonify(success=True, message="Invoice generated successfully.", invoice_id=invoice_id, invoice_number=invoice_number), 201
        else:
            return jsonify(success=False, message="Invoice might already exist or failed to generate."), 409
    except ValueError as ve:
        return jsonify(message=str(ve), success=False), 404 # Or 400 for bad input
    except Exception as e:
        current_app.logger.error(f"API error generating invoice for order {order_id}: {e}", exc_info=True)
        return jsonify(message="An internal error occurred during invoice generation.", success=False), 500

@orders_bp.route('/invoices/download/<int:invoice_id>', methods=['GET'])
@jwt_required()
def download_invoice(invoice_id):
    user_id = get_jwt_identity()
    claims = get_jwt()
    is_admin = claims.get('role') == 'admin'

    invoice = db.session.get(Invoice, invoice_id) # Use db.session.get for primary key lookup

    if not invoice:
        abort(404, "Invoice not found.")

    if not is_admin and invoice.b2b_user_id != user_id and (not invoice.order or invoice.order.user_id != user_id) :
         abort(403, "You do not have permission to access this invoice.")

    pdf_path = invoice.pdf_path
    if not pdf_path or not os.path.exists(pdf_path): # Check absolute path
        current_app.logger.error(f"Invoice PDF file not found at path: {pdf_path} for invoice ID {invoice_id}")
        abort(404, "Invoice file not found on server. It may need to be regenerated.")
    
    directory = os.path.dirname(pdf_path)
    filename = os.path.basename(pdf_path)

    try:
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        current_app.logger.error(f"Error sending invoice file {filename}: {e}", exc_info=True)
        abort(500)
