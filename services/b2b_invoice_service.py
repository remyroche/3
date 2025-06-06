# services/b2b_invoice_service.py
from flask import current_app, render_template
from weasyprint import HTML
import os
from datetime import datetime, timezone, timedelta

from .. import db
from ..models import (Invoice, InvoiceItem, Order, User,
                    InvoiceStatusEnum, OrderStatusEnum, UserRoleEnum)
from ..utils import sanitize_input

class B2BInvoiceService:
    """Handles invoice creation and management for B2B clients."""

    @staticmethod
    def _prepare_logo_path():
        """Prepares the absolute file path for the logo for PDF embedding."""
        company_info = current_app.config.get('DEFAULT_COMPANY_INFO', {})
        logo_path_config = company_info.get('logo_path')
        if not logo_path_config or not os.path.exists(logo_path_config):
            current_app.logger.warning(f"B2B Invoice logo path not found or not configured: {logo_path_config}")
            return None
        return f'file://{os.path.abspath(logo_path_config)}'


    @staticmethod
    def create_manual_invoice(b2b_user_id, line_items_data, notes=None, issued_by_admin_id=None):
        """
        Creates a manual B2B invoice, typically by an admin.
        """
        user = User.query.get(b2b_user_id)
        if not user or user.role != UserRoleEnum.B2B_PROFESSIONAL:
            raise ValueError("Invalid B2B user ID provided.")

        invoice_service = B2BInvoiceService()
        invoice_number = invoice_service._generate_b2b_invoice_number()
        issue_date = datetime.now(timezone.utc)
        due_date = issue_date + timedelta(days=current_app.config.get('INVOICE_DUE_DAYS', 30))

        new_invoice = Invoice(
            b2b_user_id=b2b_user_id,
            invoice_number=invoice_number,
            issue_date=issue_date,
            due_date=due_date,
            currency='EUR',
            status=InvoiceStatusEnum.DRAFT,
            notes=sanitize_input(notes),
            created_by_admin_id=issued_by_admin_id
        )

        subtotal_ht = 0
        for item_data in line_items_data:
            total_price = item_data['quantity'] * item_data['unit_price']
            subtotal_ht += total_price
            invoice_item = InvoiceItem(
                description=sanitize_input(item_data['description']),
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                total_price=total_price,
                product_id=item_data.get('product_id')
            )
            new_invoice.items.append(invoice_item)
        
        new_invoice.total_amount = subtotal_ht # For B2B, total_amount can be subtotal HT

        # PDF generation can be triggered here or upon a status change (e.g., to 'Issued')
        # pdf_path = invoice_service._generate_and_save_b2b_pdf(new_invoice, user)
        # new_invoice.pdf_path = pdf_path
        # new_invoice.status = InvoiceStatusEnum.ISSUED

        db.session.add(new_invoice)
        return new_invoice

    @staticmethod
    def create_invoice_from_b2b_order(order: Order):
        """
        Generates a B2B invoice from a confirmed B2B order.
        """
        if not order.is_b2b_order:
            raise ValueError("This function is only for B2B orders.")
        
        # The logic here would be very similar to create_manual_invoice,
        # but the line items would be derived from `order.items`.
        # It would also handle VAT calculation based on B2B rules.
        
        # Placeholder for the more complex B2B invoice from order logic
        current_app.logger.info(f"Placeholder for generating B2B invoice from order {order.id}")
        return None


    def _generate_b2b_invoice_number(self):
        """Generates a B2B-specific invoice number."""
        prefix = "B2B-INV"
        last_invoice = Invoice.query.filter(Invoice.invoice_number.like(f"{prefix}-%"))\
                                    .order_by(Invoice.id.desc()).first()
        current_year = str(datetime.now(timezone.utc).year)
        next_id = 1
        
        if last_invoice and last_invoice.invoice_number:
            parts = last_invoice.invoice_number.split('-')
            if len(parts) == 3 and parts[1] == current_year:
                try:
                    next_id = int(parts[2]) + 1
                except ValueError:
                    pass
        
        return f"{prefix}-{current_year}-{next_id:05d}"


def create_b2b_invoice_from_order(order):
    """
    Creates and saves a B2BInvoice record from a completed Order.
    This is called when a B2B user pays by card.
    """
    if not order or not order.user_id:
        return None

    # Generate a unique invoice number
    invoice_number = f"INV-B2B-{order.id}-{order.created_at.strftime('%Y%m%d')}"

    # Create the new invoice
    new_invoice = B2BInvoice(
        invoice_number=invoice_number,
        user_id=order.user_id,
        order_id=order.id,
        amount=order.total_amount,
        status='PAID'  # Marked as PAID since it's from a card transaction
    )

    db.session.add(new_invoice)
    # The commit will happen as part of the order creation process
    
    return new_invoice


  
    def _generate_and_save_b2b_pdf(self, invoice: Invoice, user: User, order: Order = None):
        """Renders the B2B HTML template and converts it to a PDF."""
        company_info = current_app.config.get('DEFAULT_COMPANY_INFO', {})
        logo_path = self._prepare_logo_path()
        
        # B2B invoices often have more complex data requirements (VAT, payment terms)
        context = {
            "invoice": invoice,
            "client": user, # In B2B, user is the client
            "order": order,
            "company": {**company_info, 'logo_path': logo_path},
            "is_b2b": True
            # Add more B2B-specific context like VAT details, payment terms etc.
        }
        
        html_string = render_template('b2b_invoice_template.html', **context)
        
        pdf_filename = f"{invoice.invoice_number}.pdf"
        invoice_pdf_dir = current_app.config['INVOICE_PDF_PATH']
        os.makedirs(invoice_pdf_dir, exist_ok=True)
        pdf_full_path = os.path.join(invoice_pdf_dir, pdf_filename)
        
        HTML(string=html_string).write_pdf(pdf_full_path)
        
        base_asset_path = current_app.config['ASSET_STORAGE_PATH']
        relative_path = os.path.relpath(pdf_full_path, base_asset_path).replace(os.sep, '/')
        
        current_app.logger.info(f"Generated PDF for B2B invoice {invoice.invoice_number} at {relative_path}")
        return relative_path
