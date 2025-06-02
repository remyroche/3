import os
from datetime import timedelta

class Config:
    """Base configuration."""
    # CRITICAL: Set these via environment variables in production.
    # Generate strong, random keys.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change_this_default_secret_key_in_prod') 
    DEBUG = False
    TESTING = False
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:8000') 
    
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'maison_truvra.sqlite3'))
    
    # JWT Extended Settings
    # CRITICAL: Set this via environment variable in production.
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'change_this_default_jwt_secret_key_in_prod') 
    JWT_TOKEN_LOCATION = ['headers', 'cookies'] 
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_COOKIE_SECURE = False # Default to False, True in ProductionConfig
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_REFRESH_COOKIE_PATH = '/api/auth/refresh' 
    JWT_ACCESS_COOKIE_PATH = '/api/' 
    JWT_COOKIE_CSRF_PROTECT = True 
    JWT_CSRF_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE'] 
    JWT_CSRF_IN_COOKIES = True 

    # File Uploads / Asset Storage
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'uploads'))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'} # Review if PDF is needed for all upload types
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024 # Reduced to 8MB, adjust as needed

    ASSET_STORAGE_PATH = os.environ.get('ASSET_STORAGE_PATH', os.path.join(UPLOAD_FOLDER, 'generated_assets'))
    QR_CODE_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'qr_codes')
    PASSPORT_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'passports')
    LABEL_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'labels')
    
    DEFAULT_FONT_PATH = os.environ.get('DEFAULT_FONT_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'fonts', 'DejaVuSans.ttf')) 
    MAISON_TRUVRA_LOGO_PATH_LABEL = os.environ.get('MAISON_TRUVRA_LOGO_PATH_LABEL', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'logos', 'maison_truvra_label_logo.png')) 
    MAISON_TRUVRA_LOGO_PATH_PASSPORT = os.environ.get('MAISON_TRUVRA_LOGO_PATH_PASSPORT', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'logos', 'maison_truvra_passport_logo.png'))

    # Email Configuration (Ensure these are securely set in production environment variables)
    MAIL_SERVER = os.environ.get('MAIL_SERVER') 
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587)) 
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 't')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') 
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') 
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') # For initial admin setup and notifications

    # Stripe Configuration (Set via environment variables)
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY') 
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY') 
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET') 

    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_FILE = os.environ.get('LOG_FILE', None) # e.g., /var/log/maison_truvra/app.log

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
    
    API_VERSION = "v1.2" # Increment API version due to security changes

    # Rate Limiting
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', "memory://") 
    RATELIMIT_STRATEGY = "fixed-window" # or "moving-window"
    RATELIMIT_HEADERS_ENABLED = True
    DEFAULT_RATELIMITS = ["200 per day", "50 per hour"]
    AUTH_RATELIMITS = ["10 per minute", "100 per hour"] 
    ADMIN_LOGIN_RATELIMITS = ["5 per minute", "50 per hour"] 
    PASSWORD_RESET_RATELIMITS = ["5 per 15 minutes"] 

    # Content Security Policy (Review and tighten for production)
    # Removing 'unsafe-inline' from script-src is a good goal but may require frontend changes.
    # 'unsafe-inline' for style-src is common with utility CSS but should be reviewed.
    CONTENT_SECURITY_POLICY = {
        'default-src': ['\'self\''],
        'img-src': ['\'self\'', 'https://placehold.co', 'data:'], # Add other CDNs if used
        'script-src': [
            '\'self\'', 
            'https://cdn.tailwindcss.com' 
            # Consider adding 'nonce-...' or 'sha256-...' for inline scripts if 'unsafe-inline' must be avoided
        ],
        'style-src': [
            '\'self\'', 
            'https://cdnjs.cloudflare.com', 
            'https://fonts.googleapis.com', 
            '\'unsafe-inline\'' # Review if this can be removed
        ],
        'font-src': ['\'self\'', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
        'connect-src': ['\'self\''], # Restrict to your API domain in production
        'form-action': ['\'self\''], # Restrict form submissions to self
        'frame-ancestors': ['\'none\''] # Prevent clickjacking
    }
    TALISMAN_FORCE_HTTPS = False # Default to False, True in ProductionConfig

    # Initial Admin User (Set via environment variables for production)
    INITIAL_ADMIN_EMAIL = os.environ.get('INITIAL_ADMIN_EMAIL')
    INITIAL_ADMIN_PASSWORD = os.environ.get('INITIAL_ADMIN_PASSWORD')


    # Add MySQL Configuration
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'your_mysql_user')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'your_mysql_password')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'maison_truvra_mysql')
    MYSQL_CURSORCLASS = 'DictCursor' # To get results as dictionaries

    # If you were to use Flask-SQLAlchemy, it would be:
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
    #    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"
    # SQLALCHEMY_TRACK_MODIFICATIONS = False
    # ...

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    JWT_COOKIE_SECURE = False # HTTP for local dev
    # DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'maison_truvra.sqlite3'))
    # Use MailHog or similar for local email testing
    MAIL_SERVER = os.environ.get('DEV_MAIL_SERVER', 'localhost') 
    MAIL_PORT = int(os.environ.get('DEV_MAIL_PORT', 1025))      
    MAIL_USE_TLS = False
    MAIL_USERNAME = None
    MAIL_PASSWORD = None
    TALISMAN_FORCE_HTTPS = False
    APP_BASE_URL = os.environ.get('DEV_APP_BASE_URL', 'http://localhost:8000') # Frontend URL
    # For development, allow broader connect-src if frontend is on a different port
    Config.CONTENT_SECURITY_POLICY['connect-src'].extend(['http://localhost:5001', 'http://127.0.0.1:5001'])


class TestingConfig(Config):
    TESTING = True
    DEBUG = True 
    # DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'maison_truvra.sqlite3'))
    JWT_COOKIE_SECURE = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(minutes=10)
    MAIL_SUPPRESS_SEND = True # Don't send emails during tests
    TALISMAN_FORCE_HTTPS = False
    WTF_CSRF_ENABLED = False # If using Flask-WTF for forms, disable CSRF for tests
    RATELIMIT_ENABLED = False # Disable rate limiting for tests
    INITIAL_ADMIN_EMAIL = 'test_admin@example.com'
    INITIAL_ADMIN_PASSWORD = 'test_password123'


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    
    # CRITICAL: Ensure SECRET_KEY and JWT_SECRET_KEY are strong and unique, set via environment variables
    if Config.SECRET_KEY == 'change_this_default_secret_key_in_prod':
        raise ValueError("Production SECRET_KEY is not set or is using the default value. Set the SECRET_KEY environment variable.")
    if Config.JWT_SECRET_KEY == 'change_this_default_jwt_secret_key_in_prod':
        raise ValueError("Production JWT_SECRET_KEY is not set or is using the default value. Set the JWT_SECRET_KEY environment variable.")

    JWT_COOKIE_SECURE = True 
    JWT_COOKIE_SAMESITE = 'Strict' # More secure than Lax
    TALISMAN_FORCE_HTTPS = True 
    
    APP_BASE_URL = os.environ.get('PROD_APP_BASE_URL') # e.g., https://www.maisontruvra.com
    if not APP_BASE_URL:
        raise ValueError("PROD_APP_BASE_URL environment variable must be set for production.")

    # Configure CORS for your specific production frontend domain(s)
    PROD_CORS_ORIGINS = os.environ.get('PROD_CORS_ORIGINS')
    if not PROD_CORS_ORIGINS:
        raise ValueError("PROD_CORS_ORIGINS environment variable must be set for production (e.g., https://www.maisontruvra.com).")
    CORS_ORIGINS = PROD_CORS_ORIGINS

    # Use a persistent rate limiter backend like Redis in production
    RATELIMIT_STORAGE_URI = os.environ.get('PROD_RATELIMIT_STORAGE_URI') # e.g., "redis://localhost:6379/0"
    if not RATELIMIT_STORAGE_URI or RATELIMIT_STORAGE_URI == "memory://":
        print("WARNING: RATELIMIT_STORAGE_URI is not set or is 'memory://' for production. Consider using Redis for rate limiting.")

    # Ensure email and Stripe configurations are set via environment variables
    if not Config.MAIL_SERVER or not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
        print("WARNING: Production email server (MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD) is not fully configured. Email functionality will be impaired.")
    if not Config.STRIPE_SECRET_KEY or not Config.STRIPE_PUBLISHABLE_KEY:
        print("WARNING: Stripe keys (STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY) are not configured for production.")
    
    # Update CSP connect-src for production API domain
    Config.CONTENT_SECURITY_POLICY['connect-src'] = ['\'self\'', APP_BASE_URL]

    if not Config.INITIAL_ADMIN_EMAIL or not Config.INITIAL_ADMIN_PASSWORD:
        print("WARNING: INITIAL_ADMIN_EMAIL or INITIAL_ADMIN_PASSWORD environment variables are not set. Initial admin user creation might fail or use insecure defaults if any remain.")


config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig,
    production=ProductionConfig,
    default=DevelopmentConfig # Default to Development for safety if FLASK_ENV is not set
)

def get_config_by_name(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    
    # Ensure production config is explicitly chosen if FLASK_ENV is 'production'
    if os.getenv('FLASK_ENV') == 'production' and config_name != 'production':
        print(f"Warning: FLASK_ENV is 'production' but config_name is '{config_name}'. Forcing ProductionConfig.")
        config_name = 'production'
        
    config_instance = config_by_name.get(config_name)()
    
    # Create necessary directories
    paths_to_create = [
        os.path.dirname(config_instance.DATABASE_PATH), config_instance.UPLOAD_FOLDER,
        config_instance.ASSET_STORAGE_PATH, config_instance.QR_CODE_FOLDER,
        config_instance.PASSPORT_FOLDER, config_instance.LABEL_FOLDER,
        config_instance.PROFESSIONAL_DOCS_UPLOAD_PATH, config_instance.INVOICE_PDF_PATH
    ]
    for path in paths_to_create:
        if path: # Ensure path is not None
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                # Log this error, but allow app to continue if it's just a directory creation issue
                # that might be handled by deployment scripts.
                print(f"Warning: Could not create directory {path}: {e}")
    return config_instance

