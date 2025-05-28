import os
import sqlite3
import uuid
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
# from ..services.email_service import send_email # Uncomment when ready
# from ..services.invoice_service import generate_invoice_pdf # Assuming this would be the actual service
from ..database import get_db_connection, query_db
from ..utils import format_datetime_for_display

professional_bp = Blueprint('professional', __name__, url_prefix='/api/professional')

# Placeholder for a decorator that checks for admin or a specific "staff" role
# This would be similar to admin_required but might allow other roles.
def staff_or_admin_required(fn):
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        allowed_roles = ['admin', 'staff'] # Define roles that can access professional routes
        if claims.get('role') not in allowed_roles:
            return jsonify(message="Administration or staff rights required."), 403
        
        # Optional: Check if user is active
        # current_user_id = get_jwt_identity()
        # user = query_db("SELECT is_active FROM users WHERE id = ? AND role IN (?, ?)", 
        #                 [current_user_id] + allowed_roles, 
        #                 db_conn=get_db_connection(), one=True)
        # if not user or not user['is_active']:
        #     return jsonify(message="Account is not active."), 403
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


@professional_bp.route('/applications', methods=['GET'])
@staff_or_admin_required 
def get_professional_applications():
    db = get_db_connection()
    audit_logger = current_app.audit_log_service
    current_user_id = get_jwt_identity() # Admin/staff performing the action

    status_filter = request.args.get('status', 'pending') # Default to pending applications

    try:
        query = """
            SELECT id, email, first_name, last_name, company_name, vat_number, siret_number, 
                   professional_status, created_at, updated_at 
            FROM users 
            WHERE role = 'b2b_professional'
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
            # Fetch documents if any
            # docs_data = query_db("SELECT id, document_type, file_path, upload_date, status FROM professional_documents WHERE user_id = ?", [app_data['id']], db_conn=db)
            # app_data['documents'] = [dict(doc_row) for doc_row in docs_data] if docs_data else []

        return jsonify(applications), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching B2B applications: {e}")
        audit_logger.log_action(
            user_id=current_user_id,
            action='get_b2b_applications_fail',
            details=f"Failed to fetch B2B applications: {str(e)}",
            status='failure'
        )
        return jsonify(message="Failed to fetch B2B applications"), 500


@professional_bp.route('/applications/<int:user_id>/status', methods=['PUT'])
@staff_or_admin_required
def update_professional_application_status(user_id):
    data = request.json
    new_status = data.get('status') # 'approved', 'rejected'
    
    current_admin_id = get_jwt_identity() # Admin/staff performing the action
    audit_logger = current_app.audit_log_service

    if not new_status or new_status not in ['approved', 'rejected', 'pending']:
        audit_logger.log_action(
            user_id=current_admin_id,
            action='update_b2b_status_fail',
            target_type='user_b2b_application',
            target_id=user_id,
            details=f"Invalid status provided: {new_status}.",
            status='failure'
        )
        return jsonify(message="Invalid status. Must be 'approved', 'rejected', or 'pending'."), 400

    db = get_db_connection()
    try:
        user_to_update = query_db("SELECT id, email, first_name, professional_status FROM users WHERE id = ? AND role = 'b2b_professional'", [user_id], db_conn=db, one=True)
        if not user_to_update:
            audit_logger.log_action(
                user_id=current_admin_id,
                action='update_b2b_status_fail',
                target_type='user_b2b_application',
                target_id=user_id,
                details="B2B user application not found.",
                status='failure'
            )
            return jsonify(message="B2B user application not found."), 404

        old_status = user_to_update['professional_status']
        if old_status == new_status:
             return jsonify(message=f"B2B application status is already {new_status}."), 200


        cursor = db.cursor()
        cursor.execute(
            "UPDATE users SET professional_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_status, user_id)
        )
        db.commit()

        # Send notification email to the professional user
        user_email = user_to_update['email']
        user_first_name = user_to_update.get('first_name', 'Applicant')
        email_subject = f"Your Maison Trüvra Professional Account Application Status"
        email_body = f"<p>Dear {user_first_name},</p>"
        email_body += f"<p>The status of your professional account application has been updated to: <strong>{new_status.upper()}</strong>.</p>"
        if new_status == 'approved':
            email_body += "<p>You can now log in and access professional pricing and features.</p>"
        elif new_status == 'rejected':
            email_body += "<p>If you have questions, please contact our support team.</p>"
        email_body += "<p>Regards,<br/>The Maison Trüvra Team</p>"

        # try:
        #     send_email(to_email=user_email, subject=email_subject, body_html=email_body)
        #     audit_logger.log_action(user_id=current_admin_id, action='notify_user_b2b_status_update', target_type='user', target_id=user_id, details=f"Emailed {user_email} about status change to {new_status}.", status='success')
        # except Exception as e:
        #     current_app.logger.error(f"Failed to send B2B status update email to {user_email}: {e}")
        #     audit_logger.log_action(user_id=current_admin_id, action='notify_user_b2b_status_update_fail', target_type='user', target_id=user_id, details=f"Failed to email {user_email}: {str(e)}", status='failure')
        current_app.logger.info(f"Simulated sending B2B application status email to {user_email} (New Status: {new_status})")


        audit_logger.log_action(
            user_id=current_admin_id,
            action='update_b2b_status_success',
            target_type='user_b2b_application',
            target_id=user_id,
            details=f"B2B application for user {user_id} ({user_email}) status changed from '{old_status}' to '{new_status}'.",
            status='success'
        )
        return jsonify(message=f"B2B application status updated to {new_status}."), 200

    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating B2B application status for user {user_id}: {e}")
        audit_logger.log_action(
            user_id=current_admin_id,
            action='update_b2b_status_fail',
            target_type='user_b2b_application',
            target_id=user_id,
            details=f"Server error: {str(e)}",
            status='failure'
        )
        return jsonify(message="Failed to update B2B application status."), 500


@professional_bp.route('/invoices/generate', methods=['POST'])
@staff_or_admin_required
def generate_professional_invoice_pdf():
    data = request.json
    b2b_user_id = data.get('b2b_user_id')
    order_id = data.get('order_id') # Optional, if invoice is for a specific web order
    invoice_items_data = data.get('items', []) # List of dicts: {description, quantity, unit_price, total_price}
    notes = data.get('notes', '')
    # Other details like due_date, custom invoice number prefix can be added

    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not b2b_user_id or not invoice_items_data:
        audit_logger.log_action(user_id=current_admin_id, action='generate_b2b_invoice_fail', details="B2B User ID and items are required.", status='failure')
        return jsonify(message="B2B User ID and items are required to generate an invoice."), 400

    db = get_db_connection()
    try:
        # Verify B2B user exists and is approved
        b2b_user = query_db("SELECT id, email, company_name FROM users WHERE id = ? AND role = 'b2b_professional' AND professional_status = 'approved'", 
                            [b2b_user_id], db_conn=db, one=True)
        if not b2b_user:
            audit_logger.log_action(user_id=current_admin_id, action='generate_b2b_invoice_fail', target_type='user', target_id=b2b_user_id, details="B2B user not found or not approved.", status='failure')
            return jsonify(message="B2B user not found or not approved."), 404

        # Calculate total amount from items
        total_amount = sum(float(item.get('total_price', 0)) for item in invoice_items_data)
        if total_amount <= 0:
            audit_logger.log_action(user_id=current_admin_id, action='generate_b2b_invoice_fail', target_type='user', target_id=b2b_user_id, details="Invoice total amount must be positive.", status='failure')
            return jsonify(message="Invoice total amount must be positive based on items provided."), 400

        # Generate a unique invoice number (e.g., B2B-YYYYMMDD-XXXX)
        # This is a simplified example. A more robust system might use a sequence.
        invoice_number_prefix = current_app.config.get('B2B_INVOICE_PREFIX', 'B2BINV')
        timestamp_part = datetime.now().strftime('%Y%m%d%H%M')
        random_part = uuid.uuid4().hex[:4].upper()
        invoice_number = f"{invoice_number_prefix}-{timestamp_part}-{random_part}"
        
        # Determine due date (e.g., 30 days from issue date)
        issue_date = datetime.now()
        due_date = issue_date + timedelta(days=current_app.config.get('B2B_INVOICE_DUE_DAYS', 30))

        # Path for saving the PDF
        invoice_pdf_dir = current_app.config['INVOICE_PDF_PATH'] # Use correct config key
        os.makedirs(invoice_pdf_dir, exist_ok=True)
        pdf_filename = f"{invoice_number}.pdf"
        pdf_full_path = os.path.join(invoice_pdf_dir, pdf_filename)
        pdf_relative_path = os.path.join('invoices', pdf_filename) # Relative to ASSET_STORAGE_PATH

        # --- Actual PDF Generation Logic (Mocked) ---
        # This part needs to be implemented with a PDF library like ReportLab or WeasyPrint
        # from ..services.pdf_generation_service import create_professional_invoice_pdf 
        # pdf_generated = create_professional_invoice_pdf(
        #     invoice_number=invoice_number,
        #     issue_date=issue_date,
        #     due_date=due_date,
        #     b2b_user_info=dict(b2b_user), 
        #     items=invoice_items_data, 
        #     total_amount=total_amount,
        #     notes=notes,
        #     output_path=pdf_full_path,
        #     company_info=current_app.config['DEFAULT_COMPANY_INFO']
        # )
        # For now, simulate PDF creation:
        try:
            with open(pdf_full_path, 'w') as f:
                f.write(f"Mock PDF for Invoice: {invoice_number}\nUser: {b2b_user['company_name']}\nTotal: {total_amount} EUR")
            pdf_generated = True # Simulate success
            current_app.logger.info(f"Mock PDF generated at: {pdf_full_path}")
        except IOError as e:
            current_app.logger.error(f"Mock PDF generation error: {e}")
            pdf_generated = False
        # --- End Mock PDF Generation ---

        if not pdf_generated:
            audit_logger.log_action(user_id=current_admin_id, action='generate_b2b_invoice_fail_pdf', target_type='user', target_id=b2b_user_id, details="PDF generation failed.", status='failure')
            return jsonify(message="Invoice PDF generation failed."), 500

        cursor = db.cursor()
        # Insert into invoices table
        cursor.execute(
            """INSERT INTO invoices (b2b_user_id, order_id, invoice_number, issue_date, due_date, 
                                   total_amount, status, pdf_path, notes, currency)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (b2b_user_id, order_id, invoice_number, issue_date.isoformat(), due_date.isoformat(), 
             total_amount, 'issued', pdf_relative_path, notes, 'EUR')
        )
        invoice_id = cursor.lastrowid

        # Insert invoice items
        for item in invoice_items_data:
            cursor.execute(
                """INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price)
                   VALUES (?, ?, ?, ?, ?)""",
                (invoice_id, item.get('description'), item.get('quantity'), item.get('unit_price'), item.get('total_price'))
            )
        
        db.commit()
        audit_logger.log_action(
            user_id=current_admin_id,
            action='generate_b2b_invoice_success',
            target_type='invoice',
            target_id=invoice_id,
            details=f"Generated B2B invoice {invoice_number} for user {b2b_user_id}. PDF: {pdf_relative_path}",
            status='success'
        )
        return jsonify(message="B2B invoice generated successfully.", invoice_id=invoice_id, invoice_number=invoice_number, pdf_url=pdf_relative_path), 201

    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error generating B2B invoice for user {b2b_user_id}: {e}")
        audit_logger.log_action(
            user_id=current_admin_id,
            action='generate_b2b_invoice_fail',
            target_type='user',
            target_id=b2b_user_id if b2b_user_id else None,
            details=f"Server error: {str(e)}",
            status='failure'
        )
        return jsonify(message="Failed to generate B2B invoice."), 500

@professional_bp.route('/invoices', methods=['GET'])
@staff_or_admin_required
def get_professional_invoices():
    db = get_db_connection()
    audit_logger = current_app.audit_log_service
    current_user_id = get_jwt_identity()

    # Add filters like b2b_user_id, status, date range
    b2b_user_id_filter = request.args.get('b2b_user_id', type=int)
    status_filter = request.args.get('status')

    query_sql = """
        SELECT i.*, u.email as b2b_user_email, u.company_name as b2b_company_name
        FROM invoices i
        JOIN users u ON i.b2b_user_id = u.id 
        WHERE u.role = 'b2b_professional' 
    """ # Ensure we only fetch B2B invoices if this endpoint is specific
    params = []

    if b2b_user_id_filter:
        query_sql += " AND i.b2b_user_id = ?"
        params.append(b2b_user_id_filter)
    if status_filter:
        query_sql += " AND i.status = ?"
        params.append(status_filter)
    
    query_sql += " ORDER BY i.issue_date DESC"

    try:
        invoices_data = query_db(query_sql, params, db_conn=db)
        invoices = [dict(row) for row in invoices_data] if invoices_data else []
        for inv in invoices:
            inv['issue_date'] = format_datetime_for_display(inv['issue_date'])
            inv['due_date'] = format_datetime_for_display(inv['due_date'])
            if inv.get('pdf_path'):
                # URL to serve the PDF, likely via the admin asset route
                inv['pdf_full_url'] = f"{request.host_url.rstrip('/')}{current_app.blueprints['admin_api'].url_prefix}/assets/{inv['pdf_path']}"


        return jsonify(invoices), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching B2B invoices: {e}")
        audit_logger.log_action(user_id=current_user_id, action='get_b2b_invoices_fail', details=str(e), status='failure')
        return jsonify(message="Failed to fetch B2B invoices"), 500

# Add routes for updating invoice status (e.g., to 'paid', 'cancelled')