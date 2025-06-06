# backend/admin_api/auth_routes.py
# Admin Authentication, Profile, and Security Management

import requests
import secrets
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta

from flask import request, jsonify, current_app, redirect, session
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity, get_jwt, 
    unset_jwt_cookies, set_access_cookies
)
from sqlalchemy import func
import pyotp

from . import admin_api_bp
from .. import db, limiter
from ..models import User, TokenBlocklist, UserRoleEnum
from ..utils import admin_required

# --- Helper Function ---
def _create_admin_session_and_get_response(admin_user, redirect_url=None):
    """Helper to create JWT and user info for successful admin login."""
    identity = admin_user.id
    additional_claims = {
        "role": admin_user.role.value, "email": admin_user.email, "is_admin": True,
        "first_name": admin_user.first_name, "last_name": admin_user.last_name
    }
    access_token = create_access_token(identity=identity, additional_claims=additional_claims)
    
    if redirect_url: 
        response = redirect(redirect_url)
        # set_access_cookies is a Flask-JWT-Extended function to set JWT in cookies
        if 'cookies' in current_app.config.get('JWT_TOKEN_LOCATION', ['headers']):
            set_access_cookies(response, access_token)
        current_app.logger.info(f"SSO successful for {admin_user.email}, redirecting...")
        return response
    else: 
        user_info_to_return = admin_user.to_dict()
        return jsonify(success=True, message="Admin login successful!", token=access_token, user=user_info_to_return), 200

# --- Login, Logout, and SSO Routes ---
@admin_api_bp.route('/logout', methods=['POST'])
@jwt_required()
def admin_logout():
    jti = get_jwt()["jti"]
    now = datetime.now(timezone.utc)
    token_exp_timestamp = get_jwt().get("exp")
    expires_at = datetime.fromtimestamp(token_exp_timestamp, tz=timezone.utc) if token_exp_timestamp else now + current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', timedelta(hours=1))
    
    try:
        db.session.add(TokenBlocklist(jti=jti, created_at=now, expires_at=expires_at))
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Error blocklisting token during admin logout: {e}", exc_info=True)
    
    response = jsonify(success=True, message="Admin logout successful. Token invalidated.")
    unset_jwt_cookies(response)
    return response, 200

@admin_api_bp.route('/login', methods=['POST'])
@limiter.limit(lambda: current_app.config.get('ADMIN_LOGIN_RATELIMITS', ["10 per 5 minutes"])[0])
def admin_login_step1_password():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    audit_logger = current_app.audit_log_service

    if not email or not password:
        audit_logger.log_action(action='admin_login_fail_step1', email=email, details="Email and password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email and password are required", success=False, totp_required=False), 400
    try:
        admin_user = User.query.filter(func.lower(User.email) == email.lower(), User.role == UserRoleEnum.ADMIN).first()
        if admin_user and admin_user.check_password(password):
            if not admin_user.is_active:
                audit_logger.log_action(user_id=admin_user.id, action='admin_login_fail_inactive_step1', details="Admin account is inactive.", status='failure', ip_address=request.remote_addr)
                return jsonify(message="Admin account is inactive. Please contact support.", success=False, totp_required=False), 403
            
            if admin_user.is_totp_enabled and admin_user.totp_secret:
                session['pending_totp_admin_id'] = admin_user.id
                session['pending_totp_admin_email'] = admin_user.email 
                session.permanent = True 
                current_app.permanent_session_lifetime = current_app.config.get('TOTP_LOGIN_STATE_TIMEOUT', timedelta(minutes=5))
                audit_logger.log_action(user_id=admin_user.id, action='admin_login_totp_required', status='pending', ip_address=request.remote_addr)
                return jsonify(message="Password verified. Please enter your TOTP code.", success=True, totp_required=True, email=admin_user.email), 200 
            else:
                audit_logger.log_action(user_id=admin_user.id, action='admin_login_success_no_totp', status='success', ip_address=request.remote_addr)
                return _create_admin_session_and_get_response(admin_user)
        else:
            audit_logger.log_action(action='admin_login_fail_credentials_step1', email=email, details="Invalid admin credentials.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid admin email or password", success=False, totp_required=False), 401
    except Exception as e:
        current_app.logger.error(f"Error during admin login step 1 for {email}: {e}", exc_info=True)
        return jsonify(message="Admin login failed due to a server error.", success=False, totp_required=False), 500

@admin_api_bp.route('/login/verify-totp', methods=['POST'])
@limiter.limit(lambda: current_app.config.get('ADMIN_LOGIN_RATELIMITS', ["10 per 5 minutes"]))
def admin_login_step2_verify_totp():
    data = request.json
    totp_code = data.get('totp_code')
    audit_logger = current_app.audit_log_service
    pending_admin_id = session.get('pending_totp_admin_id')
    pending_admin_email = session.get('pending_totp_admin_email')

    if not pending_admin_id:
        return jsonify(message="Login session expired or invalid. Please start over.", success=False), 400
    if not totp_code:
        return jsonify(message="TOTP code is required.", success=False), 400
    
    try:
        admin_user = User.query.get(pending_admin_id)
        if not admin_user or not admin_user.is_active or admin_user.role != UserRoleEnum.ADMIN:
            session.pop('pending_totp_admin_id', None); session.pop('pending_totp_admin_email', None)
            return jsonify(message="Invalid user state for TOTP verification.", success=False), 403

        if admin_user.verify_totp(totp_code):
            session.pop('pending_totp_admin_id', None); session.pop('pending_totp_admin_email', None)
            audit_logger.log_action(user_id=admin_user.id, action='admin_login_success_totp_verified', status='success', ip_address=request.remote_addr)
            return _create_admin_session_and_get_response(admin_user)
        else:
            audit_logger.log_action(user_id=admin_user.id, action='admin_totp_verify_fail_invalid_code', email=pending_admin_email, status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid TOTP code. Please try again.", success=False), 401
    except Exception as e:
        current_app.logger.error(f"Error during admin TOTP verification for {pending_admin_email}: {e}", exc_info=True)
        return jsonify(message="TOTP verification failed due to a server error.", success=False), 500

@admin_api_bp.route('/login/simplelogin/initiate', methods=['GET'])
def simplelogin_initiate():
    client_id = current_app.config.get('SIMPLELOGIN_CLIENT_ID')
    redirect_uri = current_app.config.get('SIMPLELOGIN_REDIRECT_URI_ADMIN')
    authorize_url = current_app.config.get('SIMPLELOGIN_AUTHORIZE_URL')
    scopes = current_app.config.get('SIMPLELOGIN_SCOPES')

    if not all([client_id, redirect_uri, authorize_url, scopes]):
        current_app.logger.error("SimpleLogin OAuth settings are not fully configured.")
        return jsonify(message="SimpleLogin SSO is not configured correctly.", success=False), 500

    session['oauth_state_sl'] = secrets.token_urlsafe(16)
    params = {'response_type': 'code', 'client_id': client_id, 'redirect_uri': redirect_uri, 'scope': scopes, 'state': session['oauth_state_sl']}
    auth_redirect_url = f"{authorize_url}?{urlencode(params)}"
    current_app.logger.info(f"Redirecting admin to SimpleLogin: {auth_redirect_url}")
    return redirect(auth_redirect_url)

@admin_api_bp.route('/login/simplelogin/callback', methods=['GET'])
def simplelogin_callback():
    auth_code = request.args.get('code')
    state_returned = request.args.get('state')
    audit_logger = current_app.audit_log_service
    base_admin_login_url = current_app.config.get('APP_BASE_URL_FRONTEND', 'http://localhost:8000') + '/admin/admin_login.html'
    admin_dashboard_url = current_app.config.get('APP_BASE_URL_FRONTEND', 'http://localhost:8000') + '/admin/admin_dashboard.html'

    expected_state = session.pop('oauth_state_sl', None)
    if not expected_state or expected_state != state_returned:
        audit_logger.log_action(action='simplelogin_callback_fail_state_mismatch', details="OAuth state mismatch.", status='failure', ip_address=request.remote_addr)
        return redirect(f"{base_admin_login_url}?error=sso_state_mismatch")

    if not auth_code:
        return redirect(f"{base_admin_login_url}?error=sso_no_code")

    token_url = current_app.config['SIMPLELOGIN_TOKEN_URL']
    payload = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': current_app.config['SIMPLELOGIN_REDIRECT_URI_ADMIN'],
        'client_id': current_app.config['SIMPLELOGIN_CLIENT_ID'],
        'client_secret': current_app.config['SIMPLELOGIN_CLIENT_SECRET'],
    }
    try:
        token_response = requests.post(token_url, data=payload, timeout=10)
        token_response.raise_for_status() 
        sl_access_token = token_response.json().get('access_token')
        if not sl_access_token:
            return redirect(f"{base_admin_login_url}?error=sso_token_error")

        userinfo_response = requests.get(current_app.config['SIMPLELOGIN_USERINFO_URL'], headers={'Authorization': f'Bearer {sl_access_token}'}, timeout=10)
        userinfo_response.raise_for_status()
        sl_user_info = userinfo_response.json()
        sl_email = sl_user_info.get('email')
        sl_simplelogin_user_id = sl_user_info.get('sub') 

        if not sl_email:
            return redirect(f"{base_admin_login_url}?error=sso_email_error")
        
        allowed_admin_emails_str = current_app.config.get('SIMPLELOGIN_ALLOWED_ADMIN_EMAILS', "")
        allowed_admin_emails = [email.strip().lower() for email in allowed_admin_emails_str.split(',') if email.strip()]

        if not allowed_admin_emails:
            current_app.logger.error("SIMPLELOGIN_ALLOWED_ADMIN_EMAILS is not configured. Denying SimpleLogin attempt.")
            audit_logger.log_action(action='simplelogin_callback_fail_config_missing', email=sl_email, details="Allowed admin emails for SSO not configured.", status='failure', ip_address=request.remote_addr)
            return redirect(f"{base_admin_login_url}?error=sso_config_error")

        if sl_email.lower() not in allowed_admin_emails:
            audit_logger.log_action(action='simplelogin_callback_fail_email_not_allowed', email=sl_email, details=f"SSO attempt from non-allowed email: {sl_email}", status='failure', ip_address=request.remote_addr)
            return redirect(f"{base_admin_login_url}?error=sso_unauthorized_email")

        admin_user = User.query.filter(func.lower(User.email) == sl_email.lower(), User.role == UserRoleEnum.ADMIN).first()
        if admin_user and admin_user.is_active:
            if not admin_user.simplelogin_user_id and sl_simplelogin_user_id:
                admin_user.simplelogin_user_id = sl_simplelogin_user_id
                db.session.commit()
            audit_logger.log_action(user_id=admin_user.id, action='admin_login_success_simplelogin', target_type='user_admin', target_id=admin_user.id, details=f"Admin {sl_email} logged in via SimpleLogin.", status='success', ip_address=request.remote_addr)
            return _create_admin_session_and_get_response(admin_user, admin_dashboard_url)
        elif admin_user and not admin_user.is_active:
            return redirect(f"{base_admin_login_url}?error=sso_account_inactive")
        else: 
            return redirect(f"{base_admin_login_url}?error=sso_admin_not_found")
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"SimpleLogin OAuth request exception: {e}", exc_info=True)
        return redirect(f"{base_admin_login_url}?error=sso_communication_error")
    except Exception as e:
        current_app.logger.error(f"Generic error during SimpleLogin callback: {e}", exc_info=True)
        return redirect(f"{base_admin_login_url}?error=sso_server_error")

# --- TOTP Management Routes ---
@admin_api_bp.route('/totp/setup-initiate', methods=['POST'])
@admin_required
@limiter.limit(lambda: current_app.config.get('ADMIN_TOTP_SETUP_RATELIMITS', "5 per 10 minutes"))
def totp_setup_initiate():
    current_admin_id = get_jwt_identity()
    data = request.json
    password = data.get('password')
    audit_logger = current_app.audit_log_service
    admin_user = User.query.get(current_admin_id)

    if not admin_user or admin_user.role != UserRoleEnum.ADMIN: 
        return jsonify(message="Admin user not found or invalid.", success=False), 403
    if not password or not admin_user.check_password(password):
        audit_logger.log_action(user_id=current_admin_id, action='totp_setup_initiate_fail_password', details="Incorrect password for TOTP setup.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Incorrect current password.", success=False), 401
    try:
        new_secret = admin_user.generate_totp_secret()
        session['pending_totp_secret_for_setup'] = new_secret 
        session['pending_totp_user_id_for_setup'] = admin_user.id
        session.permanent = True
        current_app.permanent_session_lifetime = current_app.config.get('TOTP_SETUP_SECRET_TIMEOUT', timedelta(minutes=10))
        provisioning_uri = admin_user.get_totp_uri()
        if not provisioning_uri: 
            raise Exception("Could not generate provisioning URI.")
        audit_logger.log_action(user_id=current_admin_id, action='totp_setup_initiate_success', details="TOTP secret generated.", status='success', ip_address=request.remote_addr)
        return jsonify(message="TOTP setup initiated. Scan QR code and verify.", totp_provisioning_uri=provisioning_uri, totp_manual_secret=new_secret, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error initiating TOTP setup for admin {current_admin_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to initiate TOTP setup: {str(e)}", success=False), 500

@admin_api_bp.route('/totp/setup-verify', methods=['POST'])
@admin_required
@limiter.limit(lambda: current_app.config.get('ADMIN_TOTP_SETUP_RATELIMITS', "5 per 10 minutes"))
def totp_setup_verify_and_enable():
    current_admin_id = get_jwt_identity()
    data = request.json
    totp_code = data.get('totp_code')
    audit_logger = current_app.audit_log_service
    pending_secret = session.get('pending_totp_secret_for_setup')
    pending_user_id = session.get('pending_totp_user_id_for_setup')

    if not pending_secret or not pending_user_id or pending_user_id != current_admin_id:
        return jsonify(message="TOTP setup session expired or invalid. Please start over.", success=False), 400
    if not totp_code: 
        return jsonify(message="TOTP code is required for verification.", success=False), 400

    admin_user = User.query.get(current_admin_id)
    if not admin_user: 
        return jsonify(message="Admin user not found.", success=False), 404
    
    temp_totp_instance = pyotp.TOTP(pending_secret)
    if temp_totp_instance.verify(totp_code):
        try:
            admin_user.totp_secret = pending_secret
            admin_user.is_totp_enabled = True
            admin_user.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            session.pop('pending_totp_secret_for_setup', None)
            session.pop('pending_totp_user_id_for_setup', None)
            audit_logger.log_action(user_id=current_admin_id, action='totp_setup_verify_success', details="TOTP enabled.", status='success', ip_address=request.remote_addr)
            return jsonify(message="Two-Factor Authentication (TOTP) enabled successfully!", success=True), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving TOTP setup for admin {current_admin_id}: {e}", exc_info=True)
            return jsonify(message="Failed to save TOTP settings.", success=False), 500
    else:
        audit_logger.log_action(user_id=current_admin_id, action='totp_setup_verify_fail_invalid_code', details="Invalid TOTP code during setup.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid TOTP code. Please try again.", success=False), 400

@admin_api_bp.route('/totp/disable', methods=['POST'])
@admin_required
@limiter.limit(lambda: current_app.config.get('ADMIN_TOTP_SETUP_RATELIMITS', "5 per 10 minutes"))
def totp_disable():
    current_admin_id = get_jwt_identity()
    data = request.json
    password = data.get('password')
    totp_code = data.get('totp_code')
    audit_logger = current_app.audit_log_service
    admin_user = User.query.get(current_admin_id)

    if not admin_user or admin_user.role != UserRoleEnum.ADMIN: 
        return jsonify(message="Admin user not found or invalid.", success=False), 403
    if not admin_user.is_totp_enabled or not admin_user.totp_secret:
        return jsonify(message="TOTP is not currently enabled for your account.", success=False), 400
    if not password or not admin_user.check_password(password):
        return jsonify(message="Incorrect current password.", success=False), 401
    if not totp_code or not admin_user.verify_totp(totp_code):
        return jsonify(message="Invalid current TOTP code.", success=False), 401
    try:
        admin_user.is_totp_enabled = False
        admin_user.totp_secret = None
        admin_user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='totp_disable_success', details="TOTP disabled.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Two-Factor Authentication (TOTP) has been disabled.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error disabling TOTP for admin {current_admin_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to disable TOTP: {str(e)}", success=False), 500
