# admin_api/site_management_routes.py
from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from . import admin_api_bp
from ..database import get_db_connection, query_db
from ..utils import admin_required, sanitize_input, generate_static_json_files

# --- Review Management ---
@admin_api_bp.route('/reviews', methods=['GET'])
@admin_required
def get_reviews_admin():
    """Retrieves a list of reviews with filtering options."""
    db = get_db_connection()
    status_filter = request.args.get('status')
    product_filter = request.args.get('product_id')
    user_filter = request.args.get('user_id')

    query = """
        SELECT r.*, p.name as product_name, p.product_code, u.email as user_email
        FROM reviews r
        JOIN products p ON r.product_id = p.id
        JOIN users u ON r.user_id = u.id
    """
    conditions = []
    params = []

    if status_filter == 'pending':
        conditions.append("r.is_approved = FALSE")
    elif status_filter == 'approved':
        conditions.append("r.is_approved = TRUE")

    if product_filter:
        if product_filter.isdigit():
            conditions.append("r.product_id = ?")
            params.append(int(product_filter))
        else:
            conditions.append("(p.name LIKE ? OR p.product_code LIKE ?)")
            params.extend([f"%{product_filter}%", f"%{product_filter}%"])

    if user_filter:
        if user_filter.isdigit():
            conditions.append("r.user_id = ?")
            params.append(int(user_filter))
        else:
            conditions.append("u.email LIKE ?")
            params.append(f"%{user_filter}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY r.review_date DESC"

    try:
        reviews_data = query_db(query, params, db_conn=db)
        reviews = [dict(r) for r in reviews_data] if reviews_data else []
        for rev in reviews:
            rev['review_date'] = format_datetime_for_display(rev['review_date'])
        return jsonify(reviews=reviews, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin reviews: {e}", exc_info=True)
        return jsonify(message="Failed to fetch reviews.", success=False), 500

def _update_review_approval_admin(review_id, is_approved_status):
    """Helper function to approve or unapprove a review."""
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor()
    action = "approve" if is_approved_status else "unapprove"

    try:
        if not query_db("SELECT id FROM reviews WHERE id = ?", [review_id], db_conn=db, one=True):
            return jsonify(message="Review not found", success=False), 404
        cursor.execute("UPDATE reviews SET is_approved = ? WHERE id = ?", (is_approved_status, review_id))
        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action=f'{action}_review_admin', target_type='review', target_id=review_id, details=f"Review {review_id} set to {is_approved_status}.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Review successfully {'approved' if is_approved_status else 'unapproved'}", success=True), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action=f'{action}_review_admin_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        current_app.logger.error(f"Failed to {action} review ID {review_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to {action} review: {str(e)}", success=False), 500

@admin_api_bp.route('/reviews/<int:review_id>/approve', methods=['PUT'])
@admin_required
def approve_review_admin(review_id):
    return _update_review_approval_admin(review_id, True)

@admin_api_bp.route('/reviews/<int:review_id>/unapprove', methods=['PUT'])
@admin_required
def unapprove_review_admin(review_id):
    return _update_review_approval_admin(review_id, False)

@admin_api_bp.route('/reviews/<int:review_id>', methods=['DELETE'])
@admin_required
def delete_review_admin(review_id):
    """Deletes a review."""
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor()
    try:
        if not query_db("SELECT id FROM reviews WHERE id = ?", [review_id], db_conn=db, one=True):
            return jsonify(message="Review not found", success=False), 404
        cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin', target_type='review', target_id=review_id, details=f"Review {review_id} deleted.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Review deleted successfully", success=True), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        current_app.logger.error(f"Failed to delete review ID {review_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to delete review: {str(e)}", success=False), 500

# --- Settings Management ---
@admin_api_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings_admin():
    """Retrieves all site settings."""
    db = get_db_connection()
    try:
        settings_data = query_db("SELECT key, value, description FROM settings", db_conn=db)
        settings = {row['key']: {'value': row['value'], 'description': row['description']} for row in settings_data} if settings_data else {}
        return jsonify(settings=settings, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching settings for admin: {e}", exc_info=True)
        return jsonify(message=f"Failed to fetch settings: {str(e)}", success=False), 500

@admin_api_bp.route('/settings', methods=['POST'])
@admin_required
def update_settings_admin():
    """Updates one or more site settings."""
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor()
    data = request.json
    if not data:
        return jsonify(message="No settings data provided", success=False), 400
    updated_keys = []
    try:
        for key, value_obj in data.items():
            value = value_obj.get('value') if isinstance(value_obj, dict) else value_obj
            if value is not None:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (key, str(value)))
                updated_keys.append(key)
        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin', target_type='application_settings', details=f"Settings updated: {', '.join(updated_keys)}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Settings updated successfully", updated_settings=updated_keys, success=True), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        current_app.logger.error(f"Failed to update settings: {e}", exc_info=True)
        return jsonify(message=f"Failed to update settings: {str(e)}", success=False), 500

# --- Static File Generation ---
@admin_api_bp.route('/regenerate-static-json', methods=['POST'])
@admin_required
def regenerate_static_json_endpoint():
    """Triggers the regeneration of static JSON data files."""
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        generate_static_json_files()
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json', status='success', ip_address=request.remote_addr)
        return jsonify(message="Static JSON files regenerated successfully.", success=True), 200
    except Exception as e:
        current_app.logger.error(f"Failed to regenerate static JSON files via API: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to regenerate static JSON files: {str(e)}", success=False), 500
