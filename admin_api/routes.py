# backend/admin_api/routes.py
import os
import uuid
import requests 
from urllib.parse import urlencode 
import secrets # Make sure secrets is imported

from werkzeug.utils import secure_filename
from flask import request, jsonify, current_app, url_for, redirect, session, abort as flask_abort 
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt, set_access_cookies # Added set_access_cookies
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
import pyotp # Added for TOTP setup routes

from . import admin_api_bp # Assuming limiter is initialized elsewhere and applied to blueprint or app


# Helper function (can be part of this file or a utils file if used elsewhere)
def _create_admin_session_and_get_response(admin_user, redirect_url):
    """Helper to create JWT, set cookies, and prepare a redirect response."""
    identity = admin_user.id
    additional_claims = {
        "role": admin_user.role, "email": admin_user.email, "is_admin": True,
        "first_name": admin_user.first_name, "last_name": admin_user.last_name
    }
    access_token = create_access_token(identity=identity, additional_claims=additional_claims)
    
    response = redirect(redirect_url)
    # Explicitly set the access token in cookies if JWT_TOKEN_LOCATION includes 'cookies'
    # and if Flask-JWT-Extended doesn't automatically do it on redirect responses.
    if 'cookies' in current_app.config.get('JWT_TOKEN_LOCATION', ['headers']):
        set_access_cookies(response, access_token)
        current_app.logger.info(f"Access cookie set for admin {admin_user.email} during SSO redirect.")
    
    current_app.logger.info(f"SSO successful for {admin_user.email}, redirecting. Token (prefix): {access_token[:20]}...")
    return response

# ... (other routes like admin_login_step1_password, admin_login_step2_verify_totp, simplelogin_initiate remain the same) ...
# Make sure the _create_admin_session helper from the previous turn is also included or adapted if it was separate.
# For this update, I'm focusing only on simplelogin_callback.

@admin_api_bp.route('/login/simplelogin/callback', methods=['GET'])
def simplelogin_callback():
    auth_code = request.args.get('code')
    state_returned = request.args.get('state')
    audit_logger = current_app.audit_log_service
    # Define the base admin login URL for redirects
    base_admin_login_url = url_for('admin_api_bp.admin_login_step1_password', _external=True).replace('/login', '/admin_login.html')
    # A more robust way if your admin login page is static:
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
                session['pending_totp_admin_id'] = admin_user.id
                session['pending_totp_admin_email'] = admin_user.email 
                session.permanent = True 
                current_app.permanent_session_lifetime = current_app.config.get('TOTP_LOGIN_STATE_TIMEOUT', timedelta(minutes=5))

                audit_logger.log_action(user_id=admin_user.id, action='admin_login_totp_required', target_type='user_admin', target_id=admin_user.id, status='pending', ip_address=request.remote_addr)
                return jsonify(message="Password verified. Please enter your TOTP code.", success=True, totp_required=True, email=admin_user.email), 200 
            else:
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
            audit_logger.log_action(user_id=admin_user.id, action='admin_totp_verify_fail_invalid_code', email=pending_admin_email, details="Invalid TOTP code.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid TOTP code.", success=False), 401
            
    except Exception as e:
        current_app.logger.error(f"Error during admin TOTP verification for {pending_admin_email}: {e}", exc_info=True)
        audit_logger.log_action(user_id=pending_admin_id, action='admin_totp_verify_fail_server_error', email=pending_admin_email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="TOTP verification failed due to a server error.", success=False), 500

@admin_api_bp.route('/login/simplelogin/initiate', methods=['GET'])
def simplelogin_initiate():
    client_id = current_app.config.get('SIMPLELOGIN_CLIENT_ID')
    redirect_uri = current_app.config.get('SIMPLELOGIN_REDIRECT_URI_ADMIN')
    authorize_url = current_app.config.get('SIMPLELOGIN_AUTHORIZE_URL')
    scopes = current_app.config.get('SIMPLELOGIN_SCOPES')

    if not all([client_id, redirect_uri, authorize_url, scopes]):
        current_app.logger.error("SimpleLogin OAuth settings are not fully configured in the backend.")
        return jsonify(message="SimpleLogin SSO is not configured correctly on the server.", success=False), 500

    session['oauth_state_sl'] = secrets.token_urlsafe(16) # Store state for CSRF protection

    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': scopes,
        'state': session['oauth_state_sl'] 
    }
    auth_redirect_url = f"{authorize_url}?{urlencode(params)}"
    current_app.logger.info(f"Redirecting admin to SimpleLogin for authentication: {auth_redirect_url}")
    return redirect(auth_redirect_url)


@admin_api_bp.route('/login/simplelogin/callback', methods=['GET'])
def simplelogin_callback():
    auth_code = request.args.get('code')
    state_returned = request.args.get('state')
    audit_logger = current_app.audit_log_service

    # Verify state parameter for CSRF protection
    expected_state = session.pop('oauth_state_sl', None)
    if not expected_state or expected_state != state_returned:
        audit_logger.log_action(action='simplelogin_callback_fail_state_mismatch', details="OAuth state mismatch.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="SimpleLogin authentication failed (state mismatch).", success=False), 400


    if not auth_code:
        audit_logger.log_action(action='simplelogin_callback_fail_no_code', details="No authorization code received from SimpleLogin.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="SimpleLogin authentication failed (no code).", success=False), 400

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
            return jsonify(message="Failed to get access token from SimpleLogin.", success=False), 500

        userinfo_url = current_app.config['SIMPLELOGIN_USERINFO_URL']
        headers = {'Authorization': f'Bearer {sl_access_token}'}
        userinfo_response = requests.get(userinfo_url, headers=headers)
        userinfo_response.raise_for_status()
        sl_user_info = userinfo_response.json()
        
        sl_email = sl_user_info.get('email')
        sl_simplelogin_user_id = sl_user_info.get('sub') # SimpleLogin's unique user ID

        if not sl_email:
            audit_logger.log_action(action='simplelogin_callback_fail_no_email', details="No email in userinfo from SimpleLogin.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Could not retrieve email from SimpleLogin.", success=False), 500

        admin_user = User.query.filter_by(email=sl_email, role='admin').first()

        if admin_user and admin_user.is_active:
            # Optionally link SimpleLogin ID if not already linked
            if not admin_user.simplelogin_user_id and sl_simplelogin_user_id:
                admin_user.simplelogin_user_id = sl_simplelogin_user_id
                db.session.commit()
            
            audit_logger.log_action(user_id=admin_user.id, action='admin_login_success_simplelogin', target_type='user_admin', target_id=admin_user.id, details=f"Admin {sl_email} logged in via SimpleLogin.", status='success', ip_address=request.remote_addr)
            
            # Create JWT and set cookies
            identity = admin_user.id
            additional_claims = {
                "role": admin_user.role, "email": admin_user.email, "is_admin": True,
                "first_name": admin_user.first_name, "last_name": admin_user.last_name
            }
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            
            # Redirect to admin dashboard. Flask-JWT-Extended will handle setting cookies if configured.
            admin_dashboard_url = current_app.config.get('APP_BASE_URL', 'http://localhost:8000') + '/admin/admin_dashboard.html'
            
            response = redirect(admin_dashboard_url)
            # If JWT_TOKEN_LOCATION includes 'cookies', Flask-JWT-Extended should set them on this response.
            # To be explicit, you might use set_access_cookies from flask_jwt_extended if needed,
            # but usually it's automatic on responses from decorated endpoints or by returning the token in JSON.
            # Since we are redirecting, the cookie setting relies on the global response handling of Flask-JWT-Extended.
            # If it doesn't work, you might need to redirect to a frontend page that makes one more call to get the token.
            current_app.logger.info(f"SimpleLogin successful for {sl_email}, redirecting to dashboard. Token: {access_token[:20]}...") # Log part of token
            return response

        else:
            audit_logger.log_action(action='simplelogin_callback_fail_user_not_admin_or_inactive', email=sl_email, details="User found but not an active admin.", status='failure', ip_address=request.remote_addr)
            login_page_url = current_app.config.get('APP_BASE_URL', 'http://localhost:8000') + '/admin/admin_login.html?error=sso_admin_not_found'
            return redirect(login_page_url)

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"SimpleLogin OAuth request failed: {e}", exc_info=True)
        audit_logger.log_action(action='simplelogin_callback_fail_request_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        login_page_url = current_app.config.get('APP_BASE_URL', 'http://localhost:8000') + '/admin/admin_login.html?error=sso_communication_error'
        return redirect(login_page_url)
    except Exception as e:
        current_app.logger.error(f"Error during SimpleLogin callback: {e}", exc_info=True)
        audit_logger.log_action(action='simplelogin_callback_fail_server_error', details=str(e), status='failure', ip_address=request.remote_addr)
        login_page_url = current_app.config.get('APP_BASE_URL', 'http://localhost:8000') + '/admin/admin_login.html?error=sso_server_error'
        return redirect(login_page_url)


# --- TOTP Setup Routes ---
@admin_api_bp.route('/totp/setup-initiate', methods=['POST'])
@admin_required
@limiter.limit(lambda: current_app.config.get('ADMIN_TOTP_SETUP_RATELIMITS', "5 per 10 minutes"))
def totp_setup_initiate():
    current_admin_id = get_jwt_identity()
    data = request.json
    password = data.get('password')
    audit_logger = current_app.audit_log_service

    admin_user = User.query.get(current_admin_id)
    if not admin_user or admin_user.role != 'admin':
        return jsonify(message="Admin user not found or invalid.", success=False), 403

    if not password or not admin_user.check_password(password):
        audit_logger.log_action(user_id=current_admin_id, action='totp_setup_initiate_fail_password', details="Incorrect password for TOTP setup.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Incorrect current password.", success=False), 401

    try:
        # Generate a new secret. If one exists but TOTP is not enabled, this will overwrite it,
        # which is generally desired for a fresh setup.
        new_secret = admin_user.generate_totp_secret()
        # Store the new secret temporarily in the session for verification step
        session['pending_totp_secret_for_setup'] = new_secret 
        session['pending_totp_user_id_for_setup'] = admin_user.id
        session.permanent = True
        current_app.permanent_session_lifetime = current_app.config.get('TOTP_SETUP_SECRET_TIMEOUT', timedelta(minutes=10))
        
        # Do NOT save the secret to DB yet, only after verification.
        # The user.generate_totp_secret() method just creates it in memory on the instance.
        
        provisioning_uri = admin_user.get_totp_uri() # This will use the newly generated in-memory secret
        if not provisioning_uri:
             raise Exception("Could not generate provisioning URI.")

        audit_logger.log_action(user_id=current_admin_id, action='totp_setup_initiate_success', details="TOTP secret generated, provisioning URI provided.", status='success', ip_address=request.remote_addr)
        return jsonify(
            message="TOTP setup initiated. Scan the QR code and verify.",
            totp_provisioning_uri=provisioning_uri,
            totp_manual_secret=new_secret, # Send secret for manual entry
            success=True
        ), 200
    except Exception as e:
        current_app.logger.error(f"Error initiating TOTP setup for admin {current_admin_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='totp_setup_initiate_fail_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to initiate TOTP setup: {str(e)}", success=False), 500


@admin_api_bp.route('/totp/setup-verify', methods=['POST'])
@admin_required
@limiter.limit(lambda: current_app.config.get('ADMIN_TOTP_SETUP_RATELIMITS', "5 per 10 minutes"))
def totp_setup_verify_and_enable():
    current_admin_id = get_jwt_identity()
    data = request.json
    totp_code = data.get('totp_code')
    audit_logger = current_app.audit_log_service

    pending_secret = session.get('pending_totp_secret_for_setup')
    pending_user_id = session.get('pending_totp_user_id_for_setup')

    if not pending_secret or not pending_user_id or pending_user_id != current_admin_id:
        audit_logger.log_action(user_id=current_admin_id, action='totp_setup_verify_fail_no_pending_state', details="No pending TOTP setup state found or user mismatch.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="TOTP setup session expired or invalid. Please start over.", success=False), 400
    
    if not totp_code:
        return jsonify(message="TOTP code is required for verification.", success=False), 400

    admin_user = User.query.get(current_admin_id)
    if not admin_user: # Should not happen if JWT is valid
        return jsonify(message="Admin user not found.", success=False), 404
    
    # Use the temporary secret from session for verification
    temp_totp_instance = pyotp.TOTP(pending_secret)
    if temp_totp_instance.verify(totp_code):
        try:
            admin_user.totp_secret = pending_secret # Now save the verified secret
            admin_user.is_totp_enabled = True
            admin_user.updated_at = datetime.now(timezone.utc)
            db.session.commit()

            session.pop('pending_totp_secret_for_setup', None)
            session.pop('pending_totp_user_id_for_setup', None)
            
            audit_logger.log_action(user_id=current_admin_id, action='totp_setup_verify_success', details="TOTP enabled successfully.", status='success', ip_address=request.remote_addr)
            return jsonify(message="Two-Factor Authentication (TOTP) enabled successfully!", success=True), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving TOTP setup for admin {current_admin_id}: {e}", exc_info=True)
            audit_logger.log_action(user_id=current_admin_id, action='totp_setup_verify_fail_db_error', details=str(e), status='failure', ip_address=request.remote_addr)
            return jsonify(message="Failed to save TOTP settings.", success=False), 500
    else:
        audit_logger.log_action(user_id=current_admin_id, action='totp_setup_verify_fail_invalid_code', details="Invalid TOTP code during setup.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid TOTP code. Please try again.", success=False), 400


@admin_api_bp.route('/totp/disable', methods=['POST'])
@admin_required
@limiter.limit(lambda: current_app.config.get('ADMIN_TOTP_SETUP_RATELIMITS', "5 per 10 minutes"))
def totp_disable():
    current_admin_id = get_jwt_identity()
    data = request.json
    password = data.get('password')
    totp_code = data.get('totp_code') # Current TOTP code to confirm disabling
    audit_logger = current_app.audit_log_service

    admin_user = User.query.get(current_admin_id)
    if not admin_user or admin_user.role != 'admin':
        return jsonify(message="Admin user not found or invalid.", success=False), 403

    if not admin_user.is_totp_enabled or not admin_user.totp_secret:
        return jsonify(message="TOTP is not currently enabled for your account.", success=False), 400

    if not password or not admin_user.check_password(password):
        audit_logger.log_action(user_id=current_admin_id, action='totp_disable_fail_password', details="Incorrect password for TOTP disable.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Incorrect current password.", success=False), 401
    
    if not totp_code or not admin_user.verify_totp(totp_code):
        audit_logger.log_action(user_id=current_admin_id, action='totp_disable_fail_invalid_code', details="Invalid TOTP code for disable.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid current TOTP code.", success=False), 401

    try:
        admin_user.is_totp_enabled = False
        admin_user.totp_secret = None # Clear the secret
        admin_user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='totp_disable_success', details="TOTP disabled successfully.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Two-Factor Authentication (TOTP) has been disabled.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error disabling TOTP for admin {current_admin_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='totp_disable_fail_exception', details=str(e), status='failure', ip_address=request.remote_addr)
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
