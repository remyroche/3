from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, B2BUser, Quote, Order, OrderItem, Product
from models.enums import OrderStatus

order_blueprint = Blueprint('b2b_order', __name__)

@order_blueprint.route('/quotes', methods=['GET'])
@login_required
def get_quotes():
    """
    Get all quotes for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
    
    quotes = Quote.query.filter_by(user_id=current_user.id).all()
    return jsonify([quote.to_dict() for quote in quotes])

@order_blueprint.route('/orders', methods=['GET'])
@login_required
def get_orders():
    """
    Get all orders for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
        
    orders = Order.query.filter_by(user_id=current_user.id).all()
    return jsonify([order.to_dict() for order in orders])


@order_blueprint.route('/quote_to_order', methods=['POST'])
@login_required
def quote_to_order():
    """
    Convert a quote to an order for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403

    data = request.get_json()
    quote_id = data.get('quote_id')
    if not quote_id:
        return jsonify({'error': 'Quote ID is required'}), 400

    quote = Quote.query.get(quote_id)
    if not quote or quote.user_id != current_user.id:
        return jsonify({'error': 'Quote not found or access denied'}), 404

    if quote.order_id:
        return jsonify({'error': 'Quote has already been converted to an order'}), 400

    # Create a new order
    new_order = Order(
        user_id=current_user.id,
        total_amount=quote.total_price,
        status=OrderStatus.PENDING
    )
    db.session.add(new_order)
    db.session.flush()  # To get the new_order.id

    # Create order items from quote items
    for quote_item in quote.items:
        product = Product.query.get(quote_item.product_id)
        if not product:
            db.session.rollback()
            return jsonify({'error': f'Product with id {quote_item.product_id} not found'}), 404
            
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=quote_item.product_id,
            quantity=quote_item.quantity,
            price=product.price  # Use current product price
        )
        db.session.add(order_item)

    # Link the order to the quote
    quote.order_id = new_order.id
    
    db.session.commit()

    return jsonify({'success': True, 'order_id': new_order.id})
