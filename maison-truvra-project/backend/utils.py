import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, jsonify, g # Added g
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity
from functools import wraps
from unidecode import unidecode
from datetime import datetime, timezone, timedelta

# --- Email Validation and Sending (Basic Implementation) ---
def is_valid_email(email):
    if not email:
        return False
    # Basic regex, consider a more robust library for production if strict validation is needed
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

def send_email_alert(subject, body, recipient_email=None):
    # This is a basic email sending function. For production, consider using Flask-Mail or a dedicated email service.
    if not current_app.config.get('MAIL_SERVER'):
        current_app.logger.error("Mail server not configured. Cannot send email alert.")
        return False

    sender_email = current_app.config.get('MAIL_USERNAME') # Should be MAIL_DEFAULT_SENDER or specific sender
    sender_password = current_app.config.get('MAIL_PASSWORD')
    mail_recipient = recipient_email or current_app.config.get('ADMIN_EMAIL') # Use ADMIN_EMAIL as default recipient

    if not sender_email or not mail_recipient: # Password might not be needed for all servers
        current_app.logger.error("Mail sender or recipient not fully configured. Cannot send email alert.")
        return False

    msg = MIMEMultipart()
    msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER', sender_email)
    msg['To'] = mail_recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain')) # Or 'html' for HTML emails

    try:
        mail_port = current_app.config.get('MAIL_PORT', 587)
        use_tls = current_app.config.get('MAIL_USE_TLS', True)
        use_ssl = current_app.config.get('MAIL_USE_SSL', False)

        if use_ssl:
            server = smtplib.SMTP_SSL(current_app.config['MAIL_SERVER'], mail_port)
        else:
            server = smtplib.SMTP(current_app.config['MAIL_SERVER'], mail_port)
        
        if use_tls and not use_ssl: # TLS is typically used with port 587
            server.starttls()
        
        if sender_password: # Login only if password is provided
            server.login(sender_email, sender_password)
        
        text = msg.as_string()
        server.sendmail(msg['From'], mail_recipient, text)
        server.quit()
        current_app.logger.info(f"Email alert '{subject}' sent successfully to {mail_recipient}.")
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email alert '{subject}' to {mail_recipient}: {e}", exc_info=True)
        return False

# --- Decorators for Route Protection ---
def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # verify_jwt_in_request() # This is automatically called by @jwt_required if used on the route
        # If @jwt_required is not used, then verify_jwt_in_request() is needed here.
        # Assuming g.is_admin is populated by a @before_request hook
        if not hasattr(g, 'is_admin') or not g.is_admin:
            # Fallback if g.is_admin not set: try to verify and check claims directly
            try:
                verify_jwt_in_request()
                claims = get_jwt()
                if claims.get('role') != 'admin':
                    return jsonify(message="Administration rights required (claim missing/invalid)."), 403
            except Exception as e: # Catches NoAuthorizationError, InvalidHeaderError, etc.
                current_app.logger.warning(f"Admin access denied for {request.path}: {e}")
                return jsonify(message="Administration rights required (token issue)."), 401 # Or 403
        
        # Optional: Check if the admin user is active in DB
        # current_user_id = get_jwt_identity()
        # from .database import query_db, get_db_connection
        # db = get_db_connection()
        # admin_user = query_db("SELECT is_active FROM users WHERE id = ? AND role = 'admin'", [current_user_id], db_conn=db, one=True)
        # if not admin_user or not admin_user['is_active']:
        #     return jsonify(message="Admin account is not active."), 403
            
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__ # Preserve original function name for Flask
    return wrapper

def staff_or_admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Assuming g.current_user_role is populated by a @before_request hook
        allowed_roles = ['admin', 'staff']
        if not hasattr(g, 'current_user_role') or g.current_user_role not in allowed_roles:
            try:
                verify_jwt_in_request()
                claims = get_jwt()
                if claims.get('role') not in allowed_roles:
                    return jsonify(message="Administration or staff rights required (claim missing/invalid)."), 403
            except Exception as e:
                current_app.logger.warning(f"Staff/Admin access denied for {request.path}: {e}")
                return jsonify(message="Administration or staff rights required (token issue)."), 401
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

# --- File Handling ---
def allowed_file(filename, allowed_extensions_config_key='ALLOWED_EXTENSIONS'):
    """Checks if the file has an allowed extension from app config."""
    allowed_extensions = current_app.config.get(allowed_extensions_config_key, {'png', 'jpg', 'jpeg', 'gif', 'pdf'})
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_file_extension(filename):
    """Extracts the file extension from a filename."""
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ''

# --- String Manipulation ---
def generate_slug(text):
    """Generates a URL-friendly slug from text."""
    if not text: return ""
    text = unidecode(str(text))
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    text = re.sub(r'[-\s]+', '-', text)
    return text

# --- Date and Time Formatting/Parsing ---
def format_datetime_for_display(dt_obj_or_str, fmt='%Y-%m-%d %H:%M:%S'):
    """Formats a datetime object or ISO string to a readable format."""
    if not dt_obj_or_str: return None
    
    if isinstance(dt_obj_or_str, str):
        try:
            dt_obj_or_str = dt_obj_or_str.replace('Z', '+00:00')
            dt_obj = datetime.fromisoformat(dt_obj_or_str)
        except ValueError:
            try: dt_obj = datetime.strptime(dt_obj_or_str, '%Y-%m-%d %H:%M:%S.%f') # Common SQLite format
            except ValueError:
                try: dt_obj = datetime.strptime(dt_obj_or_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    current_app.logger.debug(f"Could not parse date string for display: {dt_obj_or_str}")
                    return dt_obj_or_str # Return original if parsing fails
    elif isinstance(dt_obj_or_str, datetime):
        dt_obj = dt_obj_or_str
    else:
        return str(dt_obj_or_str)

    # If datetime is timezone-aware, convert to local time for display (optional)
    # For simplicity, just formatting. Add timezone conversion if needed.
    return dt_obj.strftime(fmt)

def parse_datetime_from_iso(iso_str):
    """Parses an ISO 8601 string to a timezone-aware datetime object (UTC)."""
    if not iso_str: return None
    try:
        if iso_str.endswith('Z'):
            iso_str = iso_str[:-1] + '+00:00'
        dt_obj = datetime.fromisoformat(iso_str)
        if dt_obj.tzinfo is None:
            return dt_obj.replace(tzinfo=timezone.utc)
        return dt_obj.astimezone(timezone.utc) # Ensure it's UTC
    except ValueError as e:
        current_app.logger.warning(f"Failed to parse ISO datetime string '{iso_str}': {e}")
        return None

def format_datetime_for_storage(dt_obj=None):
    """Formats a datetime object (or now if None) to ISO 8601 UTC string for DB."""
    if dt_obj is None:
        dt_obj = datetime.now(timezone.utc)
    if not isinstance(dt_obj, datetime):
        return None
    
    if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    else:
        dt_obj = dt_obj.astimezone(timezone.utc)
        
    return dt_obj.isoformat(timespec='seconds')