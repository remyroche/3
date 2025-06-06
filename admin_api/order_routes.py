# admin_api/order_routes.py
from flask import request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity

from . import admin_api_bp
from ..database import get_db_connection, query_db
from ..utils import admin_required, format_datetime_for_display

@admin_api_bp.route('/orders', methods=['GET'])
@admin_required
def get_orders_admin():
    """Retrieves a list of all orders for the admin panel."""
    db = get_db_connection()
    search_filter = request.args.get('search')
    status_filter = request.args.get('status')
    date_filter_str = request.args.get('date')

    query_sql = """
        SELECT o.id as order_id, o.user_id, o.order_date, o.status, o.total_amount, o.currency,
               u.email as customer_email, (u.first_name || ' ' || u.last_name) as customer_name
        FROM orders o LEFT JOIN users u ON o.user_id = u.id
    """
    conditions = []
    params = []

    if search_filter:
        conditions.append("(CAST(o.id AS TEXT) LIKE ? OR u.email LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ? OR o.payment_transaction_id LIKE ?)")
        term = f"%{search_filter}%"
        params.extend([term, term, term, term, term])
    if status_filter:
        conditions.append("o.status = ?")
        params.append(status_filter)
    if date_filter_str:
        try:
            from datetime import datetime
            datetime.strptime(date_filter_str, '%Y-%m-%d')
            conditions.append("DATE(o.order_date) = ?")
            params.append(date_filter_str)
        except ValueError:
            return jsonify(message="Invalid date format. Use YYYY-MM-DD.", success=False), 400

    if conditions:
        query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY o.order_date DESC"

    try:
        orders_data = query_db(query_sql, params, db_conn=db)
        orders = [dict(row) for row in orders_data] if orders_data else []
        for order in orders:
            order['order_date'] = format_datetime_for_display(order['order_date'])
        return jsonify(orders=orders, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin orders: {e}", exc_info=True)
        return jsonify(message="Failed to fetch orders. Please try again later.", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>', methods=['GET'])
@admin_required
def get_order_admin_detail(order_id):
    """Retrieves detailed information for a single order."""
    db = get_db_connection()
    try:
        order_data_row = query_db("SELECT o.*, u.email as customer_email, (u.first_name || ' ' || u.last_name) as customer_name FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.id = ?", [order_id], db_conn=db, one=True)
        if not order_data_row:
            return jsonify(message="Order not found.", success=False), 404
        order = dict(order_data_row)
        for dt_field in ['order_date', 'created_at', 'updated_at']:
            order[dt_field] = format_datetime_for_display(order[dt_field])

        items_data = query_db("SELECT oi.*, p.main_image_url as product_image_url FROM order_items oi LEFT JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?", [order_id], db_conn=db)
        order['items'] = []
        if items_data:
            for item_row in items_data:
                item_dict = dict(item_row)
                # This logic should be adapted if you need full URLs for images
                order['items'].append(item_dict)
        return jsonify(order=order, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin order detail for ID {order_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch order details. Please try again later.", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@admin_required
def update_order_status_admin(order_id):
    """Updates the status of an order."""
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor()
    data = request.json
    new_status = data.get('status')
    tracking_number = data.get('tracking_number')
    carrier = data.get('carrier')

    if not new_status:
        return jsonify(message="New status not provided.", success=False), 400

    allowed_statuses = ['pending_payment', 'paid', 'processing', 'awaiting_shipment', 'shipped', 'delivered', 'completed', 'cancelled', 'refunded', 'on_hold', 'failed']
    if new_status not in allowed_statuses:
        return jsonify(message=f"Invalid status. Allowed: {', '.join(allowed_statuses)}", success=False), 400

    try:
        order_info = query_db("SELECT status FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)
        if not order_info:
            return jsonify(message="Order not found", success=False), 404
        old_status = order_info['status']

        updates = {"status": new_status}
        if new_status in ['shipped', 'delivered']:
            if tracking_number:
                updates["tracking_number"] = tracking_number
            if carrier:
                updates["shipping_method"] = carrier

        set_parts = [f"{k} = ?" for k in updates] + ["updated_at = CURRENT_TIMESTAMP"]
        params = list(updates.values()) + [order_id]
        cursor.execute(f"UPDATE orders SET {', '.join(set_parts)} WHERE id = ?", tuple(params))
        db.commit()

        audit_logger.log_action(user_id=current_admin_id, action='update_order_status_admin', target_type='order', target_id=order_id, details=f"Order {order_id} status from '{old_status}' to '{new_status}'. Tracking: {tracking_number or 'N/A'}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Order status updated to {new_status}", success=True), 200

    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_order_status_admin_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        current_app.logger.error(f"Failed to update order status for ID {order_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to update order status: {str(e)}", success=False), 500


@admin_api_bp.route('/orders/<int:order_id>/notes', methods=['POST'])
@admin_required
def add_order_note_admin(order_id):
    """Adds an internal note to an order."""
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor()
    data = request.json
    note_content = data.get('note')

    if not note_content or not note_content.strip():
        return jsonify(message="Note content cannot be empty.", success=False), 400

    try:
        if not query_db("SELECT id FROM orders WHERE id = ?", [order_id], db_conn=db, one=True):
            return jsonify(message="Order not found", success=False), 404

        current_notes = query_db("SELECT notes_internal FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)['notes_internal'] or ""
        admin_info = query_db("SELECT email FROM users WHERE id = ?", [current_admin_id], db_conn=db, one=True)
        admin_id_str = admin_info['email'] if admin_info else f"AdminID:{current_admin_id}"
        new_entry = f"[{format_datetime_for_display(None)} by {admin_id_str}]: {note_content}"
        updated_notes = f"{current_notes}\n{new_entry}".strip()

        cursor.execute("UPDATE orders SET notes_internal = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (updated_notes, order_id))
        db.commit()

        audit_logger.log_action(user_id=current_admin_id, action='add_order_note_admin', target_type='order', target_id=order_id, details=f"Added note: '{note_content[:50]}...'", status='success', ip_address=request.remote_addr)
        return jsonify(message="Note added successfully.", new_note_entry=new_entry, success=True), 201

    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note_admin_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        current_app.logger.error(f"Failed to add note to order ID {order_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to add note: {str(e)}", success=False), 500

