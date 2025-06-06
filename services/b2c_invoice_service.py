# services/b2c/b2c_invoice_service.py
from flask import current_app, render_template
from weasyprint import HTML
import os
from datetime import datetime, timezone

from .. import db
from ..models import Invoice, InvoiceItem, Order, User, SerializedInventoryItem, InvoiceStatusEnum, OrderStatusEnum
from ..utils import format_datetime_for_display

class B2CInvoiceService:
    """Handles invoice creation for B2C (retail) orders."""

    @staticmethod
    def _prepare_logo_path():
        """Prepares the absolute file path for the logo to be embedded in the PDF."""
        company_info = current_app.config.get('DEFAULT_COMPANY_INFO', {})
        logo_path_config = company_info.get('logo_path')
        if not logo_path_config:
            return None
        
        # Check if it's an absolute path that exists
        if os.path.isabs(logo_path_config) and os.path.exists(logo_path_config):
            return f'file://{logo_path_config}'
        
        # Check relative to project root
        path_from_root = os.path.join(current_app.root_path, '..', logo_path_config)
        if os.path.exists(path_from_root):
            return f'file://{os.path.abspath(path_from_root)}'
            
        current_app.logger.warning(f"Invoice logo path could not be resolved: {logo_path_config}")
        return None

    @staticmethod
    def create_invoice_for_order(order: Order):
        """
        Generates and saves a PDF invoice for a given B2C order.

        Args:
            order (Order): The SQLAlchemy Order object.

        Returns:
            Invoice: The newly created Invoice object.
            
        Raises:
            ValueError: If the order already has an invoice or is invalid.
        """
        if order.invoice:
            raise ValueError(f"Order {order.id} already has an invoice (ID: {order.invoice.id}).")
        if not order.customer:
            raise ValueError(f"Order {order.id} does not have an associated customer.")

        invoice_service = C2CInvoiceService()
        invoice_number = invoice_service._generate_invoice_number()
        
        # For B2C, issue date is typically the order/payment date.
        issue_date = order.payment_date or order.order_date or datetime.now(timezone.utc)

        new_invoice = Invoice(
            order_id=order.id,
            invoice_number=invoice_number,
            issue_date=issue_date,
            due_date=issue_date, # B2C invoices are pre-paid
            total_amount=order.total_amount,
            currency=order.currency,
            status=InvoiceStatusEnum.PAID,
            payment_date=issue_date
        )

        for item in order.items:
            # For B2C, unit_price on OrderItem is likely TTC. InvoiceItem should reflect this.
            invoice_item = InvoiceItem(
                description=f"{item.product_name} {item.variant_description or ''}".strip(),
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=item.total_price,
                product_id=item.product_id,
                serialized_item_id=item.serialized_item_id
            )
            new_invoice.items.append(invoice_item)

        # Generate and save the PDF
        pdf_path = invoice_service._generate_and_save_pdf(new_invoice, order.customer, order)
        new_invoice.pdf_path = pdf_path

        db.session.add(new_invoice)
        # The calling function should commit the session.

        current_app.logger.info(f"Successfully created C2C Invoice object {invoice_number} for Order {order.id}.")
        return new_invoice

    def _generate_invoice_number(self):
        """Generates a new invoice number."""
        prefix = "INV"
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

    def _generate_and_save_pdf(self, invoice: Invoice, user: User, order: Order):
        """Renders the HTML template and converts it to a PDF."""
        company_info = current_app.config.get('DEFAULT_COMPANY_INFO', {})
        logo_path = self._prepare_logo_path()

        context = {
            "invoice": invoice,
            "user": user,
            "order": order,
            "company": {**company_info, 'logo_path': logo_path},
            "shipping_address": {
                "line1": order.shipping_address_line1,
                "line2": order.shipping_address_line2,
                "city": order.shipping_city,
                "postal_code": order.shipping_postal_code,
                "country": order.shipping_country
            }
        }
        
        html_string = render_template('invoice_template.html', **context)
        
        pdf_filename = f"{invoice.invoice_number}.pdf"
        invoice_pdf_dir = current_app.config['INVOICE_PDF_PATH']
        os.makedirs(invoice_pdf_dir, exist_ok=True)
        pdf_full_path = os.path.join(invoice_pdf_dir, pdf_filename)

        HTML(string=html_string).write_pdf(pdf_full_path)

        base_asset_path = current_app.config['ASSET_STORAGE_PATH']
        relative_path = os.path.relpath(pdf_full_path, base_asset_path).replace(os.sep, '/')
        
        current_app.logger.info(f"Generated PDF for invoice {invoice.invoice_number} at {relative_path}")
        return relative_path

