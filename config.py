# backend/config.py
import os
from datetime import timedelta

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change_this_default_secret_key_in_prod_sqlalchemy')
    DEBUG = False
    TESTING = False
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:8000')

    # SQLAlchemy Configuration
    # Example for MySQL with PyMySQL driver:
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
    #    f"mysql+pymysql://{os.environ.get('MYSQL_USER', 'your_user')}:{os.environ.get('MYSQL_PASSWORD', 'your_pass')}@{os.environ.get('MYSQL_HOST', 'localhost')}/{os.environ.get('MYSQL_DB', 'maison_truvra_mysql_orm')}"

    # Example for SQLite (ensure instance folder exists or is created by app factory)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'maison_truvra_orm.sqlite3')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False # Set to True to see generated SQL in logs (useful for debugging)

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

    # File Uploads / Asset Storage (paths remain the same conceptually)
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
    
    API_VERSION = "v1.3-sqlalchemy" # Updated API version

    # Rate Limiting
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', "memory://")
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_HEADERS_ENABLED = True
    DEFAULT_RATELIMITS = ["200 per day", "50 per hour"] # Corrected key names in __init__.py
    AUTH_RATELIMITS = ["10 per minute", "100 per hour"]
    ADMIN_LOGIN_RATELIMITS = ["5 per minute", "50 per hour"]
    PASSWORD_RESET_RATELIMITS = ["5 per 15 minutes"]
    NEWSLETTER_RATELIMITS = ["10 per minute"] # Added for newsletter
    ADMIN_API_RATELIMITS = ["200 per hour"] # Added for general admin API

    # Content Security Policy
    CONTENT_SECURITY_POLICY = {
        'default-src': ['\'self\''],
        'img-src': ['\'self\'', 'https://placehold.co', 'data:'],
        'script-src': ['\'self\'', 'https://cdn.tailwindcss.com'],
        'style-src': ['\'self\'', 'https://cdnjs.cloudflare.com', 'https://fonts.googleapis.com', '\'unsafe-inline\''],
        'font-src': ['\'self\'', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
        'connect-src': ['\'self\''],
        'form-action': ['\'self\''],
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


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    SQLALCHEMY_ECHO = False # Can be True to see SQL queries
    JWT_COOKIE_SECURE = False
    # Use a different DB file for dev with ORM
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'dev_maison_truvra_orm.sqlite3')
    MAIL_SERVER = os.environ.get('DEV_MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('DEV_MAIL_PORT', 1025))
    MAIL_USE_TLS = False
    MAIL_USERNAME = None
    MAIL_PASSWORD = None
    TALISMAN_FORCE_HTTPS = False
    APP_BASE_URL = os.environ.get('DEV_APP_BASE_URL', 'http://localhost:8000')
    Config.CONTENT_SECURITY_POLICY['connect-src'].extend(['http://localhost:5001', 'http://127.0.0.1:5001']) # For backend API

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

    # For MySQL in production:
    MYSQL_USER_PROD = os.environ.get('MYSQL_USER_PROD')
    MYSQL_PASSWORD_PROD = os.environ.get('MYSQL_PASSWORD_PROD')
    MYSQL_HOST_PROD = os.environ.get('MYSQL_HOST_PROD')
    MYSQL_DB_PROD = os.environ.get('MYSQL_DB_PROD')
    if not all([MYSQL_USER_PROD, MYSQL_PASSWORD_PROD, MYSQL_HOST_PROD, MYSQL_DB_PROD]):
        print("WARNING: Production MySQL connection details are not fully set. Database will not connect.")
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'prod_fallback_orm.sqlite3') # Fallback, but should fail loudly
    else:
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_USER_PROD}:{MYSQL_PASSWORD_PROD}@{MYSQL_HOST_PROD}/{MYSQL_DB_PROD}"


    RATELIMIT_STORAGE_URI = os.environ.get('PROD_RATELIMIT_STORAGE_URI')
    if not RATELIMIT_STORAGE_URI or RATELIMIT_STORAGE_URI == "memory://":
        print("WARNING: RATELIMIT_STORAGE_URI is not set or is 'memory://' for production.")

    if not Config.MAIL_SERVER or not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
        print("WARNING: Production email server is not fully configured.")
    if not Config.STRIPE_SECRET_KEY or not Config.STRIPE_PUBLISHABLE_KEY:
        print("WARNING: Stripe keys are not configured for production.")
    
    Config.CONTENT_SECURITY_POLICY['connect-src'] = ['\'self\'', APP_BASE_URL]

    if not Config.INITIAL_ADMIN_EMAIL or not Config.INITIAL_ADMIN_PASSWORD:
        print("WARNING: INITIAL_ADMIN_EMAIL or INITIAL_ADMIN_PASSWORD environment variables are not set.")

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
        os.path.dirname(config_instance.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')) if 'sqlite:///' in config_instance.SQLALCHEMY_DATABASE_URI else None, # Only for SQLite
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
