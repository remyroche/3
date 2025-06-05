# backend/services/invoice_service.py
import os
from datetime import datetime, timedelta, timezone
from flask import current_app, render_template, url_for
from weasyprint import HTML, WeasyPrintError
from sqlalchemy.exc import IntegrityError 

from .. import db 
from ..models import (
    Invoice, InvoiceItem, Order, User, UserRoleEnum, InvoiceStatusEnum,
    SerializedInventoryItem, Product # Import SerializedInventoryItem and Product
)

class InvoiceService:
    def __init__(self):
        self.config = current_app.config

    def _generate_invoice_number(self):
        # ... (existing logic) ...
        last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
        current_year_str = str(datetime.now(timezone.utc).year)
        next_id_num = 1
        
        if last_invoice and last_invoice.invoice_number:
            parts = last_invoice.invoice_number.split('-')
            if len(parts) == 3 and parts[0] == 'INV' and parts[1] == current_year_str:
                try:
                    next_id_num = int(parts[2]) + 1
                except ValueError:
                    current_app.logger.warning(f"Could not parse invoice number sequence from {last_invoice.invoice_number}")
                    next_id_num = 1 
            elif parts[0] != 'INV' or parts[1] != current_year_str :
                next_id_num = 1
        return f"INV-{current_year_str}-{next_id_num:05d}"

    def _prepare_logo_path_for_pdf(self):
        # ... (existing logic) ...
        company_info = self.config.get('DEFAULT_COMPANY_INFO', {})
        logo_path_config = company_info.get('INVOICE_COMPANY_LOGO_PATH_FOR_PDF') 
        if not logo_path_config:
            current_app.logger.warning("INVOICE_COMPANY_LOGO_PATH_FOR_PDF not configured.")
            return None
        if logo_path_config.startswith('file://') or logo_path_config.startswith('http://') or logo_path_config.startswith('https://'):
            return logo_path_config
        if os.path.isabs(logo_path_config) and os.path.exists(logo_path_config):
            return f'file://{os.path.abspath(logo_path_config)}'
        path_relative_to_root = os.path.join(current_app.root_path, logo_path_config)
        if os.path.exists(path_relative_to_root):
            return f'file://{os.path.abspath(path_relative_to_root)}'
        current_app.logger.warning(f"Invoice logo path could not be resolved: {logo_path_config}")
        return None

    def _create_pdf_and_save(self, invoice_model, user_model, 
                             invoice_items_for_template=None, # Changed name for clarity
                             shipping_address_details=None, 
                             notes_for_pdf=None,
                             raw_html_content=None, 
                             is_b2b_manual=False):
        company_info = self.config.get('DEFAULT_COMPANY_INFO', {})
        prepared_logo_path_for_template = self._prepare_logo_path_for_pdf()

        html_string_for_pdf = None

        if raw_html_content and is_b2b_manual:
            html_string_for_pdf = raw_html_content
            # Ensure logo path in raw_html_content is absolute or handled by base_url
            current_app.logger.info(f"Using raw HTML content for B2B invoice PDF: {invoice_model.invoice_number}")
        else:
            # Prepare context for Jinja2 template
            # The invoice_items_for_template should be a list of dicts with all necessary fields
            context = {
                "invoice": invoice_model, 
                "invoice_items": invoice_items_for_template or [],
                "user": user_model, 
                "shipping_address": shipping_address_details, 
                "company": {**company_info, 'logo_path': prepared_logo_path_for_template},
                "notes": notes_for_pdf or invoice_model.notes,
                "is_b2b": user_model.role == UserRoleEnum.B2B_PROFESSIONAL,
                "lang_code": "fr" # Default or get from user/request
            }
            # Add VAT details to context if applicable
            # For example, if invoice_model has vat_details and total_vat_amount attributes
            if hasattr(invoice_model, 'vat_details') and invoice_model.vat_details:
                context['invoice_vat_details'] = invoice_model.vat_details # Renamed for clarity in template
                context['invoice_total_vat_amount'] = getattr(invoice_model, 'total_vat_amount', 0.0)
                # final_total needs to be calculated or passed if it's total_amount (HT) + total_vat_amount
                context['invoice_final_total_ttc_or_ht'] = invoice_model.total_amount + getattr(invoice_model, 'total_vat_amount', 0.0)

            else: # No VAT details, assume total_amount is the final amount
                context['invoice_final_total_ttc_or_ht'] = invoice_model.total_amount


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
            weasyprint_base_url = current_app.config.get('APP_BASE_URL_FRONTEND') # For resolving relative paths in HTML
            pdf_file_content = HTML(string=html_string_for_pdf, base_url=weasyprint_base_url).write_pdf()
            
            pdf_filename = f"{invoice_model.invoice_number}.pdf"
            invoice_pdf_dir_abs = self.config['INVOICE_PDF_PATH'] 
            os.makedirs(invoice_pdf_dir_abs, exist_ok=True)
            pdf_full_path = os.path.join(invoice_pdf_dir_abs, pdf_filename)
            
            with open(pdf_full_path, 'wb') as f: f.write(pdf_file_content)
            
            base_asset_path = self.config['ASSET_STORAGE_PATH']
            invoice_model.pdf_path = os.path.relpath(pdf_full_path, base_asset_path).replace(os.sep, '/')
            
            if invoice_model.status == InvoiceStatusEnum.DRAFT : # Only upgrade from DRAFT to ISSUED
                 invoice_model.status = InvoiceStatusEnum.ISSUED
            current_app.logger.info(f"PDF generated for invoice {invoice_model.invoice_number} at {invoice_model.pdf_path}")
            return True
        except WeasyPrintError as e_wp:
            current_app.logger.error(f"WeasyPrint PDF generation failed for invoice {invoice_model.invoice_number}: {e_wp}", exc_info=True)
            invoice_model.notes = (invoice_model.notes or "") + f"\n[System Note] PDF generation failed: {e_wp}"
            return False
        except Exception as e:
            current_app.logger.error(f"General error during PDF creation/saving for invoice {invoice_model.invoice_number}: {e}", exc_info=True)
            invoice_model.notes = (invoice_model.notes or "") + f"\n[System Note] PDF creation error: {e}"
            return False

    def create_manual_invoice(self, b2b_user_id, user_currency, line_items_data, 
                              notes=None, issued_by_admin_id=None, 
                              invoice_date_str=None, due_date_str=None,
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
        
        # --- Calculate totals and prepare items for DB and template ---
        total_amount_ht = 0
        invoice_items_for_template = [] # List of dicts for the template
        db_invoice_items = [] # List of InvoiceItem model instances for DB

        for item_data in line_items_data:
            # ... (validation for description, quantity, unit_price) ...
            quantity = int(item_data['quantity'])
            unit_price = float(item_data['unit_price']) # Assuming this is HT from form
            line_total_ht = quantity * unit_price
            total_amount_ht += line_total_ht
            
            db_item = InvoiceItem(
                description=item_data['description'], quantity=quantity,
                unit_price=unit_price, total_price=line_total_ht,
                product_id=item_data.get('product_id') # Optional: if line item is linked to a product
            )
            db_invoice_items.append(db_item)

            # For template context, if not using raw_html
            item_template_data = {
                'description': item_data['description'], 'quantity': quantity,
                'unit_price': unit_price, 'total_price': line_total_ht,
                'passport_url': None, 'uid_for_passport': None, # Manual B2B invoices might not have these unless items are serialized
                'product_name_for_passport': item_data.get('product_name_for_passport', item_data['description'])
            }
            invoice_items_for_template.append(item_template_data)
        
        # Placeholder for VAT calculation if needed for display or totals
        # total_vat_amount = 0.0 # Calculate based on item_data['vat_rate'] if provided
        # final_total_ttc_or_ht = total_amount_ht + total_vat_amount

        new_invoice = Invoice(
            b2b_user_id=b2b_user_id, invoice_number=invoice_number, issue_date=issue_date, due_date=due_date,
            total_amount=round(total_amount_ht, 2), # Storing HT amount, or final TTC if no VAT breakdown
            currency=user_currency or user.currency or self.config.get('DEFAULT_CURRENCY', 'EUR'),
            status=InvoiceStatusEnum.DRAFT, notes=notes,
            created_by_admin_id=issued_by_admin_id
            # Add vat_details, total_vat_amount if calculated and stored on Invoice model
        )
        # new_invoice.final_total_ttc_or_ht = final_total_ttc_or_ht # If you add this to model for display

        db.session.add(new_invoice)
        db.session.flush() 

        for inv_item_obj in db_invoice_items:
            inv_item_obj.invoice_id = new_invoice.id
            db.session.add(inv_item_obj)
        
        pdf_created_successfully = self._create_pdf_and_save(
            new_invoice, user, 
            invoice_items_for_template=invoice_items_for_template, # Pass the list of dicts
            raw_html_content=raw_invoice_html, 
            is_b2b_manual=True,
            notes_for_pdf=notes
        )
        
        try:
            db.session.commit()
            # ... (logging) ...
            return new_invoice.id, new_invoice.invoice_number
        except Exception as e:
            db.session.rollback(); # ... (error logging) ...
            raise

    def create_invoice_from_order(self, order_id, issued_by_admin_id=None):
        if not order_id: raise ValueError("Order ID is required.")
        order = Order.query.get(order_id)
        if not order: raise ValueError(f"Order {order_id} not found.")
        
        if order.invoice_id and order.invoice:
            current_app.logger.info(f"Invoice for order {order_id} already exists (ID: {order.invoice.id}).")
            return order.invoice.id, order.invoice.invoice_number

        user = order.customer # User.query.get(order.user_id)
        if not user: raise ValueError(f"User for order {order_id} not found.")
        if not order.items: raise ValueError(f"No items found for order {order_id}.")

        invoice_number = self._generate_invoice_number()
        issue_date = datetime.now(timezone.utc)
        due_date = issue_date + timedelta(days=self.config.get('INVOICE_DUE_DAYS', 30))
        
        new_invoice = Invoice(
            order_id=order_id,
            b2b_user_id=user.id if user.role == UserRoleEnum.B2B_PROFESSIONAL else None,
            invoice_number=invoice_number, issue_date=issue_date, due_date=due_date,
            total_amount=order.total_amount, currency=order.currency, # This is usually final paid amount for B2C
            status=InvoiceStatusEnum.DRAFT, # PDF generation will set to ISSUED or PAID
            notes=order.notes_customer or order.notes_internal,
            created_by_admin_id=issued_by_admin_id if user.role == UserRoleEnum.B2B_PROFESSIONAL else None
        )
        # Set final total for template based on order (usually TTC for B2C)
        new_invoice.final_total_ttc_or_ht = order.total_amount
        new_invoice.payment_date = order.payment_date if hasattr(order, 'payment_date') else order.order_date # Assuming order has payment_date


        db.session.add(new_invoice)
        db.session.flush() 
        
        items_for_template_and_db = [] # This will be a list of dicts for template, and list of models for DB
        
        for order_item_model in order.items:
            desc = order_item_model.product_name or "Produit"
            if order_item_model.variant_description:
                desc += f" ({order_item_model.variant_description})"
            
            # Create InvoiceItem for DB
            db_inv_item = InvoiceItem(
                invoice_id=new_invoice.id, description=desc, 
                quantity=order_item_model.quantity,
                unit_price=order_item_model.unit_price, 
                total_price=order_item_model.total_price,
                product_id=order_item_model.product_id,
                serialized_item_id=order_item_model.serialized_item_id 
            )
            db.session.add(db_inv_item)

            # Prepare item data for the template
            item_template_data = {
                'description': desc,
                'quantity': order_item_model.quantity,
                'unit_price': order_item_model.unit_price,
                'total_price': order_item_model.total_price,
                'product_name_for_passport': order_item_model.product_name or 'Produit',
                'passport_url': None,
                'uid_for_passport': None,
                'passport_urls': [] # For multiple UIDs if one line item has many serialized items
            }

            # If the order item is linked to a serialized item, fetch its passport URL and UID
            if order_item_model.serialized_item_id:
                s_item = SerializedInventoryItem.query.get(order_item_model.serialized_item_id)
                if s_item and s_item.passport_url:
                    try:
                        # Assuming serve_public_asset is correctly configured for public access
                        item_template_data['passport_url'] = url_for('serve_public_asset', filepath=s_item.passport_url, _external=True)
                        item_template_data['uid_for_passport'] = s_item.item_uid
                    except Exception as e_url:
                        current_app.logger.warning(f"Could not generate passport URL for item UID {s_item.item_uid}: {e_url}")
            # If an OrderItem could link to multiple SerializedInventoryItems (e.g. quantity > 1 and serialized)
            # you would loop through those here and populate item_template_data['passport_urls']
            # For example, if OrderItem had a relationship `serialized_items_for_this_line`:
            # for s_item_in_line in order_item_model.serialized_items_for_this_line:
            #     if s_item_in_line.passport_url:
            #         try:
            #             url = url_for('serve_public_asset', filepath=s_item_in_line.passport_url, _external=True)
            #             item_template_data['passport_urls'].append({'url': url, 'uid': s_item_in_line.item_uid})
            #         except: pass
            
            items_for_template_and_db.append(item_template_data)

        shipping_details = {
            "name": f"{order.customer.first_name or ''} {order.customer.last_name or ''}".strip() if order.customer else '',
            "company_name": order.customer.company_name if order.customer and order.customer.company_name else '',
            "line1": order.shipping_address_line1, "line2": order.shipping_address_line2,
            "city": order.shipping_city, "postal_code": order.shipping_postal_code, 
            "country": order.shipping_country
        }
        
        pdf_created_successfully = self._create_pdf_and_save(
            new_invoice, user, 
            invoice_items_for_template=items_for_template_and_db, 
            shipping_address_details=shipping_details, 
            notes_for_pdf=new_invoice.notes,
            is_b2b_manual=False
        )
        
        if pdf_created_successfully and new_invoice.status == InvoiceStatusEnum.DRAFT: # If still draft after PDF attempt
             # If PDF was generated successfully, invoice should be at least ISSUED
             # If it's a B2C paid order, it could go directly to PAID status here
            if order.status == OrderStatusEnum.PAID or order.status == OrderStatusEnum.COMPLETED:
                 new_invoice.status = InvoiceStatusEnum.PAID
            else:
                 new_invoice.status = InvoiceStatusEnum.ISSUED

        try:
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

            current_app.logger.error(f"Error committing invoice for order {order_id} after PDF attempt: {e}", exc_info=True)
            raise
