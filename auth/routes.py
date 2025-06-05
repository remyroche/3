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

def register_professional():
    data = request.get_json()
    audit_logger = current_app.audit_log_service # Get audit logger from app context
    ip_address = request.remote_addr

    required_fields = ['company_name', 'email', 'password', 'first_name', 'last_name', 
                       'phone_number', 'siret_number', 'address_line1', 
                       'city', 'postal_code', 'country']
    
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        audit_logger.log_action(action='register_professional_fail_validation', details=f"Missing fields: {', '.join(missing_fields)}", status='failure', ip_address=ip_address)
        return jsonify(message=f"Missing required fields: {', '.join(missing_fields)}", success=False), 400

    email = sanitize_input(data['email'].lower())
    password = data['password'] # Sanitization of password itself is not typical, but its strength is checked

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        audit_logger.log_action(action='register_professional_fail_validation', details="Invalid email format.", email_attempted=email, status='failure', ip_address=ip_address)
        return jsonify(message="Invalid email format.", success=False), 400
        
    password_validation_error = User.validate_password(password) # Using static method from User model
    if password_validation_error: # This returns an error key, e.g., "auth.error.password_too_short"
        # Frontend should use this key for i18n
        audit_logger.log_action(action='register_professional_fail_validation', details=f"Password validation failed: {password_validation_error}", email_attempted=email, status='failure', ip_address=ip_address)
        return jsonify(message_key=password_validation_error, message=f"Password policy violated: {password_validation_error}", success=False), 400


    if User.query.filter_by(email=email).first():
        audit_logger.log_action(action='register_professional_fail_exists', details="Email already registered.", email_attempted=email, status='failure', ip_address=ip_address)
        return jsonify(message="Email already registered.", success=False), 409

    # --- Handle Referral Code ---
    submitted_referral_code = sanitize_input(data.get('referral_code')) if data.get('referral_code') else None
    valid_referrer_user = None
    if submitted_referral_code:
        # Optional: Validate if the referrer_code actually exists and belongs to an active B2B user
        valid_referrer_user = User.query.filter_by(referral_code=submitted_referral_code, role=UserRoleEnum.B2B_PROFESSIONAL, is_active=True).first()
        if not valid_referrer_user:
            # Decide on policy: reject registration, or register without applying referral benefits, or log warning
            # For now, let's log a warning and proceed with registration without linking the referral if invalid
            current_app.logger.warning(f"Registration attempt with invalid or non-B2B referral code: {submitted_referral_code} by {email}")
            audit_logger.log_action(action='register_professional_invalid_referral', details=f"Invalid referral code '{submitted_referral_code}' provided.", email_attempted=email, status='info', ip_address=ip_address)
            submitted_referral_code = None # Do not store invalid code
    # --- End Handle Referral Code ---

    try:
        new_user = User(
            email=email,
            first_name=sanitize_input(data['first_name']),
            last_name=sanitize_input(data['last_name']),
            company_name=sanitize_input(data['company_name']),
            phone_number=sanitize_input(data['phone_number']), # Assuming User model has phone_number
            siret_number=sanitize_input(data['siret_number']),
            vat_number=sanitize_input(data.get('vat_number')), # VAT is often optional initially
            address_line1=sanitize_input(data['address_line1']),
            address_line2=sanitize_input(data.get('address_line2')),
            city=sanitize_input(data['city']),
            postal_code=sanitize_input(data['postal_code']),
            country=sanitize_input(data['country']),
            role=UserRoleEnum.B2B_PROFESSIONAL,
            professional_status=ProfessionalStatusEnum.PENDING_REVIEW, # Or PENDING_DOCUMENTS if you have that flow
            is_verified=False, # Requires email verification
            # --- Store Referral Code if Valid ---
            referred_by_code=submitted_referral_code if valid_referrer_user else None
            # --- End Store Referral Code ---
        )
        new_user.set_password(password)
        
        # Generate unique referral code for the new user upon registration
        # This logic is also in b2b/routes.py get_loyalty_status, ensure consistency or make it a User model method
        new_user.referral_code = f"TRV-{new_user.id if new_user.id else uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:6].upper()}" 
        # Note: new_user.id might not be available before flush/commit. 
        # It's better to generate this after the first commit or as a User model method triggered on save.
        # For simplicity here, if ID is not set, use a temporary UUID part.
        # The get_loyalty_status route will generate a more robust one if still None.


        db.session.add(new_user)
        db.session.commit() # Commit to get new_user.id

        # If referral was valid, you might trigger awarding credit here or via a separate service/task
        if valid_referrer_user and submitted_referral_code:
            # Example: Award 5 credits to referrer. Make this configurable.
            # This logic should ideally be in a service.
            referral_bonus = float(current_app.config.get('B2B_REFERRAL_BONUS_AMOUNT', 5.0))
            if hasattr(valid_referrer_user, 'referral_credit_balance'):
                 valid_referrer_user.referral_credit_balance = (valid_referrer_user.referral_credit_balance or 0.0) + referral_bonus
                 db.session.add(valid_referrer_user) # Add to session if modified
                 # Potentially also give a starting bonus to the new user
                 # new_user.referral_credit_balance = (new_user.referral_credit_balance or 0.0) + some_new_user_bonus
                 db.session.commit() # Commit changes for referrer (and new user if applicable)
                 audit_logger.log_action(user_id=valid_referrer_user.id, action='referral_credit_awarded', target_type='user', target_id=new_user.id, details=f"Awarded {referral_bonus} credit for referring {new_user.email}.", status='success', ip_address=ip_address)


        # Send verification email
        email_service = EmailService(current_app)
        verification_token = uuid.uuid4().hex # Or a more secure token generation
        new_user.verification_token = verification_token
        new_user.verification_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=current_app.config.get('EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS', 24))
        db.session.commit()

        # Adjust frontend_url based on your actual frontend routing for email verification
        frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:3000')
        verify_url = f"{frontend_url}/verify-email?token={verification_token}"
        
        try:
            email_service.send_transactional_email(
                to_email=new_user.email,
                template_id=current_app.config.get('EMAIL_TEMPLATE_IDS', {}).get('PROFESSIONAL_REGISTRATION_VERIFY'), # Ensure this template ID is configured
                subject="Vérifiez votre adresse e-mail pour votre compte professionnel",
                context={
                    "user_name": new_user.first_name,
                    "verification_link": verify_url,
                    "company_name": current_app.config.get('COMPANY_NAME', 'VotreEntreprise')
                }
            )
        except Exception as e:
            current_app.logger.error(f"Failed to send verification email to {new_user.email}: {e}", exc_info=True)
        
        audit_logger.log_action(user_id=new_user.id, action='register_professional_success', target_type='user', target_id=new_user.id, status='success', ip_address=ip_address)
        return jsonify(message="Professional account registered. Please check your email to verify your account.", success=True, user_id=new_user.id), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during professional registration for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='register_professional_fail_exception', details=str(e), email_attempted=email, status='failure', ip_address=ip_address)
        return jsonify(message="Registration failed due to a server error.", success=False, error=str(e)), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Handles user login.
    Expects JSON payload with 'email', 'password', and optional 'totp_code'.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request. JSON payload expected."}), 400

    email = data.get('email')
    password = data.get('password')
    totp_code = data.get('totp_code') # For Two-Factor Authentication

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    # Replace User.query.filter_by with your actual user retrieval logic
    user = User.query.filter_by(email=email).first()

    if not user:
        # It's generally better not to reveal if the email exists for security reasons
        # but per request for specific error messages:
        current_app.logger.warning(f"Login attempt for non-existent user: {email}")
        return jsonify({"error": "User not found or invalid credentials."}), 401 # Changed from 404

    if not user.check_password(password):
        current_app.logger.warning(f"Invalid password attempt for user: {email}")
        return jsonify({"error": "Invalid password."}), 401

    if user.is_totp_enabled():
        if not totp_code:
            current_app.logger.info(f"TOTP code required for user: {email}")
            return jsonify({"error": "TOTP code is required."}), 401 # 401 or a custom code indicating TOTP needed
        if not user.verify_totp(totp_code):
            current_app.logger.warning(f"Invalid TOTP code for user: {email}")
            return jsonify({"error": "Invalid TOTP code."}), 401
    
    # If all checks pass, log in the user
    # login_user(user) # If using Flask-Login for session-based auth
    
    # For token-based auth, you might generate a token here
    # auth_token = user.generate_auth_token() 
    # response = {'access_token': auth_token.decode('UTF-8')}

    current_app.logger.info(f"User logged in successfully: {email}")
    # Adjust the success response as per your auth mechanism (session/token)
    return jsonify({
        "message": "Login successful.",
        "user": user.to_dict() # Or relevant user info/token
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required # If using Flask-Login
def logout():
    """Handles user logout."""
    # logout_user() # If using Flask-Login
    current_app.logger.info(f"User logged out: {current_user.email if hasattr(current_user, 'email') else 'Unknown'}")
    return jsonify({"message": "Logout successful."}), 200


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

