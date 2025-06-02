# backend/professional/routes.py
import os
from flask import Blueprint, request, jsonify, current_app, url_for, abort as flask_abort
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from werkzeug.utils import secure_filename # For file uploads
from datetime import datetime, timezone

from .. import db # Import SQLAlchemy instance
from ..models import User, Invoice, ProfessionalDocument # Assuming ProfessionalDocument model exists
from ..utils import format_datetime_for_display, staff_or_admin_required, is_valid_email, allowed_file, get_file_extension # Import necessary utils
from ..services.invoice_service import InvoiceService # Assuming this service uses SQLAlchemy

professional_bp = Blueprint('professional_bp', __name__, url_prefix='/api/professional')

@professional_bp.route('/profile', methods=['GET', 'PUT'])
@jwt_required()
def manage_professional_profile():
    user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    user = User.query.filter_by(id=user_id, role='b2b_professional').first()
    if not user:
        audit_logger.log_action(user_id=user_id, action='pro_profile_fail_unauthorized', details="User not found or not a B2B professional.", status='failure', ip_address=ip_address)
        return jsonify(message="Professional account not found or access denied.", success=False), 403

    if request.method == 'GET':
        profile_data = {
            "id": user.id, "email": user.email, "first_name": user.first_name,
            "last_name": user.last_name, "company_name": user.company_name,
            "vat_number": user.vat_number, "siret_number": user.siret_number,
            "professional_status": user.professional_status,
            "is_verified": user.is_verified, "is_active": user.is_active,
            "created_at": format_datetime_for_display(user.created_at)
        }
        audit_logger.log_action(user_id=user_id, action='pro_get_profile_success', status='success', ip_address=ip_address)
        return jsonify(profile=profile_data, success=True), 200

    if request.method == 'PUT':
        data = request.json
        # Allow professionals to update certain fields, e.g., contact info, company details
        # Password changes should go through a separate, dedicated endpoint.
        allowed_to_update = ['first_name', 'last_name', 'company_name', 'vat_number', 'siret_number']
        updated_fields = []
        for field in allowed_to_update:
            if field in data and data[field] != getattr(user, field):
                setattr(user, field, data[field])
                updated_fields.append(field)
        
        if not updated_fields:
            return jsonify(message="No changes detected or no updatable fields provided.", success=False), 400

        user.updated_at = datetime.now(timezone.utc)
        try:
            db.session.commit()
            audit_logger.log_action(user_id=user_id, action='pro_update_profile_success', details=f"Fields updated: {', '.join(updated_fields)}", status='success', ip_address=ip_address)
            return jsonify(message="Profile updated successfully.", success=True), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating B2B profile for user {user_id}: {e}", exc_info=True)
            audit_logger.log_action(user_id=user_id, action='pro_update_profile_fail_exception', details=str(e), status='failure', ip_address=ip_address)
            return jsonify(message="Failed to update profile.", success=False), 500

@professional_bp.route('/invoices', methods=['GET'])
@jwt_required()
def get_my_professional_invoices():
    user_id = get_jwt_identity()
    claims = get_jwt()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    if claims.get('role') != 'b2b_professional':
        audit_logger.log_action(user_id=user_id, action='get_my_invoices_fail_unauthorized', details="User is not a B2B professional.", status='failure', ip_address=ip_address)
        return jsonify(message="Access restricted to B2B professionals.", success=False), 403

    try:
        # Fetch invoices linked via b2b_user_id (manual) OR via order_id where order's user_id matches
        invoices = Invoice.query.filter(
            or_(
                Invoice.b2b_user_id == user_id,
                Invoice.order.has(Order.user_id == user_id) # Assuming 'order' is the relationship from Invoice to Order
            )
        ).order_by(Invoice.issue_date.desc()).all()
        
        invoices_list = []
        if invoices:
            for inv_model in invoices:
                invoice_dict = {
                    "id": inv_model.id, "invoice_number": inv_model.invoice_number,
                    "issue_date": format_datetime_for_display(inv_model.issue_date),
                    "due_date": format_datetime_for_display(inv_model.due_date) if inv_model.due_date else None,
                    "total_amount": inv_model.total_amount, "currency": inv_model.currency,
                    "status": inv_model.status, 
                    "pdf_download_url": None
                }
                if inv_model.pdf_path:
                    try:
                        # Serve via admin assets as invoices might be sensitive
                        pdf_relative_to_asset_serve = os.path.join('invoices', os.path.basename(inv_model.pdf_path))
                        # Use admin_api_bp for serving admin/protected assets, or orders_bp if that's where download is
                        # For consistency and protection, admin_api_bp.serve_asset is usually better for invoices.
                        # However, the original code pointed to orders_bp.download_invoice.
                        # Sticking to the original logic for now, assuming orders_bp.download_invoice handles auth.
                        invoice_dict['pdf_download_url'] = url_for('orders_bp.download_invoice', invoice_id=inv_model.id, _external=True)
                    except Exception as e_url:
                        current_app.logger.warning(f"Could not generate download URL for B2B invoice PDF {inv_model.pdf_path}: {e_url}")
                invoices_list.append(invoice_dict)
        
        audit_logger.log_action(user_id=user_id, action='get_my_invoices_success', details=f"Fetched {len(invoices_list)} invoices.", status='success', ip_address=ip_address)
        return jsonify(invoices=invoices_list, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching B2B invoices for user {user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=user_id, action='get_my_invoices_fail_exception', details=str(e), status='failure', ip_address=ip_address)
        return jsonify(message="Failed to fetch your invoices.", success=False), 500

@professional_bp.route('/applications', methods=['GET'])
@staff_or_admin_required # Only staff or admin can view applications
def get_professional_applications():
    audit_logger = current_app.audit_log_service
    current_staff_id = get_jwt_identity()
    ip_address = request.remote_addr
    status_filter = request.args.get('status', 'pending') # Default to 'pending'

    try:
        query = User.query.filter_by(role='b2b_professional')
        if status_filter and status_filter.lower() != 'all':
            query = query.filter(func.lower(User.professional_status) == status_filter.lower())
        
        users_models = query.order_by(User.created_at.desc()).all()
        applications = []
        for user_model in users_models:
            # Include relevant documents for review
            docs_data = [{
                "id": doc.id, "document_type": doc.document_type, "file_path": doc.file_path,
                "upload_date": format_datetime_for_display(doc.upload_date),
                "status": doc.status,
                "download_url": url_for('admin_api_bp.serve_asset', asset_relative_path=doc.file_path, _external=True) if doc.file_path else None
            } for doc in user_model.professional_documents]

            app_data = {
                "id": user_model.id, "email": user_model.email, "first_name": user_model.first_name,
                "last_name": user_model.last_name, "company_name": user_model.company_name,
                "vat_number": user_model.vat_number, "siret_number": user_model.siret_number,
                "professional_status": user_model.professional_status,
                "application_date": format_datetime_for_display(user_model.created_at),
                "documents": docs_data
            }
            applications.append(app_data)
        
        audit_logger.log_action(user_id=current_staff_id, action='admin_get_pro_applications_success', details=f"Fetched {len(applications)} B2B applications with status '{status_filter}'.", status='success', ip_address=ip_address)
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
    new_status = data.get('status') # Expect 'approved' or 'rejected'

    if not new_status or new_status not in ['approved', 'rejected']:
        return jsonify(message="Invalid status provided. Must be 'approved' or 'rejected'.", success=False), 400

    user = User.query.filter_by(id=application_user_id, role='b2b_professional').first()
    if not user:
        return jsonify(message="Professional application not found.", success=False), 404

    old_status = user.professional_status
    user.professional_status = new_status
    user.updated_at = datetime.now(timezone.utc)
    
    try:
        db.session.commit()
        # Placeholder: Send email notification to the user about status change
        # send_application_status_email(user.email, new_status, user.first_name)
        
        audit_logger.log_action(
            user_id=current_staff_id, action='admin_update_pro_app_status_success', 
            target_type='user_b2b_application', target_id=application_user_id, 
            details=f"B2B application for user {user.email} status changed from '{old_status}' to '{new_status}'.", 
            status='success', ip_address=ip_address
        )
        return jsonify(message=f"Application status updated to {new_status}.", success=True), 200
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
@jwt_required() # B2B user uploads their own documents
def upload_professional_document():
    user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    user = User.query.filter_by(id=user_id, role='b2b_professional').first()
    if not user:
        return jsonify(message="Professional account required to upload documents.", success=False), 403

    if 'document' not in request.files:
        return jsonify(message="No document file part in the request.", success=False), 400
    
    file = request.files['document']
    document_type = request.form.get('document_type')

    if file.filename == '':
        return jsonify(message="No selected file.", success=False), 400
    if not document_type:
        return jsonify(message="Document type is required.", success=False), 400
    
    allowed_doc_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'png', 'jpg', 'jpeg'})
    if file and allowed_file(file.filename, allowed_extensions_config_key='ALLOWED_EXTENSIONS'): # Use shared util
        filename_base = secure_filename(f"user_{user_id}_{document_type}_{uuid.uuid4().hex[:8]}")
        extension = get_file_extension(file.filename)
        filename = f"{filename_base}.{extension}"
        
        upload_folder = current_app.config['PROFESSIONAL_DOCS_UPLOAD_PATH']
        os.makedirs(upload_folder, exist_ok=True)
        file_path_full = os.path.join(upload_folder, filename)
        file_path_relative_for_db = os.path.join('professional_documents', filename) # Relative path for db storage

        try:
            file.save(file_path_full)
            
            new_doc = ProfessionalDocument(
                user_id=user_id,
                document_type=document_type,
                file_path=file_path_relative_for_db, # Store relative path
                status='pending_review'
            )
            db.session.add(new_doc)
            db.session.commit()
            
            audit_logger.log_action(user_id=user_id, action='pro_upload_doc_success', target_type='professional_document', target_id=new_doc.id, details=f"Document '{document_type}' uploaded: {filename}", status='success', ip_address=ip_address)
            return jsonify(message="Document uploaded successfully. It will be reviewed.", document_id=new_doc.id, file_path=new_doc.file_path, success=True), 201
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving professional document for user {user_id}: {e}", exc_info=True)
            audit_logger.log_action(user_id=user_id, action='pro_upload_doc_fail_exception', details=str(e), status='failure', ip_address=ip_address)
            # Clean up saved file if DB operation failed
            if os.path.exists(file_path_full):
                try: os.remove(file_path_full)
                except OSError: pass
            return jsonify(message="Failed to upload document due to a server error.", success=False), 500
    else:
        return jsonify(message="Invalid file type. Allowed types: PDF, PNG, JPG, JPEG.", success=False), 400

@professional_bp.route('/documents', methods=['GET'])
@jwt_required()
def get_my_professional_documents():
    user_id = get_jwt_identity()
    user = User.query.filter_by(id=user_id, role='b2b_professional').first()
    if not user: return jsonify(message="Professional account required.", success=False), 403

    try:
        documents = ProfessionalDocument.query.filter_by(user_id=user_id).order_by(ProfessionalDocument.upload_date.desc()).all()
        docs_data = [{
            "id": doc.id, "document_type": doc.document_type, 
            "upload_date": format_datetime_for_display(doc.upload_date),
            "status": doc.status, "notes": doc.notes,
            # Provide a download URL using the admin asset serving route
            "download_url": url_for('admin_api_bp.serve_asset', asset_relative_path=doc.file_path, _external=True) if doc.file_path else None
        } for doc in documents]
        return jsonify(documents=docs_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching documents for B2B user {user_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch documents.", success=False), 500
