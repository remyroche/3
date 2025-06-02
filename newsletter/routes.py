import sqlite3
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..database import get_db_connection, query_db
from ..utils import format_datetime_for_display, admin_required, is_valid_email # Use centralized admin_required

newsletter_bp = Blueprint('newsletter_bp', __name__, url_prefix='/api') # Prefix is /api

@newsletter_bp.route('/subscribe-newsletter', methods=['POST']) # Full path /api/subscribe-newsletter
def subscribe_newsletter():
    data = request.json
    email = data.get('email')
    source = data.get('source', 'website_form') # Default source
    # Consent is implicitly 'Y' by subscribing via this route. Schema has NOT NULL for consent.
    consent = 'Y' 

    audit_logger = current_app.audit_log_service

    if not email:
        audit_logger.log_action(action='newsletter_subscribe_fail_no_email', details="Email is required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email is required", success=False), 400
    if not is_valid_email(email): # Use utility
        audit_logger.log_action(action='newsletter_subscribe_fail_invalid_email', email=email, details="Invalid email format.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid email format", success=False), 400

    db = get_db_connection()
    try:
        existing_subscription = query_db("SELECT id, is_active FROM newsletter_subscriptions WHERE email = ?", [email], db_conn=db, one=True)

        if existing_subscription and existing_subscription['is_active']:
            audit_logger.log_action(action='newsletter_subscribe_already_active', email=email, details="Email already subscribed and active.", status='info', ip_address=request.remote_addr)
            return jsonify(message="You are already subscribed to our newsletter.", success=True), 200
        
        if existing_subscription and not existing_subscription['is_active']:
            query_db("UPDATE newsletter_subscriptions SET is_active = TRUE, subscribed_at = CURRENT_TIMESTAMP, source = ?, consent = ? WHERE email = ?", (source, consent, email), db_conn=db, commit=True)
            audit_logger.log_action(action='newsletter_resubscribe_success', target_type='newsletter_subscription', target_id=existing_subscription['id'], email=email, details=f"Resubscribed from {source}.", status='success', ip_address=request.remote_addr)
            return jsonify(message="Successfully re-subscribed to the newsletter!", success=True), 200
        else:
            last_id = query_db("INSERT INTO newsletter_subscriptions (email, source, consent, is_active) VALUES (?, ?, ?, TRUE)", (email, source, consent), db_conn=db, commit=True)
            audit_logger.log_action(action='newsletter_subscribe_success', target_type='newsletter_subscription', target_id=last_id, email=email, details=f"New subscription from {source}.", status='success', ip_address=request.remote_addr)
            return jsonify(message="Successfully subscribed to the newsletter!", success=True), 201

    except sqlite3.IntegrityError:
        db.rollback()
        audit_logger.log_action(action='newsletter_subscribe_fail_integrity', email=email, details="Integrity error, email likely exists.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="This email is already registered or an error occurred.", success=False), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error subscribing to newsletter for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='newsletter_subscribe_fail_server_error', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Could not subscribe to the newsletter due to a server error.", success=False), 500

@newsletter_bp.route('/unsubscribe-newsletter/<string:email>', methods=['POST']) # Or GET with a token
def unsubscribe_newsletter(email):
    audit_logger = current_app.audit_log_service
    if not email or not is_valid_email(email):
        audit_logger.log_action(action='newsletter_unsubscribe_fail_invalid_email', email=email, details="Invalid email for unsubscribe.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Valid email required for unsubscribe", success=False), 400

    db = get_db_connection()
    try:
        subscription = query_db("SELECT id, is_active FROM newsletter_subscriptions WHERE email = ?", [email], db_conn=db, one=True)
        if not subscription or not subscription['is_active']:
            audit_logger.log_action(action='newsletter_unsubscribe_not_found_or_inactive', email=email, details="Email not subscribed or already inactive.", status='info', ip_address=request.remote_addr)
            return jsonify(message="Email not found or already unsubscribed.", success=True), 200 # Or 404

        query_db("UPDATE newsletter_subscriptions SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE email = ?", [email], db_conn=db, commit=True)
        audit_logger.log_action(action='newsletter_unsubscribe_success', target_type='newsletter_subscription', target_id=subscription['id'], email=email, status='success', ip_address=request.remote_addr)
        return jsonify(message="Successfully unsubscribed from the newsletter.", success=True), 200
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error unsubscribing from newsletter for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='newsletter_unsubscribe_fail_server_error', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Could not unsubscribe due to a server error.", success=False), 500

@newsletter_bp.route('/admin/subscribers', methods=['GET']) # Path is /api/admin/subscribers
@admin_required # Use centralized admin_required
def get_subscribers_admin(): # Renamed to avoid conflict if blueprint prefix was different
    db = get_db_connection()
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    is_active_filter_str = request.args.get('is_active')
    query = "SELECT id, email, subscribed_at, is_active, source, updated_at FROM newsletter_subscriptions"
    params = []
    if is_active_filter_str is not None:
        query += " WHERE is_active = ?"
        params.append(is_active_filter_str.lower() == 'true')
    query += " ORDER BY subscribed_at DESC"

    try:
        subscribers_data = query_db(query, params, db_conn=db)
        subscribers = [dict(row) for row in subscribers_data] if subscribers_data else []
        for sub in subscribers:
            sub['subscribed_at'] = format_datetime_for_display(sub['subscribed_at'])
            sub['updated_at'] = format_datetime_for_display(sub['updated_at'])
        
        audit_logger.log_action(user_id=current_admin_id, action='admin_get_newsletter_subscribers', status='success', ip_address=request.remote_addr)
        return jsonify(subscribers), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching newsletter subscribers by admin {current_admin_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='admin_get_newsletter_subscribers_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to fetch subscribers"), 500
