from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import stripe
from models import db, Order, OrderItem, Cart, CartItem, Payment, B2BUser
from models.enums import OrderStatus, PaymentStatus
from config import Config
from services.b2b_invoice_service import create_b2b_invoice_from_order
from services.b2b_loyalty_service import get_discount_for_tier, add_points_for_order

order_blueprint = Blueprint('order', __name__)
stripe.api_key = Config.STRIPE_SECRET_KEY # Ensure you have this in your config


@order_blueprint.route('/create_order', methods=['POST'])
@login_required
def create_order():
    data = request.get_json()
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart or not cart.items:
        return jsonify({'error': 'Your cart is empty'}), 400

    total_amount = cart.get_total_price()
    discount_amount = 0

    # --- APPLY LOYALTY DISCOUNT FOR B2B USERS ---
    if isinstance(current_user, B2BUser):
        discount_percent = get_discount_for_tier(current_user.loyalty_tier)
        if discount_percent > 0:
            discount_amount = (total_amount * discount_percent) / 100
            total_amount -= discount_amount
    # ---------------------------------------------
    
    final_amount = round(total_amount, 2)

    try:
        new_order = Order(
            user_id=current_user.id,
            total_amount=final_amount,
            status=OrderStatus.PENDING
        )
        db.session.add(new_order)
        db.session.flush()

        for item in cart.items:
            order_item = OrderItem(order_id=new_order.id, product_id=item.product_id, quantity=item.quantity, price=item.product.price)
            db.session.add(order_item)

        payment_intent = stripe.PaymentIntent.create(
            amount=int(final_amount * 100),
            currency='eur',
            metadata={'order_id': new_order.id}
        )
        
        new_payment = Payment(order_id=new_order.id, stripe_payment_intent_id=payment_intent.id, amount=final_amount, status=PaymentStatus.PENDING)
        db.session.add(new_payment)

        CartItem.query.filter_by(cart_id=cart.id).delete()
        db.session.commit()

        return jsonify({'clientSecret': payment_intent.client_secret})

    except Exception as e:
        db.session.rollback()
        return jsonify(error=str(e)), 500


@order_blueprint.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    # This should be your Stripe Webhook Signing Secret
    endpoint_secret = "whsec_..." 

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        return 'Invalid signature', 400

    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        order_id = payment_intent['metadata']['order_id']
        
        order = Order.query.get(order_id)
        if order:
            # --- AWARD LOYALTY POINTS ---
            add_points_for_order(order)
            # --------------------------

            # ... (rest of the logic for order/payment status update and B2C/B2B invoice)
            if isinstance(order.user, B2BUser):
                create_b2b_invoice_from_order(order)
            db.session.commit()
            
    return 'Success', 200



@orders_bp.route('/history', methods=['GET'])
@jwt_required()
def get_order_history():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        # B2B users see all orders linked to their user_id where is_b2b_order is true
        # B2C users see all orders linked to their user_id where is_b2b_order is false (or null if old orders)
        user = User.query.get(current_user_id)
        if not user:
            return jsonify(message="User not found.", success=False), 404

        query = Order.query.filter_by(user_id=current_user_id)
        if user.role == UserRoleEnum.B2B_PROFESSIONAL:
            query = query.filter_by(is_b2b_order=True)
        else: # B2C or other roles if any
            query = query.filter(Order.is_b2b_order == False) # Explicitly check for False for B2C

        orders_models = query.order_by(Order.order_date.desc()).all()
        
        orders_data = []
        for o_model in orders_models:
            orders_data.append({
                'id': o_model.id,
                'order_date': format_datetime_for_display(o_model.order_date),
                'status': o_model.status.value if o_model.status else None,
                'total_amount': o_model.total_amount,
                'currency': o_model.currency,
                'invoice_number': o_model.invoice.invoice_number if o_model.invoice else None
            })
        audit_logger.log_action(user_id=current_user_id, action='get_order_history_success', status='success', ip_address=request.remote_addr)
        return jsonify(orders=orders_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching order history for user {current_user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='get_order_history_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Erreur serveur lors de la récupération de l'historique des commandes.", success=False), 500


@orders_bp.route('/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order_details_public(order_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        # User can only access their own orders.
        order_model = Order.query.filter_by(id=order_id, user_id=current_user_id).first()
        if not order_model:
            audit_logger.log_action(user_id=current_user_id, action='get_order_detail_fail_auth', target_type='order', target_id=order_id, status='failure', ip_address=request.remote_addr)
            return jsonify(message="Order not found or access denied.", success=False), 404
            
        # Use a more comprehensive to_dict if available, or build manually
        order_details = {
            'id': order_model.id,
            'order_date': format_datetime_for_display(order_model.order_date),
            'status': order_model.status.value if order_model.status else None,
            'total_amount': order_model.total_amount,
            'currency': order_model.currency,
            'shipping_address': {
                'first_name': order_model.shipping_first_name,
                'last_name': order_model.shipping_last_name,
                'company_name': order_model.shipping_company_name,
                'address_line1': order_model.shipping_address_line1,
                'address_line2': order_model.shipping_address_line2,
                'city': order_model.shipping_city,
                'postal_code': order_model.shipping_postal_code,
                'country': order_model.shipping_country,
                'phone': order_model.shipping_phone
            },
            'billing_address': { # Populate similarly
                'first_name': order_model.billing_first_name,
                'last_name': order_model.billing_last_name,
                'company_name': order_model.billing_company_name,
                'address_line1': order_model.billing_address_line1,
                # ...
            },
            'payment_method': order_model.payment_method,
            'notes_customer': order_model.notes_customer,
            'is_b2b_order': order_model.is_b2b_order,
            'purchase_order_reference': order_model.purchase_order_reference,
            'invoice_number': order_model.invoice.invoice_number if order_model.invoice else None,
            'invoice_download_url': url_for('orders_bp.download_invoice', invoice_id=order_model.invoice_id, _external=True) if order_model.invoice_id else None,
            'items': []
        }
        for item_model in order_model.items:
            order_details['items'].append({
                'product_name': item_model.product_name,
                'variant_description': item_model.variant_description,
                'quantity': item_model.quantity,
                'unit_price': item_model.unit_price,
                'total_price': item_model.total_price,
                'product_slug': item_model.product.slug if item_model.product else None, # For linking
                'product_image_url': item_model.product.main_image_url if item_model.product else None # For display
            })
        
        audit_logger.log_action(user_id=current_user_id, action='get_order_detail_public_success', target_type='order', target_id=order_id, status='success', ip_address=request.remote_addr)
        return jsonify(order=order_details, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching public order details for order {order_id}, user {current_user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='get_order_detail_public_fail_exception', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to fetch order details.", success=False), 500



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

    user_id = get_jwt_identity()
    claims = get_jwt()
    is_admin_role = claims.get('role') == UserRoleEnum.ADMIN.value

    invoice = db.session.get(Invoice, invoice_id)

    if not invoice:
        current_app.logger.warning(f"Invoice download attempt for non-existent invoice ID {invoice_id} by user {user_id}.")
        abort(404, description="Invoice not found.")

    # Authorization check: Admin, B2B owner, or B2C owner of the linked order
    can_access = False
    if is_admin_role:
        can_access = True
    elif invoice.b2b_user_id and invoice.b2b_user_id == user_id: # B2B user owns this invoice
        can_access = True
    elif invoice.order and invoice.order.user_id == user_id: # User owns the order linked to this (B2C) invoice
        can_access = True
    
    if not can_access:
        current_app.logger.warning(f"Unauthorized attempt to download invoice ID {invoice_id} by user {user_id}.")
        abort(403, description="You do not have permission to access this invoice.")

    if not invoice.pdf_path:
        current_app.logger.error(f"Invoice PDF path missing for invoice ID {invoice_id}")
        abort(404, description="Invoice file path not found on server. It may need to be (re)generated.")

    asset_storage_directory = current_app.config['ASSET_STORAGE_PATH']
    
    if ".." in invoice.pdf_path or invoice.pdf_path.startswith("/"):
        current_app.logger.error(f"Invalid PDF path for invoice {invoice_id}: {invoice.pdf_path}")
        abort(400, description="Invalid invoice file path.")

    full_file_path = os.path.join(asset_storage_directory, invoice.pdf_path)
    if not os.path.exists(full_file_path) or not os.path.isfile(full_file_path):
        current_app.logger.error(f"Invoice PDF file not found at: {full_file_path} for invoice ID {invoice_id}")
        abort(404, description="Invoice file not found on server. It may need to be (re)generated.")

    try:
        current_app.audit_log_service.log_action(user_id=user_id, action='download_invoice', target_type='invoice', target_id=invoice_id, status='success', ip_address=request.remote_addr)
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
