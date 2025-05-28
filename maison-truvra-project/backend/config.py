import os
from datetime import timedelta

class Config:
    """Base configuration."""
    # General Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your_default_secret_key_please_change_me') # Load from env, fallback to a default (for dev only)
    DEBUG = False
    TESTING = False
    
    # Database configuration
    # Assuming DATABASE_PATH will be set in instance or environment-specific config
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'maison_truvra.sqlite3'))
    
    # JWT Extended Settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your_default_jwt_secret_key_please_change_me') # Load from env
    JWT_TOKEN_LOCATION = ['headers', 'cookies'] # Allow JWT in headers and cookies
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_COOKIE_SECURE = False # Should be True in production over HTTPS
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_REFRESH_COOKIE_PATH = '/auth/refresh' # Path for refresh cookie

    # File Uploads / Asset Storage
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'uploads'))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # QR Code, Passport, Label Generation
    ASSET_STORAGE_PATH = os.environ.get('ASSET_STORAGE_PATH', os.path.join(UPLOAD_FOLDER, 'generated_assets'))
    QR_CODE_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'qr_codes')
    PASSPORT_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'passports')
    LABEL_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'labels')
    DEFAULT_FONT_PATH = os.environ.get('DEFAULT_FONT_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'fonts', 'DejaVuSans.ttf')) # Example path
    MAISON_TRUVRA_LOGO_PATH_LABEL = os.environ.get('MAISON_TRUVRA_LOGO_PATH_LABEL', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'logos', 'maison_truvra_label_logo.png')) # Example path
    MAISON_TRUVRA_LOGO_PATH_PASSPORT = os.environ.get('MAISON_TRUVRA_LOGO_PATH_PASSPORT', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'logos', 'maison_truvra_passport_logo.png')) # Example path


    # Email Configuration (using Flask-Mail or similar)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.mailtrap.io') # Example: mailtrap for dev
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 2525)) # Example: mailtrap port
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 't')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'your_mail_username') # Set in environment
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') # CRITICAL: Set in environment, not here
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@maisontruvra.com')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@maisontruvra.com') # For notifications

    # Stripe Configuration (Payment Processing)
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY') # CRITICAL: Set in environment
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY') # Set in environment
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET') # For verifying webhook events

    # Logging
    LOG_LEVEL = 'INFO'

    # CORS settings if frontend and backend are on different origins
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', "http://localhost:8000,http://127.0.0.1:8000") # Comma-separated list

    # Professional Application Documents
    PROFESSIONAL_DOCS_UPLOAD_PATH = os.path.join(UPLOAD_FOLDER, 'professional_documents')

    # Invoice Generation
    INVOICE_PDF_PATH = os.path.join(ASSET_STORAGE_PATH, 'invoices')
    DEFAULT_COMPANY_INFO = {
        "name": os.environ.get('INVOICE_COMPANY_NAME', "Maison Trüvra SARL"),
        "address_line1": os.environ.get('INVOICE_COMPANY_ADDRESS1', "1 Rue de la Truffe"),
        "address_line2": os.environ.get('INVOICE_COMPANY_ADDRESS2', ""),
        "city_postal_country": os.environ.get('INVOICE_COMPANY_CITY_POSTAL_COUNTRY', "75001 Paris, France"),
        "vat_number": os.environ.get('INVOICE_COMPANY_VAT', "FRXX123456789"),
        "logo_path": os.environ.get('INVOICE_COMPANY_LOGO_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'logos', 'maison_truvra_invoice_logo.png'))
    }
    
    # API Version
    API_VERSION = "v1"


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    # In development, you might want less secure cookies if not using HTTPS locally
    JWT_COOKIE_SECURE = False
    # Example for local SQLite development
    DATABASE_PATH = os.environ.get('DEV_DATABASE_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'dev_maison_truvra.sqlite3'))
    # Use a local mail server like MailHog or Mailtrap for development
    MAIL_SERVER = os.environ.get('DEV_MAIL_SERVER', 'localhost') # e.g. MailHog
    MAIL_PORT = int(os.environ.get('DEV_MAIL_PORT', 1025))      # e.g. MailHog SMTP port
    MAIL_USE_TLS = os.environ.get('DEV_MAIL_USE_TLS', 'false').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.environ.get('DEV_MAIL_USERNAME') # Often not needed for local test servers
    MAIL_PASSWORD = os.environ.get('DEV_MAIL_PASSWORD') # Often not needed for local test servers


class TestingConfig(Config):
    TESTING = True
    DEBUG = True # Often helpful to have debug true for tests
    # Use an in-memory SQLite database for tests or a dedicated test DB file
    DATABASE_PATH = os.environ.get('TEST_DATABASE_PATH', 'sqlite:///:memory:') # In-memory for tests
    # Ensure JWT cookies are not secure for testing over HTTP
    JWT_COOKIE_SECURE = False
    # Shorter token expiry for testing might be useful
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(minutes=10)
    # Disable CSRF protection for testing forms if applicable and handled by test client
    # WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True # Do not send emails during tests


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    JWT_COOKIE_SECURE = True # Cookies should be secure in production (HTTPS)
    JWT_COOKIE_SAMESITE = 'Strict' # More secure for production if possible

    # Ensure critical secrets are not using defaults in production
    def __init__(self):
        super().__init__()
        if self.SECRET_KEY == 'your_default_secret_key_please_change_me':
            raise ValueError("Production SECRET_KEY is not set or is using the default value. Please set it via environment variable.")
        if self.JWT_SECRET_KEY == 'your_default_jwt_secret_key_please_change_me':
            raise ValueError("Production JWT_SECRET_KEY is not set or is using the default value. Please set it via environment variable.")
        if not self.STRIPE_SECRET_KEY or not self.STRIPE_PUBLISHABLE_KEY:
            # Allow to run without Stripe for now, but log a warning.
            # In a real scenario, you might want to raise an error if Stripe is essential.
            print("WARNING: Stripe keys are not configured for production. Payment processing will not work.")
        if not os.environ.get('MAIL_PASSWORD'): # Check if MAIL_PASSWORD is set in env
            print("WARNING: MAIL_PASSWORD is not set in the environment. Email functionality may be impaired.")

# Dictionary to map environment names to config classes
config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig,
    production=ProductionConfig,
    default=DevelopmentConfig
)

def get_config_by_name(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    
    config_instance = config_by_name.get(config_name)()
    
    # Ensure essential paths are created if they don't exist
    paths_to_create = [
        os.path.dirname(config_instance.DATABASE_PATH), # instance folder for DB
        config_instance.UPLOAD_FOLDER,
        config_instance.ASSET_STORAGE_PATH,
        config_instance.QR_CODE_FOLDER,
        config_instance.PASSPORT_FOLDER,
        config_instance.LABEL_FOLDER,
        config_instance.PROFESSIONAL_DOCS_UPLOAD_PATH,
        config_instance.INVOICE_PDF_PATH
    ]
    for path in paths_to_create:
        if path: # Ensure path is not None or empty
            os.makedirs(path, exist_ok=True)
            
    return config_instance
