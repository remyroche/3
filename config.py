# backend/config.py
import os
from datetime import timedelta
from dotenv import load_dotenv # Added for .env support

# Determine the base directory of this config file (backend/)
# and the project root (one level up from backend/)
CONFIG_FILE_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(CONFIG_FILE_DIR)

# Load .env file from the PROJECT_ROOT if it exists
dotenv_path = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded .env file from {dotenv_path}")
else:
    print(f".env file not found at {dotenv_path}, using environment variables or defaults.")


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change_this_default_secret_key_in_prod_sqlalchemy_totp')
    DEBUG = False
    TESTING = False
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:8000')

    # SQLALCHEMY_DATABASE_URI adjusted to use PROJECT_ROOT for clarity
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(PROJECT_ROOT, 'instance', 'maison_truvra_orm.sqlite3')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False # Default to False, can be overridden in DevelopmentConfig

    # --- Backup Configuration ---
    BACKUP_ENCRYPTION_KEY = os.environ.get('BACKUP_ENCRYPTION_KEY') # No default for better security
    BACKUP_EMAIL_RECIPIENT = os.environ.get('BACKUP_EMAIL_RECIPIENT')
    # Backup directory will be PROJECT_ROOT/backend/backup/
    BACKUP_DIRECTORY = os.path.join(CONFIG_FILE_DIR, 'backup')

    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'change_this_default_jwt_secret_key_in_prod_sqlalchemy_totp')
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

    # UPLOAD_FOLDER adjusted to use PROJECT_ROOT
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(PROJECT_ROOT, 'instance', 'uploads'))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024 # 8MB
    ASSET_STORAGE_PATH = os.environ.get('ASSET_STORAGE_PATH', os.path.join(UPLOAD_FOLDER, 'generated_assets'))
    QR_CODE_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'qr_codes')
    PASSPORT_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'passports')
    LABEL_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'labels')
    # Static assets paths adjusted to use PROJECT_ROOT
    DEFAULT_FONT_PATH = os.environ.get('DEFAULT_FONT_PATH', os.path.join(PROJECT_ROOT, 'static_assets', 'fonts', 'DejaVuSans.ttf')) 
    MAISON_TRUVRA_LOGO_PATH_LABEL = os.environ.get('MAISON_TRUVRA_LOGO_PATH_LABEL', os.path.join(PROJECT_ROOT, 'static_assets', 'logos', 'maison_truvra_label_logo.png')) 
    MAISON_TRUVRA_LOGO_PATH_PASSPORT = os.environ.get('MAISON_TRUVRA_LOGO_PATH_PASSPORT', os.path.join(PROJECT_ROOT, 'static_assets', 'logos', 'maison_truvra_passport_logo.png'))

    # --- Email Configuration (for sending backups and other app emails) ---
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 't')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') # For general admin notifications

    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_FILE = os.environ.get('LOG_FILE', None) # e.g., os.path.join(PROJECT_ROOT, 'logs', 'app.log')

    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', "http://localhost:8000,http://127.0.0.1:8000")
    
    PROFESSIONAL_DOCS_UPLOAD_PATH = os.path.join(UPLOAD_FOLDER, 'professional_documents')
    INVOICE_PDF_PATH = os.path.join(ASSET_STORAGE_PATH, 'invoices')
    DEFAULT_COMPANY_INFO = {
        "name": os.environ.get('INVOICE_COMPANY_NAME', "Maison Trüvra SARL"),
        "address_line1": os.environ.get('INVOICE_COMPANY_ADDRESS1', "1 Rue de la Truffe"),
        "address_line2": os.environ.get('INVOICE_COMPANY_ADDRESS2', ""),
        "city_postal_country": os.environ.get('INVOICE_COMPANY_CITY_POSTAL_COUNTRY', "75001 Paris, France"),
        "vat_number": os.environ.get('INVOICE_COMPANY_VAT', "FRXX123456789"),
        "logo_path": os.environ.get('INVOICE_COMPANY_LOGO_PATH', os.path.join(PROJECT_ROOT, 'static_assets', 'logos', 'maison_truvra_invoice_logo.png'))
    }
    
    API_VERSION = "v1.5-sqlalchemy-totp-enrollment" # Or your current version
    # APP_BASE_URL already defined above
    BACKEND_APP_BASE_URL = os.environ.get('BACKEND_APP_BASE_URL', 'http://localhost:5001') # For backend specific URLs like callbacks

    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', "memory://")
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_HEADERS_ENABLED = True
    DEFAULT_RATELIMITS = ["200 per day", "50 per hour"] 
    AUTH_RATELIMITS = ["20 per minute", "200 per hour"] 
    ADMIN_LOGIN_RATELIMITS = ["10 per 5 minutes", "60 per hour"] 
    PASSWORD_RESET_RATELIMITS = ["5 per 15 minutes"]
    NEWSLETTER_RATELIMITS = ["10 per minute"] 
    ADMIN_API_RATELIMITS = ["200 per hour"] 
    ADMIN_TOTP_SETUP_RATELIMITS = ["5 per 10 minutes"]

    CONTENT_SECURITY_POLICY = {
        'default-src': ['\'self\''],
        'img-src': ['\'self\'', 'https://placehold.co', 'data:'], 
        'script-src': [
            '\'self\'', 
            'https://cdn.tailwindcss.com', 
            'https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js'
        ],
        'style-src': ['\'self\'', 'https://cdnjs.cloudflare.com', 'https://fonts.googleapis.com', '\'unsafe-inline\''],
        'font-src': ['\'self\'', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
        'connect-src': ['\'self\'', 'https://app.simplelogin.io'], 
        'form-action': ['\'self\'', 'https://app.simplelogin.io'], 
        'frame-ancestors': ['\'none\'']
    }

    TALISMAN_FORCE_HTTPS = False # Usually True in ProductionConfig

    INITIAL_ADMIN_EMAIL = os.environ.get('INITIAL_ADMIN_EMAIL')
    INITIAL_ADMIN_PASSWORD = os.environ.get('INITIAL_ADMIN_PASSWORD')

    VERIFICATION_TOKEN_LIFESPAN_HOURS = 24
    RESET_TOKEN_LIFESPAN_HOURS = 1
    MAGIC_LINK_LIFESPAN_MINUTES = 10

    INVOICE_DUE_DAYS = 30

    TOTP_ISSUER_NAME = os.environ.get('TOTP_ISSUER_NAME', "Maison Trüvra Admin")
    TOTP_LOGIN_STATE_TIMEOUT = timedelta(minutes=5) 
    TOTP_SETUP_SECRET_TIMEOUT = timedelta(minutes=10)

    SIMPLELOGIN_CLIENT_ID = os.environ.get('SIMPLELOGIN_CLIENT_ID', 'truvra-ykisfvoctm') 
    SIMPLELOGIN_CLIENT_SECRET = os.environ.get('SIMPLELOGIN_CLIENT_SECRET', 'cppjuelfvjkkqursqunvwigxiyabakgfthhivwzi') 
    SIMPLELOGIN_AUTHORIZE_URL = os.environ.get('SIMPLELOGIN_AUTHORIZE_URL', 'https://app.simplelogin.io/oauth2/authorize')
    SIMPLELOGIN_TOKEN_URL = os.environ.get('SIMPLELOGIN_TOKEN_URL', 'https://app.simplelogin.io/oauth2/token')
    SIMPLELOGIN_USERINFO_URL = os.environ.get('SIMPLELOGIN_USERINFO_URL', 'https://app.simplelogin.io/oauth2/userinfo')
    SIMPLELOGIN_REDIRECT_URI_ADMIN = os.environ.get(
        'SIMPLELOGIN_REDIRECT_URI_ADMIN',
        f"{BACKEND_APP_BASE_URL}/api/admin/login/simplelogin/callback"
    )
    SIMPLELOGIN_SCOPES = "openid email profile" 


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    SQLALCHEMY_ECHO = False # Set to True for verbose SQL query logging if needed
    JWT_COOKIE_SECURE = False # For local HTTP development
    # SQLALCHEMY_DATABASE_URI adjusted to use PROJECT_ROOT
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(PROJECT_ROOT, 'instance', 'dev_maison_truvra_orm.sqlite3')
    
    # Mailhog/local SMTP server for development
    MAIL_SERVER = os.environ.get('DEV_MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('DEV_MAIL_PORT', 1025))
    MAIL_USE_TLS = False
    MAIL_USE_SSL = False
    MAIL_USERNAME = None
    MAIL_PASSWORD = None
    
    TALISMAN_FORCE_HTTPS = False
    APP_BASE_URL = os.environ.get('DEV_APP_BASE_URL', 'http://localhost:8000') 
    
    # Update CSP for development if needed, e.g., for live reload servers
    # Making a copy to avoid modifying the class variable of Config
    CONTENT_SECURITY_POLICY = Config.CONTENT_SECURITY_POLICY.copy()
    CONTENT_SECURITY_POLICY['connect-src'] = Config.CONTENT_SECURITY_POLICY.get('connect-src', []) + \
                                             ['http://localhost:5001', 'http://127.0.0.1:5001'] # Example for backend API

    SIMPLELOGIN_REDIRECT_URI_ADMIN = os.environ.get(
        'DEV_SIMPLELOGIN_REDIRECT_URI_ADMIN',
        f"{Config.BACKEND_APP_BASE_URL}/api/admin/login/simplelogin/callback" # Uses Config.BACKEND_APP_BASE_URL
    )

class TestingConfig(Config):
    TESTING = True
    DEBUG = True # Often helpful for tests
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'sqlite:///:memory:')
    JWT_COOKIE_SECURE = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5) # Shorter tokens for testing
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(minutes=10)
    # MAIL_SUPPRESS_SEND = True # If using Flask-Mail, or handle in tests
    TALISMAN_FORCE_HTTPS = False
    WTF_CSRF_ENABLED = False # Disable CSRF for easier form testing if using Flask-WTF
    RATELIMIT_ENABLED = False # Disable rate limits for testing
    INITIAL_ADMIN_EMAIL = 'test_admin_orm@example.com'
    INITIAL_ADMIN_PASSWORD = 'test_password_orm123'
    SQLALCHEMY_ECHO = False
    SIMPLELOGIN_CLIENT_ID = 'test_sl_client_id_testing' 
    SIMPLELOGIN_CLIENT_SECRET = 'test_sl_client_secret_testing'
    BACKUP_ENCRYPTION_KEY = Fernet.generate_key().decode() # Use a fresh key for tests

    # Ensure a test recipient for backup emails if testing that feature
    BACKUP_EMAIL_RECIPIENT = 'test-backup-recipient@example.com'


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    
    if Config.SECRET_KEY == 'change_this_default_secret_key_in_prod_sqlalchemy_totp':
        raise ValueError("Production SECRET_KEY is not set or is using the default value.")
    if Config.JWT_SECRET_KEY == 'change_this_default_jwt_secret_key_in_prod_sqlalchemy_totp':
        raise ValueError("Production JWT_SECRET_KEY is not set or is using the default value.")
    if not Config.BACKUP_ENCRYPTION_KEY or Config.BACKUP_ENCRYPTION_KEY == 'YOUR_STRONG_FERNET_ENCRYPTION_KEY_HERE':
        raise ValueError("Production BACKUP_ENCRYPTION_KEY is not set or is a placeholder.")
    if not Config.BACKUP_EMAIL_RECIPIENT:
        raise ValueError("Production BACKUP_EMAIL_RECIPIENT is not set.")


    JWT_COOKIE_SECURE = True # Enforce HTTPS for cookies
    JWT_COOKIE_SAMESITE = 'Strict' # Stricter SameSite for production
    TALISMAN_FORCE_HTTPS = True 
    
    APP_BASE_URL = os.environ.get('PROD_APP_BASE_URL')
    if not APP_BASE_URL:
        raise ValueError("PROD_APP_BASE_URL environment variable must be set for production.")

    PROD_CORS_ORIGINS = os.environ.get('PROD_CORS_ORIGINS')
    if not PROD_CORS_ORIGINS:
        raise ValueError("PROD_CORS_ORIGINS environment variable must be set for production.")
    CORS_ORIGINS = PROD_CORS_ORIGINS

    # Database: Prefer environment variables for production credentials
    MYSQL_USER_PROD = os.environ.get('MYSQL_USER_PROD')
    MYSQL_PASSWORD_PROD = os.environ.get('MYSQL_PASSWORD_PROD')
    MYSQL_HOST_PROD = os.environ.get('MYSQL_HOST_PROD')
    MYSQL_DB_PROD = os.environ.get('MYSQL_DB_PROD')
    if all([MYSQL_USER_PROD, MYSQL_PASSWORD_PROD, MYSQL_HOST_PROD, MYSQL_DB_PROD]):
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{MYSQL_USER_PROD}:{MYSQL_PASSWORD_PROD}@{MYSQL_HOST_PROD}/{MYSQL_DB_PROD}"
    elif 'sqlite:///' not in Config.SQLALCHEMY_DATABASE_URI: # If not already using SQLite from base Config
        # This condition means if DATABASE_URL was set to something other than SQLite,
        # and MySQL specific vars are not all set, it's an issue.
        raise ValueError("Production MySQL connection details (MYSQL_USER_PROD, etc.) must be set, or a full DATABASE_URL provided.")

    SIMPLELOGIN_REDIRECT_URI_ADMIN = os.environ.get('PROD_SIMPLELOGIN_REDIRECT_URI_ADMIN')
    if not SIMPLELOGIN_REDIRECT_URI_ADMIN:
         # Fallback or raise error depending on requirements
        print("WARNING: PROD_SIMPLELOGIN_REDIRECT_URI_ADMIN is not set. Using default from Config.")
        SIMPLELOGIN_REDIRECT_URI_ADMIN = Config.SIMPLELOGIN_REDIRECT_URI_ADMIN # Or raise error
        # raise ValueError("PROD_SIMPLELOGIN_REDIRECT_URI_ADMIN must be set for production.")
        
    RATELIMIT_STORAGE_URI = os.environ.get('PROD_RATELIMIT_STORAGE_URI')
    if not RATELIMIT_STORAGE_URI or RATELIMIT_STORAGE_URI == "memory://":
        print("WARNING: RATELIMIT_STORAGE_URI is not set or is 'memory://' for production. Consider Redis for scalability.")

    if not Config.MAIL_SERVER or not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
        print("WARNING: Production email server (MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD) is not fully configured.")
    if not Config.STRIPE_SECRET_KEY or not Config.STRIPE_PUBLISHABLE_KEY:
        print("WARNING: Stripe keys (STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY) are not configured for production.")
    
    # Ensure CSP is appropriate for production
    # Making a copy to avoid modifying the class variable of Config
    CONTENT_SECURITY_POLICY = Config.CONTENT_SECURITY_POLICY.copy()
    CONTENT_SECURITY_POLICY['connect-src'] = ['\'self\'', APP_BASE_URL, 'https://app.simplelogin.io']
    CONTENT_SECURITY_POLICY['form-action'] = ['\'self\'', 'https://app.simplelogin.io']
    # Consider removing 'unsafe-inline' from style-src if possible

    if not Config.INITIAL_ADMIN_EMAIL or not Config.INITIAL_ADMIN_PASSWORD:
        print("WARNING: INITIAL_ADMIN_EMAIL or INITIAL_ADMIN_PASSWORD environment variables are not set for first-time setup.")
    
    # Check default SimpleLogin credentials
    if Config.SIMPLELOGIN_CLIENT_ID == 'truvra-ykisfvoctm' or \
       Config.SIMPLELOGIN_CLIENT_SECRET == 'cppjuelfvjkkqursqunvwigxiyabakgfthhivwzi':
        if not (os.environ.get('SIMPLELOGIN_CLIENT_ID') and os.environ.get('SIMPLELOGIN_CLIENT_SECRET')):
            print("WARNING: SimpleLogin OAuth credentials are using fallback values in production. Set environment variables for SIMPLELOGIN_CLIENT_ID and SIMPLELOGIN_CLIENT_SECRET.")


config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig,
    production=ProductionConfig,
    default=DevelopmentConfig 
)

# Added Fernet import for TestingConfig, ensure cryptography is installed
try:
    from cryptography.fernet import Fernet
except ImportError:
    print("WARNING: cryptography library not found. Fernet for TestingConfig.BACKUP_ENCRYPTION_KEY will not work.")
    class Fernet: # Dummy class if cryptography is not installed
        @staticmethod
        def generate_key(): return b'dummy_testing_key_cryptography_missing_=='


def get_config_by_name(config_name_str=None):
    """
    Retrieves a configuration instance by name.
    Creates necessary directories defined in the config.
    """
    if config_name_str is None:
        config_name_str = os.getenv('FLASK_ENV', 'default')
    
    # Force production config if FLASK_ENV is 'production' but a different one was requested
    # This is a safeguard.
    if os.getenv('FLASK_ENV') == 'production' and config_name_str != 'production':
        print(f"Warning: FLASK_ENV is 'production' but config_name is '{config_name_str}'. Forcing ProductionConfig.")
        config_name_str = 'production'
        
    SelectedConfigClass = config_by_name.get(config_name_str.lower())
    if not SelectedConfigClass:
        print(f"Warning: Config name '{config_name_str}' not found. Using default.")
        SelectedConfigClass = config_by_name['default']
        
    config_instance = SelectedConfigClass() # Instantiate the class
    
    # --- Create directories defined in the config instance ---
    # This ensures that paths used by the application exist.
    paths_to_create = [
        # For SQLite, get the directory part of the URI
        os.path.dirname(config_instance.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')) 
            if 'sqlite:///' in config_instance.SQLALCHEMY_DATABASE_URI and not config_instance.SQLALCHEMY_DATABASE_URI.endswith(':memory:') 
            else None,
        config_instance.UPLOAD_FOLDER,
        config_instance.ASSET_STORAGE_PATH, 
        config_instance.QR_CODE_FOLDER,
        config_instance.PASSPORT_FOLDER, 
        config_instance.LABEL_FOLDER,
        config_instance.PROFESSIONAL_DOCS_UPLOAD_PATH, 
        config_instance.INVOICE_PDF_PATH,
        config_instance.BACKUP_DIRECTORY, # Added backup directory
        os.path.dirname(config_instance.LOG_FILE) if config_instance.LOG_FILE else None # Directory for log file
    ]
    
    for path in paths_to_create:
        if path: # Ensure path is not None
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                # Log this error appropriately in a real application
                print(f"Warning: Could not create directory {path}: {e}") 
                
    # Validate essential backup configurations for production
    if isinstance(config_instance, ProductionConfig):
        if not config_instance.BACKUP_ENCRYPTION_KEY:
            raise ValueError("CRITICAL: Production BACKUP_ENCRYPTION_KEY is not set. Aborting.")
        if not config_instance.BACKUP_EMAIL_RECIPIENT:
            print("WARNING: Production BACKUP_EMAIL_RECIPIENT is not set. Backups cannot be emailed.")


    return config_instance

# Example of how to get the current configuration instance:
# current_config = get_config_by_name()
