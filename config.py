import os
from datetime import timedelta

class Config:
    """Base configuration."""
    # General Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your_default_secret_key_please_change_me') # Load from env, fallback to a default (for dev only)
    DEBUG = False
    TESTING = False
    APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:8000') # For frontend, or https://maisontruvra.com for prod
    
    # Database configuration
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'maison_truvra.sqlite3'))
    
    # JWT Extended Settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your_default_jwt_secret_key_please_change_me') # Load from env
    JWT_TOKEN_LOCATION = ['headers', 'cookies'] 
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_COOKIE_SECURE = False 
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_REFRESH_COOKIE_PATH = '/auth/refresh' 

    # File Uploads / Asset Storage
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'uploads'))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # QR Code, Passport, Label Generation
    ASSET_STORAGE_PATH = os.environ.get('ASSET_STORAGE_PATH', os.path.join(UPLOAD_FOLDER, 'generated_assets'))
    QR_CODE_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'qr_codes')
    PASSPORT_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'passports')
    LABEL_FOLDER = os.path.join(ASSET_STORAGE_PATH, 'labels') # For PDF labels
    
    # Ensure font path is correct and font supports French characters (e.g., DejaVuSans is good)
    DEFAULT_FONT_PATH = os.environ.get('DEFAULT_FONT_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'fonts', 'DejaVuSans.ttf')) 
    MAISON_TRUVRA_LOGO_PATH_LABEL = os.environ.get('MAISON_TRUVRA_LOGO_PATH_LABEL', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'logos', 'maison_truvra_label_logo.png')) 
    MAISON_TRUVRA_LOGO_PATH_PASSPORT = os.environ.get('MAISON_TRUVRA_LOGO_PATH_PASSPORT', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_assets', 'logos', 'maison_truvra_passport_logo.png'))

    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.mailtrap.io') 
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 2525)) 
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 't')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'your_mail_username') 
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') 
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@maisontruvra.com')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@maisontruvra.com')

    # Stripe Configuration
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY') 
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY') 
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET') 

    # Logging
    LOG_LEVEL = 'INFO'

    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', "http://localhost:8000,http://127.0.0.1:8000") 

    # Professional Application Documents
    # Corrected typo: professional_docs_upload_path
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

    # Default Content Security Policy (CSP)
    # This is a starting point and needs to be carefully tested and adjusted.
    # 'unsafe-inline' for styles is often needed for Tailwind, consider nonce/hash for production.
    # 'unsafe-eval' might be needed by some JS libraries, try to avoid.
    CONTENT_SECURITY_POLICY = {
        'default-src': [
            '\'self\''
        ],
        'img-src': [
            '\'self\'',
            'https://placehold.co', # For placeholder images
            'data:' # If you use data URIs for images
        ],
        'script-src': [
            '\'self\'',
            'https://cdn.tailwindcss.com', # Tailwind
            # Add Stripe's JS URL if used, e.g., 'https://js.stripe.com'
            # Add other external JS CDNs if used by frontend
        ],
        'style-src': [
            '\'self\'',
            'https://cdnjs.cloudflare.com', # FontAwesome (if used)
            'https://fonts.googleapis.com', # Google Fonts
            '\'unsafe-inline\'' # Often needed by Tailwind, consider alternatives for stricter CSP
        ],
        'font-src': [
            '\'self\'',
            'https://fonts.gstatic.com', # Google Fonts
            'https://cdnjs.cloudflare.com' # FontAwesome (if used)
        ],
        'connect-src': [ # For API calls if frontend is on a different port/domain during dev
            '\'self\'',
            # If your API is served on a different port during development, add it here.
            # e.g., 'http://localhost:5001' if frontend is on 8000 and API on 5001
        ],
        'form-action': [ # Restrict where forms can submit to
            '\'self\''
        ],
        'frame-ancestors': [ # Prevent clickjacking
            '\'none\'' # Or '\'self\'' if you need to frame your own site
        ]
        # Add other directives as needed (frame-src, media-src, object-src)
    }
    TALISMAN_FORCE_HTTPS = False # Set to True in production if behind a reverse proxy that handles TLS termination


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
    APP_BASE_URL = os.environ.get('DEV_APP_BASE_URL', 'http://localhost:3000') # Adjust if your dev frontend is elsewhere


class TestingConfig(Config):
    TESTING = True
    DEBUG = True 
    DATABASE_PATH = os.environ.get('TEST_DATABASE_PATH', 'sqlite:///:memory:') 
    JWT_COOKIE_SECURE = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(minutes=10)
    MAIL_SUPPRESS_SEND = True 
    TALISMAN_FORCE_HTTPS = False
    WTF_CSRF_ENABLED = False # Often disabled for easier testing of forms


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    JWT_COOKIE_SECURE = True 
    JWT_COOKIE_SAMESITE = 'Strict' 
    TALISMAN_FORCE_HTTPS = True # Enforce HTTPS in production
    APP_BASE_URL = os.environ.get('PROD_APP_BASE_URL', 'https://maisontruvra.com')

    def __init__(self):
        super().__init__()
        if self.SECRET_KEY == 'your_default_secret_key_please_change_me':
            raise ValueError("Production SECRET_KEY is not set or is using the default value. Please set it via environment variable.")
        if self.JWT_SECRET_KEY == 'your_default_jwt_secret_key_please_change_me':
            raise ValueError("Production JWT_SECRET_KEY is not set or is using the default value. Please set it via environment variable.")
        if not self.STRIPE_SECRET_KEY or not self.STRIPE_PUBLISHABLE_KEY:
            print("WARNING: Stripe keys are not configured for production. Payment processing will not work.")
        if not os.environ.get('MAIL_PASSWORD'): 
            print("WARNING: MAIL_PASSWORD is not set in the environment. Email functionality may be impaired.")
        
        # Ensure UPLOAD_FOLDER and ASSET_STORAGE_PATH are secure and appropriate for production
        # e.g., not inside the application code directory if served by a web server like Nginx.


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
        os.path.dirname(config_instance.DATABASE_PATH), 
        config_instance.UPLOAD_FOLDER,
        config_instance.ASSET_STORAGE_PATH,
        config_instance.QR_CODE_FOLDER,
        config_instance.PASSPORT_FOLDER,
        config_instance.LABEL_FOLDER,
        config_instance.PROFESSIONAL_DOCS_UPLOAD_PATH,
        config_instance.INVOICE_PDF_PATH
    ]
    for path in paths_to_create:
        if path: 
            os.makedirs(path, exist_ok=True)
            
    return config_instance
