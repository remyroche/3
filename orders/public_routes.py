# backend/orders/public_routes.py
# Contains routes accessible by any authenticated user for their own orders,
# such as viewing history or downloading their own invoices.

from flask import request, jsonify, current_app, url_for, send_from_directory, abort as flask_abort
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import os

from .. import db
from ..models import Order, User, UserRoleEnum, Invoice
from ..utils import format_datetime_for_display
from . import orders_bp

@orders_bp.route('/history', methods=['GET'])
@jwt_required()
def get_order_history():
    """
    Fetches the order history for the currently authenticated user.
    Differentiates between B2B and B2C orders based on the user's role.
    """
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        user = User.query.get(current_user_id)
        if not user:
            return jsonify(message="User not found.", success=False), 404

        query = Order.query.filter_by(user_id=current_user_id)
        
        # Filter orders based on the user's role
        if user.role == UserRoleEnum.B2B_PROFESSIONAL:
            query = query.filter_by(is_b2b_order=True)
        else:
            query = query.filter(Order.is_b2b_order == False)

        orders_models = query.order_by(Order.order_date.desc()).all()
        
        orders_data = [{
            'id': o_model.id,
            'order_date': format_datetime_for_display(o_model.order_date),
            'status': o_model.status.value if o_model.status else None,
            'total_amount': o_model.total_amount,
            'currency': o_model.currency,
            'invoice_number': o_model.invoice.invoice_number if o_model.invoice else None
        } for o_model in orders_models]
        
        audit_logger.log_action(user_id=current_user_id, action='get_order_history_success', status='success', ip_address=request.remote_addr)
        return jsonify(orders=orders_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching order history for user {current_user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='get_order_history_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Server error while fetching order history.", success=False), 500


@orders_bp.route('/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order_details_public(order_id):
    """
    Fetches the details of a specific order for the currently authenticated user.
    Ensures users can only access their own orders.
    """
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        order_model = Order.query.filter_by(id=order_id, user_id=current_user_id).first()
        if not order_model:
            audit_logger.log_action(user_id=current_user_id, action='get_order_detail_fail_auth', target_type='order', target_id=order_id, status='failure', ip_address=request.remote_addr)
            return jsonify(message="Order not found or access denied.", success=False), 404
            
        order_details = order_model.to_dict()
        
        audit_logger.log_action(user_id=current_user_id, action='get_order_detail_public_success', target_type='order', target_id=order_id, status='success', ip_address=request.remote_addr)
        return jsonify(order=order_details, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching public order details for order {order_id}, user {current_user_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch order details.", success=False), 500


@orders_bp.route('/invoices/download/<int:invoice_id>', methods=['GET'])
@jwt_required()
def download_invoice(invoice_id):
    """
    Allows an authenticated user to download an invoice PDF file they have access to.
    Access is granted if they are an admin, the B2B user on the invoice, or the owner of the associated B2C order.
    """
    user_id = get_jwt_identity()
    claims = get_jwt()
    is_admin = claims.get('is_admin', False)

    invoice = db.session.get(Invoice, invoice_id)
    if not invoice: flask_abort(404, description="Invoice not found.")

    is_b2b_owner = invoice.b2b_user_id and invoice.b2b_user_id == user_id
    is_order_owner = invoice.order and invoice.order.user_id == user_id
    
    if not (is_admin or is_b2b_owner or is_order_owner):
         flask_abort(403, description="You do not have permission to access this invoice.")

    if not invoice.pdf_path:
        current_app.logger.error(f"Invoice PDF path missing for invoice ID {invoice_id}")
        flask_abort(404, description="Invoice file path not found on server.")

    asset_storage_directory = current_app.config['ASSET_STORAGE_PATH']
    
    # Security Check
    if ".." in invoice.pdf_path or invoice.pdf_path.startswith("/"):
        current_app.logger.error(f"Invalid PDF path for invoice {invoice_id}: {invoice.pdf_path}")
        flask_abort(400, description="Invalid invoice file path.")

    # Second security check to ensure the path doesn't escape the intended directory
    full_file_path = os.path.normpath(os.path.join(asset_storage_directory, invoice.pdf_path))
    if not full_file_path.startswith(os.path.normpath(asset_storage_directory) + os.sep):
        current_app.logger.error(f"Security violation on invoice download: Attempt to access {full_file_path}")
        flask_abort(404)

    if not os.path.exists(full_file_path) or not os.path.isfile(full_file_path):
        current_app.logger.error(f"Invoice PDF file not found at: {full_file_path}")
        flask_abort(404, description="Invoice file not found.")

    try:
        current_app.audit_log_service.log_action(user_id=user_id, action='download_invoice', target_type='invoice', target_id=invoice_id, status='success', ip_address=request.remote_addr)
        return send_from_directory(asset_storage_directory, invoice.pdf_path, as_attachment=True)
    except Exception as e:
        current_app.logger.error(f"Error sending invoice file {invoice.pdf_path}: {e}", exc_info=True)
        flask_abort(500, description="Error serving invoice file.")
