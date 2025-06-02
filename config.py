import os
from datetime import timedelta

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your_default_secret_key_please_change_me') 
    DEBUG = False
    TESTING = False
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:8000') 
    
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'maison_truvra.sqlite3'))
    
    # JWT Extended Settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your_default_jwt_secret_key_please_change_me') 
    JWT_TOKEN_LOCATION = ['headers', 'cookies'] 
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_COOKIE_SECURE = False # Set to True in production if served over HTTPS
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_REFRESH_COOKIE_PATH = '/api/auth/refresh' # Ensure this matches your refresh route
    JWT_ACCESS_COOKIE_PATH = '/api/' # Limit access token cookie to API paths
    JWT_COOKIE_CSRF_PROTECT = True # Enable CSRF protection for cookies
    JWT_CSRF_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE'] # CSRF protect these methods
    JWT_CSRF_IN_COOKIES = True # Store CSRF tokens in cookies (recommended)
    # If JWT_CSRF_IN_COOKIES is True, Flask-JWT-Extended will look for CSRF token in X-CSRF-TOKEN header by default.

    # File Uploads / Asset Storage
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'uploads'))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    ASSET_STORAGE_PATH = os.environ.get('ASSET_STORAGE_PATH', os.path.join(UPLOAD_FOLDER, 'generated_assets'))
    QR_CODE_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'qr_codes')
    PASSPORT_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'passports')
    LABEL_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'labels')
    
    DEFAULT_FONT_PATH = os.environ.get('DEFAULT_FONT_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'fonts', 'DejaVuSans.ttf')) 
    MAISON_TRUVRA_LOGO_PATH_LABEL = os.environ.get('MAISON_TRUVRA_LOGO_PATH_LABEL', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'logos', 'maison_truvra_label_logo.png')) 
    MAISON_TRUVRA_LOGO_PATH_PASSPORT = os.environ.get('MAISON_TRUVRA_LOGO_PATH_PASSPORT', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'logos', 'maison_truvra_passport_logo.png'))

    # Email Configuration (Ensure these are securely set in production environment)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.mailtrap.io') 
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 2525)) 
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 't')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') 
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') 
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@maisontruvra.com')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@maisontruvra.com')

    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY') 
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY') 
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET') 

    LOG_LEVEL = 'INFO'
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
    
    API_VERSION = "v1.1" # Increment API version due to security changes

    # Rate Limiting (More specific limits)
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', "memory://") # Use Redis in production
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_HEADERS_ENABLED = True
    DEFAULT_RATELIMITS = ["200 per day", "50 per hour"]
    AUTH_RATELIMITS = ["10 per minute", "100 per hour"] # For /api/auth/*
    ADMIN_LOGIN_RATELIMITS = ["5 per minute", "50 per hour"] # For /api/admin/login
    PASSWORD_RESET_RATELIMITS = ["5 per 15 minutes"] # For /api/auth/request-password-reset

    CONTENT_SECURITY_POLICY = {
        'default-src': ['\'self\''],
        'img-src': ['\'self\'', 'https://placehold.co', 'data:'],
        'script-src': ['\'self\'', 'https://cdn.tailwindcss.com'],
        'style-src': ['\'self\'', 'https://cdnjs.cloudflare.com', 'https://fonts.googleapis.com', '\'unsafe-inline\''],
        'font-src': ['\'self\'', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
        'connect-src': ['\'self\'', 'http://localhost:5001', 'http://127.0.0.1:5001'], # Adjust for dev API
        'form-action': ['\'self\''],
        'frame-ancestors': ['\'none\'']
    }
    TALISMAN_FORCE_HTTPS = False 

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    JWT_COOKIE_SECURE = False
    DATABASE_PATH = os.environ.get('DEV_DATABASE_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'dev_maison_truvra.sqlite3'))
    MAIL_SERVER = os.environ.get('DEV_MAIL_SERVER', 'localhost') 
    MAIL_PORT = int(os.environ.get('DEV_MAIL_PORT', 1025))      
    MAIL_USE_TLS = os.environ.get('DEV_MAIL_USE_TLS', 'false').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.environ.get('DEV_MAIL_USERNAME') 
    MAIL_PASSWORD = os.environ.get('DEV_MAIL_PASSWORD')
    TALISMAN_FORCE_HTTPS = False
    APP_BASE_URL = os.environ.get('DEV_APP_BASE_URL', 'http://localhost:3000')

class TestingConfig(Config):
    TESTING = True
    DEBUG = True 
    DATABASE_PATH = os.environ.get('TEST_DATABASE_PATH', 'sqlite:///:memory:') 
    JWT_COOKIE_SECURE = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(minutes=10)
    MAIL_SUPPRESS_SEND = True 
    TALISMAN_FORCE_HTTPS = False
    WTF_CSRF_ENABLED = False 

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    JWT_COOKIE_SECURE = True 
    JWT_COOKIE_SAMESITE = 'Strict' 
    TALISMAN_FORCE_HTTPS = True 
    APP_BASE_URL = os.environ.get('PROD_APP_BASE_URL', 'https://maisontruvra.com')
    RATELIMIT_STORAGE_URI = os.environ.get('PROD_RATELIMIT_STORAGE_URI', "redis://localhost:6379/0") # Example for Redis

    def __init__(self):
        super().__init__()
        if self.SECRET_KEY == 'your_default_secret_key_please_change_me':
            raise ValueError("Production SECRET_KEY is not set or is using the default value.")
        if self.JWT_SECRET_KEY == 'your_default_jwt_secret_key_please_change_me':
            raise ValueError("Production JWT_SECRET_KEY is not set or is using the default value.")
        if not self.STRIPE_SECRET_KEY or not self.STRIPE_PUBLISHABLE_KEY:
            print("WARNING: Stripe keys are not configured for production.")
        if not os.environ.get('MAIL_PASSWORD'): 
            print("WARNING: MAIL_PASSWORD is not set. Email functionality may be impaired.")

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
    paths_to_create = [
        os.path.dirname(config_instance.DATABASE_PATH), config_instance.UPLOAD_FOLDER,
        config_instance.ASSET_STORAGE_PATH, config_instance.QR_CODE_FOLDER,
        config_instance.PASSPORT_FOLDER, config_instance.LABEL_FOLDER,
        config_instance.PROFESSIONAL_DOCS_UPLOAD_PATH, config_instance.INVOICE_PDF_PATH
    ]
    for path in paths_to_create:
        if path: os.makedirs(path, exist_ok=True)
    return config_instance
