from flask import Flask, request, g, jsonify, send_from_directory, current_app
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity, get_jwt
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import logging

from .config import get_config_by_name
from .database import register_db_commands, init_db_schema, populate_initial_data
from audit_log_service import AuditLogService

def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    
    app_config = get_config_by_name(config_name)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_static_folder = os.path.join(project_root, 'website', 'static_assets')

    app = Flask(__name__,
                instance_path=os.path.join(project_root, 'instance'),
                static_folder=app_config.STATIC_FOLDER if hasattr(app_config, 'STATIC_FOLDER') else default_static_folder,
                static_url_path=app_config.STATIC_URL_PATH if hasattr(app_config, 'STATIC_URL_PATH') else '/static_assets')

    app.config.from_object(app_config)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        app.logger.error(f"Could not create instance path at {app.instance_path}: {e}")
        pass 

    # Initialize CORS
    CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", "*").split(',')}})
    app.logger.info(f"CORS configured for origins: {app.config.get('CORS_ORIGINS', '*')}")

    # Initialize Logging
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
    app.jwt = JWTManager(app)

    # Initialize Database
    with app.app_context():
        init_db_schema()
        populate_initial_data()
    register_db_commands(app)

    # Initialize AuditLogService
    app.audit_log_service = AuditLogService(app=app)
    app.logger.info("AuditLogService initialized and attached to app.")

    # Initialize Flask-Talisman for security headers
    # CSP is defined in config.py
    Talisman(
        app,
        content_security_policy=app.config.get('CONTENT_SECURITY_POLICY'),
        force_https=app.config.get('TALISMAN_FORCE_HTTPS', False) # In production, this should be True if behind a proxy handling TLS
    )
    app.logger.info("Flask-Talisman initialized for security headers.")

    # Initialize Flask-Limiter for rate limiting
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[app.config.get('DEFAULT_RATE_LIMIT_DAY', "200 per day"), app.config.get('DEFAULT_RATE_LIMIT_HOUR', "50 per hour")],
        storage_uri=app.config.get('LIMITER_STORAGE_URI', "memory://"), # Use Redis/Memcached in production
        strategy="fixed-window" # or "moving-window"
    )
    app.limiter = limiter # Make it accessible for route-specific limits if needed
    app.logger.info(f"Flask-Limiter initialized with default limits.")


    # Register Blueprints
    from .auth import auth_bp
    app.register_blueprint(auth_bp)
    limiter.limit(app.config.get('AUTH_RATE_LIMIT', "10 per minute"))(auth_bp) # Apply specific limit to auth routes

    from .products import products_bp
    app.register_blueprint(products_bp)

    from .orders import orders_bp
    app.register_blueprint(orders_bp)
    
    from .newsletter import newsletter_bp
    app.register_blueprint(newsletter_bp)
    limiter.limit(app.config.get('NEWSLETTER_RATE_LIMIT', "5 per minute"))(newsletter_bp)


    from .inventory import inventory_bp 
    app.register_blueprint(inventory_bp)

    from .admin_api import admin_api_bp 
    app.register_blueprint(admin_api_bp)
    # Admin API might have stricter global limits or specific endpoint limits
    limiter.limit(app.config.get('ADMIN_API_RATE_LIMIT', "100 per hour"))(admin_api_bp)
    
    # Corrected blueprint name from 'professionnal_bp' to 'professional_bp'
    from .professional import professional_bp # Assuming directory is renamed to 'professional'
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
        except Exception as e:
            pass 

    @app.route('/')
    @app.route('/api')
    def api_root():
        return jsonify({
            "message": "Welcome to the Maison Trüvra API!",
            "version": app.config.get("API_VERSION", "1.0.0"),
            "documentation_url": "/api/docs" 
        })

    @app.route('/assets/passports/<path:filename>')
    def serve_passport_public(filename):
        passport_dir = os.path.join(app.config['ASSET_STORAGE_PATH'], 'passports')
        app.logger.debug(f"Attempting to serve public passport: {filename} from {passport_dir}")
        if ".." in filename or filename.startswith("/"):
            from flask import abort
            return abort(404)
        return send_from_directory(passport_dir, filename, as_attachment=False)

    # Centralized error handlers
    @app.errorhandler(400)
    def bad_request_error(error):
        return jsonify(message=str(error.description if hasattr(error, 'description') else "Bad Request")), 400

    @app.errorhandler(401)
    def unauthorized_error(error):
        return jsonify(message=str(error.description if hasattr(error, 'description') else "Unauthorized")), 401
        
    @app.errorhandler(403)
    def forbidden_error(error):
        return jsonify(message=str(error.description if hasattr(error, 'description') else "Forbidden")), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify(message=str(error.description if hasattr(error, 'description') else "Resource not found")), 404

    @app.errorhandler(429) # Rate limit exceeded
    def ratelimit_handler(e):
        return jsonify(message=f"Rate limit exceeded: {e.description}"), 429

    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error(f"Internal Server Error: {error}", exc_info=True)
        return jsonify(message="An internal server error occurred."), 500

        return app