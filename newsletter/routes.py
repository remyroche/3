# backend/newsletter/routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity # Not used in public subscribe
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import NewsletterSubscription, User # Assuming Enums are used in models
from ..utils import format_datetime_for_display, admin_required, is_valid_email

newsletter_bp = Blueprint('newsletter_bp', __name__, url_prefix='/api')

@newsletter_bp.route('/subscribe-newsletter', methods=['POST'])
def subscribe_newsletter():
    data = request.json
    email = data.get('email')
    source = data.get('source', 'website_form')
    # Expect 'Y' or True for consent, 'N' or False or missing for no consent
    consent_str = str(data.get('consent', 'N')).upper()
    consent_given = consent_str == 'Y' or consent_str == 'TRUE'
    language_code = data.get('language_code', 'unknown')[:5] # Max 5 chars for lang_code

    audit_logger = current_app.audit_log_service

    if not email:
        # ... (logging and return 400)
        audit_logger.log_action(action='newsletter_subscribe_fail_no_email', details="Email is required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email is required", success=False), 400

    if not is_valid_email(email):
        # ... (logging and return 400)
        audit_logger.log_action(action='newsletter_subscribe_fail_invalid_email', email=email, details="Invalid email format.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid email format", success=False), 400

    if not consent_given:
        audit_logger.log_action(action='newsletter_subscribe_fail_no_consent', email=email, details="Consent not given.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Consent is required to subscribe to the newsletter.", success=False), 400


    try:
        existing_subscription = NewsletterSubscription.query.filter_by(email=email).first()

        if existing_subscription and existing_subscription.is_active:
            # ... (logging and return 200)
            audit_logger.log_action(action='newsletter_subscribe_already_active', email=email, details="Email already subscribed and active.", status='info', ip_address=request.remote_addr)
            return jsonify(message="You are already subscribed to our newsletter.", success=True), 200
        
        if existing_subscription and not existing_subscription.is_active:
            existing_subscription.is_active = True
            existing_subscription.subscribed_at = datetime.now(timezone.utc)
            existing_subscription.source = source
            existing_subscription.consent = 'Y' # Update consent
            existing_subscription.language_code = language_code
            db.session.commit()
            # ... (logging and return 200)
            audit_logger.log_action(action='newsletter_resubscribe_success', target_type='newsletter_subscription', target_id=existing_subscription.id, email=email, details=f"Resubscribed from {source}, lang: {language_code}.", status='success', ip_address=request.remote_addr)
            return jsonify(message="Successfully re-subscribed to the newsletter!", success=True), 200

        else: # New subscription
            new_subscription = NewsletterSubscription(
                email=email, 
                source=source, 
                consent='Y', # Store 'Y' for consent
                language_code=language_code,
                is_active=True
            )
            db.session.add(new_subscription)
            db.session.commit()
            # ... (logging and return 201)
            audit_logger.log_action(action='newsletter_subscribe_success', target_type='newsletter_subscription', target_id=new_subscription.id, email=email, details=f"New subscription from {source}, lang: {language_code}.", status='success', ip_address=request.remote_addr)
            return jsonify(message="Successfully subscribed to the newsletter!", success=True), 201


    except IntegrityError: 
        db.session.rollback()
        # ... (logging and return 409) - This case should be rare if the above checks are done
        audit_logger.log_action(action='newsletter_subscribe_fail_integrity', email=email, details="Integrity error, email likely exists.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="This email is already registered or an error occurred.", success=False), 409

    except Exception as e:
        db.session.rollback()
        # ... (logging and return 500)
        current_app.logger.error(f"Error subscribing to newsletter for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='newsletter_subscribe_fail_server_error', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Could not subscribe to the newsletter due to a server error.", success=False), 500


# (Other newsletter routes: unsubscribe_newsletter, get_subscribers_admin remain largely the same)
@newsletter_bp.route('/unsubscribe-newsletter/<string:email>', methods=['POST'])
def unsubscribe_newsletter(email):
    # ... (existing logic) ...
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
        subscription.consent = 'N' # Explicitly mark consent as No
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
    # ... (existing logic) ...
    # Ensure Enums are converted to .value for JSON response if applicable
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
            "is_active": sub.is_active, "source": sub.source,
            "consent": sub.consent, "language_code": sub.language_code
        }
        subscribers_data.append(sub_dict)
    audit_logger.log_action(user_id=current_admin_id, action='admin_get_newsletter_subscribers', status='success', ip_address=request.remote_addr)
    return jsonify(subscribers=subscribers_data, success=True), 200
