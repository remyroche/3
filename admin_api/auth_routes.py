# backend/admin_api/auth_routes.py
# Admin Authentication and Profile Management
import requests
import secrets
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta
from flask import request, jsonify, current_app, redirect, session
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt, unset_jwt_cookies
from sqlalchemy import func

from . import admin_api_bp
from .. import db, limiter
from ..models import User, TokenBlocklist, UserRoleEnum
from ..utils import admin_required


from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, unset_jwt_cookies
from models.user_models import ProfessionalUser
from database import db
# Assuming you have a password hashing utility
from utils import check_password_hash 


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    B2B User login route. On success, sets an HttpOnly access token cookie.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    user = ProfessionalUser.query.filter_by(email=email).first()

    if user and user.check_password(password):
        # Identity can be the user's ID or any other unique identifier
        access_token = create_access_token(identity=user.id)
        response = jsonify({"message": "Login successful"})
        # set_access_cookies(response, access_token) # flask_jwt_extended > 4.0
        response.set_cookie('access_token_cookie', access_token, httponly=True, secure=True, samesite='Lax')
        return response, 200
    
    return jsonify({"message": "Invalid credentials"}), 401

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    B2B User logout route. Clears the HttpOnly access token cookie.
    """
    response = jsonify({"message": "Logout successful"})
    unset_jwt_cookies(response)
    return response, 200

</pre>

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
        # Note: set_access_cookies is not a standard Flask function, assuming custom or from an extension.
        # This part might need adjustment based on how cookies are actually set.
        # set_access_cookies(response, access_token) 
        current_app.logger.info(f"SSO successful for {admin_user.email}, redirecting...")
        return response
    else: 
        user_info_to_return = admin_user.to_dict()
        return jsonify(success=True, message="Admin login successful!", token=access_token, user=user_info_to_return), 200

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
    data = request.json; totp_code = data.get('totp_code')
    pending_admin_id = session.get('pending_totp_admin_id')
    if not pending_admin_id:
        return jsonify(message="Login session expired or invalid. Please start over.", success=False), 400
    if not totp_code:
        return jsonify(message="TOTP code is required.", success=False), 400
    try:
        admin_user = User.query.get(pending_admin_id)
        if not admin_user or not admin_user.is_active or admin_user.role != UserRoleEnum.ADMIN:
            return jsonify(message="Invalid user state for TOTP verification.", success=False), 403
        if admin_user.verify_totp(totp_code):
            session.pop('pending_totp_admin_id', None); session.pop('pending_totp_admin_email', None)
            return _create_admin_session_and_get_response(admin_user)
        else:
            return jsonify(message="Invalid TOTP code. Please try again.", success=False), 401
    except Exception as e:
        return jsonify(message="TOTP verification failed due to a server error.", success=False), 500




