# backend/services/invoice_service.py
import os
from datetime import datetime, timedelta, timezone
from flask import current_app, render_template
from weasyprint import HTML, WeasyPrintError # Ensure WeasyPrintError is imported
from sqlalchemy.exc import IntegrityError 

from .. import db 
from ..models import Invoice, InvoiceItem, Order, User, UserRoleEnum, InvoiceStatusEnum # Import necessary Enums and Models

class InvoiceService:
    def __init__(self):
        self.config = current_app.config

    def _generate_invoice_number(self):
        """
        Generates a new invoice number.
        Example format: INV-YYYY-NNNNN
        """
        last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
        current_year_str = str(datetime.now(timezone.utc).year)
        next_id_num = 1
        
        if last_invoice and last_invoice.invoice_number:
            parts = last_invoice.invoice_number.split('-')
            # Expected format INV-YYYY-NNNNN
            if len(parts) == 3 and parts[0] == 'INV' and parts[1] == current_year_str:
                try:
                    next_id_num = int(parts[2]) + 1
                except ValueError:
                    # Log error or handle cases where NNNNN is not a number
                    current_app.logger.warning(f"Could not parse invoice number sequence from {last_invoice.invoice_number}")
                    # Fallback to a high number or a different scheme if parsing fails often
                    # For now, resetting to 1 if parsing fails after matching INV-YYYY
                    next_id_num = 1 
            elif parts[0] != 'INV' or parts[1] != current_year_str :
                 # If year changed or prefix is different, reset sequence for the new year/prefix
                next_id_num = 1


        return f"INV-{current_year_str}-{next_id_num:05d}"

    def _prepare_logo_path_for_pdf(self):
        """
        Prepares the logo path for WeasyPrint consumption.
        Ensures it's an absolute file URI or an accessible HTTP/HTTPS URL.
        """
        company_info = self.config.get('DEFAULT_COMPANY_INFO', {})
        # Use a config key that explicitly states it's for PDF generation and needs to be absolute or a file URI
        logo_path_config = company_info.get('INVOICE_COMPANY_LOGO_PATH_FOR_PDF') 
        
        if not logo_path_config:
            current_app.logger.warning("INVOICE_COMPANY_LOGO_PATH_FOR_PDF not configured in DEFAULT_COMPANY_INFO.")
            return None

        if logo_path_config.startswith('file://') or logo_path_config.startswith('http://') or logo_path_config.startswith('https://'):
            return logo_path_config
        
        # If it's a relative path from project root or instance folder, resolve it
        # Assuming paths in config might be relative to current_app.root_path
        # This needs to point to where the actual image file is located.
        # Example: if INVOICE_COMPANY_LOGO_PATH_FOR_PDF = "static_assets/logos/maison_truvra_invoice_logo.png"
        # and current_app.root_path is the backend directory.
        
        # Check if it's an absolute path first
        if os.path.isabs(logo_path_config) and os.path.exists(logo_path_config):
            return f'file://{os.path.abspath(logo_path_config)}'
        
        # Check relative to app.root_path (often the 'backend' directory)
        path_relative_to_root = os.path.join(current_app.root_path, logo_path_config)
        if os.path.exists(path_relative_to_root):
            return f'file://{os.path.abspath(path_relative_to_root)}'
            
        current_app.logger.warning(f"Invoice logo path could not be resolved to an absolute file URI or URL: {logo_path_config}")
        return None


    def _create_pdf_and_save(self, invoice_model, user_model, 
                             invoice_items_list=None, 
                             shipping_address_details=None, 
                             notes_for_pdf=None,
                             raw_html_content=None, 
                             is_b2b_manual=False):
        """
        Generates a PDF for the invoice and saves it.
        Updates invoice_model.pdf_path and status.
        The calling method is expected to commit the session.
        Returns True on success, False on PDF generation failure.
        """
        company_info = self.config.get('DEFAULT_COMPANY_INFO', {})
        prepared_logo_path_for_template = self._prepare_logo_path_for_pdf() # Get processed logo path

        html_string_for_pdf = None

        if raw_html_content and is_b2b_manual:
            html_string_for_pdf = raw_html_content
            # If the raw HTML contains a placeholder for the logo, replace it here.
            # Example: if raw_html_content contains '{{ MAISON_TRUVRA_LOGO_URL_PLACEHOLDER }}'
            # This placeholder should match what admin_create_invoice.html's preview section uses for its logo src.
            # The path provided here must be absolute (file:/// or http://) for WeasyPrint.
            if prepared_logo_path_for_template: # Ensure it's not None
                 # The placeholder in your raw_html_content needs to be consistent.
                 # Let's assume it's '../images/maison_truvra_invoice_logo.png' as in admin_create_invoice.html
                 # or a specific placeholder like {{ MAISON_TRUVRA_LOGO_ABSOLUTE_PATH }}.
                 # For this example, let's assume the frontend HTML for the preview uses a relative path
                 # that WeasyPrint won't resolve correctly from a raw string. We need to replace it.
                 # A robust way is to use a unique placeholder in the captured HTML.
                 # If the admin_create_invoice.html preview uses, for instance:
                 # <img src="/static_assets/logos/maison_truvra_invoice_logo.png" ...>
                 # And your Flask app serves static_assets from root, WeasyPrint's base_url might handle it.
                 # If not, you might need to make paths absolute in the captured HTML or replace them here.

                # If the frontend preview's logo path is something like:
                # <img src="../images/maison_truvra_invoice_logo.png" ... > (relative to admin dir)
                # or <img src="/static_assets/logos/maison_truvra_invoice_logo.png" ... > (relative to site root)
                # WeasyPrint's base_url (set to APP_BASE_URL_FRONTEND) should help resolve the /static_assets/... path.
                # If it's a deeply relative path from the JS-captured HTML, it might fail.
                # The most reliable is an absolute file:/// path or an http:// URL for the logo in the PDF.
                # For simplicity here, we rely on WeasyPrint's base_url to handle well-formed relative paths
                # from the site root (like /static_assets/...).
                pass # Assuming base_url handles it, or paths in raw_html_content are already absolute.
            current_app.logger.info(f"Using raw HTML content for B2B invoice PDF: {invoice_model.invoice_number}")
        else:
            context = {
                "invoice": invoice_model, 
                "invoice_items": invoice_items_list or [], # Ensure it's a list
                "user": user_model, 
                "shipping_address": shipping_address_details, 
                "company": {**company_info, 'logo_path': prepared_logo_path_for_template}, # Pass the processed logo path
                "notes": notes_for_pdf or invoice_model.notes,
                "is_b2b": user_model.role == UserRoleEnum.B2B_PROFESSIONAL
            }
            try:
                with current_app.app_context():
                    html_string_for_pdf = render_template('invoice_template.html', **context)
            except Exception as e_render:
                current_app.logger.error(f"Error rendering invoice_template.html for {invoice_model.invoice_number}: {e_render}", exc_info=True)
                invoice_model.notes = (invoice_model.notes or "") + f"\n[System Note] PDF template rendering failed: {e_render}"
                return False

        if not html_string_for_pdf:
            current_app.logger.error(f"HTML content for PDF generation is empty for invoice {invoice_model.invoice_number}.")
            return False

        try:
            # Use APP_BASE_URL_FRONTEND (or site root URL) as base_url for WeasyPrint
            # This helps resolve relative paths for CSS, images if any are used in the HTML
            # that are relative to the frontend site's root.
            weasyprint_base_url = current_app.config.get('APP_BASE_URL_FRONTEND')
            if not weasyprint_base_url:
                 current_app.logger.warning("APP_BASE_URL_FRONTEND not configured; WeasyPrint might not resolve relative asset URLs.")
            
            pdf_file_content = HTML(string=html_string_for_pdf, base_url=weasyprint_base_url).write_pdf()
            
            pdf_filename = f"{invoice_model.invoice_number}.pdf"
            invoice_pdf_dir_abs = self.config['INVOICE_PDF_PATH'] 
            os.makedirs(invoice_pdf_dir_abs, exist_ok=True)
            pdf_full_path = os.path.join(invoice_pdf_dir_abs, pdf_filename)
            
            with open(pdf_full_path, 'wb') as f: f.write(pdf_file_content)
            
            base_asset_path = self.config['ASSET_STORAGE_PATH'] # e.g., instance/generated_assets
            # pdf_path should be relative to ASSET_STORAGE_PATH, e.g., "invoices/INV-2024-00001.pdf"
            invoice_model.pdf_path = os.path.relpath(pdf_full_path, base_asset_path).replace(os.sep, '/')
            
            # Only set to ISSUED if successfully generated
            invoice_model.status = InvoiceStatusEnum.ISSUED 
            current_app.logger.info(f"PDF generated for invoice {invoice_model.invoice_number} at {invoice_model.pdf_path}")
            return True
        except WeasyPrintError as e_wp:
            current_app.logger.error(f"WeasyPrint PDF generation failed for invoice {invoice_model.invoice_number}: {e_wp}", exc_info=True)
            invoice_model.notes = (invoice_model.notes or "") + f"\n[System Note] PDF generation failed: {e_wp}"
            # Consider setting a specific "PDF_FAILED" status if the invoice record is still to be saved.
            # For now, it will remain DRAFT or whatever status it had.
            return False
        except Exception as e:
            current_app.logger.error(f"General error during PDF creation/saving for invoice {invoice_model.invoice_number}: {e}", exc_info=True)
            invoice_model.notes = (invoice_model.notes or "") + f"\n[System Note] PDF creation error: {e}"
            return False

    def create_manual_invoice(self, b2b_user_id, user_currency, line_items_data, 
                              notes=None, issued_by_admin_id=None, 
                              invoice_date_str=None, due_date_str=None, # Added for form dates
                              raw_invoice_html=None):
        if not b2b_user_id or not line_items_data: 
            raise ValueError("B2B User ID and line items are required.")
        
        user = User.query.filter_by(id=b2b_user_id, role=UserRoleEnum.B2B_PROFESSIONAL).first()
        if not user: 
            raise ValueError(f"B2B User with ID {b2b_user_id} not found or is not a professional.")

        invoice_number = self._generate_invoice_number()
        
        issue_date = datetime.now(timezone.utc)
        if invoice_date_str:
            try: issue_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError: current_app.logger.warning(f"Invalid invoice_date_str: {invoice_date_str}, using current date.")

        due_date = issue_date + timedelta(days=self.config.get('INVOICE_DUE_DAYS', 30))
        if due_date_str:
            try: due_date = datetime.strptime(due_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError: current_app.logger.warning(f"Invalid due_date_str: {due_date_str}, calculating from issue date.")
        
        total_amount = 0
        invoice_items_for_db = []
        for item_data in line_items_data:
            if not all(k in item_data for k in ('description', 'quantity', 'unit_price')): 
                raise ValueError("Each line item must have description, quantity, and unit_price.")
            
            try:
                quantity = int(item_data['quantity'])
                unit_price = float(item_data['unit_price'])
                # vat_rate = float(item_data.get('vat_rate', 20)) # Example: default VAT rate if not provided
            except ValueError:
                raise ValueError("Invalid quantity or unit_price in line items.")

            if quantity <= 0 or unit_price < 0: 
                raise ValueError("Quantity must be positive and unit_price non-negative.")
            
            line_total_price = quantity * unit_price # This should be HT if unit_price is HT
            # If unit_price includes VAT, or if VAT is calculated separately:
            # line_total_price_ttc = line_total_price * (1 + vat_rate / 100) # Example
            total_amount += line_total_price # Summing HT totals
            
            inv_item = InvoiceItem(
                description=item_data['description'], 
                quantity=quantity,
                unit_price=unit_price, 
                total_price=line_total_price 
                # Add vat_rate to InvoiceItem model if needed per line
            )
            invoice_items_for_db.append(inv_item)

        # If total_amount needs to be TTC and line_items are HT + VAT rate per line:
        # You'd calculate VAT per line, sum them up, and add to sum of HT lines for final total_amount.
        # For simplicity here, assuming total_amount is calculated based on line_items structure from frontend.

        new_invoice = Invoice(
            b2b_user_id=b2b_user_id, 
            invoice_number=invoice_number, 
            issue_date=issue_date, 
            due_date=due_date,
            total_amount=round(total_amount, 2), # Ensure it's rounded
            currency=user_currency or user.currency or self.config.get('DEFAULT_CURRENCY', 'EUR'),
            status=InvoiceStatusEnum.DRAFT, # Start as DRAFT
            notes=notes,
            created_by_admin_id=issued_by_admin_id # Assuming you add this field to Invoice model
        )
        db.session.add(new_invoice)
        db.session.flush() # Get new_invoice.id for items

        for inv_item_obj in invoice_items_for_db:
            inv_item_obj.invoice_id = new_invoice.id
            db.session.add(inv_item_obj)
        
        # Pass raw_invoice_html to the PDF generation method
        pdf_created_successfully = self._create_pdf_and_save(
            new_invoice, user, 
            invoice_items_list=invoice_items_for_db, # Still useful for template fallback or DB record
            raw_html_content=raw_invoice_html, 
            is_b2b_manual=True, # Indicate this is a manual B2B invoice using raw HTML
            notes_for_pdf=notes
        )
        
        try:
            db.session.commit()
            if pdf_created_successfully:
                current_app.logger.info(f"Manual B2B invoice ID {new_invoice.id} ({invoice_number}) and PDF created for B2B user ID {b2b_user_id}.")
            else:
                current_app.logger.warning(f"Manual B2B invoice ID {new_invoice.id} ({invoice_number}) created, but PDF generation FAILED. Invoice status: {new_invoice.status.value}")
            return new_invoice.id, new_invoice.invoice_number
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing manual B2B invoice for user {b2b_user_id} after PDF attempt: {e}", exc_info=True)
            raise

    def create_invoice_from_order(self, order_id, issued_by_admin_id=None):
        if not order_id: raise ValueError("Order ID is required.")
        order = Order.query.get(order_id)
        if not order: raise ValueError(f"Order {order_id} not found.")
        
        if order.invoice_id and order.invoice: # Check if invoice object exists too
            current_app.logger.info(f"Invoice for order {order_id} already exists (ID: {order.invoice.id}). Returning existing: {order.invoice.invoice_number}")
            return order.invoice.id, order.invoice.invoice_number

        user = User.query.get(order.user_id)
        if not user: raise ValueError(f"User {order.user_id} for order {order_id} not found.")
        if not order.items: raise ValueError(f"No items found for order {order_id}.")

        invoice_number = self._generate_invoice_number()
        issue_date = datetime.now(timezone.utc)
        due_date = issue_date + timedelta(days=self.config.get('INVOICE_DUE_DAYS', 30))
        
        new_invoice = Invoice(
            order_id=order_id,
            b2b_user_id=user.id if user.role == UserRoleEnum.B2B_PROFESSIONAL else None,
            invoice_number=invoice_number, issue_date=issue_date, due_date=due_date,
            total_amount=order.total_amount, currency=order.currency,
            status=InvoiceStatusEnum.DRAFT, 
            notes=order.notes_customer or order.notes_internal, # Combine notes if appropriate
            created_by_admin_id=issued_by_admin_id if user.role == UserRoleEnum.B2B_PROFESSIONAL else None # Track if admin triggered for B2B
        )
        db.session.add(new_invoice)
        db.session.flush() 
        
        invoice_items_for_pdf_and_db = []
        for order_item_model in order.items:
            # Use stored product_name and variant_description from OrderItem for historical accuracy
            desc = f"{order_item_model.product_name}"
            if order_item_model.variant_description:
                desc += f" ({order_item_model.variant_description})"
            
            inv_item = InvoiceItem(
                invoice_id=new_invoice.id, 
                description=desc, 
                quantity=order_item_model.quantity,
                unit_price=order_item_model.unit_price, 
                total_price=order_item_model.total_price,
                product_id=order_item_model.product_id,
                # Link to serialized_item_id if it's part of OrderItem and relevant for invoice
                serialized_item_id=order_item_model.serialized_item_id 
            )
            db.session.add(inv_item)
            invoice_items_for_pdf_and_db.append(inv_item)

        shipping_details = {
            "name": f"{order.customer.first_name or ''} {order.customer.last_name or ''}".strip() if order.customer else '',
            "company_name": order.customer.company_name if order.customer and order.customer.company_name else '',
            "line1": order.shipping_address_line1, "line2": order.shipping_address_line2,
            "city": order.shipping_city, "postal_code": order.shipping_postal_code, 
            "country": order.shipping_country
        }
        
        # This will use invoice_template.html as raw_html_content is not passed
        pdf_created_successfully = self._create_pdf_and_save(
            new_invoice, user, 
            invoice_items_list=invoice_items_for_pdf_and_db, 
            shipping_address_details=shipping_details, 
            notes_for_pdf=new_invoice.notes, # Use notes from invoice model
            is_b2b_manual=False # Important flag
        )
        
        try:
            # Link invoice to order
            order.invoice_id = new_invoice.id
            db.session.commit()
            if pdf_created_successfully:
                current_app.logger.info(f"Invoice ID {new_invoice.id} ({invoice_number}) and PDF created for order ID {order_id}.")
            else:
                current_app.logger.warning(f"Invoice ID {new_invoice.id} ({invoice_number}) created for order ID {order_id}, but PDF generation FAILED. Invoice status: {new_invoice.status.value}")
            return new_invoice.id, new_invoice.invoice_number
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing invoice for order {order_id} after PDF attempt: {e}", exc_info=True)
            raise
