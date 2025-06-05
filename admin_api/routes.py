# backend/b2b/routes.py
from flask import Blueprint, request, jsonify, current_app, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
import uuid
import json # For parsing cart_items from form data

from .. import db
from ..models import (User, Product, Category, ProductWeightOption, ProductB2BTierPrice,
                    Order, OrderItem, QuoteRequest, QuoteRequestItem, GeneratedAsset,
                    UserRoleEnum, ProfessionalStatusEnum, B2BPricingTierEnum,
                    OrderStatusEnum, QuoteRequestStatusEnum, AssetTypeEnum, ProductTypeEnum) # Added ProductTypeEnum
from ..utils import allowed_file, get_file_extension, sanitize_input # Add other utils as needed
from ..services.email_service import EmailService # Assuming you have an email service

b2b_bp = Blueprint('b2b_bp', __name__, url_prefix='/api/b2b')

@b2b_bp.route('/products', methods=['GET'])
@jwt_required()
def get_b2b_products():
    """
    Fetches products with B2B tiered pricing for the authenticated professional user.
    """
    current_user_id = get_jwt_identity()
    b2b_user = User.query.get(current_user_id)
    audit_logger = current_app.audit_log_service # Get audit logger

    if not b2b_user or b2b_user.role != UserRoleEnum.B2B_PROFESSIONAL or b2b_user.professional_status != ProfessionalStatusEnum.APPROVED:
        audit_logger.log_action(user_id=current_user_id, action='get_b2b_products_fail_auth', details="B2B Professional account approved required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Access denied. Approved B2B professional account required.", success=False), 403

    user_tier = b2b_user.b2b_tier

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    category_slug_filter = request.args.get('category_slug')
    search_term_filter = request.args.get('search')
    sort_by_filter = request.args.get('sort', 'name_asc')


    query = Product.query.join(Category, Product.category_id == Category.id)\
                         .filter(Product.is_active == True, Category.is_active == True)


    if category_slug_filter:
        query = query.filter(Category.slug == category_slug_filter)
    if search_term_filter:
        term_like = f"%{search_term_filter.lower()}%"
        query = query.filter(Product.name.ilike(term_like)) # Simplified search on product name

    # Sorting logic (add more options as needed)
    if sort_by_filter == 'price_asc':
        # Sorting by price for B2B is complex due to tiers.
        # This might require a more complex query or sorting after fetching if performance allows.
        # For simplicity, let's sort by base_price for now, assuming tier prices follow a similar trend.
        query = query.order_by(Product.base_price.asc())
    elif sort_by_filter == 'price_desc':
        query = query.order_by(Product.base_price.desc())
    elif sort_by_filter == 'name_desc':
        query = query.order_by(Product.name.desc())
    else: # default name_asc
        query = query.order_by(Product.name.asc())


    paginated_products = query.paginate(page=page, per_page=per_page, error_out=False)
    products_data = []

    for product in paginated_products.items:
        # Determine B2B price for the main product (if simple) or as a "starting from" price
        b2b_price_display = product.base_price # Default to B2C retail / base price

        if product.type == ProductTypeEnum.SIMPLE:
            tier_price_entry = ProductB2BTierPrice.query.filter_by(
                product_id=product.id,
                variant_id=None,
                b2b_tier=user_tier
            ).first()
            if tier_price_entry:
                b2b_price_display = tier_price_entry.price
        
        product_dict = product.to_dict() # Use your existing to_dict which should be mostly B2C info
        product_dict['b2b_price'] = b2b_price_display # This is the price specific to this B2B user's tier
        product_dict['retail_price'] = product.base_price # RRP for comparison

        if product.type == ProductTypeEnum.VARIABLE_WEIGHT:
            options_list_b2b = []
            active_options = product.weight_options.filter_by(is_active=True).order_by(ProductWeightOption.weight_grams).all()
            
            min_b2b_variant_price = float('inf')

            for option in active_options:
                option_b2b_price = option.price # Default to variant's B2C retail price
                option_tier_price_entry = ProductB2BTierPrice.query.filter_by(
                    variant_id=option.id, # Tier pricing is per variant
                    b2b_tier=user_tier
                ).first()
                if option_tier_price_entry:
                    option_b2b_price = option_tier_price_entry.price
                
                if option_b2b_price < min_b2b_variant_price:
                    min_b2b_variant_price = option_b2b_price

                options_list_b2b.append({
                    "option_id": option.id,
                    "weight_grams": option.weight_grams,
                    "sku_suffix": option.sku_suffix,
                    "b2b_price": option_b2b_price, # Tiered price for this variant
                    "retail_price": option.price,    # B2C retail price for this variant
                    "aggregate_stock_quantity": option.aggregate_stock_quantity # Current stock
                })
            product_dict['weight_options_b2b'] = options_list_b2b
            if min_b2b_variant_price != float('inf'):
                product_dict['b2b_price'] = min_b2b_variant_price # "Starting from" B2B price for variable products

        products_data.append(product_dict)
    
    audit_logger.log_action(user_id=current_user_id, action='get_b2b_products_success', status='success', ip_address=request.remote_addr)
    return jsonify({
        "products": products_data,
        "page": paginated_products.page,
        "per_page": paginated_products.per_page,
        "total_products": paginated_products.total,
        "total_pages": paginated_products.pages,
        "success": True
    }), 200


@b2b_bp.route('/quote-requests', methods=['POST'])
@jwt_required()
def create_quote_request():
    current_user_id = get_jwt_identity()
    b2b_user = User.query.get(current_user_id)
    audit_logger = current_app.audit_log_service

    if not b2b_user or b2b_user.role != UserRoleEnum.B2B_PROFESSIONAL:
        audit_logger.log_action(user_id=current_user_id, action='create_quote_fail_auth', details="B2B Professional account required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="B2B professional account required.", success=False), 403

    data = request.json
    items_data = data.get('items')
    notes = sanitize_input(data.get('notes'))
    contact_person = sanitize_input(data.get('contact_person', f"{b2b_user.first_name or ''} {b2b_user.last_name or ''}".strip()))
    contact_phone = sanitize_input(data.get('contact_phone'))

    if not items_data or not isinstance(items_data, list) or len(items_data) == 0:
        audit_logger.log_action(user_id=current_user_id, action='create_quote_fail_validation', details="Empty item list for quote.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="At least one item is required for a quote request.", success=False), 400

    try:
        new_quote = QuoteRequest(
            user_id=current_user_id,
            notes=notes,
            contact_person=contact_person,
            contact_phone=contact_phone,
            status=QuoteRequestStatusEnum.PENDING
        )
        db.session.add(new_quote)
        db.session.flush() # To get new_quote.id

        for item_data in items_data:
            product_id = item_data.get('product_id')
            variant_id = item_data.get('variant_id')
            quantity = item_data.get('quantity')
            price_at_request = item_data.get('price_at_request') # This is the B2B price shown to user

            if not product_id or not quantity or price_at_request is None:
                 audit_logger.log_action(user_id=current_user_id, action='create_quote_fail_item_validation', details=f"Invalid item data: {item_data}", status='failure', ip_address=request.remote_addr)
                 db.session.rollback()
                 return jsonify(message=f"Invalid data for item {product_id}.", success=False), 400
            
            # Basic validation: Does product exist?
            product = Product.query.get(product_id)
            if not product:
                db.session.rollback()
                return jsonify(message=f"Product ID {product_id} not found.", success=False), 404

            quote_item = QuoteRequestItem(
                quote_request_id=new_quote.id,
                product_id=product_id,
                variant_id=variant_id,
                quantity=int(quantity),
                requested_price_ht=float(price_at_request)
            )
            db.session.add(quote_item)
        
        db.session.commit()
        
        # Notify Admin
        email_service = EmailService(current_app)
        admin_email = current_app.config.get('ADMIN_EMAIL', 'admin@example.com')
        subject = f"Nouvelle Demande de Devis B2B #{new_quote.id} de {b2b_user.company_name or b2b_user.email}"
        body = f"""
        Une nouvelle demande de devis a été soumise :
        ID Devis: {new_quote.id}
        Client: {b2b_user.company_name or b2b_user.email} (ID: {current_user_id})
        Contact: {contact_person} {f'({contact_phone})' if contact_phone else ''}
        Notes: {notes or 'Aucune'}
        Consultez le panneau d'administration pour plus de détails.
        """
        email_service.send_email(admin_email, subject, body)
        current_app.logger.info(f"Admin notification sent for new B2B Quote Request {new_quote.id}.")
        audit_logger.log_action(user_id=current_user_id, action='create_quote_success', target_type='quote_request', target_id=new_quote.id, status='success', ip_address=request.remote_addr)
        
        return jsonify(message="Quote request submitted successfully.", quote_id=new_quote.id, success=True), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating quote request for user {current_user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='create_quote_fail_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to submit quote request due to a server error.", error=str(e), success=False), 500


@b2b_bp.route('/purchase-orders', methods=['POST'])
@jwt_required()
def upload_purchase_order():
    current_user_id = get_jwt_identity()
    b2b_user = User.query.get(current_user_id)
    audit_logger = current_app.audit_log_service

    if not b2b_user or b2b_user.role != UserRoleEnum.B2B_PROFESSIONAL:
        audit_logger.log_action(user_id=current_user_id, action='upload_po_fail_auth', details="B2B Professional account required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="B2B professional account required.", success=False), 403

    if 'purchase_order_file' not in request.files:
        return jsonify(message="No purchase order file provided.", success=False), 400
    
    po_file = request.files['purchase_order_file']
    cart_items_json = request.form.get('cart_items')

    if po_file.filename == '':
        return jsonify(message="No selected file for purchase order.", success=False), 400
    if not cart_items_json:
        return jsonify(message="Cart items data is required with PO submission.", success=False), 400

    try:
        cart_items = json.loads(cart_items_json)
        if not isinstance(cart_items, list) or len(cart_items) == 0:
            raise ValueError("Invalid cart items format or empty cart for PO.")
    except (json.JSONDecodeError, ValueError) as e:
        audit_logger.log_action(user_id=current_user_id, action='upload_po_fail_cart_format', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Invalid cart items data: {str(e)}", success=False), 400

    # Securely save the PO file
    upload_folder_pos = current_app.config['PROFESSIONAL_DOCS_UPLOAD_PATH'] # Or a dedicated PO folder
    os.makedirs(upload_folder_pos, exist_ok=True)

    if po_file and allowed_file(po_file.filename, 'ALLOWED_DOCUMENT_EXTENSIONS'):
        filename_base = secure_filename(f"user_{current_user_id}_po_{uuid.uuid4().hex[:8]}")
        extension = get_file_extension(po_file.filename)
        filename = f"{filename_base}.{extension}"
        file_path_full = os.path.join(upload_folder_pos, filename)
        # Storing path relative to a base asset/upload directory
        file_path_relative_for_db = os.path.join('professional_documents', filename) # Adjust subfolder if needed

        try:
            po_file.save(file_path_full)

            # Create an Order with status PENDING_PO_REVIEW
            calculated_total = 0
            order_items_to_create = []
            customer_shipping_address = { # Fetch from b2b_user profile or allow override
                'line1': b2b_user.shipping_address_line1 or b2b_user.company_address_line1 or 'N/A',
                'city': b2b_user.shipping_city or b2b_user.company_city or 'N/A',
                'postal_code': b2b_user.shipping_postal_code or b2b_user.company_postal_code or 'N/A',
                'country': b2b_user.shipping_country or b2b_user.company_country or 'N/A',
            }

            for item_data in cart_items:
                product_id = item_data.get('product_id')
                variant_id = item_data.get('variant_id')
                quantity = item_data.get('quantity')
                price_at_request = item_data.get('price_at_request')

                if not product_id or not quantity or price_at_request is None:
                    if os.path.exists(file_path_full): os.remove(file_path_full)
                    audit_logger.

# --- Helper: Update or Create Product Localization ---
def _update_or_create_product_localization(product_id, lang_code, data_dict):
    loc = ProductLocalization.query.filter_by(product_id=product_id, lang_code=lang_code).first()
    if not loc:
        loc = ProductLocalization(product_id=product_id, lang_code=lang_code)
        db.session.add(loc)
    
    if lang_code == 'fr':
        loc.name_fr = data_dict.get('name', getattr(loc, 'name_fr', None)) 
        loc.description_fr = data_dict.get('description', getattr(loc, 'description_fr', None))
        loc.long_description_fr = data_dict.get('long_description', getattr(loc, 'long_description_fr', None))
        loc.sensory_evaluation_fr = data_dict.get('sensory_evaluation', getattr(loc, 'sensory_evaluation_fr', None))
        loc.food_pairings_fr = data_dict.get('food_pairings', getattr(loc, 'food_pairings_fr', None))
        loc.species_fr = data_dict.get('species', getattr(loc, 'species_fr', None))
        loc.meta_title_fr = data_dict.get('meta_title', getattr(loc, 'meta_title_fr', None)) 
        loc.meta_description_fr = data_dict.get('meta_description', getattr(loc, 'meta_description_fr', None))
        loc.ideal_uses_fr = data_dict.get('ideal_uses', getattr(loc, 'ideal_uses_fr', None)) # Added
        loc.pairing_suggestions_fr = data_dict.get('pairing_suggestions', getattr(loc, 'pairing_suggestions_fr', None)) # Added
    elif lang_code == 'en':
        loc.name_en = data_dict.get('name_en', getattr(loc, 'name_en', None))
        loc.description_en = data_dict.get('description_en', getattr(loc, 'description_en', None))
        loc.long_description_en = data_dict.get('long_description_en', getattr(loc, 'long_description_en', None))
        loc.sensory_evaluation_en = data_dict.get('sensory_evaluation_en', getattr(loc, 'sensory_evaluation_en', None))
        loc.food_pairings_en = data_dict.get('food_pairings_en', getattr(loc, 'food_pairings_en', None))
        loc.species_en = data_dict.get('species_en', getattr(loc, 'species_en', None))
        loc.meta_title_en = data_dict.get('meta_title_en', getattr(loc, 'meta_title_en', None))
        loc.meta_description_en = data_dict.get('meta_description_en', getattr(loc, 'meta_description_en', None))
        loc.ideal_uses_en = data_dict.get('ideal_uses_en', getattr(loc, 'ideal_uses_en', None)) # Added
        loc.pairing_suggestions_en = data_dict.get('pairing_suggestions_en', getattr(loc, 'pairing_suggestions_en', None)) # Added
    return loc

# --- JWT Blocklist Loader ---
@jwt.token_in_blocklist_loader
def check_if_token_in_blocklist(jwt_header, jwt_payload: dict) -> bool:
    jti = jwt_payload["jti"]
    token = db.session.query(TokenBlocklist.id).filter_by(jti=jti).scalar()
    return token is not None

# --- Admin Authentication ---
def _create_admin_session_and_get_response(admin_user, redirect_url=None):
    identity = admin_user.id
    additional_claims = {
        "role": admin_user.role.value, "email": admin_user.email, "is_admin": True,
        "first_name": admin_user.first_name, "last_name": admin_user.last_name
    }
    access_token = create_access_token(identity=identity, additional_claims=additional_claims)
    
    if redirect_url: 
        response = redirect(redirect_url)
        if 'cookies' in current_app.config.get('JWT_TOKEN_LOCATION', ['headers']):
            set_access_cookies(response, access_token) 
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
        # Log error but proceed with logout on client-side
    
    response = jsonify(success=True, message="Admin logout successful. Token invalidated.")
    unset_jwt_cookies(response) # Clear JWT cookies if used
    return response, 200


@admin_api_bp.route('/login', methods=['POST'])
@limiter.limit(lambda: current_app.config.get('ADMIN_LOGIN_RATELIMITS', "10 per 5 minutes")[0]) # Apply specific rate limit
def admin_login_step1_password():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    audit_logger = current_app.audit_log_service
    if not email or not password:
        audit_logger.log_action(action='admin_login_fail_step1', email=email, details="Email and password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email and password are required", success=False, totp_required=False), 400
    try:
        admin_user = User.query.filter(func.lower(User.email) == email.lower(), User.role == UserRoleEnum.ADMIN).first() # Case-insensitive email
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
        audit_logger.log_action(action='admin_login_fail_server_error_step1', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Admin login failed due to a server error.", success=False, totp_required=False), 500



@admin_api_bp.route('/login/verify-totp', methods=['POST'])
@limiter.limit(lambda: current_app.config.get('ADMIN_LOGIN_RATELIMITS', "10 per 5 minutes"))
def admin_login_step2_verify_totp():
    data = request.json; totp_code = data.get('totp_code')
    pending_admin_id = session.get('pending_totp_admin_id')
    if not pending_admin_id: # ... (return 400) ...
        return jsonify(message="Login session expired or invalid. Please start over.", success=False), 400
    if not totp_code: # ... (return 400) ...
        return jsonify(message="TOTP code is required.", success=False), 400
    try:
        admin_user = User.query.get(pending_admin_id)
        if not admin_user or not admin_user.is_active or admin_user.role != UserRoleEnum.ADMIN: # ... (return 403) ...
            return jsonify(message="Invalid user state for TOTP verification. Please log in again.", success=False), 403
        if admin_user.verify_totp(totp_code): # ... (TOTP success) ...
            session.pop('pending_totp_admin_id', None); session.pop('pending_totp_admin_email', None)
            return _create_admin_session_and_get_response(admin_user)
        else: # ... (TOTP fail) ...
            return jsonify(message="Invalid TOTP code. Please try again.", success=False), 401
    except Exception as e: # ... (return 500) ...
        return jsonify(message="TOTP verification failed due to a server error. Please try again.", success=False), 500

@admin_api_bp.route('/login/simplelogin/initiate', methods=['GET'])
def simplelogin_initiate(): # ... (same as before) ...
    client_id = current_app.config.get('SIMPLELOGIN_CLIENT_ID') # ...
    return redirect(f"{current_app.config.get('SIMPLELOGIN_AUTHORIZE_URL')}?{urlencode(params)}")

@admin_api_bp.route('/login/simplelogin/callback', methods=['GET'])
def simplelogin_callback():
    auth_code = request.args.get('code')
    state_returned = request.args.get('state')
    audit_logger = current_app.audit_log_service
    base_admin_login_url = current_app.config.get('APP_BASE_URL', 'http://localhost:8000') + '/admin/admin_login.html'
    admin_dashboard_url = current_app.config.get('APP_BASE_URL', 'http://localhost:8000') + '/admin/admin_dashboard.html'

    expected_state = session.pop('oauth_state_sl', None)
    if not expected_state or expected_state != state_returned:
        audit_logger.log_action(action='simplelogin_callback_fail_state_mismatch', details="OAuth state mismatch.", status='failure', ip_address=request.remote_addr)
        return redirect(f"{base_admin_login_url}?error=sso_state_mismatch")

    if not auth_code:
        audit_logger.log_action(action='simplelogin_callback_fail_no_code', details="No authorization code received from SimpleLogin.", status='failure', ip_address=request.remote_addr)
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
        token_response = requests.post(token_url, data=payload)
        token_response.raise_for_status() 
        token_data = token_response.json()
        sl_access_token = token_data.get('access_token')

        if not sl_access_token:
            audit_logger.log_action(action='simplelogin_callback_fail_no_access_token', details="No access token from SimpleLogin.", status='failure', ip_address=request.remote_addr)
            return redirect(f"{base_admin_login_url}?error=sso_token_error")

        userinfo_url = current_app.config['SIMPLELOGIN_USERINFO_URL']
        headers = {'Authorization': f'Bearer {sl_access_token}'}
        userinfo_response = requests.get(userinfo_url, headers=headers)
        userinfo_response.raise_for_status()
        sl_user_info = userinfo_response.json()
        
        sl_email = sl_user_info.get('email')
        sl_simplelogin_user_id = sl_user_info.get('sub') 

        if not sl_email:
            audit_logger.log_action(action='simplelogin_callback_fail_no_email', details="No email in userinfo from SimpleLogin.", status='failure', ip_address=request.remote_addr)
            return redirect(f"{base_admin_login_url}?error=sso_email_error")

        # --- EMAIL FILTER ---
        allowed_admin_email = "remy.roche@pm.me"
        if sl_email.lower() != allowed_admin_email.lower():
            audit_logger.log_action(action='simplelogin_callback_fail_email_not_allowed', email=sl_email, details=f"SSO attempt from non-allowed email: {sl_email}", status='failure', ip_address=request.remote_addr)
            current_app.logger.warning(f"SimpleLogin attempt from non-allowed email: {sl_email}")
            return redirect(f"{base_admin_login_url}?error=sso_unauthorized_email")
        # --- END OF EMAIL FILTER ---

        admin_user = User.query.filter(func.lower(User.email) == sl_email.lower(), User.role == 'admin').first()

        if admin_user and admin_user.is_active:
            if not admin_user.simplelogin_user_id and sl_simplelogin_user_id:
                admin_user.simplelogin_user_id = sl_simplelogin_user_id
                db.session.commit()
            
            audit_logger.log_action(user_id=admin_user.id, action='admin_login_success_simplelogin', target_type='user_admin', target_id=admin_user.id, details=f"Admin {sl_email} logged in via SimpleLogin.", status='success', ip_address=request.remote_addr)
            
            return _create_admin_session_and_get_response(admin_user, admin_dashboard_url)

        elif admin_user and not admin_user.is_active:
            audit_logger.log_action(action='simplelogin_callback_fail_user_inactive', email=sl_email, details="Admin account found but is inactive.", status='failure', ip_address=request.remote_addr)
            return redirect(f"{base_admin_login_url}?error=sso_account_inactive")
        else: 
            audit_logger.log_action(action='simplelogin_callback_fail_user_not_admin', email=sl_email, details="User authenticated via SimpleLogin but not a registered/active admin in local DB.", status='failure', ip_address=request.remote_addr)
            return redirect(f"{base_admin_login_url}?error=sso_admin_not_found")

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"SimpleLogin OAuth request failed: {e}", exc_info=True)
        audit_logger.log_action(action='simplelogin_callback_fail_request_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        return redirect(f"{base_admin_login_url}?error=sso_communication_error")
    except Exception as e:
        current_app.logger.error(f"Error during SimpleLogin callback: {e}", exc_info=True)
        audit_logger.log_action(action='simplelogin_callback_fail_server_error', details=str(e), status='failure', ip_address=request.remote_addr)
        return redirect(f"{base_admin_login_url}?error=sso_server_error")
        

        # --- ADDED EMAIL FILTER ---
        allowed_admin_email = "remy.roche@pm.me"
        if sl_email.lower() != allowed_admin_email.lower():
            audit_logger.log_action(action='simplelogin_callback_fail_email_not_allowed', email=sl_email, details=f"SSO attempt from non-allowed email: {sl_email}", status='failure', ip_address=request.remote_addr)
            current_app.logger.warning(f"SimpleLogin attempt from non-allowed email: {sl_email}")
            return redirect(f"{base_admin_login_url}?error=sso_unauthorized_email")
        # --- END OF EMAIL FILTER ---

        admin_user = User.query.filter(func.lower(User.email) == sl_email.lower(), User.role == 'admin').first()

        if admin_user and admin_user.is_active:
            if not admin_user.simplelogin_user_id and sl_simplelogin_user_id:
                admin_user.simplelogin_user_id = sl_simplelogin_user_id
                db.session.commit()
            
            audit_logger.log_action(user_id=admin_user.id, action='admin_login_success_simplelogin', target_type='user_admin', target_id=admin_user.id, details=f"Admin {sl_email} logged in via SimpleLogin.", status='success', ip_address=request.remote_addr)
            
            # Use the helper to create session and get redirect response with cookies
            return _create_admin_session_and_get_response(admin_user, admin_dashboard_url)

        elif admin_user and not admin_user.is_active:
            audit_logger.log_action(action='simplelogin_callback_fail_user_inactive', email=sl_email, details="Admin account found but is inactive.", status='failure', ip_address=request.remote_addr)
            return redirect(f"{base_admin_login_url}?error=sso_account_inactive")
        else: # User with this email is not an admin or doesn't exist in local DB
            audit_logger.log_action(action='simplelogin_callback_fail_user_not_admin', email=sl_email, details="User authenticated via SimpleLogin but not a registered/active admin in local DB.", status='failure', ip_address=request.remote_addr)
            return redirect(f"{base_admin_login_url}?error=sso_admin_not_found")

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"SimpleLogin OAuth request failed: {e}", exc_info=True)
        audit_logger.log_action(action='simplelogin_callback_fail_request_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        return redirect(f"{base_admin_login_url}?error=sso_communication_error")
    except Exception as e:
        current_app.logger.error(f"Error during SimpleLogin callback: {e}", exc_info=True)
        audit_logger.log_action(action='simplelogin_callback_fail_server_error', details=str(e), status='failure', ip_address=request.remote_addr)
        return redirect(f"{base_admin_login_url}?error=sso_server_error")


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change_this_default_secret_key_in_prod_sqlalchemy')
    DEBUG = False
    TESTING = False
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:8000') # Used for frontend redirects

    # SQLAlchemy Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'maison_truvra_orm.sqlite3')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # JWT Extended Settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'change_this_default_jwt_secret_key_in_prod_sqlalchemy')
    JWT_TOKEN_LOCATION = ['headers', 'cookies']
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_COOKIE_SECURE = False 
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_REFRESH_COOKIE_PATH = '/api/auth/refresh' 
    JWT_ACCESS_COOKIE_PATH = '/api/' 
    JWT_COOKIE_CSRF_PROTECT = True 
    JWT_CSRF_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
    JWT_CSRF_IN_COOKIES = True 

    # File Uploads / Asset Storage
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'uploads'))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    ASSET_STORAGE_PATH = os.environ.get('ASSET_STORAGE_PATH', os.path.join(UPLOAD_FOLDER, 'generated_assets'))
    QR_CODE_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'qr_codes')
    PASSPORT_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'passports')
    LABEL_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'labels')
    DEFAULT_FONT_PATH = os.environ.get('DEFAULT_FONT_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'fonts', 'DejaVuSans.ttf')) 
    MAISON_TRUVRA_LOGO_PATH_LABEL = os.environ.get('MAISON_TRUVRA_LOGO_PATH_LABEL', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'logos', 'maison_truvra_label_logo.png')) 
    MAISON_TRUVRA_LOGO_PATH_PASSPORT = os.environ.get('MAISON_TRUVRA_LOGO_PATH_PASSPORT', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'logos', 'maison_truvra_passport_logo.png'))

    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 't')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')

    # Stripe Configuration
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_FILE = os.environ.get('LOG_FILE', None)

    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', "http://localhost:8000,http://127.0.0.1:8000")
    
    PROFESSIONAL_DOCS_UPLOAD_PATH = os.path.join(UPLOAD_FOLDER, 'professional_documents')
    INVOICE_PDF_PATH = os.path.join(ASSET_STORAGE_PATH, 'invoices')
    DEFAULT_COMPANY_INFO = {
        "name": os.environ.get('INVOICE_COMPANY_NAME', "Maison Trüvra SARL"),
        "address_line1": os.environ.get('INVOICE_COMPANY_ADDRESS1', "1 Rue de la Truffe"),
        "address_line2": os.environ.get('INVOICE_COMPANY_ADDRESS2', ""),
        "city_postal_country": os.environ.get('INVOICE_COMPANY_CITY_POSTAL_COUNTRY', "75001 Paris, France"),
        "vat_number": os.environ.get('INVOICE_COMPANY_VAT', "FRXX123456789"),
        "logo_path": os.environ.get('INVOICE_COMPANY_LOGO_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'logos', 'maison_truvra_invoice_logo.png'))
    }
    
    API_VERSION = "v1.4-sqlalchemy-totp-sso" 

    # Rate Limiting
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', "memory://")
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_HEADERS_ENABLED = True
    DEFAULT_RATELIMITS = ["200 per day", "50 per hour"] 
    AUTH_RATELIMITS = ["20 per minute", "200 per hour"] 
    ADMIN_LOGIN_RATELIMITS = ["10 per 5 minutes", "60 per hour"] 
    PASSWORD_RESET_RATELIMITS = ["5 per 15 minutes"]
    NEWSLETTER_RATELIMITS = ["10 per minute"] 
    ADMIN_API_RATELIMITS = ["200 per hour"] 

    # Content Security Policy
    CONTENT_SECURITY_POLICY = {
        'default-src': ['\'self\''],
        'img-src': ['\'self\'', 'https://placehold.co', 'data:'], 
        'script-src': ['\'self\'', 'https://cdn.tailwindcss.com'],
        'style-src': ['\'self\'', 'https://cdnjs.cloudflare.com', 'https://fonts.googleapis.com', '\'unsafe-inline\''],
        'font-src': ['\'self\'', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
        'connect-src': ['\'self\'', 'https://app.simplelogin.io'], 
        'form-action': ['\'self\'', 'https://app.simplelogin.io'], 
        'frame-ancestors': ['\'none\'']
    }
    TALISMAN_FORCE_HTTPS = False

    # Initial Admin User
    INITIAL_ADMIN_EMAIL = os.environ.get('INITIAL_ADMIN_EMAIL')
    INITIAL_ADMIN_PASSWORD = os.environ.get('INITIAL_ADMIN_PASSWORD')

    # Token Lifespans
    VERIFICATION_TOKEN_LIFESPAN_HOURS = 24
    RESET_TOKEN_LIFESPAN_HOURS = 1
    MAGIC_LINK_LIFESPAN_MINUTES = 10

    # Invoice Settings
    INVOICE_DUE_DAYS = 30

    # TOTP Configuration
    TOTP_ISSUER_NAME = os.environ.get('TOTP_ISSUER_NAME', "Maison Trüvra Admin")
    TOTP_LOGIN_STATE_TIMEOUT = timedelta(minutes=5) 

    # SimpleLogin OAuth Configuration
    SIMPLELOGIN_CLIENT_ID = os.environ.get('SIMPLELOGIN_CLIENT_ID', 'truvra-ykisfvoctm') # Updated with your App ID
    SIMPLELOGIN_CLIENT_SECRET = os.environ.get('SIMPLELOGIN_CLIENT_SECRET', 'cppjuelfvjkkqursqunvwigxiyabakgfthhivwzi') # Updated with your App Secret
    SIMPLELOGIN_AUTHORIZE_URL = os.environ.get('SIMPLELOGIN_AUTHORIZE_URL', 'https://app.simplelogin.io/oauth2/authorize')
    SIMPLELOGIN_TOKEN_URL = os.environ.get('SIMPLELOGIN_TOKEN_URL', 'https://app.simplelogin.io/oauth2/token')
    SIMPLELOGIN_USERINFO_URL = os.environ.get('SIMPLELOGIN_USERINFO_URL', 'https://app.simplelogin.io/oauth2/userinfo')
    SIMPLELOGIN_REDIRECT_URI_ADMIN = os.environ.get('SIMPLELOGIN_REDIRECT_URI_ADMIN', 'http://localhost:5001/api/admin/login/simplelogin/callback')
    SIMPLELOGIN_SCOPES = "openid email profile" 


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    SQLALCHEMY_ECHO = False 
    JWT_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'dev_maison_truvra_orm.sqlite3')
    MAIL_SERVER = os.environ.get('DEV_MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('DEV_MAIL_PORT', 1025))
    MAIL_USE_TLS = False
    MAIL_USERNAME = None
    MAIL_PASSWORD = None
    TALISMAN_FORCE_HTTPS = False
    APP_BASE_URL = os.environ.get('DEV_APP_BASE_URL', 'http://localhost:8000') 
    Config.CONTENT_SECURITY_POLICY['connect-src'].extend(['http://localhost:5001', 'http://127.0.0.1:5001'])
    # Development values for SimpleLogin are now taken from the base Config or environment variables


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'sqlite:///:memory:')
    JWT_COOKIE_SECURE = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(minutes=10)
    MAIL_SUPPRESS_SEND = True
    TALISMAN_FORCE_HTTPS = False
    WTF_CSRF_ENABLED = False 
    RATELIMIT_ENABLED = False
    INITIAL_ADMIN_EMAIL = 'test_admin_orm@example.com'
    INITIAL_ADMIN_PASSWORD = 'test_password_orm123'
    SQLALCHEMY_ECHO = False
    SIMPLELOGIN_CLIENT_ID = 'test_sl_client_id_testing' # Keep test credentials separate
    SIMPLELOGIN_CLIENT_SECRET = 'test_sl_client_secret_testing'


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    
    if Config.SECRET_KEY == 'change_this_default_secret_key_in_prod_sqlalchemy':
        raise ValueError("Production SECRET_KEY is not set or is using the default value.")
    if Config.JWT_SECRET_KEY == 'change_this_default_jwt_secret_key_in_prod_sqlalchemy':
        raise ValueError("Production JWT_SECRET_KEY is not set or is using the default value.")

    JWT_COOKIE_SECURE = True
    JWT_COOKIE_SAMESITE = 'Strict'
    TALISMAN_FORCE_HTTPS = True 
    
    APP_BASE_URL = os.environ.get('PROD_APP_BASE_URL')
    if not APP_BASE_URL:
        raise ValueError("PROD_APP_BASE_URL environment variable must be set for production.")

    PROD_CORS_ORIGINS = os.environ.get('PROD_CORS_ORIGINS')
    if not PROD_CORS_ORIGINS:
        raise ValueError("PROD_CORS_ORIGINS environment variable must be set for production.")
    CORS_ORIGINS = PROD_CORS_ORIGINS

    MYSQL_USER_PROD = os.environ.get('MYSQL_USER_PROD')
    MYSQL_PASSWORD_PROD = os.environ.get('MYSQL_PASSWORD_PROD')
    MYSQL_HOST_PROD = os.environ.get('MYSQL_HOST_PROD')
    MYSQL_DB_PROD = os.environ.get('MYSQL_DB_PROD')
    if not all([MYSQL_USER_PROD, MYSQL_PASSWORD_PROD, MYSQL_HOST_PROD, MYSQL_DB_PROD]):
        print("WARNING: Production MySQL connection details are not fully set. Database will not connect.")
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'prod_fallback_orm.sqlite3')
    else:
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_USER_PROD}:{MYSQL_PASSWORD_PROD}@{MYSQL_HOST_PROD}/{MYSQL_DB_PROD}"

    RATELIMIT_STORAGE_URI = os.environ.get('PROD_RATELIMIT_STORAGE_URI')
    if not RATELIMIT_STORAGE_URI or RATELIMIT_STORAGE_URI == "memory://":
        print("WARNING: RATELIMIT_STORAGE_URI is not set or is 'memory://' for production. Consider Redis.")

    if not Config.MAIL_SERVER or not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
        print("WARNING: Production email server is not fully configured.")
    if not Config.STRIPE_SECRET_KEY or not Config.STRIPE_PUBLISHABLE_KEY:
        print("WARNING: Stripe keys are not configured for production.")
    
    Config.CONTENT_SECURITY_POLICY['connect-src'] = ['\'self\'', APP_BASE_URL, 'https://app.simplelogin.io']
    Config.CONTENT_SECURITY_POLICY['form-action'] = ['\'self\'', 'https://app.simplelogin.io']

    if not Config.INITIAL_ADMIN_EMAIL or not Config.INITIAL_ADMIN_PASSWORD:
        print("WARNING: INITIAL_ADMIN_EMAIL or INITIAL_ADMIN_PASSWORD environment variables are not set.")
    
    # Ensure production uses actual environment variables for SimpleLogin credentials
    if Config.SIMPLELOGIN_CLIENT_ID == 'truvra-ykisfvoctm' or Config.SIMPLELOGIN_CLIENT_SECRET == 'cppjuelfvjkkqursqunvwigxiyabakgfthhivwzi':
        if not (os.environ.get('SIMPLELOGIN_CLIENT_ID') and os.environ.get('SIMPLELOGIN_CLIENT_SECRET')):
             print("WARNING: SimpleLogin OAuth credentials are using fallback values in production. Set environment variables.")


config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig,
    production=ProductionConfig,
    default=DevelopmentConfig 
)

def get_config_by_name(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    
    if os.getenv('FLASK_ENV') == 'production' and config_name != 'production':
        print(f"Warning: FLASK_ENV is 'production' but config_name is '{config_name}'. Forcing ProductionConfig.")
        config_name = 'production'
        
    config_instance = config_by_name.get(config_name)()
    
    paths_to_create = [
        os.path.dirname(config_instance.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')) if 'sqlite:///' in config_instance.SQLALCHEMY_DATABASE_URI else None,
        config_instance.UPLOAD_FOLDER,
        config_instance.ASSET_STORAGE_PATH, config_instance.QR_CODE_FOLDER,
        config_instance.PASSPORT_FOLDER, config_instance.LABEL_FOLDER,
        config_instance.PROFESSIONAL_DOCS_UPLOAD_PATH, config_instance.INVOICE_PDF_PATH
    ]
    for path in paths_to_create:
        if path: 
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                print(f"Warning: Could not create directory {path}: {e}") 
    return config_instance
```python
# backend/models.py
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
import enum
import pyotp # For TOTP functionality
from flask import current_app # For accessing config like TOTP_ISSUER_NAME

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256)) 
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    role = db.Column(db.String(50), nullable=False, default='b2c_customer', index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False, index=True) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    company_name = db.Column(db.String(120))
    vat_number = db.Column(db.String(50))
    siret_number = db.Column(db.String(50))
    professional_status = db.Column(db.String(50), index=True) 
    
    reset_token = db.Column(db.String(100), index=True)
    reset_token_expires_at = db.Column(db.DateTime)
    verification_token = db.Column(db.String(100), index=True)
    verification_token_expires_at = db.Column(db.DateTime)
    
    totp_secret = db.Column(db.String(100)) 
    is_totp_enabled = db.Column(db.Boolean, default=False, nullable=False)
    
    simplelogin_user_id = db.Column(db.String(255), unique=True, nullable=True, index=True) 

    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    reviews = db.relationship('Review', backref='user', lazy='dynamic')
    cart = db.relationship('Cart', backref='user', uselist=False, lazy='joined')
    professional_documents = db.relationship('ProfessionalDocument', backref='user', lazy='dynamic')
    b2b_invoices = db.relationship('Invoice', foreign_keys='Invoice.b2b_user_id', backref='b2b_user', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', foreign_keys='AuditLog.user_id', backref='acting_user', lazy='dynamic')


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash: 
            return False
        return check_password_hash(self.password_hash, password)

    def generate_totp_secret(self):
        self.totp_secret = pyotp.random_base32()
        return self.totp_secret

    def get_totp_uri(self, issuer_name=None):
        if not self.totp_secret:
            return None
        effective_issuer_name = issuer_name or current_app.config.get('TOTP_ISSUER_NAME', 'Maison Truvra')
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.email, 
            issuer_name=effective_issuer_name
        )

    def verify_totp(self, code_attempt):
        if not self.totp_secret or not self.is_totp_enabled:
            return False 
        totp_instance = pyotp.TOTP(self.totp_secret)
        return totp_instance.verify(code_attempt)

    def to_dict(self): 
        return {
            "id": self.id, "email": self.email, "first_name": self.first_name,
            "last_name": self.last_name, "role": self.role, "is_active": self.is_active,
            "is_verified": self.is_verified, "company_name": self.company_name,
            "professional_status": self.professional_status, "is_totp_enabled": self.is_totp_enabled,
            "is_admin": self.role == 'admin' 
        }

    def __repr__(self):
        return f'<User {self.email}>'

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    category_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), index=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    products = db.relationship('Product', backref='category', lazy='dynamic')
    children = db.relationship('Category', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    localizations = db.relationship('CategoryLocalization', backref='category', lazy='dynamic', cascade="all, delete-orphan")
    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "description": self.description, 
            "image_url": self.image_url, "category_code": self.category_code,
            "parent_id": self.parent_id, "slug": self.slug, "is_active": self.is_active,
            "product_count": self.products.filter_by(is_active=True).count()
        }
    def __repr__(self): return f'<Category {self.name}>'

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), index=True)
    product_code = db.Column(db.String(100), unique=True, nullable=False, index=True)
    sku_prefix = db.Column(db.String(100), unique=True, index=True)
    brand = db.Column(db.String(100), index=True)
    type = db.Column(db.String(50), nullable=False, default='simple', index=True)
    base_price = db.Column(db.Float)
    currency = db.Column(db.String(10), default='EUR')
    main_image_url = db.Column(db.String(255))
    aggregate_stock_quantity = db.Column(db.Integer, default=0)
    aggregate_stock_weight_grams = db.Column(db.Float)
    unit_of_measure = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_featured = db.Column(db.Boolean, default=False, index=True)
    meta_title = db.Column(db.String(255))
    meta_description = db.Column(db.Text)
    slug = db.Column(db.String(170), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    images = db.relationship('ProductImage', backref='product', lazy='dynamic', cascade="all, delete-orphan")
    weight_options = db.relationship('ProductWeightOption', backref='product', lazy='dynamic', cascade="all, delete-orphan")
    serialized_items = db.relationship('SerializedInventoryItem', backref='product', lazy='dynamic')
    stock_movements = db.relationship('StockMovement', backref='product', lazy='dynamic')
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')
    reviews = db.relationship('Review', backref='product', lazy='dynamic')
    cart_items = db.relationship('CartItem', backref='product', lazy='dynamic')
    localizations = db.relationship('ProductLocalization', backref='product', lazy='dynamic', cascade="all, delete-orphan")
    generated_assets = db.relationship('GeneratedAsset', foreign_keys='GeneratedAsset.related_product_id', backref='product_asset_owner', lazy='dynamic')
    def to_dict(self): 
        return {
            "id": self.id, "name": self.name, "product_code": self.product_code,
            "slug": self.slug, "type": self.type, "base_price": self.base_price,
            "is_active": self.is_active, "is_featured": self.is_featured,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "main_image_url": self.main_image_url, 
            "aggregate_stock_quantity": self.aggregate_stock_quantity
        }
    def __repr__(self): return f'<Product {self.name}>'

class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    image_url = db.Column(db.String(255), nullable=False)
    alt_text = db.Column(db.String(255))
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class ProductWeightOption(db.Model):
    __tablename__ = 'product_weight_options'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    weight_grams = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    sku_suffix = db.Column(db.String(50), nullable=False)
    aggregate_stock_quantity = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    serialized_items = db.relationship('SerializedInventoryItem', backref='variant', lazy='dynamic')
    stock_movements = db.relationship('StockMovement', backref='variant', lazy='dynamic')
    order_items = db.relationship('OrderItem', backref='variant', lazy='dynamic')
    cart_items = db.relationship('CartItem', backref='variant', lazy='dynamic')
    __table_args__ = (db.UniqueConstraint('product_id', 'weight_grams', name='uq_product_weight'),
                      db.UniqueConstraint('product_id', 'sku_suffix', name='uq_product_sku_suffix'))

class SerializedInventoryItem(db.Model):
    __tablename__ = 'serialized_inventory_items'
    id = db.Column(db.Integer, primary_key=True)
    item_uid = db.Column(db.String(100), unique=True, nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id'), index=True)
    batch_number = db.Column(db.String(100), index=True)
    production_date = db.Column(db.DateTime)
    expiry_date = db.Column(db.DateTime, index=True)
    actual_weight_grams = db.Column(db.Float)
    cost_price = db.Column(db.Float)
    purchase_price = db.Column(db.Float)
    status = db.Column(db.String(50), nullable=False, default='available', index=True)
    qr_code_url = db.Column(db.String(255))
    passport_url = db.Column(db.String(255))
    label_url = db.Column(db.String(255))
    notes = db.Column(db.Text)
    supplier_id = db.Column(db.Integer)
    received_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sold_at = db.Column(db.DateTime)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id'), unique=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    stock_movements = db.relationship('StockMovement', backref='serialized_item', lazy='dynamic')
    generated_assets = db.relationship('GeneratedAsset', foreign_keys='GeneratedAsset.related_item_uid', backref='inventory_item_asset_owner', lazy='dynamic')
    def to_dict(self):
        return {
            "id": self.id, "item_uid": self.item_uid, "product_id": self.product_id,
            "variant_id": self.variant_id, "batch_number": self.batch_number,
            "production_date": self.production_date.isoformat() if self.production_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "status": self.status, "notes": self.notes,
            "product_name": self.product.name if self.product else None, 
            "variant_sku_suffix": self.variant.sku_suffix if self.variant else None,
        }

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id'), index=True)
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id'), index=True)
    movement_type = db.Column(db.String(50), nullable=False, index=True)
    quantity_change = db.Column(db.Integer)
    weight_change_grams = db.Column(db.Float)
    reason = db.Column(db.Text)
    related_order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), index=True)
    related_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    movement_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    notes = db.Column(db.Text)
    def to_dict(self): 
        return {
            "id": self.id, "product_id": self.product_id, "variant_id": self.variant_id,
            "serialized_item_id": self.serialized_item_id, "movement_type": self.movement_type,
            "quantity_change": self.quantity_change, "reason": self.reason,
            "movement_date": self.movement_date.isoformat(), "notes": self.notes
        }

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.String(50), nullable=False, default='pending_payment', index=True)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='EUR')
    shipping_address_line1 = db.Column(db.String(255))
    shipping_address_line2 = db.Column(db.String(255))
    shipping_city = db.Column(db.String(100))
    shipping_postal_code = db.Column(db.String(20))
    shipping_country = db.Column(db.String(100))
    billing_address_line1 = db.Column(db.String(255))
    billing_address_line2 = db.Column(db.String(255))
    billing_city = db.Column(db.String(100))
    billing_postal_code = db.Column(db.String(20))
    billing_country = db.Column(db.String(100))
    payment_method = db.Column(db.String(50))
    payment_transaction_id = db.Column(db.String(100), index=True)
    shipping_method = db.Column(db.String(100))
    shipping_cost = db.Column(db.Float, default=0.0)
    tracking_number = db.Column(db.String(100))
    notes_customer = db.Column(db.Text)
    notes_internal = db.Column(db.Text)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), unique=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade="all, delete-orphan")
    stock_movements = db.relationship('StockMovement', backref='related_order', lazy='dynamic')
    invoice = db.relationship('Invoice', backref=db.backref('order_link', uselist=False)) 

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id'), index=True)
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id'), unique=True, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False) 
    total_price = db.Column(db.Float, nullable=False)
    product_name = db.Column(db.String(150)) 
    variant_description = db.Column(db.String(100)) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sold_serialized_item = db.relationship('SerializedInventoryItem', backref='order_item_link', foreign_keys=[serialized_item_id], uselist=False)

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False) 
    comment = db.Column(db.Text)
    review_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    is_approved = db.Column(db.Boolean, default=False, index=True)

class Cart(db.Model):
    __tablename__ = 'carts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, index=True) 
    session_id = db.Column(db.String(255), unique=True, index=True) 
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    items = db.relationship('CartItem', backref='cart', lazy='dynamic', cascade="all, delete-orphan")

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    variant_id = db.Column(db.Integer, db.ForeignKey('product_weight_options.id'), index=True) 
    quantity = db.Column(db.Integer, nullable=False)
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class ProfessionalDocument(db.Model):
    __tablename__ = 'professional_documents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    document_type = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(50), default='pending_review', index=True) 
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id')) 
    reviewed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), unique=True, index=True) 
    b2b_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True) 
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    issue_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    due_date = db.Column(db.DateTime, index=True)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='EUR') 
    status = db.Column(db.String(50), nullable=False, default='draft', index=True) 
    pdf_path = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    items = db.relationship('InvoiceItem', backref='invoice', lazy='dynamic', cascade="all, delete-orphan")

class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id')) 
    serialized_item_id = db.Column(db.Integer, db.ForeignKey('serialized_inventory_items.id')) 

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True) 
    username = db.Column(db.String(120)) 
    action = db.Column(db.String(255), nullable=False, index=True)
    target_type = db.Column(db.String(50), index=True) 
    target_id = db.Column(db.Integer, index=True)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = db.Column(db.String(20), default='success', index=True) 

class NewsletterSubscription(db.Model):
    __tablename__ = 'newsletter_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    subscribed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True, index=True)
    source = db.Column(db.String(100)) 
    consent = db.Column(db.String(10), nullable=False, default='Y') 

class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ProductLocalization(db.Model):
    __tablename__ = 'product_localizations'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    lang_code = db.Column(db.String(5), nullable=False) 
    name_fr = db.Column(db.String(150))
    name_en = db.Column(db.String(150))
    description_fr = db.Column(db.Text)
    description_en = db.Column(db.Text)
    short_description_fr = db.Column(db.Text)
    short_description_en = db.Column(db.Text)
    ideal_uses_fr = db.Column(db.Text)
    ideal_uses_en = db.Column(db.Text)
    pairing_suggestions_fr = db.Column(db.Text)
    pairing_suggestions_en = db.Column(db.Text)
    sensory_description_fr = db.Column(db.Text)
    sensory_description_en = db.Column(db.Text)
    __table_args__ = (db.UniqueConstraint('product_id', 'lang_code', name='uq_product_lang'),)

class CategoryLocalization(db.Model):
    __tablename__ = 'category_localizations'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    lang_code = db.Column(db.String(5), nullable=False)
    name_fr = db.Column(db.String(100))
    name_en = db.Column(db.String(100))
    description_fr = db.Column(db.Text)
    description_en = db.Column(db.Text)
    species_fr = db.Column(db.Text)
    species_en = db.Column(db.Text)
    main_ingredients_fr = db.Column(db.Text)
    main_ingredients_en = db.Column(db.Text)
    ingredients_notes_fr = db.Column(db.Text)
    ingredients_notes_en = db.Column(db.Text)
    fresh_vs_preserved_fr = db.Column(db.Text)
    fresh_vs_preserved_en = db.Column(db.Text)
    size_details_fr = db.Column(db.Text)
    size_details_en = db.Column(db.Text)
    pairings_fr = db.Column(db.Text)
    pairings_en = db.Column(db.Text)
    weight_info_fr = db.Column(db.Text)
    weight_info_en = db.Column(db.Text)
    category_notes_fr = db.Column(db.Text)
    category_notes_en = db.Column(db.Text)
    __table_args__ = (db.UniqueConstraint('category_id', 'lang_code', name='uq_category_lang'),)

class GeneratedAsset(db.Model):
    __tablename__ = 'generated_assets'
    id = db.Column(db.Integer, primary_key=True)
    asset_type = db.Column(db.String(50), nullable=False, index=True) 
    related_item_uid = db.Column(db.String(100), db.ForeignKey('serialized_inventory_items.item_uid'), index=True)
    related_product_id = db.Column(db.Integer, db.ForeignKey('products.id'), index=True)
    file_path = db.Column(db.String(255), nullable=False, unique=True)
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
```python
# backend/admin_api/routes.py
import os
import uuid
import requests 
from urllib.parse import urlencode 

from werkzeug.utils import secure_filename
from flask import request, jsonify, current_app, url_for, redirect, session, abort as flask_abort
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


def _create_admin_session(admin_user):
    """Helper to create JWT and user info for successful admin login."""
    identity = admin_user.id
    additional_claims = {
        "role": admin_user.role, "email": admin_user.email, "is_admin": True,
        "first_name": admin_user.first_name, "last_name": admin_user.last_name
    }
    access_token = create_access_token(identity=identity, additional_claims=additional_claims)
    user_info_to_return = admin_user.to_dict() 
    return jsonify(success=True, message="Admin login successful!", token=access_token, user=user_info_to_return), 200



@admin_api_bp.route('/login', methods=['POST'])
@limiter.limit(lambda: current_app.config.get('ADMIN_LOGIN_RATELIMITS', "10 per 5 minutes"))
def admin_login_step1_password():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    audit_logger = current_app.audit_log_service

    if not email or not password:
        audit_logger.log_action(action='admin_login_fail_step1', email=email, details="Email and password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email and password are required", success=False, totp_required=False), 400
    try:
        admin_user = User.query.filter_by(email=email, role=UserRoleEnum.ADMIN).first()
        if admin_user and admin_user.check_password(password):
            if not admin_user.is_active:
                audit_logger.log_action(user_id=admin_user.id, action='admin_login_fail_inactive_step1', target_type='user_admin', target_id=admin_user.id, details="Admin account is inactive.", status='failure', ip_address=request.remote_addr)
                return jsonify(message="Admin account is inactive. Please contact support.", success=False, totp_required=False), 403
            
            if admin_user.is_totp_enabled and admin_user.totp_secret:
                session['pending_totp_admin_id'] = admin_user.id
                session['pending_totp_admin_email'] = admin_user.email 
                session.permanent = True 
                current_app.permanent_session_lifetime = current_app.config.get('TOTP_LOGIN_STATE_TIMEOUT', timedelta(minutes=5))
                audit_logger.log_action(user_id=admin_user.id, action='admin_login_totp_required', target_type='user_admin', target_id=admin_user.id, status='pending', ip_address=request.remote_addr)
                return jsonify(message="Password verified. Please enter your TOTP code.", success=True, totp_required=True, email=admin_user.email), 200 
            else:
                audit_logger.log_action(user_id=admin_user.id, action='admin_login_success_no_totp', target_type='user_admin', target_id=admin_user.id, status='success', ip_address=request.remote_addr)
                return _create_admin_session_and_get_response(admin_user)
        else:
            audit_logger.log_action(action='admin_login_fail_credentials_step1', email=email, details="Invalid admin credentials.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid admin email or password", success=False, totp_required=False), 401
    except Exception as e:
        current_app.logger.error(f"Error during admin login step 1 for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='admin_login_fail_server_error_step1', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Admin login failed due to a server error. Please try again later.", success=False, totp_required=False), 500

@admin_api_bp.route('/login/verify-totp', methods=['POST'])
@limiter.limit(lambda: current_app.config.get('ADMIN_LOGIN_RATELIMITS', "10 per 5 minutes")) # Same limit as step 1
def admin_login_step2_verify_totp():
    data = request.json
    totp_code = data.get('totp_code')
    audit_logger = current_app.audit_log_service
    
    pending_admin_id = session.get('pending_totp_admin_id')
    pending_admin_email = session.get('pending_totp_admin_email') 

    if not pending_admin_id:
        audit_logger.log_action(action='admin_totp_verify_fail_no_pending_state', details="No pending TOTP login state found in session.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Login session expired or invalid. Please start over.", success=False), 400
    
    if not totp_code:
        audit_logger.log_action(user_id=pending_admin_id, action='admin_totp_verify_fail_no_code', email=pending_admin_email, details="TOTP code missing.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="TOTP code is required.", success=False), 400
    try:
        admin_user = User.query.get(pending_admin_id)
        if not admin_user or not admin_user.is_active or admin_user.role != UserRoleEnum.ADMIN:
            session.pop('pending_totp_admin_id', None)
            session.pop('pending_totp_admin_email', None)
            audit_logger.log_action(user_id=pending_admin_id, action='admin_totp_verify_fail_user_invalid', email=pending_admin_email, details="Admin user not found, inactive, or not admin role during TOTP.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid user state for TOTP verification. Please log in again.", success=False), 403

        if admin_user.verify_totp(totp_code): # Uses User model method
            session.pop('pending_totp_admin_id', None)
            session.pop('pending_totp_admin_email', None)
            audit_logger.log_action(user_id=admin_user.id, action='admin_login_success_totp_verified', target_type='user_admin', target_id=admin_user.id, status='success', ip_address=request.remote_addr)
            return _create_admin_session_and_get_response(admin_user)
        else:
            audit_logger.log_action(user_id=admin_user.id, action='admin_totp_verify_fail_invalid_code', email=pending_admin_email, details="Invalid TOTP code.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid TOTP code. Please try again.", success=False), 401
            
    except Exception as e:
        current_app.logger.error(f"Error during admin TOTP verification for {pending_admin_email}: {e}", exc_info=True)
        audit_logger.log_action(user_id=pending_admin_id, action='admin_totp_verify_fail_server_error', email=pending_admin_email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="TOTP verification failed due to a server error. Please try again.", success=False), 500

@admin_api_bp.route('/login/simplelogin/initiate', methods=['GET'])
def simplelogin_initiate():
    client_id = current_app.config.get('SIMPLELOGIN_CLIENT_ID')
    redirect_uri = current_app.config.get('SIMPLELOGIN_REDIRECT_URI_ADMIN') # This should be the backend callback
    authorize_url = current_app.config.get('SIMPLELOGIN_AUTHORIZE_URL')
    scopes = current_app.config.get('SIMPLELOGIN_SCOPES')

    if not all([client_id, redirect_uri, authorize_url, scopes]):
        current_app.logger.error("SimpleLogin OAuth settings are not fully configured in the backend.")
        return jsonify(message="SimpleLogin SSO is not configured correctly on the server.", success=False), 500

    session['oauth_state_sl'] = secrets.token_urlsafe(16)
    params = {'response_type': 'code', 'client_id': client_id, 'redirect_uri': redirect_uri, 'scope': scopes, 'state': session['oauth_state_sl']}
    auth_redirect_url = f"{authorize_url}?{urlencode(params)}"
    current_app.logger.info(f"Redirecting admin to SimpleLogin for authentication: {auth_redirect_url}")
    return redirect(auth_redirect_url)

@admin_api_bp.route('/login/simplelogin/callback', methods=['GET'])
def simplelogin_callback():
    auth_code = request.args.get('code')
    state_returned = request.args.get('state')
    audit_logger = current_app.audit_log_service
    base_admin_login_url = current_app.config.get('APP_BASE_URL_FRONTEND', 'http://localhost:8000') + '/admin/admin_login.html' # Frontend login page for errors
    admin_dashboard_url = current_app.config.get('APP_BASE_URL_FRONTEND', 'http://localhost:8000') + '/admin/admin_dashboard.html' # Frontend dashboard

    expected_state = session.pop('oauth_state_sl', None)
    if not expected_state or expected_state != state_returned:
        audit_logger.log_action(action='simplelogin_callback_fail_state_mismatch', details="OAuth state mismatch.", status='failure', ip_address=request.remote_addr)
        return redirect(f"{base_admin_login_url}?error=sso_state_mismatch")

    if not auth_code: # ... (handle no code) ...
        return redirect(f"{base_admin_login_url}?error=sso_no_code")

    token_url = current_app.config['SIMPLELOGIN_TOKEN_URL']
    payload = { 'grant_type': 'authorization_code', 'code': auth_code, 'redirect_uri': current_app.config['SIMPLELOGIN_REDIRECT_URI_ADMIN'],
                'client_id': current_app.config['SIMPLELOGIN_CLIENT_ID'], 'client_secret': current_app.config['SIMPLELOGIN_CLIENT_SECRET'],}
    try:
        token_response = requests.post(token_url, data=payload, timeout=10)
        token_response.raise_for_status() 
        sl_access_token = token_response.json().get('access_token')
        if not sl_access_token: # ... (handle no SL token) ...
            return redirect(f"{base_admin_login_url}?error=sso_token_error")

        userinfo_response = requests.get(current_app.config['SIMPLELOGIN_USERINFO_URL'], headers={'Authorization': f'Bearer {sl_access_token}'}, timeout=10)
        userinfo_response.raise_for_status()
        sl_user_info = userinfo_response.json()
        sl_email = sl_user_info.get('email')
        sl_simplelogin_user_id = sl_user_info.get('sub') 

        if not sl_email: # ... (handle no email from SL) ...
            return redirect(f"{base_admin_login_url}?error=sso_email_error")
        
        # Configurable list of allowed admin emails for SimpleLogin
        allowed_admin_emails_str = current_app.config.get('SIMPLELOGIN_ALLOWED_ADMIN_EMAILS', "")
        allowed_admin_emails = [email.strip().lower() for email in allowed_admin_emails_str.split(',') if email.strip()]

        if not allowed_admin_emails: # If not configured, deny all SimpleLogin attempts for safety
            current_app.logger.error("SIMPLELOGIN_ALLOWED_ADMIN_EMAILS is not configured. Denying SimpleLogin attempt.")
            audit_logger.log_action(action='simplelogin_callback_fail_config_missing', email=sl_email, details="Allowed admin emails for SSO not configured.", status='failure', ip_address=request.remote_addr)
            return redirect(f"{base_admin_login_url}?error=sso_config_error")

        if sl_email.lower() not in allowed_admin_emails:
            audit_logger.log_action(action='simplelogin_callback_fail_email_not_allowed', email=sl_email, details=f"SSO attempt from non-allowed email: {sl_email}", status='failure', ip_address=request.remote_addr)
            return redirect(f"{base_admin_login_url}?error=sso_unauthorized_email")

        admin_user = User.query.filter(func.lower(User.email) == sl_email.lower(), User.role == UserRoleEnum.ADMIN).first()
        if admin_user and admin_user.is_active:
            if not admin_user.simplelogin_user_id and sl_simplelogin_user_id:
                admin_user.simplelogin_user_id = sl_simplelogin_user_id # Link SL ID
                db.session.commit()
            audit_logger.log_action(user_id=admin_user.id, action='admin_login_success_simplelogin', target_type='user_admin', target_id=admin_user.id, details=f"Admin {sl_email} logged in via SimpleLogin.", status='success', ip_address=request.remote_addr)
            return _create_admin_session_and_get_response(admin_user, admin_dashboard_url) # Redirect to frontend dashboard
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

@admin_api_bp.route('/totp/setup-initiate', methods=['POST'])
@admin_required
@limiter.limit(lambda: current_app.config.get('ADMIN_TOTP_SETUP_RATELIMITS', "5 per 10 minutes"))
def totp_setup_initiate():
    current_admin_id = get_jwt_identity()
    data = request.json; password = data.get('password')
    audit_logger = current_app.audit_log_service
    admin_user = User.query.get(current_admin_id)

    if not admin_user or admin_user.role != UserRoleEnum.ADMIN: return jsonify(message="Admin user not found or invalid.", success=False), 403
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
        if not provisioning_uri: raise Exception("Could not generate provisioning URI.")
        audit_logger.log_action(user_id=current_admin_id, action='totp_setup_initiate_success', details="TOTP secret generated.", status='success', ip_address=request.remote_addr)
        return jsonify(message="TOTP setup initiated. Scan QR code and verify.", totp_provisioning_uri=provisioning_uri, totp_manual_secret=new_secret, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error initiating TOTP setup for admin {current_admin_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to initiate TOTP setup: {str(e)}", success=False), 500

@admin_api_bp.route('/totp/setup-verify', methods=['POST'])
@admin_required
@limiter.limit(lambda: current_app.config.get('ADMIN_TOTP_SETUP_RATELIMITS', "5 per 10 minutes"))
def totp_setup_verify_and_enable():
    current_admin_id = get_jwt_identity(); data = request.json; totp_code = data.get('totp_code')
    audit_logger = current_app.audit_log_service
    pending_secret = session.get('pending_totp_secret_for_setup')
    pending_user_id = session.get('pending_totp_user_id_for_setup')

    if not pending_secret or not pending_user_id or pending_user_id != current_admin_id:
        return jsonify(message="TOTP setup session expired or invalid. Please start over.", success=False), 400
    if not totp_code: return jsonify(message="TOTP code is required for verification.", success=False), 400

    admin_user = User.query.get(current_admin_id)
    if not admin_user: return jsonify(message="Admin user not found.", success=False), 404
    
    temp_totp_instance = pyotp.TOTP(pending_secret)
    if temp_totp_instance.verify(totp_code):
        try:
            admin_user.totp_secret = pending_secret; admin_user.is_totp_enabled = True
            admin_user.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            session.pop('pending_totp_secret_for_setup', None); session.pop('pending_totp_user_id_for_setup', None)
            audit_logger.log_action(user_id=current_admin_id, action='totp_setup_verify_success', details="TOTP enabled.", status='success', ip_address=request.remote_addr)
            return jsonify(message="Two-Factor Authentication (TOTP) enabled successfully!", success=True), 200
        except Exception as e:
            db.session.rollback(); current_app.logger.error(f"Error saving TOTP setup for admin {current_admin_id}: {e}", exc_info=True)
            return jsonify(message="Failed to save TOTP settings.", success=False), 500
    else:
        audit_logger.log_action(user_id=current_admin_id, action='totp_setup_verify_fail_invalid_code', details="Invalid TOTP code during setup.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid TOTP code. Please try again.", success=False), 400

@admin_api_bp.route('/totp/disable', methods=['POST'])
@admin_required
@limiter.limit(lambda: current_app.config.get('ADMIN_TOTP_SETUP_RATELIMITS', "5 per 10 minutes")) # Same rate limit for disable
def totp_disable():
    current_admin_id = get_jwt_identity(); data = request.json
    password = data.get('password'); totp_code = data.get('totp_code')
    audit_logger = current_app.audit_log_service
    admin_user = User.query.get(current_admin_id)

    if not admin_user or admin_user.role != UserRoleEnum.ADMIN: return jsonify(message="Admin user not found or invalid.", success=False), 403
    if not admin_user.is_totp_enabled or not admin_user.totp_secret:
        return jsonify(message="TOTP is not currently enabled for your account.", success=False), 400
    if not password or not admin_user.check_password(password):
        return jsonify(message="Incorrect current password.", success=False), 401
    if not totp_code or not admin_user.verify_totp(totp_code):
        return jsonify(message="Invalid current TOTP code.", success=False), 401
    try:
        admin_user.is_totp_enabled = False; admin_user.totp_secret = None
        admin_user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='totp_disable_success', details="TOTP disabled.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Two-Factor Authentication (TOTP) has been disabled.", success=True), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error disabling TOTP for admin {current_admin_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to disable TOTP: {str(e)}", success=False), 500
        

@admin_api_bp.route('/dashboard/stats', methods=['GET'])
@admin_required
def get_dashboard_stats():
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
            "pending_b2b_applications": pending_b2b_applications
            # "success": True # No longer needed here, _request handles it
        }
        audit_logger.log_action(user_id=current_admin_id, action='get_dashboard_stats', status='success', ip_address=request.remote_addr)
        return jsonify(stats=stats, success=True), 200 # Ensure success=True is in the main body
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
def get_categories():
    try:
        categories_models = Category.query.order_by(Category.name).all()
        categories_data = []
        for cat_model in categories_models:
            cat_dict = cat_model.to_dict() 
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
def create_product_admin():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    
    try:
        data = request.form.to_dict() 
        main_image_file = request.files.get('main_image_file')
        additional_image_files = request.files.getlist('additional_image_files') # For multiple files

        name_fr = sanitize_input(data.get('name')) # This is the primary name in Product model
        product_code = sanitize_input(data.get('product_code', '')).strip().upper()
        
        product_type_str = sanitize_input(data.get('type', 'simple'))
        try: product_type = ProductTypeEnum(product_type_str)
        except ValueError: return jsonify(message=f"Invalid product type: {product_type_str}", success=False), 400

        description_fr = sanitize_input(data.get('description', ''), allow_html=False)
        long_description_fr = sanitize_input(data.get('long_description', ''), allow_html=True)
        
        category_id_str = data.get('category_id')
        brand = sanitize_input(data.get('brand', "Maison Trüvra"))
        base_price_str = data.get('price') # 'price' from form is base_price
        currency = sanitize_input(data.get('currency', 'EUR'))
        
        unit_of_measure = sanitize_input(data.get('unit_of_measure'))
        is_active_str = data.get('is_active', 'true')
        is_active = is_active_str.lower() == 'true' if isinstance(is_active_str, str) else bool(is_active_str)
        is_featured_str = data.get('is_featured', 'false')
        is_featured = is_featured_str.lower() == 'true' if isinstance(is_featured_str, str) else bool(is_featured_str)
        
        meta_title_fr = sanitize_input(data.get('meta_title', name_fr))
        meta_description_fr = sanitize_input(data.get('meta_description', description_fr[:160] if description_fr else ''), allow_html=False)
        slug = generate_slug(name_fr)

        preservation_type_str = sanitize_input(data.get('preservation_type'))
        preservation_type_enum = PreservationTypeEnum(preservation_type_str) if preservation_type_str else PreservationTypeEnum.NOT_SPECIFIED
        notes_internal_val = sanitize_input(data.get('notes_internal'), allow_html=False)
        supplier_info_val = sanitize_input(data.get('supplier_info'))

        if not all([name_fr, product_code, product_type_str, category_id_str]):
            return jsonify(message="Name (FR), Product Code, Type, and Category are required.", success=False), 400
        category_id = int(category_id_str) if category_id_str.isdigit() else None
        if category_id is None: return jsonify(message="Valid Category ID is required.", success=False), 400
        
        if Product.query.filter(func.upper(Product.product_code) == product_code).first():
            return jsonify(message=f"Product Code '{product_code}' already exists.", success=False), 409
        if Product.query.filter_by(slug=slug).first():
            return jsonify(message=f"Product name (slug: '{slug}') already exists.", success=False), 409

        main_image_filename_db = None
        if main_image_file and allowed_file(main_image_file.filename):
            # ... (save main_image_file logic as before) ...
            pass 

        base_price = None
        if base_price_str is not None and base_price_str != '':
            try: base_price = float(base_price_str)
            except ValueError: return jsonify(message="Invalid Base Price format.", success=False), 400
        
        if product_type == ProductTypeEnum.SIMPLE and base_price is None:
            return jsonify(message="Base Price is required for simple products.", success=False), 400
        
        new_product = Product(
            name=name_fr, description=description_fr, long_description=long_description_fr,
            category_id=category_id, product_code=product_code, brand=brand, 
            type=product_type, base_price=base_price, currency=currency, 
            main_image_url=main_image_filename_db, 
            unit_of_measure=unit_of_measure, is_active=is_active, is_featured=is_featured, 
            meta_title=meta_title_fr, meta_description=meta_description_fr, slug=slug,
            preservation_type=preservation_type_enum, notes_internal=notes_internal_val, supplier_info=supplier_info_val
        )
        db.session.add(new_product)
        db.session.flush()

        # Handle localizations
        loc_data_fr = {
            'name': name_fr, 'description': description_fr, 'long_description': long_description_fr,
            'sensory_evaluation': sanitize_input(data.get('sensory_evaluation'), allow_html=True),
            'food_pairings': sanitize_input(data.get('food_pairings'), allow_html=True),
            'species': sanitize_input(data.get('species')),
            'meta_title': meta_title_fr, 'meta_description': meta_description_fr
        }
        _update_or_create_product_localization(new_product.id, 'fr', loc_data_fr)
        
        loc_data_en = {
            'name_en': sanitize_input(data.get('name_en')), 
            'description_en': sanitize_input(data.get('description_en'), allow_html=False),
            'long_description_en': sanitize_input(data.get('long_description_en'), allow_html=True),
            'sensory_evaluation_en': sanitize_input(data.get('sensory_evaluation_en'), allow_html=True),
            'food_pairings_en': sanitize_input(data.get('food_pairings_en'), allow_html=True),
            'species_en': sanitize_input(data.get('species_en')),
            'meta_title_en': sanitize_input(data.get('meta_title_en', data.get('name_en', name_fr))),
            'meta_description_en': sanitize_input(data.get('meta_description_en', (data.get('description_en') or description_fr)[:160] if (data.get('description_en') or description_fr) else ''), allow_html=False)
        }
        if any(loc_data_en.values()): # Only create/update EN if any EN data provided
             _update_or_create_product_localization(new_product.id, 'en', loc_data_en)
        
        # Handle additional image uploads
        # ... (loop through additional_image_files, save them, create ProductImage records) ...

        db.session.commit()
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='create_product_admin_success', target_type='product', target_id=new_product.id, details=f"Product '{name_fr}' created.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Product created successfully", product=new_product.to_dict(), success=True), 201

    except ValueError as e_val: # ... (handle ValueError) ...
        db.session.rollback()
        return jsonify(message=str(e_val), success=False), 400
    except Exception as e: # ... (handle general Exception) ...
        db.session.rollback()
        return jsonify(message=f"Failed to create product: {str(e)}", success=False), 500


@admin_api_bp.route('/products/<int:product_id>', methods=['PUT'])
@admin_required
def update_product_admin(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    
    try:
        product = Product.query.get(product_id)
        if not product: return jsonify(message="Product not found", success=False), 404

        data = request.form.to_dict()
        main_image_file = request.files.get('main_image_file')
        remove_main_image = data.get('remove_main_image_flag') == 'true'
        # additional_image_files = request.files.getlist('additional_image_files')
        # additional_images_text_json = data.get('additional_images_text') # For URLs

        name_fr = sanitize_input(data.get('name', product.name))
        new_product_code = sanitize_input(data.get('product_code', product.product_code)).strip().upper()
        
        product_type_str = sanitize_input(data.get('type', product.type.value if product.type else 'simple'))
        try: new_product_type = ProductTypeEnum(product_type_str)
        except ValueError: return jsonify(message=f"Invalid product type: {product_type_str}", success=False), 400
        
        old_type = product.type
        product.type = new_product_type

        if name_fr != product.name:
            new_slug = generate_slug(name_fr)
            if Product.query.filter(Product.slug == new_slug, Product.id != product_id).first():
                return jsonify(message=f"Product name (slug: '{new_slug}') already exists.", success=False), 409
            product.slug = new_slug
        
        if new_product_code != product.product_code:
            if Product.query.filter(Product.product_code == new_product_code, Product.id != product_id).first():
                return jsonify(message=f"Product Code '{new_product_code}' already exists.", success=False), 409
            product.product_code = new_product_code
        
        product.name = name_fr
        product.description = sanitize_input(data.get('description', product.description), allow_html=False)
        product.long_description = sanitize_input(data.get('long_description', product.long_description), allow_html=True)
        product.category_id = int(data['category_id']) if data.get('category_id') and data['category_id'].isdigit() else product.category_id
        product.brand = sanitize_input(data.get('brand', product.brand))
        
        if 'price' in data:
            try: product.base_price = float(data['price']) if data['price'] != '' else None
            except ValueError: return jsonify(message="Invalid Base Price format.", success=False), 400
        if product.type == ProductTypeEnum.SIMPLE and product.base_price is None:
             return jsonify(message="Base Price is required for simple products.", success=False), 400

        product.currency = sanitize_input(data.get('currency', product.currency))
        product.unit_of_measure = sanitize_input(data.get('unit_of_measure', product.unit_of_measure))
        is_active_str = data.get('is_active', str(product.is_active))
        product.is_active = is_active_str.lower() == 'true' if isinstance(is_active_str, str) else bool(is_active_str)
        is_featured_str = data.get('is_featured', str(product.is_featured))
        product.is_featured = is_featured_str.lower() == 'true' if isinstance(is_featured_str, str) else bool(is_featured_str)
        
        # Update new informational fields
        preservation_type_str = sanitize_input(data.get('preservation_type'))
        product.preservation_type = PreservationTypeEnum(preservation_type_str) if preservation_type_str else product.preservation_type
        product.notes_internal = sanitize_input(data.get('notes_internal', product.notes_internal), allow_html=False)
        product.supplier_info = sanitize_input(data.get('supplier_info', product.supplier_info))

        # Main image handling (simplified)
        if remove_main_image and product.main_image_url: product.main_image_url = None # ... delete file ...
        elif main_image_file: product.main_image_url = "path/to/new_image.jpg" # ... save file ...
        
        # Update localizations
        loc_data_fr = {
            'name': name_fr, 'description': product.description, 'long_description': product.long_description,
            'sensory_evaluation': sanitize_input(data.get('sensory_evaluation')), 'food_pairings': sanitize_input(data.get('food_pairings')),
            'species': sanitize_input(data.get('species')),
            'meta_title': sanitize_input(data.get('meta_title', name_fr)),
            'meta_description': sanitize_input(data.get('meta_description', product.description[:160] if product.description else ''))
        }
        _update_or_create_product_localization(product_id, 'fr', loc_data_fr)
        
        loc_data_en = {
            'name_en': sanitize_input(data.get('name_en')), 'description_en': sanitize_input(data.get('description_en')),
            'long_description_en': sanitize_input(data.get('long_description_en')),
            'sensory_evaluation_en': sanitize_input(data.get('sensory_evaluation_en')),
            'food_pairings_en': sanitize_input(data.get('food_pairings_en')),
            'species_en': sanitize_input(data.get('species_en')),
            'meta_title_en': sanitize_input(data.get('meta_title_en', data.get('name_en', name_fr))),
            'meta_description_en': sanitize_input(data.get('meta_description_en', (data.get('description_en') or product.description)[:160] if (data.get('description_en') or product.description) else ''))
        }
        if any(loc_data_en.values()):
            _update_or_create_product_localization(product_id, 'en', loc_data_en)

        # Additional image handling (text JSON for URLs, and file uploads) would go here.

        if old_type == ProductTypeEnum.VARIABLE_WEIGHT and new_product_type == ProductTypeEnum.SIMPLE:
            ProductWeightOption.query.filter_by(product_id=product_id).delete()

        db.session.commit()
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='update_product_admin_success', target_type='product', target_id=product_id, details=f"Product '{name_fr}' updated.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Product updated successfully", product=product.to_dict(), success=True), 200

    except ValueError as e_val: # ... (handle ValueError) ...
        db.session.rollback()
        return jsonify(message=str(e_val), success=False), 400
    except Exception as e: # ... (handle general Exception) ...
        db.session.rollback()
        return jsonify(message=f"Failed to update product: {str(e)}", success=False), 500

@admin_api_bp.route('/products/<int:product_id>/options', methods=['PUT'])
@admin_required
def update_product_options_admin(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    data = request.json
    options_data = data.get('options', []) # Expecting a list of option objects

    product = Product.query.get(product_id)
    if not product:
        return jsonify(message="Product not found", success=False), 404
    if product.type != ProductTypeEnum.VARIABLE_WEIGHT:
        return jsonify(message="Options can only be managed for 'variable_weight' products.", success=False), 400

    try:
        existing_option_ids_from_payload = {opt.get('option_id') for opt in options_data if opt.get('option_id')}
        
        # Delete options not present in the payload
        for existing_opt in list(product.weight_options): # Iterate over a copy
            if existing_opt.id not in existing_option_ids_from_payload:
                # Before deleting, ensure no serialized items are tied to this specific variant if strict FK exists
                # Or ensure stock is zero if you are managing stock here (which we are not anymore for options)
                db.session.delete(existing_opt)

        for opt_data in options_data:
            weight_grams = opt_data.get('weight_grams')
            price = opt_data.get('price')
            sku_suffix = sanitize_input(opt_data.get('sku_suffix', '')).strip().upper()
            option_id = opt_data.get('option_id')

            if not all([weight_grams, price, sku_suffix]):
                raise ValueError("Weight, price, and SKU suffix are required for each option.")
            
            weight_grams = float(weight_grams)
            price = float(price)
            if weight_grams <= 0 or price < 0:
                raise ValueError("Weight must be positive and price non-negative.")

            # Check for duplicate SKU suffix within this product's options (excluding self if editing)
            existing_sku_option = ProductWeightOption.query.filter(
                ProductWeightOption.product_id == product_id,
                ProductWeightOption.sku_suffix == sku_suffix,
                ProductWeightOption.id != option_id if option_id else True # Exclude self if option_id exists
            ).first()
            if existing_sku_option:
                raise ValueError(f"SKU Suffix '{sku_suffix}' already exists for this product.")

            if option_id: # Update existing option
                option = ProductWeightOption.query.get(option_id)
                if option and option.product_id == product_id:
                    option.weight_grams = weight_grams
                    option.price = price
                    option.sku_suffix = sku_suffix
                    option.is_active = opt_data.get('is_active', True) # Assuming form might send this
                    # Stock is NOT updated here.
                else: # Should not happen if frontend sends correct option_ids for this product
                    current_app.logger.warning(f"Attempt to update non-existent or mismatched option ID {option_id} for product {product_id}")
                    continue 
            else: # Create new option
                new_option = ProductWeightOption(
                    product_id=product_id, weight_grams=weight_grams, price=price, 
                    sku_suffix=sku_suffix, is_active=opt_data.get('is_active', True)
                    # aggregate_stock_quantity will default to 0
                )
                db.session.add(new_option)
        
        db.session.commit()
        audit_logger.log_action(user_id=current_user_id, action='update_product_options_success', target_type='product', target_id=product_id, details=f"Weight options for product {product.name} updated.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Product weight options updated successfully.", success=True), 200

    except ValueError as ve:
        db.session.rollback()
        return jsonify(message=str(ve), success=False), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update product options for product ID {product_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='update_product_options_fail', target_type='product', target_id=product_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update product options due to a server error.", success=False), 500


# --- User Management ---        
@admin_api_bp.route('/users', methods=['GET'])
@admin_required
def get_users_admin(): # Renamed to avoid conflict if a public /users endpoint exists
    # Filters
    role_filter_str = sanitize_input(request.args.get('role'))
    status_filter_str = sanitize_input(request.args.get('is_active'))
    search_term = sanitize_input(request.args.get('search'))

    query = User.query
    if role_filter_str:
        try:
            role_enum = UserRoleEnum(role_filter_str)
            query = query.filter(User.role == role_enum)
        except ValueError:
            return jsonify(message=f"Invalid role filter value: {role_filter_str}", success=False), 400
            
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
                func.cast(User.id, db.String).like(term_like)
            )
        )
    
    try:
        users_models = query.order_by(User.created_at.desc()).all()
        users_data = [u.to_dict() for u in users_models] # Leverage to_dict for consistency
        return jsonify(users=users_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching users for admin: {e}", exc_info=True)
        return jsonify(message="Failed to fetch users. Please try again later.", success=False), 500

@admin_api_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user_admin_detail(user_id): # Renamed
    try:
        user_model = User.query.get(user_id)
        if not user_model: 
            return jsonify(message="User not found.", success=False), 404
        
        user_data = user_model.to_dict()
        # Add more details if to_dict() is too brief for admin view, e.g., order history
        user_data['created_at_display'] = format_datetime_for_display(user_model.created_at)
        user_data['updated_at_display'] = format_datetime_for_display(user_model.updated_at)
        # Example: Fetch recent orders
        # user_data['recent_orders'] = [o.to_dict_summary() for o in user_model.orders.order_by(Order.order_date.desc()).limit(5).all()]
        return jsonify(user=user_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin user detail for ID {user_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch user details. Please try again later.", success=False), 500

@admin_api_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user_admin(user_id): # Renamed
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    data = request.json
    if not data: return jsonify(message="No data provided for update.", success=False), 400

    user = User.query.get(user_id)
    if not user: return jsonify(message="User not found.", success=False), 404

    allowed_fields = ['first_name', 'last_name', 'role', 'is_active', 'is_verified', 
                      'company_name', 'vat_number', 'siret_number', 'professional_status']
    updated_fields_log = []
    validation_errors = {}

    for field in allowed_fields:
        if field in data:
            new_value_raw = data[field]
            new_value_sanitized = sanitize_input(str(new_value_raw) if new_value_raw is not None else None) # Basic sanitize

            current_value = getattr(user, field)
            # Handle Enum conversions and boolean conversions
            try:
                if field == 'role' and new_value_sanitized:
                    new_value_processed = UserRoleEnum(new_value_sanitized)
                elif field == 'professional_status' and new_value_sanitized:
                    new_value_processed = ProfessionalStatusEnum(new_value_sanitized)
                elif field in ['is_active', 'is_verified']:
                    new_value_processed = str(new_value_sanitized).lower() == 'true'
                else:
                    new_value_processed = new_value_sanitized
            except ValueError as e_enum: # Invalid enum value
                validation_errors[field] = f"Invalid value for {field}: {new_value_sanitized}"
                continue # Skip this field

            if new_value_processed != current_value:
                setattr(user, field, new_value_processed)
                updated_fields_log.append(field)
    
    if validation_errors:
        return jsonify(message="Validation errors occurred.", errors=validation_errors, success=False), 400
    if not updated_fields_log: 
        return jsonify(message="No changes detected or no updatable fields provided.", success=True), 200 # Not an error

    try:
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_user_admin_success', target_type='user', target_id=user_id, details=f"User {user_id} updated. Fields: {', '.join(updated_fields_log)}", status='success', ip_address=request.remote_addr)
        return jsonify(message="User updated successfully.", user=user.to_dict(), success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update user ID {user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='update_user_admin_fail', target_type='user', target_id=user_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update user due to a server error.", success=False), 500


# backend/admin_api/routes.py (Continued - Order Management)
from ..models import Order, OrderItem, User, OrderStatusEnum # Ensure Enums imported

@admin_api_bp.route('/orders', methods=['GET'])
@admin_required
def get_orders_admin(): # Renamed
    search_filter = sanitize_input(request.args.get('search'))
    status_filter_str = sanitize_input(request.args.get('status'))
    date_filter_str = sanitize_input(request.args.get('date'))

    query = Order.query.join(User, Order.user_id == User.id) # Join for customer info
    if search_filter:
        term_like = f"%{search_filter.lower()}%"
        query = query.filter(
            or_(func.cast(Order.id, db.String).like(term_like),
                func.lower(User.email).like(term_like),
                func.lower(User.first_name).like(term_like),
                func.lower(User.last_name).like(term_like),
                Order.payment_transaction_id.like(term_like)))
    if status_filter_str:
        try:
            status_enum = OrderStatusEnum(status_filter_str)
            query = query.filter(Order.status == status_enum)
        except ValueError:
            return jsonify(message=f"Invalid status filter: {status_filter_str}", success=False), 400
    if date_filter_str: 
        try:
            filter_date = datetime.strptime(date_filter_str, '%Y-%m-%d').date()
            query = query.filter(func.date(Order.order_date) == filter_date)
        except ValueError: 
            return jsonify(message="Invalid date format. Use YYYY-MM-DD.", success=False), 400
    
    try:
        orders_models = query.order_by(Order.order_date.desc()).all()
        orders_data = []
        for o in orders_models:
            orders_data.append({
                "order_id": o.id, "user_id": o.user_id, 
                "order_date": format_datetime_for_display(o.order_date),
                "status": o.status.value if o.status else None, # Enum value
                "total_amount": o.total_amount, "currency": o.currency,
                "customer_email": o.customer.email, 
                "customer_name": f"{o.customer.first_name or ''} {o.customer.last_name or ''}".strip()
            })
        return jsonify(orders=orders_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin orders: {e}", exc_info=True)
        return jsonify(message="Failed to fetch orders. Please try again later.", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>', methods=['GET'])
@admin_required
def get_order_admin_detail(order_id): # Renamed
    try:
        order_model = Order.query.options(
            selectinload(Order.items).joinedload(OrderItem.product), # Eager load items and their products
            selectinload(Order.customer) # Eager load customer
        ).get(order_id)

        if not order_model: return jsonify(message="Order not found.", success=False), 404
        
        order_data = {
            "id": order_model.id, "user_id": order_model.user_id, 
            "customer_email": order_model.customer.email,
            "customer_name": f"{order_model.customer.first_name or ''} {order_model.customer.last_name or ''}".strip(),
            "order_date": format_datetime_for_display(order_model.order_date), 
            "status": order_model.status.value if order_model.status else None,
            "total_amount": order_model.total_amount, "currency": order_model.currency,
            "shipping_address_line1": order_model.shipping_address_line1, 
            "shipping_address_line2": order_model.shipping_address_line2,
            "shipping_city": order_model.shipping_city,
            "shipping_postal_code": order_model.shipping_postal_code,
            "shipping_country": order_model.shipping_country,
            "billing_address_line1": order_model.billing_address_line1, # ... and other billing fields
            "payment_method": order_model.payment_method, 
            "payment_transaction_id": order_model.payment_transaction_id,
            "notes_internal": order_model.notes_internal, 
            "notes_customer": order_model.notes_customer,
            "tracking_number": order_model.tracking_number, 
            "shipping_method": order_model.shipping_method,
            "items": []
        }
        for item_model in order_model.items: # Access eager-loaded items
            item_dict = {
                "id": item_model.id, "product_id": item_model.product_id, 
                "product_name": item_model.product_name, # Stored at order time
                "quantity": item_model.quantity, "unit_price": item_model.unit_price,
                "total_price": item_model.total_price, 
                "variant_description": item_model.variant_description, # Stored at order time
                "product_image_full_url": None
            }
            if item_model.product and item_model.product.main_image_url: # Access related product
                try: item_dict['product_image_full_url'] = url_for('serve_public_asset', filepath=item_model.product.main_image_url, _external=True)
                except Exception: pass
            order_data['items'].append(item_dict)
        return jsonify(order=order_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin order detail for ID {order_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch order details. Please try again later.", success=False), 500


@admin_api_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@admin_required
def update_order_status_admin(order_id): # Renamed
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    data = request.json
    new_status_str = sanitize_input(data.get('status'))
    tracking_number = sanitize_input(data.get('tracking_number'))
    carrier = sanitize_input(data.get('carrier'))
    
    if not new_status_str: return jsonify(message="New status not provided.", success=False), 400
    try:
        new_status_enum = OrderStatusEnum(new_status_str)
    except ValueError:
        return jsonify(message=f"Invalid status value: {new_status_str}", success=False), 400

    order = Order.query.get(order_id)
    if not order: return jsonify(message="Order not found.", success=False), 404
    
    old_status = order.status.value if order.status else "None"
    order.status = new_status_enum
    if new_status_enum in [OrderStatusEnum.SHIPPED, OrderStatusEnum.DELIVERED]:
        if tracking_number: order.tracking_number = tracking_number
        if carrier: order.shipping_method = carrier 
    
    try:
        order.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_order_status_admin_success', target_type='order', target_id=order_id, details=f"Order {order_id} status from '{old_status}' to '{new_status_enum.value}'. Tracking: {tracking_number or 'N/A'}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Order status updated to {new_status_enum.value}.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update order status for ID {order_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='update_order_status_admin_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update order status due to a server error.", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>/notes', methods=['POST'])
@admin_required
def add_order_note_admin(order_id): # Renamed
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    data = request.json; note_content_raw = data.get('note')
    note_content = sanitize_input(note_content_raw, allow_html=False) # Disallow HTML in internal notes

    if not note_content or not note_content.strip(): 
        return jsonify(message="Note content cannot be empty.", success=False), 400

    order = Order.query.get(order_id)
    if not order: return jsonify(message="Order not found.", success=False), 404
    
    admin_user = User.query.get(current_admin_id)
    admin_identifier = admin_user.email if admin_user else f"AdminID:{current_admin_id}"
    
    new_entry = f"[{format_datetime_for_display(datetime.now(timezone.utc))} by {admin_identifier}]: {note_content}"
    order.notes_internal = f"{order.notes_internal or ''}\n{new_entry}".strip()
    order.updated_at = datetime.now(timezone.utc)
    
    try:
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note_admin_success', target_type='order', target_id=order_id, details=f"Added note: '{note_content[:50]}...'", status='success', ip_address=request.remote_addr)
        return jsonify(message="Note added successfully.", new_note_entry=new_entry, success=True), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to add note to order ID {order_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note_admin_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to add note due to a server error.", success=False), 500

# backend/admin_api/routes.py (Continued - Review Management)
from ..models import Review, Product, User # Ensure Review model is imported

@admin_api_bp.route('/reviews', methods=['GET'])
@admin_required
def get_reviews_admin(): # Renamed
    status_filter_str = sanitize_input(request.args.get('status')) 
    product_filter = sanitize_input(request.args.get('product_id')) # Can be ID, name, or code
    user_filter = sanitize_input(request.args.get('user_id')) # Can be ID or email

    query = Review.query.join(Product, Review.product_id == Product.id)\
                        .join(User, Review.user_id == User.id)
    
    if status_filter_str == 'pending': query = query.filter(Review.is_approved == False)
    elif status_filter_str == 'approved': query = query.filter(Review.is_approved == True)
    
    if product_filter:
        if product_filter.isdigit():
            query = query.filter(Review.product_id == int(product_filter))
        else:
            term_like_prod = f"%{product_filter.lower()}%"
            query = query.filter(or_(func.lower(Product.name).like(term_like_prod), 
                                     func.lower(Product.product_code).like(term_like_prod)))
    if user_filter:
        if user_filter.isdigit():
            query = query.filter(Review.user_id == int(user_filter))
        else:
            query = query.filter(func.lower(User.email).like(f"%{user_filter.lower()}%"))
            
    try:
        reviews_models = query.order_by(Review.review_date.desc()).all()
        reviews_data = []
        for r in reviews_models:
            reviews_data.append({
                "id": r.id, "product_id": r.product_id, "user_id": r.user_id,
                "rating": r.rating, "comment": r.comment, # Comment is stored raw
                "review_date": format_datetime_for_display(r.review_date),
                "is_approved": r.is_approved,
                "product_name": r.product.name, "product_code": r.product.product_code,
                "user_email": r.user.email
            })
        return jsonify(reviews=reviews_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin reviews: {e}", exc_info=True)
        return jsonify(message="Failed to fetch reviews. Please try again later.", success=False), 500

def _update_review_approval_admin(review_id, is_approved_status):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    action_str = "approve" if is_approved_status else "unapprove"
    
    review = Review.query.get(review_id)
    if not review: return jsonify(message="Review not found.", success=False), 404
    
    review.is_approved = is_approved_status
    review.updated_at = datetime.now(timezone.utc) # Assuming Review model has updated_at
    try:
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action=f'{action_str}_review_admin_success', target_type='review', target_id=review_id, details=f"Review {review_id} set to approved={is_approved_status}.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Review successfully {action_str}d.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to {action_str} review ID {review_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action=f'{action_str}_review_admin_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to {action_str} review due to a server error.", success=False), 500

@admin_api_bp.route('/reviews/<int:review_id>/approve', methods=['PUT'])
@admin_required
def approve_review_admin(review_id): return _update_review_approval_admin(review_id, True)

@admin_api_bp.route('/reviews/<int:review_id>/unapprove', methods=['PUT'])
@admin_required
def unapprove_review_admin(review_id): return _update_review_approval_admin(review_id, False)

@admin_api_bp.route('/reviews/<int:review_id>', methods=['DELETE'])
@admin_required
def delete_review_admin(review_id): # Renamed
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    review = Review.query.get(review_id)
    if not review: return jsonify(message="Review not found.", success=False), 404
    try:
        db.session.delete(review)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin_success', target_type='review', target_id=review_id, details=f"Review {review_id} deleted.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Review deleted successfully.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete review ID {review_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete review due to a server error.", success=False), 500
        # backend/admin_api/routes.py (Continued - Settings Management)
from ..models import Setting # Ensure Setting model is imported

@admin_api_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings_admin(): # Renamed
    try:
        settings_models = Setting.query.all()
        settings_data = {s.key: {'value': s.value, 'description': s.description} for s in settings_models}
        return jsonify(settings=settings_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching settings for admin: {e}", exc_info=True)
        return jsonify(message="Failed to fetch settings. Please try again later.", success=False), 500

@admin_api_bp.route('/settings', methods=['POST']) # Using POST for create/update simplicity
@admin_required
def update_settings_admin(): # Renamed
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    data = request.json
    if not data: return jsonify(message="No settings data provided.", success=False), 400
    
    updated_keys = []
    try:
        for key, value_obj_or_direct_value in data.items():
            # Sanitize key to prevent unexpected characters if keys could be arbitrary
            safe_key = sanitize_input(str(key))
            if not safe_key: continue

            # Value can be a direct value or an object like {'value': '...', 'description': '...'}
            # For this API, assume frontend sends {'key1': 'value1', 'key2': 'value2'}
            # If frontend sends {'key1': {'value': 'value1'}}, adjust accordingly
            value_to_store = sanitize_input(str(value_obj_or_direct_value), allow_html=False) # Sanitize setting value, disallow HTML by default

            setting = Setting.query.get(safe_key)
            if setting:
                if setting.value != value_to_store:
                    setting.value = value_to_store
                    setting.updated_at = datetime.now(timezone.utc)
                    updated_keys.append(safe_key)
            else:
                # For creating new settings, a description might be useful if the form allows it.
                # If only value is sent, description would be None for new settings.
                db.session.add(Setting(key=safe_key, value=value_to_store, description=data.get(f"{safe_key}_description"))) # Example
                updated_keys.append(safe_key)
        
        if updated_keys:
            db.session.commit()
            audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin_success', target_type='application_settings', details=f"Settings updated: {', '.join(updated_keys)}", status='success', ip_address=request.remote_addr)
            return jsonify(message="Settings updated successfully.", updated_settings=updated_keys, success=True), 200
        else:
            return jsonify(message="No settings were changed.", success=True), 200
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update settings: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update settings due to a server error.", success=False), 500


@admin_api_bp.route('/assets/<path:asset_relative_path>')
@admin_required 
def serve_asset(asset_relative_path):
    # Security: Basic path validation
    if ".." in asset_relative_path or asset_relative_path.startswith("/"):
        current_app.logger.warning(f"Directory traversal attempt for admin asset: {asset_relative_path}")
        return flask_abort(404)

    # Map asset types to their base directories (absolute paths from config)
    asset_type_map = {
        'qr_codes': current_app.config.get('QR_CODE_FOLDER'),
        'labels': current_app.config.get('LABEL_FOLDER'),
        'invoices': current_app.config.get('INVOICE_PDF_PATH'),
        'professional_documents': current_app.config.get('PROFESSIONAL_DOCS_UPLOAD_PATH'),
        'products': os.path.join(current_app.config.get('UPLOAD_FOLDER'), 'products'), # For product images via admin
        'categories': os.path.join(current_app.config.get('UPLOAD_FOLDER'), 'categories') # For category images via admin
    }
    
    try:
        path_parts = asset_relative_path.split(os.sep, 1)
        asset_type_key = path_parts[0]
        filename_in_type_folder = path_parts[1] if len(path_parts) > 1 else None

        if asset_type_key in asset_type_map and filename_in_type_folder:
            base_path_abs = asset_type_map[asset_type_key]
            if not base_path_abs: # Check if config key returned None
                current_app.logger.error(f"Asset base path for type '{asset_type_key}' is not configured.")
                return flask_abort(404)

            # Construct full path and perform security check
            full_path = os.path.normpath(os.path.join(base_path_abs, filename_in_type_folder))
            
            # Ensure the resolved path is still within the intended base directory
            if not os.path.abspath(full_path).startswith(os.path.abspath(base_path_abs)):
                current_app.logger.error(f"Security violation: Attempt to access file outside designated admin asset directory. Requested: {full_path}, Base: {base_path_abs}")
                return flask_abort(404)

            if os.path.exists(full_path) and os.path.isfile(full_path):
                current_app.logger.debug(f"Serving admin asset: {filename_in_type_folder} from directory: {base_path_abs}")
                # send_from_directory needs the directory and the filename (which can include subpaths relative to that directory)
                return send_from_directory(base_path_abs, filename_in_type_folder)
        
        current_app.logger.warning(f"Admin asset not found or path not recognized: {asset_relative_path}")
        return flask_abort(404)
    except Exception as e:
        current_app.logger.error(f"Error serving admin asset '{asset_relative_path}': {e}", exc_info=True)
        return flask_abort(500)

# --- Admin B2B Quote Request Management ---
@admin_api_bp.route('/b2b/quote-requests', methods=['GET'])
@admin_required # Or @staff_or_admin_required
def admin_get_b2b_quote_requests():
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    status_filter = sanitize_input(request.args.get('status'))
    customer_search_filter = sanitize_input(request.args.get('customer_search'))
    date_filter = sanitize_input(request.args.get('date'))

    query = QuoteRequest.query.join(User, QuoteRequest.user_id == User.id)

    if status_filter:
        try:
            status_enum = QuoteRequestStatusEnum(status_filter)
            query = query.filter(QuoteRequest.status == status_enum)
        except ValueError:
            return jsonify(message=f"Invalid status filter: {status_filter}", success=False), 400
    
    if customer_search_filter:
        term_like = f"%{customer_search_filter.lower()}%"
        query = query.filter(
            or_(
                User.email.ilike(term_like),
                User.first_name.ilike(term_like),
                User.last_name.ilike(term_like),
                User.company_name.ilike(term_like)
            )
        )
    if date_filter:
        try:
            filter_date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(db.func.date(QuoteRequest.request_date) == filter_date_obj)
        except ValueError:
             return jsonify(message="Invalid date format for filter. Use YYYY-MM-DD.", success=False), 400


    try:
        paginated_quotes = query.order_by(QuoteRequest.request_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
        quotes_data = []
        for quote in paginated_quotes.items:
            quotes_data.append({
                "id": quote.id,
                "user_id": quote.user_id,
                "user_email": quote.user.email,
                "user_company_name": quote.user.company_name,
                "user_first_name": quote.user.first_name,
                "user_last_name": quote.user.last_name,
                "request_date": format_datetime_for_display(quote.request_date),
                "status": quote.status.value,
                "item_count": len(quote.items), # Efficiently count items if relationship is dynamic
                "admin_assigned_name": f"{quote.assigned_admin.first_name} {quote.assigned_admin.last_name}".strip() if quote.assigned_admin else None,
                "valid_until": format_datetime_for_display(quote.valid_until) if quote.valid_until else None,
                "contact_person": quote.contact_person,
                "contact_phone": quote.contact_phone,
                "notes": quote.notes, # Customer notes
                "admin_notes": quote.admin_notes # Admin internal notes
                # Potentially add a calculated estimated total if needed for list view
            })
        audit_logger.log_action(user_id=current_admin_id, action='admin_get_b2b_quotes', status='success', ip_address=request.remote_addr)
        return jsonify({
            "quotes": quotes_data,
            "pagination": {
                "current_page": paginated_quotes.page,
                "per_page": paginated_quotes.per_page,
                "total_items": paginated_quotes.total,
                "total_pages": paginated_quotes.pages
            },
            "success": True
        }), 200
    except Exception as e:
        current_app.logger.error(f"Admin error fetching B2B quote requests: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='admin_get_b2b_quotes_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to fetch B2B quote requests.", error=str(e), success=False), 500

@admin_api_bp.route('/b2b/quote-requests/<int:quote_id>', methods=['GET'])
@admin_required
def admin_get_b2b_quote_request_detail(quote_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        quote = QuoteRequest.query.get(quote_id)
        if not quote:
            return jsonify(message="Quote request not found.", success=False), 404

        items_data = []
        for item in quote.items:
            items_data.append({
                "id": item.id, # QuoteRequestItem ID
                "product_id": item.product_id,
                "variant_id": item.variant_id,
                "product_name_snapshot": item.product_name_snapshot or (item.product.name if item.product else "N/A"),
                "variant_description_snapshot": item.variant_description_snapshot or (f"{item.variant.weight_grams}g ({item.variant.sku_suffix})" if item.variant else None),
                "product_code_snapshot": item.product.product_code if item.product else "N/A",
                "quantity": item.quantity,
                "requested_price_ht": item.requested_price_ht,
                "quoted_price_ht": item.quoted_price_ht # Price admin proposes
            })
        
        quote_data = {
            "id": quote.id,
            "user_id": quote.user_id,
            "user_email": quote.user.email,
            "user_company_name": quote.user.company_name,
            "user_first_name": quote.user.first_name,
            "user_last_name": quote.user.last_name,
            "request_date": format_datetime_for_display(quote.request_date),
            "status": quote.status.value,
            "notes": quote.notes,
            "admin_notes": quote.admin_notes,
            "contact_person": quote.contact_person,
            "contact_phone": quote.contact_phone,
            "valid_until": format_datetime_for_storage(quote.valid_until) if quote.valid_until else None, # Send as YYYY-MM-DD for date input
            "admin_assigned_id": quote.admin_assigned_id,
            "admin_assigned_name": f"{quote.assigned_admin.first_name} {quote.assigned_admin.last_name}".strip() if quote.assigned_admin else None,
            "items": items_data
        }
        audit_logger.log_action(user_id=current_admin_id, action='admin_get_b2b_quote_detail', target_type='quote_request', target_id=quote_id, status='success', ip_address=request.remote_addr)
        return jsonify(quote=quote_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Admin error fetching B2B quote detail for ID {quote_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch quote request details.", error=str(e), success=False), 500


@admin_api_bp.route('/b2b/quote-requests/<int:quote_id>', methods=['PUT'])
@admin_required
def admin_update_b2b_quote_request(quote_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    data = request.json

    quote = QuoteRequest.query.get(quote_id)
    if not quote:
        return jsonify(message="Quote request not found.", success=False), 404

    new_status_str = sanitize_input(data.get('status'))
    admin_notes = sanitize_input(data.get('admin_notes'))
    valid_until_str = sanitize_input(data.get('valid_until'))
    items_proposed_prices = data.get('items', []) # list of {item_id, proposed_price_ht}

    try:
        if new_status_str:
            new_status_enum = QuoteRequestStatusEnum(new_status_str)
            quote.status = new_status_enum
        if admin_notes is not None: # Allow clearing notes
            quote.admin_notes = admin_notes
        if valid_until_str:
            quote.valid_until = datetime.strptime(valid_until_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        elif data.get('valid_until') == None: # Explicitly clearing the date
             quote.valid_until = None


        # Update proposed prices for items
        updated_item_ids = []
        for item_price_data in items_proposed_prices:
            qr_item_id = item_price_data.get('item_id')
            proposed_price = item_price_data.get('proposed_price_ht')
            if qr_item_id is not None and proposed_price is not None:
                qr_item = QuoteRequestItem.query.get(qr_item_id)
                if qr_item and qr_item.quote_request_id == quote.id:
                    qr_item.quoted_price_ht = float(proposed_price)
                    updated_item_ids.append(qr_item_id)
                else:
                    current_app.logger.warning(f"Admin tried to update price for non-existent/mismatched QuoteRequestItem ID {qr_item_id} in Quote {quote.id}")


        quote.updated_at = datetime.now(timezone.utc)
        quote.admin_assigned_id = current_admin_id # Mark who last updated it

        db.session.commit()

        # If status is 'sent_to_client', trigger email to B2B user
        if new_status_enum == QuoteRequestStatusEnum.SENT_TO_CLIENT:
            email_service = EmailService(current_app)
            client_email = quote.user.email
            subject = f"Votre Devis Maison Trüvra #{quote.id} est Prêt"
            # TODO: Create a proper HTML email template for quotes
            body = f"""
            Bonjour {quote.user.first_name or quote.user.company_name},

            Votre demande de devis #{quote.id} a été traitée.
            Vous pouvez consulter les détails et les prix proposés.
            Ce devis est valide jusqu'au {quote.valid_until.strftime('%d/%m/%Y') if quote.valid_until else 'N/A'}.

            Notes de notre équipe : {quote.admin_notes or 'Aucune'}

            Pour accepter ce devis ou discuter davantage, veuillez nous contacter.
            
            Cordialement,
            L'équipe Maison Trüvra
            """
            try:
                email_service.send_email(client_email, subject, body)
                current_app.logger.info(f"Quote #{quote.id} sent to client {client_email}.")
                audit_logger.log_action(user_id=current_admin_id, action='admin_sent_b2b_quote_email', target_type='quote_request', target_id=quote.id, status='success', ip_address=request.remote_addr)
            except Exception as e_mail_quote:
                 current_app.logger.error(f"Failed to send quote email for quote {quote.id} to {client_email}: {e_mail_quote}", exc_info=True)
                 audit_logger.log_action(user_id=current_admin_id, action='admin_sent_b2b_quote_email_fail', target_type='quote_request', target_id=quote.id, details=str(e_mail_quote), status='failure', ip_address=request.remote_addr)


        audit_logger.log_action(user_id=current_admin_id, action='admin_update_b2b_quote_status', target_type='quote_request', target_id=quote.id, details=f"Status to {new_status_enum.value}. Items updated: {len(updated_item_ids)}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Quote request updated successfully.", success=True), 200
    except ValueError as ve: # For bad enum
        db.session.rollback()
        return jsonify(message=f"Invalid data: {str(ve)}", success=False), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin error updating B2B quote request {quote_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='admin_update_b2b_quote_status_fail', target_type='quote_request', target_id=quote_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update quote request.", error=str(e), success=False), 500

@admin_api_bp.route('/b2b/quote-requests/<int:quote_id>/convert-to-order', methods=['POST'])
@admin_required
def admin_convert_quote_to_order(quote_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    quote = QuoteRequest.query.get(quote_id)
    if not quote:
        return jsonify(message="Quote request not found.", success=False), 404
    
    if quote.status != QuoteRequestStatusEnum.ACCEPTED_BY_CLIENT:
        audit_logger.log_action(user_id=current_admin_id, action='convert_quote_fail_status', target_type='quote_request', target_id=quote_id, details=f"Quote not in 'accepted_by_client' status (current: {quote.status.value}).", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Quote must be 'accepted_by_client' to be converted to an order.", success=False), 400
    
    if quote.related_order: # Check if already converted
        audit_logger.log_action(user_id=current_admin_id, action='convert_quote_fail_already_converted', target_type='quote_request', target_id=quote_id, details=f"Quote already linked to order ID {quote.related_order.id}.", status='info', ip_address=request.remote_addr)
        return jsonify(message="This quote has already been converted to an order.", order_id=quote.related_order.id, success=True), 200

    b2b_user = quote.user
    if not b2b_user: # Should not happen if quote has user_id
        return jsonify(message="Associated B2B user not found.", success=False), 500

    try:
        order_total_amount = 0
        order_items_to_create = []

        for qi_item in quote.items:
            if qi_item.quoted_price_ht is None: # Admin must have set a price
                db.session.rollback()
                audit_logger.log_action(user_id=current_admin_id, action='convert_quote_fail_missing_prices', target_type='quote_request', target_id=quote_id, details=f"Item {qi_item.id} missing quoted_price_ht.", status='failure', ip_address=request.remote_addr)
                return jsonify(message=f"All items in the quote must have a proposed price (quoted_price_ht) set by an admin before converting. Item ID: {qi_item.id}", success=False), 400

            item_total = qi_item.quoted_price_ht * qi_item.quantity
            order_total_amount += item_total
            order_items_to_create.append({
                "product_id": qi_item.product_id,
                "variant_id": qi_item.variant_id,
                "quantity": qi_item.quantity,
                "unit_price": qi_item.quoted_price_ht, # Use admin's quoted price
                "total_price": item_total,
                "product_name": qi_item.product_name_snapshot or (qi_item.product.name if qi_item.product else "N/A"),
                "variant_description": qi_item.variant_description_snapshot or (f"{qi_item.variant.weight_grams}g ({qi_item.variant.sku_suffix})" if qi_item.variant else None)
            })

        # Create the Order
        new_order = Order(
            user_id=b2b_user.id,
            is_b2b_order=True,
            status=OrderStatusEnum.ORDER_PENDING_APPROVAL, # Or straight to PROCESSING if no further approval needed
            total_amount=round(order_total_amount, 2), # This is HT for B2B orders from quotes
            currency=b2b_user.currency or 'EUR',
            quote_request_id=quote.id,
            # Populate shipping/billing from B2B user's profile or quote if it had specific addresses
            shipping_address_line1=b2b_user.shipping_address_line1 or b2b_user.company_address_line1 or 'N/A',
            # ... other address fields (ensure these are available on b2b_user or quote)
            shipping_city=b2b_user.shipping_city or b2b_user.company_city or 'N/A',
            shipping_postal_code=b2b_user.shipping_postal_code or b2b_user.company_postal_code or 'N/A',
            shipping_country=b2b_user.shipping_country or b2b_user.company_country or 'N/A',
            # Assuming billing is same as shipping for simplicity, or pull from user's billing fields
            billing_address_line1=b2b_user.billing_address_line1 or new_order.shipping_address_line1,
            # ...
            notes_internal=f"Order created from B2B Quote Request #{quote.id}. Admin: {current_admin_id}."
        )
        db.session.add(new_order)
        db.session.flush()

        for oi_data in order_items_to_create:
            db.session.add(OrderItem(order_id=new_order.id, **oi_data))
            # Stock movement for allocated items will occur when order status changes to processing/shipped
            # No stock movement here yet, as it's just an order created from a quote.

        quote.status = QuoteRequestStatusEnum.CONVERTED_TO_ORDER
        quote.related_order_id = new_order.id # Link order to quote
        quote.updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        audit_logger.log_action(user_id=current_admin_id, action='admin_convert_quote_to_order_success', target_type='order', target_id=new_order.id, details=f"Quote #{quote_id} converted to Order #{new_order.id}.", status='success', ip_address=request.remote_addr)
        
        # Optionally send notification to B2B user that their quote is now an order
        # email_service = EmailService(current_app)
        # ...

        return jsonify(message="Quote successfully converted to order.", order_id=new_order.id, success=True), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin error converting quote {quote_id} to order: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='admin_convert_quote_to_order_fail', target_type='quote_request', target_id=quote_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to convert quote to order.", error=str(e), success=False), 500


# --- Admin PO Management (Primarily viewing and updating status of orders created from POs) ---
# The PO upload itself creates an Order with a specific status (e.g., PENDING_PO_REVIEW).
# Admin uses the general Order Management UI to find these orders and update them.
# An endpoint to download the PO file associated with an order:
@admin_api_bp.route('/orders/<int:order_id}/purchase-order-file', methods=['GET'])
@admin_required
def download_order_po_file(order_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    order = Order.query.get(order_id)
    if not order:
        return jsonify(message="Order not found.", success=False), 404
    
    if not order.is_b2b_order or not order.po_file_path_stored: # Ensure it's a B2B order with a PO
        audit_logger.log_action(user_id=current_admin_id, action='download_po_file_fail_no_po', target_type='order', target_id=order_id, details="Order has no PO file attached.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="No Purchase Order file attached to this order.", success=False), 404

    # Assuming po_file_path_stored is relative to 'UPLOAD_FOLDER' or a subfolder like 'purchase_orders'
    # Example: 'purchase_orders/user_X_po_Y.pdf'
    # The serve_asset route should handle this correctly.
    try:
        # Using the existing admin_api_bp.serve_asset for protected file serving
        # The path for serve_asset should be relative to ASSET_STORAGE_PATH or UPLOAD_FOLDER based on its config.
        # If po_file_path_stored is 'purchase_orders/file.pdf' and ASSET_STORAGE_PATH points to 'instance/generated_assets'
        # but POs are in 'instance/uploads/purchase_orders', this needs alignment or a dedicated PO serving route.

        # For now, let's assume po_file_path_stored IS relative to a directory that serve_asset can handle,
        # like 'professional_documents/user_123_po_abc.pdf' if POs are stored there.
        # OR, if POs are in UPLOAD_FOLDER/purchase_orders, and serve_asset is configured for UPLOAD_FOLDER subdirs.

        # Simpler: directly use send_from_directory ensuring path is safe.
        # This requires po_file_path_stored to be just the filename if base_dir is the PO folder.
        
        po_upload_base_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'purchase_orders')
        # Assuming order.po_file_path_stored is just "filename.ext" and not "purchase_orders/filename.ext"
        # If it IS "purchase_orders/filename.ext", then base_dir should be UPLOAD_FOLDER
        # and filename_only would be "purchase_orders/filename.ext"
        
        # Let's assume po_file_path_stored is 'purchase_orders/user_X_po_Y.pdf'
        # and UPLOAD_FOLDER is the parent of 'purchase_orders'
        
        # Security: Ensure asset_relative_path does not allow traversal.
        # The serve_asset route in admin_api/routes.py has checks.
        # If po_file_path_stored is like "purchase_orders/xyz.pdf"
        # and serve_asset expects "purchase_orders" as asset_type_key:
        if ".." in order.po_file_path_stored or order.po_file_path_stored.startswith("/"):
             audit_logger.log_action(user_id=current_admin_id, action='download_po_file_fail_path', target_type='order', target_id=order_id, details="Invalid PO file path.", status='failure', ip_address=request.remote_addr)
             return jsonify(message="Invalid PO file path.", success=False), 400
        
        # If serve_asset is robust enough:
        # return redirect(url_for('admin_api_bp.serve_asset', asset_relative_path=order.po_file_path_stored))
        
        # Direct send_from_directory for more control here:
        directory = os.path.join(current_app.config['UPLOAD_FOLDER']) # Base is UPLOAD_FOLDER
        filename = order.po_file_path_stored # Assumes this path is relative to UPLOAD_FOLDER, e.g., "purchase_orders/file.pdf"
        
        full_path = os.path.normpath(os.path.join(directory, filename))
        if not full_path.startswith(os.path.normpath(directory) + os.sep):
            current_app.logger.error(f"Security violation: PO file path traversal. Path: {filename}")
            abort(404)

        audit_logger.log_action(user_id=current_admin_id, action='download_po_file_success', target_type='order', target_id=order_id, status='success', ip_address=request.remote_addr)
        return send_from_directory(directory, filename, as_attachment=True)

    except Exception as e:
        current_app.logger.error(f"Error downloading PO file for order {order_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='download_po_file_fail_exception', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to download Purchase Order file.", error=str(e), success=False), 500


# Endpoint for Admin to trigger B2B invoice generation for an order (e.g., after PO approval)
@admin_api_bp.route('/orders/<int:order_id>/generate-b2b-invoice', methods=['POST'])
@admin_required
def admin_generate_b2b_invoice_for_order(order_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    order = Order.query.get(order_id)
    if not order:
        return jsonify(message="Order not found.", success=False), 404
    if not order.is_b2b_order:
        audit_logger.log_action(user_id=current_admin_id, action='admin_gen_b2b_invoice_fail_not_b2b', target_type='order', target_id=order_id, status='failure', ip_address=request.remote_addr)
        return jsonify(message="This is not a B2B order.", success=False), 400
    if order.invoice:
        audit_logger.log_action(user_id=current_admin_id, action='admin_gen_b2b_invoice_fail_exists', target_type='order', target_id=order_id, details=f"Invoice {order.invoice.invoice_number} already exists.", status='info', ip_address=request.remote_addr)
        return jsonify(message=f"Invoice {order.invoice.invoice_number} already exists for this order.", invoice_id=order.invoice.id, success=True), 200 # Or 409 if considered an error

    # Ensure order is in a state where invoice can be generated (e.g., PO approved, processing)
    if order.status not in [OrderStatusEnum.PROCESSING, OrderStatusEnum.AWAITING_SHIPMENT, OrderStatusEnum.SHIPPED, OrderStatusEnum.DELIVERED, OrderStatusEnum.COMPLETED]:
        audit_logger.log_action(user_id=current_admin_id, action='admin_gen_b2b_invoice_fail_status', target_type='order', target_id=order_id, details=f"Order status {order.status.value} not suitable for invoicing.", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Cannot generate invoice for order with status '{order.status.value}'. Order should be at least 'Processing'.", success=False), 400

    try:
        invoice_service = InvoiceService()
        invoice_id, invoice_number = invoice_service.create_invoice_from_order(order.id, is_b2b_order=True, issued_by_admin_id=current_admin_id)
        
        if invoice_id:
            order.invoice_id = invoice_id # Ensure link is saved
            db.session.commit()
            audit_logger.log_action(user_id=current_admin_id, action='admin_gen_b2b_invoice_success', target_type='invoice', target_id=invoice_id, details=f"B2B Invoice {invoice_number} generated for order {order_id}.", status='success', ip_address=request.remote_addr)
            return jsonify(message=f"B2B Invoice {invoice_number} generated successfully.", invoice_id=invoice_id, invoice_number=invoice_number, success=True), 201
        else: # Should not happen if service throws error
             audit_logger.log_action(user_id=current_admin_id, action='admin_gen_b2b_invoice_fail_service', target_type='order', target_id=order_id, details="Invoice service did not return ID.", status='failure', ip_address=request.remote_addr)
             return jsonify(message="Invoice generation failed via service.", success=False), 500
    except ValueError as ve:
        db.session.rollback()
        return jsonify(message=str(ve), success=False), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin error generating B2B invoice for order {order_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='admin_gen_b2b_invoice_fail_exception', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to generate B2B invoice due to a server error.", error=str(e), success=False), 500


