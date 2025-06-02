import sqlite3
from flask import Blueprint, request, jsonify, current_app, g
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required, 
    get_jwt_identity, get_jwt
)
from datetime import datetime, timedelta, timezone
import secrets

from ..database import get_db_connection, query_db
from ..utils import (
    parse_datetime_from_iso, 
    format_datetime_for_storage, 
    format_datetime_for_display,
    is_valid_email
)
# from ..services.email_service import send_email # Uncomment when email service is ready

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/auth') # Keep /auth prefix for these routes

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    role = data.get('role', 'b2c_customer') 

    company_name = data.get('company_name')
    vat_number = data.get('vat_number')
    siret_number = data.get('siret_number')

    audit_logger = current_app.audit_log_service

    if not email or not password:
        audit_logger.log_action(action='register_fail', email=email, details="Email and password are required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email and password are required"), 400
    if not is_valid_email(email):
        audit_logger.log_action(action='register_fail', email=email, details="Invalid email format.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid email format"), 400


    if role not in ['b2c_customer', 'b2b_professional']:
        audit_logger.log_action(action='register_fail', email=email, details="Invalid role specified.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid role specified"), 400

    db = get_db_connection()
    try:
        if query_db("SELECT id FROM users WHERE email = ?", [email], db_conn=db, one=True):
            audit_logger.log_action(action='register_fail', email=email, details="Email already registered.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Email already registered"), 409

        password_hash = generate_password_hash(password)
        verification_token = secrets.token_urlsafe(32)
        verification_token_expires_at = format_datetime_for_storage(datetime.now(timezone.utc) + timedelta(hours=24))
        
        professional_status = None
        if role == 'b2b_professional':
            if not company_name or not siret_number:
                audit_logger.log_action(action='register_fail_b2b', email=email, details="Company name and SIRET are required for B2B.", status='failure', ip_address=request.remote_addr)
                return jsonify(message="Company name and SIRET number are required for professional accounts."), 400
            professional_status = 'pending'

        cursor = db.cursor()
        cursor.execute(
            """INSERT INTO users (email, password_hash, first_name, last_name, role, 
                                verification_token, verification_token_expires_at,
                                company_name, vat_number, siret_number, professional_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (email, password_hash, first_name, last_name, role, 
             verification_token, verification_token_expires_at,
             company_name, vat_number, siret_number, professional_status)
        )
        user_id = cursor.lastrowid
        db.commit()

        # verification_link = f"{current_app.config.get('FRONTEND_URL', 'http://localhost:8000')}/verify-email?token={verification_token}"
        # try:
        #     send_email(to_email=email, subject="Verify Your Email - Maison Trüvra", body_html=f"<p>Please verify your email: <a href='{verification_link}'>{verification_link}</a></p>")
        #     audit_logger.log_action(user_id=user_id, action='verification_email_sent', target_type='user', target_id=user_id, status='success', ip_address=request.remote_addr)
        # except Exception as e_mail:
        #     current_app.logger.error(f"Failed to send verification email to {email}: {e_mail}")
        #     audit_logger.log_action(user_id=user_id, action='verification_email_fail', target_type='user', target_id=user_id, details=str(e_mail), status='failure', ip_address=request.remote_addr)
        current_app.logger.info(f"Simulated sending verification email to {email} with token {verification_token}")

        audit_logger.log_action(user_id=user_id, action='register_success', target_type='user', target_id=user_id, details=f"User {email} registered as {role}.", status='success', ip_address=request.remote_addr)
        return jsonify(message="User registered successfully. Please check your email to verify your account.", user_id=user_id, success=True), 201

    except sqlite3.IntegrityError:
        db.rollback()
        audit_logger.log_action(action='register_fail_integrity', email=email, details="Email already registered (DB integrity).", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email already registered"), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error during registration for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='register_fail_server_error', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Registration failed due to a server error"), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    audit_logger = current_app.audit_log_service

    if not email or not password:
        audit_logger.log_action(action='login_fail_missing_fields', email=email, details="Email and password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email and password are required"), 400

    db = get_db_connection()
    user_data = query_db("SELECT id, email, password_hash, role, is_active, is_verified, first_name, last_name, company_name, professional_status FROM users WHERE email = ?", [email], db_conn=db, one=True)

    if user_data and check_password_hash(user_data['password_hash'], password):
        user = dict(user_data)
        if not user['is_active']:
            audit_logger.log_action(user_id=user['id'], action='login_fail_inactive', target_type='user', target_id=user['id'], details="Account is inactive.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Account is inactive. Please contact support."), 403
        
        if user['role'] == 'b2c_customer' and not user['is_verified']:
            audit_logger.log_action(user_id=user['id'], action='login_fail_unverified', target_type='user', target_id=user['id'], details="B2C account not verified.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Account not verified. Please check your email for verification link."), 403
        
        if user['role'] == 'b2b_professional' and user['professional_status'] != 'approved':
            audit_logger.log_action(user_id=user['id'], action='login_fail_b2b_not_approved', target_type='user', target_id=user['id'], details=f"B2B status: {user['professional_status']}.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Your professional account is currently {user['professional_status']}. Please wait for approval or contact support."), 403

        identity = user['id'] 
        additional_claims = {
            "role": user['role'], "email": user['email'], "is_verified": user['is_verified'],
            "first_name": user.get('first_name'), "last_name": user.get('last_name'),
            "professional_status": user.get('professional_status')
        }
        access_token = create_access_token(identity=identity, additional_claims=additional_claims)
        refresh_token = create_refresh_token(identity=identity)

        audit_logger.log_action(user_id=user['id'], action='login_success', target_type='user', target_id=user['id'], status='success', ip_address=request.remote_addr)
        
        user_info_to_return = {
            "id": user['id'], "email": user['email'], "prenom": user.get('first_name'), "nom": user.get('last_name'),
            "role": user['role'], "is_admin": user['role'] == 'admin', # Explicitly add is_admin for frontend admin check
            "is_verified": user['is_verified'], "company_name": user.get('company_name'),
            "professional_status": user.get('professional_status')
        }
        return jsonify(success=True, token=access_token, refresh_token=refresh_token, user=user_info_to_return, message="Connexion réussie"), 200
    else:
        audit_logger.log_action(action='login_fail_credentials', email=email, details="Invalid credentials.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid email or password"), 401

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    
    user = query_db("SELECT role, email, is_verified, first_name, last_name, professional_status FROM users WHERE id = ? AND is_active = TRUE", [current_user_id], db_conn=db, one=True)
    if not user:
        audit_logger.log_action(user_id=current_user_id, action='refresh_token_fail_user_not_found_or_inactive', details="User not found or inactive for refresh token.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid refresh token (user not found or inactive)"), 401

    additional_claims = {
        "role": user['role'], "email": user['email'], "is_verified": user['is_verified'],
        "first_name": user.get('first_name'), "last_name": user.get('last_name'),
        "professional_status": user.get('professional_status')
    }
    new_access_token = create_access_token(identity=current_user_id, additional_claims=additional_claims)
    
    audit_logger.log_action(user_id=current_user_id, action='refresh_token_success', target_type='user', target_id=current_user_id, status='success', ip_address=request.remote_addr)
    return jsonify(access_token=new_access_token), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required(optional=True) # Make it optional so client can call it even if token already cleared
def logout():
    current_user_id = get_jwt_identity() # Will be None if token already cleared or invalid
    audit_logger = current_app.audit_log_service
    audit_logger.log_action(user_id=current_user_id, action='logout', target_type='user', target_id=current_user_id, status='success', ip_address=request.remote_addr)
    # JWT blocklisting would happen here if implemented
    return jsonify(message="Logout successful"), 200

@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    token = request.json.get('token')
    audit_logger = current_app.audit_log_service

    if not token:
        audit_logger.log_action(action='verify_email_fail_no_token', details="Verification token missing.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Verification token is missing."), 400

    db = get_db_connection()
    try:
        user_data = query_db("SELECT id, verification_token_expires_at, is_verified FROM users WHERE verification_token = ?", [token], db_conn=db, one=True)

        if not user_data:
            audit_logger.log_action(action='verify_email_fail_invalid_token', details="Invalid verification token.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid or expired verification token."), 400
        
        user = dict(user_data)
        if user['is_verified']:
            audit_logger.log_action(user_id=user['id'], action='verify_email_already_verified', target_type='user', target_id=user['id'], status='info', ip_address=request.remote_addr)
            return jsonify(message="Email already verified."), 200

        expires_at = parse_datetime_from_iso(user['verification_token_expires_at'])
        if expires_at is None or datetime.now(timezone.utc) > expires_at:
            audit_logger.log_action(user_id=user['id'], action='verify_email_fail_expired_token', target_type='user', target_id=user['id'], details="Verification token expired.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Verification token expired."), 400

        query_db("UPDATE users SET is_verified = TRUE, verification_token = NULL, verification_token_expires_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [user['id']], db_conn=db, commit=True)
        
        audit_logger.log_action(user_id=user['id'], action='verify_email_success', target_type='user', target_id=user['id'], status='success', ip_address=request.remote_addr)
        return jsonify(message="Email verified successfully."), 200

    except Exception as e:
        db.rollback() # Ensure rollback on any unexpected error
        current_app.logger.error(f"Error during email verification: {e}", exc_info=True)
        audit_logger.log_action(action='verify_email_fail_server_error', details=f"Server error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email verification failed due to a server error."), 500

@auth_bp.route('/request-password-reset', methods=['POST'])
def request_password_reset():
    email = request.json.get('email')
    audit_logger = current_app.audit_log_service

    if not email:
        audit_logger.log_action(action='request_password_reset_fail_no_email', details="Email required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email is required."), 400

    db = get_db_connection()
    try:
        user = query_db("SELECT id, is_active FROM users WHERE email = ?", [email], db_conn=db, one=True)
        if user and user['is_active']:
            reset_token = secrets.token_urlsafe(32)
            expires_at_iso = format_datetime_for_storage(datetime.now(timezone.utc) + timedelta(hours=1))
            query_db("UPDATE users SET reset_token = ?, reset_token_expires_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [reset_token, expires_at_iso, user['id']], db_conn=db, commit=True)
            
            # reset_link = f"{current_app.config.get('FRONTEND_URL', 'http://localhost:8000')}/reset-password?token={reset_token}"
            # try:
            #     send_email(to_email=email, subject="Password Reset Request - Maison Trüvra", body_html=f"<p>Click to reset password: <a href='{reset_link}'>{reset_link}</a>. Valid for 1 hour.</p>")
            #     audit_logger.log_action(user_id=user['id'], action='password_reset_email_sent', target_type='user', target_id=user['id'], status='success', ip_address=request.remote_addr)
            # except Exception as e_mail:
            #     current_app.logger.error(f"Failed to send password reset email to {email}: {e_mail}")
            #     audit_logger.log_action(user_id=user['id'], action='password_reset_email_fail', target_type='user', target_id=user['id'], details=str(e_mail), status='failure', ip_address=request.remote_addr)
            current_app.logger.info(f"Simulated sending password reset email to {email} with token {reset_token}")
        else:
            audit_logger.log_action(action='request_password_reset_user_not_found_or_inactive', email=email, details="User not found or inactive.", status='info', ip_address=request.remote_addr)
        
        return jsonify(message="If your email is registered and active, you will receive a password reset link."), 200
    except Exception as e:
        current_app.logger.error(f"Error during password reset request for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='request_password_reset_fail_server_error', email=email, details=f"Server error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Password reset request failed due to a server error."), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    token = data.get('token')
    new_password = data.get('new_password')
    audit_logger = current_app.audit_log_service

    if not token or not new_password:
        audit_logger.log_action(action='reset_password_fail_missing_fields', details="Token and new password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Token and new password are required."), 400
    if len(new_password) < 8: # Basic password policy
        audit_logger.log_action(action='reset_password_fail_weak_password', details="Password too short.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Password must be at least 8 characters long."),400


    db = get_db_connection()
    try:
        user_data = query_db("SELECT id, reset_token_expires_at FROM users WHERE reset_token = ?", [token], db_conn=db, one=True)
        if not user_data:
            audit_logger.log_action(action='reset_password_fail_invalid_token', details="Invalid reset token.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid or expired reset token."), 400
        
        user = dict(user_data)
        expires_at = parse_datetime_from_iso(user['reset_token_expires_at'])

        if expires_at is None or datetime.now(timezone.utc) > expires_at:
            query_db("UPDATE users SET reset_token = NULL, reset_token_expires_at = NULL WHERE id = ?", [user['id']], db_conn=db, commit=True)
            audit_logger.log_action(user_id=user['id'], action='reset_password_fail_expired_token', target_type='user', target_id=user['id'], details="Reset token expired.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Password reset token has expired."), 400

        new_password_hash = generate_password_hash(new_password)
        query_db("UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expires_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [new_password_hash, user['id']], db_conn=db, commit=True)

        audit_logger.log_action(user_id=user['id'], action='reset_password_success', target_type='user', target_id=user['id'], status='success', ip_address=request.remote_addr)
        return jsonify(message="Password has been reset successfully."), 200
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error during password reset: {e}", exc_info=True)
        audit_logger.log_action(action='reset_password_fail_server_error', details=f"Server error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Password reset failed due to a server error."), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    current_user_id = get_jwt_identity()
    db = get_db_connection()
    user_data = query_db("SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, vat_number, siret_number, professional_status, created_at, updated_at FROM users WHERE id = ?", [current_user_id], db_conn=db, one=True)
    if user_data:
        user = dict(user_data)
        user['created_at'] = format_datetime_for_display(user['created_at'])
        user['updated_at'] = format_datetime_for_display(user['updated_at'])
        # Add is_admin for convenience if frontend admin logic relies on it directly from /me
        user['is_admin'] = (user['role'] == 'admin') 
        return jsonify(user=user), 200
    return jsonify(message="User not found"), 404
