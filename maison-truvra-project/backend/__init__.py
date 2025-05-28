from flask import Flask, request, g, jsonify, send_from_directory, current_app
from flask_cors import CORS
from flask_jwt_extended import JWTManager # Added for JWT setup
import os
import logging

# Assuming AppConfig is correctly defined in .config
from .config import get_config_by_name, Config, AppConfig # Ensure AppConfig is imported or use Config directly

# Updated database import
from .database import register_db_commands, init_db_schema, populate_initial_data

# Import AuditLogService
from ..audit_log_service import AuditLogService # Assuming audit_log_service.py is in maison-truvra-project/

def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    
    app_config = get_config_by_name(config_name)

    # Ensure static_folder path is robust
    # Project root is two levels up from backend directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Default static folder to 'website/static_assets' relative to project_root
    default_static_folder = os.path.join(project_root, 'website', 'static_assets')
    
    app = Flask(__name__,
                instance_path=os.path.join(project_root, 'instance'), # Instance folder in project root
                static_folder=app_config.get('STATIC_FOLDER', default_static_folder),
                static_url_path=app_config.get('STATIC_URL_PATH', '/static_assets')) # Common static URL

    app.config.from_object(app_config)

    # Ensure instance path exists (for SQLite DB, uploads, etc.)
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        # Also ensure critical subdirectories defined in config are created
        # This is already handled by get_config_by_name, but good to be aware
    except OSError as e:
        app.logger.error(f"Could not create instance path at {app.instance_path}: {e}")
        pass 

    # Initialize CORS
    CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", "*").split(',')}})

    # Setup logging
    log_level_str = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logging.basicConfig(level=log_level,
                        format='%(asctime)s %(levelname)s: %(message)s [%(name)s:%(lineno)d]',
                        datefmt='%Y-%m-%dT%H:%M:%S%z')
    app.logger.setLevel(log_level)
    app.logger.info(f"Maison Trüvra App starting with config: {config_name}")
    app.logger.info(f"Database path: {app.config['DATABASE_PATH']}")
    app.logger.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    app.logger.info(f"Asset storage path: {app.config['ASSET_STORAGE_PATH']}")


    # Initialize JWTManager
    app.jwt = JWTManager(app) # Use app.jwt to avoid conflicts if JWTManager is imported elsewhere

    # Initialize Database and Commands
    with app.app_context():
        init_db_schema()  # Initializes schema from schema.sql
        populate_initial_data() # Populates initial admin user, etc.
    register_db_commands(app) # Registers CLI commands like 'flask init-db'

    # Initialize AuditLogService
    # The AuditLogService in maison-truvra-project expects app object
    app.audit_log_service = AuditLogService(app=app)
    app.logger.info("AuditLogService initialized and attached to app.")


    # Register Blueprints
    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .products import products_bp
    app.register_blueprint(products_bp)

    from .orders import orders_bp
    app.register_blueprint(orders_bp)
    
    from .newsletter import newsletter_bp
    app.register_blueprint(newsletter_bp) # Ensure prefix is /api as per its __init__

    from .inventory import inventory_bp 
    app.register_blueprint(inventory_bp)

    from .admin_api import admin_api_bp 
    app.register_blueprint(admin_api_bp)
    
    from .professionnal import professional_bp # Assuming professional_bp is defined
    app.register_blueprint(professional_bp)

    app.logger.info("Blueprints registered.")

    # Global before_request for JWT user loading (if needed by g.current_user_id)
    @app.before_request
    def load_user_from_token():
        # This is a basic example. flask_jwt_extended typically handles
        # this implicitly when routes are decorated with @jwt_required.
        # If you need g.current_user_id outside protected routes, you might
        # try to verify token optionally.
        g.current_user_id = None
        g.is_admin = False
        try:
            # This is just an example, typically you wouldn't need to do this manually
            # if your routes are protected. But if some routes are optional-auth:
            # verify_jwt_in_request(optional=True)
            # current_user = get_jwt_identity()
            # if current_user:
            #     g.current_user_id = current_user
            #     claims = get_jwt()
            #     g.is_admin = claims.get('role') == 'admin'
            pass # For now, let specific routes handle identity via @jwt_required
        except Exception as e:
            # app.logger.debug(f"No valid JWT in request or error: {e}")
            pass


    # Simple root endpoint
    @app.route('/')
    @app.route('/api')
    def api_root():
        return jsonify({
            "message": "Welcome to the Maison Trüvra API!",
            "version": app.config.get("API_VERSION", "1.0.0"),
            "documentation": "/api/docs" # Placeholder
        })

    # Route to serve generated assets like passports, QR codes, labels if they are stored
    # within a publicly accessible part of the static folder or a dedicated asset folder.
    # The admin_api/routes.py has an /api/admin/assets/<path:asset_relative_path>
    # which is admin-protected. If public access is needed:
    @app.route('/assets/passports/<filename>')
    def serve_passport_public(filename):
        # Ensure this path aligns with how passports are stored and made public
        passport_dir = os.path.join(app.config['ASSET_STORAGE_PATH'], 'passports')
        app.logger.debug(f"Attempting to serve public passport: {filename} from {passport_dir}")
        # Add security checks for filename (e.g., secure_filename or path traversal checks)
        if ".." in filename or filename.startswith("/"):
            from flask import abort
            return abort(404)
        return send_from_directory(passport_dir, filename)
        
    # Similar routes can be added for public QR codes or labels if needed.

    return app