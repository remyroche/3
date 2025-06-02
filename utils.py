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
from .database import get_db_connection, query_db 

# --- Email Validation and Sending ---
def is_valid_email(email):
    if not email:
        return False
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

def send_email_alert(subject, body, recipient_email=None):
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

# --- Decorators for Route Protection ---
def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try: verify_jwt_in_request()
        except Exception as e:
            current_app.logger.warning(f"Admin access denied for {request.path}: JWT verification failed - {e}")
            return jsonify(message="Access token is missing or invalid."), 401
        if hasattr(g, 'is_admin') and g.is_admin: return fn(*args, **kwargs)
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
        if hasattr(g, 'current_user_role') and g.current_user_role in allowed_roles: return fn(*args, **kwargs)
        claims = get_jwt()
        if claims.get('role') in allowed_roles: return fn(*args, **kwargs)
        else:
            current_app.logger.warning(f"Staff/Admin access denied for {request.path}: Role not in {allowed_roles}.")
            return jsonify(message="Administration or staff rights required."), 403
    wrapper.__name__ = fn.__name__
    return wrapper

# --- File Handling ---
def allowed_file(filename, allowed_extensions_config_key='ALLOWED_EXTENSIONS'):
    allowed_extensions = current_app.config.get(allowed_extensions_config_key, {'png', 'jpg', 'jpeg', 'gif', 'pdf'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_file_extension(filename):
    if '.' in filename: return filename.rsplit('.', 1)[1].lower()
    return ''

# --- String Manipulation ---
def generate_slug(text):
    if not text: return ""
    text = unidecode(str(text)); text = re.sub(r'[^\w\s-]', '', text).strip().lower(); text = re.sub(r'[-\s]+', '-', text)
    return text

# --- Date and Time Formatting/Parsing ---
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

# --- Static JSON Generation for Build Process ---
def generate_static_json_files():
    if not current_app:
        print("Cannot generate static files: Flask app context is not available.")
        return
    with current_app.app_context():
        current_app.logger.info("Starting generation of static JSON files for products and categories.")
        db = get_db_connection()
        
        try:
            products_data = query_db(
                """SELECT p.id, p.name, p.slug, p.sku_prefix, p.description, p.base_price, p.currency, 
                          p.main_image_url, p.type, p.is_featured, p.brand, c.name as category_name, c.slug as category_slug
                   FROM products p 
                   LEFT JOIN categories c ON p.category_id = c.id 
                   WHERE p.is_active = TRUE 
                   ORDER BY p.name""", db_conn=db)
            products_list = [dict(row) for row in products_data] if products_data else []
            for product in products_list:
                if product.get('main_image_url'):
                    # Use 'serve_public_asset' for URLs in static JSONs
                    product['main_image_full_url'] = url_for('serve_public_asset', filepath=product['main_image_url'], _external=True)
                if product['type'] == 'variable_weight':
                    options_data = query_db(
                        """SELECT id as option_id, weight_grams, price, sku_suffix, aggregate_stock_quantity as stock_quantity, is_active
                           FROM product_weight_options WHERE product_id = ? AND is_active = TRUE ORDER BY weight_grams""", 
                        [product['id']], db_conn=db)
                    product['variants'] = [dict(opt) for opt in options_data] if options_data else []
                else: product['stock_quantity'] = product.get('aggregate_stock_quantity', 0)
                images_data = query_db(
                    "SELECT image_url, alt_text FROM product_images WHERE product_id = ? AND is_primary = FALSE ORDER BY id", 
                    [product['id']], db_conn=db)
                product['additional_images'] = []
                if images_data:
                    for img_row in images_data:
                        img_dict = dict(img_row)
                        if img_dict.get('image_url'):
                            # Use 'serve_public_asset' for URLs in static JSONs
                            img_dict['image_full_url'] = url_for('serve_public_asset', filepath=img_dict['image_url'], _external=True)
                        product['additional_images'].append(img_dict)
            data_dir = os.path.join(current_app.root_path, 'website', 'source', 'data')
            os.makedirs(data_dir, exist_ok=True)
            products_file_path = os.path.join(data_dir, 'products_details.json')
            with open(products_file_path, 'w', encoding='utf-8') as f:
                json.dump(products_list, f, ensure_ascii=False, indent=4)
            current_app.logger.info(f"Successfully generated {products_file_path}")
        except Exception as e:
            current_app.logger.error(f"Failed to generate products_details.json: {e}", exc_info=True)

        try:
            categories_data = query_db(
                "SELECT id, name, slug, description, image_url, parent_id FROM categories WHERE is_active = TRUE ORDER BY name", db_conn=db)
            categories_list = [dict(row) for row in categories_data] if categories_data else []
            for category in categories_list:
                 if category.get('image_url'):
                    # Use 'serve_public_asset' for URLs in static JSONs
                    category['image_full_url'] = url_for('serve_public_asset', filepath=category['image_url'], _external=True)
            data_dir = os.path.join(current_app.root_path, 'website', 'source', 'data') # Ensure data_dir is defined here too
            os.makedirs(data_dir, exist_ok=True)
            categories_file_path = os.path.join(data_dir, 'categories_details.json')
            with open(categories_file_path, 'w', encoding='utf-8') as f:
                json.dump(categories_list, f, ensure_ascii=False, indent=4)
            current_app.logger.info(f"Successfully generated {categories_file_path}")
        except Exception as e:
            current_app.logger.error(f"Failed to generate categories_details.json: {e}", exc_info=True)
