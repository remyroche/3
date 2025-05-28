import sqlite3
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from datetime import datetime, timedelta, timezone
import secrets # For generating secure tokens
from ..database import get_db_connection, query_db
from ..utils import parse_datetime_from_iso, format_datetime_for_storage # Ensure format_datetime_for_storage if needed, or use isoformat()
# from ..services.email_service import send_email # Uncomment when email service is ready

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    role = data.get('role', 'b2c_customer') # Default to b2c_customer

    # B2B specific fields
    company_name = data.get('company_name')
    vat_number = data.get('vat_number')
    siret_number = data.get('siret_number')

    audit_logger = current_app.audit_log_service

    if not email or not password:
        audit_logger.log_action(action='register_fail', details="Email and password are required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email and password are required"), 400

    if role not in ['b2c_customer', 'b2b_professional']:
        audit_logger.log_action(action='register_fail', email=email, details="Invalid role specified.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid role specified"), 400

    db = get_db_connection()
    try:
        existing_user = query_db("SELECT id FROM users WHERE email = ?", [email], db_conn=db, one=True)
        if existing_user:
            audit_logger.log_action(action='register_fail', email=email, details="Email already registered.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Email already registered"), 409

        password_hash = generate_password_hash(password)
        verification_token = secrets.token_urlsafe(32)
        # Store verification_token_expires_at in ISO format
        verification_token_expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        
        professional_status = None
        if role == 'b2b_professional':
            if not company_name or not siret_number: # VAT might be optional depending on country/rules
                audit_logger.log_action(action='register_fail_b2b', email=email, details="Company name and SIRET number are required for B2B.", status='failure', ip_address=request.remote_addr)
                return jsonify(message="Company name and SIRET number are required for professional accounts."), 400
            professional_status = 'pending' # B2B accounts start as pending validation

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

        # Send verification email
        # verification_link = f"{current_app.config.get('FRONTEND_URL', 'http://localhost:8000')}/verify-email?token={verification_token}"
        # try:
        #     send_email(
        #         to_email=email,
        #         subject="Verify Your Email - Maison Trüvra",
        #         body_html=f"<p>Please verify your email by clicking this link: <a href='{verification_link}'>{verification_link}</a></p>"
        #     )
        #     audit_logger.log_action(user_id=user_id, action='verification_email_sent', target_type='user', target_id=user_id, status='success', ip_address=request.remote_addr)
        # except Exception as e:
        #     current_app.logger.error(f"Failed to send verification email to {email}: {e}")
        #     audit_logger.log_action(user_id=user_id, action='verification_email_fail', target_type='user', target_id=user_id, details=str(e), status='failure', ip_address=request.remote_addr)
        current_app.logger.info(f"Simulated sending verification email to {email} with token {verification_token}")


        audit_logger.log_action(
            user_id=user_id, 
            action='register_success', 
            target_type='user', 
            target_id=user_id,
            details=f"User {email} registered as {role}.",
            status='success',
            ip_address=request.remote_addr
        )
        return jsonify(message="User registered successfully. Please check your email to verify your account.", user_id=user_id), 201

    except sqlite3.IntegrityError: # Should be caught by email check, but as a safeguard
        db.rollback()
        audit_logger.log_action(action='register_fail', email=email, details="Email already registered (integrity error).", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email already registered"), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error during registration for {email}: {e}")
        audit_logger.log_action(action='register_fail', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Registration failed"), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    audit_logger = current_app.audit_log_service

    if not email or not password:
        audit_logger.log_action(action='login_fail', email=email, details="Email and password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email and password are required"), 400

    db = get_db_connection()
    user_data = query_db("SELECT id, email, password_hash, role, is_active, is_verified, first_name, last_name, company_name, professional_status FROM users WHERE email = ?", [email], db_conn=db, one=True)

    if user_data and check_password_hash(user_data['password_hash'], password):
        user = dict(user_data)
        if not user['is_active']:
            audit_logger.log_action(user_id=user['id'], action='login_fail_inactive', target_type='user', target_id=user['id'], details="Account is inactive.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Account is inactive. Please contact support."), 403
        
        # For B2C, verification might be required to login. For B2B, approval might be.
        if user['role'] == 'b2c_customer' and not user['is_verified']:
            # Option: allow login but limited functionality, or block.
            audit_logger.log_action(user_id=user['id'], action='login_fail_unverified', target_type='user', target_id=user['id'], details="B2C account not verified.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Account not verified. Please check your email for verification link."), 403
        
        if user['role'] == 'b2b_professional' and user['professional_status'] != 'approved':
            audit_logger.log_action(user_id=user['id'], action='login_fail_b2b_not_approved', target_type='user', target_id=user['id'], details=f"B2B account status: {user['professional_status']}.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Your professional account is currently {user['professional_status']}. Please wait for approval or contact support."), 403

        # Identity for JWT can be just user ID, or a dict with more info if needed in claims
        identity = user['id'] 
        additional_claims = {
            "role": user['role'], 
            "email": user['email'],
            "is_verified": user['is_verified'], # Include verification status
            "professional_status": user.get('professional_status') # Include B2B status
        }
        access_token = create_access_token(identity=identity, additional_claims=additional_claims)
        refresh_token = create_refresh_token(identity=identity) # Refresh token usually doesn't need extra claims

        audit_logger.log_action(
            user_id=user['id'], 
            action='login_success', 
            target_type='user', 
            target_id=user['id'],
            status='success',
            ip_address=request.remote_addr
        )
        
        user_info_to_return = {
            "id": user['id'],
            "email": user['email'],
            "firstName": user.get('first_name'),
            "lastName": user.get('last_name'),
            "role": user['role'],
            "isVerified": user['is_verified'],
            "companyName": user.get('company_name'),
            "professionalStatus": user.get('professional_status')
        }

        return jsonify(
            access_token=access_token, 
            refresh_token=refresh_token,
            user=user_info_to_return
        ), 200
    else:
        audit_logger.log_action(action='login_fail_credentials', email=email, details="Invalid credentials.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid email or password"), 401

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection() # Needed to fetch user claims if not in refresh token
    
    user = query_db("SELECT role, email, is_verified, professional_status FROM users WHERE id = ?", [current_user_id], db_conn=db, one=True)
    if not user:
        audit_logger.log_action(user_id=current_user_id, action='refresh_token_fail', details="User not found for refresh token.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid refresh token (user not found)"), 401

    additional_claims = {
        "role": user['role'], 
        "email": user['email'],
        "is_verified": user['is_verified'],
        "professional_status": user.get('professional_status')
    }
    new_access_token = create_access_token(identity=current_user_id, additional_claims=additional_claims)
    
    audit_logger.log_action(
        user_id=current_user_id, 
        action='refresh_token_success', 
        target_type='user', 
        target_id=current_user_id,
        status='success',
        ip_address=request.remote_addr
    )
    return jsonify(access_token=new_access_token), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required() # Require a valid access token to logout (optional, could also be unauthenticated)
def logout():
    # For JWT, logout is typically handled client-side by deleting the token.
    # Server-side, you might want to implement token blocklisting if needed.
    # For simplicity, this endpoint acknowledges the logout request.
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    audit_logger.log_action(
        user_id=current_user_id, 
        action='logout', 
        target_type='user', 
        target_id=current_user_id,
        status='success',
        ip_address=request.remote_addr
    )
    return jsonify(message="Logout successful"), 200


@auth_bp.route('/verify-email', methods=['POST']) # Changed to POST to accept token in body
def verify_email():
    token = request.json.get('token')
    audit_logger = current_app.audit_log_service

    if not token:
        audit_logger.log_action(action='verify_email_fail', details="Verification token missing.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Verification token is missing."), 400

    db = get_db_connection()
    try:
        user_data = query_db("SELECT id, verification_token_expires_at, is_verified FROM users WHERE verification_token = ?", [token], db_conn=db, one=True)

        if not user_data:
            audit_logger.log_action(action='verify_email_fail', details="Invalid or expired verification token.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid or expired verification token."), 400
        
        user = dict(user_data)
        if user['is_verified']:
            audit_logger.log_action(user_id=user['id'], action='verify_email_already_verified', target_type='user', target_id=user['id'], status='success', ip_address=request.remote_addr)
            return jsonify(message="Email already verified."), 200 # Or 400 if considered an error

        # Parse expiry date using the utility
        expires_at = parse_datetime_from_iso(user['verification_token_expires_at'])
        if expires_at is None or datetime.now(timezone.utc) > expires_at:
            audit_logger.log_action(user_id=user['id'], action='verify_email_fail_expired', target_type='user', target_id=user['id'], details="Verification token expired.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Verification token expired."), 400

        cursor = db.cursor()
        cursor.execute("UPDATE users SET is_verified = TRUE, verification_token = NULL, verification_token_expires_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [user['id']])
        db.commit()
        
        audit_logger.log_action(user_id=user['id'], action='verify_email_success', target_type='user', target_id=user['id'], status='success', ip_address=request.remote_addr)
        return jsonify(message="Email verified successfully."), 200

    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error during email verification with token {token[:10]}...: {e}")
        audit_logger.log_action(action='verify_email_fail', details=f"Server error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email verification failed due to a server error."), 500


@auth_bp.route('/request-password-reset', methods=['POST'])
def request_password_reset():
    email = request.json.get('email')
    audit_logger = current_app.audit_log_service

    if not email:
        audit_logger.log_action(action='request_password_reset_fail', details="Email required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email is required."), 400

    db = get_db_connection()
    try:
        user = query_db("SELECT id, is_active FROM users WHERE email = ?", [email], db_conn=db, one=True)
        if user and user['is_active']:
            reset_token = secrets.token_urlsafe(32)
            # Store expiry in full ISO format
            expires_at_iso = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

            cursor = db.cursor()
            cursor.execute("UPDATE users SET reset_token = ?, reset_token_expires_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                           [reset_token, expires_at_iso, user['id']])
            db.commit()

            # Send password reset email
            # reset_link = f"{current_app.config.get('FRONTEND_URL', 'http://localhost:8000')}/reset-password?token={reset_token}"
            # try:
            #     send_email(
            #         to_email=email,
            #         subject="Password Reset Request - Maison Trüvra",
            #         body_html=f"<p>Please click this link to reset your password: <a href='{reset_link}'>{reset_link}</a>. This link is valid for 1 hour.</p>"
            #     )
            #     audit_logger.log_action(user_id=user['id'], action='password_reset_email_sent', target_type='user', target_id=user['id'], status='success', ip_address=request.remote_addr)
            # except Exception as e:
            #     current_app.logger.error(f"Failed to send password reset email to {email}: {e}")
            #     # Don't necessarily rollback the token generation if email fails, user can try again.
            #     audit_logger.log_action(user_id=user['id'], action='password_reset_email_fail', target_type='user', target_id=user['id'], details=str(e), status='failure', ip_address=request.remote_addr)
            current_app.logger.info(f"Simulated sending password reset email to {email} with token {reset_token}")
        else:
            # User not found or inactive, still log attempt but don't reveal existence
            audit_logger.log_action(action='request_password_reset_nonexistent_or_inactive', email=email, details="User not found or inactive.", status='info', ip_address=request.remote_addr)

        # Always return a generic success message to prevent email enumeration
        return jsonify(message="If your email is registered, you will receive a password reset link."), 200

    except Exception as e:
        # db.rollback() # Not strictly needed if select query fails, but good if any writes were planned before error
        current_app.logger.error(f"Error during password reset request for {email}: {e}")
        audit_logger.log_action(action='request_password_reset_fail', email=email, details=f"Server error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Password reset request failed due to a server error."), 500


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    token = data.get('token')
    new_password = data.get('new_password')
    audit_logger = current_app.audit_log_service

    if not token or not new_password:
        audit_logger.log_action(action='reset_password_fail', details="Token and new password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Token and new password are required."), 400

    db = get_db_connection()
    try:
        user_data = query_db("SELECT id, reset_token_expires_at FROM users WHERE reset_token = ?", [token], db_conn=db, one=True)
        if not user_data:
            audit_logger.log_action(action='reset_password_fail_invalid_token', details="Invalid or expired reset token.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid or expired reset token."), 400
        
        user = dict(user_data)
        
        # Parse expiry date using the utility
        expires_at = parse_datetime_from_iso(user['reset_token_expires_at'])

        if expires_at is None or datetime.now(timezone.utc) > expires_at:
            # Invalidate token even if expired, to prevent reuse
            cursor_invalidate = db.cursor()
            cursor_invalidate.execute("UPDATE users SET reset_token = NULL, reset_token_expires_at = NULL WHERE id = ?", [user['id']])
            db.commit() # Commit invalidation separately
            audit_logger.log_action(user_id=user['id'], action='reset_password_fail_expired_token', target_type='user', target_id=user['id'], details="Reset token expired.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Password reset token has expired."), 400

        new_password_hash = generate_password_hash(new_password)
        cursor = db.cursor()
        cursor.execute("UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expires_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                       [new_password_hash, user['id']])
        db.commit()

        audit_logger.log_action(user_id=user['id'], action='reset_password_success', target_type='user', target_id=user['id'], status='success', ip_address=request.remote_addr)
        return jsonify(message="Password has been reset successfully."), 200

    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error during password reset with token {token[:10]}...: {e}")
        audit_logger.log_action(action='reset_password_fail', details=f"Server error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Password reset failed due to a server error."), 500

# Example protected route
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
        return jsonify(user=user), 200
    return jsonify(message="User not found"), 404

