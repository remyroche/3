from flask import Flask, request, g, jsonify, send_from_directory, current_app
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity, get_jwt
import os
import logging

from .config import get_config_by_name # AppConfig is part of Config object now
from .database import register_db_commands, init_db_schema, populate_initial_data
from ..audit_log_service import AuditLogService # Corrected import path

def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    
    app_config = get_config_by_name(config_name)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_static_folder = os.path.join(project_root, 'website', 'static_assets') # For general static assets
    
    # Admin panel static files (Tailwind CSS based ones) are in `admin/` directory,
    # typically served by Flask's static handling or a web server.
    # If `admin/` is meant to be the new static root for admin pages:
    # admin_static_folder = os.path.join(project_root, 'admin')
    # For now, assuming Flask serves from `static_folder` for general assets,
    # and admin HTMLs correctly reference their CSS.

    app = Flask(__name__,
                instance_path=os.path.join(project_root, 'instance'),
                static_folder=app_config.get('STATIC_FOLDER', default_static_folder),
                static_url_path=app_config.get('STATIC_URL_PATH', '/static_assets'))

    app.config.from_object(app_config)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        app.logger.error(f"Could not create instance path at {app.instance_path}: {e}")
        pass 

    CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", "*").split(',')}})

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

    app.jwt = JWTManager(app)

    with app.app_context():
        init_db_schema()
        populate_initial_data()
    register_db_commands(app)

    app.audit_log_service = AuditLogService(app=app)
    app.logger.info("AuditLogService initialized and attached to app.")

    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .products import products_bp
    app.register_blueprint(products_bp)

    from .orders import orders_bp
    app.register_blueprint(orders_bp)
    
    from .newsletter import newsletter_bp
    app.register_blueprint(newsletter_bp)

    from .inventory import inventory_bp 
    app.register_blueprint(inventory_bp)

    from .admin_api import admin_api_bp 
    app.register_blueprint(admin_api_bp)
    
    from .professionnal import professional_bp
    app.register_blueprint(professional_bp)

    app.logger.info("Blueprints registered.")

    @app.before_request
    def load_user_from_token_if_present():
        g.current_user_id = None
        g.current_user_role = None
        g.is_admin = False # Explicitly set default
        try:
            # This attempts to verify a JWT in the request. If it's not present,
            # or invalid (and optional=True), it won't raise an exception.
            verify_jwt_in_request(optional=True)
            current_user_identity = get_jwt_identity() # Returns None if no JWT or not verified
            if current_user_identity:
                g.current_user_id = current_user_identity
                claims = get_jwt() # Returns None if no JWT or not verified
                if claims:
                    g.current_user_role = claims.get('role')
                    g.is_admin = (claims.get('role') == 'admin')
                # app.logger.debug(f"User loaded from token: ID={g.current_user_id}, Role={g.current_user_role}, IsAdmin={g.is_admin}")
        except Exception as e:
            # app.logger.debug(f"No valid JWT in request or error during user loading: {e}")
            pass # Silently pass if no token or if optional verification fails

    @app.route('/')
    @app.route('/api')
    def api_root():
        return jsonify({
            "message": "Welcome to the Maison Trüvra API!",
            "version": app.config.get("API_VERSION", "1.0.0"),
            "documentation_url": "/api/docs" # Placeholder
        })

    # Publicly accessible asset serving for generated passports.
    # QR codes and labels might be served directly if their paths are relative to static_assets.
    @app.route('/assets/passports/<path:filename>')
    def serve_passport_public(filename):
        passport_dir = os.path.join(app.config['ASSET_STORAGE_PATH'], 'passports')
        app.logger.debug(f"Attempting to serve public passport: {filename} from {passport_dir}")
        # Basic security check for filename
        if ".." in filename or filename.startswith("/"):
            from flask import abort
            return abort(404)
        return send_from_directory(passport_dir, filename, as_attachment=False)

    return app
