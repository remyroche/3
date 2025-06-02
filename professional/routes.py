import os
import uuid
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, current_app, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..database import get_db_connection, query_db
from ..utils import (
    format_datetime_for_display, 
    staff_or_admin_required, 
    format_datetime_for_storage
)
from ..services.invoice_service import InvoiceService # Import InvoiceService

professional_bp = Blueprint('professional_bp', __name__, url_prefix='/api/professional')

@professional_bp.route('/invoices', methods=['GET'])
@jwt_required() 
def get_my_professional_invoices():
    """
    Fetches all invoices for the currently logged-in B2B professional user.
    """
    user_id = get_jwt_identity()
    claims = get_jwt()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    if claims.get('role') != 'b2b_professional':
        audit_logger.log_action(user_id=user_id, action='get_my_invoices_fail_unauthorized', details="User is not a B2B professional.", status='failure', ip_address=ip_address)
        return jsonify(message="Access restricted to B2B professionals."), 403

    db = get_db_connection()
    try:
        invoices_data = query_db(
            "SELECT id, invoice_number, issue_date, due_date, total_amount, currency, status, pdf_path FROM invoices WHERE b2b_user_id = ? ORDER BY issue_date DESC",
            [user_id],
            db_conn=db
        )
        invoices_list = []
        if invoices_data:
            for row in invoices_data:
                invoice_dict = dict(row)
                invoice_dict['issue_date'] = format_datetime_for_display(invoice_dict['issue_date'])
                invoice_dict['due_date'] = format_datetime_for_display(invoice_dict['due_date'])
                if invoice_dict.get('pdf_path'):
                    try:
                        invoice_dict['pdf_download_url'] = url_for('orders_bp.download_invoice', invoice_id=invoice_dict['id'], _external=True)
                    except Exception as e_url:
                        current_app.logger.warning(f"Could not generate download URL for B2B invoice PDF {invoice_dict['pdf_path']}: {e_url}")
                        invoice_dict['pdf_download_url'] = None
                invoices_list.append(invoice_dict)
        
        audit_logger.log_action(user_id=user_id, action='get_my_invoices_success', details=f"Fetched {len(invoices_list)} invoices.", status='success', ip_address=ip_address)
        return jsonify(invoices=invoices_list, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching B2B invoices for user {user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=user_id, action='get_my_invoices_fail_exception', details=str(e), status='failure', ip_address=ip_address)
        return jsonify(message="Failed to fetch your invoices.", success=False), 500


@professional_bp.route('/applications', methods=['GET'])
@staff_or_admin_required 
def get_professional_applications():
    """
    STAFF/ADMIN Route: Fetches B2B professional applications based on status.
    """
    db = get_db_connection()
    audit_logger = current_app.audit_log_service
    current_staff_id = get_jwt_identity()
    ip_address = request.remote_addr

    status_filter = request.args.get('status', 'pending') 

    try:
        query_sql = """
            SELECT id, email, first_name, last_name, company_name, vat_number, siret_number, 
                   professional_status, created_at, updated_at 
            FROM users WHERE role = 'b2b_professional'
        """
        params = []
        if status_filter and status_filter != 'all': 
            query_sql += " AND professional_status = ?"
            params.append(status_filter)
        query_sql += " ORDER BY created_at DESC"

        users_data = query_db(query_sql, params, db_conn=db)
        applications = [dict(row) for row in users_data] if users_data else []
        
        for app_data in applications:
            app_data['created_at'] = format_datetime_for_display(app_data['created_at'])
            app_data['updated_at'] = format_datetime_for_display(app_data['updated_at'])
            
            docs_data = query_db("SELECT id, document_type, file_path, upload_date, status FROM professional_documents WHERE user_id = ? ORDER BY upload_date DESC", [app_data['id']], db_conn=db)
            app_data['documents'] = []
            if docs_data:
                for doc_row in docs_data:
                    doc_dict = dict(doc_row)
                    doc_dict['upload_date'] = format_datetime_for_display(doc_dict['upload_date'])
                    if doc_dict.get('file_path'): 
                        try:
                            doc_dict['file_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=doc_dict['file_path'], _external=True)
                        except Exception as e_url:
                            current_app.logger.warning(f"Could not generate URL for professional document {doc_dict['file_path']}: {e_url}")
                            doc_dict['file_full_url'] = None
                    app_data['documents'].append(doc_dict)
        
        audit_logger.log_action(user_id=current_staff_id, action='get_b2b_applications', details=f"Filter: {status_filter}", status='success', ip_address=ip_address)
        return jsonify(applications=applications, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching B2B applications: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_staff_id, action='get_b2b_applications_fail', details=str(e), status='failure', ip_address=ip_address)
        return jsonify(message="Failed to fetch B2B applications", success=False), 500

@professional_bp.route('/applications/<int:user_id>/status', methods=['PUT'])
@staff_or_admin_required
def update_professional_application_status(user_id):
    """
    STAFF/ADMIN Route: Updates the status of a B2B professional application.
    """
    data = request.json
    new_status = data.get('status') 
    rejection_reason = data.get('rejection_reason', '') 
    
    current_staff_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    if not new_status or new_status not in ['approved', 'rejected', 'pending']:
        return jsonify(message="Invalid status. Must be 'approved', 'rejected', or 'pending'.", success=False), 400

    db = get_db_connection()
    cursor = db.cursor()
    try:
        user_to_update_row = query_db("SELECT id, email, first_name, professional_status FROM users WHERE id = ? AND role = 'b2b_professional'", [user_id], db_conn=db, one=True)
        if not user_to_update_row:
            return jsonify(message="B2B user application not found.", success=False), 404
        
        user_to_update = dict(user_to_update_row)
        old_status = user_to_update['professional_status']
        if old_status == new_status:
             return jsonify(message=f"B2B application status is already {new_status}.", success=True), 200
        
        notes_update = f"Status changed from {old_status} to {new_status} by staff ID {current_staff_id}."
        if new_status == 'rejected' and rejection_reason:
            notes_update += f" Reason: {rejection_reason}"
        
        cursor.execute("UPDATE users SET professional_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, user_id))
        
        current_app.logger.info(f"Simulated B2B status update email to {user_to_update['email']} (New Status: {new_status})")

        db.commit()
        audit_logger.log_action(user_id=current_staff_id, action='update_b2b_status_success', target_type='user_b2b_application', target_id=user_id, details=f"B2B app for {user_to_update['email']} status from '{old_status}' to '{new_status}'. Notes: {notes_update}", status='success', ip_address=ip_address)
        return jsonify(message=f"B2B application status updated to {new_status}.", success=True), 200
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating B2B application status for user {user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_staff_id, action='update_b2b_status_fail_exception', target_type='user_b2b_application', target_id=user_id, details=str(e), status='failure', ip_address=ip_address)
        return jsonify(message="Failed to update B2B application status.", success=False), 500


@professional_bp.route('/invoices/generate', methods=['POST'])
@staff_or_admin_required
def generate_professional_invoice_pdf_route():
    """
    STAFF/ADMIN Route: Generates a manual invoice for a B2B professional user.
    This route now uses the InvoiceService.
    """
    data = request.json
    b2b_user_id = data.get('b2b_user_id')
    # order_id = data.get('order_id') # This was present but not used if it's a manual invoice not tied to an order
    invoice_items_data = data.get('items', [])
    notes = data.get('notes', '')
    currency = data.get('currency', 'EUR') # Assume EUR if not provided, or fetch from user profile
    
    current_staff_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    if not b2b_user_id or not invoice_items_data:
        audit_logger.log_action(user_id=current_staff_id, action='generate_b2b_invoice_fail_missing_data', details="B2B User ID and items required.", status='failure', ip_address=ip_address)
        return jsonify(message="B2B User ID and items are required."), 400

    # Validate line items structure
    for item_data in invoice_items_data:
        if not all(k in item_data for k in ('description', 'quantity', 'unit_price')):
            audit_logger.log_action(user_id=current_staff_id, action='generate_b2b_invoice_fail_invalid_item', target_type='user', target_id=b2b_user_id, details="Invalid line item structure.", status='failure', ip_address=ip_address)
            return jsonify(message="Each line item must have description, quantity, and unit_price."), 400
        try:
            int(item_data['quantity'])
            float(item_data['unit_price'])
        except ValueError:
            audit_logger.log_action(user_id=current_staff_id, action='generate_b2b_invoice_fail_invalid_item_type', target_type='user', target_id=b2b_user_id, details="Invalid quantity or unit_price type.", status='failure', ip_address=ip_address)
            return jsonify(message="Invalid quantity or unit_price in line items. Must be numbers."), 400


    try:
        invoice_service = InvoiceService()
        invoice_id, invoice_number = invoice_service.create_manual_invoice(
            b2b_user_id=b2b_user_id,
            user_currency=currency, # Pass currency
            line_items_data=invoice_items_data,
            notes=notes
        )
        
        pdf_full_url = None
        if invoice_id: # If invoice was created, try to get its PDF path
            db_conn = get_db_connection()
            invoice_details = query_db("SELECT pdf_path FROM invoices WHERE id = ?", [invoice_id], db_conn=db_conn, one=True)
            if invoice_details and invoice_details['pdf_path']:
                try:
                    # Admin-generated invoices are served via admin asset route
                    pdf_full_url = url_for('admin_api_bp.serve_asset', asset_relative_path=invoice_details['pdf_path'], _external=True)
                except Exception as e_url_inv:
                    current_app.logger.warning(f"Could not generate URL for B2B invoice PDF {invoice_details['pdf_path']}: {e_url_inv}")

        audit_logger.log_action(user_id=current_staff_id, action='generate_b2b_invoice_success', target_type='invoice', target_id=invoice_id, details=f"Generated B2B invoice {invoice_number}. PDF URL: {pdf_full_url}", status='success', ip_address=ip_address)
        return jsonify(message="B2B invoice generated successfully.", invoice_id=invoice_id, invoice_number=invoice_number, pdf_url=pdf_full_url, success=True), 201

    except ValueError as ve:
        current_app.logger.warning(f"Validation error generating B2B invoice for user {b2b_user_id}: {ve}")
        audit_logger.log_action(user_id=current_staff_id, action='generate_b2b_invoice_fail_validation', target_type='user', target_id=b2b_user_id, details=str(ve), status='failure', ip_address=ip_address)
        return jsonify(message=str(ve), success=False), 400
    except Exception as e:
        current_app.logger.error(f"Error generating B2B invoice for user {b2b_user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_staff_id, action='generate_b2b_invoice_fail_exception', target_type='user', target_id=b2b_user_id, details=str(e), status='failure', ip_address=ip_address)
        return jsonify(message="Failed to generate B2B invoice.", success=False), 500

# This route seems redundant if /api/admin/invoices is used for admin listing.
# If this is for B2B users to see *their own* invoices, it's correctly placed but was already defined above.
# I'll assume the first /invoices GET route is for the B2B user themselves.
# The one below is for admins to get *all* professional invoices, which should be in admin_api_bp.
# For clarity, I'll comment out this potentially redundant admin-facing route here.
# If it's needed, it should be moved to admin_api_bp and use @admin_required.

# @professional_bp.route('/invoices', methods=['GET'])
# @staff_or_admin_required # Changed from admin_required to staff_or_admin_required
# def get_professional_invoices(): # Renamed to avoid conflict
#     db = get_db_connection()
#     audit_logger = current_app.audit_log_service
#     current_staff_id = get_jwt_identity()

#     b2b_user_id_filter = request.args.get('b2b_user_id', type=int)
#     status_filter = request.args.get('status')

#     query_sql = """
#         SELECT i.id, i.invoice_number, i.issue_date, i.due_date, i.total_amount, i.status, i.pdf_path,
#                u.email as b2b_user_email, u.company_name as b2b_company_name
#         FROM invoices i JOIN users u ON i.b2b_user_id = u.id WHERE u.role = 'b2b_professional' 
#     """
#     params = []
#     if b2b_user_id_filter: query_sql += " AND i.b2b_user_id = ?"; params.append(b2b_user_id_filter)
#     if status_filter: query_sql += " AND i.status = ?"; params.append(status_filter)
#     query_sql += " ORDER BY i.issue_date DESC"

#     try:
#         invoices_data = query_db(query_sql, params, db_conn=db)
#         invoices = [dict(row) for row in invoices_data] if invoices_data else []
#         for inv in invoices:
#             inv['issue_date'] = format_datetime_for_display(inv['issue_date'])
#             inv['due_date'] = format_datetime_for_display(inv['due_date'])
#             if inv.get('pdf_path'):
#                 try:
#                     inv['pdf_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=inv['pdf_path'], _external=True)
#                 except Exception as e_url_list:
#                     current_app.logger.warning(f"Could not generate URL for invoice PDF {inv['pdf_path']} in list: {e_url_list}")
#                     inv['pdf_full_url'] = None
#         return jsonify(invoices=invoices, success=True), 200
#     except Exception as e:
#         current_app.logger.error(f"Error fetching B2B invoices: {e}", exc_info=True)
#         audit_logger.log_action(user_id=current_staff_id, action='get_b2b_invoices_fail', details=str(e), status='failure', ip_address=request.remote_addr)
#         return jsonify(message="Failed to fetch B2B invoices", success=False), 500

@professional_bp.route('/invoices/<int:invoice_id>/status', methods=['PUT'])
@staff_or_admin_required # Changed from admin_required
def update_invoice_status(invoice_id):
    data = request.json
    new_status = data.get('status')
    
    current_staff_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    ip_address = request.remote_addr

    allowed_statuses = ['draft', 'issued', 'paid', 'overdue', 'cancelled', 'voided', 'sent', 'partially_paid']
    if not new_status or new_status not in allowed_statuses:
        audit_logger.log_action(user_id=current_staff_id, action='update_invoice_status_fail_invalid', target_type='invoice', target_id=invoice_id, details=f"Invalid status: {new_status}.", status='failure', ip_address=ip_address)
        return jsonify(message=f"Invalid status. Allowed: {', '.join(allowed_statuses)}"), 400

    db = get_db_connection()
    cursor = db.cursor()
    try:
        invoice_row = query_db("SELECT id, status, b2b_user_id FROM invoices WHERE id = ?", [invoice_id], db_conn=db, one=True)
        if not invoice_row:
            audit_logger.log_action(user_id=current_staff_id, action='update_invoice_status_fail_not_found', target_type='invoice', target_id=invoice_id, details="Invoice not found.", status='failure', ip_address=ip_address)
            return jsonify(message="Invoice not found."), 404
        
        invoice = dict(invoice_row)
        # Ensure the invoice belongs to a B2B user if that's a constraint for this blueprint
        if not invoice.get('b2b_user_id'):
            audit_logger.log_action(user_id=current_staff_id, action='update_invoice_status_fail_not_b2b', target_type='invoice', target_id=invoice_id, details="Attempt to update non-B2B invoice via professional route.", status='failure', ip_address=ip_address)
            return jsonify(message="This invoice does not appear to be a B2B professional invoice."), 400

        old_status = invoice['status']
        cursor.execute("UPDATE invoices SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, invoice_id))
        db.commit()
        
        audit_logger.log_action(user_id=current_staff_id, action='update_invoice_status_success', target_type='invoice', target_id=invoice_id, details=f"Invoice {invoice_id} status from '{old_status}' to '{new_status}'.", status='success', ip_address=ip_address)
        return jsonify(message=f"Invoice status updated to {new_status}.", success=True), 200
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating invoice {invoice_id} status: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_staff_id, action='update_invoice_status_fail_exception', target_type='invoice', target_id=invoice_id, details=str(e), status='failure', ip_address=ip_address)
        return jsonify(message="Failed to update invoice status.", success=False), 500
