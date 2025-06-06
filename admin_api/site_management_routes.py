# backend/admin_api/site_management_routes.py
# Admin routes for managing site-wide features like reviews and settings.

from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, or_
from datetime import datetime, timezone

from . import admin_api_bp
from .. import db
from ..models import Review, Product, User, Setting
from ..utils import admin_required, sanitize_input, generate_static_json_files

# --- Review Management ---
@admin_api_bp.route('/reviews', methods=['GET'])
@admin_required
def get_reviews_admin():
    status_filter_str = sanitize_input(request.args.get('status')) 
    product_filter = sanitize_input(request.args.get('product_id'))
    user_filter = sanitize_input(request.args.get('user_id'))

    query = Review.query.join(Product, Review.product_id == Product.id)\
                        .join(User, Review.user_id == User.id)
    
    if status_filter_str == 'pending': query = query.filter(Review.is_approved == False)
    elif status_filter_str == 'approved': query = query.filter(Review.is_approved == True)
    
    if product_filter:
        if product_filter.isdigit():
            query = query.filter(Review.product_id == int(product_filter))
        else:
            term_like_prod = f"%{product_filter.lower()}%"
            query = query.filter(or_(func.lower(Product.name).like(term_like_prod), 
                                     func.lower(Product.product_code).like(term_like_prod)))
    if user_filter:
        if user_filter.isdigit():
            query = query.filter(Review.user_id == int(user_filter))
        else:
            query = query.filter(func.lower(User.email).like(f"%{user_filter.lower()}%"))
            
    try:
        reviews_models = query.order_by(Review.review_date.desc()).all()
        reviews_data = [{
            "id": r.id, "product_id": r.product_id, "user_id": r.user_id,
            "rating": r.rating, "comment": r.comment,
            "review_date": r.review_date.isoformat(),
            "is_approved": r.is_approved,
            "product_name": r.product.name, "product_code": r.product.product_code,
            "user_email": r.user.email
        } for r in reviews_models]
        return jsonify(reviews=reviews_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin reviews: {e}", exc_info=True)
        return jsonify(message="Failed to fetch reviews.", success=False), 500

def _update_review_approval_admin(review_id, is_approved_status):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    action_str = "approve" if is_approved_status else "unapprove"
    
    review = Review.query.get_or_404(review_id)
    review.is_approved = is_approved_status
    review.updated_at = datetime.now(timezone.utc)
    try:
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action=f'{action_str}_review_admin_success', target_type='review', target_id=review_id, details=f"Review set to approved={is_approved_status}.", status='success')
        return jsonify(message=f"Review successfully {action_str}d.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to {action_str} review ID {review_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to {action_str} review.", success=False), 500

@admin_api_bp.route('/reviews/<int:review_id>/approve', methods=['PUT'])
@admin_required
def approve_review_admin(review_id): return _update_review_approval_admin(review_id, True)

@admin_api_bp.route('/reviews/<int:review_id>/unapprove', methods=['PUT'])
@admin_required
def unapprove_review_admin(review_id): return _update_review_approval_admin(review_id, False)

@admin_api_bp.route('/reviews/<int:review_id>', methods=['DELETE'])
@admin_required
def delete_review_admin(review_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    review = Review.query.get_or_404(review_id)
    try:
        db.session.delete(review)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin_success', target_type='review', target_id=review_id, status='success')
        return jsonify(message="Review deleted successfully.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete review ID {review_id}: {e}", exc_info=True)
        return jsonify(message="Failed to delete review.", success=False), 500

# --- Settings Management ---
@admin_api_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings_admin():
    try:
        settings_models = Setting.query.all()
        settings_data = {s.key: {'value': s.value, 'description': s.description} for s in settings_models}
        return jsonify(settings=settings_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching settings for admin: {e}", exc_info=True)
        return jsonify(message="Failed to fetch settings.", success=False), 500

@admin_api_bp.route('/settings', methods=['POST'])
@admin_required
def update_settings_admin():
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    data = request.json
    if not data: return jsonify(message="No settings data provided.", success=False), 400
    
    updated_keys = []
    try:
        for key, value_obj_or_direct_value in data.items():
            safe_key = sanitize_input(str(key))
            if not safe_key: continue
            value_to_store = sanitize_input(str(value_obj_or_direct_value), allow_html=False)
            
            setting = Setting.query.get(safe_key)
            if setting:
                if setting.value != value_to_store:
                    setting.value = value_to_store
                    setting.updated_at = datetime.now(timezone.utc)
                    updated_keys.append(safe_key)
            else:
                db.session.add(Setting(key=safe_key, value=value_to_store, description=data.get(f"{safe_key}_description")))
                updated_keys.append(safe_key)
        
        if updated_keys:
            db.session.commit()
            audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin_success', target_type='application_settings', details=f"Settings updated: {', '.join(updated_keys)}", status='success')
            return jsonify(message="Settings updated successfully.", updated_settings=updated_keys, success=True), 200
        else:
            return jsonify(message="No settings were changed.", success=True), 200
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update settings: {e}", exc_info=True)
        return jsonify(message="Failed to update settings.", success=False), 500

# --- Static File Generation ---
@admin_api_bp.route('/site-data/regenerate-static-json', methods=['POST'])
@admin_required
def regenerate_static_json_endpoint():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        result = generate_static_json_files() 
        if result and (result.get("product_errors") or result.get("category_errors")):
            audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json_with_errors', status='warning', ip_address=request.remote_addr, details=str(result))
            return jsonify(message="Static JSON files regenerated with some errors.", success=True, errors=result), 207
        
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json_success', status='success', ip_address=request.remote_addr)
        return jsonify(message="Static JSON files regenerated successfully.", success=True), 200
    except Exception as e:
        current_app.logger.error(f"Failed to regenerate static JSON files via API: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to regenerate static JSON files: {str(e)}", success=False), 500
