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
    # ... (Implementation is identical to the one in routes.py, so it's moved here) ...
    # This function handles the OAuth callback, exchanges code for token,
    # gets user info, and logs in the admin if they are authorized.
    pass # The full implementation from routes.py goes here

# --- TOTP Management Routes ---
@admin_api_bp.route('/totp/setup-initiate', methods=['POST'])
@admin_required
def totp_setup_initiate():
    # ... (Implementation from routes.py) ...
    pass

@admin_api_bp.route('/totp/setup-verify', methods=['POST'])
@admin_required
def totp_setup_verify_and_enable():
    # ... (Implementation from routes.py) ...
    pass

@admin_api_bp.route('/totp/disable', methods=['POST'])
@admin_required
def totp_disable():
    # ... (Implementation from routes.py) ...
    pass

