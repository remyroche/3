# backend/newsletter/routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError # For handling unique constraint violations

from .. import db # Import SQLAlchemy instance
from ..models import NewsletterSubscription, User # Import NewsletterSubscription model
from ..utils import format_datetime_for_display, admin_required, is_valid_email

newsletter_bp = Blueprint('newsletter_bp', __name__, url_prefix='/api')

@newsletter_bp.route('/subscribe-newsletter', methods=['POST'])
def subscribe_newsletter():
    data = request.json
    email = data.get('email')
    source = data.get('source', 'website_form')
    consent = 'Y' # Implicit consent by subscribing

    audit_logger = current_app.audit_log_service

    if not email:
        audit_logger.log_action(action='newsletter_subscribe_fail_no_email', details="Email is required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email is required", success=False), 400
    if not is_valid_email(email):
        audit_logger.log_action(action='newsletter_subscribe_fail_invalid_email', email=email, details="Invalid email format.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid email format", success=False), 400

    try:
        existing_subscription = NewsletterSubscription.query.filter_by(email=email).first()

        if existing_subscription and existing_subscription.is_active:
            audit_logger.log_action(action='newsletter_subscribe_already_active', email=email, details="Email already subscribed and active.", status='info', ip_address=request.remote_addr)
            return jsonify(message="You are already subscribed to our newsletter.", success=True), 200
        
        if existing_subscription and not existing_subscription.is_active:
            existing_subscription.is_active = True
            existing_subscription.subscribed_at = db.func.current_timestamp() # Reset subscription date
            existing_subscription.source = source
            existing_subscription.consent = consent
            db.session.commit()
            audit_logger.log_action(action='newsletter_resubscribe_success', target_type='newsletter_subscription', target_id=existing_subscription.id, email=email, details=f"Resubscribed from {source}.", status='success', ip_address=request.remote_addr)
            return jsonify(message="Successfully re-subscribed to the newsletter!", success=True), 200
        else:
            new_subscription = NewsletterSubscription(
                email=email, 
                source=source, 
                consent=consent, 
                is_active=True
            )
            db.session.add(new_subscription)
            db.session.commit()
            audit_logger.log_action(action='newsletter_subscribe_success', target_type='newsletter_subscription', target_id=new_subscription.id, email=email, details=f"New subscription from {source}.", status='success', ip_address=request.remote_addr)
            return jsonify(message="Successfully subscribed to the newsletter!", success=True), 201

    except IntegrityError: # Handles unique email constraint violation
        db.session.rollback()
        audit_logger.log_action(action='newsletter_subscribe_fail_integrity', email=email, details="Integrity error, email likely exists.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="This email is already registered or an error occurred.", success=False), 409
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error subscribing to newsletter for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='newsletter_subscribe_fail_server_error', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Could not subscribe to the newsletter due to a server error.", success=False), 500

@newsletter_bp.route('/unsubscribe-newsletter/<string:email>', methods=['POST'])
def unsubscribe_newsletter(email):
    audit_logger = current_app.audit_log_service
    if not email or not is_valid_email(email):
        audit_logger.log_action(action='newsletter_unsubscribe_fail_invalid_email', email=email, details="Invalid email for unsubscribe.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Valid email required for unsubscribe", success=False), 400

    try:
        subscription = NewsletterSubscription.query.filter_by(email=email).first()
        if not subscription or not subscription.is_active:
            audit_logger.log_action(action='newsletter_unsubscribe_not_found_or_inactive', email=email, details="Email not subscribed or already inactive.", status='info', ip_address=request.remote_addr)
            return jsonify(message="Email not found or already unsubscribed.", success=True), 200

        subscription.is_active = False
        # Consider adding an 'unsubscribed_at' field if needed
        # subscription.updated_at = db.func.current_timestamp() # Handled by model's onupdate
        db.session.commit()
        audit_logger.log_action(action='newsletter_unsubscribe_success', target_type='newsletter_subscription', target_id=subscription.id, email=email, status='success', ip_address=request.remote_addr)
        return jsonify(message="Successfully unsubscribed from the newsletter.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unsubscribing from newsletter for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='newsletter_unsubscribe_fail_server_error', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Could not unsubscribe due to a server error.", success=False), 500

@newsletter_bp.route('/admin/subscribers', methods=['GET'])
@admin_required
def get_subscribers_admin():
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    is_active_filter_str = request.args.get('is_active')
    
    query = NewsletterSubscription.query
    if is_active_filter_str is not None:
        is_active_val = is_active_filter_str.lower() == 'true'
        query = query.filter_by(is_active=is_active_val)
    
    subscribers_models = query.order_by(NewsletterSubscription.subscribed_at.desc()).all()
    
    subscribers_data = []
    for sub in subscribers_models:
        sub_dict = {
            "id": sub.id, "email": sub.email, 
            "subscribed_at": format_datetime_for_display(sub.subscribed_at),
            "is_active": sub.is_active, "source": sub.source
            # "updated_at": format_datetime_for_display(sub.updated_at) # If you have an updated_at field
        }
        subscribers_data.append(sub_dict)
        
    audit_logger.log_action(user_id=current_admin_id, action='admin_get_newsletter_subscribers', status='success', ip_address=request.remote_addr)
    return jsonify(subscribers=subscribers_data, success=True), 200
