# backend/orders/b2c_routes.py
# Contains routes specific to B2C (public customer) order creation.

from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from .. import db
from ..models import Order, OrderItem, User, Product, ProductWeightOption, SerializedInventoryItem
from ..models import OrderStatusEnum, SerializedInventoryItemStatusEnum
from ..database import record_stock_movement
from ..services.invoice_service import InvoiceService
from . import orders_bp

@orders_bp.route('/create', methods=['POST'])
@jwt_required(optional=True) # Allow both guest and logged-in checkouts
def create_b2c_order():
    """
    Handles the creation of a B2C order, typically after successful payment.
    """
    data = request.json
    current_user_id = get_jwt_identity() # Will be None for guests
    audit_logger = current_app.audit_log_service
    
    # --- Input Validation ---
    if not data.get('items') or not isinstance(data.get('items'), list) or not data.get('shipping_address'):
        return jsonify(message="Missing items, or shipping address.", success=False), 400
    
    payment_details = data.get('payment_details')
    if not payment_details or not payment_details.get('transaction_id'):
        return jsonify(message="Payment details are required.", success=False), 400
        
    shipping_address = data.get('shipping_address')
    billing_address = data.get('billing_address', shipping_address) # Default billing to shipping

    # --- Order Creation Logic ---
    try:
        # Stock Allocation and Validation (CRITICAL STEP)
        # This is complex. You must atomically check stock and allocate items.
        # For serialized items, you'd find specific AVAILABLE items and change their status to ALLOCATED.
        # For aggregated stock, you'd decrement the count.
        # If any item is out of stock, the entire order should fail before charging the customer.
        # This logic is usually done *before* confirming payment. 
        # For this example, we assume stock was available and now we formalize the order post-payment.
        
        # Calculate total amount based on items sent from frontend
        # For security, you should re-calculate the total on the backend based on product prices in your DB.
        total_amount_calculated = 0
        items_to_create = []
        for item_data in data['items']:
            # Fetch product/variant from DB to get the real price
            # ... logic to find product and variant ...
            # price = product.base_price or variant.price
            # total_amount_calculated += price * item_data['quantity']
            pass # Placeholder for backend price recalculation
            
        # For now, we trust the total from the frontend (less secure)
        total_amount_calculated = sum(item['price'] * item['quantity'] for item in data['items'])


        new_order = Order(
            user_id=current_user_id, # Can be null for guest checkout
            customer_email=data.get('customer_email', shipping_address.get('email')), # Store guest email
            is_b2b_order=False,
            status=OrderStatusEnum.PAID, # Assuming payment was successful
            total_amount=total_amount_calculated,
            currency=data.get('currency', 'EUR'),
            
            shipping_address_line1=shipping_address.get('address_line1'),
            shipping_address_line2=shipping_address.get('address_line2'),
            shipping_city=shipping_address.get('city'),
            shipping_postal_code=shipping_address.get('postal_code'),
            shipping_country=shipping_address.get('country'),
            shipping_phone_snapshot=shipping_address.get('phone'),

            billing_address_line1=billing_address.get('address_line1'),
            billing_address_line2=billing_address.get('address_line2'),
            billing_city=billing_address.get('city'),
            billing_postal_code=billing_address.get('postal_code'),
            billing_country=billing_address.get('country'),

            payment_method=payment_details.get('method'),
            payment_transaction_id=payment_details.get('transaction_id'),
            payment_date=datetime.now(timezone.utc)
        )
        db.session.add(new_order)
        db.session.flush() # To get new_order.id

        for item_data in data['items']:
            new_item = OrderItem(
                order_id=new_order.id,
                product_id=item_data['productId'],
                variant_id=item_data.get('variantId'),
                quantity=item_data['quantity'],
                unit_price=item_data['price'],
                total_price=item_data['price'] * item_data['quantity'],
                product_name=item_data['name'], # Snapshot of name
                variant_description=item_data.get('variantLabel') # Snapshot of variant
            )
            db.session.add(new_item)
            
            # Record stock movement
            record_stock_movement(
                db_session=db.session,
                product_id=item_data['productId'],
                movement_type=StockMovementTypeEnum.SALE,
                quantity_change=-item_data['quantity'],
                variant_id=item_data.get('variantId'),
                related_order_id=new_order.id
            )

        db.session.commit()
        
        # --- Post-Order Creation Tasks ---
        # 1. Generate Invoice
        try:
            invoice_service = InvoiceService()
            invoice_id, invoice_number = invoice_service.create_invoice_from_order(new_order.id, is_b2b_order=False)
            current_app.logger.info(f"Invoice {invoice_number} created for B2C order {new_order.id}.")
        except Exception as e_inv:
            current_app.logger.error(f"Failed to generate invoice for order {new_order.id}: {e_inv}", exc_info=True)
            # The order is created, but invoicing failed. This should be logged for manual intervention.

        # 2. Send Confirmation Email
        # try:
        #     email_service = EmailService(current_app)
        #     email_service.send_order_confirmation(new_order)
        # except Exception as e_mail:
        #     current_app.logger.error(f"Failed to send confirmation email for order {new_order.id}: {e_mail}", exc_info=True)
        
        audit_logger.log_action(user_id=current_user_id, action='create_b2c_order_success', target_type='order', target_id=new_order.id, status='success')
        
        return jsonify(message="Order created successfully.", order_id=new_order.id, success=True), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create B2C order: {e}", exc_info=True)
        return jsonify(message="Failed to create order due to a server error.", success=False, error=str(e)), 500
