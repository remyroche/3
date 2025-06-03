# backend/audit_log_service.py (or within __init__.py)
import logging
from flask import current_app, request
from .. import db # Assuming db is accessible
from ..models import AuditLog, User, AuditLogStatusEnum # Import Enum

class AuditLogService:
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.logger = app.logger # Use Flask app's logger
        else:
            self.logger = logging.getLogger(__name__) # Fallback logger

    def log_action(self, action, user_id=None, email_for_unauthenticated=None, 
                   target_type=None, target_id=None, details=None, 
                   status="success", ip_address=None):
        try:
            # Convert status string to Enum member
            try:
                status_enum = AuditLogStatusEnum(status.lower())
            except ValueError:
                self.logger.warning(f"Invalid audit log status string '{status}' received. Defaulting to INFO.")
                status_enum = AuditLogStatusEnum.INFO
            
            final_details = details
            if not user_id and email_for_unauthenticated:
                detail_prefix = f"Attempt by email: {email_for_unauthenticated}. "
                final_details = f"{detail_prefix}{details}" if details else detail_prefix

            log_entry = AuditLog(
                action=action,
                user_id=user_id, # user_id is sufficient, username removed from model
                target_type=target_type,
                target_id=int(target_id) if target_id is not None else None,
                details=final_details,
                status=status_enum, # Store Enum member
                ip_address=ip_address or (request.remote_addr if request else None)
            )
            
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            self.logger.error(f"Failed to write audit log: Action={action}, UserID={user_id}, Target={target_type}/{target_id}. Error: {e}", exc_info=True)
            # Avoid rollback if the main transaction should proceed,
            # but if audit logging is critical, this might need its own session or careful handling.
            # For now, assume a simple commit and log error on failure.
            # db.session.rollback() # This might rollback more than just the audit log if called within a larger transaction
