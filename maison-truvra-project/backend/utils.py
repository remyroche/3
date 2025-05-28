import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from functools import wraps
from unidecode import unidecode # For slug generation
from datetime import datetime, timezone # For date parsing/formatting

# --- Email Validation and Sending (Basic Implementation) ---
def is_valid_email(email):
    if not email:
        return False
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

def send_email_alert(subject, body, recipient_email=None):
    if not current_app.config.get('MAIL_SERVER'):
        current_app.logger.error("Mail server not configured. Cannot send email alert.")
        return False

    sender_email = current_app.config.get('MAIL_USERNAME')
    sender_password = current_app.config.get('MAIL_PASSWORD')
    mail_recipient = recipient_email or current_app.config.get('ADMIN_ALERT_EMAIL', current_app.config.get('ADMIN_EMAIL')) # Fallback to ADMIN_EMAIL

    if not sender_email or not sender_password or not mail_recipient:
        current_app.logger.error("Mail credentials or recipient not fully configured. Cannot send email alert.")
        return False

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = mail_recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

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
        
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, mail_recipient, text)
        server.quit()
        current_app.logger.info(f"Email alert '{subject}' sent successfully to {mail_recipient}.")
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email alert '{subject}' to {mail_recipient}: {e}", exc_info=True)
        return False

# --- Decorators ---
def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        # Check if the user has the 'admin' role.
        # The claim name for role might be 'role', 'user_claims', 'authorities', etc.,
        # depending on how it was set during token creation.
        # Assuming it's set as 'role' in additional_claims.
        if claims.get('role') != 'admin':
            return jsonify(message="Administration rights required"), 403
        
        # Optional: Further checks like is_active can be added here by querying the database
        # current_user_id = get_jwt_identity() # from flask_jwt_extended
        # user = query_db("SELECT is_active FROM users WHERE id = ? AND role = 'admin'", [current_user_id], one=True)
        # if not user or not user['is_active']:
        #     return jsonify(message="Admin account is not active."), 403
            
        return fn(*args, **kwargs)
    return wrapper

def staff_or_admin_required(fn): # From professional/routes.py, centralized here
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        allowed_roles = ['admin', 'staff'] 
        if claims.get('role') not in allowed_roles:
            return jsonify(message="Administration or staff rights required."), 403
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__ # Preserve original function name for Flask
    return wrapper

# --- File Handling ---
def allowed_file(filename, allowed_extensions):
    """Checks if the file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_file_extension(filename):
    """Extracts the file extension from a filename."""
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ''

# --- String Manipulation ---
def generate_slug(text):
    """
    Generates a URL-friendly slug from a given text string.
    Converts to lowercase, replaces spaces with hyphens, removes special characters,
    and uses unidecode for transliteration of non-ASCII characters.
    """
    if not text:
        return ""
    # Transliterate non-ASCII characters to their closest ASCII representation
    text = unidecode(str(text))
    # Remove characters that are not alphanumeric or hyphens
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    # Replace whitespace and multiple hyphens with a single hyphen
    text = re.sub(r'[-\s]+', '-', text)
    return text

# --- Date and Time Formatting/Parsing ---
def format_datetime_for_display(dt_obj_or_str):
    """
    Formats a datetime object or an ISO string to a more readable 'YYYY-MM-DD HH:MM:SS' string.
    Returns None or 'N/A' if input is invalid or None.
    """
    if not dt_obj_or_str:
        return None # Or 'N/A' depending on desired output for None/empty
    
    if isinstance(dt_obj_or_str, str):
        try:
            # Attempt to parse ISO format, handling 'Z' for UTC
            dt_obj_or_str = dt_obj_or_str.replace('Z', '+00:00')
            dt_obj = datetime.fromisoformat(dt_obj_or_str)
        except ValueError:
            # Fallback for other common formats or if parsing fails
            try:
                dt_obj = datetime.strptime(dt_obj_or_str, '%Y-%m-%d %H:%M:%S.%f%z') # With microsecond and timezone
            except ValueError:
                try:
                    dt_obj = datetime.strptime(dt_obj_or_str, '%Y-%m-%d %H:%M:%S%z') # Without microsecond
                except ValueError:
                    try:
                        dt_obj = datetime.strptime(dt_obj_or_str, '%Y-%m-%d %H:%M:%S') # No timezone
                    except ValueError:
                         current_app.logger.warning(f"Could not parse date string: {dt_obj_or_str}")
                         return dt_obj_or_str # Return original string if all parsing fails
    elif isinstance(dt_obj_or_str, datetime):
        dt_obj = dt_obj_or_str
    else:
        return str(dt_obj_or_str) # Or None or 'N/A'

    return dt_obj.strftime('%Y-%m-%d %H:%M:%S')


def parse_datetime_from_iso(iso_str):
    """
    Parses an ISO 8601 datetime string (potentially with 'Z' or timezone offset)
    into a timezone-aware datetime object (UTC if 'Z' or no offset).
    Returns None if parsing fails.
    """
    if not iso_str:
        return None
    try:
        # Handle 'Z' for UTC explicitly for robust parsing
        if iso_str.endswith('Z'):
            iso_str = iso_str[:-1] + '+00:00'
        
        dt_obj = datetime.fromisoformat(iso_str)
        # If no timezone info, assume UTC (or make it naive, then localize if needed)
        if dt_obj.tzinfo is None:
            return dt_obj.replace(tzinfo=timezone.utc) # Make it timezone-aware (UTC)
        return dt_obj
    except ValueError as e:
        current_app.logger.warning(f"Failed to parse ISO datetime string '{iso_str}': {e}")
        return None

def format_datetime_for_storage(dt_obj):
    """
    Formats a datetime object into an ISO 8601 string suitable for database storage,
    preferably in UTC.
    """
    if not isinstance(dt_obj, datetime):
        return None # Or raise error
    
    # If datetime is naive, assume it's local time and convert to UTC
    # Or, if it should be treated as UTC already, make it aware
    if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None:
        # Assuming naive datetime should be treated as UTC
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC if it's timezone-aware but not UTC
        dt_obj = dt_obj.astimezone(timezone.utc)
        
    return dt_obj.isoformat(timespec='seconds') # Store up to seconds, append Z for UTC