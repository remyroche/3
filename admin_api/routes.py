# backend/admin_api/routes.py
import os
import uuid
import requests # For SimpleLogin OAuth calls
from urllib.parse import urlencode # For building query strings

from werkzeug.utils import secure_filename
# werkzeug.security.check_password_hash is not used directly here, User.check_password is used
from flask import request, jsonify, current_app, url_for, redirect, session # Added session for temp storage
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import func, or_, and_
from datetime import datetime, timezone, timedelta

from .. import db
from ..models import (
    User, Category, Product, ProductImage, ProductWeightOption,
    Order, OrderItem, Review, Setting, SerializedInventoryItem,
    StockMovement, Invoice, InvoiceItem, ProfessionalDocument,
    ProductLocalization, CategoryLocalization, GeneratedAsset
)
from ..utils import (
    admin_required, staff_or_admin_required, format_datetime_for_display, parse_datetime_from_iso,
    generate_slug, allowed_file, get_file_extension, format_datetime_for_storage,
    generate_static_json_files
)
from ..services.invoice_service import InvoiceService
from ..database import record_stock_movement

from . import admin_api_bp

# Temporary storage for user ID during TOTP verification.
# In a real app, use Flask session or a more secure temporary token mechanism.
# For simplicity here, we'll use Flask's session. Ensure SECRET_KEY is strong.
# This requires `session` to be imported from `flask`.

def _create_admin_session(admin_user):
    """Helper to create JWT and user info for successful admin login."""
    identity = admin_user.id
    additional_claims = {
        "role": admin_user.role, "email": admin_user.email, "is_admin": True,
        "first_name": admin_user.first_name, "last_name": admin_user.last_name
    }
    access_token = create_access_token(identity=identity, additional_claims=additional_claims)
    user_info_to_return = admin_user.to_dict() # Use the to_dict method
    return jsonify(success=True, message="Admin login successful!", token=access_token, user=user_info_to_return), 200

@admin_api_bp.route('/login', methods=['POST'])
def admin_login_step1_password():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    audit_logger = current_app.audit_log_service

    if not email or not password:
        audit_logger.log_action(action='admin_login_fail_step1', email=email, details="Email and password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email and password are required", success=False, totp_required=False), 400

    try:
        admin_user = User.query.filter_by(email=email, role='admin').first()

        if admin_user and admin_user.check_password(password):
            if not admin_user.is_active:
                audit_logger.log_action(user_id=admin_user.id, action='admin_login_fail_inactive_step1', target_type='user_admin', target_id=admin_user.id, details="Admin account is inactive.", status='failure', ip_address=request.remote_addr)
                return jsonify(message="Admin account is inactive. Please contact support.", success=False, totp_required=False), 403

            if admin_user.is_totp_enabled and admin_user.totp_secret:
                # Password correct, TOTP enabled. Store user_id temporarily and ask for TOTP.
                # Using Flask session for temporary storage.
                session['pending_totp_admin_id'] = admin_user.id
                session['pending_totp_admin_email'] = admin_user.email # For logging
                session.permanent = True # Make it last for the configured timeout
                current_app.permanent_session_lifetime = current_app.config.get('TOTP_LOGIN_STATE_TIMEOUT', timedelta(minutes=5))

                audit_logger.log_action(user_id=admin_user.id, action='admin_login_totp_required', target_type='user_admin', target_id=admin_user.id, status='pending', ip_address=request.remote_addr)
                return jsonify(message="Password verified. Please enter your TOTP code.", success=True, totp_required=True, email=admin_user.email), 200 # Indicate TOTP is next
            else:
                # Password correct, TOTP not enabled. Log in directly.
                audit_logger.log_action(user_id=admin_user.id, action='admin_login_success_no_totp', target_type='user_admin', target_id=admin_user.id, status='success', ip_address=request.remote_addr)
                return _create_admin_session(admin_user)
        else:
            audit_logger.log_action(action='admin_login_fail_credentials_step1', email=email, details="Invalid admin credentials.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid admin email or password", success=False, totp_required=False), 401

    except Exception as e:
        current_app.logger.error(f"Error during admin login step 1 for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='admin_login_fail_server_error_step1', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Admin login failed due to a server error", success=False, totp_required=False), 500

@admin_api_bp.route('/login/verify-totp', methods=['POST'])
def admin_login_step2_verify_totp():
    data = request.json
    totp_code = data.get('totp_code')
    # email_from_request = data.get('email') # Client might send email for context

    audit_logger = current_app.audit_log_service
    
    pending_admin_id = session.get('pending_totp_admin_id')
    pending_admin_email = session.get('pending_totp_admin_email') # For logging

    if not pending_admin_id:
        audit_logger.log_action(action='admin_totp_verify_fail_no_pending_state', details="No pending TOTP login state found in session.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Login session expired or invalid. Please start over.", success=False), 400
    
    if not totp_code:
        audit_logger.log_action(user_id=pending_admin_id, action='admin_totp_verify_fail_no_code', email=pending_admin_email, details="TOTP code missing.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="TOTP code is required.", success=False), 400

    try:
        admin_user = User.query.get(pending_admin_id)
        if not admin_user or not admin_user.is_active or admin_user.role != 'admin':
            session.pop('pending_totp_admin_id', None)
            session.pop('pending_totp_admin_email', None)
            audit_logger.log_action(user_id=pending_admin_id, action='admin_totp_verify_fail_user_invalid', email=pending_admin_email, details="Admin user not found, inactive, or not admin role during TOTP.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid user state for TOTP verification.", success=False), 403

        if admin_user.verify_totp(totp_code):
            session.pop('pending_totp_admin_id', None)
            session.pop('pending_totp_admin_email', None)
            audit_logger.log_action(user_id=admin_user.id, action='admin_login_success_totp_verified', target_type='user_admin', target_id=admin_user.id, status='success', ip_address=request.remote_addr)
            return _create_admin_session(admin_user)
        else:
            # Do not clear session yet, allow retries (rate limit this endpoint heavily)
            audit_logger.log_action(user_id=admin_user.id, action='admin_totp_verify_fail_invalid_code', email=pending_admin_email, details="Invalid TOTP code.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid TOTP code.", success=False), 401
            
    except Exception as e:
        current_app.logger.error(f"Error during admin TOTP verification for {pending_admin_email}: {e}", exc_info=True)
        audit_logger.log_action(user_id=pending_admin_id, action='admin_totp_verify_fail_server_error', email=pending_admin_email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="TOTP verification failed due to a server error.", success=False), 500


# --- SimpleLogin SSO Routes ---
@admin_api_bp.route('/login/simplelogin/initiate', methods=['GET'])
def simplelogin_initiate():
    """Initiates the OAuth flow by redirecting the user to SimpleLogin."""
    client_id = current_app.config.get('SIMPLELOGIN_CLIENT_ID')
    redirect_uri = current_app.config.get('SIMPLELOGIN_REDIRECT_URI_ADMIN')
    authorize_url = current_app.config.get('SIMPLELOGIN_AUTHORIZE_URL')
    scopes = current_app.config.get('SIMPLELOGIN_SCOPES')

    if not all([client_id, redirect_uri, authorize_url, scopes]):
        current_app.logger.error("SimpleLogin OAuth settings are not fully configured in the backend.")
        return jsonify(message="SimpleLogin SSO is not configured correctly on the server.", success=False), 500

    # Generate a state parameter for CSRF protection (recommended)
    # For simplicity, not implemented here but crucial for production.
    # session['oauth_state'] = secrets.token_urlsafe(16)

    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': scopes,
        # 'state': session['oauth_state'] # Add state here
    }
    auth_redirect_url = f"{authorize_url}?{urlencode(params)}"
    current_app.logger.info(f"Redirecting admin to SimpleLogin for authentication: {auth_redirect_url}")
    return redirect(auth_redirect_url)


@admin_api_bp.route('/login/simplelogin/callback', methods=['GET'])
def simplelogin_callback():
    """Handles the callback from SimpleLogin after user authentication."""
    auth_code = request.args.get('code')
    # state_returned = request.args.get('state') # Verify state here against session['oauth_state']

    audit_logger = current_app.audit_log_service

    if not auth_code:
        audit_logger.log_action(action='simplelogin_callback_fail_no_code', details="No authorization code received from SimpleLogin.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="SimpleLogin authentication failed (no code).", success=False), 400

    # Exchange authorization code for access token
    token_url = current_app.config['SIMPLELOGIN_TOKEN_URL']
    payload = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': current_app.config['SIMPLELOGIN_REDIRECT_URI_ADMIN'],
        'client_id': current_app.config['SIMPLELOGIN_CLIENT_ID'],
        'client_secret': current_app.config['SIMPLELOGIN_CLIENT_SECRET'],
    }
    try:
        token_response = requests.post(token_url, data=payload)
        token_response.raise_for_status() # Raise an exception for HTTP errors
        token_data = token_response.json()
        sl_access_token = token_data.get('access_token')

        if not sl_access_token:
            audit_logger.log_action(action='simplelogin_callback_fail_no_access_token', details="No access token from SimpleLogin.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Failed to get access token from SimpleLogin.", success=False), 500

        # Fetch user info from SimpleLogin
        userinfo_url = current_app.config['SIMPLELOGIN_USERINFO_URL']
        headers = {'Authorization': f'Bearer {sl_access_token}'}
        userinfo_response = requests.get(userinfo_url, headers=headers)
        userinfo_response.raise_for_status()
        sl_user_info = userinfo_response.json()
        
        sl_email = sl_user_info.get('email')
        # sl_name = sl_user_info.get('name') # Optional
        # sl_sub = sl_user_info.get('sub') # SimpleLogin user ID

        if not sl_email:
            audit_logger.log_action(action='simplelogin_callback_fail_no_email', details="No email in userinfo from SimpleLogin.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Could not retrieve email from SimpleLogin.", success=False), 500

        # Find or provision admin user in your database
        admin_user = User.query.filter_by(email=sl_email, role='admin').first()

        if admin_user and admin_user.is_active:
            # User exists and is an active admin, log them in
            audit_logger.log_action(user_id=admin_user.id, action='admin_login_success_simplelogin', target_type='user_admin', target_id=admin_user.id, details=f"Admin {sl_email} logged in via SimpleLogin.", status='success', ip_address=request.remote_addr)
            
            # Create your application's session/JWT
            _, status_code = _create_admin_session(admin_user) # We only need the JSON response part
            
            # Redirect to admin dashboard with token (or set cookie if JWT_TOKEN_LOCATION includes 'cookies')
            # For simplicity, redirecting and letting frontend JS handle token from response if needed,
            # or assuming cookie-based JWT session is set by _create_admin_session.
            # If using header-based JWT, the frontend needs a way to get this token after redirect.
            # A common pattern is to redirect to a frontend page that then makes a request to get the token,
            # or pass the token as a query parameter (less secure).
            # If JWT_TOKEN_LOCATION includes 'cookies' and JWT_COOKIE_CSRF_PROTECT is True,
            # Flask-JWT-Extended will set the cookies automatically on the response from _create_admin_session.
            # The redirect below assumes cookies are used or frontend handles it.
            
            admin_dashboard_url = url_for('admin_dashboard_frontend_route', _external=True) # Define this route if you have a separate frontend router
            if not admin_dashboard_url or admin_dashboard_url == '/': # Fallback if not defined
                 admin_dashboard_url = current_app.config.get('APP_BASE_URL', 'http://localhost:8000') + '/admin/admin_dashboard.html'
            
            # Create the response from _create_admin_session
            response_data, _ = _create_admin_session(admin_user)
            # Manually create a redirect response and set cookies if needed by Flask-JWT-Extended
            # This is a bit complex if not using Flask-Login for session management directly after OAuth.
            # For now, let's assume the JWT is set as a cookie by `create_access_token`
            # if `JWT_TOKEN_LOCATION` includes `cookies`.
            # The `_create_admin_session` returns a jsonify response. We need to make it a redirect.

            # Simplest redirect assuming cookies are set by create_access_token
            final_response = redirect(admin_dashboard_url)
            # If create_access_token is configured to set cookies, it will do so on the response.
            # We need to ensure the JWT cookies are set on this redirect response.
            # Flask-JWT-Extended does this automatically if JWT_TOKEN_LOCATION includes 'cookies'.
            # The token from _create_admin_session is in its JSON body.
            # We need to call create_access_token again here or pass the response object to set cookies.

            # Re-creating token to ensure cookies are set on the redirect response
            identity = admin_user.id
            additional_claims = {
                "role": admin_user.role, "email": admin_user.email, "is_admin": True,
                "first_name": admin_user.first_name, "last_name": admin_user.last_name
            }
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            # If using cookies, Flask-JWT-Extended will set them on the response object `final_response`
            # if this function is decorated with @jwt_required or similar, or if done manually.
            # Since this is a callback, we might need to manually set cookies if not automatic.
            # However, `create_access_token` itself doesn't set cookies; it returns the token.
            # The response from `_create_admin_session` *would* set cookies if it were returned directly.
            
            # For simplicity, let's assume the frontend will handle a token passed via query param after redirect.
            # This is less secure than cookies or server-side sessions post-OAuth.
            # A better approach is to redirect to a page that then fetches user info using the JWT.
            # Or, if JWTs are in cookies, the redirect itself is fine.
            
            # Assuming JWT is in cookies:
            # Create the token which will be set in cookies by Flask-JWT-Extended on the response
            create_access_token(identity=admin_user.id, additional_claims={
                "role": admin_user.role, "email": admin_user.email, "is_admin": True,
                "first_name": admin_user.first_name, "last_name": admin_user.last_name
            })
            # The redirect response will have the JWT cookies set by Flask-JWT-Extended
            return final_response

        else:
            audit_logger.log_action(action='simplelogin_callback_fail_user_not_admin_or_inactive', email=sl_email, details="User found but not an active admin.", status='failure', ip_address=request.remote_addr)
            # Redirect to login page with an error message
            login_page_url = url_for('admin_login_frontend_route', error="sso_admin_not_found", _external=True) # Define this route
            if not login_page_url or login_page_url == '/':
                login_page_url = current_app.config.get('APP_BASE_URL', 'http://localhost:8000') + '/admin/admin_login.html?error=sso_admin_not_found'
            return redirect(login_page_url)

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"SimpleLogin OAuth request failed: {e}", exc_info=True)
        audit_logger.log_action(action='simplelogin_callback_fail_request_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Communication error with SimpleLogin: {e}", success=False), 502 # Bad Gateway
    except Exception as e:
        current_app.logger.error(f"Error during SimpleLogin callback: {e}", exc_info=True)
        audit_logger.log_action(action='simplelogin_callback_fail_server_error', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"An unexpected error occurred during SimpleLogin SSO: {e}", success=False), 500


# --- Dashboard ---
# (get_dashboard_stats and other routes remain the same)
# Ensure you have placeholder routes for 'admin_dashboard_frontend_route' and 'admin_login_frontend_route'
# if you use url_for with them, or construct URLs manually.
# For simplicity, I'll assume frontend handles query params on admin_login.html for errors.
@admin_api_bp.route('/dashboard/stats', methods=['GET'])
@admin_required
def get_dashboard_stats():
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        total_users = db.session.query(func.count(User.id)).scalar()
        total_products = Product.query.filter_by(is_active=True).count()
        # More specific count for pending orders based on typical statuses
        pending_order_statuses = ('paid', 'processing', 'awaiting_shipment')
        pending_orders = Order.query.filter(Order.status.in_(pending_order_statuses)).count()
        total_categories = Category.query.filter_by(is_active=True).count()
        pending_b2b_applications = User.query.filter_by(role='b2b_professional', professional_status='pending').count()
        
        stats = {
            "total_users": total_users,
            "total_products": total_products,
            "pending_orders": pending_orders, # Updated key for clarity
            "total_categories": total_categories,
            "pending_b2b_applications": pending_b2b_applications,
            "success": True
        }
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        total_users = db.session.query(func.count(User.id)).scalar()
        total_products = Product.query.filter_by(is_active=True).count()
        pending_order_statuses = ('paid', 'processing', 'awaiting_shipment')
        pending_orders = Order.query.filter(Order.status.in_(pending_order_statuses)).count()
        total_categories = Category.query.filter_by(is_active=True).count()
        pending_b2b_applications = User.query.filter_by(role='b2b_professional', professional_status='pending').count()
        
        stats = {
            "total_users": total_users,
            "total_products": total_products,
            "pending_orders": pending_orders,
            "total_categories": total_categories,
            "pending_b2b_applications": pending_b2b_applications,
            "success": True
        }
        audit_logger.log_action(user_id=current_admin_id, action='get_dashboard_stats', status='success', ip_address=request.remote_addr)
        return jsonify(stats=stats), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching dashboard stats: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='get_dashboard_stats_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to fetch dashboard statistics", success=False), 500


# --- Category Management ---
@admin_api_bp.route('/categories', methods=['POST'])
@admin_required
def create_category():
    data = request.form.to_dict() 
    name = data.get('name')
    description = data.get('description', '')
    parent_id_str = data.get('parent_id')
    category_code = data.get('category_code', '').strip().upper()
    image_file = request.files.get('image_url') 
    is_active = data.get('is_active', 'true').lower() == 'true'
    
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not name or not category_code:
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail_validation', details="Name and Category Code are required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Name and Category Code are required", success=False), 400

    slug = generate_slug(name)
    image_filename_db = None 

    try:
        if Category.query.filter_by(name=name).first():
            return jsonify(message=f"Category name '{name}' already exists", success=False), 409
        if Category.query.filter_by(slug=slug).first():
            return jsonify(message=f"Category slug '{slug}' already exists. Try a different name.", success=False), 409
        if Category.query.filter_by(category_code=category_code).first():
            return jsonify(message=f"Category code '{category_code}' already exists.", success=False), 409

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(f"category_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
            upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
            os.makedirs(upload_folder_categories, exist_ok=True)
            image_path_full = os.path.join(upload_folder_categories, filename)
            image_file.save(image_path_full)
            image_filename_db = os.path.join('categories', filename) # Relative path for DB

        parent_id = int(parent_id_str) if parent_id_str and parent_id_str.strip() and parent_id_str.lower() != 'null' else None

        new_category = Category(
            name=name, description=description, parent_id=parent_id, slug=slug, 
            image_url=image_filename_db, category_code=category_code, is_active=is_active
        )
        db.session.add(new_category)
        db.session.commit()
        
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='create_category_success', target_type='category', target_id=new_category.id, details=f"Category '{name}' created.", status='success', ip_address=request.remote_addr)
        # Assuming Category model has a to_dict() method
        return jsonify(message="Category created successfully", category=new_category.to_dict() if hasattr(new_category, 'to_dict') else {"id": new_category.id, "name": new_category.name}, success=True), 201
    except Exception as e: # Catch broader SQLAlchemy exceptions
        db.session.rollback()
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to create category: {str(e)}", success=False), 500

@admin_api_bp.route('/categories', methods=['GET'])
@admin_required
@admin_api_bp.route('/categories', methods=['GET'])
@admin_required
def get_categories():
    try:
        categories_models = Category.query.order_by(Category.name).all()
        categories_data = []
        for cat_model in categories_models:
            cat_dict = cat_model.to_dict() # Assuming to_dict method exists
            if cat_model.image_url:
                try:
                    cat_dict['image_full_url'] = url_for('serve_public_asset', filepath=cat_model.image_url, _external=True)
                except Exception as e_url:
                    current_app.logger.warning(f"Could not generate URL for category image {cat_model.image_url}: {e_url}")
            categories_data.append(cat_dict)
        return jsonify(categories=categories_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching categories for admin: {e}", exc_info=True)
        return jsonify(message=f"Failed to fetch categories: {str(e)}", success=False), 500


@admin_api_bp.route('/categories/<int:category_id>', methods=['GET'])
@admin_required
def get_category_detail(category_id):
    try:
        category_model = Category.query.get(category_id)
        if not category_model:
            return jsonify(message="Category not found", success=False), 404
        
        cat_dict = {
            "id": category_model.id, "name": category_model.name, "description": category_model.description, 
            "parent_id": category_model.parent_id, "slug": category_model.slug, 
            "image_url": category_model.image_url, "category_code": category_model.category_code,
            "is_active": category_model.is_active,
            "created_at": format_datetime_for_display(category_model.created_at),
            "updated_at": format_datetime_for_display(category_model.updated_at),
            "image_full_url": None
        }
        if category_model.image_url:
            try:
                cat_dict['image_full_url'] = url_for('serve_public_asset', filepath=category_model.image_url, _external=True)
            except Exception as e_url:
                current_app.logger.warning(f"Could not generate URL for category image {category_model.image_url}: {e_url}")
        
        return jsonify(category=cat_dict, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching category detail for ID {category_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to fetch category details: {str(e)}", success=False), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['PUT'])
@admin_required
def update_category(category_id):
    data = request.form.to_dict()
    name = data.get('name')
    description = data.get('description') 
    parent_id_str = data.get('parent_id')
    category_code = data.get('category_code', '').strip().upper()
    is_active_str = data.get('is_active')
    image_file = request.files.get('image_url')
    remove_image = data.get('remove_image') == 'true'

    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    
    if not name or not category_code:
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail_validation', target_type='category', target_id=category_id, details="Name and Category Code are required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Name and Category Code are required for update", success=False), 400

    try:
        category = Category.query.get(category_id)
        if not category:
            return jsonify(message="Category not found", success=False), 404

        new_slug = generate_slug(name) if name != category.name else category.slug
        
        # Check for uniqueness conflicts excluding the current category
        if name != category.name and Category.query.filter(Category.name == name, Category.id != category_id).first():
            return jsonify(message=f"Another category with the name '{name}' already exists", success=False), 409
        if new_slug != category.slug and Category.query.filter(Category.slug == new_slug, Category.id != category_id).first():
            return jsonify(message=f"Another category with slug '{new_slug}' already exists. Try a different name.", success=False), 409
        if category_code != category.category_code and Category.query.filter(Category.category_code == category_code, Category.id != category_id).first():
            return jsonify(message=f"Another category with code '{category_code}' already exists.", success=False), 409

        image_filename_to_update_db = category.image_url
        upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
        os.makedirs(upload_folder_categories, exist_ok=True)

        if remove_image and category.image_url:
            full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category.image_url)
            if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            image_filename_to_update_db = None
        elif image_file and allowed_file(image_file.filename):
            if category.image_url: # Remove old image if a new one is uploaded
                full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category.image_url)
                if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            filename = secure_filename(f"category_{new_slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
            image_file.save(os.path.join(upload_folder_categories, filename))
            image_filename_to_update_db = os.path.join('categories', filename)

        category.name = name
        category.slug = new_slug
        category.category_code = category_code
        category.description = description if description is not None else category.description
        category.parent_id = int(parent_id_str) if parent_id_str and parent_id_str.strip() and parent_id_str.lower() != 'null' else None
        if category.parent_id == category_id: # Prevent self-parenting
             return jsonify(message="Category cannot be its own parent.", success=False), 400
        category.image_url = image_filename_to_update_db
        if is_active_str is not None:
            category.is_active = is_active_str.lower() == 'true'
        
        db.session.commit()
        
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)
        
        audit_logger.log_action(user_id=current_user_id, action='update_category_success', target_type='category', target_id=category_id, details=f"Category '{name}' updated.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Category updated successfully", category=category.to_dict() if hasattr(category, 'to_dict') else {"id": category.id, "name": category.name}, success=True), 200
    except Exception as e:
        db.session.rollback()
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail_exception', target_type='category', target_id=category_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update category: {str(e)}", success=False), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        category_to_delete = Category.query.get(category_id)
        if not category_to_delete:
            return jsonify(message="Category not found", success=False), 404
        
        category_name_for_log = category_to_delete.name # Get name before delete

        # Check if category is in use by products
        if category_to_delete.products.count() > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail_in_use', target_type='category', target_id=category_id, details=f"Category '{category_name_for_log}' in use.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category '{category_name_for_log}' is in use. Reassign products first.", success=False), 409
        
        if category_to_delete.image_url:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category_to_delete.image_url)
            if os.path.exists(full_image_path): os.remove(full_image_path)
        
        db.session.delete(category_to_delete)
        db.session.commit()

        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='delete_category_success', target_type='category', target_id=category_id, details=f"Category '{category_name_for_log}' deleted.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Category '{category_name_for_log}' deleted successfully", success=True), 200
    except Exception as e:
        db.session.rollback()
        audit_logger.log_action(user_id=current_user_id, action='delete_category_fail_exception', target_type='category', target_id=category_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to delete category: {str(e)}", success=False), 500

# --- Product Management ---
@admin_api_bp.route('/products', methods=['POST'])
@admin_required
def create_product():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    
    try:
        data = request.form.to_dict() 
        main_image_file = request.files.get('main_image_url')
        
        name = data.get('name')
        product_code = data.get('product_code', '').strip().upper()
        sku_prefix = data.get('sku_prefix', product_code).strip().upper()
        product_type = data.get('type', 'simple')
        description = data.get('description', '')
        category_id_str = data.get('category_id')
        brand = data.get('brand', "Maison Trüvra")
        base_price_str = data.get('price')
        currency = data.get('currency', 'EUR')
        aggregate_stock_quantity_str = data.get('quantity', '0') # from 'quantity' field in form
        # aggregate_stock_weight_grams_str = data.get('aggregate_stock_weight_grams') # No direct form field, calculated or for serialized
        unit_of_measure = data.get('unit_of_measure')
        is_active = data.get('is_active', 'true').lower() == 'true'
        is_featured = data.get('is_featured', 'false').lower() == 'true'
        meta_title = data.get('meta_title', name)
        meta_description = data.get('meta_description', description[:160] if description else '')
        slug = generate_slug(name)

        if not all([name, product_code, product_type, category_id_str]):
            return jsonify(message="Name, Product Code, Type, and Category are required.", success=False), 400
        
        category_id = int(category_id_str) if category_id_str.isdigit() else None
        if category_id is None: return jsonify(message="Valid Category ID is required.", success=False), 400

        if Product.query.filter_by(product_code=product_code).first():
            return jsonify(message=f"Product Code '{product_code}' already exists.", success=False), 409
        if sku_prefix and Product.query.filter_by(sku_prefix=sku_prefix).first(): # Ensure SKU prefix is also unique if provided and different
             return jsonify(message=f"SKU Prefix '{sku_prefix}' already exists for another product.", success=False), 409
        if Product.query.filter_by(slug=slug).first():
            return jsonify(message=f"Product name (slug: '{slug}') already exists.", success=False), 409

        main_image_filename_db = None
        if main_image_file and allowed_file(main_image_file.filename):
            filename = secure_filename(f"product_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(main_image_file.filename)}")
            upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
            os.makedirs(upload_folder_products, exist_ok=True)
            main_image_file.save(os.path.join(upload_folder_products, filename))
            main_image_filename_db = os.path.join('products', filename)

        base_price = float(base_price_str) if base_price_str is not None and base_price_str != '' else None
        aggregate_stock_quantity = int(aggregate_stock_quantity_str) if aggregate_stock_quantity_str is not None and aggregate_stock_quantity_str != '' else 0
        # aggregate_stock_weight_grams = float(aggregate_stock_weight_grams_str) if aggregate_stock_weight_grams_str else None

        if product_type == 'simple' and base_price is None:
            return jsonify(message="Base price (Price field) is required for simple products.", success=False), 400
        
        new_product = Product(
            name=name, description=description, category_id=category_id, product_code=product_code, brand=brand, 
            sku_prefix=sku_prefix if sku_prefix else product_code, type=product_type, base_price=base_price, currency=currency, 
            main_image_url=main_image_filename_db, 
            aggregate_stock_quantity=aggregate_stock_quantity if product_type == 'simple' else 0, # Stock for simple, variants manage their own
            # aggregate_stock_weight_grams=aggregate_stock_weight_grams, # This is usually for variable or summed up, not directly set for parent
            unit_of_measure=unit_of_measure, is_active=is_active, is_featured=is_featured, 
            meta_title=meta_title, meta_description=meta_description, slug=slug
        )
        db.session.add(new_product)
        db.session.flush() # To get ID for stock movement

        if product_type == 'simple' and aggregate_stock_quantity > 0:
            record_stock_movement(db.session, new_product.id, 'initial_stock', quantity_change=aggregate_stock_quantity, reason="Initial stock for new simple product", related_user_id=current_user_id)
        
        db.session.commit()
        
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='create_product_success', target_type='product', target_id=new_product.id, details=f"Product '{name}' (Code: {product_code}) created.", status='success', ip_address=request.remote_addr)
        
        response_data = {"message": "Product created successfully", "product_id": new_product.id, "slug": slug, "success": True, "product": new_product.to_dict() if hasattr(new_product, 'to_dict') else {"id": new_product.id, "name": new_product.name}}
        return jsonify(response_data), 201

    except (ValueError) as e: # Catch specific errors like int/float conversion
        db.session.rollback()
        return jsonify(message=f"Invalid data provided: {str(e)}", success=False), 400
    except Exception as e:
        db.session.rollback()
        audit_logger.log_action(user_id=current_user_id, action='create_product_fail_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to create product: {str(e)}", success=False), 500

@admin_api_bp.route('/products', methods=['GET'])
@admin_required
def get_products_admin():
    # (SQLAlchemy conversion for get_products_admin - from previous turn)
    # This was already mostly converted, ensuring it's complete and consistent.
    include_variants_param = request.args.get('include_variants', 'false').lower() == 'true'
    search_term = request.args.get('search')
    try:
        query = Product.query.outerjoin(Category, Product.category_id == Category.id)
        
        if search_term:
            term_like = f"%{search_term.lower()}%"
            query = query.filter(
                or_(
                    func.lower(Product.name).like(term_like),
                    func.lower(Product.description).like(term_like),
                    func.lower(Product.product_code).like(term_like),
                    func.lower(Category.name).like(term_like) # Search in category name as well
                )
            )
            
        products_models = query.order_by(Product.name).all()
        products_data = []
        for p in products_models:
            p_dict = {
                "id": p.id, "name": p.name, "product_code": p.product_code, "sku_prefix": p.sku_prefix,
                "type": p.type, "base_price": p.base_price, "is_active": p.is_active, "is_featured": p.is_featured,
                "category_id": p.category_id, # Added category_id
                "category_name": p.category.name if p.category else None,
                "category_code": p.category.category_code if p.category else None,
                "main_image_full_url": url_for('serve_public_asset', filepath=p.main_image_url, _external=True) if p.main_image_url else None,
                "aggregate_stock_quantity": p.aggregate_stock_quantity,
                "created_at": format_datetime_for_display(p.created_at),
                "updated_at": format_datetime_for_display(p.updated_at),
                "price": p.base_price, 
                "quantity": p.aggregate_stock_quantity 
            }
            if p.type == 'variable_weight' or include_variants_param:
                options = p.weight_options.order_by(ProductWeightOption.weight_grams).all()
                p_dict['weight_options'] = [{'option_id': opt.id, 'weight_grams': opt.weight_grams, 'price': opt.price, 'sku_suffix': opt.sku_suffix, 'aggregate_stock_quantity': opt.aggregate_stock_quantity, 'is_active': opt.is_active} for opt in options]
                p_dict['variant_count'] = len(p_dict['weight_options'])
                if p.type == 'variable_weight' and p_dict['weight_options']:
                    p_dict['quantity'] = sum(opt.get('aggregate_stock_quantity', 0) for opt in p_dict['weight_options'])
            
            p_dict['additional_images'] = [{'id': img.id, 'image_url': img.image_url, 'image_full_url': url_for('serve_public_asset', filepath=img.image_url, _external=True) if img.image_url else None, 'is_primary': img.is_primary} for img in p.images]

            products_data.append(p_dict)
        return jsonify(products=products_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin products: {e}", exc_info=True)
        return jsonify(message=f"Failed to fetch products for admin: {str(e)}", success=False), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['GET'])
@admin_required
def get_product_admin_detail(product_id):
    try:
        product_model = Product.query.get(product_id)
        if not product_model:
            return jsonify(message="Product not found", success=False), 404
            
        product_details = {
            'id': product_model.id, 'name': product_model.name, 'description': product_model.description,
            'slug': product_model.slug, 'base_price': product_model.base_price, 'currency': product_model.currency,
            'main_image_url': product_model.main_image_url, 'type': product_model.type, 'sku_prefix': product_model.sku_prefix,
            'unit_of_measure': product_model.unit_of_measure, 'is_active': product_model.is_active, 'is_featured': product_model.is_featured,
            'aggregate_stock_quantity': product_model.aggregate_stock_quantity,
            'aggregate_stock_weight_grams': product_model.aggregate_stock_weight_grams,
            'product_code': product_model.product_code, 'brand': product_model.brand,
            'category_id': product_model.category_id,
            'category_name': product_model.category.name if product_model.category else None,
            'meta_title': product_model.meta_title, 'meta_description': product_model.meta_description,
            'created_at': format_datetime_for_display(product_model.created_at),
            'updated_at': format_datetime_for_display(product_model.updated_at),
            'main_image_full_url': None, 'additional_images': [], 'weight_options': [], 'assets': {}
        }

        if product_model.main_image_url:
            try: product_details['main_image_full_url'] = url_for('serve_public_asset', filepath=product_model.main_image_url, _external=True)
            except Exception as e_url: current_app.logger.warning(f"Could not generate URL for product image {product_model.main_image_url}: {e_url}")

        for img_model in product_model.images.order_by(ProductImage.is_primary.desc(), ProductImage.id.asc()).all():
            img_dict = {'id': img_model.id, 'image_url': img_model.image_url, 'alt_text': img_model.alt_text, 'is_primary': img_model.is_primary, 'image_full_url': None}
            if img_model.image_url:
                try: img_dict['image_full_url'] = url_for('serve_public_asset', filepath=img_model.image_url, _external=True)
                except Exception as e_img_url: current_app.logger.warning(f"Could not generate URL for additional image {img_model.image_url}: {e_img_url}")
            product_details['additional_images'].append(img_dict)

        if product_model.type == 'variable_weight':
            options = product_model.weight_options.order_by(ProductWeightOption.weight_grams).all()
            product_details['weight_options'] = [
                {'option_id': opt.id, 'weight_grams': opt.weight_grams, 'price': opt.price, 'sku_suffix': opt.sku_suffix, 
                 'aggregate_stock_quantity': opt.aggregate_stock_quantity, 'is_active': opt.is_active} for opt in options
            ]
        
        for asset_model in product_model.generated_assets:
            asset_type_key = asset_model.asset_type.lower().replace(' ', '_')
            asset_full_url = None
            if asset_model.file_path:
                try:
                    if asset_model.asset_type == 'passport_html': # Passports are public
                        asset_full_url = url_for('serve_public_asset', filepath=asset_model.file_path, _external=True)
                    else: # QR codes, labels might be admin-accessed
                        asset_full_url = url_for('admin_api_bp.serve_asset', asset_relative_path=asset_model.file_path, _external=True)
                except Exception as e_asset_url: current_app.logger.warning(f"Could not generate URL for asset {asset_model.file_path}: {e_asset_url}")
            product_details['assets'][f"{asset_type_key}_url"] = asset_full_url
            product_details['assets'][f"{asset_type_key}_file_path"] = asset_model.file_path
            
        return jsonify(product=product_details, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching product admin detail for ID {product_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to fetch product details (admin): {str(e)}", success=False), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['PUT'])
@admin_required
def update_product(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify(message="Product not found", success=False), 404

        data = request.form.to_dict()
        main_image_file = request.files.get('main_image_url')
        remove_main_image = data.get('remove_main_image') == 'true'

        name = data.get('name', product.name)
        new_slug = generate_slug(name) if name != product.name else product.slug
        
        new_product_code = data.get('product_code', product.product_code).strip().upper()
        if new_product_code != product.product_code and Product.query.filter(Product.product_code == new_product_code, Product.id != product_id).first():
            return jsonify(message=f"Product Code '{new_product_code}' already exists.", success=False), 409
        
        new_sku_prefix = data.get('sku_prefix', product.sku_prefix if product.sku_prefix else new_product_code).strip().upper()
        if new_sku_prefix != product.sku_prefix and Product.query.filter(Product.sku_prefix == new_sku_prefix, Product.id != product_id).first():
             return jsonify(message=f"SKU Prefix '{new_sku_prefix}' already exists for another product.", success=False), 409

        if new_slug != product.slug and Product.query.filter(Product.slug == new_slug, Product.id != product_id).first():
            return jsonify(message=f"Product name (slug: '{new_slug}') already exists.", success=False), 409
        
        main_image_filename_db = product.main_image_url
        upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
        os.makedirs(upload_folder_products, exist_ok=True)

        if remove_main_image and product.main_image_url:
            full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], product.main_image_url)
            if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            main_image_filename_db = None
        elif main_image_file and allowed_file(main_image_file.filename):
            if product.main_image_url:
                full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], product.main_image_url)
                if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            filename = secure_filename(f"product_{new_slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(main_image_file.filename)}")
            main_image_file.save(os.path.join(upload_folder_products, filename))
            main_image_filename_db = os.path.join('products', filename)

        product.name = name
        product.slug = new_slug
        product.product_code = new_product_code
        product.sku_prefix = new_sku_prefix
        product.description = data.get('description', product.description)
        product.category_id = int(data['category_id']) if data.get('category_id') and data['category_id'].isdigit() else product.category_id
        product.brand = data.get('brand', product.brand)
        product.type = data.get('type', product.type)
        product.base_price = float(data['price']) if data.get('price') is not None and data.get('price') != '' else product.base_price
        product.currency = data.get('currency', product.currency)
        product.main_image_url = main_image_filename_db
        product.aggregate_stock_quantity = int(data['quantity']) if data.get('quantity') is not None and data.get('quantity') != '' else product.aggregate_stock_quantity
        # product.aggregate_stock_weight_grams = float(data['aggregate_stock_weight_grams']) if data.get('aggregate_stock_weight_grams') is not None and data.get('aggregate_stock_weight_grams') != '' else product.aggregate_stock_weight_grams
        product.unit_of_measure = data.get('unit_of_measure', product.unit_of_measure)
        product.is_active = data.get('is_active', str(product.is_active)).lower() == 'true'
        product.is_featured = data.get('is_featured', str(product.is_featured)).lower() == 'true'
        product.meta_title = data.get('meta_title', product.meta_title or name)
        product.meta_description = data.get('meta_description', product.meta_description or data.get('description', '')[:160])
        
        if product.type == 'simple' and product.base_price is None:
            return jsonify(message="Base price (Price field) is required for simple products.", success=False), 400
        
        # If type changed from variable_weight to simple, delete options
        if product.type == 'simple' and data.get('type') == 'simple' and Product.query.get(product_id).type == 'variable_weight':
             ProductWeightOption.query.filter_by(product_id=product_id).delete()

        db.session.commit()
        
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='update_product_success', target_type='product', target_id=product_id, details=f"Product '{name}' (Code: {new_product_code}) updated.", status='success', ip_address=request.remote_addr)
        
        return jsonify(message="Product updated successfully", product=product.to_dict() if hasattr(product, 'to_dict') else {"id": product.id, "name": product.name}, success=True), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify(message=f"Invalid data provided: {str(e)}", success=False), 400
    except Exception as e:
        db.session.rollback()
        audit_logger.log_action(user_id=current_user_id, action='update_product_fail_exception', target_type='product', target_id=product_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update product: {str(e)}", success=False), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['DELETE'])
@admin_required
def delete_product(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        product_to_delete = Product.query.get(product_id)
        if not product_to_delete:
            return jsonify(message="Product not found", success=False), 404
        
        product_name_for_log = product_to_delete.name

        # Delete associated images from filesystem
        if product_to_delete.main_image_url:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], product_to_delete.main_image_url)
            if os.path.exists(full_image_path): os.remove(full_image_path)
        for img in product_to_delete.images:
            if img.image_url:
                full_add_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], img.image_url)
                if os.path.exists(full_add_image_path): os.remove(full_add_image_path)
        
        # SQLAlchemy will handle cascading deletes for related tables like ProductImage, ProductWeightOption due to model definitions
        db.session.delete(product_to_delete)
        db.session.commit()

        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='delete_product_success', target_type='product', target_id=product_id, details=f"Product '{product_name_for_log}' deleted.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Product '{product_name_for_log}' deleted successfully", success=True), 200
    except Exception as e: # Catch broader SQLAlchemy exceptions
        db.session.rollback()
        audit_logger.log_action(user_id=current_user_id, action='delete_product_fail_exception', target_type='product', target_id=product_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to delete product: {str(e)}", success=False), 500
        
# --- User Management ---
@admin_api_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    role_filter = request.args.get('role')
    status_filter_str = request.args.get('is_active') 
    search_term = request.args.get('search')

    query = User.query
    if role_filter: query = query.filter(User.role == role_filter)
    if status_filter_str is not None:
        is_active_val = status_filter_str.lower() == 'true'
        query = query.filter(User.is_active == is_active_val)
    if search_term:
        term_like = f"%{search_term.lower()}%"
        query = query.filter(
            or_(
                func.lower(User.email).like(term_like),
                func.lower(User.first_name).like(term_like),
                func.lower(User.last_name).like(term_like),
                func.lower(User.company_name).like(term_like),
                func.cast(User.id, db.String).like(term_like) # Cast ID to string for LIKE
            )
        )
    
    users_models = query.order_by(User.created_at.desc()).all()
    users_data = [{
        "id": u.id, "email": u.email, "first_name": u.first_name, "last_name": u.last_name,
        "role": u.role, "is_active": u.is_active, "is_verified": u.is_verified,
        "company_name": u.company_name, "professional_status": u.professional_status,
        "created_at": format_datetime_for_display(u.created_at)
    } for u in users_models]
    return jsonify(users=users_data, success=True), 200

@admin_api_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user_admin_detail(user_id):
    user_model = User.query.get(user_id)
    if not user_model: return jsonify(message="User not found", success=False), 404
    
    user_data = {
        "id": user_model.id, "email": user_model.email, "first_name": user_model.first_name, 
        "last_name": user_model.last_name, "role": user_model.role, "is_active": user_model.is_active, 
        "is_verified": user_model.is_verified, "company_name": user_model.company_name, 
        "vat_number": user_model.vat_number, "siret_number": user_model.siret_number, 
        "professional_status": user_model.professional_status,
        "created_at": format_datetime_for_display(user_model.created_at),
        "updated_at": format_datetime_for_display(user_model.updated_at),
        "orders": []
    }
    for order_model in user_model.orders.order_by(Order.order_date.desc()).limit(10).all(): # Example: last 10 orders
        user_data['orders'].append({
            "order_id": order_model.id, "order_date": format_datetime_for_display(order_model.order_date),
            "total_amount": order_model.total_amount, "status": order_model.status
        })
    return jsonify(user=user_data, success=True), 200

@admin_api_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user_admin(user_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    data = request.json
    if not data: return jsonify(message="No data provided", success=False), 400

    user = User.query.get(user_id)
    if not user: return jsonify(message="User not found", success=False), 404

    allowed_fields = ['first_name', 'last_name', 'role', 'is_active', 'is_verified', 
                      'company_name', 'vat_number', 'siret_number', 'professional_status']
    updated_fields_log = []

    for field in allowed_fields:
        if field in data:
            if field == 'is_active' or field == 'is_verified':
                setattr(user, field, str(data[field]).lower() == 'true')
            else:
                setattr(user, field, data[field])
            updated_fields_log.append(field)
    
    if not updated_fields_log: return jsonify(message="No valid fields to update", success=False), 400

    try:
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_user_admin_success', target_type='user', target_id=user_id, details=f"User {user_id} updated. Fields: {', '.join(updated_fields_log)}", status='success', ip_address=request.remote_addr)
        return jsonify(message="User updated successfully", success=True), 200
    except Exception as e:
        db.session.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_user_admin_fail', target_type='user', target_id=user_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update user: {str(e)}", success=False), 500

# --- Order Management ---
@admin_api_bp.route('/orders', methods=['GET'])
@admin_required
def get_orders_admin():
    search_filter = request.args.get('search')
    status_filter = request.args.get('status')
    date_filter_str = request.args.get('date')

    query = Order.query.join(User, Order.user_id == User.id)
    if search_filter:
        term_like = f"%{search_filter.lower()}%"
        query = query.filter(
            or_(
                func.cast(Order.id, db.String).like(term_like),
                func.lower(User.email).like(term_like),
                func.lower(User.first_name).like(term_like),
                func.lower(User.last_name).like(term_like),
                Order.payment_transaction_id.like(term_like)
            )
        )
    if status_filter: query = query.filter(Order.status == status_filter)
    if date_filter_str: 
        try:
            filter_date = datetime.strptime(date_filter_str, '%Y-%m-%d').date()
            query = query.filter(func.date(Order.order_date) == filter_date)
        except ValueError: return jsonify(message="Invalid date format. Use YYYY-MM-DD.", success=False), 400
    
    orders_models = query.order_by(Order.order_date.desc()).all()
    orders_data = [{
        "order_id": o.id, "user_id": o.user_id, 
        "order_date": format_datetime_for_display(o.order_date),
        "status": o.status, "total_amount": o.total_amount, "currency": o.currency,
        "customer_email": o.customer.email, 
        "customer_name": f"{o.customer.first_name or ''} {o.customer.last_name or ''}".strip()
    } for o in orders_models]
    return jsonify(orders=orders_data, success=True), 200

@admin_api_bp.route('/orders/<int:order_id>', methods=['GET'])
@admin_required
def get_order_admin_detail(order_id):
    order_model = Order.query.get(order_id)
    if not order_model: return jsonify(message="Order not found", success=False), 404
    
    order_data = {
        "id": order_model.id, "user_id": order_model.user_id, 
        "customer_email": order_model.customer.email,
        "customer_name": f"{order_model.customer.first_name or ''} {order_model.customer.last_name or ''}".strip(),
        "order_date": format_datetime_for_display(order_model.order_date), "status": order_model.status,
        "total_amount": order_model.total_amount, "currency": order_model.currency,
        "shipping_address_line1": order_model.shipping_address_line1, # ... and other address fields ...
        "payment_method": order_model.payment_method, "payment_transaction_id": order_model.payment_transaction_id,
        "notes_internal": order_model.notes_internal, "notes_customer": order_model.notes_customer,
        "tracking_number": order_model.tracking_number, "shipping_method": order_model.shipping_method,
        "items": []
    }
    for item_model in order_model.items:
        item_dict = {
            "id": item_model.id, "product_id": item_model.product_id, "product_name": item_model.product_name,
            "quantity": item_model.quantity, "unit_price": item_model.unit_price,
            "total_price": item_model.total_price, "variant_description": item_model.variant_description,
            "product_image_full_url": None
        }
        if item_model.product and item_model.product.main_image_url:
            try: item_dict['product_image_full_url'] = url_for('serve_public_asset', filepath=item_model.product.main_image_url, _external=True)
            except Exception: pass
        order_data['items'].append(item_dict)
    return jsonify(order=order_data, success=True), 200

@admin_api_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@admin_required
def update_order_status_admin(order_id):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    data = request.json
    new_status = data.get('status'); tracking_number = data.get('tracking_number'); carrier = data.get('carrier')
    
    if not new_status: return jsonify(message="New status not provided", success=False), 400
    # Add more comprehensive list of statuses from your Order model
    allowed_statuses = ['pending_payment', 'paid', 'processing', 'awaiting_shipment', 'shipped', 'delivered', 'completed', 'cancelled', 'refunded', 'on_hold', 'failed']
    if new_status not in allowed_statuses: return jsonify(message=f"Invalid status. Allowed: {', '.join(allowed_statuses)}", success=False), 400

    order = Order.query.get(order_id)
    if not order: return jsonify(message="Order not found", success=False), 404
    
    old_status = order.status
    order.status = new_status
    if new_status in ['shipped', 'delivered']:
        if tracking_number: order.tracking_number = tracking_number
        if carrier: order.shipping_method = carrier # Or a dedicated carrier field
    
    try:
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_order_status_admin_success', target_type='order', target_id=order_id, details=f"Order {order_id} status from '{old_status}' to '{new_status}'. Tracking: {tracking_number or 'N/A'}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Order status updated to {new_status}", success=True), 200
    except Exception as e:
        db.session.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_order_status_admin_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update order status: {str(e)}", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>/notes', methods=['POST'])
@admin_required
def add_order_note_admin(order_id):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    data = request.json; note_content = data.get('note')
    if not note_content or not note_content.strip(): return jsonify(message="Note content cannot be empty.", success=False), 400

    order = Order.query.get(order_id)
    if not order: return jsonify(message="Order not found", success=False), 404
    
    admin_user = User.query.get(current_admin_id)
    admin_id_str = admin_user.email if admin_user else f"AdminID:{current_admin_id}"
    
    new_entry = f"[{format_datetime_for_display(datetime.now(timezone.utc))} by {admin_id_str}]: {note_content}"
    order.notes_internal = f"{order.notes_internal or ''}\n{new_entry}".strip()
    
    try:
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note_admin_success', target_type='order', target_id=order_id, details=f"Added note: '{note_content[:50]}...'", status='success', ip_address=request.remote_addr)
        return jsonify(message="Note added successfully.", new_note_entry=new_entry, success=True), 201
    except Exception as e:
        db.session.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note_admin_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to add note: {str(e)}", success=False), 500

# --- Review Management ---
@admin_api_bp.route('/reviews', methods=['GET'])
@admin_required
def get_reviews_admin():
    status_filter = request.args.get('status') 
    product_filter = request.args.get('product_id') # Can be ID or name/code
    user_filter = request.args.get('user_id') # Can be ID or email

    query = Review.query.join(Product, Review.product_id == Product.id).join(User, Review.user_id == User.id)
    if status_filter == 'pending': query = query.filter(Review.is_approved == False)
    elif status_filter == 'approved': query = query.filter(Review.is_approved == True)
    
    if product_filter:
        if product_filter.isdigit():
            query = query.filter(Review.product_id == int(product_filter))
        else:
            term_like = f"%{product_filter.lower()}%"
            query = query.filter(or_(func.lower(Product.name).like(term_like), func.lower(Product.product_code).like(term_like)))
    if user_filter:
        if user_filter.isdigit():
            query = query.filter(Review.user_id == int(user_filter))
        else:
            query = query.filter(func.lower(User.email).like(f"%{user_filter.lower()}%"))
            
    reviews_models = query.order_by(Review.review_date.desc()).all()
    reviews_data = [{
        "id": r.id, "product_id": r.product_id, "user_id": r.user_id,
        "rating": r.rating, "comment": r.comment, 
        "review_date": format_datetime_for_display(r.review_date),
        "is_approved": r.is_approved,
        "product_name": r.product.name, "product_code": r.product.product_code,
        "user_email": r.user.email
    } for r in reviews_models]
    return jsonify(reviews=reviews_data, success=True), 200

def _update_review_approval_admin(review_id, is_approved_status):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    action = "approve" if is_approved_status else "unapprove"
    review = Review.query.get(review_id)
    if not review: return jsonify(message="Review not found", success=False), 404
    
    review.is_approved = is_approved_status
    try:
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action=f'{action}_review_admin_success', target_type='review', target_id=review_id, details=f"Review {review_id} set to {is_approved_status}.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Review {'approved' if is_approved_status else 'unapproved'} successfully", success=True), 200
    except Exception as e:
        db.session.rollback()
        audit_logger.log_action(user_id=current_admin_id, action=f'{action}_review_admin_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to {action} review: {str(e)}", success=False), 500

@admin_api_bp.route('/reviews/<int:review_id>/approve', methods=['PUT'])
@admin_required
def approve_review_admin(review_id): return _update_review_approval_admin(review_id, True)

@admin_api_bp.route('/reviews/<int:review_id>/unapprove', methods=['PUT'])
@admin_required
def unapprove_review_admin(review_id): return _update_review_approval_admin(review_id, False)

@admin_api_bp.route('/reviews/<int:review_id>', methods=['DELETE'])
@admin_required
def delete_review_admin(review_id):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    review = Review.query.get(review_id)
    if not review: return jsonify(message="Review not found", success=False), 404
    try:
        db.session.delete(review)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin_success', target_type='review', target_id=review_id, details=f"Review {review_id} deleted.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Review deleted successfully", success=True), 200
    except Exception as e:
        db.session.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to delete review: {str(e)}", success=False), 500

# --- Settings Management ---
@admin_api_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings_admin():
    settings_models = Setting.query.all()
    settings_data = {s.key: {'value': s.value, 'description': s.description} for s in settings_models}
    return jsonify(settings=settings_data, success=True), 200

@admin_api_bp.route('/settings', methods=['POST']) # Using POST for create/update simplicity
@admin_required
def update_settings_admin():
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    data = request.json
    if not data: return jsonify(message="No settings data provided", success=False), 400
    updated_keys = []
    try:
        for key, value_obj in data.items():
            value = value_obj.get('value') if isinstance(value_obj, dict) else value_obj
            if value is not None:
                setting = Setting.query.get(key)
                if setting: setting.value = str(value)
                else: db.session.add(Setting(key=key, value=str(value)))
                updated_keys.append(key)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin_success', target_type='application_settings', details=f"Settings updated: {', '.join(updated_keys)}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Settings updated successfully", updated_settings=updated_keys, success=True), 200
    except Exception as e:
        db.session.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update settings: {str(e)}", success=False), 500

# --- Detailed Inventory View ---
@admin_api_bp.route('/inventory/items/detailed', methods=['GET'])
@admin_required
def get_detailed_inventory_items_admin():
    try:
        # Joining with Product and ProductWeightOption to get names
        query = db.session.query(
            SerializedInventoryItem, 
            Product.name.label('product_name'), 
            Product.product_code,
            func.coalesce(ProductLocalization.name_fr, Product.name).label('product_name_fr'), # Example localization
            func.coalesce(ProductLocalization.name_en, Product.name).label('product_name_en'), # Example localization
            ProductWeightOption.weight_grams.label('variant_weight_grams'),
            ProductWeightOption.sku_suffix.label('variant_sku_suffix')
        ).join(Product, SerializedInventoryItem.product_id == Product.id)\
         .outerjoin(ProductWeightOption, SerializedInventoryItem.variant_id == ProductWeightOption.id)\
         .outerjoin(ProductLocalization, and_(Product.id == ProductLocalization.product_id, ProductLocalization.lang_code == 'fr')) # Example localization join
        
        items_data_tuples = query.order_by(Product.name, SerializedInventoryItem.item_uid).all()
        
        detailed_items = []
        for item_tuple in items_data_tuples:
            item = item_tuple.SerializedInventoryItem # The main model instance
            item_dict = {
                "item_uid": item.item_uid, "product_id": item.product_id, "variant_id": item.variant_id,
                "batch_number": item.batch_number, 
                "production_date": format_datetime_for_storage(item.production_date) if item.production_date else None,
                "expiry_date": format_datetime_for_storage(item.expiry_date) if item.expiry_date else None,
                "cost_price": item.cost_price, "status": item.status, "notes": item.notes,
                "qr_code_url": item.qr_code_url, "passport_url": item.passport_url, "label_url": item.label_url,
                "actual_weight_grams": item.actual_weight_grams,
                "received_at": format_datetime_for_storage(item.received_at) if item.received_at else None,
                "sold_at": format_datetime_for_storage(item.sold_at) if item.sold_at else None,
                "updated_at": format_datetime_for_storage(item.updated_at) if item.updated_at else None,
                # Add joined fields
                "product_name": item_tuple.product_name,
                "product_name_fr": item_tuple.product_name_fr,
                "product_name_en": item_tuple.product_name_en,
                "product_code": item_tuple.product_code,
                "variant_name": f"{item_tuple.product_name} - {item_tuple.variant_weight_grams}g ({item_tuple.variant_sku_suffix})" if item_tuple.variant_sku_suffix else None,
                "qr_code_full_url": None, "passport_full_url": None, "label_full_url": None
            }
            if item.qr_code_url: item_dict['qr_code_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item.qr_code_url, _external=True)
            if item.passport_url: item_dict['passport_full_url'] = url_for('serve_public_asset', filepath=item.passport_url, _external=True) # Assuming passports are public
            if item.label_url: item_dict['label_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item.label_url, _external=True)
            detailed_items.append(item_dict)
            
        return jsonify(detailed_items=detailed_items, success=True), 200 # Return as object with 'detailed_items' key
    except Exception as e:
        current_app.logger.error(f"Error fetching detailed inventory items for admin: {e}", exc_info=True)
        return jsonify(message="Failed to fetch detailed inventory", detailed_items=[], success=False), 500 # Return empty array with success=False

# --- Admin Asset Serving (for protected assets like QR codes, labels, invoices) ---
@admin_api_bp.route('/assets/<path:asset_relative_path>')
@admin_required 
def serve_asset(asset_relative_path):
    # This function was already quite robust. Added products and categories to the map as they might be stored in UPLOAD_FOLDER
    # and an admin might want to access them via a protected route for some reason (though usually they'd be public).
    if ".." in asset_relative_path or asset_relative_path.startswith("/"):
        current_app.logger.warning(f"Directory traversal attempt for admin asset: {asset_relative_path}")
        return flask_abort(404)

    asset_type_map = {
        'qr_codes': current_app.config['QR_CODE_FOLDER'],
        'labels': current_app.config['LABEL_FOLDER'],
        'invoices': current_app.config['INVOICE_PDF_PATH'],
        'professional_documents': current_app.config['PROFESSIONAL_DOCS_UPLOAD_PATH'],
        'products': os.path.join(current_app.config['UPLOAD_FOLDER'], 'products'),      # If admin needs direct access
        'categories': os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories') # If admin needs direct access
    }
    
    path_parts = asset_relative_path.split(os.sep, 1)
    asset_type_key = path_parts[0]
    filename_in_type_folder = path_parts[1] if len(path_parts) > 1 else None

    if asset_type_key in asset_type_map and filename_in_type_folder:
        base_path = asset_type_map[asset_type_key]
        full_path = os.path.normpath(os.path.join(base_path, filename_in_type_folder))
        
        if not os.path.realpath(full_path).startswith(os.path.realpath(base_path)):
            current_app.logger.error(f"Security violation: Attempt to access file outside designated admin asset directory. Requested: {full_path}, Base: {base_path}")
            return flask_abort(404)

        if os.path.exists(full_path) and os.path.isfile(full_path):
            current_app.logger.debug(f"Serving admin asset: {filename_in_type_folder} from directory: {base_path}")
            return send_from_directory(base_path, filename_in_type_folder)
    
    current_app.logger.warning(f"Admin asset not found or path not recognized: {asset_relative_path}")
    return flask_abort(404)


# --- Regenerate Static JSON Files ---
@admin_api_bp.route('/regenerate-static-json', methods=['POST'])
@admin_required
def regenerate_static_json_endpoint():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        # generate_static_json_files function (in utils.py) needs to be fully SQLAlchemy aware.
        # This means it should query data using db.session and SQLAlchemy models.
        generate_static_json_files() 
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json_success', status='success', ip_address=request.remote_addr)
        return jsonify(message="Static JSON files regenerated successfully.", success=True), 200
    except Exception as e:
        current_app.logger.error(f"Failed to regenerate static JSON files via API: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to regenerate static JSON files: {str(e)}", success=False), 500

@admin_api_bp.route('/users/professionals', methods=['GET'])
@staff_or_admin_required 
def get_professional_users_list(): # Already existed and seems fine with SQLAlchemy
    try:
        professionals = User.query.filter_by(role='b2b_professional')\
                                  .order_by(User.company_name, User.last_name, User.first_name).all()
        professionals_data = [{
            "id": user.id, "email": user.email, "first_name": user.first_name,
            "last_name": user.last_name, "company_name": user.company_name,
            "professional_status": user.professional_status # Keep status for admin view
        } for user in professionals]
        return jsonify(professionals=professionals_data, success=True), 200 # Ensure consistent response structure
    except Exception as e:
        current_app.logger.error(f"Error fetching professional users for admin: {e}", exc_info=True)
        return jsonify(message="Failed to fetch professional users.", success=False), 500

@admin_api_bp.route('/invoices/create', methods=['POST'])
@admin_required
def admin_create_manual_invoice():
    data = request.json
    b2b_user_id = data.get('b2b_user_id')
    line_items_data = data.get('line_items') # Expects list of dicts with description, quantity, unit_price
    notes = data.get('notes')
    currency = data.get('currency', 'EUR') # Default currency if not provided

    if not b2b_user_id or not line_items_data or not isinstance(line_items_data, list) or len(line_items_data) == 0:
        return jsonify(message="Missing required fields: b2b_user_id and at least one line_item.", success=False), 400

    audit_logger = current_app.audit_log_service
    current_admin_id = get_jwt_identity()

    try:
        invoice_service = InvoiceService() # Assumes InvoiceService is adapted for SQLAlchemy
        invoice_id, invoice_number = invoice_service.create_manual_invoice(
            b2b_user_id=b2b_user_id, 
            user_currency=currency, 
            line_items_data=line_items_data, 
            notes=notes,
            issued_by_admin_id=current_admin_id # Optional: record who created it
        )
        
        pdf_full_url = None
        if invoice_id:
            invoice = Invoice.query.get(invoice_id)
            if invoice and invoice.pdf_path:
                 # Assuming pdf_path stored in Invoice model is relative to ASSET_STORAGE_PATH/invoices
                 # and serve_asset can resolve 'invoices/filename.pdf'
                 pdf_relative_to_asset_serve = os.path.join('invoices', os.path.basename(invoice.pdf_path))
                 pdf_full_url = url_for('admin_api_bp.serve_asset', asset_relative_path=pdf_relative_to_asset_serve, _external=True)

        audit_logger.log_action(user_id=current_admin_id, action='admin_create_manual_invoice_success', target_type='invoice', target_id=invoice_id, details=f"Manual invoice {invoice_number} created for user {b2b_user_id}.", status='success', ip_address=request.remote_addr)
        return jsonify(success=True, message="Manual invoice created successfully.", invoice_id=invoice_id, invoice_number=invoice_number, pdf_url=pdf_full_url), 201
    except ValueError as ve: 
        audit_logger.log_action(user_id=current_admin_id, action='admin_create_manual_invoice_fail_validation', details=str(ve), status='failure', ip_address=request.remote_addr)
        return jsonify(message=str(ve), success=False), 400 
    except Exception as e:
        current_app.logger.error(f"Admin API error creating manual invoice: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='admin_create_manual_invoice_fail_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"An internal error occurred: {str(e)}", success=False), 500
