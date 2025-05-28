import re
import smtplib # Basic SMTP, consider Flask-Mail for production
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, jsonify, g, request # Added request
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity
from functools import wraps
from unidecode import unidecode
from datetime import datetime, timezone, timedelta

# --- Email Validation and Sending ---
def is_valid_email(email):
    if not email:
        return False
    # Basic regex, consider a more robust library for production if strict validation is needed
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

def send_email_alert(subject, body, recipient_email=None):
    """
    Basic email sending function.
    WARNING: This is a basic implementation. For production, use Flask-Mail
    or a dedicated email service (e.g., SendGrid, Mailgun) for reliability,
    template management, and better error handling.
    This function is kept as a placeholder and might be commented out
    or replaced entirely when a proper email service is integrated.
    """
    # TODO: Replace this with Flask-Mail or a dedicated email service integration.
    # Example structure for Flask-Mail (after setting up Flask-Mail in create_app):
    # from flask_mail import Message
    # from your_app import mail # Assuming 'mail' is your Flask-Mail instance
    # try:
    #     msg = Message(subject,
    #                   sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
    #                   recipients=[recipient_email or current_app.config.get('ADMIN_EMAIL')])
    #     msg.body = body # For plain text
    #     # msg.html = "<h1>HTML Body</h1>" # For HTML emails
    #     mail.send(msg)
    #     current_app.logger.info(f"Email '{subject}' sent successfully to {msg.recipients[0]} via Flask-Mail.")
    #     return True
    # except Exception as e:
    #     current_app.logger.error(f"Flask-Mail failed to send email '{subject}': {e}", exc_info=True)
    #     return False

    current_app.logger.warning(f"Attempting to send email via basic smtplib (not recommended for production). Subject: {subject}")

    if not current_app.config.get('MAIL_SERVER'):
        current_app.logger.error("Mail server not configured. Cannot send email alert.")
        return False

    sender_email = current_app.config.get('MAIL_USERNAME') 
    sender_password = current_app.config.get('MAIL_PASSWORD')
    mail_recipient = recipient_email or current_app.config.get('ADMIN_EMAIL')

    if not sender_email or not mail_recipient:
        current_app.logger.error("Mail sender or recipient not fully configured. Cannot send email alert.")
        return False

    msg_obj = MIMEMultipart()
    msg_obj['From'] = current_app.config.get('MAIL_DEFAULT_SENDER', sender_email)
    msg_obj['To'] = mail_recipient
    msg_obj['Subject'] = subject
    msg_obj.attach(MIMEText(body, 'plain')) # Or 'html' for HTML emails

    try:
        mail_port = current_app.config.get('MAIL_PORT', 587)
        use_tls = current_app.config.get('MAIL_USE_TLS', True)
        use_ssl = current_app.config.get('MAIL_USE_SSL', False)

        if use_ssl:
            server = smtplib.SMTP_SSL(current_app.config['MAIL_SERVER'], mail_port)
        else:
            server = smtplib.SMTP(current_app.config['MAIL_SERVER'], mail_port)
        
        if use_tls and not use_ssl:
            server.starttls()
        
        if sender_password: 
            server.login(sender_email, sender_password)
        
        text_to_send = msg_obj.as_string()
        server.sendmail(msg_obj['From'], mail_recipient, text_to_send)
        server.quit()
        current_app.logger.info(f"Basic email alert '{subject}' sent successfully to {mail_recipient}.")
        return True
    except Exception as e:
        current_app.logger.error(f"Basic smtplib failed to send email alert '{subject}' to {mail_recipient}: {e}", exc_info=True)
        return False

# --- Decorators for Route Protection ---
def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Ensure JWT is present and valid
        try:
            verify_jwt_in_request()
        except Exception as e:
            current_app.logger.warning(f"Admin access denied for {request.path}: JWT verification failed - {e}")
            return jsonify(message="Access token is missing or invalid."), 401

        # Check if g.is_admin is populated by the @before_request hook in __init__.py
        if hasattr(g, 'is_admin') and g.is_admin:
            # Optionally, re-verify against DB if needed, but g.is_admin should be trusted if set correctly
            return fn(*args, **kwargs)
        
        # Fallback: If g.is_admin is not set or false, check claims directly (should ideally not be needed if before_request is robust)
        claims = get_jwt()
        if claims.get('role') == 'admin':
            # To be absolutely sure, you might re-check the user's active status from DB here
            # current_user_id = get_jwt_identity()
            # from .database import query_db, get_db_connection # Avoid circular import if possible
            # db = get_db_connection()
            # admin_user = query_db("SELECT is_active FROM users WHERE id = ? AND role = 'admin'", [current_user_id], db_conn=db, one=True)
            # if not admin_user or not admin_user['is_active']:
            #     return jsonify(message="Admin account is not active."), 403
            return fn(*args, **kwargs)
        else:
            current_app.logger.warning(f"Admin access denied for {request.path}: Role is not admin.")
            return jsonify(message="Administration rights required."), 403
            
    wrapper.__name__ = fn.__name__ 
    return wrapper

def staff_or_admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception as e:
            current_app.logger.warning(f"Staff/Admin access denied for {request.path}: JWT verification failed - {e}")
            return jsonify(message="Access token is missing or invalid."), 401

        allowed_roles = ['admin', 'staff'] # Define staff role if it exists
        
        if hasattr(g, 'current_user_role') and g.current_user_role in allowed_roles:
            return fn(*args, **kwargs)

        claims = get_jwt()
        if claims.get('role') in allowed_roles:
            return fn(*args, **kwargs)
        else:
            current_app.logger.warning(f"Staff/Admin access denied for {request.path}: Role not in {allowed_roles}.")
            return jsonify(message="Administration or staff rights required."), 403
            
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
    text = unidecode(str(text)) # Transliterate non-ASCII characters
    text = re.sub(r'[^\w\s-]', '', text).strip().lower() # Remove special chars, strip, lowercase
    text = re.sub(r'[-\s]+', '-', text) # Replace spaces and multiple hyphens with single hyphen
    return text

# --- Date and Time Formatting/Parsing ---
def format_datetime_for_display(dt_obj_or_str, fmt='%Y-%m-%d %H:%M:%S'):
    """Formats a datetime object or ISO string to a readable format."""
    if not dt_obj_or_str: return None
    
    dt_obj = None
    if isinstance(dt_obj_or_str, str):
        try:
            # Handle 'Z' for UTC explicitly for robust parsing
            dt_str_normalized = dt_obj_or_str.replace('Z', '+00:00')
            dt_obj = datetime.fromisoformat(dt_str_normalized)
        except ValueError:
            # Try common SQLite formats if ISO parsing fails
            common_formats = ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']
            for date_fmt in common_formats:
                try:
                    dt_obj = datetime.strptime(dt_obj_or_str, date_fmt)
                    break 
                except ValueError:
                    continue
            if not dt_obj:
                current_app.logger.debug(f"Could not parse date string for display: {dt_obj_or_str}")
                return dt_obj_or_str # Return original if all parsing fails
    elif isinstance(dt_obj_or_str, datetime):
        dt_obj = dt_obj_or_str
    else:
        return str(dt_obj_or_str) # Return as string if not datetime or parsable string

    # If datetime is timezone-aware, convert to local time for display (optional)
    # For simplicity, this example just formats. Add timezone conversion if needed.
    # e.g., local_tz = get_localzone(); dt_obj = dt_obj.astimezone(local_tz)
    return dt_obj.strftime(fmt)

def parse_datetime_from_iso(iso_str):
    """Parses an ISO 8601 string to a timezone-aware datetime object (UTC)."""
    if not iso_str: return None
    try:
        dt_str_normalized = iso_str.replace('Z', '+00:00')
        dt_obj = datetime.fromisoformat(dt_str_normalized)
        # If datetime object is naive, assume it's UTC.
        if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None:
            return dt_obj.replace(tzinfo=timezone.utc)
        return dt_obj.astimezone(timezone.utc) # Ensure it's UTC
    except ValueError as e:
        current_app.logger.warning(f"Failed to parse ISO datetime string '{iso_str}': {e}")
        # Try to parse common date-only format as well
        try:
            dt_obj = datetime.strptime(iso_str, '%Y-%m-%d')
            return dt_obj.replace(tzinfo=timezone.utc) # Assume UTC if only date
        except ValueError:
            return None # Return None if all parsing fails


def format_datetime_for_storage(dt_obj=None):
    """Formats a datetime object (or now if None) to ISO 8601 UTC string for DB."""
    if dt_obj is None:
        dt_obj = datetime.now(timezone.utc)
    if not isinstance(dt_obj, datetime):
        # Try to parse if it's a string that might be a date
        if isinstance(dt_obj, str):
            parsed_dt = parse_datetime_from_iso(dt_obj)
            if parsed_dt:
                dt_obj = parsed_dt
            else:
                return None # Cannot format if not datetime or parsable
        else:
            return None 
    
    # Ensure the datetime object is timezone-aware and in UTC
    if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc) # Assume UTC if naive
    else:
        dt_obj = dt_obj.astimezone(timezone.utc) # Convert to UTC if timezone-aware but not UTC
        
    return dt_obj.isoformat(timespec='seconds') # Store with second precision
