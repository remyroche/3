# backend/professional/routes.py
import os
import re # For VAT/SIRET validation
from flask import Blueprint, request, jsonify, current_app, url_for, abort as flask_abort
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from werkzeug.utils import secure_filename 
from datetime import datetime, timezone
from sqlalchemy import or_, func # For queries
from sqlalchemy.orm import selectinload # For eager loading

from .. import db 
from ..models import User, Invoice, Order, ProfessionalDocument, UserRoleEnum, ProfessionalStatusEnum # Import Enums
from ..utils import format_datetime_for_display, staff_or_admin_required, is_valid_email, allowed_file, get_file_extension 
from ..services.invoice_service import InvoiceService 

professional_bp = Blueprint('professional_bp', __name__, url_prefix='/api/professional')

# --- Validation Helpers (can be moved to a dedicated validation module) ---
def is_valid_siret(siret):
    """Basic SIRET validation (length and digits). More complex checksum validation can be added."""
    if not siret: return True # Allow empty if optional
    return bool(re.match(r'^\d{14}$', siret))

def is_valid_vat(vat_number):
    """Basic VAT number validation (example, often country-specific)."""
    if not vat_number: return True # Allow empty if optional
    # Example: French VAT: FR + 2 letters/digits + 9 digits. This is a very basic check.
    return bool(re.match(r'^[A-Z]{2}[A-Z0-9]{2,13}$', vat_number.upper())) 
# --- End Validation Helpers ---

@professional_bp.route('/profile', methods=['GET', 'PUT'])
@jwt_required()
def manage_professional_profile():
    user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    # Ensure user is a B2B professional
    user = User.query.filter_by(id=user_id, role=UserRoleEnum.B2B_PROFESSIONAL).first()
    if not user:
        audit_logger.log_action(user_id=user_id, action='pro_profile_fail_unauthorized', details="User not found or not a B2B professional.", status='failure', ip_address=ip_address)
        return jsonify(message="Professional account not found or access denied.", success=False), 403

    if request.method == 'GET':
        profile_data = {
            "id": user.id, "email": user.email, 
            "first_name": user.first_name, "last_name": user.last_name, 
            "company_name": user.company_name, "vat_number": user.vat_number, 
            "siret_number": user.siret_number,
            "professional_status": user.professional_status.value if user.professional_status else None,
            "is_verified": user.is_verified, "is_active": user.is_active,
            "created_at": format_datetime_for_display(user.created_at)
        }
        audit_logger.log_action(user_id=user_id, action='pro_get_profile_success', status='success', ip_address=ip_address)
        return jsonify(profile=profile_data, success=True), 200

    if request.method == 'PUT':
        data = request.json
        allowed_to_update = ['first_name', 'last_name', 'company_name', 'vat_number', 'siret_number']
        updated_fields = []
        validation_errors = {}

        for field in allowed_to_update:
            if field in data:
                new_value = data[field]
                # Add validation
                if field == 'siret_number' and new_value and not is_valid_siret(new_value):
                    validation_errors[field] = "Invalid SIRET number format (must be 14 digits)."
                elif field == 'vat_number' and new_value and not is_valid_vat(new_value):
                    validation_errors[field] = "Invalid VAT number format."
                # Add length checks or other specific validations if needed
                elif field in ['first_name', 'last_name', 'company_name'] and new_value and len(new_value) > 100: # Example length
                     validation_errors[field] = f"{field.replace('_', ' ').capitalize()} is too long (max 100 chars)."
                
                if field not in validation_errors and new_value != getattr(user, field):
                    setattr(user, field, new_value)
                    updated_fields.append(field)
        
        if validation_errors:
            audit_logger.log_action(user_id=user_id, action='pro_update_profile_fail_validation', details=str(validation_errors), status='failure', ip_address=ip_address)
            return jsonify(message="Validation failed.", errors=validation_errors, success=False), 400

        if not updated_fields:
            return jsonify(message="No changes detected or no updatable fields provided.", success=True), 200 # 200 as it's not an error

        user.updated_at = datetime.now(timezone.utc)
        try:
            db.session.commit()
            audit_logger.log_action(user_id=user_id, action='pro_update_profile_success', details=f"Fields updated: {', '.join(updated_fields)}", status='success', ip_address=ip_address)
            return jsonify(message="Profile updated successfully.", success=True), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating B2B profile for user {user_id}: {e}", exc_info=True)
            audit_logger.log_action(user_id=user_id, action='pro_update_profile_fail_exception', details=str(e), status='failure', ip_address=ip_address)
            return jsonify(message="Failed to update profile due to a server error.", success=False), 500

@professional_bp.route('/invoices', methods=['GET'])
@jwt_required()
def get_my_professional_invoices():
    user_id = get_jwt_identity()
    claims = get_jwt()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    if claims.get('role') != UserRoleEnum.B2B_PROFESSIONAL.value: # Compare with Enum value
        audit_logger.log_action(user_id=user_id, action='get_my_invoices_fail_unauthorized', details="User is not a B2B professional.", status='failure', ip_address=ip_address)
        return jsonify(message="Access restricted to B2B professionals.", success=False), 403

    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int) # Default 10 invoices per page

    if page < 1 or per_page < 1:
        return jsonify(message="Page and per_page parameters must be positive.", success=False), 400


    try:
        base_query = Invoice.query.filter(
            or_(
                Invoice.b2b_user_id == user_id,
                Invoice.order.has(Order.user_id == user_id) 
            )
        )
        
        paginated_invoices = base_query.order_by(Invoice.issue_date.desc())\
                                       .paginate(page=page, per_page=per_page, error_out=False)
        
        invoices_list = []
        for inv_model in paginated_invoices.items:
            invoice_dict = {
                "id": inv_model.id, "invoice_number": inv_model.invoice_number,
                "issue_date": format_datetime_for_display(inv_model.issue_date),
                "due_date": format_datetime_for_display(inv_model.due_date) if inv_model.due_date else None,
                "total_amount": inv_model.total_amount, "currency": inv_model.currency,
                "status": inv_model.status.value if inv_model.status else None, # Use Enum value
                "pdf_download_url": None
            }
            if inv_model.pdf_path:
                try:
                    # Ensure the path is relative to the ASSET_STORAGE_PATH for serve_asset
                    # If pdf_path is 'invoices/filename.pdf' and ASSET_STORAGE_PATH is the root for that:
                    pdf_relative_to_asset_serve = inv_model.pdf_path 
                    # If pdf_path is absolute or includes a different base, adjust accordingly.
                    # For now, assuming pdf_path is already correctly relative for admin_api_bp.serve_asset
                    invoice_dict['pdf_download_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=pdf_relative_to_asset_serve, _external=True)
                except Exception as e_url:
                    current_app.logger.warning(f"Could not generate download URL for B2B invoice PDF {inv_model.pdf_path}: {e_url}")
            invoices_list.append(invoice_dict)
        
        audit_logger.log_action(user_id=user_id, action='get_my_invoices_success', details=f"Fetched page {page} of {paginated_invoices.pages} for B2B invoices.", status='success', ip_address=ip_address)
        return jsonify(
            invoices=invoices_list, 
            total_invoices=paginated_invoices.total,
            current_page=paginated_invoices.page,
            total_pages=paginated_invoices.pages,
            per_page=paginated_invoices.per_page,
            success=True
        ), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching B2B invoices for user {user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=user_id, action='get_my_invoices_fail_exception', details=str(e), status='failure', ip_address=ip_address)
        return jsonify(message="Failed to fetch your invoices due to a server error.", success=False), 500

@professional_bp.route('/applications', methods=['GET'])
@staff_or_admin_required 
def get_professional_applications():
    audit_logger = current_app.audit_log_service
    current_staff_id = get_jwt_identity()
    ip_address = request.remote_addr
    status_filter_str = request.args.get('status', 'pending') 

    try:
        query = User.query.filter_by(role=UserRoleEnum.B2B_PROFESSIONAL)\
                          .options(selectinload(User.professional_documents)) # Eager load documents
        
        if status_filter_str and status_filter_str.lower() != 'all':
            try:
                status_enum_filter = ProfessionalStatusEnum(status_filter_str.lower())
                query = query.filter(User.professional_status == status_enum_filter)
            except ValueError:
                return jsonify(message=f"Invalid status filter value: {status_filter_str}", success=False), 400
        
        users_models = query.order_by(User.created_at.desc()).all()
        applications = []
        for user_model in users_models:
            docs_data = []
            for doc in user_model.professional_documents: # Access directly due to selectinload
                doc_download_url = None
                if doc.file_path:
                    try:
                        # Documents are sensitive, serve via admin asset route
                        doc_download_url = url_for('admin_api_bp.serve_asset', asset_relative_path=doc.file_path, _external=True)
                    except Exception as e_doc_url:
                         current_app.logger.warning(f"Could not generate download URL for prof. doc {doc.file_path}: {e_doc_url}")
                docs_data.append({
                    "id": doc.id, "document_type": doc.document_type, 
                    "file_path_stored": doc.file_path, # For admin reference, not direct client use
                    "upload_date": format_datetime_for_display(doc.upload_date),
                    "status": doc.status.value if doc.status else None, # Use Enum value
                    "download_url": doc_download_url
                })

            app_data = {
                "id": user_model.id, "email": user_model.email, 
                "first_name": user_model.first_name, "last_name": user_model.last_name, 
                "company_name": user_model.company_name, "vat_number": user_model.vat_number, 
                "siret_number": user_model.siret_number,
                "professional_status": user_model.professional_status.value if user_model.professional_status else None,
                "application_date": format_datetime_for_display(user_model.created_at),
                "documents": docs_data
            }
            applications.append(app_data)
        
        audit_logger.log_action(user_id=current_staff_id, action='admin_get_pro_applications_success', details=f"Fetched {len(applications)} B2B applications with status '{status_filter_str}'.", status='success', ip_address=ip_address)
        return jsonify(applications=applications, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching B2B applications by admin/staff {current_staff_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_staff_id, action='admin_get_pro_applications_fail', details=str(e), status='failure', ip_address=ip_address)
        return jsonify(message="Failed to fetch professional applications.", success=False), 500

@professional_bp.route('/applications/<int:application_user_id>/status', methods=['PUT'])
@staff_or_admin_required
def update_professional_application_status(application_user_id):
    current_staff_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr
    data = request.json
    new_status_str = data.get('status') 

    if not new_status_str:
        return jsonify(message="Status is required.", success=False), 400
    
    try:
        new_status_enum = ProfessionalStatusEnum(new_status_str.lower())
        if new_status_enum not in [ProfessionalStatusEnum.APPROVED, ProfessionalStatusEnum.REJECTED]:
            return jsonify(message="Invalid status provided. Must be 'approved' or 'rejected'.", success=False), 400
    except ValueError:
        return jsonify(message=f"Invalid status value: {new_status_str}", success=False), 400


    user = User.query.filter_by(id=application_user_id, role=UserRoleEnum.B2B_PROFESSIONAL).first()
    if not user:
        return jsonify(message="Professional application (user) not found.", success=False), 404

    old_status_val = user.professional_status.value if user.professional_status else "None"
    user.professional_status = new_status_enum
    user.updated_at = datetime.now(timezone.utc)
    
    # If approved, also mark user as verified if not already
    if new_status_enum == ProfessionalStatusEnum.APPROVED and not user.is_verified:
        user.is_verified = True
    
    try:
        db.session.commit()
        
        # Send email notification to the user
        # frontend_base_url = current_app.config.get('APP_BASE_URL_FRONTEND', current_app.config.get('APP_BASE_URL'))
        # subject = f"Your Maison Trüvra Professional Account Status: {new_status_enum.value.capitalize()}"
        # body = f"Dear {user.first_name or user.company_name},\n\nYour application for a professional account has been {new_status_enum.value}.\n"
        # if new_status_enum == ProfessionalStatusEnum.APPROVED:
        #     body += f"You can now log in to your professional area: {frontend_base_url}/professionnels.html\n"
        # else: # Rejected
        #     body += "If you have questions, please contact support.\n"
        # body += "\nRegards,\nMaison Trüvra Team"
        # send_email_alert(subject, body, user.email) # Replace with your actual email sending function
        current_app.logger.info(f"SIMULATED: Email notification for B2B status update to {user.email}, status: {new_status_enum.value}")

        audit_logger.log_action(
            user_id=current_staff_id, action='admin_update_pro_app_status_success', 
            target_type='user_b2b_application', target_id=application_user_id, 
            details=f"B2B application for user {user.email} status changed from '{old_status_val}' to '{new_status_enum.value}'.", 
            status='success', ip_address=ip_address
        )
        return jsonify(message=f"Application status updated to {new_status_enum.value}.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating B2B application status for user {application_user_id}: {e}", exc_info=True)
        audit_logger.log_action(
            user_id=current_staff_id, action='admin_update_pro_app_status_fail', 
            target_type='user_b2b_application', target_id=application_user_id, 
            details=str(e), status='failure', ip_address=ip_address
        )
        return jsonify(message="Failed to update application status.", success=False), 500

@professional_bp.route('/documents/upload', methods=['POST'])
@jwt_required() 
def upload_professional_document():
    user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    user = User.query.filter_by(id=user_id, role=UserRoleEnum.B2B_PROFESSIONAL).first()
    if not user:
        return jsonify(message="Professional account required to upload documents.", success=False), 403

    if 'document' not in request.files:
        return jsonify(message="No document file part in the request.", success=False), 400
    
    file = request.files['document']
    document_type = request.form.get('document_type') # e.g., "kbis", "vat_certificate"

    if file.filename == '':
        return jsonify(message="No selected file.", success=False), 400
    if not document_type:
        return jsonify(message="Document type is required.", success=False), 400
    
    # Sanitize document_type to prevent path traversal or invalid characters if used in filename
    safe_document_type = re.sub(r'[^a-zA-Z0-9_-]', '', document_type)
    if not safe_document_type:
        return jsonify(message="Invalid document type characters.", success=False), 400

    # Use a broader set of allowed extensions for documents
    allowed_doc_extensions = current_app.config.get('ALLOWED_DOCUMENT_EXTENSIONS', {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'})
    if file and allowed_file(file.filename, allowed_extensions_config_key='ALLOWED_DOCUMENT_EXTENSIONS'): # Pass config key
        filename_base = secure_filename(f"user_{user_id}_{safe_document_type}_{uuid.uuid4().hex[:8]}")
        extension = get_file_extension(file.filename)
        filename = f"{filename_base}.{extension}"
        
        upload_folder = current_app.config['PROFESSIONAL_DOCS_UPLOAD_PATH']
        os.makedirs(upload_folder, exist_ok=True)
        file_path_full = os.path.join(upload_folder, filename)
        file_path_relative_for_db = os.path.join('professional_documents', filename)

        try:
            file.save(file_path_full)
            
            new_doc = ProfessionalDocument(
                user_id=user_id,
                document_type=document_type, # Store original type from user
                file_path=file_path_relative_for_db, 
                status=ProfessionalStatusEnum.PENDING_REVIEW # Use Enum
            )
            db.session.add(new_doc)
            db.session.commit()
            
            audit_logger.log_action(user_id=user_id, action='pro_upload_doc_success', target_type='professional_document', target_id=new_doc.id, details=f"Document '{document_type}' uploaded: {filename}", status='success', ip_address=ip_address)
            return jsonify(message="Document uploaded successfully. It will be reviewed.", document_id=new_doc.id, file_path=new_doc.file_path, success=True), 201
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving professional document for user {user_id}: {e}", exc_info=True)
            audit_logger.log_action(user_id=user_id, action='pro_upload_doc_fail_exception', details=str(e), status='failure', ip_address=ip_address)
            if os.path.exists(file_path_full):
                try: os.remove(file_path_full)
                except OSError: pass
            return jsonify(message="Failed to upload document due to a server error.", success=False), 500
    else:
        return jsonify(message=f"Invalid file type. Allowed: {', '.join(allowed_doc_extensions)}.", success=False), 400

@professional_bp.route('/documents', methods=['GET'])
@jwt_required()
def get_my_professional_documents():
    user_id = get_jwt_identity()
    user = User.query.filter_by(id=user_id, role=UserRoleEnum.B2B_PROFESSIONAL).first()
    if not user: return jsonify(message="Professional account required.", success=False), 403

    try:
        documents = ProfessionalDocument.query.filter_by(user_id=user_id).order_by(ProfessionalDocument.upload_date.desc()).all()
        docs_data = []
        for doc in documents:
            download_url = None
            if doc.file_path:
                try:
                    download_url = url_for('admin_api_bp.serve_asset', asset_relative_path=doc.file_path, _external=True)
                except Exception as e_doc_url:
                    current_app.logger.warning(f"URL gen error for prof. doc {doc.file_path}: {e_doc_url}")
            docs_data.append({
                "id": doc.id, "document_type": doc.document_type, 
                "upload_date": format_datetime_for_display(doc.upload_date),
                "status": doc.status.value if doc.status else None, # Use Enum value
                "notes": doc.notes,
                "download_url": download_url
            })
        return jsonify(documents=docs_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching documents for B2B user {user_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch documents.", success=False), 500
