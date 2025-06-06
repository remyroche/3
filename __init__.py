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
from flask_wtf.csrf import CSRFProtect

from .config import get_config_by_name
from .audit_log_service import AuditLogService

# Initialize extensions without app object yet
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)
talisman = Talisman()
csrf = CSRFProtect() # Initialize CSRFProtect

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
    csrf.init_app(app) # Initialize CSRF protection for the app
    
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

    box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.3) !important; /* Red focus ring */
}   
