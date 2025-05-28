import sqlite3
import json
from flask import g, request, current_app
from datetime import datetime

# Import the centralized get_db_connection function
from backend.database import get_db_connection, query_db # query_db might be useful for fetching username

class AuditLogService:
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initializes the service with the Flask app, if not done in constructor."""
        self.app = app
        # Ensure the service instance is attached to the app context if needed elsewhere
        # app.audit_log_service = self # This is typically done in create_app

    def _get_db(self):
        """
        Gets the database connection from Flask's application context.
        Relies on the connection being managed by backend.database.get_db_connection().
        """
        # Always use the get_db_connection from the centralized database module.
        # This ensures it uses g.db_conn and is managed within the app context.
        try:
            return get_db_connection()
        except RuntimeError as e:
            # This might happen if called outside of an app context where 'g' is not available
            # or current_app is not set up correctly.
            # For audit logging, it's critical to have a valid app and request context.
            if self.app: # Try to use self.app if current_app is not available (less ideal)
                with self.app.app_context():
                    # current_app.logger.warning("AuditLogService._get_db: Re-attempting DB connection within explicit app_context.")
                    return get_db_connection()
            # If still failing, log to stderr as app logger might not be available.
            print(f"CRITICAL: AuditLogService could not obtain database connection: {e}")
            raise RuntimeError(f"AuditLogService failed to get DB connection: {e}. Ensure it's used within an active Flask app/request context.")


    def log_action(self, action: str, user_id: int = None, username: str = None,
                   target_type: str = None, target_id = None, # target_id can be int or str (e.g. item_uid)
                   details: str = None, status: str = 'success', 
                   ip_address: str = None, email: str = None): # Added email for logging attempts before user_id is known
        """
        Logs an action to the audit log table.
        The database commit is expected to be handled by the caller as part of the main transaction.
        """
        if not self.app and not current_app:
            print(f"ERROR: AuditLogService cannot log action '{action}' - Flask app not configured.")
            return

        # Use current_app if available, otherwise fallback to self.app (from init)
        app_context = current_app if current_app else self.app
        if not app_context:
            print(f"CRITICAL ERROR: AuditLogService cannot operate without an app context for action: {action}")
            return # Cannot proceed without an app context

        try:
            db = self._get_db() # Get connection from app context
            cursor = db.cursor()

            # If user_id is provided but username is not, try to fetch it
            if user_id is not None and username is None:
                try:
                    # Use query_db for consistency, ensuring it uses the same db_conn
                    user_data = query_db("SELECT email FROM users WHERE id = ?", [user_id], db_conn=db, one=True)
                    if user_data:
                        username = user_data['email'] # Using email as username for audit
                    else:
                        username = f"User ID {user_id} (Not Found)"
                except Exception as e_user:
                    # Log to app logger if available, otherwise print
                    logger = app_context.logger if hasattr(app_context, 'logger') else print
                    logger(f"AuditLogService: Could not fetch username for user_id {user_id}: {e_user}")
                    username = f"User ID {user_id} (Error Fetching)"
            
            if username is None and email is not None: # If login attempt failed, email might be available
                username = email


            # Determine IP address if not provided and request context is available
            if ip_address is None:
                try:
                    if request: # Check if request context is active
                        ip_address = request.remote_addr
                except RuntimeError: # Outside of request context
                    ip_address = None 
            
            # Serialize details if it's a dictionary
            if isinstance(details, dict):
                try:
                    details_str = json.dumps(details)
                except TypeError:
                    details_str = str(details) # Fallback to string representation
            else:
                details_str = details

            sql = """
                INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, status, ip_address, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            params = (user_id, username, action, target_type, str(target_id) if target_id is not None else None, details_str, status, ip_address)
            
            cursor.execute(sql, params)
            # DO NOT COMMIT HERE. The calling route/service is responsible for the transaction.
            
            # Log to app logger (if available) that an audit entry was prepared
            logger = app_context.logger if hasattr(app_context, 'logger') else print
            logger.debug(f"Audit action prepared for logging (pending commit): User='{username}', Action='{action}', Status='{status}'")

        except sqlite3.Error as e_sql:
            logger = app_context.logger if hasattr(app_context, 'logger') else print
            logger.error(f"AuditLogService: Database error writing audit log for action '{action}': {e_sql}. Parameters: {params}")
            # Depending on policy, you might want to raise this or just log it.
            # If audit logging is critical, raising might be appropriate.
            # For now, just log, as failing an audit log shouldn't break the main app flow.
        except Exception as e:
            logger = app_context.logger if hasattr(app_context, 'logger') else print
            logger.error(f"AuditLogService: Unexpected error logging action '{action}': {e}")
            # Similar to above, decide on re-raising.

    def get_logs(self, page=1, per_page=20, user_id_filter=None, action_filter=None, target_type_filter=None, status_filter=None):
        """
        Retrieves audit logs with pagination and optional filters.
        """
        if not self.app and not current_app:
            print("ERROR: AuditLogService cannot get logs - Flask app not configured.")
            return [], 0
        
        app_context = current_app if current_app else self.app
        if not app_context:
            print(f"CRITICAL ERROR: AuditLogService cannot operate without an app context for get_logs")
            return [],0


        db = self._get_db()
        offset = (page - 1) * per_page
        
        base_query = "SELECT * FROM audit_log"
        count_query = "SELECT COUNT(*) FROM audit_log"
        conditions = []
        params = []

        if user_id_filter:
            conditions.append("user_id = ?")
            params.append(user_id_filter)
        if action_filter:
            conditions.append("action LIKE ?")
            params.append(f"%{action_filter}%")
        if target_type_filter:
            conditions.append("target_type = ?")
            params.append(target_type_filter)
        if status_filter:
            conditions.append("status = ?")
            params.append(status_filter)

        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)
            base_query += where_clause
            count_query += where_clause
        
        base_query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        query_params = params + [per_page, offset]
        
        try:
            logs_data = query_db(base_query, query_params, db_conn=db)
            total_logs_row = query_db(count_query, params, db_conn=db, one=True) # Params for count query
            
            logs = [dict(row) for row in logs_data] if logs_data else []
            total_logs = total_logs_row[0] if total_logs_row else 0
            
            return logs, total_logs
        except Exception as e:
            logger = app_context.logger if hasattr(app_context, 'logger') else print
            logger.error(f"AuditLogService: Error fetching audit logs: {e}")
            return [], 0
