import os
import sqlite3
import uuid
from flask import Blueprint, request, jsonify, current_app, send_from_directory, url_for # Added url_for
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..database import get_db_connection, query_db
from ..utils import format_datetime_for_display, staff_or_admin_required, allowed_file, get_file_extension, format_datetime_for_storage
# from ..services.email_service import send_email # Uncomment when ready
from ..services.invoice_service import generate_invoice_pdf # Assuming this service is ready

professional_bp = Blueprint('professional_bp', __name__, url_prefix='/api/professional') # Keep prefix

@professional_bp.route('/applications', methods=['GET'])
@staff_or_admin_required 
def get_professional_applications():
    db = get_db_connection()
    audit_logger = current_app.audit_log_service
    current_staff_id = get_jwt_identity()

    status_filter = request.args.get('status', 'pending')

    try:
        query = """
            SELECT id, email, first_name, last_name, company_name, vat_number, siret_number, 
                   professional_status, created_at, updated_at 
            FROM users WHERE role = 'b2b_professional'
        """
        params = []
        if status_filter:
            query += " AND professional_status = ?"
            params.append(status_filter)
        query += " ORDER BY created_at DESC"

        users_data = query_db(query, params, db_conn=db)
        applications = [dict(row) for row in users_data] if users_data else []
        for app_data in applications:
            app_data['created_at'] = format_datetime_for_display(app_data['created_at'])
            app_data['updated_at'] = format_datetime_for_display(app_data['updated_at'])
            # Fetch documents if schema supports it well
            docs_data = query_db("SELECT id, document_type, file_path, upload_date, status FROM professional_documents WHERE user_id = ? ORDER BY upload_date DESC", [app_data['id']], db_conn=db)
            app_data['documents'] = []
            if docs_data:
                for doc_row in docs_data:
                    doc_dict = dict(doc_row)
                    doc_dict['upload_date'] = format_datetime_for_display(doc_dict['upload_date'])
                    if doc_dict.get('file_path'): # Generate URL to serve the document
                        doc_dict['file_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=doc_dict['file_path'], _external=True)
                    app_data['documents'].append(doc_dict)
        
        audit_logger.log_action(user_id=current_staff_id, action='get_b2b_applications', details=f"Filter: {status_filter}", status='success', ip_address=request.remote_addr)
        return jsonify(applications), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching B2B applications: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_staff_id, action='get_b2b_applications_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to fetch B2B applications"), 500

@professional_bp.route('/applications/<int:user_id>/status', methods=['PUT'])
@staff_or_admin_required
def update_professional_application_status(user_id):
    data = request.json
    new_status = data.get('status') # 'approved', 'rejected', 'pending'
    rejection_reason = data.get('rejection_reason', '') # Optional reason for rejection
    
    current_staff_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not new_status or new_status not in ['approved', 'rejected', 'pending']:
        audit_logger.log_action(user_id=current_staff_id, action='update_b2b_status_fail_invalid_status', target_type='user_b2b_application', target_id=user_id, details=f"Invalid status: {new_status}.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid status. Must be 'approved', 'rejected', or 'pending'."), 400

    db = get_db_connection()
    try:
        user_to_update = query_db("SELECT id, email, first_name, professional_status FROM users WHERE id = ? AND role = 'b2b_professional'", [user_id], db_conn=db, one=True)
        if not user_to_update:
            audit_logger.log_action(user_id=current_staff_id, action='update_b2b_status_fail_not_found', target_type='user_b2b_application', target_id=user_id, details="B2B app not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="B2B user application not found."), 404

        old_status = user_to_update['professional_status']
        if old_status == new_status:
             return jsonify(message=f"B2B application status is already {new_status}."), 200

        # Add notes for status change, especially rejection
        notes_update = f"Status changed from {old_status} to {new_status} by staff ID {current_staff_id}."
        if new_status == 'rejected' and rejection_reason:
            notes_update += f" Reason: {rejection_reason}"
        
        # This assumes a general 'notes' field on user or a dedicated B2B application notes field
        # For simplicity, we're just logging it for now. If storing, update users table.
        
        query_db("UPDATE users SET professional_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, user_id), db_conn=db, commit=True)

        user_email = user_to_update['email']
        user_first_name = user_to_update.get('first_name', 'Applicant')
        email_subject = f"Your Maison Trüvra Professional Account Status: {new_status.upper()}"
        email_body = f"<p>Dear {user_first_name},</p><p>The status of your professional account application is now: <strong>{new_status.upper()}</strong>.</p>"
        if new_status == 'approved': email_body += "<p>You can now log in and access professional features.</p>"
        elif new_status == 'rejected': email_body += f"<p>Reason: {rejection_reason if rejection_reason else 'Please contact support for more details.'}</p>"
        email_body += "<p>Regards,<br/>The Maison Trüvra Team</p>"

        # try:
        #     send_email(to_email=user_email, subject=email_subject, body_html=email_body)
        #     audit_logger.log_action(user_id=current_staff_id, action='notify_user_b2b_status_update', target_type='user', target_id=user_id, details=f"Emailed {user_email} (status: {new_status}).", status='success', ip_address=request.remote_addr)
        # except Exception as e_mail:
        #     current_app.logger.error(f"Failed to send B2B status update email to {user_email}: {e_mail}")
        #     audit_logger.log_action(user_id=current_staff_id, action='notify_user_b2b_status_update_fail', target_type='user', target_id=user_id, details=f"Email fail: {str(e_mail)}", status='failure', ip_address=request.remote_addr)
        current_app.logger.info(f"Simulated B2B status email to {user_email} (New Status: {new_status})")

        audit_logger.log_action(user_id=current_staff_id, action='update_b2b_status_success', target_type='user_b2b_application', target_id=user_id, details=f"B2B app for {user_email} status from '{old_status}' to '{new_status}'. Notes: {notes_update}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"B2B application status updated to {new_status}."), 200
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating B2B application status for user {user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_staff_id, action='update_b2b_status_fail_exception', target_type='user_b2b_application', target_id=user_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update B2B application status."), 500

@professional_bp.route('/invoices/generate', methods=['POST'])
@staff_or_admin_required
def generate_professional_invoice_pdf_route(): # Renamed to avoid conflict
    data = request.json
    b2b_user_id = data.get('b2b_user_id')
    order_id = data.get('order_id') 
    invoice_items_data = data.get('items', [])
    notes = data.get('notes', '')
    
    current_staff_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not b2b_user_id or not invoice_items_data:
        audit_logger.log_action(user_id=current_staff_id, action='generate_b2b_invoice_fail_missing_data', details="B2B User ID and items required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="B2B User ID and items are required."), 400

    db = get_db_connection()
    try:
        b2b_user = query_db("SELECT id, email, first_name, last_name, company_name, vat_number, siret_number, shipping_address_line1, shipping_city, shipping_postal_code, shipping_country FROM users WHERE id = ? AND role = 'b2b_professional' AND professional_status = 'approved'", [b2b_user_id], db_conn=db, one=True)
        if not b2b_user:
            audit_logger.log_action(user_id=current_staff_id, action='generate_b2b_invoice_fail_user_invalid', target_type='user', target_id=b2b_user_id, details="B2B user not found/approved.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="B2B user not found or not approved."), 404

        total_amount = sum(float(item.get('total_price', 0)) for item in invoice_items_data)
        if total_amount <= 0:
            audit_logger.log_action(user_id=current_staff_id, action='generate_b2b_invoice_fail_zero_total', target_type='user', target_id=b2b_user_id, details="Invoice total must be positive.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invoice total amount must be positive."), 400

        invoice_number_prefix = current_app.config.get('B2B_INVOICE_PREFIX', 'B2BINV')
        timestamp_part = datetime.now(timezone.utc).strftime('%Y%m%d%H%M')
        random_part = uuid.uuid4().hex[:4].upper()
        invoice_number = f"{invoice_number_prefix}-{timestamp_part}-{random_part}"
        
        issue_date = datetime.now(timezone.utc)
        due_date = issue_date + timedelta(days=current_app.config.get('B2B_INVOICE_DUE_DAYS', 30))

        customer_info_for_pdf = {
            "name": f"{b2b_user.get('first_name','')} {b2b_user.get('last_name','')} ({b2b_user.get('company_name', 'N/A')})".strip(),
            "company_name": b2b_user.get('company_name'),
            "email": b2b_user.get('email'),
            "address_line1": b2b_user.get('shipping_address_line1'), # Assuming B2B users have address info
            "city_postal_country": f"{b2b_user.get('shipping_city','')} {b2b_user.get('shipping_postal_code','')} {b2b_user.get('shipping_country','')}".strip(),
            "vat_number": b2b_user.get('vat_number')
        }
        
        # Actual PDF generation
        pdf_relative_path = generate_invoice_pdf(
            invoice_id=None, # Will be set after DB insert
            invoice_number=invoice_number, issue_date=issue_date, due_date=due_date,
            customer_info=customer_info_for_pdf, items=invoice_items_data, total_amount=total_amount,
            notes=notes, currency='EUR' # Assuming EUR
        )

        if not pdf_relative_path:
            audit_logger.log_action(user_id=current_staff_id, action='generate_b2b_invoice_fail_pdf_gen', target_type='user', target_id=b2b_user_id, details="PDF generation failed.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invoice PDF generation failed."), 500

        invoice_id_db = query_db(
            """INSERT INTO invoices (b2b_user_id, order_id, invoice_number, issue_date, due_date, 
                                   total_amount, status, pdf_path, notes, currency)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (b2b_user_id, order_id, invoice_number, format_datetime_for_storage(issue_date), format_datetime_for_storage(due_date), 
             total_amount, 'issued', pdf_relative_path, notes, 'EUR'), db_conn=db, commit=True
        )
        
        for item in invoice_items_data:
            query_db(
                """INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price, product_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (invoice_id_db, item.get('description'), item.get('quantity'), item.get('unit_price'), item.get('total_price'), item.get('product_id')), db_conn=db, commit=True # Commit each item or all at end
            )
        
        audit_logger.log_action(user_id=current_staff_id, action='generate_b2b_invoice_success', target_type='invoice', target_id=invoice_id_db, details=f"Generated B2B invoice {invoice_number}. PDF: {pdf_relative_path}", status='success', ip_address=request.remote_addr)
        
        pdf_full_url = url_for('admin_api_bp.serve_asset', asset_relative_path=pdf_relative_path, _external=True) if pdf_relative_path else None
        return jsonify(message="B2B invoice generated successfully.", invoice_id=invoice_id_db, invoice_number=invoice_number, pdf_url=pdf_full_url), 201

    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error generating B2B invoice for user {b2b_user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_staff_id, action='generate_b2b_invoice_fail_exception', target_type='user', target_id=b2b_user_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to generate B2B invoice."), 500

@professional_bp.route('/invoices', methods=['GET'])
@staff_or_admin_required
def get_professional_invoices():
    db = get_db_connection()
    audit_logger = current_app.audit_log_service
    current_staff_id = get_jwt_identity()

    b2b_user_id_filter = request.args.get('b2b_user_id', type=int)
    status_filter = request.args.get('status')

    query_sql = """
        SELECT i.*, u.email as b2b_user_email, u.company_name as b2b_company_name
        FROM invoices i JOIN users u ON i.b2b_user_id = u.id WHERE u.role = 'b2b_professional' 
    """
    params = []
    if b2b_user_id_filter: query_sql += " AND i.b2b_user_id = ?"; params.append(b2b_user_id_filter)
    if status_filter: query_sql += " AND i.status = ?"; params.append(status_filter)
    query_sql += " ORDER BY i.issue_date DESC"

    try:
        invoices_data = query_db(query_sql, params, db_conn=db)
        invoices = [dict(row) for row in invoices_data] if invoices_data else []
        for inv in invoices:
            inv['issue_date'] = format_datetime_for_display(inv['issue_date'])
            inv['due_date'] = format_datetime_for_display(inv['due_date'])
            if inv.get('pdf_path'):
                inv['pdf_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=inv['pdf_path'], _external=True)
        return jsonify(invoices), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching B2B invoices: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_staff_id, action='get_b2b_invoices_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to fetch B2B invoices"), 500

# Add routes for updating invoice status (e.g., to 'paid', 'cancelled')
@professional_bp.route('/invoices/<int:invoice_id>/status', methods=['PUT'])
@staff_or_admin_required
def update_invoice_status(invoice_id):
    data = request.json
    new_status = data.get('status')
    
    current_staff_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    allowed_statuses = ['draft', 'issued', 'paid', 'overdue', 'cancelled', 'void']
    if not new_status or new_status not in allowed_statuses:
        audit_logger.log_action(user_id=current_staff_id, action='update_invoice_status_fail_invalid', target_type='invoice', target_id=invoice_id, details=f"Invalid status: {new_status}.", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Invalid status. Allowed: {', '.join(allowed_statuses)}"), 400

    db = get_db_connection()
    try:
        invoice = query_db("SELECT id, status FROM invoices WHERE id = ?", [invoice_id], db_conn=db, one=True)
        if not invoice:
            audit_logger.log_action(user_id=current_staff_id, action='update_invoice_status_fail_not_found', target_type='invoice', target_id=invoice_id, details="Invoice not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invoice not found."), 404

        old_status = invoice['status']
        query_db("UPDATE invoices SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, invoice_id), db_conn=db, commit=True)
        
        audit_logger.log_action(user_id=current_staff_id, action='update_invoice_status_success', target_type='invoice', target_id=invoice_id, details=f"Invoice {invoice_id} status from '{old_status}' to '{new_status}'.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Invoice status updated to {new_status}."), 200
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating invoice {invoice_id} status: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_staff_id, action='update_invoice_status_fail_exception', target_type='invoice', target_id=invoice_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update invoice status."), 500
