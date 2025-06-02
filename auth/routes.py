# backend/auth/routes.py
from flask import Blueprint, request, jsonify, current_app, url_for
from werkzeug.security import check_password_hash # generate_password_hash is in User model
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jwt
)
from datetime import datetime, timedelta, timezone
import secrets

# Import db instance and models
from .. import db
from ..models import User
from ..utils import (
    parse_datetime_from_iso,
    format_datetime_for_storage,
    is_valid_email
)
# from ..services.email_service import send_email # Placeholder

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/api/auth') # Corrected prefix


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
        return jsonify(message="Email and password are required", success=False), 400
    if not is_valid_email(email):
        audit_logger.log_action(action='register_fail', email=email, details="Invalid email format.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid email format", success=False), 400

    # --- UPDATED PASSWORD VALIDATION ---
    if len(password) < 8:
        audit_logger.log_action(action='register_fail_weak_password', email=email, details="Password too short.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Password must be at least 8 characters long.", success=False), 400
    if not re.search(r"[A-Z]", password):
        audit_logger.log_action(action='register_fail_weak_password', email=email, details="Password missing uppercase letter.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Password must contain at least one uppercase letter.", success=False), 400
    if not re.search(r"[a-z]", password):
        audit_logger.log_action(action='register_fail_weak_password', email=email, details="Password missing lowercase letter.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Password must contain at least one lowercase letter.", success=False), 400
    if not re.search(r"[0-9]", password):
        audit_logger.log_action(action='register_fail_weak_password', email=email, details="Password missing a digit.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Password must contain at least one digit.", success=False), 400
    # --- END OF UPDATED PASSWORD VALIDATION ---

    if role not in ['b2c_customer', 'b2b_professional']:
        audit_logger.log_action(action='register_fail', email=email, details="Invalid role specified.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid role specified", success=False), 400

    try:
        if User.query.filter_by(email=email).first():
            audit_logger.log_action(action='register_fail', email=email, details="Email already registered.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Email already registered", success=False), 409

        verification_token = secrets.token_urlsafe(32)
        verification_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=current_app.config.get('VERIFICATION_TOKEN_LIFESPAN_HOURS', 24))
        
        professional_status = None
        if role == 'b2b_professional':
            if not company_name or not siret_number: # Assuming SIRET is a key identifier for B2B
                audit_logger.log_action(action='register_fail_b2b', email=email, details="Company name and SIRET are required for B2B.", status='failure', ip_address=request.remote_addr)
                return jsonify(message="Company name and SIRET number are required for professional accounts.", success=False), 400
            professional_status = 'pending' # B2B accounts start as pending approval

        new_user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            verification_token=verification_token,
            verification_token_expires_at=verification_token_expires_at,
            company_name=company_name,
            vat_number=vat_number,
            siret_number=siret_number,
            professional_status=professional_status,
            is_active=True, # New users are active by default, verification handles access to certain features
            is_verified=False # Email not verified yet
        )
        new_user.set_password(password) # Use the method from the User model
        
        db.session.add(new_user)
        db.session.commit()

        # Placeholder for sending verification email
        # verification_link = url_for('auth_bp.verify_email_route_get', token=verification_token, _external=True) 
        # current_app.logger.info(f"SIMULATED: Verification email to {email} with link: {verification_link}")
        # send_email(to_email=email, subject="Verify Your Email - Maison Trüvra", body_html=f"<p>Please verify your email: <a href='{verification_link}'>{verification_link}</a></p>")
        audit_logger.log_action(user_id=new_user.id, action='verification_email_sent_simulated', target_type='user', target_id=new_user.id, status='success', ip_address=request.remote_addr)

        audit_logger.log_action(user_id=new_user.id, action='register_success', target_type='user', target_id=new_user.id, details=f"User {email} registered as {role}.", status='success', ip_address=request.remote_addr)
        return jsonify(message="User registered successfully. Please check your email to verify your account.", user_id=new_user.id, success=True), 201

    except Exception as e: # Catch broader exceptions
        db.session.rollback()
        current_app.logger.error(f"Error during registration for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='register_fail_server_error', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Registration failed due to a server error", success=False), 500
        

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    audit_logger = current_app.audit_log_service

    if not email or not password:
        audit_logger.log_action(action='login_fail_missing_fields', email=email, details="Email and password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email and password are required", success=False), 400

    user = User.query.filter_by(email=email).first()

    if user and user.check_password(password):
        if not user.is_active:
            audit_logger.log_action(user_id=user.id, action='login_fail_inactive', target_type='user', target_id=user.id, details="Account is inactive.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Account is inactive. Please contact support.", success=False), 403
        
        if user.role == 'b2c_customer' and not user.is_verified:
            audit_logger.log_action(user_id=user.id, action='login_fail_unverified', target_type='user', target_id=user.id, details="B2C account not verified.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Account not verified. Please check your email for verification link.", success=False), 403
        
        if user.role == 'b2b_professional' and user.professional_status != 'approved':
            audit_logger.log_action(user_id=user.id, action='login_fail_b2b_not_approved', target_type='user', target_id=user.id, details=f"B2B status: {user.professional_status}.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Your professional account is currently {user.professional_status}. Please wait for approval or contact support.", success=False), 403

        identity = user.id
        additional_claims = {
            "role": user.role, "email": user.email, "is_verified": user.is_verified,
            "first_name": user.first_name, "last_name": user.last_name,
            "professional_status": user.professional_status
        }
        access_token = create_access_token(identity=identity, additional_claims=additional_claims)
        refresh_token = create_refresh_token(identity=identity)

        audit_logger.log_action(user_id=user.id, action='login_success', target_type='user', target_id=user.id, status='success', ip_address=request.remote_addr)
        
        user_info_to_return = {
            "id": user.id, "email": user.email, "prenom": user.first_name, "nom": user.last_name,
            "role": user.role, "is_admin": user.role == 'admin',
            "is_verified": user.is_verified, "company_name": user.company_name,
            "professional_status": user.professional_status
        }
        return jsonify(success=True, token=access_token, refresh_token=refresh_token, user=user_info_to_return, message="Connexion réussie"), 200
    else:
        user_id_attempt = user.id if user else None
        audit_logger.log_action(user_id=user_id_attempt, action='login_fail_credentials', email=email, details="Invalid credentials.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid email or password", success=False), 401

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    
    user = User.query.filter_by(id=current_user_id, is_active=True).first()
    if not user:
        audit_logger.log_action(user_id=current_user_id, action='refresh_token_fail_user_not_found_or_inactive', details="User not found or inactive for refresh token.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid refresh token (user not found or inactive)", success=False), 401

    additional_claims = {
        "role": user.role, "email": user.email, "is_verified": user.is_verified,
        "first_name": user.first_name, "last_name": user.last_name,
        "professional_status": user.professional_status
    }
    new_access_token = create_access_token(identity=current_user_id, additional_claims=additional_claims)
    
    audit_logger.log_action(user_id=current_user_id, action='refresh_token_success', target_type='user', target_id=current_user_id, status='success', ip_address=request.remote_addr)
    return jsonify(access_token=new_access_token, success=True), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required(optional=True)
def logout():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    audit_logger.log_action(user_id=current_user_id, action='logout', target_type='user', target_id=current_user_id, status='success', ip_address=request.remote_addr)
    return jsonify(message="Logout successful", success=True), 200

@auth_bp.route('/verify-email', methods=['POST']) # Changed from GET to POST to accept token in body
def verify_email_route_post():
    token = request.json.get('token')
    audit_logger = current_app.audit_log_service

    if not token:
        audit_logger.log_action(action='verify_email_fail_no_token', details="Verification token missing.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Verification token is missing.", success=False), 400

    try:
        user = User.query.filter_by(verification_token=token).first()

        if not user:
            audit_logger.log_action(action='verify_email_fail_invalid_token', details="Invalid verification token.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid or expired verification token.", success=False), 400
        
        if user.is_verified:
            audit_logger.log_action(user_id=user.id, action='verify_email_already_verified', target_type='user', target_id=user.id, status='info', ip_address=request.remote_addr)
            return jsonify(message="Email already verified.", success=True), 200

        expires_at = user.verification_token_expires_at
        
        if expires_at is None or datetime.now(timezone.utc) > expires_at:
            user.verification_token = None
            user.verification_token_expires_at = None
            db.session.commit()
            audit_logger.log_action(user_id=user.id, action='verify_email_fail_expired_token', target_type='user', target_id=user.id, details="Verification token expired.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Verification token expired.", success=False), 400

        user.is_verified = True
        user.verification_token = None
        user.verification_token_expires_at = None
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        audit_logger.log_action(user_id=user.id, action='verify_email_success', target_type='user', target_id=user.id, status='success', ip_address=request.remote_addr)
        return jsonify(message="Email verified successfully.", success=True), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during email verification: {e}", exc_info=True)
        audit_logger.log_action(action='verify_email_fail_server_error', details=f"Server error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email verification failed due to a server error.", success=False), 500

@auth_bp.route('/request-password-reset', methods=['POST'])
def request_password_reset():
    email = request.json.get('email')
    audit_logger = current_app.audit_log_service

    if not email:
        audit_logger.log_action(action='request_password_reset_fail_no_email', details="Email required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email is required.", success=False), 400

    try:
        user = User.query.filter_by(email=email, is_active=True).first()
        if user:
            reset_token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=current_app.config.get('RESET_TOKEN_LIFESPAN_HOURS', 1))
            
            user.reset_token = reset_token
            user.reset_token_expires_at = expires_at
            user.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            
            # reset_link = url_for('auth_bp.reset_password_page', token=reset_token, _external=True) # Assuming a frontend page
            # current_app.logger.info(f"SIMULATED: Password reset email to {email} with link: {reset_link}")
            # send_email(to_email=email, subject="Password Reset Request - Maison Trüvra", body_html=f"<p>Click to reset password: <a href='{reset_link}'>{reset_link}</a>. Valid for 1 hour.</p>")
            audit_logger.log_action(user_id=user.id, action='password_reset_email_sent_simulated', target_type='user', target_id=user.id, status='success', ip_address=request.remote_addr)
        else:
            audit_logger.log_action(action='request_password_reset_user_not_found_or_inactive', email=email, details="User not found or inactive.", status='info', ip_address=request.remote_addr)
        
        return jsonify(message="If your email is registered and active, you will receive a password reset link.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during password reset request for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='request_password_reset_fail_server_error', email=email, details=f"Server error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Password reset request failed due to a server error.", success=False), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    token = data.get('token')
    new_password = data.get('new_password')
    audit_logger = current_app.audit_log_service

    if not token or not new_password:
        audit_logger.log_action(action='reset_password_fail_missing_fields', details="Token and new password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Token and new password are required.", success=False), 400
    
    if len(new_password) < 8:
        audit_logger.log_action(action='reset_password_fail_weak_password', details="Password too short.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Password must be at least 8 characters long.", success=False), 400

    try:
        user = User.query.filter_by(reset_token=token).first()
        if not user:
            audit_logger.log_action(action='reset_password_fail_invalid_token', details="Invalid reset token.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid or expired reset token.", success=False), 400
        
        expires_at = user.reset_token_expires_at
        if expires_at is None or datetime.now(timezone.utc) > expires_at:
            user.reset_token = None
            user.reset_token_expires_at = None
            db.session.commit()
            audit_logger.log_action(user_id=user.id, action='reset_password_fail_expired_token', target_type='user', target_id=user.id, details="Reset token expired.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Password reset token has expired.", success=False), 400

        user.set_password(new_password)
        user.reset_token = None
        user.reset_token_expires_at = None
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        audit_logger.log_action(user_id=user.id, action='reset_password_success', target_type='user', target_id=user.id, status='success', ip_address=request.remote_addr)
        return jsonify(message="Password has been reset successfully.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during password reset: {e}", exc_info=True)
        audit_logger.log_action(action='reset_password_fail_server_error', details=f"Server error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Password reset failed due to a server error.", success=False), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user:
        user_data = {
            "id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name,
            "role": user.role, "is_active": user.is_active, "is_verified": user.is_verified,
            "company_name": user.company_name, "vat_number": user.vat_number,
            "siret_number": user.siret_number, "professional_status": user.professional_status,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            "is_admin": (user.role == 'admin')
        }
        return jsonify(user=user_data, success=True), 200
    return jsonify(message="User not found", success=False), 404

@auth_bp.route('/request-magic-link', methods=['POST'])
def request_magic_link():
    data = request.json
    email = data.get('email')
    audit_logger = current_app.audit_log_service

    if not email:
        return jsonify(message="Email is required.", success=False), 400

    user = User.query.filter_by(email=email, role='b2b_professional', is_active=True).first()

    if user:
        magic_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=current_app.config.get('MAGIC_LINK_LIFESPAN_MINUTES', 10))
        
        user.reset_token = magic_token # Re-using reset_token field for magic link
        user.reset_token_expires_at = expires_at
        db.session.commit()
        
        # magic_link_url = f"{current_app.config.get('APP_BASE_URL')}/professionnels.html?magic_token={magic_token}"
        # current_app.logger.info(f"SIMULATED: Magic link email to {email} with link: {magic_link_url}")
        # send_email(to_email=email, subject="Votre lien de connexion Maison Trüvra", body_html=f"<p>Cliquez ici pour vous connecter : <a href='{magic_link_url}'>{magic_link_url}</a>. Valide 10 minutes.</p>")
        audit_logger.log_action(user_id=user.id, action='magic_link_request_sent_simulated', status='success', ip_address=request.remote_addr)
    else:
        audit_logger.log_action(action='magic_link_request_user_not_found_or_inactive', email=email, status='info', ip_address=request.remote_addr)
        
    return jsonify(message="If an active professional account with that email exists, a magic link has been sent.", success=True), 200

@auth_bp.route('/verify-magic-link', methods=['POST'])
def verify_magic_link():
    data = request.json
    token = data.get('token')
    audit_logger = current_app.audit_log_service

    if not token:
        return jsonify(message="Magic token is missing.", success=False), 400

    user = User.query.filter_by(reset_token=token).first() # Using reset_token field

    if not user:
        audit_logger.log_action(action='magic_link_fail_invalid_token', status='failure', ip_address=request.remote_addr)
        return jsonify(message="Magic link is invalid or has already been used.", success=False), 400
    
    expires_at = user.reset_token_expires_at
    
    if expires_at is None or datetime.now(timezone.utc) > expires_at:
        user.reset_token = None
        user.reset_token_expires_at = None
        db.session.commit()
        audit_logger.log_action(user_id=user.id, action='magic_link_fail_expired', status='failure', ip_address=request.remote_addr)
        return jsonify(message="Magic link has expired.", success=False), 400

    user.reset_token = None # Invalidate token after use
    user.reset_token_expires_at = None
    db.session.commit()
    
    identity = user.id
    additional_claims = {
        "role": user.role, "email": user.email, "is_verified": user.is_verified,
        "first_name": user.first_name, "last_name": user.last_name,
        "professional_status": user.professional_status
    }
    access_token = create_access_token(identity=identity, additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=identity)

    audit_logger.log_action(user_id=user.id, action='login_success_magic_link', status='success', ip_address=request.remote_addr)

    user_info_to_return = {
        "id": user.id, "email": user.email, "prenom": user.first_name, "nom": user.last_name,
        "role": user.role, "is_admin": user.role == 'admin',
        "is_verified": user.is_verified, "company_name": user.company_name,
        "professional_status": user.professional_status
    }
    return jsonify(success=True, token=access_token, refresh_token=refresh_token, user=user_info_to_return, message="Connexion réussie"), 200
