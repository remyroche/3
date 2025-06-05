# backend/services/invoice_service.py
import os
from datetime import datetime, timedelta, timezone
from flask import current_app, render_template, url_for
from weasyprint import HTML, WeasyPrintError # type: ignore
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import (
    Invoice, InvoiceItem, Order, User, UserRoleEnum, InvoiceStatusEnum,
    SerializedInventoryItem, Product, ProfessionalDocument, ProductLocalization, # Added ProductLocalization
    OrderStatusEnum, CategoryLocalization # Added CategoryLocalization
)
from ..utils import format_datetime_for_display, sanitize_input

class InvoiceService:
    def __init__(self):
        self.config = current_app.config
        self.audit_logger = current_app.audit_log_service

    def _generate_invoice_number(self, is_b2b=False):
        prefix = "B2B-INV" if is_b2b else "INV"
        last_invoice = Invoice.query.filter(Invoice.invoice_number.like(f"{prefix}-%"))\
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
            elif parts[0] != prefix or parts[1] != current_year_str:
                 next_id_num = 1
        
        return f"{prefix}-{current_year_str}-{next_id_num:05d}"

    def _prepare_logo_path_for_pdf(self):
        company_info_invoice_config = self.config.get('DEFAULT_COMPANY_INFO_INVOICE', {})
        logo_path_config_key = 'LOGO_PATH_FOR_PDF_ABSOLUTE_OR_STATIC'
        logo_path_config = company_info_invoice_config.get(logo_path_config_key)
        
        if not logo_path_config:
            current_app.logger.warning(f"{logo_path_config_key} not configured in DEFAULT_COMPANY_INFO_INVOICE.")
            return None

        if os.path.isabs(logo_path_config) and os.path.exists(logo_path_config):
            return f'file://{os.path.abspath(logo_path_config)}'
        
        # Try path relative to Flask root (where 'static_assets' or similar might be)
        # Assumes logo_path_config might be like 'static_assets/logos/invoice_logo.png'
        path_relative_to_root = os.path.join(current_app.root_path, logo_path_config)
        if os.path.exists(path_relative_to_root):
            return f'file://{os.path.abspath(path_relative_to_root)}'
        
        # Fallback: try relative to 'instance' folder (common for user uploads or generated assets)
        path_relative_to_instance = os.path.join(current_app.instance_path, logo_path_config)
        if os.path.exists(path_relative_to_instance):
             return f'file://{os.path.abspath(path_relative_to_instance)}'

        current_app.logger.warning(f"Invoice logo path could not be resolved to an existing absolute file: {logo_path_config}")
        return None


    def _create_pdf_and_save(self, invoice_model, user_model, order_model, # order_model can be None for manual B2B
                             invoice_items_for_template=None,
                             is_b2b_invoice=False,
                             raw_html_content=None): # HTML from admin preview for manual B2B
        company_config = self.config.get('DEFAULT_COMPANY_INFO_INVOICE', {})
        prepared_logo_path = self._prepare_logo_path_for_pdf()

        html_string_for_pdf = None
        template_name = 'b2b_invoice_template.html' if is_b2b_invoice else 'invoice_template.html'

        if raw_html_content and is_b2b_invoice:
            html_string_for_pdf = raw_html_content
            current_app.logger.info(f"Using raw HTML content for B2B invoice PDF: {invoice_model.invoice_number}")
        else:
            client_details = {}
            if user_model:
                client_details = {
                    'company_name': user_model.company_name,
                    'first_name': user_model.first_name,
                    'last_name': user_model.last_name,
                    'contact_name': f"{user_model.first_name or ''} {user_model.last_name or ''}".strip(),
                    'email': user_model.email,
                    'siret_number': user_model.siret_number,
                    'vat_number': user_model.vat_number,
                    'billing_address': {
                        'line1': user_model.billing_address_line1 or (order_model.billing_address_line1 if order_model else None) or "N/A",
                        'line2': user_model.billing_address_line2 or (order_model.billing_address_line2 if order_model else None),
                        'city': user_model.billing_city or (order_model.billing_city if order_model else None) or "N/A",
                        'postal_code': user_model.billing_postal_code or (order_model.billing_postal_code if order_model else None) or "N/A",
                        'country': user_model.billing_country or (order_model.billing_country if order_model else None) or "N/A",
                    },
                    'delivery_address': { # Primarily from order, fallback to user's billing if not on order
                        'line1': order_model.shipping_address_line1 if order_model else (user_model.shipping_address_line1 or user_model.billing_address_line1 or "N/A"),
                        'line2': order_model.shipping_address_line2 if order_model else (user_model.shipping_address_line2 or user_model.billing_address_line2),
                        'city': order_model.shipping_city if order_model else (user_model.shipping_city or user_model.billing_city or "N/A"),
                        'postal_code': order_model.shipping_postal_code if order_model else (user_model.shipping_postal_code or user_model.billing_postal_code or "N/A"),
                        'country': order_model.shipping_country if order_model else (user_model.shipping_country or user_model.billing_country or "N/A"),
                    },
                    'delivery_company_name': (order_model.shipping_company_name if order_model and order_model.shipping_company_name else user_model.company_name)
                }

            # Use pre-calculated totals from invoice_model if available (set during manual creation or order conversion)
            context = {
                "invoice": invoice_model,
                "invoice_items": invoice_items_for_template or [], # These items should have ht and ttc totals calculated
                "client": client_details,
                "company": {**company_config, 'logo_path': prepared_logo_path},
                "order": order_model,
                "is_b2b": is_b2b_invoice,
                "lang_code": user_model.preferred_language if user_model and hasattr(user_model, 'preferred_language') and user_model.preferred_language else 'fr',
                # Directly use values from invoice_model for totals if they exist
                "subtotal_ht": invoice_model.subtotal_ht,
                "vat_summary": invoice_model.vat_breakdown or {},
                "total_vat_amount": invoice_model.total_vat_amount,
                "grand_total_ttc": invoice_model.grand_total_ttc,
                "net_to_pay": invoice_model.net_to_pay or invoice_model.grand_total_ttc # Fallback for net_to_pay
            }
            # Add PO reference if it's a B2B invoice and order exists
            if is_b2b_invoice and order_model and order_model.purchase_order_reference:
                context["invoice_po_reference"] = order_model.purchase_order_reference
            elif is_b2b_invoice and invoice_model.po_reference_snapshot: # For manual B2B invoices
                 context["invoice_po_reference"] = invoice_model.po_reference_snapshot


            try:
                with current_app.app_context():
                    html_string_for_pdf = render_template(template_name, **context)
            except Exception as e_render:
                current_app.logger.error(f"Error rendering {template_name} for {invoice_model.invoice_number}: {e_render}", exc_info=True)
                invoice_model.notes = (invoice_model.notes or "") + f"\n[System Note] PDF template rendering failed: {e_render}"
                return False

        if not html_string_for_pdf: # Should be caught by template rendering error
            current_app.logger.error(f"HTML content for PDF generation is empty for invoice {invoice_model.invoice_number}.")
            return False

        try:
            # For local file paths (like logo), base_url might need to be the app's root or instance path.
            # If logo_path is an absolute file:// URL, base_url is less critical for that specific asset.
            weasyprint_base_url = current_app.config.get('APP_BASE_URL_FOR_PDF_ASSETS', current_app.root_path)

            pdf_file_content = HTML(string=html_string_for_pdf, base_url=f"file://{weasyprint_base_url}/").write_pdf()
            
            pdf_filename = f"{invoice_model.invoice_number}.pdf"
            invoice_pdf_dir_abs = self.config['INVOICE_PDF_PATH']
            os.makedirs(invoice_pdf_dir_abs, exist_ok=True)
            pdf_full_path = os.path.join(invoice_pdf_dir_abs, pdf_filename)
            
            with open(pdf_full_path, 'wb') as f: f.write(pdf_file_content)
            
            base_asset_path = self.config['ASSET_STORAGE_PATH']
            invoice_model.pdf_path = os.path.relpath(pdf_full_path, base_asset_path).replace(os.sep, '/')
            
            if invoice_model.status == InvoiceStatusEnum.DRAFT :
                 invoice_model.status = InvoiceStatusEnum.ISSUED
                 if not is_b2b_invoice and order_model and order_model.status == OrderStatusEnum.PAID:
                     invoice_model.status = InvoiceStatusEnum.PAID
                     invoice_model.payment_date = order_model.payment_date or datetime.now(timezone.utc)

            current_app.logger.info(f"PDF generated for invoice {invoice_model.invoice_number} at {invoice_model.pdf_path}")
            return True
        except WeasyPrintError as e_wp: # type: ignore
            current_app.logger.error(f"WeasyPrint PDF generation failed for invoice {invoice_model.invoice_number}: {e_wp}", exc_info=True)
            invoice_model.notes = (invoice_model.notes or "") + f"\n[System Note] PDF generation failed (WeasyPrint): {e_wp}"
            return False
        except Exception as e:
            current_app.logger.error(f"General error during PDF creation/saving for invoice {invoice_model.invoice_number}: {e}", exc_info=True)
            invoice_model.notes = (invoice_model.notes or "") + f"\n[System Note] PDF creation error: {e}"
            return False

    def create_manual_invoice(self, b2b_user_id, user_currency, line_items_data,
                              notes=None, issued_by_admin_id=None,
                              invoice_date_str=None, due_date_str=None,
                              raw_invoice_html=None, # HTML from admin create invoice preview
                              po_reference=None):
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
        
        company_invoice_config = self.config.get('DEFAULT_COMPANY_INFO_INVOICE', {})
        company_due_days = company_invoice_config.get('PAYMENT_DUE_DAYS', 30)
        due_date = issue_date + timedelta(days=company_due_days)
        if due_date_str:
            try: due_date = datetime.strptime(due_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError: current_app.logger.warning(f"Invalid due_date_str: {due_date_str}, calculating from issue date.")
        
        subtotal_ht_calc = 0
        total_vat_calc = 0
        vat_breakdown_calc = {}
        invoice_items_for_db = []
        
        for item_data in line_items_data:
            quantity = int(item_data['quantity'])
            unit_price_ht = float(item_data['unit_price'])
            vat_rate = float(item_data.get('vat_rate', 20.0))
            
            line_total_ht = quantity * unit_price_ht
            subtotal_ht_calc += line_total_ht
            
            line_vat_amount = line_total_ht * (vat_rate / 100.0)
            total_vat_calc += line_vat_amount
            vat_rate_str = f"{vat_rate:.1f}".rstrip('0').rstrip('.')
            vat_breakdown_calc[vat_rate_str] = vat_breakdown_calc.get(vat_rate_str, 0) + line_vat_amount

            db_item = InvoiceItem(
                description=sanitize_input(item_data['description']), quantity=quantity,
                unit_price=unit_price_ht, total_price=line_total_ht,
                vat_rate = vat_rate,
                product_id=item_data.get('product_id')
            )
            invoice_items_for_db.append(db_item)
        
        grand_total_ttc_calc = subtotal_ht_calc + total_vat_calc

        new_invoice = Invoice(
            b2b_user_id=b2b_user_id, invoice_number=invoice_number, issue_date=issue_date, due_date=due_date,
            total_amount=round(subtotal_ht_calc, 2), # For B2B manual, total_amount is HT
            subtotal_ht=round(subtotal_ht_calc, 2),
            vat_breakdown= {rate: round(amount, 2) for rate, amount in vat_breakdown_calc.items()},
            total_vat_amount=round(total_vat_calc, 2),
            grand_total_ttc=round(grand_total_ttc_calc, 2),
            net_to_pay=round(grand_total_ttc_calc, 2),
            currency=user_currency or user.currency or self.config.get('DEFAULT_CURRENCY', 'EUR'),
            status=InvoiceStatusEnum.DRAFT,
            notes=sanitize_input(notes),
            created_by_admin_id=issued_by_admin_id,
            client_company_name_snapshot=user.company_name,
            client_vat_number_snapshot=user.vat_number,
            client_siret_number_snapshot=user.siret_number,
            po_reference_snapshot=sanitize_input(po_reference)
        )
        db.session.add(new_invoice)
        db.session.flush()

        for inv_item_obj in invoice_items_for_db:
            inv_item_obj.invoice_id = new_invoice.id
            db.session.add(inv_item_obj)
        
        pdf_created = self._create_pdf_and_save(
            new_invoice, user, order_model=None,
            is_b2b_invoice=True,
            raw_html_content=raw_invoice_html
        )
        
        try:
            db.session.commit()
            self.audit_logger.log_action(user_id=issued_by_admin_id, action='create_manual_b2b_invoice_success', target_type='invoice', target_id=new_invoice.id, details=f"Manual B2B Invoice {invoice_number} created for {user.email}. PDF Created: {pdf_created}", status='success')
            return new_invoice.id, new_invoice.invoice_number
        except Exception as e:
            db.session.rollback()
            self.audit_logger.log_action(user_id=issued_by_admin_id, action='create_manual_b2b_invoice_fail', details=f"Error creating invoice for {user.email}: {str(e)}", status='failure')
            current_app.logger.error(f"DB Commit error creating manual B2B invoice: {e}", exc_info=True)
            raise

    def create_invoice_from_order(self, order_id, is_b2b_order=False, issued_by_admin_id=None):
        if not order_id: raise ValueError("Order ID is required.")
        order = Order.query.get(order_id)
        if not order: raise ValueError(f"Order {order_id} not found.")
        
        if order.invoice: # Check if invoice relationship exists and is not None
            current_app.logger.info(f"Invoice for order {order_id} already exists (ID: {order.invoice.id}).")
            return order.invoice.id, order.invoice.invoice_number

        user = order.customer
        if not user: raise ValueError(f"User for order {order_id} not found.")
        if not order.items: raise ValueError(f"No items found for order {order_id}.")

        final_is_b2b_invoice = is_b2b_order
        if not is_b2b_order and user.role == UserRoleEnum.B2B_PROFESSIONAL:
            final_is_b2b_invoice = True

        invoice_number = self._generate_invoice_number(is_b2b=final_is_b2b_invoice)
        issue_date = datetime.now(timezone.utc)
        
        company_invoice_config = self.config.get('DEFAULT_COMPANY_INFO_INVOICE', {})
        company_due_days = company_invoice_config.get('PAYMENT_DUE_DAYS', 30)
        due_date = issue_date + timedelta(days=company_due_days if final_is_b2b_invoice else 0)

        invoice_items_for_template_processed = []
        db_invoice_items_to_add = []
        current_invoice_subtotal_ht = 0
        current_invoice_vat_breakdown = {}
        current_invoice_total_vat = 0

        for order_item_model in order.items:
            desc = sanitize_input(order_item_model.product_name) or "Produit"
            if order_item_model.variant_description:
                desc += f" ({sanitize_input(order_item_model.variant_description)})"
            
            unit_price_order = float(order_item_model.unit_price)
            quantity = int(order_item_model.quantity)
            
            # VAT Logic: Assume products have a vat_rate. B2C prices are TTC, B2B are HT from order.
            # This logic needs to be robust based on how prices are stored in OrderItem.
            # Let's assume OrderItem.unit_price is HT for B2B orders, and TTC for B2C orders.
            item_vat_rate = 20.0 # Default VAT
            if order_item_model.product and hasattr(order_item_model.product, 'vat_rate') and order_item_model.product.vat_rate is not None:
                item_vat_rate = float(order_item_model.product.vat_rate)
            
            line_total_ht_calculated = 0
            if final_is_b2b_invoice: # Assume unit_price_order is HT
                line_total_ht_calculated = unit_price_order * quantity
            else: # B2C: Assume unit_price_order is TTC, calculate HT
                line_total_ht_calculated = (unit_price_order * quantity) / (1 + item_vat_rate / 100.0)

            line_vat_amount_calculated = line_total_ht_calculated * (item_vat_rate / 100.0)
            
            current_invoice_subtotal_ht += line_total_ht_calculated
            vat_rate_str = f"{item_vat_rate:.1f}".rstrip('0').rstrip('.')
            current_invoice_vat_breakdown[vat_rate_str] = current_invoice_vat_breakdown.get(vat_rate_str, 0) + line_vat_amount_calculated
            current_invoice_total_vat += line_vat_amount_calculated

            db_item = InvoiceItem(
                description=desc, quantity=quantity,
                unit_price=unit_price_order, # Store what was on the order
                total_price=unit_price_order * quantity, # Store what was on the order
                vat_rate=item_vat_rate,
                product_id=order_item_model.product_id,
                serialized_item_id=order_item_model.serialized_item_id
            )
            db_invoice_items_to_add.append(db_item)
            
            item_template_data = {
                'description': desc, 'quantity': quantity, 
                'unit_price': unit_price_order, # Price from order
                'vat_rate': item_vat_rate,
                'total_price_ht': round(line_total_ht_calculated, 2),
                'total_price_ttc': round(line_total_ht_calculated + line_vat_amount_calculated, 2),
                'passport_urls': [], 'uid_for_passport': None,
                'product_name_for_passport': sanitize_input(order_item_model.product_name)
            }
            # Populate passport_urls logic here (as in your previous version)
            invoice_items_for_template_processed.append(item_template_data)

        current_grand_total_ttc = current_invoice_subtotal_ht + current_invoice_total_vat

        # For B2C, order.total_amount is TTC. For B2B, it might be HT or need confirmation.
        # The invoice model's total_amount will store HT if B2B, TTC if B2C.
        invoice_main_total = round(current_invoice_subtotal_ht, 2) if final_is_b2b_invoice else round(current_grand_total_ttc, 2)

        new_invoice = Invoice(
            order_id=order_id,
            b2b_user_id=user.id if final_is_b2b_invoice else None,
            invoice_number=invoice_number, issue_date=issue_date, due_date=due_date,
            total_amount=invoice_main_total,
            currency=order.currency,
            status=InvoiceStatusEnum.DRAFT, # PDF generation will update it
            notes=order.notes_customer or order.notes_internal,
            subtotal_ht=round(current_invoice_subtotal_ht, 2),
            vat_breakdown={rate: round(amount, 2) for rate, amount in current_invoice_vat_breakdown.items()},
            total_vat_amount=round(current_invoice_total_vat, 2),
            grand_total_ttc=round(current_grand_total_ttc, 2),
            net_to_pay=round(current_grand_total_ttc, 2),
            payment_date=order.payment_date if order.status == OrderStatusEnum.PAID else None,
            client_company_name_snapshot=user.company_name if final_is_b2b_invoice else None,
            client_vat_number_snapshot=user.vat_number if final_is_b2b_invoice else None,
            client_siret_number_snapshot=user.siret_number if final_is_b2b_invoice else None,
            po_reference_snapshot=order.purchase_order_reference if final_is_b2b_invoice and order.purchase_order_reference else None,
            created_by_admin_id=issued_by_admin_id if issued_by_admin_id and final_is_b2b_invoice else None
        )
        db.session.add(new_invoice)
        db.session.flush()

        for inv_item_obj in db_invoice_items_to_add:
            inv_item_obj.invoice_id = new_invoice.id
            db.session.add(inv_item_obj)
        
        order.invoice_id = new_invoice.id # Link invoice to order immediately

        pdf_created = self._create_pdf_and_save(
            new_invoice, user, order,
            invoice_items_for_template=invoice_items_for_template_processed,
            is_b2b_invoice=final_is_b2b_invoice
        )
        
        try:
            db.session.commit()
            self.audit_logger.log_action(user_id=issued_by_admin_id or user.id, action='create_invoice_from_order_success', target_type='invoice', target_id=new_invoice.id, details=f"Invoice {invoice_number} for order {order_id}. B2B: {final_is_b2b_invoice}. PDF: {pdf_created}", status='success')
            return new_invoice.id, new_invoice.invoice_number
        except Exception as e:
            db.session.rollback()
            self.audit_logger.log_action(user_id=issued_by_admin_id or user.id, action='create_invoice_from_order_fail_commit', target_type='order', target_id=order_id, details=f"DB Commit error: {str(e)}", status='failure')
            current_app.logger.error(f"DB Commit error creating invoice for order {order_id}: {e}", exc_info=True)
            raise
