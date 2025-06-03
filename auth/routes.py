# backend/auth/routes.py
from flask import Blueprint, request, jsonify, current_app, url_for
from werkzeug.security import check_password_hash 
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jwt, get_jti # Import get_jti for blocklisting
)
from datetime import datetime, timedelta, timezone
import secrets
import re # Keep for B2B field validation if not moved to model

# Import db instance and models
from .. import db, jwt # Import jwt for blocklist loader
from ..models import User, TokenBlocklist # Import UserRoleEnum if using it directly here, or rely on model's default
from ..models import UserRoleEnum, ProfessionalStatusEnum # Import Enums for direct use if needed
from ..utils import (
    parse_datetime_from_iso,
    format_datetime_for_storage,
    is_valid_email,
    send_email_alert # Assuming this is your email sending utility
)
# from ..services.email_service import send_email # Or your actual email service

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    role_str = data.get('role', 'b2c_customer') # Get role as string from request

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

    # Use User model's password validation
    password_error_key = User.validate_password(password)
    if password_error_key:
        # Assuming your frontend t() function can handle these keys
        audit_logger.log_action(action='register_fail_weak_password', email=email, details=f"Password complexity issue: {password_error_key}", status='failure', ip_address=request.remote_addr)
        return jsonify(message=password_error_key, success=False), 400 # Send key for frontend translation

    try:
        role = UserRoleEnum(role_str) # Convert string to Enum member
    except ValueError:
        audit_logger.log_action(action='register_fail', email=email, details="Invalid role specified.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid role specified", success=False), 400

    try:
        if User.query.filter_by(email=email).first():
            audit_logger.log_action(action='register_fail', email=email, details="Email already registered.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Email already registered", success=False), 409

        verification_token = secrets.token_urlsafe(32)
        verification_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=current_app.config.get('VERIFICATION_TOKEN_LIFESPAN_HOURS', 24))
        
        professional_status_enum = None
        if role == UserRoleEnum.B2B_PROFESSIONAL:
            if not company_name or not siret_number: 
                audit_logger.log_action(action='register_fail_b2b', email=email, details="Company name and SIRET are required for B2B.", status='failure', ip_address=request.remote_addr)
                return jsonify(message="Company name and SIRET number are required for professional accounts.", success=False), 400
            professional_status_enum = ProfessionalStatusEnum.PENDING

        new_user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role, # Store Enum member
            verification_token=verification_token,
            verification_token_expires_at=verification_token_expires_at,
            company_name=company_name,
            vat_number=vat_number,
            siret_number=siret_number,
            professional_status=professional_status_enum, # Store Enum member
            is_active=True, 
            is_verified=False
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()

        # Email sending logic (using a configurable frontend URL)
        frontend_base_url = current_app.config.get('APP_BASE_URL_FRONTEND', current_app.config.get('APP_BASE_URL', 'http://localhost:8000'))
        # Assuming your frontend has a route like /verify-email?token=...
        verification_link = f"{frontend_base_url}/verify-email?token={verification_token}"
        
        current_app.logger.info(f"SIMULATED: Verification email to {email} with link: {verification_link}")
        # send_email_alert(
        #     subject="Verify Your Email - Maison Trüvra",
        #     body=f"Please verify your email by clicking this link: {verification_link}",
        #     recipient_email=email
        # )
        audit_logger.log_action(user_id=new_user.id, action='verification_email_sent_simulated', target_type='user', target_id=new_user.id, status='success', ip_address=request.remote_addr)

        audit_logger.log_action(user_id=new_user.id, action='register_success', target_type='user', target_id=new_user.id, details=f"User {email} registered as {role.value}.", status='success', ip_address=request.remote_addr)
        return jsonify(message="User registered successfully. Please check your email to verify your account.", user_id=new_user.id, success=True), 201

    except Exception as e: 
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
        # ... (logging and return 400)
        audit_logger.log_action(action='login_fail_missing_fields', email=email, details="Email and password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email and password are required", success=False), 400


    user = User.query.filter_by(email=email).first()

    if user and user.check_password(password):
        if not user.is_active:
            # ... (logging and return 403)
            audit_logger.log_action(user_id=user.id, action='login_fail_inactive', target_type='user', target_id=user.id, details="Account is inactive.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Account is inactive. Please contact support.", success=False), 403
        
        if user.role == UserRoleEnum.B2C_CUSTOMER and not user.is_verified:
            # ... (logging and return 403)
            audit_logger.log_action(user_id=user.id, action='login_fail_unverified', target_type='user', target_id=user.id, details="B2C account not verified.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Account not verified. Please check your email for verification link.", success=False), 403
        
        if user.role == UserRoleEnum.B2B_PROFESSIONAL and user.professional_status != ProfessionalStatusEnum.APPROVED:
            # ... (logging and return 403)
            audit_logger.log_action(user_id=user.id, action='login_fail_b2b_not_approved', target_type='user', target_id=user.id, details=f"B2B status: {user.professional_status.value if user.professional_status else 'N/A'}.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Your professional account is currently {user.professional_status.value if user.professional_status else 'under review'}. Please wait for approval or contact support.", success=False), 403


        identity = user.id
        additional_claims = {
            "role": user.role.value, 
            "email": user.email, 
            "is_verified": user.is_verified,
            "first_name": user.first_name, 
            "last_name": user.last_name,
            "professional_status": user.professional_status.value if user.professional_status else None
        }
        access_token = create_access_token(identity=identity, additional_claims=additional_claims)
        refresh_token = create_refresh_token(identity=identity)

        audit_logger.log_action(user_id=user.id, action='login_success', target_type='user', target_id=user.id, status='success', ip_address=request.remote_addr)
        
        user_info_to_return = user.to_dict() # Use the model's to_dict method
        return jsonify(success=True, token=access_token, refresh_token=refresh_token, user=user_info_to_return, message="Connexion réussie"), 200
    else:
        # ... (logging and return 401)
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
        # ... (logging and return 401)
        audit_logger.log_action(user_id=current_user_id, action='refresh_token_fail_user_not_found_or_inactive', details="User not found or inactive for refresh token.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid refresh token (user not found or inactive)", success=False), 401


    additional_claims = {
        "role": user.role.value, 
        "email": user.email, 
        "is_verified": user.is_verified,
        "first_name": user.first_name, 
        "last_name": user.last_name,
        "professional_status": user.professional_status.value if user.professional_status else None
    }
    new_access_token = create_access_token(identity=current_user_id, additional_claims=additional_claims)
    
    audit_logger.log_action(user_id=current_user_id, action='refresh_token_success', target_type='user', target_id=current_user_id, status='success', ip_address=request.remote_addr)
    return jsonify(access_token=new_access_token, success=True), 200

# Blocklist loader for JWT
@jwt.token_in_blocklist_loader
def check_if_token_in_blocklist(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    token = TokenBlocklist.query.filter_by(jti=jti).first()
    return token is not None

@auth_bp.route('/logout', methods=['POST'])
@jwt_required() # Now requires a valid token to logout (for blocklisting)
def logout():
    current_user_id = get_jwt_identity()
    jti = get_jwt()["jti"] # Get the JTI of the current access token
    now = datetime.now(timezone.utc)
    
    # Get the 'exp' claim from the token to set blocklist expiry
    # Flask-JWT-Extended stores 'exp' as a Unix timestamp
    token_exp_timestamp = get_jwt().get("exp")
    if token_exp_timestamp:
        token_expires = datetime.fromtimestamp(token_exp_timestamp, tz=timezone.utc)
    else:
        # Fallback if 'exp' is not found, though it should be.
        # Set a reasonable default block duration, e.g., config.JWT_ACCESS_TOKEN_EXPIRES
        token_expires = now + current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', timedelta(hours=1))

    try:
        db.session.add(TokenBlocklist(jti=jti, created_at=now, expires_at=token_expires))
        db.session.commit()
        audit_logger = current_app.audit_log_service
        audit_logger.log_action(user_id=current_user_id, action='logout_success_blocklisted', target_type='user', target_id=current_user_id, details=f"Token JTI {jti} blocklisted.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Logout successful. Token has been invalidated.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error blocklisting token for user {current_user_id}: {e}", exc_info=True)
        # Still log out client-side, but log server error
        return jsonify(message="Logout processed, but server error during token invalidation.", success=False), 500


@auth_bp.route('/verify-email', methods=['POST']) 
def verify_email_route_post():
    token = request.json.get('token')
    audit_logger = current_app.audit_log_service

    if not token:
        # ... (logging and return 400)
        audit_logger.log_action(action='verify_email_fail_no_token', details="Verification token missing.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Verification token is missing.", success=False), 400

    try:
        user = User.query.filter_by(verification_token=token).first()

        if not user:
            # ... (logging and return 400)
            audit_logger.log_action(action='verify_email_fail_invalid_token', details="Invalid verification token.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid or expired verification token.", success=False), 400
        
        if user.is_verified:
            # ... (logging and return 200)
            audit_logger.log_action(user_id=user.id, action='verify_email_already_verified', target_type='user', target_id=user.id, status='info', ip_address=request.remote_addr)
            return jsonify(message="Email already verified.", success=True), 200

        expires_at = user.verification_token_expires_at
        
        if expires_at is None or datetime.now(timezone.utc) > expires_at:
            user.verification_token = None
            user.verification_token_expires_at = None
            db.session.commit()
            # ... (logging and return 400)
            audit_logger.log_action(user_id=user.id, action='verify_email_fail_expired_token', target_type='user', target_id=user.id, details="Verification token expired.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Verification token expired.", success=False), 400


        user.is_verified = True
        user.verification_token = None
        user.verification_token_expires_at = None # Clear the field
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
        # ... (logging and return 400)
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
            
            frontend_base_url = current_app.config.get('APP_BASE_URL_FRONTEND', current_app.config.get('APP_BASE_URL', 'http://localhost:8000'))
            # Assuming frontend route like /reset-password?token=...
            reset_link = f"{frontend_base_url}/reset-password?token={reset_token}" 
            
            current_app.logger.info(f"SIMULATED: Password reset email to {email} with link: {reset_link}")
            # send_email_alert(
            #     subject="Password Reset Request - Maison Trüvra",
            #     body=f"Click to reset password: {reset_link}. Valid for {current_app.config.get('RESET_TOKEN_LIFESPAN_HOURS', 1)} hour(s).",
            #     recipient_email=email
            # )
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
        # ... (logging and return 400)
        audit_logger.log_action(action='reset_password_fail_missing_fields', details="Token and new password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Token and new password are required.", success=False), 400
    
    password_error_key = User.validate_password(new_password)
    if password_error_key:
        audit_logger.log_action(action='reset_password_fail_weak_password', details=f"Password complexity issue: {password_error_key}", status='failure', ip_address=request.remote_addr)
        return jsonify(message=password_error_key, success=False), 400


    try:
        user = User.query.filter_by(reset_token=token).first()
        if not user:
            # ... (logging and return 400)
            audit_logger.log_action(action='reset_password_fail_invalid_token', details="Invalid reset token.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid or expired reset token.", success=False), 400
        
        expires_at = user.reset_token_expires_at
        if expires_at is None or datetime.now(timezone.utc) > expires_at:
            user.reset_token = None
            user.reset_token_expires_at = None
            db.session.commit()
            # ... (logging and return 400)
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
        user_data = user.to_dict() # Use the model's to_dict method
        return jsonify(user=user_data, success=True), 200
    return jsonify(message="User not found", success=False), 404


@auth_bp.route('/request-magic-link', methods=['POST'])
def request_magic_link():
    data = request.json
    email = data.get('email')
    audit_logger = current_app.audit_log_service

    if not email:
        return jsonify(message="Email is required.", success=False), 400

    # Only active B2B professionals can use magic links
    user = User.query.filter_by(email=email, role=UserRoleEnum.B2B_PROFESSIONAL, is_active=True).first()

    if user:
        # Use new dedicated fields for magic link
        token_value = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=current_app.config.get('MAGIC_LINK_LIFESPAN_MINUTES', 10))
        
        user.magic_link_token = token_value
        user.magic_link_expires_at = expires_at
        db.session.commit()
        
        frontend_base_url = current_app.config.get('APP_BASE_URL_FRONTEND', current_app.config.get('APP_BASE_URL', 'http://localhost:8000'))
        # Frontend URL for professionals page that will handle the token
        magic_link_url = f"{frontend_base_url}/professionnels.html?magic_token={token_value}"
        
        current_app.logger.info(f"SIMULATED: Magic link email to {email} with link: {magic_link_url}")
        # send_email_alert(
        #     subject="Votre lien de connexion Maison Trüvra (Professionnel)",
        #     body=f"Cliquez ici pour vous connecter à votre espace professionnel : {magic_link_url}. Ce lien est valide pour {current_app.config.get('MAGIC_LINK_LIFESPAN_MINUTES', 10)} minutes.",
        #     recipient_email=email
        # )
        audit_logger.log_action(user_id=user.id, action='magic_link_request_sent_simulated', status='success', ip_address=request.remote_addr)
    else:
        audit_logger.log_action(action='magic_link_request_user_not_found_or_inactive_b2b', email=email, status='info', ip_address=request.remote_addr)
        
    return jsonify(message="If an active professional account with that email exists, a magic link has been sent.", success=True), 200


@auth_bp.route('/verify-magic-link', methods=['POST'])
def verify_magic_link():
    data = request.json
    token = data.get('token')
    audit_logger = current_app.audit_log_service

    if not token:
        return jsonify(message="Magic token is missing.", success=False), 400

    # Query using the new dedicated magic link token field
    user = User.query.filter_by(magic_link_token=token).first()

    if not user:
        audit_logger.log_action(action='magic_link_fail_invalid_token', status='failure', ip_address=request.remote_addr)
        return jsonify(message="Magic link is invalid or has already been used.", success=False), 400
    
    # Check role again, just in case a non-B2B user somehow got a magic link token
    if user.role != UserRoleEnum.B2B_PROFESSIONAL or not user.is_active:
        audit_logger.log_action(user_id=user.id, action='magic_link_fail_wrong_role_or_inactive', status='failure', ip_address=request.remote_addr)
        return jsonify(message="This magic link is not valid for your account type or your account is inactive.", success=False), 403

    expires_at = user.magic_link_expires_at
    
    if expires_at is None or datetime.now(timezone.utc) > expires_at:
        user.magic_link_token = None # Clear expired token
        user.magic_link_expires_at = None
        db.session.commit()
        audit_logger.log_action(user_id=user.id, action='magic_link_fail_expired', status='failure', ip_address=request.remote_addr)
        return jsonify(message="Magic link has expired.", success=False), 400

    # Invalidate token after successful use
    user.magic_link_token = None 
    user.magic_link_expires_at = None
    # Optionally, update last login time for the user here
    # user.last_login_at = datetime.now(timezone.utc) 
    db.session.commit()
    
    identity = user.id
    additional_claims = {
        "role": user.role.value, 
        "email": user.email, 
        "is_verified": user.is_verified, # B2B accounts might have a separate verification flow
        "first_name": user.first_name, 
        "last_name": user.last_name,
        "professional_status": user.professional_status.value if user.professional_status else None,
        "company_name": user.company_name
    }
    access_token = create_access_token(identity=identity, additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=identity)

    audit_logger.log_action(user_id=user.id, action='login_success_magic_link', status='success', ip_address=request.remote_addr)

    user_info_to_return = user.to_dict()
    return jsonify(success=True, token=access_token, refresh_token=refresh_token, user=user_info_to_return, message="Connexion via lien magique réussie"), 200

