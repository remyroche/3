# backend/utils.py
import re
import smtplib 
import os
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, jsonify, g, request, url_for
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity
from functools import wraps
from unidecode import unidecode
from datetime import datetime, timezone, timedelta

# Import db and models for generate_static_json_files
from . import db 
from .models import Product, Category, ProductWeightOption, ProductImage, ProductLocalization, CategoryLocalization

# --- Sanitization Helper ---
def sanitize_input(value, allow_html=False, max_length=None):
    """
    Basic input sanitizer.
    - Strips leading/trailing whitespace.
    - Optionally removes HTML tags (very basic, for more robust use a library like bleach).
    - Optionally truncates to max_length.
    """
    if value is None:
        return None
    
    value_str = str(value).strip()
    
    if not allow_html:
        # Basic HTML tag stripping - NOT for security against XSS if rendered as HTML.
        # For security, use libraries like Bleach on output or a stricter input validation.
        # This is more for cleaning up accidental simple HTML.
        value_str = re.sub(r'<[^>]*>', '', value_str)
    
    if max_length is not None and len(value_str) > max_length:
        value_str = value_str[:max_length]
        # Optionally log truncation:
        # current_app.logger.debug(f"Input truncated to {max_length} chars: {value_str[:30]}...")

    return value_str

# --- Constants for Selective Field Export ---
# Define which fields to include in the public JSON for products
# This helps keep the JSON lean and only exposes necessary data.
PRODUCT_EXPORT_FIELDS = [
    'id', 'name', 'slug', 'sku_prefix', 'description', 'base_price', 'currency',
    'main_image_url', 'type', 'is_featured', 'brand',
    'category_name', 'category_slug', 'category_code', # From joined Category
    'main_image_full_url', 'aggregate_stock_quantity' # Added for simple products
    # 'long_description', 'meta_title', 'meta_description' # Example of fields to potentially exclude
]
PRODUCT_VARIANT_EXPORT_FIELDS = [
    'option_id', 'weight_grams', 'price', 'sku_suffix', 'aggregate_stock_quantity'
]
PRODUCT_IMAGE_EXPORT_FIELDS = [
    'id', 'image_url', 'alt_text', 'is_primary', 'image_full_url'
]

# Define which fields to include for categories
CATEGORY_EXPORT_FIELDS = [
    'id', 'name', 'slug', 'category_code', 'description', 'image_url',
    'parent_id', 'image_full_url', 'product_count'
    # 'species_fr', 'species_en', etc. for categories_details.json if that's a different file/purpose
]

def is_valid_email(email):
    if not email:
        return False
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

def send_email_alert(subject, body, recipient_email=None):
    # (Keep existing send_email_alert logic)
    current_app.logger.warning(f"Attempting to send email via basic smtplib (not recommended for production). Subject: {subject}")
    if not current_app.config.get('MAIL_SERVER'):
        current_app.logger.error("Mail server not configured. Cannot send email alert.")
        return False
    sender_email = current_app.config.get('MAIL_USERNAME') 
    sender_password = current_app.config.get('MAIL_PASSWORD')
    mail_recipient = recipient_email or current_app.config.get('ADMIN_EMAIL')
    if not sender_email or not mail_recipient:
        current_app.logger.error("Mail sender or recipient not fully configured. Cannot send email alert.")
        return False
    msg_obj = MIMEMultipart()
    msg_obj['From'] = current_app.config.get('MAIL_DEFAULT_SENDER', sender_email)
    msg_obj['To'] = mail_recipient
    msg_obj['Subject'] = subject
    msg_obj.attach(MIMEText(body, 'plain')) 
    try:
        mail_port = current_app.config.get('MAIL_PORT', 587)
        use_tls = current_app.config.get('MAIL_USE_TLS', True)
        use_ssl = current_app.config.get('MAIL_USE_SSL', False)
        if use_ssl: server = smtplib.SMTP_SSL(current_app.config['MAIL_SERVER'], mail_port)
        else: server = smtplib.SMTP(current_app.config['MAIL_SERVER'], mail_port)
        if use_tls and not use_ssl: server.starttls()
        if sender_password: server.login(sender_email, sender_password)
        text_to_send = msg_obj.as_string()
        server.sendmail(msg_obj['From'], mail_recipient, text_to_send)
        server.quit()
        current_app.logger.info(f"Basic email alert '{subject}' sent successfully to {mail_recipient}.")
        return True
    except Exception as e:
        current_app.logger.error(f"Basic smtplib failed to send email alert '{subject}' to {mail_recipient}: {e}", exc_info=True)
        return False

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try: verify_jwt_in_request()
        except Exception as e:
            current_app.logger.warning(f"Admin access denied for {request.path}: JWT verification failed - {e}")
            return jsonify(message="Access token is missing or invalid."), 401
        # g.is_admin is set in @app.before_request in __init__.py
        if hasattr(g, 'is_admin') and g.is_admin: return fn(*args, **kwargs)
        # Fallback check on claims if g.is_admin wasn't set for some reason (shouldn't happen)
        claims = get_jwt()
        if claims.get('role') == 'admin': return fn(*args, **kwargs)
        else:
            current_app.logger.warning(f"Admin access denied for {request.path}: Role is not admin.")
            return jsonify(message="Administration rights required."), 403
    wrapper.__name__ = fn.__name__ 
    return wrapper

def staff_or_admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try: verify_jwt_in_request()
        except Exception as e:
            current_app.logger.warning(f"Staff/Admin access denied for {request.path}: JWT verification failed - {e}")
            return jsonify(message="Access token is missing or invalid."), 401
        allowed_roles = ['admin', 'staff'] 
        # g.current_user_role is set in @app.before_request
        if hasattr(g, 'current_user_role') and g.current_user_role in allowed_roles: return fn(*args, **kwargs)
        # Fallback check on claims
        claims = get_jwt()
        if claims.get('role') in allowed_roles: return fn(*args, **kwargs)
        else:
            current_app.logger.warning(f"Staff/Admin access denied for {request.path}: Role not in {allowed_roles}.")
            return jsonify(message="Administration or staff rights required."), 403
    wrapper.__name__ = fn.__name__
    return wrapper

def allowed_file(filename, allowed_extensions_config_key='ALLOWED_EXTENSIONS'):
    allowed_extensions = current_app.config.get(allowed_extensions_config_key, {'png', 'jpg', 'jpeg', 'gif', 'pdf'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_file_extension(filename):
    if '.' in filename: return filename.rsplit('.', 1)[1].lower()
    return ''

def generate_slug(text):
    if not text: return ""
    text = unidecode(str(text)); text = re.sub(r'[^\w\s-]', '', text).strip().lower(); text = re.sub(r'[-\s]+', '-', text)
    return text

def format_datetime_for_display(dt_obj_or_str, fmt='%Y-%m-%d %H:%M:%S'):
    if not dt_obj_or_str: return None
    dt_obj = None
    if isinstance(dt_obj_or_str, str):
        try: dt_str_normalized = dt_obj_or_str.replace('Z', '+00:00'); dt_obj = datetime.fromisoformat(dt_str_normalized)
        except ValueError:
            common_formats = ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']
            for date_fmt in common_formats:
                try: dt_obj = datetime.strptime(dt_obj_or_str, date_fmt); break 
                except ValueError: continue
            if not dt_obj:
                current_app.logger.debug(f"Could not parse date string for display: {dt_obj_or_str}")
                return dt_obj_or_str 
    elif isinstance(dt_obj_or_str, datetime): dt_obj = dt_obj_or_str
    else: return str(dt_obj_or_str) 
    return dt_obj.strftime(fmt)

def parse_datetime_from_iso(iso_str):
    if not iso_str: return None
    try:
        dt_str_normalized = iso_str.replace('Z', '+00:00'); dt_obj = datetime.fromisoformat(dt_str_normalized)
        if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None: return dt_obj.replace(tzinfo=timezone.utc)
        return dt_obj.astimezone(timezone.utc) 
    except ValueError as e:
        current_app.logger.warning(f"Failed to parse ISO datetime string '{iso_str}': {e}")
        try: dt_obj = datetime.strptime(iso_str, '%Y-%m-%d'); return dt_obj.replace(tzinfo=timezone.utc) 
        except ValueError: return None 

def format_datetime_for_storage(dt_obj=None):
    if dt_obj is None: dt_obj = datetime.now(timezone.utc)
    if not isinstance(dt_obj, datetime):
        if isinstance(dt_obj, str):
            parsed_dt = parse_datetime_from_iso(dt_obj)
            if parsed_dt: dt_obj = parsed_dt
            else: return None 
        else: return None 
    if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None: dt_obj = dt_obj.replace(tzinfo=timezone.utc) 
    else: dt_obj = dt_obj.astimezone(timezone.utc) 
    return dt_obj.isoformat(timespec='seconds') 


def generate_static_json_files():
    """
    Generates static JSON files for products and categories.
    Implements selective field export and per-item error handling.
    """
    if not current_app:
        print("Cannot generate static files: Flask app context is not available.")
        return

    with current_app.app_context():
        current_app.logger.info("Starting generation of static JSON files for products and categories (SQLAlchemy version).")
        
        # --- Products JSON ---
        products_list = []
        product_generation_errors = []
        try:
            products_models = Product.query.filter_by(is_active=True).order_by(Product.name).all()
            for p_model in products_models:
                try:
                    product_dict = {field: getattr(p_model, field, None) for field in PRODUCT_EXPORT_FIELDS if hasattr(p_model, field)}
                    
                    # Add related/calculated fields explicitly
                    product_dict['id'] = p_model.id # Ensure ID is always present
                    product_dict['name'] = p_model.name # Ensure name is present
                    product_dict['slug'] = p_model.slug

                    if p_model.category:
                        product_dict['category_name'] = p_model.category.name
                        product_dict['category_slug'] = p_model.category.slug
                        product_dict['category_code'] = p_model.category.category_code
                    else:
                        product_dict['category_name'] = None
                        product_dict['category_slug'] = None
                        product_dict['category_code'] = None

                    if p_model.main_image_url:
                        try:
                            product_dict['main_image_full_url'] = url_for('serve_public_asset', filepath=p_model.main_image_url, _external=True)
                        except Exception as e_url:
                            current_app.logger.warning(f"Could not generate URL for product main image {p_model.main_image_url} (ID: {p_model.id}): {e_url}")
                            product_dict['main_image_full_url'] = None # Fallback
                    else:
                        product_dict['main_image_full_url'] = None

                    product_dict['weight_options'] = []
                    if p_model.type == ProductTypeEnum.VARIABLE_WEIGHT: # Assuming ProductTypeEnum is defined
                        options_models = p_model.weight_options.filter_by(is_active=True).order_by(ProductWeightOption.weight_grams).all()
                        for opt in options_models:
                            variant_data = {v_field: getattr(opt, v_field, None) for v_field in PRODUCT_VARIANT_EXPORT_FIELDS if hasattr(opt, v_field)}
                            variant_data['option_id'] = opt.id # Ensure option_id is present
                            product_dict['weight_options'].append(variant_data)
                    
                    product_dict['additional_images'] = []
                    for img_model in p_model.images.filter_by(is_primary=False).order_by(ProductImage.id).all():
                        img_data = {img_field: getattr(img_model, img_field, None) for img_field in PRODUCT_IMAGE_EXPORT_FIELDS if hasattr(img_model, img_field)}
                        img_data['id'] = img_model.id # Ensure id is present
                        if img_model.image_url:
                            try:
                                img_data['image_full_url'] = url_for('serve_public_asset', filepath=img_model.image_url, _external=True)
                            except Exception as e_img_url:
                                current_app.logger.warning(f"Could not generate URL for additional image {img_model.image_url} (Product ID: {p_model.id}): {e_img_url}")
                                img_data['image_full_url'] = None
                        product_dict['additional_images'].append(img_data)
                    
                    # Add localized fields (example for name and description)
                    # This assumes ProductLocalization model and relationships are set up
                    loc_fr = p_model.localizations.filter_by(lang_code='fr').first()
                    loc_en = p_model.localizations.filter_by(lang_code='en').first()
                    product_dict['name_fr'] = loc_fr.name_fr if loc_fr and loc_fr.name_fr else p_model.name
                    product_dict['name_en'] = loc_en.name_en if loc_en and loc_en.name_en else p_model.name
                    product_dict['description_fr'] = loc_fr.description_fr if loc_fr and loc_fr.description_fr else p_model.description
                    product_dict['description_en'] = loc_en.description_en if loc_en and loc_en.description_en else p_model.description
                    # Add other localized fields as needed, checking PRODUCT_EXPORT_FIELDS

                    products_list.append(product_dict)
                except Exception as e_item:
                    error_detail = f"Failed to process product ID {p_model.id} ({p_model.name}): {str(e_item)}"
                    current_app.logger.error(error_detail, exc_info=True)
                    product_generation_errors.append(error_detail)
                    continue # Skip this product and continue with others

            data_dir = os.path.join(current_app.root_path, 'website', 'source', 'data')
            os.makedirs(data_dir, exist_ok=True)
            products_file_path = os.path.join(data_dir, 'products_details.json')
            with open(products_file_path, 'w', encoding='utf-8') as f:
                json.dump(products_list, f, ensure_ascii=False, indent=4)
            current_app.logger.info(f"Successfully generated {products_file_path} with {len(products_list)} products.")
            if product_generation_errors:
                current_app.logger.warning(f"Encountered {len(product_generation_errors)} errors during product JSON generation. See logs for details.")

        except Exception as e_global_prod:
            current_app.logger.error(f"Critical error during products_details.json generation: {e_global_prod}", exc_info=True)
            product_generation_errors.append(f"Global error in product generation: {str(e_global_prod)}")


        # --- Categories JSON ---
        categories_list = []
        category_generation_errors = []
        try:
            categories_models = Category.query.filter_by(is_active=True).order_by(Category.name).all()
            for cat_model in categories_models:
                try:
                    cat_dict = {field: getattr(cat_model, field, None) for field in CATEGORY_EXPORT_FIELDS if hasattr(cat_model, field)}
                    cat_dict['id'] = cat_model.id # Ensure ID
                    cat_dict['name'] = cat_model.name # Ensure name

                    if cat_model.image_url:
                        try:
                            cat_dict['image_full_url'] = url_for('serve_public_asset', filepath=cat_model.image_url, _external=True)
                        except Exception as e_url:
                            current_app.logger.warning(f"Could not generate URL for category image {cat_model.image_url} (ID: {cat_model.id}): {e_url}")
                            cat_dict['image_full_url'] = None
                    else:
                        cat_dict['image_full_url'] = None
                    
                    cat_dict['product_count'] = cat_model.products.filter_by(is_active=True).count()

                    # Add localized fields (example for name and description)
                    loc_fr_cat = cat_model.localizations.filter_by(lang_code='fr').first()
                    loc_en_cat = cat_model.localizations.filter_by(lang_code='en').first()
                    cat_dict['name_fr'] = loc_fr_cat.name_fr if loc_fr_cat and loc_fr_cat.name_fr else cat_model.name
                    cat_dict['name_en'] = loc_en_cat.name_en if loc_en_cat and loc_en_cat.name_en else cat_model.name
                    cat_dict['description_fr'] = loc_fr_cat.description_fr if loc_fr_cat and loc_fr_cat.description_fr else cat_model.description
                    cat_dict['description_en'] = loc_en_cat.description_en if loc_en_cat and loc_en_cat.description_en else cat_model.description
                    # Add other localized fields as needed, checking CATEGORY_EXPORT_FIELDS

                    categories_list.append(cat_dict)
                except Exception as e_item_cat:
                    error_detail = f"Failed to process category ID {cat_model.id} ({cat_model.name}): {str(e_item_cat)}"
                    current_app.logger.error(error_detail, exc_info=True)
                    category_generation_errors.append(error_detail)
                    continue # Skip this category

            # data_dir already created or checked above
            categories_file_path = os.path.join(data_dir, 'categories_details.json')
            with open(categories_file_path, 'w', encoding='utf-8') as f:
                json.dump(categories_list, f, ensure_ascii=False, indent=4)
            current_app.logger.info(f"Successfully generated {categories_file_path} with {len(categories_list)} categories.")
            if category_generation_errors:
                current_app.logger.warning(f"Encountered {len(category_generation_errors)} errors during category JSON generation. See logs for details.")

        except Exception as e_global_cat:
            current_app.logger.error(f"Critical error during categories_details.json generation: {e_global_cat}", exc_info=True)
            category_generation_errors.append(f"Global error in category generation: {str(e_global_cat)}")
        
        # Return status or list of errors if needed by caller
        return {
            "product_errors": product_generation_errors,
            "categor
