# backend/__init__.py
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, g, jsonify, send_from_directory, current_app, abort as flask_abort
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity, get_jwt
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from .config import get_config_by_name
from .audit_log_service import AuditLogService

# Initialize extensions without app object yet
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager() # Initialize JWTManager
limiter = Limiter(key_func=get_remote_address) # Initialize Limiter
talisman = Talisman() # Initialize Talisman

def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    
    app_config = get_config_by_name(config_name)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_static_folder = os.path.join(project_root, 'website', 'source', 'static_assets')
    if not os.path.exists(default_static_folder):
        default_static_folder = os.path.join(project_root, 'static_assets')
        if not os.path.exists(default_static_folder):
            os.makedirs(default_static_folder, exist_ok=True)

    app = Flask(__name__,
                instance_path=os.path.join(project_root, 'instance'),
                static_folder=getattr(app_config, 'STATIC_FOLDER', default_static_folder),
                static_url_path=getattr(app_config, 'STATIC_URL_PATH', '/static'))

    app.config.from_object(app_config)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        pass 

    # --- Logging Configuration ---
    log_level_str = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    if not app.debug and not app.testing:
        log_file = app.config.get('LOG_FILE')
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024 * 100, backupCount=20)
            file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
            file_handler.setLevel(log_level)
            if not app.logger.handlers: app.logger.addHandler(file_handler)
        else:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
            stream_handler.setLevel(log_level)
            if not app.logger.handlers: app.logger.addHandler(stream_handler)
        app.logger.setLevel(log_level)
    elif app.debug:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        if not app.logger.handlers: app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.DEBUG)
    
    app.logger.info(f"Maison Trüvra App starting with config: {config_name}")
    app.logger.info(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    app.logger.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    
    # Initialize extensions with app object
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    
    talisman_config = {
        'content_security_policy': app.config.get('CONTENT_SECURITY_POLICY'),
        'force_https': app.config.get('TALISMAN_FORCE_HTTPS', False),
        'strict_transport_security': app.config.get('TALISMAN_FORCE_HTTPS', False),
        'session_cookie_secure': app.config.get('JWT_COOKIE_SECURE', False),
        'session_cookie_samesite': app.config.get('JWT_COOKIE_SAMESITE', 'Lax'),
        'frame_options': 'DENY',
        'referrer_policy': 'strict-origin-when-cross-origin',
    }
    talisman.init_app(app, **talisman_config)

    CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", "*").split(',')}})
    app.logger.info(f"CORS configured for origins: {app.config.get('CORS_ORIGINS', '*')}")

    # Initialize AuditLogService (needs db to be initialized)
    app.audit_log_service = AuditLogService(app=app)
    app.logger.info("AuditLogService initialized and attached to app.")

    # Import and register models here so Flask-Migrate can find them
    from . import models 

    # Register Blueprints
    from .auth.routes import auth_bp
    app.register_blueprint(auth_bp)
    limiter.limit(app.config.get('AUTH_RATELIMITS', "20 per minute"))(auth_bp)

    from .products.routes import products_bp
    app.register_blueprint(products_bp)

    from .orders.routes import orders_bp
    app.register_blueprint(orders_bp)
    
    from .newsletter.routes import newsletter_bp
    app.register_blueprint(newsletter_bp)
    limiter.limit(app.config.get('NEWSLETTER_RATELIMITS', "10 per minute"))(newsletter_bp)

    from .inventory.routes import inventory_bp
    app.register_blueprint(inventory_bp)

    from .admin_api.routes import admin_api_bp
    app.register_blueprint(admin_api_bp)
    limiter.limit(app.config.get('ADMIN_API_RATELIMITS', "200 per hour"))(admin_api_bp)
    
    from .professional.routes import professional_bp
    app.register_blueprint(professional_bp)

    app.logger.info("Blueprints registered.")

    # Remove old database.py CLI commands
    # from .database import register_db_commands # This line should be removed or adapted
    # register_db_commands(app) # This would be replaced by Flask-Migrate commands

    # Add Flask-Migrate CLI commands (they are usually available via `flask db`)
    # No explicit registration needed here for standard `flask db` commands.

    @app.before_request
    def load_user_from_token_if_present():
        g.current_user_id = None
        g.current_user_role = None
        g.is_admin = False 
        try:
            verify_jwt_in_request(optional=True)
            current_user_identity = get_jwt_identity() 
            if current_user_identity:
                g.current_user_id = current_user_identity
                claims = get_jwt() 
                if claims:
                    g.current_user_role = claims.get('role')
                    g.is_admin = (claims.get('role') == 'admin')
        except Exception: 
            pass

    # --- API Root and Public Asset Serving ---
    @app.route('/')
    @app.route('/api')
    def api_root():
        return jsonify({
            "message": "Welcome to the Maison Trüvra API!",
            "version": app.config.get("API_VERSION", "1.0.0"),
            "documentation_url": "/api/docs" 
        })

    @app.route('/public-assets/<path:filepath>')
    def serve_public_asset(filepath):
        if ".." in filepath or filepath.startswith("/"):
            app.logger.warning(f"Directory traversal attempt for public asset: {filepath}")
            return flask_abort(404)
        
        base_serve_path = None
        actual_filename = filepath

        if filepath.startswith('products/'):
            base_serve_path = os.path.join(app.config['UPLOAD_FOLDER'], 'products')
            actual_filename = filepath[len('products/'):]
        elif filepath.startswith('categories/'):
            base_serve_path = os.path.join(app.config['UPLOAD_FOLDER'], 'categories')
            actual_filename = filepath[len('categories/'):]
        elif filepath.startswith('passports/'):
            base_serve_path = os.path.join(app.config['ASSET_STORAGE_PATH'], 'passports')
            actual_filename = filepath[len('passports/'):]
        
        if base_serve_path:
            requested_path_full = os.path.normpath(os.path.join(base_serve_path, actual_filename))
            if not requested_path_full.startswith(os.path.normpath(base_serve_path) + os.sep) and requested_path_full != os.path.normpath(base_serve_path) :
                app.logger.error(f"Security violation: Attempt to access file outside designated public asset directory. Requested: {requested_path_full}, Base: {base_serve_path}")
                return flask_abort(404)
            if os.path.exists(requested_path_full) and os.path.isfile(requested_path_full):
                app.logger.debug(f"Serving public asset: {actual_filename} from {base_serve_path}")
                return send_from_directory(base_serve_path, actual_filename)
        
        app.logger.warning(f"Public asset not found or path not recognized: {filepath}")
        return flask_abort(404)

    # --- Error Handlers ---
    @app.errorhandler(400)
    def bad_request_error(error): return jsonify(message=str(error.description if hasattr(error, 'description') else "Bad Request"), success=False), 400
    @app.errorhandler(401)
    def unauthorized_error(error): return jsonify(message=str(error.description if hasattr(error, 'description') else "Unauthorized"), success=False), 401
    @app.errorhandler(403)
    def forbidden_error(error): return jsonify(message=str(error.description if hasattr(error, 'description') else "Forbidden"), success=False), 403
    @app.errorhandler(404)
    def not_found_error(error): return jsonify(message=str(error.description if hasattr(error, 'description') else "Resource not found"), success=False), 404
    @app.errorhandler(429)
    def ratelimit_handler(e): return jsonify(message=f"Rate limit exceeded: {e.description}", success=False), 429
    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error(f"Internal Server Error: {error}", exc_info=True)
        return jsonify(message="An internal server error occurred. Please try again later.", success=False), 500

    return app

    

    @app.route('/')
    @app.route('/api')
    def api_root():
        return jsonify({
            "message": "Welcome to the Maison Trüvra API!",
            "version": app.config.get("API_VERSION", "1.0.0"),
            "documentation_url": "/api/docs" # Placeholder for API docs
        })

    # --- Consolidated Public Asset Serving ---
    @app.route('/public-assets/<path:filepath>')
    def serve_public_asset(filepath):
        # Security: Prevent directory traversal and ensure path is normalized
        if ".." in filepath or filepath.startswith("/"):
            app.logger.warning(f"Directory traversal attempt for public asset: {filepath}")
            return flask_abort(404)

        # Define base directories for different types of public assets
        # These paths should be relative to the UPLOAD_FOLDER or ASSET_STORAGE_PATH
        # or a dedicated public asset directory configured in app.config
        
        # Example: Product and category images are in UPLOAD_FOLDER/products and UPLOAD_FOLDER/categories
        # Example: Public passports are in ASSET_STORAGE_PATH/passports
        
        # Determine which base directory to use based on the filepath prefix
        # This logic needs to be robust.
        
        base_serve_path = None
        actual_filename = filepath

        if filepath.startswith('products/'):
            base_serve_path = os.path.join(app.config['UPLOAD_FOLDER'], 'products')
            actual_filename = filepath[len('products/'):]
        elif filepath.startswith('categories/'):
            base_serve_path = os.path.join(app.config['UPLOAD_FOLDER'], 'categories')
            actual_filename = filepath[len('categories/'):]
        elif filepath.startswith('passports/'): # Public passports
            base_serve_path = os.path.join(app.config['ASSET_STORAGE_PATH'], 'passports')
            actual_filename = filepath[len('passports/'):]
        # Add more conditions for other public asset types if needed
        
        if base_serve_path:
            # Final security check on the resolved path
            requested_path_full = os.path.join(base_serve_path, actual_filename)
            if not os.path.realpath(requested_path_full).startswith(os.path.realpath(base_serve_path)):
                app.logger.error(f"Security violation: Attempt to access file outside designated public asset directory. Requested: {requested_path_full}, Base: {base_serve_path}")
                return flask_abort(404)

            if os.path.exists(requested_path_full) and os.path.isfile(requested_path_full):
                app.logger.debug(f"Serving public asset: {actual_filename} from {base_serve_path}")
                return send_from_directory(base_serve_path, actual_filename)
        
        app.logger.warning(f"Public asset not found or path not recognized: {filepath}")
        return flask_abort(404)

    # Keep the original serve_passport_public if it has very specific logic not covered above,
    # otherwise, it can be removed if /public-assets/passports/... works.
    # For now, I'll comment it out, assuming the new route handles it.
    # @app.route('/assets/passports/<path:filename>')
    # def serve_passport_public(filename):
    #     passport_dir = os.path.join(app.config['ASSET_STORAGE_PATH'], 'passports')
    #     app.logger.debug(f"Attempting to serve public passport: {filename} from {passport_dir}")
    #     if ".." in filename or filename.startswith("/"):
    #         return flask_abort(404)
    #     return send_from_directory(passport_dir, filename, as_attachment=False)

    # Centralized error handlers
    @app.errorhandler(400)
    def bad_request_error(error):
        return jsonify(message=str(error.description if hasattr(error, 'description') else "Bad Request"), success=False), 400

    @app.errorhandler(401)
    def unauthorized_error(error):
        return jsonify(message=str(error.description if hasattr(error, 'description') else "Unauthorized"), success=False), 401
        
    @app.errorhandler(403)
    def forbidden_error(error):
        return jsonify(message=str(error.description if hasattr(error, 'description') else "Forbidden"), success=False), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify(message=str(error.description if hasattr(error, 'description') else "Resource not found"), success=False), 404

    @app.errorhandler(429) 
    def ratelimit_handler(e):
        return jsonify(message=f"Rate limit exceeded: {e.description}", success=False), 429

    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error(f"Internal Server Error: {error}", exc_info=True)
        return jsonify(message="An internal server error occurred.", success=False), 500

    return app
```


```python
# contraste/admin_api/routes.py

import os
import json
import uuid
import sqlite3
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash 
from flask import Blueprint, request, jsonify, current_app, g, url_for, send_from_directory, abort as flask_abort # Added abort
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity 

from ..utils import (
    admin_required,
    format_datetime_for_display,
    parse_datetime_from_iso,
    generate_slug,
    allowed_file,
    get_file_extension,
    format_datetime_for_storage,
    generate_static_json_files
)
from ..database import get_db_connection, query_db, record_stock_movement # Removed get_product_id_from_code as it's not used here
from . import admin_api_bp

# --- Admin Authentication ---
@admin_api_bp.route('/login', methods=['POST'])
def admin_login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    audit_logger = current_app.audit_log_service

    if not email or not password:
        audit_logger.log_action(action='admin_login_fail', email=email, details="Email and password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email and password are required", success=False), 400

    db = get_db_connection()
    try:
        admin_user_data = query_db(
            "SELECT id, email, password_hash, role, is_active, first_name, last_name FROM users WHERE email = ? AND role = 'admin'",
            [email],
            db_conn=db,
            one=True
        )

        if admin_user_data and check_password_hash(admin_user_data['password_hash'], password):
            admin_user = dict(admin_user_data)
            if not admin_user['is_active']:
                audit_logger.log_action(user_id=admin_user['id'], action='admin_login_fail_inactive', target_type='user_admin', target_id=admin_user['id'], details="Admin account is inactive.", status='failure', ip_address=request.remote_addr)
                return jsonify(message="Admin account is inactive. Please contact support.", success=False), 403

            identity = admin_user['id']
            additional_claims = {
                "role": admin_user['role'], "email": admin_user['email'], "is_admin": True,
                "first_name": admin_user.get('first_name'), "last_name": admin_user.get('last_name')
            }
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            
            audit_logger.log_action(user_id=admin_user['id'], action='admin_login_success', target_type='user_admin', target_id=admin_user['id'], status='success', ip_address=request.remote_addr)
            
            user_info_to_return = {
                "id": admin_user['id'], "email": admin_user['email'], 
                "prenom": admin_user.get('first_name'), "nom": admin_user.get('last_name'),
                "role": admin_user['role'], "is_admin": True
            }
            return jsonify(success=True, message="Admin login successful!", token=access_token, user=user_info_to_return), 200
        else:
            audit_logger.log_action(action='admin_login_fail_credentials', email=email, details="Invalid admin credentials.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid admin email or password", success=False), 401

    except Exception as e:
        current_app.logger.error(f"Error during admin login for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='admin_login_fail_server_error', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Admin login failed due to a server error", success=False), 500

# --- Dashboard ---
@admin_api_bp.route('/dashboard/stats', methods=['GET'])
@admin_required
def get_dashboard_stats():
    db = get_db_connection()
    try:
        total_users = query_db("SELECT COUNT(*) FROM users", db_conn=db, one=True)[0]
        total_products = query_db("SELECT COUNT(*) FROM products WHERE is_active = TRUE", db_conn=db, one=True)[0]
        total_orders = query_db("SELECT COUNT(*) FROM orders WHERE status NOT IN ('cancelled', 'pending_payment')", db_conn=db, one=True)[0]
        pending_b2b_applications = query_db("SELECT COUNT(*) FROM users WHERE role = 'b2b_professional' AND professional_status = 'pending'", db_conn=db, one=True)[0]
        
        return jsonify({
            "total_users": total_users, "total_products": total_products,
            "total_orders": total_orders, "pending_b2b_applications": pending_b2b_applications,
            "success": True
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching dashboard stats: {e}", exc_info=True)
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
    is_active = data.get('is_active', 'true').lower() == 'true' # Get is_active from form
    
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not name or not category_code:
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details="Name and Category Code are required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Name and Category Code are required", success=False), 400

    slug = generate_slug(name)
    db = get_db_connection()
    cursor = db.cursor() 
    image_filename_db = None 

    try:
        if query_db("SELECT id FROM categories WHERE name = ?", [name], db_conn=db, one=True):
            return jsonify(message=f"Category name '{name}' already exists", success=False), 409
        if query_db("SELECT id FROM categories WHERE slug = ?", [slug], db_conn=db, one=True):
            return jsonify(message=f"Category slug '{slug}' already exists. Try a different name.", success=False), 409
        if query_db("SELECT id FROM categories WHERE category_code = ?", [category_code], db_conn=db, one=True):
            return jsonify(message=f"Category code '{category_code}' already exists.", success=False), 409

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(f"category_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
            upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
            os.makedirs(upload_folder_categories, exist_ok=True)
            image_path_full = os.path.join(upload_folder_categories, filename)
            image_file.save(image_path_full)
            image_filename_db = os.path.join('categories', filename) 

        parent_id = int(parent_id_str) if parent_id_str and parent_id_str.strip() and parent_id_str.lower() != 'null' else None

        cursor.execute(
            "INSERT INTO categories (name, description, parent_id, slug, image_url, category_code, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, description, parent_id, slug, image_filename_db, category_code, is_active)
        )
        category_id = cursor.lastrowid
        db.commit() 
        
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='create_category', target_type='category', target_id=category_id, details=f"Category '{name}' created.", status='success', ip_address=request.remote_addr)
        created_category = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        return jsonify(message="Category created successfully", category=dict(created_category) if created_category else {}, success=True), 201
    except sqlite3.IntegrityError as e:
        db.rollback()
        return jsonify(message="Category name, slug, or code likely already exists (DB integrity).", success=False), 409
    except Exception as e:
        db.rollback()
        return jsonify(message=f"Failed to create category: {str(e)}", success=False), 500

@admin_api_bp.route('/categories', methods=['GET'])
@admin_required
def get_categories():
    db = get_db_connection()
    try:
        categories_data = query_db("SELECT id, name, description, parent_id, slug, image_url, category_code, is_active, created_at, updated_at FROM categories ORDER BY name", db_conn=db)
        categories = [dict(row) for row in categories_data] if categories_data else []
        
        for category in categories:
            category['created_at'] = format_datetime_for_display(category['created_at'])
            category['updated_at'] = format_datetime_for_display(category['updated_at'])
            if category.get('image_url'):
                 # Use the public asset route for images that might be displayed on the frontend via admin data
                 category['image_full_url'] = url_for('serve_public_asset', filepath=category['image_url'], _external=True)
        return jsonify(categories=categories, success=True), 200 # Return as object with 'categories' key
    except Exception as e:
        return jsonify(message=f"Failed to fetch categories: {str(e)}", success=False), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['GET'])
@admin_required
def get_category_detail(category_id):
    db = get_db_connection()
    try:
        category_data = query_db("SELECT *, is_active FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if category_data:
            category = dict(category_data)
            category['created_at'] = format_datetime_for_display(category['created_at'])
            category['updated_at'] = format_datetime_for_display(category['updated_at'])
            if category.get('image_url'):
                 category['image_full_url'] = url_for('serve_public_asset', filepath=category['image_url'], _external=True)
            return jsonify(category=category, success=True), 200
        return jsonify(message="Category not found", success=False), 404
    except Exception as e:
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
        return jsonify(message="Name and Category Code are required for update", success=False), 400

    db = get_db_connection()
    cursor = db.cursor() 
    try:
        current_category_row = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if not current_category_row:
            return jsonify(message="Category not found", success=False), 404
        current_category = dict(current_category_row)

        new_slug = generate_slug(name) if name != current_category['name'] else current_category['slug']
        
        if name != current_category['name'] and query_db("SELECT id FROM categories WHERE name = ? AND id != ?", [name, category_id], db_conn=db, one=True):
            return jsonify(message=f"Another category with the name '{name}' already exists", success=False), 409
        if new_slug != current_category['slug'] and query_db("SELECT id FROM categories WHERE slug = ? AND id != ?", [new_slug, category_id], db_conn=db, one=True):
            return jsonify(message=f"Another category with slug '{new_slug}' already exists. Try a different name.", success=False), 409
        if category_code != current_category.get('category_code') and query_db("SELECT id FROM categories WHERE category_code = ? AND id != ?", [category_code, category_id], db_conn=db, one=True):
            return jsonify(message=f"Another category with code '{category_code}' already exists.", success=False), 409

        upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
        os.makedirs(upload_folder_categories, exist_ok=True)
        image_filename_to_update_db = current_category['image_url']

        if remove_image and current_category['image_url']:
            full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_category['image_url'])
            if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            image_filename_to_update_db = None
        elif image_file and allowed_file(image_file.filename):
            if current_category['image_url']:
                full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_category['image_url'])
                if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            filename = secure_filename(f"category_{new_slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
            image_file.save(os.path.join(upload_folder_categories, filename))
            image_filename_to_update_db = os.path.join('categories', filename)

        parent_id_to_update = None
        if parent_id_str and parent_id_str.strip() and parent_id_str.lower() != 'null':
            try:
                parent_id_to_update = int(parent_id_str)
                if parent_id_to_update == category_id:
                    return jsonify(message="Category cannot be its own parent.", success=False), 400
            except ValueError:
                return jsonify(message="Invalid parent ID format.", success=False), 400
        
        description_to_update = description if description is not None else current_category['description']
        is_active_to_update = is_active_str.lower() == 'true' if is_active_str is not None else current_category['is_active']

        cursor.execute(
            """UPDATE categories SET 
               name = ?, description = ?, parent_id = ?, slug = ?, image_url = ?, category_code = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (name, description_to_update, parent_id_to_update, new_slug, image_filename_to_update_db, category_code, is_active_to_update, category_id)
        )
        db.commit() 
        
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)
        
        audit_logger.log_action(user_id=current_user_id, action='update_category', target_type='category', target_id=category_id, details=f"Category '{name}' updated.", status='success', ip_address=request.remote_addr)
        updated_category = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        return jsonify(message="Category updated successfully", category=dict(updated_category) if updated_category else {}, success=True), 200
    except sqlite3.IntegrityError as e:
        db.rollback()
        return jsonify(message="Category name, slug, or code likely conflicts (DB integrity).", success=False), 409
    except Exception as e:
        db.rollback()
        return jsonify(message=f"Failed to update category: {str(e)}", success=False), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() 

    try:
        category_to_delete_row = query_db("SELECT image_url, name FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if not category_to_delete_row:
            return jsonify(message="Category not found", success=False), 404
        category_to_delete = dict(category_to_delete_row)

        products_in_category_row = query_db("SELECT COUNT(*) FROM products WHERE category_id = ?", [category_id], db_conn=db, one=True)
        if products_in_category_row and products_in_category_row[0] > 0:
            return jsonify(message=f"Category '{category_to_delete['name']}' in use. Reassign products first.", success=False), 409
        
        if category_to_delete['image_url']:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category_to_delete['image_url'])
            if os.path.exists(full_image_path): os.remove(full_image_path)
        
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        db.commit() 

        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)

        if cursor.rowcount > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_category', target_type='category', target_id=category_id, details=f"Category '{category_to_delete['name']}' deleted.", status='success', ip_address=request.remote_addr)
            return jsonify(message=f"Category '{category_to_delete['name']}' deleted successfully", success=True), 200
        else: 
            return jsonify(message="Category not found during delete operation", success=False), 404
    except sqlite3.IntegrityError as e: 
        db.rollback()
        return jsonify(message="Failed to delete category (DB integrity constraints).", success=False), 409
    except Exception as e:
        db.rollback()
        return jsonify(message=f"Failed to delete category: {str(e)}", success=False), 500

# --- Product Management ---
# (create_product, get_products_admin, get_product_admin_detail, update_product, delete_product routes remain largely the same but ensure consistency with image_full_url and error/success=False|True in responses)
# Make sure to use url_for('serve_public_asset', filepath=...) for product images if they are public,
# or url_for('admin_api_bp.serve_asset', asset_relative_path=...) if they are admin-only.
# Assuming product images are generally public:

@admin_api_bp.route('/products', methods=['POST'])
@admin_required
def create_product():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor()

    try:
        data = request.form.to_dict() 
        main_image_file = request.files.get('main_image_url') # Name from form
        
        name = data.get('name')
        product_code = data.get('product_code', '').strip().upper() # From form, ensure uppercase
        sku_prefix = data.get('sku_prefix', product_code).strip().upper() # Default to product_code if not separate
        product_type = data.get('type', 'simple')
        description = data.get('description', '')
        
        category_id_str = data.get('category_id')
        category_id = int(category_id_str) if category_id_str and category_id_str.isdigit() else None

        brand = data.get('brand', "Maison Trüvra")
        base_price_str = data.get('price') # Form uses 'price' for base_price
        currency = data.get('currency', 'EUR')
        
        aggregate_stock_quantity_str = data.get('quantity', '0')
        aggregate_stock_weight_grams_str = data.get('aggregate_stock_weight_grams')
        unit_of_measure = data.get('unit_of_measure')
        
        is_active = data.get('is_active', 'true').lower() == 'true'
        is_featured = data.get('is_featured', 'false').lower() == 'true'
        
        meta_title = data.get('meta_title', name)
        meta_description = data.get('meta_description', description[:160] if description else '')
        slug = generate_slug(name)

        if not all([name, product_code, sku_prefix, product_type, category_id is not None]):
            return jsonify(message="Name, Product Code, SKU Prefix, Type, and Category are required.", success=False), 400
        
        if query_db("SELECT id FROM products WHERE product_code = ?", [product_code], db_conn=db, one=True):
            return jsonify(message=f"Product Code '{product_code}' already exists.", success=False), 409
        if sku_prefix != product_code and query_db("SELECT id FROM products WHERE sku_prefix = ?", [sku_prefix], db_conn=db, one=True):
             return jsonify(message=f"SKU Prefix '{sku_prefix}' already exists for another product.", success=False), 409
        if query_db("SELECT id FROM products WHERE slug = ?", [slug], db_conn=db, one=True):
            return jsonify(message=f"Product name (slug: '{slug}') already exists.", success=False), 409

        main_image_filename_db = None
        if main_image_file and allowed_file(main_image_file.filename):
            filename = secure_filename(f"product_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(main_image_file.filename)}")
            upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
            os.makedirs(upload_folder_products, exist_ok=True)
            main_image_file.save(os.path.join(upload_folder_products, filename))
            main_image_filename_db = os.path.join('products', filename) # Relative path for DB

        base_price = float(base_price_str) if base_price_str is not None and base_price_str != '' else None
        aggregate_stock_quantity = int(aggregate_stock_quantity_str) if aggregate_stock_quantity_str is not None and aggregate_stock_quantity_str != '' else 0
        aggregate_stock_weight_grams = float(aggregate_stock_weight_grams_str) if aggregate_stock_weight_grams_str else None

        if product_type == 'simple' and base_price is None:
            return jsonify(message="Base price (Price field) is required for simple products.", success=False), 400
        
        cursor.execute(
            """INSERT INTO products (name, description, category_id, product_code, brand, sku_prefix, type, 
                                   base_price, currency, main_image_url, aggregate_stock_quantity, 
                                   aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured, 
                                   meta_title, meta_description, slug)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, description, category_id, product_code, brand, sku_prefix, product_type, 
             base_price, currency, main_image_filename_db, 
             aggregate_stock_quantity if product_type == 'simple' else 0, 
             aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured, 
             meta_title, meta_description, slug)
        )
        product_id = cursor.lastrowid
        
        if product_type == 'simple' and aggregate_stock_quantity > 0:
             record_stock_movement(db, product_id, 'initial_stock', quantity_change=aggregate_stock_quantity, reason="Initial stock for new simple product", related_user_id=current_user_id)
        
        db.commit() 
        
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='create_product', target_type='product', target_id=product_id, details=f"Product '{name}' (Code: {product_code}) created.", status='success', ip_address=request.remote_addr)
        
        created_product_data_row = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        response_data = {"message": "Product created successfully", "product_id": product_id, "slug": slug, "success": True}
        if created_product_data_row:
            response_data["product"] = dict(created_product_data_row)
        return jsonify(response_data), 201

    except (sqlite3.IntegrityError, ValueError) as e:
        db.rollback()
        return jsonify(message=f"Failed to create product: {str(e)}", success=False), 400 if isinstance(e, ValueError) else 409
    except Exception as e:
        db.rollback()
        return jsonify(message=f"Failed to create product: {str(e)}", success=False), 500

@admin_api_bp.route('/products', methods=['GET'])
@admin_required
def get_products_admin():
    db = get_db_connection()
    include_variants_param = request.args.get('include_variants', 'false').lower() == 'true'
    try:
        products_data = query_db(
            """SELECT p.*, c.name as category_name, c.category_code 
               FROM products p LEFT JOIN categories c ON p.category_id = c.id 
               ORDER BY p.name""", db_conn=db
        )
        products = [dict(row) for row in products_data] if products_data else []
        for product in products:
            product['created_at'] = format_datetime_for_display(product['created_at'])
            product['updated_at'] = format_datetime_for_display(product['updated_at'])
            product['price'] = product.get('base_price') 
            product['quantity'] = product.get('aggregate_stock_quantity')

            if product.get('main_image_url'):
                # Assuming product images are public
                product['main_image_full_url'] = url_for('serve_public_asset', filepath=product['main_image_url'], _external=True)
            
            if product['type'] == 'variable_weight' or include_variants_param:
                options_data = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product['id']], db_conn=db)
                product['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
                product['variant_count'] = len(product['weight_options'])
                if product['type'] == 'variable_weight' and product['weight_options']:
                    product['quantity'] = sum(opt.get('aggregate_stock_quantity', 0) for opt in product['weight_options'])
            
            images_data = query_db("SELECT id, image_url, alt_text, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC", [product['id']], db_conn=db)
            product['additional_images'] = []
            if images_data:
                for img_row in images_data:
                    img_dict = dict(img_row)
                    if img_dict.get('image_url'):
                         img_dict['image_full_url'] = url_for('serve_public_asset', filepath=img_dict['image_url'], _external=True)
                    product['additional_images'].append(img_dict)
        return jsonify(products=products, success=True), 200 # Return as object
    except Exception as e:
        return jsonify(message=f"Failed to fetch products for admin: {str(e)}", success=False), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['GET'])
@admin_required
def get_product_admin_detail(product_id):
    db = get_db_connection()
    try:
        product_data = query_db("SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.id = ?", [product_id], db_conn=db, one=True)
        if not product_data:
            return jsonify(message="Product not found", success=False), 404
            
        product = dict(product_data)
        product['created_at'] = format_datetime_for_display(product['created_at'])
        product['updated_at'] = format_datetime_for_display(product['updated_at'])
        if product.get('main_image_url'):
            product['main_image_full_url'] = url_for('serve_public_asset', filepath=product['main_image_url'], _external=True)

        if product['type'] == 'variable_weight':
            options_data = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product_id], db_conn=db)
            product['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
        
        images_data = query_db("SELECT id, image_url, alt_text, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC", [product_id], db_conn=db)
        product['additional_images'] = []
        if images_data:
            for img_row in images_data:
                img_dict = dict(img_row)
                if img_dict.get('image_url'):
                    img_dict['image_full_url'] = url_for('serve_public_asset', filepath=img_dict['image_url'], _external=True)
                product['additional_images'].append(img_dict)
        
        assets_data = query_db("SELECT asset_type, file_path FROM generated_assets WHERE related_product_id = ?", [product_id], db_conn=db)
        product_assets = {}
        if assets_data:
            for asset_row in assets_data:
                asset_type_key = asset_row['asset_type'].lower().replace(' ', '_')
                asset_full_url = None
                if asset_row.get('file_path'):
                    try:
                        if asset_row['asset_type'] == 'passport_html':
                            passport_filename = os.path.basename(asset_row['file_path'])
                            asset_full_url = url_for('serve_public_asset', filepath=f"passports/{passport_filename}", _external=True)
                        else: # QR codes, labels are admin-accessed via this blueprint's serve_asset
                            asset_full_url = url_for('admin_api_bp.serve_asset', asset_relative_path=asset_row['file_path'], _external=True)
                    except Exception as e_asset_url:
                        current_app.logger.warning(f"Could not generate URL for asset {asset_row['file_path']}: {e_asset_url}")
                
                product_assets[f"{asset_type_key}_url"] = asset_full_url
                product_assets[f"{asset_type_key}_file_path"] = asset_row['file_path']
        product['assets'] = product_assets
            
        return jsonify(product=product, success=True), 200
    except Exception as e:
        return jsonify(message=f"Failed to fetch product details (admin): {str(e)}", success=False), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['PUT'])
@admin_required
def update_product(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() 

    try:
        current_product_row = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not current_product_row:
            return jsonify(message="Product not found", success=False), 404
        current_product = dict(current_product_row)

        data = request.form.to_dict()
        main_image_file = request.files.get('main_image_url') # Form sends 'main_image_url' for new file
        remove_main_image = data.get('remove_main_image') == 'true'

        name = data.get('name', current_product['name'])
        new_slug = generate_slug(name) if name != current_product['name'] else current_product['slug']
        
        new_product_code = data.get('product_code', current_product['product_code']).strip().upper()
        if new_product_code != current_product['product_code'] and query_db("SELECT id FROM products WHERE product_code = ? AND id != ?", [new_product_code, product_id], db_conn=db, one=True):
            return jsonify(message=f"Product Code '{new_product_code}' already exists.", success=False), 409
        
        new_sku_prefix = data.get('sku_prefix', current_product['sku_prefix'] if current_product['sku_prefix'] else new_product_code).strip().upper()
        if new_sku_prefix != current_product['sku_prefix'] and query_db("SELECT id FROM products WHERE sku_prefix = ? AND id != ?", [new_sku_prefix, product_id], db_conn=db, one=True):
             return jsonify(message=f"SKU Prefix '{new_sku_prefix}' already exists for another product.", success=False), 409

        if new_slug != current_product['slug'] and query_db("SELECT id FROM products WHERE slug = ? AND id != ?", [new_slug, product_id], db_conn=db, one=True):
            return jsonify(message=f"Product name (slug: '{new_slug}') already exists.", success=False), 409
        
        upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
        os.makedirs(upload_folder_products, exist_ok=True)
        main_image_filename_db = current_product['main_image_url']

        if remove_main_image and current_product['main_image_url']:
            full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_product['main_image_url'])
            if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            main_image_filename_db = None
        elif main_image_file and allowed_file(main_image_file.filename):
            if current_product['main_image_url']:
                full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_product['main_image_url'])
                if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            filename = secure_filename(f"product_{new_slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(main_image_file.filename)}")
            main_image_file.save(os.path.join(upload_folder_products, filename))
            main_image_filename_db = os.path.join('products', filename)

        category_id_str = data.get('category_id')
        category_id_to_update = current_product['category_id']
        if category_id_str:
            category_id_to_update = int(category_id_str) if category_id_str.isdigit() else None
        
        update_payload_product = {
            'name': name, 'slug': new_slug, 'product_code': new_product_code, 'sku_prefix': new_sku_prefix,
            'description': data.get('description', current_product['description']),
            'category_id': category_id_to_update,
            'brand': data.get('brand', current_product['brand']),
            'type': data.get('type', current_product['type']),
            'base_price': float(data['price']) if data.get('price') is not None and data.get('price') != '' else current_product['base_price'],
            'currency': data.get('currency', current_product['currency']),
            'main_image_url': main_image_filename_db,
            'aggregate_stock_quantity': int(data.get('quantity', current_product['aggregate_stock_quantity'])),
            'aggregate_stock_weight_grams': float(data['aggregate_stock_weight_grams']) if data.get('aggregate_stock_weight_grams') is not None and data.get('aggregate_stock_weight_grams') != '' else current_product['aggregate_stock_weight_grams'],
            'unit_of_measure': data.get('unit_of_measure', current_product['unit_of_measure']),
            'is_active': data.get('is_active', str(current_product['is_active'])).lower() == 'true',
            'is_featured': data.get('is_featured', str(current_product['is_featured'])).lower() == 'true',
            'meta_title': data.get('meta_title', current_product['meta_title'] or name),
            'meta_description': data.get('meta_description', current_product['meta_description'] or data.get('description', '')[:160]),
        }
        
        if update_payload_product['type'] == 'simple' and update_payload_product['base_price'] is None:
            return jsonify(message="Base price (Price field) is required for simple products.", success=False), 400
        
        set_clause_product = ", ".join([f"{key} = ?" for key in update_payload_product.keys()])
        sql_args_product = list(update_payload_product.values())
        sql_args_product.append(product_id)

        cursor.execute(f"UPDATE products SET {set_clause_product}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", tuple(sql_args_product))
        
        if current_product['type'] == 'variable_weight' and update_payload_product['type'] == 'simple':
            cursor.execute("DELETE FROM product_weight_options WHERE product_id = ?", (product_id,))
        
        db.commit() 
        
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='update_product', target_type='product', target_id=product_id, details=f"Product '{name}' (Code: {new_product_code}) updated.", status='success', ip_address=request.remote_addr)
        
        updated_product_data = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True) # Re-fetch
        return jsonify(message="Product updated successfully", product=dict(updated_product_data) if updated_product_data else {}, success=True), 200

    except (sqlite3.IntegrityError, ValueError) as e:
        db.rollback()
        return jsonify(message=f"Failed to update product: {str(e)}", success=False), 400 if isinstance(e, ValueError) else 409
    except Exception as e:
        db.rollback()
        return jsonify(message=f"Failed to update product: {str(e)}", success=False), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['DELETE'])
@admin_required
def delete_product(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() 
    try:
        product_to_delete_row = query_db("SELECT name, main_image_url, product_code FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not product_to_delete_row:
            return jsonify(message="Product not found", success=False), 404
        product_to_delete = dict(product_to_delete_row)

        if product_to_delete['main_image_url']:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], product_to_delete['main_image_url'])
            if os.path.exists(full_image_path): os.remove(full_image_path)
        
        additional_images = query_db("SELECT image_url FROM product_images WHERE product_id = ?", [product_id], db_conn=db)
        if additional_images:
            for img in additional_images:
                full_add_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], img['image_url'])
                if os.path.exists(full_add_image_path): os.remove(full_add_image_path)
        
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        db.commit() 

        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)

        if cursor.rowcount > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_product', target_type='product', target_id=product_id, details=f"Product '{product_to_delete['name']}' deleted.", status='success', ip_address=request.remote_addr)
            return jsonify(message=f"Product '{product_to_delete['name']}' deleted successfully", success=True), 200
        else: 
            return jsonify(message="Product not found during delete operation", success=False), 404
    except sqlite3.IntegrityError as e:
        db.rollback()
        return jsonify(message="Failed to delete product (DB integrity constraints).", success=False), 409
    except Exception as e:
        db.rollback()
        return jsonify(message=f"Failed to delete product: {str(e)}", success=False), 500

# --- User Management ---
# (get_users, get_user_admin_detail, update_user_admin routes remain largely the same but ensure success=True/False in responses)
@admin_api_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    db = get_db_connection()
    role_filter = request.args.get('role')
    status_filter_str = request.args.get('is_active') 
    search_term = request.args.get('search')

    query_sql = "SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, professional_status, created_at FROM users"
    conditions = []
    params = []

    if role_filter: conditions.append("role = ?"); params.append(role_filter)
    if status_filter_str is not None:
        is_active_val = status_filter_str.lower() == 'true'
        conditions.append("is_active = ?"); params.append(is_active_val)
    if search_term:
        conditions.append("(email LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR company_name LIKE ? OR CAST(id AS TEXT) LIKE ?)")
        term = f"%{search_term}%"; params.extend([term, term, term, term, term])
    
    if conditions: query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY created_at DESC"

    try:
        users_data = query_db(query_sql, params, db_conn=db)
        users = [dict(row) for row in users_data] if users_data else []
        for user in users: user['created_at'] = format_datetime_for_display(user['created_at'])
        return jsonify(users=users, success=True), 200
    except Exception as e:
        return jsonify(message=f"Failed to fetch users: {str(e)}", success=False), 500

@admin_api_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user_admin_detail(user_id):
    db = get_db_connection()
    try:
        user_data = query_db("SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, vat_number, siret_number, professional_status, created_at, updated_at FROM users WHERE id = ?", [user_id], db_conn=db, one=True)
        if not user_data: return jsonify(message="User not found", success=False), 404
        
        user = dict(user_data)
        user['created_at'] = format_datetime_for_display(user['created_at'])
        user['updated_at'] = format_datetime_for_display(user['updated_at'])
        
        orders_data = query_db("SELECT id as order_id, order_date, total_amount, status FROM orders WHERE user_id = ? ORDER BY order_date DESC", [user_id], db_conn=db)
        user['orders'] = [dict(row) for row in orders_data] if orders_data else []
        for order_item in user['orders']: order_item['order_date'] = format_datetime_for_display(order_item['order_date'])
        return jsonify(user=user, success=True), 200
    except Exception as e:
        return jsonify(message=f"Failed to fetch user details (admin): {str(e)}", success=False), 500

@admin_api_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user_admin(user_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() 
    data = request.json

    if not data: return jsonify(message="No data provided", success=False), 400

    allowed_fields = ['first_name', 'last_name', 'role', 'is_active', 'is_verified', 
                      'company_name', 'vat_number', 'siret_number', 'professional_status']
    update_payload = {k: data[k] for k in data if k in allowed_fields}

    if not update_payload: return jsonify(message="No valid fields to update", success=False), 400
    
    if 'is_active' in update_payload: update_payload['is_active'] = str(update_payload['is_active']).lower() == 'true'
    if 'is_verified' in update_payload: update_payload['is_verified'] = str(update_payload['is_verified']).lower() == 'true'

    set_clause = ", ".join([f"{key} = ?" for key in update_payload.keys()])
    sql_args = list(update_payload.values())
    sql_args.append(user_id)

    try:
        if not query_db("SELECT id FROM users WHERE id = ?", [user_id], db_conn=db, one=True):
             return jsonify(message="User not found", success=False), 404

        cursor.execute(f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", tuple(sql_args))
        db.commit() 
        
        if cursor.rowcount == 0: return jsonify(message="User not found or no changes made", success=False), 404
        
        audit_logger.log_action(user_id=current_admin_id, action='update_user_admin', target_type='user', target_id=user_id, details=f"User {user_id} updated. Fields: {', '.join(update_payload.keys())}", status='success', ip_address=request.remote_addr)
        return jsonify(message="User updated successfully", success=True), 200
    except sqlite3.Error as e:
        db.rollback()
        return jsonify(message="Failed to update user due to DB error", success=False), 500
    except Exception as e:
        db.rollback()
        return jsonify(message=f"Failed to update user: {str(e)}", success=False), 500

# --- Order Management ---
# (get_orders_admin, get_order_admin_detail, update_order_status_admin, add_order_note_admin routes remain largely the same but ensure success=True/False)
@admin_api_bp.route('/orders', methods=['GET'])
@admin_required
def get_orders_admin():
    db = get_db_connection()
    search_filter = request.args.get('search')
    status_filter = request.args.get('status')
    date_filter_str = request.args.get('date')

    query_sql = """
        SELECT o.id as order_id, o.user_id, o.order_date, o.status, o.total_amount, o.currency,
               u.email as customer_email, (u.first_name || ' ' || u.last_name) as customer_name
        FROM orders o LEFT JOIN users u ON o.user_id = u.id
    """
    conditions = []; params = []
    if search_filter:
        conditions.append("(CAST(o.id AS TEXT) LIKE ? OR u.email LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ? OR o.payment_transaction_id LIKE ?)")
        term = f"%{search_filter}%"; params.extend([term, term, term, term, term])
    if status_filter: conditions.append("o.status = ?"); params.append(status_filter)
    if date_filter_str: 
        try:
            datetime.strptime(date_filter_str, '%Y-%m-%d')
            conditions.append("DATE(o.order_date) = ?"); params.append(date_filter_str)
        except ValueError: return jsonify(message="Invalid date format. Use YYYY-MM-DD.", success=False), 400

    if conditions: query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY o.order_date DESC"

    try:
        orders_data = query_db(query_sql, params, db_conn=db)
        orders = [dict(row) for row in orders_data] if orders_data else []
        for order in orders: order['order_date'] = format_datetime_for_display(order['order_date'])
        return jsonify(orders=orders, success=True), 200
    except Exception as e:
        return jsonify(message=f"Failed to fetch orders: {str(e)}", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>', methods=['GET'])
@admin_required
def get_order_admin_detail(order_id):
    db = get_db_connection()
    try:
        order_data_row = query_db("SELECT o.*, u.email as customer_email, (u.first_name || ' ' || u.last_name) as customer_name FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.id = ?", [order_id], db_conn=db, one=True)
        if not order_data_row: return jsonify(message="Order not found", success=False), 404
        order = dict(order_data_row)
        for dt_field in ['order_date', 'created_at', 'updated_at']: order[dt_field] = format_datetime_for_display(order[dt_field])
        items_data = query_db("SELECT oi.*, p.main_image_url as product_image_url FROM order_items oi LEFT JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?", [order_id], db_conn=db)
        order['items'] = []
        if items_data:
            for item_row in items_data:
                item_dict = dict(item_row)
                if item_dict.get('product_image_url'):
                    item_dict['product_image_full_url'] = url_for('serve_public_asset', filepath=item_dict['product_image_url'], _external=True)
                order['items'].append(item_dict)
        return jsonify(order=order, success=True), 200
    except Exception as e:
        return jsonify(message=f"Failed to fetch order details: {str(e)}", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@admin_required
def update_order_status_admin(order_id):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor(); data = request.json
    new_status = data.get('status'); tracking_number = data.get('tracking_number'); carrier = data.get('carrier')
    if not new_status: return jsonify(message="New status not provided", success=False), 400
    allowed = ['pending_payment', 'paid', 'processing', 'awaiting_shipment', 'shipped', 'delivered', 'completed', 'cancelled', 'refunded', 'on_hold', 'failed']
    if new_status not in allowed: return jsonify(message=f"Invalid status. Allowed: {', '.join(allowed)}", success=False), 400
    try:
        order_info = query_db("SELECT status FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)
        if not order_info: return jsonify(message="Order not found", success=False), 404
        updates = {"status": new_status}; old_status = order_info['status']
        if new_status in ['shipped', 'delivered']:
            if tracking_number: updates["tracking_number"] = tracking_number
            if carrier: updates["shipping_method"] = carrier
        set_parts = [f"{k} = ?" for k in updates] + ["updated_at = CURRENT_TIMESTAMP"]
        params = list(updates.values()) + [order_id]
        cursor.execute(f"UPDATE orders SET {', '.join(set_parts)} WHERE id = ?", tuple(params)); db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_order_status_admin', target_type='order', target_id=order_id, details=f"Order {order_id} status from '{old_status}' to '{new_status}'. Tracking: {tracking_number or 'N/A'}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Order status updated to {new_status}", success=True), 200
    except Exception as e:
        db.rollback(); audit_logger.log_action(user_id=current_admin_id, action='update_order_status_admin_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update order status: {str(e)}", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>/notes', methods=['POST'])
@admin_required
def add_order_note_admin(order_id):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor(); data = request.json
    note_content = data.get('note')
    if not note_content or not note_content.strip(): return jsonify(message="Note content cannot be empty.", success=False), 400
    try:
        if not query_db("SELECT id FROM orders WHERE id = ?", [order_id], db_conn=db, one=True): return jsonify(message="Order not found", success=False), 404
        current_notes = query_db("SELECT notes_internal FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)['notes_internal'] or ""
        admin_info = query_db("SELECT email FROM users WHERE id = ?", [current_admin_id], db_conn=db, one=True)
        admin_id_str = admin_info['email'] if admin_info else f"AdminID:{current_admin_id}"
        new_entry = f"[{format_datetime_for_display(None)} by {admin_id_str}]: {note_content}"
        updated_notes = f"{current_notes}\n{new_entry}".strip()
        cursor.execute("UPDATE orders SET notes_internal = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (updated_notes, order_id)); db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note_admin', target_type='order', target_id=order_id, details=f"Added note: '{note_content[:50]}...'", status='success', ip_address=request.remote_addr)
        return jsonify(message="Note added successfully.", new_note_entry=new_entry, success=True), 201
    except Exception as e:
        db.rollback(); audit_logger.log_action(user_id=current_admin_id, action='add_order_note_admin_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to add note: {str(e)}", success=False), 500

# --- Review Management ---
# (get_reviews_admin, approve_review_admin, unapprove_review_admin, delete_review_admin routes remain largely the same but ensure success=True/False)
@admin_api_bp.route('/reviews', methods=['GET'])
@admin_required
def get_reviews_admin():
    db = get_db_connection(); status_filter = request.args.get('status') 
    product_filter = request.args.get('product_id'); user_filter = request.args.get('user_id')
    query = "SELECT r.*, p.name as product_name, p.product_code, u.email as user_email FROM reviews r JOIN products p ON r.product_id = p.id JOIN users u ON r.user_id = u.id"
    conditions = []; params = []
    if status_filter == 'pending': conditions.append("r.is_approved = FALSE")
    elif status_filter == 'approved': conditions.append("r.is_approved = TRUE")
    if product_filter:
        if product_filter.isdigit(): conditions.append("r.product_id = ?"); params.append(int(product_filter))
        else: conditions.append("(p.name LIKE ? OR p.product_code LIKE ?)"); params.extend([f"%{product_filter}%", f"%{product_filter}%"])
    if user_filter:
        if user_filter.isdigit(): conditions.append("r.user_id = ?"); params.append(int(user_filter))
        else: conditions.append("u.email LIKE ?"); params.append(f"%{user_filter}%")
    if conditions: query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY r.review_date DESC"
    try:
        reviews_data = query_db(query, params, db_conn=db)
        reviews = [dict(r) for r in reviews_data] if reviews_data else []
        for rev in reviews: rev['review_date'] = format_datetime_for_display(rev['review_date'])
        return jsonify(reviews=reviews, success=True), 200
    except Exception as e: return jsonify(message=f"Failed to fetch reviews: {str(e)}", success=False), 500

@admin_api_bp.route('/reviews/<int:review_id>/approve', methods=['PUT'])
@admin_required
def approve_review_admin(review_id): return _update_review_approval_admin(review_id, True)

@admin_api_bp.route('/reviews/<int:review_id>/unapprove', methods=['PUT'])
@admin_required
def unapprove_review_admin(review_id): return _update_review_approval_admin(review_id, False)

def _update_review_approval_admin(review_id, is_approved_status):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor(); action = "approve" if is_approved_status else "unapprove"
    try:
        if not query_db("SELECT id FROM reviews WHERE id = ?", [review_id], db_conn=db, one=True): return jsonify(message="Review not found", success=False), 404
        cursor.execute("UPDATE reviews SET is_approved = ? WHERE id = ?", (is_approved_status, review_id)); db.commit()
        audit_logger.log_action(user_id=current_admin_id, action=f'{action}_review_admin', target_type='review', target_id=review_id, details=f"Review {review_id} set to {is_approved_status}.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Review {'approved' if is_approved_status else 'unapproved'} successfully", success=True), 200
    except Exception as e:
        db.rollback(); audit_logger.log_action(user_id=current_admin_id, action=f'{action}_review_admin_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to {action} review: {str(e)}", success=False), 500

@admin_api_bp.route('/reviews/<int:review_id>', methods=['DELETE'])
@admin_required
def delete_review_admin(review_id):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor()
    try:
        if not query_db("SELECT id FROM reviews WHERE id = ?", [review_id], db_conn=db, one=True): return jsonify(message="Review not found", success=False), 404
        cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,)); db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin', target_type='review', target_id=review_id, details=f"Review {review_id} deleted.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Review deleted successfully", success=True), 200
    except Exception as e:
        db.rollback(); audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to delete review: {str(e)}", success=False), 500

# --- Settings Management ---
# (get_settings_admin, update_settings_admin routes remain largely the same but ensure success=True/False)
@admin_api_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings_admin():
    db = get_db_connection()
    try:
        settings_data = query_db("SELECT key, value, description FROM settings", db_conn=db)
        settings = {row['key']: {'value': row['value'], 'description': row['description']} for row in settings_data} if settings_data else {}
        return jsonify(settings=settings, success=True), 200
    except Exception as e: return jsonify(message=f"Failed to fetch settings: {str(e)}", success=False), 500

@admin_api_bp.route('/settings', methods=['POST'])
@admin_required
def update_settings_admin():
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor(); data = request.json
    if not data: return jsonify(message="No settings data provided", success=False), 400
    updated_keys = []
    try:
        for key, value_obj in data.items():
            value = value_obj.get('value') if isinstance(value_obj, dict) else value_obj
            if value is not None:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (key, str(value)))
                updated_keys.append(key)
        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin', target_type='application_settings', details=f"Settings updated: {', '.join(updated_keys)}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Settings updated successfully", updated_settings=updated_keys, success=True), 200
    except Exception as e:
        db.rollback(); audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update settings: {str(e)}", success=False), 500

# --- Detailed Inventory View ---
@admin_api_bp.route('/inventory/items/detailed', methods=['GET'])
@admin_required
def get_detailed_inventory_items_admin():
    db = get_db_connection()
    try:
        sql_query = """
            SELECT p.name AS product_name, p.product_code,
                   pl_fr.name as product_name_fr, pl_en.name as product_name_en,
                   CASE WHEN pwo.id IS NOT NULL THEN p.name || ' - ' || pwo.weight_grams || 'g (' || pwo.sku_suffix || ')' ELSE NULL END AS variant_name,
                   sii.* FROM serialized_inventory_items sii
            JOIN products p ON sii.product_id = p.id
            LEFT JOIN product_localizations pl_fr ON p.id = pl_fr.product_id AND pl_fr.lang_code = 'fr'
            LEFT JOIN product_localizations pl_en ON p.id = pl_en.product_id AND pl_en.lang_code = 'en'
            LEFT JOIN product_weight_options pwo ON sii.variant_id = pwo.id
            ORDER BY p.name, sii.item_uid;
        """
        items_data = query_db(sql_query, db_conn=db)
        detailed_items = []
        if items_data:
            for row in items_data:
                item = dict(row)
                for dt_field in ['production_date', 'expiry_date', 'received_at', 'sold_at', 'updated_at']:
                    item[dt_field] = format_datetime_for_storage(item[dt_field]) if item.get(dt_field) else None
                if item.get('qr_code_url'): item['qr_code_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item['qr_code_url'], _external=True)
                if item.get('passport_url'): item['passport_full_url'] = url_for('serve_public_asset', filepath=f"passports/{os.path.basename(item['passport_url'])}", _external=True)
                if item.get('label_url'): item['label_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item['label_url'], _external=True)
                detailed_items.append(item)
        return jsonify(detailed_items), 200 # Return array directly as expected by frontend
    except Exception as e:
        current_app.logger.error(f"Error fetching detailed inventory items for admin: {e}", exc_info=True)
        return jsonify([]), 500 # Return empty array on error

# --- Admin Asset Serving (for protected assets like QR codes, labels, invoices) ---
@admin_api_bp.route('/assets/<path:asset_relative_path>')
@admin_required 
def serve_asset(asset_relative_path):
    if ".." in asset_relative_path or asset_relative_path.startswith("/"):
        current_app.logger.warning(f"Directory traversal attempt for admin asset: {asset_relative_path}")
        return flask_abort(404)

    # Define specific mappings for admin-accessible generated assets
    asset_type_map = {
        'qr_codes': current_app.config['QR_CODE_FOLDER'],
        'labels': current_app.config['LABEL_FOLDER'],
        'invoices': current_app.config['INVOICE_PDF_PATH'],
        'professional_documents': current_app.config['PROFESSIONAL_DOCS_UPLOAD_PATH']
        # Add other admin-specific asset types if needed
    }
    
    path_parts = asset_relative_path.split(os.sep, 1)
    asset_type_key = path_parts[0]
    filename_in_type_folder = path_parts[1] if len(path_parts) > 1 else None

    if asset_type_key in asset_type_map and filename_in_type_folder:
        base_path = asset_type_map[asset_type_key]
        full_path = os.path.join(base_path, filename_in_type_folder)
        
        # Security check: Ensure the resolved path is still within the intended base directory
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
        generate_static_json_files() 
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json', status='success', ip_address=request.remote_addr)
        return jsonify(message="Static JSON files regenerated successfully.", success=True), 200
    except Exception as e:
        current_app.logger.error(f"Failed to regenerate static JSON files via API: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to regenerate static JSON files: {str(e)}", success=False), 500
```


```python
import os
import uuid
import sqlite3
import csv 
from io import StringIO 
from flask import request, jsonify, current_app, g, url_for, Response, send_from_directory, make_response, abort as flask_abort 
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone 

from ..database import get_db_connection, query_db, record_stock_movement, get_product_id_from_code
from ..services.asset_service import (
    generate_qr_code_for_item, 
    generate_item_passport,
    generate_product_label_pdf 
)
from ..utils import admin_required, format_datetime_for_display, parse_datetime_from_iso, format_datetime_for_storage 
from . import inventory_bp 


@inventory_bp.route('/serialized/receive', methods=['POST'])
@admin_required
def receive_serialized_stock():
    data = request.json
    product_code_str = data.get('product_code') 
    quantity_received_str = data.get('quantity_received')
    variant_sku_suffix = data.get('variant_sku_suffix') 
    batch_number = data.get('batch_number')
    production_date_iso_str = data.get('production_date') 
    expiry_date_iso_str = data.get('expiry_date')     
    cost_price_str = data.get('cost_price')          
    notes = data.get('notes', '')
    actual_weight_grams_str = data.get('actual_weight_grams') 

    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not all([product_code_str, quantity_received_str]):
        return jsonify(message="Product Code and quantity are required", success=False), 400

    db = get_db_connection()
    product_row = query_db("SELECT id, name, sku_prefix, category_id FROM products WHERE product_code = ?", [product_code_str.upper()], db_conn=db, one=True)
    if not product_row:
        return jsonify(message=f"Product Code '{product_code_str}' not found.", success=False), 404
    product_id = product_row['id']
    product_name_for_assets = product_row['name'] # Default name
    product_sku_prefix = product_row.get('sku_prefix') or product_code_str.upper()
    category_id_for_product = product_row.get('category_id')
    
    # Fetch localized product names for assets if available
    product_loc_fr = query_db("SELECT name_fr FROM product_localizations WHERE product_id = ? AND lang_code = 'fr'", [product_id], db_conn=db, one=True)
    product_loc_en = query_db("SELECT name_en FROM product_localizations WHERE product_id = ? AND lang_code = 'en'", [product_id], db_conn=db, one=True)
    product_name_fr_for_assets = product_loc_fr['name_fr'] if product_loc_fr else product_name_for_assets
    product_name_en_for_assets = product_loc_en['name_en'] if product_loc_en else product_name_for_assets


    variant_id = None
    if variant_sku_suffix:
        variant_info = query_db("SELECT id FROM product_weight_options WHERE product_id = ? AND sku_suffix = ?", [product_id, variant_sku_suffix.upper()], db_conn=db, one=True)
        if not variant_info:
            return jsonify(message=f"Variant SKU suffix '{variant_sku_suffix}' not found for product code '{product_code_str}'.", success=False), 400
        variant_id = variant_info['id']

    try:
        quantity_received = int(quantity_received_str)
        if quantity_received <= 0: raise ValueError("Quantity received must be positive.")
        cost_price = float(cost_price_str) if cost_price_str else None
        actual_weight_grams_item = float(actual_weight_grams_str) if actual_weight_grams_str else None
    except ValueError as ve:
        return jsonify(message=f"Invalid data type: {ve}", success=False), 400

    cursor = db.cursor()
    
    category_info_for_passport = {"name_fr": "N/A", "name_en": "N/A", "species_fr": "N/A", "species_en": "N/A", "ingredients_fr": "N/A", "ingredients_en": "N/A"}
    if category_id_for_product:
        cat_details_row = query_db("SELECT cl.name_fr, cl.name_en, cl.species_fr, cl.species_en, cl.ingredients_fr, cl.ingredients_en FROM category_localizations cl WHERE cl.category_id = ? UNION ALL SELECT c.name, c.name, NULL, NULL, NULL, NULL FROM categories c WHERE c.id = ? AND NOT EXISTS (SELECT 1 FROM category_localizations cl2 WHERE cl2.category_id = c.id) LIMIT 1", [category_id_for_product, category_id_for_product], db_conn=db, one=True)
        if cat_details_row: category_info_for_passport = dict(cat_details_row)

    production_date_db = format_datetime_for_storage(parse_datetime_from_iso(production_date_iso_str)) if production_date_iso_str else None
    expiry_date_db = format_datetime_for_storage(parse_datetime_from_iso(expiry_date_iso_str)) if expiry_date_iso_str else None
    processing_date_for_label_fr = datetime.now(timezone.utc).strftime('%d/%m/%Y')
    app_base_url = current_app.config.get('APP_BASE_URL', 'http://localhost:8000')

    generated_items_details = []
    try:
        for i in range(quantity_received):
            item_uid = f"{product_sku_prefix}-{uuid.uuid4().hex[:8].upper()}" 
            
            item_specific_data_for_passport = {
                "batch_number": batch_number, "production_date": production_date_iso_str, 
                "expiry_date": expiry_date_iso_str, "actual_weight_grams": actual_weight_grams_item 
            }
            # Use the product_row directly for product_info in passport generation
            passport_relative_path = generate_item_passport(item_uid, product_row, category_info_for_passport, item_specific_data_for_passport)
            if not passport_relative_path: raise Exception(f"Failed to generate passport for item {i+1}.")

            # Public URL for QR code content
            passport_public_url = url_for('serve_public_asset', filepath=f"passports/{os.path.basename(passport_relative_path)}", _external=True)
            qr_code_png_relative_path = generate_qr_code_for_item(item_uid, product_id, product_name_fr_for_assets, product_name_en_for_assets) # This saves the QR code image
            if not qr_code_png_relative_path: raise Exception(f"Failed to generate passport QR code PNG for item {i+1}.")

            weight_for_label = actual_weight_grams_item
            if not weight_for_label and variant_id:
                variant_data_for_label = query_db("SELECT weight_grams FROM product_weight_options WHERE id = ?", [variant_id], db_conn=db, one=True)
                if variant_data_for_label: weight_for_label = variant_data_for_label['weight_grams']
            
            label_pdf_relative_path = generate_product_label_pdf(
                item_uid=item_uid, product_name_fr=product_name_fr_for_assets, product_name_en=product_name_en_for_assets,
                weight_grams=weight_for_label, processing_date_str=processing_date_for_label_fr,
                passport_url=passport_public_url # Use the public URL for the QR code on the label
            )
            if not label_pdf_relative_path: raise Exception(f"Failed to generate PDF label for item {i+1}.")

            cursor.execute(
                """INSERT INTO serialized_inventory_items 
                   (item_uid, product_id, variant_id, batch_number, production_date, expiry_date, 
                    cost_price, notes, status, qr_code_url, passport_url, label_url, actual_weight_grams)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_uid, product_id, variant_id, batch_number, production_date_db, expiry_date_db, 
                 cost_price, notes, 'available', qr_code_png_relative_path, passport_relative_path, label_pdf_relative_path,
                 actual_weight_grams_item)
            )
            serialized_item_id = cursor.lastrowid
            record_stock_movement(db, product_id, 'receive_serialized', quantity_change=1, variant_id=variant_id, serialized_item_id=serialized_item_id, reason="Initial stock receipt", related_user_id=current_admin_id)
            
            generated_items_details.append({
                "item_uid": item_uid, "product_name": product_name_fr_for_assets, "product_code": product_code_str.upper(),
                "qr_code_path": qr_code_png_relative_path, "passport_path": passport_relative_path, "label_pdf_path": label_pdf_relative_path
            })
        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_success', target_type='product', target_id=product_id, details=f"Received {quantity_received} items for {product_code_str}.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"{quantity_received} items received.", items=generated_items_details, success=True), 201
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error receiving stock for {product_code_str}: {e}", exc_info=True)
        # Clean up generated assets if commit failed
        asset_base = current_app.config['ASSET_STORAGE_PATH']
        for item_detail in generated_items_details:
            for key in ['qr_code_path', 'passport_path', 'label_pdf_path']:
                if item_detail.get(key):
                    try: os.remove(os.path.join(asset_base, item_detail[key]))
                    except OSError: pass 
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail_exception', target_type='product', target_id=product_id, details=f"Failed for {product_code_str}: {str(e)}.", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to receive stock: {str(e)}", success=False), 500

@inventory_bp.route('/export/serialized_items', methods=['GET'])
@admin_required
def export_serialized_items_csv():
    db = get_db_connection(); audit_logger = current_app.audit_log_service; current_admin_id = get_jwt_identity()
    try:
        query_sql = """
            SELECT si.item_uid, p.product_code, COALESCE(pl_fr.name, p.name) AS product_name_fr, 
                   COALESCE(pl_en.name, p.name) AS product_name_en, pwo.weight_grams AS variant_weight_grams,
                   pwo.sku_suffix AS variant_sku_suffix, si.status, si.batch_number, si.production_date,
                   si.expiry_date, si.received_at, si.sold_at, si.cost_price, si.actual_weight_grams, si.notes
            FROM serialized_inventory_items si JOIN products p ON si.product_id = p.id
            LEFT JOIN product_localizations pl_fr ON p.id = pl_fr.product_id AND pl_fr.lang_code = 'fr'
            LEFT JOIN product_localizations pl_en ON p.id = pl_en.product_id AND pl_en.lang_code = 'en'
            LEFT JOIN product_weight_options pwo ON si.variant_id = pwo.id
            ORDER BY p.product_code, si.item_uid;
        """
        items_data = query_db(query_sql, db_conn=db)
        if not items_data:
            return jsonify(message="No serialized items found to export.", success=False), 404

        output = StringIO(); writer = csv.writer(output)
        headers = ['Item UID', 'Product Code', 'Product Name (FR)', 'Product Name (EN)', 'Variant Weight (g)', 'Variant SKU Suffix', 'Status', 'Batch Number', 'Production Date', 'Expiry Date', 'Received At', 'Sold At', 'Cost Price', 'Actual Weight (g)', 'Notes']
        writer.writerow(headers)
        for item_row in items_data:
            item = dict(item_row)
            writer.writerow([ item.get(h.lower().replace(' ', '_').replace('(', '').replace(')', ''), '') for h in headers ]) # Simplified mapping
        output.seek(0); timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"maison_truvra_serialized_inventory_{timestamp}.csv"
        audit_logger.log_action(user_id=current_admin_id, action='export_serialized_items_csv_success', details=f"Exported {len(items_data)} items.", status='success', ip_address=request.remote_addr)
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={filename}"})
    except Exception as e:
        current_app.logger.error(f"Error exporting CSV: {e}", exc_info=True)
        return jsonify(message="Failed to export serialized items.", success=False), 500

@inventory_bp.route('/import/serialized_items', methods=['POST'])
@admin_required
def import_serialized_items_csv():
    db = get_db_connection(); audit_logger = current_app.audit_log_service; current_admin_id = get_jwt_identity()
    if 'file' not in request.files: return jsonify(message="No file part in request.", success=False), 400
    file = request.files['file']
    if file.filename == '': return jsonify(message="No selected file.", success=False), 400
    if not file.filename.endswith('.csv'): return jsonify(message="Invalid file format. Only CSV.", success=False), 400

    imported = 0; updated = 0; failed = []; processed = 0
    try:
        stream = StringIO(file.stream.read().decode("UTF-8"), newline=None)
        reader = csv.DictReader(stream)
        headers = ['Product Code', 'Status'] # Required
        if not all(h in reader.fieldnames for h in headers):
            return jsonify(message=f"Missing CSV headers: {', '.join(h for h in headers if h not in reader.fieldnames)}", success=False), 400

        for row_num, row_dict in enumerate(reader, start=1):
            processed += 1; product_code = row_dict.get('Product Code', '').strip().upper()
            uid = row_dict.get('Item UID', '').strip(); variant_sku = row_dict.get('Variant SKU Suffix', '').strip().upper()
            status = row_dict.get('Status', 'available').strip()
            # ... (parse other fields: batch, dates, cost, weight, notes) ...
            prod_date = format_datetime_for_storage(parse_datetime_from_iso(row_dict.get('Production Date'))) if row_dict.get('Production Date') else None
            exp_date = format_datetime_for_storage(parse_datetime_from_iso(row_dict.get('Expiry Date'))) if row_dict.get('Expiry Date') else None
            cost = float(row_dict['Cost Price']) if row_dict.get('Cost Price') else None
            actual_weight = float(row_dict['Actual Weight (g)']) if row_dict.get('Actual Weight (g)') else None
            notes_csv = row_dict.get('Notes', '')

            if not product_code: failed.append({'row': row_num, 'uid': uid, 'error': 'Product Code missing.'}); continue
            prod_info = query_db("SELECT id, sku_prefix FROM products WHERE product_code = ?", [product_code], db_conn=db, one=True)
            if not prod_info: failed.append({'row': row_num, 'uid': uid, 'error': 'Product Code not found.'}); continue
            prod_id = prod_info['id']; prod_sku_prefix = prod_info.get('sku_prefix') or product_code

            var_id = None
            if variant_sku:
                var_info = query_db("SELECT id FROM product_weight_options WHERE product_id = ? AND sku_suffix = ?", [prod_id, variant_sku], db_conn=db, one=True)
                if not var_info: failed.append({'row': row_num, 'uid': uid, 'error': 'Variant SKU not found.'}); continue
                var_id = var_info['id']
            
            cursor = db.cursor()
            existing = query_db("SELECT id FROM serialized_inventory_items WHERE item_uid = ?", [uid], db_conn=db, one=True) if uid else None
            if existing:
                cursor.execute("UPDATE serialized_inventory_items SET status=?, batch_number=?, production_date=?, expiry_date=?, cost_price=?, actual_weight_grams=?, notes=?, product_id=?, variant_id=?, updated_at=CURRENT_TIMESTAMP WHERE item_uid=?",
                               (status, row_dict.get('Batch Number'), prod_date, exp_date, cost, actual_weight, notes_csv, prod_id, var_id, uid))
                updated += 1
            else:
                uid_to_insert = uid if uid else f"{prod_sku_prefix}-{uuid.uuid4().hex[:8].upper()}"
                while query_db("SELECT id FROM serialized_inventory_items WHERE item_uid = ?", [uid_to_insert], db_conn=db, one=True):
                    uid_to_insert = f"{prod_sku_prefix}-{uuid.uuid4().hex[:8].upper()}"
                cursor.execute("INSERT INTO serialized_inventory_items (item_uid, product_id, variant_id, status, batch_number, production_date, expiry_date, cost_price, actual_weight_grams, notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (uid_to_insert, prod_id, var_id, status, row_dict.get('Batch Number'), prod_date, exp_date, cost, actual_weight, notes_csv))
                ser_id = cursor.lastrowid
                record_stock_movement(db, prod_id, 'import_csv_new', 1, var_id, ser_id, "CSV Import", current_admin_id)
                imported += 1
        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='import_serialized_csv_success', details=f"Imported: {imported}, Updated: {updated}, Failed: {len(failed)} from {processed} rows.", status='success', ip_address=request.remote_addr)
        return jsonify(message="CSV import processed.", imported=imported, updated=updated, failed_rows=failed, total_processed=processed, success=True), 200
    except Exception as e:
        db.rollback(); current_app.logger.error(f"Error importing CSV: {e}", exc_info=True)
        return jsonify(message=f"Failed to import CSV: {str(e)}", success=False), 500

# Removed serve_label_pdf and serve_passport_html as they are covered by admin_api_bp.serve_asset and public asset serving
# These routes were admin-protected, so admin_api_bp.serve_asset is the correct replacement for admin access.
# Public access to passports is handled by serve_public_asset in __init__.py

@inventory_bp.route('/stock/adjust', methods=['POST'])
@admin_required
def adjust_stock():
    data = request.json; product_code = data.get('product_code'); variant_sku = data.get('variant_sku_suffix')
    qty_change_str = data.get('quantity_change'); reason = data.get('notes'); mov_type = data.get('movement_type')
    admin_id = get_jwt_identity(); audit = current_app.audit_log_service; db = get_db_connection()

    if not all([product_code, reason, mov_type]) or qty_change_str is None:
        return jsonify(message="Product Code, reason, movement type, and quantity change required", success=False), 400
    
    prod_id = get_product_id_from_code(product_code.upper(), db_conn=db)
    if not prod_id: return jsonify(message=f"Product code '{product_code}' not found.", success=False), 404
    
    var_id = None
    if variant_sku:
        var_info = query_db("SELECT id FROM product_weight_options WHERE product_id = ? AND sku_suffix = ?", [prod_id, variant_sku.upper()], db_conn=db, one=True)
        if not var_info: return jsonify(message=f"Variant SKU '{variant_sku}' not found.", success=False), 400
        var_id = var_info['id']
        
    cursor = db.cursor()
    try:
        qty_change = int(qty_change_str)
        allowed_mov = ['ajustement_manuel', 'correction', 'perte', 'retour_non_commande', 'addition', 'creation_lot', 'decouverte_stock', 'retour_client']
        if mov_type not in allowed_mov: return jsonify(message=f"Invalid movement type: {mov_type}", success=False), 400
        
        if qty_change != 0:
            if var_id: cursor.execute("UPDATE product_weight_options SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", (qty_change, var_id))
            else: cursor.execute("UPDATE products SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", (qty_change, prod_id))
        
        record_stock_movement(db, prod_id, mov_type, qty_change, var_id, reason=reason, related_user_id=admin_id, notes=reason)
        db.commit()
        audit.log_action(user_id=admin_id, action='adjust_stock_success', target_type='product', target_id=prod_id, details=f"Stock for {product_code} (var: {variant_sku or 'N/A'}) adjusted by {qty_change}. Reason: {reason}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Stock adjusted successfully", success=True), 200
    except ValueError as ve:
        db.rollback(); return jsonify(message=f"Invalid data: {ve}", success=False), 400
    except Exception as e:
        db.rollback(); current_app.logger.error(f"Error adjusting stock for {product_code}: {e}", exc_info=True)
        return jsonify(message="Failed to adjust stock", success=False), 500

@inventory_bp.route('/product/<string:product_code>', methods=['GET'])
@admin_required
def get_admin_product_inventory_details(product_code):
    db = get_db_connection(); variant_sku = request.args.get('variant_sku_suffix')
    prod_id = get_product_id_from_code(product_code.upper(), db_conn=db)
    if not prod_id: return jsonify(message="Product not found", success=False), 404

    try:
        prod_info = query_db("SELECT * FROM products WHERE id = ?", [prod_id], db_conn=db, one=True)
        if not prod_info: return jsonify(message="Product not found", success=False), 404
        details = dict(prod_info); var_id_filter = None
        
        if details['type'] == 'variable_weight':
            options = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [prod_id], db_conn=db)
            details['current_stock_by_variant'] = [dict(o) for o in options] if options else []
            details['calculated_total_variant_stock'] = sum(v.get('aggregate_stock_quantity',0) for v in details['current_stock_by_variant'])
            if variant_sku:
                match_var = next((v for v in details['current_stock_by_variant'] if v['sku_suffix'].upper() == variant_sku.upper()), None)
                if match_var: var_id_filter = match_var['option_id']
        
        mov_query = "SELECT * FROM stock_movements WHERE product_id = ?"
        mov_params = [prod_id]
        if var_id_filter: mov_query += " AND variant_id = ?"; mov_params.append(var_id_filter)
        elif variant_sku and not var_id_filter: details['stock_movements_log'] = [] # No match, no movements
        
        if not (variant_sku and not var_id_filter):
            mov_query += " ORDER BY movement_date DESC LIMIT 100"
            movements = query_db(mov_query, mov_params, db_conn=db)
            details['stock_movements_log'] = []
            if movements:
                for m in movements:
                    m_dict = dict(m); m_dict['movement_date'] = format_datetime_for_display(m_dict['movement_date'])
                    details['stock_movements_log'].append(m_dict)
        return jsonify(details=details, success=True), 200 # Return as object
    except Exception as e:
        current_app.logger.error(f"Error fetching admin inventory details for {product_code}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch inventory details", success=False), 500

@inventory_bp.route('/serialized/items/<string:item_uid>/status', methods=['PUT'])
@admin_required
def update_serialized_item_status(item_uid):
    data = request.json; new_status = data.get('status'); notes = data.get('notes', '')
    admin_id = get_jwt_identity(); audit = current_app.audit_log_service; db = get_db_connection()

    if not new_status: return jsonify(message="New status required", success=False), 400
    allowed = ['available', 'damaged', 'recalled', 'reserved_internal', 'missing']
    if new_status not in allowed: return jsonify(message=f"Invalid status. Allowed: {', '.join(allowed)}", success=False), 400

    cursor = db.cursor()
    try:
        item_info = query_db("SELECT id, product_id, variant_id, status, notes as current_notes FROM serialized_inventory_items WHERE item_uid = ?", [item_uid], db_conn=db, one=True)
        if not item_info: return jsonify(message="Item not found", success=False), 404
        item = dict(item_info); old_status = item['status']
        if old_status == new_status: return jsonify(message="Status unchanged.", item_status=new_status, success=True), 200

        updated_notes = item.get('current_notes', '') or ''
        if notes: updated_notes += f"\n[{format_datetime_for_display(None)} by AdminID:{admin_id}]: Status {old_status} -> {new_status}. Reason: {notes}"
        
        cursor.execute("UPDATE serialized_inventory_items SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE item_uid = ?", (new_status, updated_notes.strip(), item_uid))
        
        qty_change_agg = 0
        if old_status == 'available' and new_status != 'available': qty_change_agg = -1
        elif old_status != 'available' and new_status == 'available': qty_change_agg = 1
        
        if qty_change_agg != 0:
            if item['variant_id']: cursor.execute("UPDATE product_weight_options SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", (qty_change_agg, item['variant_id']))
            else: cursor.execute("UPDATE products SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", (qty_change_agg, item['product_id']))
        db.commit()
        audit.log_action(user_id=admin_id, action='update_item_status_success', target_type='serialized_item', target_id=item_uid, details=f"Status of {item_uid} from '{old_status}' to '{new_status}'. Notes: {notes}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Status of {item_uid} updated to {new_status}.", success=True), 200
    except Exception as e:
        db.rollback(); current_app.logger.error(f"Error updating status for {item_uid}: {e}", exc_info=True)
        return jsonify(message="Failed to update item status", success=False), 500

```
**Key changes for asset serving:**

* **`backend/__init__.py`:**
    * A new route `@app.route('/public-assets/<path:filepath>')` named `serve_public_asset` is added.
    * This route is designed to serve assets that are meant for public access (e.g., product images, category images, public HTML passports).
    * It includes logic to determine the correct base directory based on the `filepath` prefix (e.g., `products/`, `categories/`, `passports/`). You'll need to adjust the `base_serve_path` logic if your public asset structure is different.
    * Crucially, it includes security checks to prevent directory traversal.
    * The old `serve_passport_public` is commented out, assuming the new route can handle it. If `serve_passport_public` had very specific logic (like custom headers or processing), you might keep it or merge its logic.
    * Static folder configuration was also slightly adjusted for clarity, using `/static` as the URL path.
* **`backend/admin_api/routes.py`:**
    * The `serve_asset` route is refined. It now uses a dictionary `asset_type_map` to define valid base paths for different types of admin-accessible assets (QR codes, labels, invoices, professional documents). This makes it more secure and maintainable than checking multiple arbitrary base paths.
    * `url_for` calls within this file that generate links to assets (e.g., for product images, category images, passport URLs in `get_product_admin_detail` and `get_detailed_inventory_items_admin`) are updated to point to the new `serve_public_asset` route for assets that should be publicly viewable (like product/category images and HTML passports). Admin-specific assets like QR codes or labels generated by `asset_service.py` and stored in `ASSET_STORAGE_PATH` would still be served via `admin_api_bp.serve_asset` if they are meant for admin eyes only or require admin authentication to download.
* **`backend/inventory/routes.py`:**
    * The `serve_label_pdf` and `serve_passport_html` routes have been **removed**.
        * Admin access to labels and passports (if needed directly via a URL) should now go through `admin_api_bp.serve_asset`.
        * Public access to passports is handled by `serve_public_asset` in `__init__.py`.
    * When generating assets in `receive_serialized_stock`, the `passport_url_for_qr` now correctly points to the public asset serving route.

**Important Considerations for Asset Serving:**

1.  **Security:** The path traversal checks are basic. Ensure `os.path.realpath` is used correctly to prevent any exploits.
2.  **Configuration:** Your `UPLOAD_FOLDER` and `ASSET_STORAGE_PATH` in `config.py` must be correctly set up. The public asset serving route needs to know where to find these files. You might consider a dedicated `PUBLIC_ASSET_FOLDER` config variable if your public assets are stored separately from general uploads or admin-generated assets.
3.  **URL Generation:** Double-check all `url_for()` calls throughout your Flask app that link to assets. Ensure they use the correct endpoint (`serve_public_asset` for public, `admin_api_bp.serve_asset` for admin-protected).
4.  **File Structure:** The logic in `serve_public_asset` and `admin_api_bp.serve_asset` assumes a certain structure for `filepath` (e.g., `products/image.jpg`). Ensure your file saving logic (e.g., in `create_product`, `create_category`, `asset_service.py`) stores files in paths that match this expectation.

Now, let's move on to consolidating the CSS. I will update `website/source/admin/admin_manage_categories.html` and `website/source/admin/js/css/admin_style.css` as an example.


```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - Manage Categories</title>
    <link rel="stylesheet" href="css/admin_style.css"> 
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" rel="stylesheet">
</head>
<body id="page-admin-manage-categories"> <header class="bg-white shadow-md p-4 sticky top-0 z-50">
        <div class="container mx-auto flex justify-between items-center">
            <div class="flex items-center space-x-4">
                <a href="admin_dashboard.html" id="back-to-dashboard-button" class="text-indigo-600 hover:text-indigo-800 font-medium text-sm flex items-center hidden">
                    <i class="fas fa-arrow-left mr-2"></i>
                    Retour au Tableau de Bord
                </a>
                <div id="admin-header-title-area">
                     <h1 class="text-xl font-semibold text-gray-700">Maison Trüvra - Admin</h1>
                </div>
            </div>
            <div class="flex items-center space-x-4">
                <span id="admin-user-greeting" class="text-gray-700 text-sm mr-2"></span>
                <button id="admin-logout-button" class="bg-red-600 hover:bg-red-700 text-white font-semibold py-2 px-3 rounded text-sm flex items-center">
                    <i class="fas fa-sign-out-alt mr-2"></i>Déconnexion
                </button>
            </div>
        </div>
    </header>

    <nav class="bg-gray-800 text-white shadow-md">
        <div class="container mx-auto px-4">
            <div class="flex items-center justify-start h-12 space-x-1">
                <a href="admin_dashboard.html" class="admin-nav-link px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700">Tableau de Bord</a>
                <a href="admin_manage_products.html" class="admin-nav-link px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700">Produits</a>
                <a href="admin_manage_inventory.html" class="admin-nav-link px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700">Inventaire</a>
                <a href="admin_manage_orders.html" class="admin-nav-link px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700">Commandes</a>
                <a href="admin_manage_users.html" class="admin-nav-link px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700">Utilisateurs</a>
                <a href="admin_manage_categories.html" class="admin-nav-link px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 active">Catégories</a>
                </div>
        </div>
    </nav>
    <main class="admin-content-area container mx-auto p-6 space-y-6">
        <h2 class="text-2xl font-semibold text-gray-800">Manage Categories</h2>

        <div id="categoryFormContainer" class="admin-form-container bg-white p-6 rounded-lg shadow-md">
            <h3 class="text-xl font-semibold text-gray-700 mb-4"><span id="categoryFormTitle">Add New Category</span></h3>
            <form id="categoryForm" class="admin-form space-y-4">
                <div>
                    <label for="categoryCode" class="form-label">Category Code: <span class="required">*</span></label>
                    <input type="text" id="categoryCode" name="category_code" required class="form-input-admin">
                    <small class="form-text">Unique code for the category (e.g., MIEL, HUILE, SAVON).</small>
                </div>
                <div>
                    <label for="categoryName" class="form-label">Category Name: <span class="required">*</span></label>
                    <input type="text" id="categoryName" name="name" required class="form-input-admin">
                </div>
                <div>
                    <label for="categoryDescription" class="form-label">Description:</label>
                    <textarea id="categoryDescription" name="description" class="form-input-admin" rows="3"></textarea>
                </div>
                <div>
                    <label for="categoryImageUrl" class="form-label">Image URL:</label>
                    <input type="url" id="categoryImageUrl" name="image_url" placeholder="https://example.com/category_image.jpg" class="form-input-admin">
                </div>
                <div class="flex items-center">
                    <input type="checkbox" id="categoryIsActive" name="is_active" checked class="form-checkbox-admin">
                    <label for="categoryIsActive" class="ml-2 form-label-inline">Is Active (visible on site)</label>
                </div>
                <div class="flex space-x-2">
                    <button type="submit" id="saveCategoryButton" class="btn btn-admin-primary">Save Category</button>
                    <button type="button" id="cancelCategoryEditButton" class="btn btn-admin-secondary" style="display:none;">Cancel Edit</button>
                </div>
            </form>
        </div>

        <div id="categoriesTableContainer" class="bg-white p-6 rounded-lg shadow-md">
            <h3 class="text-xl font-semibold text-gray-700 mb-4">Existing Categories</h3>
            <div class="overflow-x-auto">
                <table id="categoriesTable" class="admin-table min-w-full">
                    <thead>
                        <tr>
                            <th>Code</th>
                            <th>Name</th>
                            <th>Description</th>
                            <th>Active</th>
                            <th>Products</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="categoriesTableBody">
                        <tr><td colspan="6" class="text-center py-4">Loading categories...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </main>

    <footer class="admin-footer text-center py-4 mt-6 bg-gray-200 text-sm text-gray-600">
        <p>&copy; <span id="currentYearCategories"></span> Maison Trüvra - Admin Panel</p>
    </footer>

    <div id="admin-toast-container" class="fixed bottom-0 right-0 p-4 space-y-2 z-[1051]"></div>

    <script src="js/admin_config.js"></script>
    <script src="js/admin_ui.js"></script>
    <script src="js/admin_api.js"></script>
    <script src="js/admin_auth.js"></script>
    <script src="js/admin_main.js"></script>
    <script src="js/admin_categories.js"></script>
    <script>
        // This can be moved to admin_main.js if it's a common footer element
        const currentYearSpanCategories = document.getElementById('currentYearCategories');
        if (currentYearSpanCategories) {
            currentYearSpanCategories.textContent = new Date().getFullYear();
        }
    </script>
</body>
</html>
```


```css
/* General Body and Resets */
body {
    font-family: 'Inter', sans-serif; /* Assuming Inter is preferred, fallback to sans-serif */
    margin: 0;
    background-color: #F5F5F4; /* bg-stone-100 */
    color: #44403C; /* text-stone-700 */
    display: flex;
    flex-direction: column; /* Ensure body takes full height for footer */
    min-height: 100vh; /* Full viewport height */
    overflow-x: hidden; /* Prevent horizontal scroll on body */
}

* {
    box-sizing: border-box;
}

a {
    color: #D97706; /* amber-600 - Brand Accent */
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

/* Layout: Sidebar and Main Content - This seems to be from an older layout.
   The current HTML structure (e.g., admin_manage_categories) uses a simpler header/nav/main.
   I'll keep some general admin layout styles that might be useful.
*/

/* Common Admin Header (used in provided HTMLs) */
header.bg-white { /* Styles for the main admin header bar */
    /* Tailwind classes handle most of this: bg-white shadow-md p-4 sticky top-0 z-50 */
}
header.bg-white .container { /* Tailwind: mx-auto flex justify-between items-center */ }
header.bg-white #admin-header-title-area h1 { /* Tailwind: text-xl font-semibold text-gray-700 */ }
header.bg-white #admin-user-greeting { /* Tailwind: text-gray-700 text-sm mr-2 */ }
header.bg-white #admin-logout-button { /* Tailwind: bg-red-600 hover:bg-red-700 text-white font-semibold py-2 px-3 rounded text-sm flex items-center */ }
header.bg-white #admin-logout-button i { /* Tailwind: mr-2 */ }


/* Common Admin Navigation (used in provided HTMLs) */
nav.bg-gray-800 { /* Tailwind: bg-gray-800 text-white shadow-md */ }
nav.bg-gray-800 .container { /* Tailwind: mx-auto px-4 */ }
nav.bg-gray-800 .admin-nav-link {
    /* Tailwind: px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 */
    color: #E5E7EB; /* Default link color on dark nav */
    transition: background-color 0.2s ease, color 0.2s ease;
}
nav.bg-gray-800 .admin-nav-link:hover {
    background-color: #4B5563; /* gray-700 */
    color: #FFFFFF;
}
nav.bg-gray-800 .admin-nav-link.active {
    background-color: #374151; /* gray-900 or a brand accent color */
    color: #FFFFFF;
    font-weight: 500;
}


/* Main Content Area */
main.admin-content-area { /* General wrapper for content below nav */
    /* Tailwind: container mx-auto p-6 space-y-6 */
    flex-grow: 1; /* Allow main content to take remaining space */
}

main.admin-content-area h2 { /* General h2 style within main content */
    /* Tailwind: text-2xl font-semibold text-gray-800 */
    /* Can add margin-bottom here if consistent, e.g., mb-6 */
}

/* Form Container Styling */
.admin-form-container {
    /* Tailwind: bg-white p-6 rounded-lg shadow-md */
    margin-bottom: 1.5rem; /* space-y-6 on parent implies this */
}
.admin-form-container h3 {
    /* Tailwind: text-xl font-semibold text-gray-700 mb-4 */
}

/* General Admin Form Styling */
.admin-form {
    /* Tailwind: space-y-4 */
}
.admin-form .form-label {
    display: block;
    font-size: 0.875rem; /* text-sm */
    font-weight: 500; /* font-medium */    
    color: #292524; /* stone-800 */
    margin-bottom: 0.25rem; /* mb-1 */
}
.admin-form .form-label-inline { /* For labels next to checkboxes */
    display: inline;
    margin-left: 0.5rem; /* ml-2 */
}

.admin-form .form-input-admin,
.admin-form input[type="text"],
.admin-form input[type="email"],
.admin-form input[type="password"],
.admin-form input[type="number"],
.admin-form input[type="date"],
.admin-form input[type="url"],
.admin-form select,
.admin-form textarea {
    display: block;
    width: 100%;
    padding: 0.5rem 0.75rem; /* py-2 px-3 */
    font-size: 0.875rem; /* text-sm */
    border: 1px solid #D6D3D1; /* stone-300 / gray-300 */
    border-radius: 0.375rem; /* rounded-md */
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); /* shadow-sm */
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.admin-form .form-input-admin:focus,
.admin-form input[type="text"]:focus,
.admin-form input[type="email"]:focus,
.admin-form input[type="password"]:focus,
.admin-form input[type="number"]:focus,
.admin-form input[type="date"]:focus,
.admin-form input[type="url"]:focus,
.admin-form select:focus,
.admin-form textarea:focus {
    outline: none;
    border-color: #6366F1; /* indigo-500 (Tailwind focus color) */
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.3); /* indigo focus ring */
}
.admin-form textarea.form-input-admin {
    min-height: 80px;
}

.admin-form .form-checkbox-admin {
    height: 1rem; /* h-4 */
    width: 1rem; /* w-4 */
    border-radius: 0.25rem; /* rounded */
    border-color: #D6D3D1; /* stone-300 / gray-300 */
    color: #6366F1; /* indigo-600 (checked color) */
    vertical-align: middle;
}
.admin-form .form-checkbox-admin:focus {
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.3); /* indigo focus ring */
}

.admin-form .form-text { /* For small helper text below inputs */
    font-size: 0.75rem; /* text-xs */
    color: #71717A; /* stone-500 / gray-500 */
    display: block;
    margin-top: 0.25rem; /* mt-1 */
}
.admin-form .required {
    color: #EF4444; /* red-500 */
    margin-left: 2px;
}


/* Tables */
.admin-table-container { /* Wrapper for table if needed, e.g., for responsive overflow */
    /* Tailwind: bg-white p-6 rounded-lg shadow-md */
    margin-bottom: 1.5rem;
}
.admin-table-container h3 {
    /* Tailwind: text-xl font-semibold text-gray-700 mb-4 */
}
.admin-table {
    min-width: 100%; /* min-w-full */
    border-collapse: collapse; 
    /* Tailwind divide-y divide-gray-200 handles borders between rows */
}
.admin-table thead {
    background-color: #F9FAFB; /* gray-50 */
}
.admin-table th {
    padding: 0.75rem 1.5rem; /* px-6 py-3 */
    text-align: left;
    font-size: 0.75rem; /* text-xs */
    font-weight: 500; /* font-medium */
    color: #4B5563; /* gray-500 */
    text-transform: uppercase;
    letter-spacing: 0.05em; /* tracking-wider */
    border-bottom: 1px solid #E5E7EB; /* gray-200 */
}
.admin-table tbody {
    background-color: #ffffff; /* bg-white */
    /* divide-y divide-gray-200 */
}
.admin-table tbody tr:nth-child(even) {
    background-color: #F9FAFB; /* gray-50 for alternating rows */
}
.admin-table td {
    padding: 0.75rem 1.5rem; /* px-6 py-3 */
    font-size: 0.875rem; /* text-sm */
    color: #374151; /* gray-700 */
    white-space: nowrap; 
    border-bottom: 1px solid #E5E7EB; /* gray-200 */
}
.admin-table tbody tr:last-child td {
    border-bottom: none;
}
.admin-table .action-buttons button,
.admin-table .action-buttons a {
    margin-right: 0.5rem;
}
.admin-table .action-buttons button:last-child,
.admin-table .action-buttons a:last-child {
    margin-right: 0;
}


/* Buttons (General .btn class and specific admin ones) */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem 1rem; /* py-2 px-4 */
    font-size: 0.875rem; /* text-sm */
    font-weight: 500; /* font-medium */
    border-radius: 0.375rem; /* rounded-md */
    border: 1px solid transparent;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); /* shadow-sm */
    cursor: pointer;
    transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease, opacity 0.2s ease;
}
.btn:focus {
    outline: none;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.4); /* indigo focus ring */
}
.btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}
.btn i { /* For FontAwesome icons inside buttons */
    margin-right: 0.5rem;
}

.btn-admin-primary {
    background-color: #4F46E5; /* indigo-600 */
    color: #ffffff;
}
.btn-admin-primary:hover { background-color: #4338CA; /* indigo-700 */ }

.btn-admin-secondary {
    background-color: #6B7280; /* gray-500 */
    color: #ffffff;
}
.btn-admin-secondary:hover { background-color: #4B5563; /* gray-600 */ }

.btn-admin-danger, .btn.delete { /* Added .btn.delete for consistency */
    background-color: #EF4444; /* red-500 */
    color: #ffffff;
}
.btn-admin-danger:hover, .btn.delete:hover { background-color: #DC2626; /* red-600 */ }

.btn.small-button { /* For table action buttons */
    padding: 0.375rem 0.75rem; /* py-1.5 px-3 */
    font-size: 0.75rem; /* text-xs */
}


/* Admin Footer */
.admin-footer {
    /* Tailwind: text-center py-4 mt-6 bg-gray-200 text-sm text-gray-600 */
    margin-top: auto; /* Push footer to bottom if body is flex-col */
}


/* Login Page Specific Styles (from admin_login.html and previous admin_style.css) */
body#page-admin-login { /* Target specific body ID */
    /* Tailwind: bg-gray-100 flex items-center justify-center h-screen */
}
.admin-login-container {
    /* Tailwind: bg-white p-8 rounded-lg shadow-xl w-full max-w-md */
}
.admin-login-container .logo-container {
    /* Tailwind: text-center mb-8 */
}
.admin-login-container .logo-container i { /* FontAwesome icon */
    /* Tailwind: fa-3x text-gray-700 */
}
.admin-login-container .logo-container h1 {
    /* Tailwind: text-3xl font-bold text-gray-800 mt-2 */
}
.admin-login-container .logo-container p {
    /* Tailwind: text-gray-600 */
}
.admin-login-container form {
    /* Tailwind: space-y-6 */
}
.admin-login-container .input-group { /* If you use this class for icon inputs */
    position: relative;
}
.admin-login-container .input-group .icon {
    position: absolute;
    left: 0.75rem; /* pl-3 */
    top: 50%;
    transform: translateY(-50%);
    pointer-events: none;
    color: #9CA3AF; /* gray-400 */
}
.admin-login-container .input-group input.form-input-admin { /* If icon is present */
    padding-left: 2.5rem; /* pl-10 */
}
.admin-login-container #login-error-message {
    /* Tailwind: hidden text-red-500 text-sm text-center min-h-[1.25rem] */
    /* min-height ensures space even when hidden, adjust if needed */
}
.admin-login-container .login-button {
    /* Tailwind: w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 */
}
.admin-login-container .back-to-site-link {
    /* Tailwind: mt-6 text-center text-sm text-gray-500 */
}
.admin-login-container .back-to-site-link a {
    /* Tailwind: font-medium text-indigo-600 hover:text-indigo-500 */
}


/* Modals (from previous admin_style.css, ensure consistency with Tailwind if modals are built with it) */
.admin-modal-overlay {
    display: none; 
    position: fixed; 
    z-index: 1050; /* Ensure it's above other content, e.g. sticky header */
    inset: 0;
    overflow-y: auto;
    background-color: rgba(0, 0, 0, 0.6); 
    align-items: center; 
    justify-content: center; 
    padding: 1rem; /* Padding for smaller screens */
}
.admin-modal-overlay.active {
    display: flex; 
}

.admin-modal-content {
    background-color: #ffffff;
    border-radius: 0.5rem; /* rounded-lg */
    text-align: left;
    overflow: hidden;
    box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04); /* shadow-xl */
    transform: scale(0.95);
    transition: transform 0.3s ease-out, opacity 0.3s ease-out;
    opacity: 0;
    margin: 1rem auto; /* my-8 for sm, p-0 for sm */
    width: 100%;
    max-width: 32rem; /* default max-w-lg, can be overridden */
    display: flex;
    flex-direction: column;
}
.admin-modal-overlay.active .admin-modal-content {
    transform: scale(1);
    opacity: 1;
}

/* Specific modal sizes (can be added as classes to .admin-modal-content) */
.admin-modal-content.sm-max-w-md { max-width: 28rem; }
.admin-modal-content.sm-max-w-lg { max-width: 32rem; }
.admin-modal-content.sm-max-w-xl { max-width: 36rem; }
.admin-modal-content.sm-max-w-2xl { max-width: 42rem; }
.admin-modal-content.sm-max-w-3xl { max-width: 48rem; }


.admin-modal-header {
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #e5e7eb; /* gray-200 */
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.admin-modal-header h3 {
    font-size: 1.125rem; /* text-lg */
    line-height: 1.5rem; /* leading-6 */
    font-weight: 500; /* font-medium */
    color: #1F2937; /* gray-800 */
    margin: 0;
}
.admin-modal-close {
    color: #6B7280; /* gray-500 */
    font-size: 1.5rem; /* text-2xl */
    font-weight: bold;
    cursor: pointer;
    padding: 0.25rem;
    line-height: 1;
    background: none;
    border: none;
}
.admin-modal-close:hover,
.admin-modal-close:focus {
    color: #1F2937; /* gray-800 */
    text-decoration: none;
}

.admin-modal-body {
    padding: 1.5rem; /* p-6 */
    font-size: 0.875rem; /* text-sm */
    color: #374151; /* gray-700 */
    line-height: 1.6;
    flex-grow: 1; /* Allow body to expand if content is large */
    overflow-y: auto; /* Scroll for large content */
}
.admin-modal-body p {
    margin-top: 0;
    margin-bottom: 1rem;
}
.admin-modal-body strong {
    color: #1F2937; /* gray-800 */
}

.admin-modal-actions {
    background-color: #F9FAFB; /* gray-50 */
    padding: 0.75rem 1.5rem; /* px-4 py-3 sm:px-6 */
    display: flex;
    flex-direction: row-reverse; /* Align buttons to the right */
    border-top: 1px solid #e5e7eb; /* gray-200 */
    border-bottom-left-radius: 0.5rem;
    border-bottom-right-radius: 0.5rem;
}
.admin-modal-actions .btn { /* Use .btn for modal buttons */
    margin-left: 0.75rem; /* sm:ml-3 */
}
.admin-modal-actions .btn:first-child { /* The rightmost button in flex-row-reverse */
    margin-left: 0;
}


/* Toast / Global Messages (from admin_ui.js logic and admin_style.css) */
#admin-toast-container { 
    position: fixed;
    bottom: 1.25rem; /* bottom-5 */
    right: 1.25rem; /* right-5 */
    z-index: 1051; /* Ensure above modals if they are 1050 */
    display: flex;
    flex-direction: column-reverse; /* New toasts appear on top */
    gap: 0.5rem; /* space-y-2 */
}

.admin-toast { /* Class for individual toast messages */
    padding: 1rem; /* p-4 */
    border-radius: 0.5rem; /* rounded-lg */
    box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05); /* shadow-xl */
    color: #ffffff;
    min-width: 250px;
    max-width: 400px;
    opacity: 0;
    transform: translateY(20px);
    transition: opacity 0.3s ease-out, transform 0.3s ease-out;
}
.admin-toast.show {
    opacity: 1;
    transform: translateY(0);
}
.admin-toast.success { background-color: #10B981; } /* green-500 */
.admin-toast.error   { background-color: #EF4444; } /* red-500 */
.admin-toast.info    { background-color: #3B82F6; } /* blue-500 */
.admin-toast.warning { background-color: #F59E0B; } /* amber-500 */


/* Styles for product form weight options (from admin_manage_products_inventory.html) */
.weight-option-row {
    background-color: #f9fafb; 
    border: 1px solid #e5e7eb;
    padding: 0.75rem;
    border-radius: 0.375rem;
    margin-bottom: 0.5rem;
    /* Using grid for layout within each row if needed */
}
.weight-option-row label {
    font-size: 0.75rem; /* text-xs */
}
.weight-option-row input.form-input-admin { /* Apply admin input style */
    padding: 0.5rem; 
    font-size: 0.875rem; 
}
.weight-option-row button.btn-admin-danger { /* For the "Retirer" button */
    align-self: flex-end; 
}

/* For product assets preview section (from admin_manage_products_inventory.html) */
#product-assets-preview-section {
    margin-top: 1.5rem;
    padding: 1rem;
    border: 1px dashed #ccc;
    border-radius: 0.375rem;
    background-color: #f9fafb;
}
#product-assets-preview-section h4 {
    font-size: 1rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
}
#product-assets-links p {
    margin-bottom: 0.5rem;
    font-size: 0.875rem;
}
#product-assets-links a {
    word-break: break-all;
}
#product-assets-links img {
    border: 1px solid #ddd;
    border-radius: 0.25rem;
    margin-top: 0.25rem;
    max-width: 100px; /* Example size */
    height: auto;
}

/* Error message styling for form fields */
.error-message {
    color: #EF4444; /* text-red-500 */
    font-size: 0.75rem; /* text-xs */
    margin-top: 0.25rem; /* mt-1 */
}
input.border-red-500, /* For Tailwind compatibility if used alongside */
select.border-red-500,
textarea.border-red-500,
.form-input-admin.error-field { /* Custom class for non-Tailwind error indication */
    border-color: #EF4444 !important; 
}
input.border-red-500:focus,
select.border-red-500:focus,
textarea.border-red-500:focus,
.form-input-admin.error-field:focus {
    border-color: #EF4444 !important;
    box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.3) !important; /* Red focus ring */
}   
