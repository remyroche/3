# backend/services/invoice_service.py
import os
from datetime import datetime, timedelta, timezone
from flask import current_app, render_template, url_for
from weasyprint import HTML, WeasyPrintError # type: ignore
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import (
    Invoice, InvoiceItem, Order, User, UserRoleEnum, ProfessionalStatusEnum, # Added ProfessionalStatusEnum
    InvoiceStatusEnum, OrderStatusEnum, # Added OrderStatusEnum
    SerializedInventoryItem, Product, ProductWeightOption # Added ProductWeightOption
)
# Removed unused get_file_extension and allowed_file as they are not used here

class InvoiceService:
    def __init__(self):
        self.config = current_app.config

    def _generate_invoice_number(self, is_b2b=False):
        prefix = "FP" if is_b2b else "FV" # Facture Pro / Facture Vente
        last_invoice = Invoice.query.filter(Invoice.invoice_number.startswith(prefix + "-"))\
                                    .order_by(Invoice.id.desc()).first()
        current_year_str = str(datetime.now(timezone.utc).year)
        next_id_num = 1

        if last_invoice and last_invoice.invoice_number:
            parts = last_invoice.invoice_number.split('-')
            if len(parts) == 3 and parts[0] == prefix and parts[1] == current_year_str:
                try:
                    next_id_num = int(parts[2]) + 1
                except ValueError:
                    current_app.logger.warning(f"Could not parse invoice number sequence from {last_invoice.invoice_number}")
            elif parts[0] != prefix or parts[1] != current_year_str: # Reset if prefix or year changes
                next_id_num = 1
        return f"{prefix}-{current_year_str}-{next_id_num:05d}"

    def _prepare_logo_path_for_pdf(self):
        company_info = self.config.get('DEFAULT_COMPANY_INFO', {})
        logo_path_config = company_info.get('INVOICE_COMPANY_LOGO_PATH_FOR_PDF', 
                                            os.path.join(current_app.root_path, 'static_assets', 'logos', 'maison_truvra_invoice_logo.png'))
        
        if logo_path_config.startswith('file://') or logo_path_config.startswith('http://') or logo_path_config.startswith('https://'):
            return logo_path_config
        
        # Try absolute path first
        if os.path.isabs(logo_path_config) and os.path.exists(logo_path_config):
            return f'file://{os.path.abspath(logo_path_config)}'
        
        # Try path relative to app root (current_app.root_path is backend/)
        path_relative_to_root = os.path.join(current_app.root_path, '..', logo_path_config) # Go up one level for project root
        if os.path.exists(path_relative_to_root):
            return f'file://{os.path.abspath(path_relative_to_root)}'
            
        current_app.logger.warning(f"Invoice logo path could not be resolved: {logo_path_config}. Ensure it's absolute or relative to project root.")
        return None


    def _create_pdf_and_save(self, invoice_model, user_model,
                             invoice_items_for_template=None,
                             shipping_address_details=None,
                             billing_address_details=None, # Added for B2B
                             notes_for_pdf=None,
                             raw_html_content=None,
                             is_b2b_invoice=False): # Flag for B2B template
        company_info_from_config = self.config.get('DEFAULT_COMPANY_INFO', {})
        prepared_logo_path = self._prepare_logo_path_for_pdf()

        html_string_for_pdf = None

        # Use raw HTML if provided (typically for admin-generated manual invoices)
        if raw_html_content and is_b2b_invoice: # Only allow raw_html for B2B for now
            html_string_for_pdf = raw_html_content
            current_app.logger.info(f"Using raw HTML content for B2B invoice PDF: {invoice_model.invoice_number}")
        else:
            # Determine template based on B2B flag
            template_name = 'b2b_invoice_template.html' if is_b2b_invoice else 'invoice_template.html'
            
            context = {
                "invoice": invoice_model,
                "invoice_items": invoice_items_for_template or [],
                "client": user_model, # Renamed for clarity in B2B template
                "shipping_address": shipping_address_details,
                "billing_address": billing_address_details or shipping_address_details, # Fallback billing to shipping for B2C
                "company": {**company_info_from_config, 'logo_path': prepared_logo_path},
                "notes": notes_for_pdf or invoice_model.notes,
                "is_b2b": is_b2b_invoice,
                "lang_code": "fr" # TODO: Get from user preferences or request context
            }

            # Add specific VAT and total details to context for template logic
            if is_b2b_invoice:
                context['subtotal_ht'] = invoice_model.subtotal_ht
                context['total_vat_amount'] = invoice_model.total_vat_amount
                context['grand_total_ttc'] = invoice_model.grand_total_ttc
                context['net_to_pay'] = invoice_model.grand_total_ttc # Assuming net to pay is TTC for B2B
                context['vat_summary'] = invoice_model.vat_breakdown or {}
            else: # B2C context (total_amount is usually TTC)
                context['final_total_ttc_or_ht'] = invoice_model.total_amount # B2C template expects this

            try:
                with current_app.app_context(): # Ensure context for url_for if used in template
                    html_string_for_pdf = render_template(template_name, **context)
            except Exception as e_render:
                current_app.logger.error(f"Error rendering {template_name} for {invoice_model.invoice_number}: {e_render}", exc_info=True)
                invoice_model.notes = (invoice_model.notes or "") + f"\n[System Note] PDF template rendering failed: {e_render}"
                return False

        if not html_string_for_pdf:
            current_app.logger.error(f"HTML content for PDF generation is empty for invoice {invoice_model.invoice_number}.")
            return False

        try:
            # For resolving relative paths in HTML (e.g., for images if not using absolute URLs)
            weasyprint_base_url = current_app.config.get('APP_BASE_URL_FRONTEND', 'http://localhost:8000')
            pdf_file_content = HTML(string=html_string_for_pdf, base_url=weasyprint_base_url).write_pdf()

            pdf_filename = f"{invoice_model.invoice_number}.pdf"
            invoice_pdf_dir_abs = self.config['INVOICE_PDF_PATH'] # Absolute path to 'instance/uploads/generated_assets/invoices'
            os.makedirs(invoice_pdf_dir_abs, exist_ok=True)
            pdf_full_path = os.path.join(invoice_pdf_dir_abs, pdf_filename)

            with open(pdf_full_path, 'wb') as f: f.write(pdf_file_content)

            # Store path relative to ASSET_STORAGE_PATH for DB
            base_asset_path = self.config['ASSET_STORAGE_PATH'] # e.g., 'instance/uploads/generated_assets'
            invoice_model.pdf_path = os.path.relpath(pdf_full_path, base_asset_path).replace(os.sep, '/') # e.g., 'invoices/INV-XYZ.pdf'
            
            # Update invoice status if it was a draft
            if invoice_model.status == InvoiceStatusEnum.DRAFT:
                invoice_model.status = InvoiceStatusEnum.ISSUED # Or PAID if payment confirmed (e.g. B2C)
            
            current_app.logger.info(f"PDF generated for invoice {invoice_model.invoice_number} at {invoice_model.pdf_path}")
            return True
        except WeasyPrintError as e_wp:
            current_app.logger.error(f"WeasyPrint PDF generation failed for invoice {invoice_model.invoice_number}: {e_wp}", exc_info=True)
            invoice_model.notes = (invoice_model.notes or "") + f"\n[System Note] WeasyPrint PDF generation error: {e_wp}"
            return False
        except Exception as e:
            current_app.logger.error(f"General error during PDF creation/saving for invoice {invoice_model.invoice_number}: {e}", exc_info=True)
            invoice_model.notes = (invoice_model.notes or "") + f"\n[System Note] General PDF creation error: {e}"
            return False

    def create_manual_invoice(self, b2b_user_id, user_currency, line_items_data,
                              notes=None, issued_by_admin_id=None,
                              invoice_date_str=None, due_date_str=None,
                              raw_invoice_html=None):
        if not b2b_user_id or not line_items_data:
            raise ValueError("B2B User ID and line items are required for manual invoice.")
        user = User.query.filter_by(id=b2b_user_id, role=UserRoleEnum.B2B_PROFESSIONAL).first()
        if not user:
            raise ValueError(f"B2B User with ID {b2b_user_id} not found or is not a professional.")

        invoice_number = self._generate_invoice_number(is_b2b=True)
        issue_date = datetime.now(timezone.utc)
        if invoice_date_str:
            try: issue_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError: current_app.logger.warning(f"Invalid invoice_date_str: {invoice_date_str}, using current date.")
        
        due_days_setting = self.config.get('DEFAULT_COMPANY_INFO', {}).get('invoice_due_days', 30)
        due_date = issue_date + timedelta(days=due_days_setting)
        if due_date_str:
            try: due_date = datetime.strptime(due_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError: current_app.logger.warning(f"Invalid due_date_str: {due_date_str}, calculating from issue date.")

        subtotal_ht = 0
        total_vat = 0
        vat_breakdown_summary = {}
        invoice_items_for_template = []
        db_invoice_items = []

        for item_data in line_items_data:
            quantity = int(item_data['quantity'])
            unit_price_ht = float(item_data['unit_price']) # From form, assumed HT
            vat_rate = float(item_data.get('vat_rate', 20.0)) # Default VAT if not specified

            line_total_ht = quantity * unit_price_ht
            line_vat_amount = line_total_ht * (vat_rate / 100)
            line_total_ttc = line_total_ht + line_vat_amount

            subtotal_ht += line_total_ht
            total_vat += line_vat_amount
            
            vat_rate_key = f"{vat_rate:.1f}" # Consistent key e.g. "20.0"
            vat_breakdown_summary[vat_rate_key] = vat_breakdown_summary.get(vat_rate_key, 0) + line_vat_amount

            db_item = InvoiceItem(
                description=item_data['description'], quantity=quantity,
                unit_price=unit_price_ht, total_price=line_total_ht, # Store HT line total
                vat_rate=vat_rate, # Store applied VAT rate for this item
                product_id=item_data.get('product_id')
            )
            db_invoice_items.append(db_item)

            invoice_items_for_template.append({
                'description': item_data['description'], 'quantity': quantity,
                'unit_price': unit_price_ht, 'total_price_ht': line_total_ht, # For template
                'vat_rate': vat_rate, 'total_price_ttc': line_total_ttc # For template
            })
        
        grand_total_ttc_calc = subtotal_ht + total_vat

        new_invoice = Invoice(
            b2b_user_id=b2b_user_id, invoice_number=invoice_number, issue_date=issue_date, due_date=due_date,
            total_amount=subtotal_ht, # Store subtotal HT here for B2B manual invoice
            currency=user_currency or user.currency or self.config.get('DEFAULT_CURRENCY', 'EUR'),
            status=InvoiceStatusEnum.DRAFT, notes=notes, created_by_admin_id=issued_by_admin_id,
            subtotal_ht=round(subtotal_ht, 2),
            total_vat_amount=round(total_vat, 2),
            grand_total_ttc=round(grand_total_ttc_calc, 2),
            vat_breakdown=vat_breakdown_summary,
            client_company_name_snapshot=user.company_name,
            client_vat_number_snapshot=user.vat_number,
            client_siret_number_snapshot=user.siret_number
        )
        db.session.add(new_invoice)
        db.session.flush()

        for inv_item_obj in db_invoice_items:
            inv_item_obj.invoice_id = new_invoice.id
            db.session.add(inv_item_obj)

        # Prepare billing/shipping details for the PDF from the User model
        billing_address_for_pdf = {
            "line1": user.billing_address_line1 or user.shipping_address_line1, # Fallback
            "line2": user.billing_address_line2 or user.shipping_address_line2,
            "city": user.billing_city or user.shipping_city,
            "postal_code": user.billing_postal_code or user.shipping_postal_code,
            "country": user.billing_country or user.shipping_country
        }
        delivery_address_for_pdf = { # Assume delivery can be different, or defaults to billing/shipping
            "line1": user.shipping_address_line1,
            "line2": user.shipping_address_line2,
            "city": user.shipping_city,
            "postal_code": user.shipping_postal_code,
            "country": user.shipping_country
        }


        pdf_created = self._create_pdf_and_save(
            new_invoice, user,
            invoice_items_for_template=invoice_items_for_template,
            billing_address_details=billing_address_for_pdf,
            shipping_address_details=delivery_address_for_pdf, # Could be same as billing
            notes_for_pdf=notes,
            raw_html_content=raw_invoice_html, # This comes from admin_create_invoice.html preview
            is_b2b_invoice=True
        )
        
        # If PDF created and status was DRAFT, it's now ISSUED (by _create_pdf_and_save)
        # Or, if it was a "Save as Draft" action, keep it DRAFT.
        # For now, creating PDF implies it's ready to be issued.

        try:
            db.session.commit()
            current_app.logger.info(f"Manual B2B Invoice {invoice_number} (ID: {new_invoice.id}) created by admin {issued_by_admin_id} for user {b2b_user_id}. PDF Status: {pdf_created}")
            return new_invoice.id, new_invoice.invoice_number, new_invoice.status.value
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing manual B2B invoice {invoice_number}: {e}", exc_info=True)
            raise

        def create_b2c_invoice_from_order(self, order_id):
        # This is the original create_invoice_from_order, renamed for clarity
        if not order_id: raise ValueError("Order ID is required for B2C invoice.")
        order = Order.query.get(order_id)
        if not order: raise ValueError(f"Order {order_id} not found.")
        if order.is_b2b_order: # Ensure it's not a B2B order
             raise ValueError(f"Order {order_id} is a B2B order. Use create_b2b_invoice_from_order instead.")


        if order.invoice_id and order.invoice:
            current_app.logger.info(f"B2C Invoice for order {order_id} already exists (ID: {order.invoice.id}).")
            return order.invoice.id, order.invoice.invoice_number, order.invoice.status.value

        user = order.customer
        if not user: raise ValueError(f"Customer for order {order_id} not found.")
        if not order.items: raise ValueError(f"No items found for order {order_id}.")

        invoice_number = self._generate_invoice_number(is_b2b=False)
        issue_date = datetime.now(timezone.utc)
        
        # B2C invoices are typically for immediate payment or already paid orders
        due_date = issue_date # Or None if not applicable
        invoice_status = InvoiceStatusEnum.PAID if order.status == OrderStatusEnum.PAID or order.status == OrderStatusEnum.COMPLETED else InvoiceStatusEnum.ISSUED

        new_invoice = Invoice(
            order_id=order_id,
            invoice_number=invoice_number, issue_date=issue_date, due_date=due_date,
            total_amount=order.total_amount, # This is TTC for B2C
            currency=order.currency,
            status=InvoiceStatusEnum.DRAFT, # Will be updated by _create_pdf_and_save
            notes=order.notes_customer,
            payment_date=order.payment_date or order.order_date # Snapshot payment date
        )
        db.session.add(new_invoice)
        db.session.flush()

        invoice_items_for_template = []
        for order_item_model in order.items:
            desc = order_item_model.product_name or "Produit"
            if order_item_model.variant_description:
                desc += f" ({order_item_model.variant_description})"
            
            db_inv_item = InvoiceItem(
                invoice_id=new_invoice.id, description=desc,
                quantity=order_item_model.quantity,
                unit_price=order_item_model.unit_price, # This is TTC unit price for B2C
                total_price=order_item_model.total_price, # Line total TTC
                product_id=order_item_model.product_id,
                serialized_item_id=order_item_model.serialized_item_id
            )
            db.session.add(db_inv_item)

            item_template_data = {
                'description': desc, 'quantity': order_item_model.quantity,
                'unit_price': order_item_model.unit_price, # TTC
                'total_price': order_item_model.total_price, # TTC
                'passport_url': None, 'uid_for_passport': None,
                'product_name_for_passport': order_item_model.product_name or 'Produit',
                'passport_urls': []
            }
            # ... (passport URL logic as before if needed for B2C invoices) ...
            invoice_items_for_template.append(item_template_data)

        shipping_details = {
            "name": f"{order.customer.first_name or ''} {order.customer.last_name or ''}".strip() if order.customer else '',
            "line1": order.shipping_address_line1, "line2": order.shipping_address_line2,
            "city": order.shipping_city, "postal_code": order.shipping_postal_code,
            "country": order.shipping_country
        }
        
        # For B2C, billing is usually same as shipping, unless explicitly different in order
        billing_details = shipping_details # Default for B2C

        pdf_created = self._create_pdf_and_save(
            new_invoice, user,
            invoice_items_for_template=invoice_items_for_template,
            shipping_address_details=shipping_details,
            billing_address_details=billing_details,
            notes_for_pdf=new_invoice.notes,
            is_b2b_invoice=False # Important flag
        )
        
        if pdf_created and new_invoice.status == InvoiceStatusEnum.DRAFT:
            # If order was paid, set invoice to PAID, otherwise ISSUED
            new_invoice.status = InvoiceStatusEnum.PAID if order.status in [OrderStatusEnum.PAID, OrderStatusEnum.PROCESSING, OrderStatusEnum.AWAITING_SHIPMENT, OrderStatusEnum.SHIPPED, OrderStatusEnum.DELIVERED, OrderStatusEnum.COMPLETED] else InvoiceStatusEnum.ISSUED

        try:
            order.invoice_id = new_invoice.id
            db.session.commit()
            current_app.logger.info(f"B2C Invoice {new_invoice.invoice_number} (ID: {new_invoice.id}) created for order {order_id}. PDF: {pdf_created}, Status: {new_invoice.status.value}")
            return new_invoice.id, new_invoice.invoice_number, new_invoice.status.value
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing B2C invoice for order {order_id}: {e}", exc_info=True)
            raise

    def create_b2b_invoice_from_order(self, order_id, issued_by_admin_id=None):
        # New method specifically for B2B orders
        if not order_id: raise ValueError("Order ID is required for B2B invoice.")
        order = Order.query.get(order_id)
        if not order: raise ValueError(f"Order {order_id} not found.")
        if not order.is_b2b_order:
            raise ValueError(f"Order {order_id} is not a B2B order. Use create_b2c_invoice_from_order instead.")
        
        if order.invoice_id and order.invoice:
            current_app.logger.info(f"B2B Invoice for order {order_id} already exists (ID: {order.invoice.id}).")
            return order.invoice.id, order.invoice.invoice_number, order.invoice.status.value

        user = order.customer
        if not user or user.role != UserRoleEnum.B2B_PROFESSIONAL:
             raise ValueError(f"Order {order_id} is not linked to a valid B2B professional customer.")
        if not order.items: raise ValueError(f"No items found for B2B order {order_id}.")

        invoice_number = self._generate_invoice_number(is_b2b=True)
        issue_date = datetime.now(timezone.utc)
        due_days_setting = self.config.get('DEFAULT_COMPANY_INFO', {}).get('invoice_due_days', 30)
        due_date = issue_date + timedelta(days=due_days_setting)
        
        # B2B: Calculate HT totals and VAT breakdown
        subtotal_ht_calc = 0
        total_vat_calc = 0
        vat_breakdown_summary = {}
        invoice_items_for_template = []
        db_invoice_items = []

        for order_item_model in order.items:
            # For B2B, order_item.unit_price is assumed to be HT
            unit_price_ht = order_item_model.unit_price
            quantity = order_item_model.quantity
            line_total_ht = unit_price_ht * quantity
            
            # TODO: Determine VAT rate for B2B items. This needs a source.
            # For now, assuming a default VAT rate (e.g., 20%) or product-specific VAT rate if available.
            # This logic needs to be robust based on your product setup.
            # Example: vat_rate_percent = order_item_model.product.vat_rate_percent if order_item_model.product else 20.0
            vat_rate_percent = 20.0 # Placeholder: Needs to be dynamic
            
            line_vat_amount = line_total_ht * (vat_rate_percent / 100)
            line_total_ttc = line_total_ht + line_vat_amount

            subtotal_ht_calc += line_total_ht
            total_vat_calc += line_vat_amount
            vat_rate_key = f"{vat_rate_percent:.1f}"
            vat_breakdown_summary[vat_rate_key] = vat_breakdown_summary.get(vat_rate_key, 0) + line_vat_amount

            desc = order_item_model.product_name or "Produit Pro"
            if order_item_model.variant_description:
                desc += f" ({order_item_model.variant_description})"

            db_item = InvoiceItem(
                description=desc, quantity=quantity, unit_price=unit_price_ht,
                total_price=line_total_ht, vat_rate=vat_rate_percent,
                product_id=order_item_model.product_id,
                serialized_item_id=order_item_model.serialized_item_id
            )
            db_invoice_items.append(db_item)

            invoice_items_for_template.append({
                'description': desc, 'quantity': quantity,
                'unit_price': unit_price_ht, 'total_price_ht': line_total_ht,
                'vat_rate': vat_rate_percent, 'total_price_ttc': line_total_ttc,
                'passport_urls': [], # Populate if applicable
                'product_name_for_passport': order_item_model.product_name or 'Produit Pro'
            })
        
        grand_total_ttc_calc = subtotal_ht_calc + total_vat_calc

        new_invoice = Invoice(
            order_id=order_id, b2b_user_id=user.id,
            invoice_number=invoice_number, issue_date=issue_date, due_date=due_date,
            total_amount=subtotal_ht_calc, # Main total_amount is HT for B2B invoices
            currency=order.currency,
            status=InvoiceStatusEnum.DRAFT, # PDF generation will set to ISSUED
            notes=order.notes_internal or order.notes_customer,
            created_by_admin_id=issued_by_admin_id,
            subtotal_ht=round(subtotal_ht_calc, 2),
            total_vat_amount=round(total_vat_calc, 2),
            grand_total_ttc=round(grand_total_ttc_calc, 2),
            vat_breakdown=vat_breakdown_summary,
            client_company_name_snapshot=user.company_name,
            client_vat_number_snapshot=user.vat_number,
            client_siret_number_snapshot=user.siret_number,
            po_reference_snapshot=order.purchase_order_reference
        )
        db.session.add(new_invoice)
        db.session.flush()

        for inv_item_obj in db_invoice_items:
            inv_item_obj.invoice_id = new_invoice.id
            db.session.add(inv_item_obj)

        # B2B Address details for PDF
        billing_address_pdf = {
            "line1": user.billing_address_line1, "line2": user.billing_address_line2,
            "city": user.billing_city, "postal_code": user.billing_postal_code,
            "country": user.billing_country
        }
        shipping_address_pdf = {
            "line1": order.shipping_address_line1 or user.shipping_address_line1, # Order specific or user default
            "line2": order.shipping_address_line2 or user.shipping_address_line2,
            "city": order.shipping_city or user.shipping_city,
            "postal_code": order.shipping_postal_code or user.shipping_postal_code,
            "country": order.shipping_country or user.shipping_country
        }

        pdf_created = self._create_pdf_and_save(
            new_invoice, user,
            invoice_items_for_template=invoice_items_for_template,
            billing_address_details=billing_address_pdf,
            shipping_address_details=shipping_address_pdf,
            notes_for_pdf=new_invoice.notes,
            is_b2b_invoice=True
        )
        
        # If PDF created, invoice status should be ISSUED (or PAID if order status reflects that)
        if pdf_created and new_invoice.status == InvoiceStatusEnum.DRAFT:
            new_invoice.status = InvoiceStatusEnum.PAID if order.status == OrderStatusEnum.PAID else InvoiceStatusEnum.ISSUED


        try:
            order.invoice_id = new_invoice.id
            db.session.commit()
            current_app.logger.info(f"B2B Invoice {new_invoice.invoice_number} (ID: {new_invoice.id}) created for order {order_id}. PDF: {pdf_created}, Status: {new_invoice.status.value}")
            return new_invoice.id, new_invoice.invoice_number, new_invoice.status.value
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing B2B invoice for order {order_id}: {e}", exc_info=True)
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
