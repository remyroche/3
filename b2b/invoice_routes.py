from flask import Blueprint, render_template, jsonify, send_file
from flask_login import login_required, current_user
from models import B2BUser, B2BInvoice, Invoice
from services.b2b_invoice_service import get_invoice_html
from io import BytesIO
from flask_jwt_extended import jwt_required, get_jwt_identity
from . import b2b_bp


invoice_blueprint = Blueprint('b2b_invoice', __name__)

@b2b_bp.route('/invoices', methods=['GET'])
@jwt_required()
def get_b2b_invoices():
    user_id = get_jwt_identity()
    invoices = Invoice.query.filter_by(b2b_user_id=user_id).order_by(Invoice.issue_date.desc()).all()
    return jsonify([inv.to_dict() for inv in invoices])


@invoice_blueprint.route('/invoices')
@login_required
def list_invoices():
    """
    List all invoices for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
    invoices = B2BInvoice.query.filter_by(user_id=current_user.id).all()
    return jsonify([invoice.to_dict() for invoice in invoices])

@invoice_blueprint.route('/invoice/<invoice_id>')
@login_required
def view_invoice(invoice_id):
    """
    View a specific invoice for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
    invoice = B2BInvoice.query.get(invoice_id)
    if not invoice or invoice.user_id != current_user.id:
        return jsonify({"error": "Invoice not found or access denied"}), 404
    
    invoice_html = get_invoice_html(invoice)
    # This assumes you have a generic invoice template that can be populated.
    return render_template('b2b_invoice_template.html', invoice_html=invoice_html)


@invoice_blueprint.route('/download_invoice/<invoice_id>')
@login_required
def download_invoice(invoice_id):
    """
    Download a specific invoice as a PDF for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
        
    invoice = B2BInvoice.query.get(invoice_id)
    if not invoice or invoice.user_id != current_user.id:
        return jsonify({"error": "Invoice not found or access denied"}), 404

    try:
        from weasyprint import HTML
        invoice_html = get_invoice_html(invoice)
        pdf = HTML(string=invoice_html).write_pdf()
        return send_file(
            BytesIO(pdf),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'invoice_{invoice.invoice_number}.pdf'
        )
    except ImportError:
        return jsonify({"error": "PDF generation library not installed."}), 500
    except Exception as e:
        return jsonify({"error": "Could not generate PDF.", "details": str(e)}), 500
