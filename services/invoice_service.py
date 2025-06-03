# backend/services/invoice_service.py
import os
from datetime import datetime, timedelta, timezone
from flask import current_app, render_template, url_for
from weasyprint import HTML# backend/services/invoice_service.py
import os
from datetime import datetime, timedelta, timezone
from flask import current_app, render_template, url_for 
from weasyprint import HTML 
from sqlalchemy.exc import IntegrityError 

from .. import db 
from ..models import Invoice, InvoiceItem, Order, User, ProductWeightOption, InvoiceStatusEnum # Assuming Enums used in models

class InvoiceService:
    def __init__(self):
        self.config = current_app.config

    def _generate_invoice_number(self):
        # ... (Generates INV-YYYY-NNNNN, checks last invoice in DB) ...
        # Logic seems sound for sequential numbering within a year.
        # Consider potential race conditions if multiple invoice creations happen simultaneously,
        # though for most systems, a slight delay or DB transaction isolation handles this.
        # Using `with_for_update()` on the last_invoice query could be an option for high concurrency.
        last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
        current_year_str = str(datetime.now().year)
        next_id_num = 1
        if last_invoice and last_invoice.invoice_number:
            parts = last_invoice.invoice_number.split('-')
            if len(parts) == 3 and parts[0] == 'INV' and parts[1] == current_year_str:
                try:
                    next_id_num = int(parts[2]) + 1
                except ValueError:
                    pass # Fallback to 1 if parsing fails
        return f"INV-{current_year_str}-{next_id_num:05d}"


    def _create_pdf_and_save(self, invoice_model, user_model, invoice_items_list, shipping_address_details=None, notes_for_pdf=None):
        company_info = self.config.get('DEFAULT_COMPANY_INFO', {})
        logo_path_config = company_info.get('logo_path')
        prepared_logo_path = None
        if logo_path_config:
            if logo_path_config.startswith('file://'): prepared_logo_path = logo_path_config
            elif os.path.isabs(logo_path_config) and os.path.exists(logo_path_config): prepared_logo_path = f'file://{os.path.abspath(logo_path_config)}'
            elif os.path.exists(os.path.join(current_app.root_path, logo_path_config)): prepared_logo_path = f'file://{os.path.abspath(os.path.join(current_app.root_path, logo_path_config))}'
            else: current_app.logger.warning(f"Invoice logo path not found or invalid: {logo_path_config}")
        
        company_info_for_template = {**company_info, 'logo_path': prepared_logo_path}

        context = {
            "invoice": invoice_model, 
            "invoice_items": invoice_items_list, 
            "user": user_model, 
            "shipping_address": shipping_address_details, 
            "company": company_info_for_template,
            "notes": notes_for_pdf or invoice_model.notes 
        }
        
        # Ensure we are in an app context for render_template and url_for (if used in template)
        with current_app.app_context():
            html_string = render_template('invoice_template.html', **context)
        
        pdf_file_content = HTML(string=html_string).write_pdf()
        
        pdf_filename = f"{invoice_model.invoice_number}.pdf"
        invoice_pdf_dir = self.config['INVOICE_PDF_PATH'] # Absolute path from config
        os.makedirs(invoice_pdf_dir, exist_ok=True)
        pdf_full_path = os.path.join(invoice_pdf_dir, pdf_filename)
        
        with open(pdf_full_path, 'wb') as f: f.write(pdf_file_content)
        
        # Store relative path for DB, assuming ASSET_STORAGE_PATH is the base for serving 'invoices/*'
        # e.g., ASSET_STORAGE_PATH = '/var/www/app/instance/generated_assets'
        # INVOICE_PDF_PATH = '/var/www/app/instance/generated_assets/invoices'
        # pdf_path_for_db should be 'invoices/INV-2024-00001.pdf'
        base_asset_path = self.config['ASSET_STORAGE_PATH']
        invoice_model.pdf_path = os.path.relpath(pdf_full_path, base_asset_path).replace(os.sep, '/')

        invoice_model.status = InvoiceStatusEnum.ISSUED # Use Enum
        current_app.logger.info(f"PDF generated for invoice {invoice_model.invoice_number} at {invoice_model.pdf_path}")


    def create_invoice_from_order(self, order_id, issued_by_admin_id=None):
        if not order_id: raise ValueError("Order ID is required.")
        order = Order.query.get(order_id)
        if not order: raise ValueError(f"Order with ID {order_id} not found.")
        if order.invoice:
            current_app.logger.warning(f"Invoice for order {order_id} already exists (ID: {order.invoice.id}). Returning existing: {order.invoice.invoice_number}")
            return order.invoice.id, order.invoice.invoice_number

        user = User.query.get(order.user_id)
        if not user: raise ValueError(f"User with ID {order.user_id} not found for order {order_id}.")
        if not order.items: raise ValueError(f"No items found for order ID {order_id}.")

        invoice_number = self._generate_invoice_number()
        issue_date = datetime.now(timezone.utc)
        due_date = issue_date + timedelta(days=self.config.get('INVOICE_DUE_DAYS', 30))
        
        new_invoice = Invoice(
            order_id=order_id,
            b2b_user_id=user.id if user.role == UserRoleEnum.B2B_PROFESSIONAL else None,
            invoice_number=invoice_number, issue_date=issue_date, due_date=due_date,
            total_amount=order.total_amount, currency=order.currency,
            status=InvoiceStatusEnum.DRAFT, notes=order.notes_internal
        )
        db.session.add(new_invoice)
        db.session.flush() 
        
        invoice_items_for_pdf = []
        for order_item_model in order.items:
            desc = f"{order_item_model.product_name} ({order_item_model.variant_description or 'Standard'})"
            inv_item = InvoiceItem(
                invoice_id=new_invoice.id, description=desc, quantity=order_item_model.quantity,
                unit_price=order_item_model.unit_price, total_price=order_item_model.total_price,
                product_id=order_item_model.product_id
            )
            db.session.add(inv_item)
            invoice_items_for_pdf.append(inv_item)

        shipping_details = {"line1": order.shipping_address_line1, "line2": order.shipping_address_line2,
                            "city": order.shipping_city, "postal_code": order.shipping_postal_code, 
                            "country": order.shipping_country}
        self._create_pdf_and_save(new_invoice, user, invoice_items_for_pdf, shipping_details, order.notes_internal)
        
        try:
            db.session.commit()
            current_app.logger.info(f"Invoice ID {new_invoice.id} ({invoice_number}) created for order ID {order_id}.")
            return new_invoice.id, new_invoice.invoice_number
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing invoice for order {order_id}: {e}", exc_info=True)
            raise


    def create_manual_invoice(self, b2b_user_id, user_currency, line_items_data, notes=None, issued_by_admin_id=None):
        if not b2b_user_id or not line_items_data: raise ValueError("B2B User ID and line items are required.")
        user = User.query.filter_by(id=b2b_user_id, role=UserRoleEnum.B2B_PROFESSIONAL).first()
        if not user: raise ValueError(f"B2B Professional User with ID {b2b_user_id} not found.")

        invoice_number = self._generate_invoice_number()
        issue_date = datetime.now(timezone.utc)
        due_date = issue_date + timedelta(days=self.config.get('INVOICE_DUE_DAYS', 30))
        
        total_amount = 0
        for item_data in line_items_data:
            if not all(k in item_data for k in ('description', 'quantity', 'unit_price')):
                raise ValueError("Each line item must have description, quantity, and unit_price.")
            item_data['quantity'] = int(item_data['quantity'])
            item_data['unit_price'] = float(item_data['unit_price'])
            if item_data['quantity'] <= 0 or item_data['unit_price'] < 0:
                raise ValueError("Item quantity must be positive and unit price non-negative.")
            total_amount += item_data['quantity'] * item_data['unit_price']

        new_invoice = Invoice(
            b2b_user_id=b2b_user_id, invoice_number=invoice_number, issue_date=issue_date, due_date=due_date,
            total_amount=total_amount, currency=user_currency or user.currency or 'EUR',
            status=InvoiceStatusEnum.DRAFT, notes=notes
        )
        db.session.add(new_invoice)
        db.session.flush()
        
        invoice_items_for_pdf = []
        for item_data in line_items_data:
            item_total = item_data['quantity'] * item_data['unit_price']
            inv_item = InvoiceItem(
                invoice_id=new_invoice.id, description=item_data['description'],
                quantity=item_data['quantity'], unit_price=item_data['unit_price'],
                total_price=item_total
            )
            db.session.add(inv_item)
            invoice_items_for_pdf.append(inv_item)
        
        self._create_pdf_and_save(new_invoice, user, invoice_items_for_pdf, shipping_address_details=None, notes_for_pdf=notes)
        
        try:
            db.session.commit()
            current_app.logger.info(f"Manual invoice ID {new_invoice.id} ({invoice_number}) created for B2B user ID {b2b_user_id}.")
            return new_invoice.id, new_invoice.invoice_number
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing manual invoice for B2B user {b2b_user_id}: {e}", exc_info=True)
            raise
