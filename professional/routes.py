import os
import uuid
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, current_app, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..database import get_db_connection, query_db
from ..utils import (# backend/professional/routes.py
import os
from flask import Blueprint, request, jsonify, current_app, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from .. import db
from ..models import User, Invoice, ProfessionalDocument # Assuming Invoice model exists
from ..utils import format_datetime_for_display, staff_or_admin_required
from ..services.invoice_service import InvoiceService # Ensure this service uses SQLAlchemy

professional_bp = Blueprint('professional_bp', __name__, url_prefix='/api/professional')

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
        invoices = Invoice.query.filter_by(b2b_user_id=user_id).order_by(Invoice.issue_date.desc()).all()
        invoices_list = []
        if invoices:
            for inv_model in invoices:
                invoice_dict = {
                    "id": inv_model.id, "invoice_number": inv_model.invoice_number,
                    "issue_date": format_datetime_for_display(inv_model.issue_date),
                    "due_date": format_datetime_for_display(inv_model.due_date),
                    "total_amount": inv_model.total_amount, "currency": inv_model.currency,
                    "status": inv_model.status, "pdf_path": inv_model.pdf_path,
                    "pdf_download_url": None
                }
                if inv_model.pdf_path:
                    try:
                        # Assuming 'orders_bp.download_invoice' is the correct endpoint for downloading
                        # This might need to be 'admin_api_bp.serve_asset' if invoices are served that way
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
@staff_or_admin_required
def get_professional_applications():
    audit_logger = current_app.audit_log_service
    current_staff_id = get_jwt_identity()
    ip_address = request.remote_addr
    status_filter = request.args.get('status', 'pending')

    try:
        query = User.query.filter_by(role='b2b_professional')
        if status_filter and status_filter != 'all':
            query = query.filter_by(professional_status=status_filter)
        
        users_models = query.order_by(User.created_at.desc()).all()
        applications = []
        for user_model in users_models:
            app_data = {
                "id": user_model.id, "email": user_model.email, "first_name": user_model.first_name,
                "last_name": user_model.last_name, "company_name": user_model.company_name,
                "vat_number": user_model.vat_number, "siret_number": user_mod
