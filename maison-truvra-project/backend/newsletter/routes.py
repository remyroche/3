import sqlite3
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt # For admin route
from ..database import get_db_connection, query_db # Use standardized DB access
from ..utils import format_datetime_for_display

newsletter_bp = Blueprint('newsletter', __name__, url_prefix='/api/newsletter')

# Decorator for admin-only access (similar to other modules)
def admin_required_newsletter(fn):
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get('role') != 'admin':
            return jsonify(message="Administration rights required."), 403
        # Optional: check if admin user is active
        # current_user_id = get_jwt_identity()
        # user = query_db("SELECT is_active FROM users WHERE id = ? AND role = 'admin'", [current_user_id], db_conn=get_db_connection(), one=True)
        # if not user or not user['is_active']:
        #     return jsonify(message="Admin account is not active."), 403
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


@newsletter_bp.route('/subscribe', methods=['POST'])
def subscribe_newsletter():
    data = request.json
    email = data.get('email')
    source = data.get('source', 'unknown') # Capture subscription source

    audit_logger = current_app.audit_log_service

    if not email:
        # For public endpoint, user_id is None for audit log if not logged in
        audit_logger.log_action(action='newsletter_subscribe_fail', details="Email is required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email is required"), 400

    # Basic email validation (can be more sophisticated)
    if "@" not in email or "." not in email.split("@")[-1]:
        audit_logger.log_action(action='newsletter_subscribe_fail', email=email, details="Invalid email format.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid email format"), 400

    db = get_db_connection()
    try:
        # Check if already subscribed and active
        existing_subscription = query_db(
            "SELECT id, is_active FROM newsletter_subscriptions WHERE email = ?", 
            [email], 
            db_conn=db, 
            one=True
        )

        if existing_subscription and existing_subscription['is_active']:
            audit_logger.log_action(action='newsletter_subscribe_already_active', email=email, details="Email already subscribed and active.", status='info', ip_address=request.remote_addr)
            return jsonify(message="You are already subscribed to our newsletter."), 200 # Or 208 Already Reported
        
        if existing_subscription and not existing_subscription['is_active']:
            # Re-subscribe: update is_active to TRUE and update subscribed_at and source
            cursor = db.cursor()
            cursor.execute(
                "UPDATE newsletter_subscriptions SET is_active = TRUE, subscribed_at = CURRENT_TIMESTAMP, source = ? WHERE email = ?",
                (source, email)
            )
            db.commit()
            subscription_id = existing_subscription['id']
            audit_logger.log_action(
                action='newsletter_resubscribe_success', 
                target_type='newsletter_subscription',
                target_id=subscription_id, # Log with existing ID
                email=email, 
                details=f"Email re-subscribed from source: {source}.", 
                status='success',
                ip_address=request.remote_addr
            )
            return jsonify(message="Successfully re-subscribed to the newsletter!"), 200
        else:
            # New subscription
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO newsletter_subscriptions (email, source, is_active) VALUES (?, ?, TRUE)",
                (email, source)
            )
            subscription_id = cursor.lastrowid
            db.commit()
            audit_logger.log_action(
                action='newsletter_subscribe_success', 
                target_type='newsletter_subscription',
                target_id=subscription_id,
                email=email, 
                details=f"New email subscribed from source: {source}.", 
                status='success',
                ip_address=request.remote_addr
            )
            return jsonify(message="Successfully subscribed to the newsletter!"), 201

    except sqlite3.IntegrityError: # Should be caught by the check above, but as a safeguard for email UNIQUE constraint
        db.rollback()
        # This means the email exists, but the logic above might have missed it (e.g., race condition)
        # Or it was inactive and we tried to insert again instead of update.
        # The current logic should handle re-subscription by updating.
        audit_logger.log_action(action='newsletter_subscribe_fail_integrity', email=email, details="Integrity error, email likely exists.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="This email is already registered or an error occurred."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error subscribing to newsletter for {email}: {e}")
        audit_logger.log_action(action='newsletter_subscribe_fail_server_error', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Could not subscribe to the newsletter due to a server error."), 500


@newsletter_bp.route('/unsubscribe/<string:email>', methods=['POST']) # Changed to POST for consistency or could be GET with token
def unsubscribe_newsletter(email):
    # For a public unsubscribe link, consider using a token sent via email
    # to prevent malicious unsubscribes. For now, direct email unsubscribe.
    audit_logger = current_app.audit_log_service

    if not email:
        audit_logger.log_action(action='newsletter_unsubscribe_fail', details="Email is required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email is required"), 400

    db = get_db_connection()
    try:
        subscription = query_db("SELECT id, is_active FROM newsletter_subscriptions WHERE email = ?", [email], db_conn=db, one=True)
        if not subscription or not subscription['is_active']:
            audit_logger.log_action(action='newsletter_unsubscribe_not_found_or_inactive', email=email, details="Email not found or already unsubscribed.", status='info', ip_address=request.remote_addr)
            return jsonify(message="Email not found or already unsubscribed."), 404 # Or 200 with a message

        cursor = db.cursor()
        cursor.execute("UPDATE newsletter_subscriptions SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE email = ?", [email])
        db.commit()
        
        audit_logger.log_action(
            action='newsletter_unsubscribe_success', 
            target_type='newsletter_subscription',
            target_id=subscription['id'],
            email=email, 
            status='success',
            ip_address=request.remote_addr
        )
        return jsonify(message="Successfully unsubscribed from the newsletter."), 200
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error unsubscribing from newsletter for {email}: {e}")
        audit_logger.log_action(action='newsletter_unsubscribe_fail_server_error', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Could not unsubscribe from the newsletter due to a server error."), 500


@newsletter_bp.route('/admin/subscribers', methods=['GET'])
@admin_required_newsletter # Protect this route
def get_subscribers():
    db = get_db_connection()
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    # Optional: filter by is_active
    is_active_filter = request.args.get('is_active') # 'true', 'false', or None for all

    query = "SELECT id, email, subscribed_at, is_active, source, updated_at FROM newsletter_subscriptions"
    params = []
    if is_active_filter is not None:
        query += " WHERE is_active = ?"
        params.append(is_active_filter.lower() == 'true')
    query += " ORDER BY subscribed_at DESC"

    try:
        subscribers_data = query_db(query, params, db_conn=db)
        subscribers = [dict(row) for row in subscribers_data] if subscribers_data else []
        for sub in subscribers:
            sub['subscribed_at'] = format_datetime_for_display(sub['subscribed_at'])
            sub['updated_at'] = format_datetime_for_display(sub['updated_at'])
        
        audit_logger.log_action(
            user_id=current_admin_id,
            action='get_newsletter_subscribers',
            status='success'
        )
        return jsonify(subscribers), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching newsletter subscribers by admin {current_admin_id}: {e}")
        audit_logger.log_action(
            user_id=current_admin_id,
            action='get_newsletter_subscribers_fail',
            details=str(e),
            status='failure'
        )
        return jsonify(message="Failed to fetch subscribers"), 500
