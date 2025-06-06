# admin_api/user_routes.py
from flask import request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity
import sqlite3

from . import admin_api_bp
from ..database import get_db_connection, query_db
from ..utils import admin_required, format_datetime_for_display

@admin_api_bp.route('/users', methods=['GET'])
@admin_required
def get_users_admin():
    """Retrieves a list of users, with optional filters."""
    db = get_db_connection()
    role_filter = request.args.get('role')
    status_filter_str = request.args.get('is_active')
    search_term = request.args.get('search')

    query_sql = "SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, professional_status, created_at FROM users"
    conditions = []
    params = []

    if role_filter:
        conditions.append("role = ?")
        params.append(role_filter)
    if status_filter_str is not None:
        is_active_val = status_filter_str.lower() == 'true'
        conditions.append("is_active = ?")
        params.append(is_active_val)
    if search_term:
        conditions.append("(email LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR company_name LIKE ? OR CAST(id AS TEXT) LIKE ?)")
        term = f"%{search_term}%"
        params.extend([term, term, term, term, term])

    if conditions:
        query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY created_at DESC"

    try:
        users_data = query_db(query_sql, params, db_conn=db)
        users = [dict(row) for row in users_data] if users_data else []
        for user in users:
            user['created_at'] = format_datetime_for_display(user['created_at'])
        return jsonify(users=users, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching users for admin: {e}", exc_info=True)
        return jsonify(message=f"Failed to fetch users: {str(e)}", success=False), 500

@admin_api_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user_admin_detail(user_id):
    """Retrieves detailed information for a single user."""
    db = get_db_connection()
    try:
        user_data = query_db("SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, vat_number, siret_number, professional_status, created_at, updated_at FROM users WHERE id = ?", [user_id], db_conn=db, one=True)
        if not user_data:
            return jsonify(message="User not found", success=False), 404

        user = dict(user_data)
        user['created_at'] = format_datetime_for_display(user['created_at'])
        user['updated_at'] = format_datetime_for_display(user['updated_at'])

        orders_data = query_db("SELECT id as order_id, order_date, total_amount, status FROM orders WHERE user_id = ? ORDER BY order_date DESC", [user_id], db_conn=db)
        user['orders'] = [dict(row) for row in orders_data] if orders_data else []
        for order_item in user['orders']:
            order_item['order_date'] = format_datetime_for_display(order_item['order_date'])
        return jsonify(user=user, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin user detail for ID {user_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to fetch user details (admin): {str(e)}", success=False), 500


@admin_api_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user_admin(user_id):
    """Updates a user's details."""
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor()
    data = request.json

    if not data:
        return jsonify(message="No data provided for update.", success=False), 400

    allowed_fields = ['first_name', 'last_name', 'role', 'is_active', 'is_verified',
                      'company_name', 'vat_number', 'siret_number', 'professional_status']
    update_payload = {k: data[k] for k in data if k in allowed_fields}

    if not update_payload:
        return jsonify(message="No valid fields to update", success=False), 400

    if 'is_active' in update_payload:
        update_payload['is_active'] = str(update_payload['is_active']).lower() == 'true'
    if 'is_verified' in update_payload:
        update_payload['is_verified'] = str(update_payload['is_verified']).lower() == 'true'

    set_clause = ", ".join([f"{key} = ?" for key in update_payload.keys()])
    sql_args = list(update_payload.values()) + [user_id]

    try:
        if not query_db("SELECT id FROM users WHERE id = ?", [user_id], db_conn=db, one=True):
             return jsonify(message="User not found", success=False), 404

        cursor.execute(f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", tuple(sql_args))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify(message="User not found or no changes made", success=False), 404

        audit_logger.log_action(user_id=current_admin_id, action='update_user_admin', target_type='user', target_id=user_id, details=f"User {user_id} updated. Fields: {', '.join(update_payload.keys())}", status='success', ip_address=request.remote_addr)
        return jsonify(message="User updated successfully", success=True), 200
    except sqlite3.Error as e:
        db.rollback()
        current_app.logger.error(f"DB Error updating user {user_id}: {e}", exc_info=True)
        return jsonify(message="Failed to update user due to a database error.", success=False), 500
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating user {user_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to update user: {str(e)}", success=False), 500
