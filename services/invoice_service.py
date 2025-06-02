# backend/services/invoice_service.py
import os
from datetime import datetime, timedelta, timezone
from flask import current_app, render_template, url_for
from weasyprint import HTML
from sqlalchemy.exc import IntegrityError

from .. import db # Import SQLAlchemy instance
from ..models import Invoice, InvoiceItem, Order, User, ProductWeightOption # Import necessary models

class InvoiceService:
    """Service class for handling invoice generation and management using SQLAlchemy."""

    def __init__(self):
        self.config = current_app.config

    def _generate_invoice_number(self):
        """Generates a new, unique invoice number using SQLAlchemy."""
        try:
            last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
            if last_invoice and last_invoice.invoice_number:
                parts = last_invoice.invoice_number.split('-')
                current_year_str = str(datetime.now().year)
                if len(parts) == 3 and parts[0] == 'INV' and parts[1] == current_year_str:
                    next_id = int(parts[2]) + 1
                else: # Fallback for different format or new year
                    next_id = 1
            else:
                next_id = 1
            return f"INV-{datetime.now().year}-{next_id:05d}"
        except Exception as e:
            current_app.logger.error(f"Error generating invoice number: {e}", exc_info=True)
            return f"INV-ERR-{int(datetime.now().timestamp())}"

    def _create_pdf_and_save(self, invoice_model, user_model, invoice_items_list, shipping_address_details=None, notes_for_pdf=None):
        """Helper function to generate PDF and save its path to the invoice_model."""
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
            "invoice": invoice_model, # Pass the SQLAlchemy model instance
            "invoice_items": invoice_items_list, # List of dicts or model instances
            "user": user_model, # User SQLAlchemy model instance
            "shipping_address": shipping_address_details, # Dict
            "company": company_info_for_template,
            "notes": notes_for_pdf or invoice_model.notes # Use passed notes or invoice model notes
        }
        
        html_string = render_template('invoice_template.html', **context)
        pdf_file_content = HTML(string=html_string).write_pdf()
        
        pdf_filename = f"{invoice_model.invoice_number}.pdf"
        invoice_pdf_dir = self.config['INVOICE_PDF_PATH']
        os.makedirs(invoice_pdf_dir, exist_ok=True)
        pdf_full_path = os.path.join(invoice_pdf_dir, pdf_filename)
        
        with open(pdf_full_path, 'wb') as f: f.write(pdf_file_content)
        
        # Store relative path for DB, easier for serving later
        invoice_model.pdf_path = os.path.join('invoices', pdf_filename) # e.g., 'invoices/INV-2024-00001.pdf'
        invoice_model.status = 'issued' # Update status after PDF generation
        # The calling method will commit the session.
        current_app.logger.info(f"PDF generated for invoice {invoice_model.invoice_number} at {invoice_model.pdf_path}")


    def create_invoice_from_order(self, order_id, issued_by_admin_id=None):
        """Creates an invoice for a given order using SQLAlchemy."""
        if not order_id: raise ValueError("Order ID is required.")

        order = Order.query.get(order_id)
        if not order: raise ValueError(f"Order with ID {order_id} not found.")

        if order.invoice: # Check if an invoice already exists via relationship
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
            b2b_user_id=user.id if user.role == 'b2b_professional' else None, # Link B2B user if applicable
            invoice_number=invoice_number,
            issue_date=issue_date,
            due_date=due_date,
            total_amount=order.total_amount,
            currency=order.currency,
            status='draft', # Initial status
            notes=order.notes_internal # Or specific invoice notes logic
        )
        db.session.add(new_invoice)
        db.session.flush() # To get new_invoice.id
        
        invoice_items_for_pdf = []
        for order_item_model in order.items:
            inv_item = InvoiceItem(
                invoice_id=new_invoice.id,
                description=f"{order_item_model.product_name} ({order_item_model.variant_description or 'Standard'})",
                quantity=order_item_model.quantity,
                unit_price=order_item_model.unit_price,
                total_price=order_item_model.total_price,
                product_id=order_item_model.product_id
                # serialized_item_id can be linked if applicable
            )
            db.session.add(inv_item)
            invoice_items_for_pdf.append(inv_item) # Pass model instance

        shipping_details = {
            "line1": order.shipping_address_line1, "line2": order.shipping_address_line2,
            "city": order.shipping_city, "postal_code": order.shipping_postal_code, "country": order.shipping_country
        }

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
        """Creates a manual invoice for a B2B user using SQLAlchemy."""
        if not b2b_user_id or not line_items_data:
            raise ValueError("B2B User ID and line items are required.")

        user = User.query.filter_by(id=b2b_user_id, role='b2b_professional').first()
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
            b2b_user_id=b2b_user_id,
            invoice_number=invoice_number,
            issue_date=issue_date,
            due_date=due_date,
            total_amount=total_amount,
            currency=user_currency or user.currency or 'EUR', # Fallback currency
            status='draft', notes=notes
        )
        db.session.add(new_invoice)
        db.session.flush() # To get new_invoice.id
        
        invoice_items_for_pdf = []
        for item_data in line_items_data:
            item_total = item_data['quantity'] * item_data['unit_price']
            inv_item = InvoiceItem(
                invoice_id=new_invoice.id,
                description=item_data['description'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                total_price=item_total
            )
            db.session.add(inv_item)
            invoice_items_for_pdf.append(inv_item) # Pass model instance

        # Fetch user's primary shipping address if needed for PDF, or pass None
        # For now, assume no specific shipping address for manual invoice unless provided differently
        
        self._create_pdf_and_save(new_invoice, user, invoice_items_for_pdf, shipping_address_details=None, notes_for_pdf=notes)
        
        try:
            db.session.commit()
            current_app.logger.info(f"Manual invoice ID {new_invoice.id} ({invoice_number}) created for B2B user ID {b2b_user_id}.")
            return new_invoice.id, new_invoice.invoice_number
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing manual invoice for B2B user {b2b_user_id}: {e}", exc_info=True)
            raises_for_pdf=notes)
        
        try:
            db.session.commit()
            current_app.logger.info(f"Manual invoice ID {new_invoice.id} ({invoice_number}) created for B2B user ID {b2b_user_id}.")
            return new_invoice.id, new_invoice.invoice_number
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing manual invoice for B2B user {b2b_user_id}: {e}", exc_info=True)
            raise
