import os
import sqlite3
from datetime import datetime, timedelta
from flask import current_app, render_template
from weasyprint import HTML, CSS # Ensure WeasyPrint is installed
from ..database import get_db_connection, query_db

class InvoiceService:
    """Service class for handling invoice generation and management."""

    def __init__(self):
        # Each method will get its own connection to ensure thread safety
        # and proper transaction management per operation.
        self.config = current_app.config

    def _get_db_connection(self):
        """Gets a fresh database connection."""
        return get_db_connection()

    def _generate_invoice_number(self, db_conn):
        """Generates a new, unique invoice number."""
        try:
            last_invoice = query_db(
                "SELECT invoice_number FROM invoices ORDER BY id DESC LIMIT 1",
                db_conn=db_conn,
                one=True
            )
            if last_invoice and last_invoice['invoice_number']:
                parts = last_invoice['invoice_number'].split('-')
                if len(parts) == 3 and parts[0] == 'INV' and parts[1] == str(datetime.now().year):
                    next_id = int(parts[2]) + 1
                else: # Fallback for different format or new year
                    next_id = 1
            else:
                next_id = 1
            
            return f"INV-{datetime.now().year}-{next_id:05d}"
        except Exception as e:
            current_app.logger.error(f"Error generating invoice number: {e}")
            return f"INV-ERR-{int(datetime.now().timestamp())}" # Fallback

    def _create_pdf_and_save(self, db_conn, invoice_id, invoice_number, user_details, invoice_items_details, shipping_address_details=None, notes=None):
        """Helper function to generate PDF and save its path."""
        company_info = self.config.get('DEFAULT_COMPANY_INFO', {})
        logo_path_config = company_info.get('logo_path')
        
        # Prepare logo path for WeasyPrint (needs to be absolute file path or data URI)
        prepared_logo_path = None
        if logo_path_config:
            # Check if it's already a file URI or an absolute path
            if logo_path_config.startswith('file://'):
                prepared_logo_path = logo_path_config
            elif os.path.isabs(logo_path_config) and os.path.exists(logo_path_config):
                prepared_logo_path = f'file://{os.path.abspath(logo_path_config)}'
            elif os.path.exists(os.path.join(current_app.root_path, logo_path_config)): # Relative to app root
                prepared_logo_path = f'file://{os.path.abspath(os.path.join(current_app.root_path, logo_path_config))}'
            else:
                current_app.logger.warning(f"Invoice logo path not found or invalid: {logo_path_config}")

        company_info_for_template = {**company_info, 'logo_path': prepared_logo_path}


        invoice_main_details = query_db("SELECT * FROM invoices WHERE id = ?", [invoice_id], db_conn=db_conn, one=True)

        context = {
            "invoice": invoice_main_details,
            "invoice_items": invoice_items_details,
            "user": user_details,
            "shipping_address": shipping_address_details,
            "company": company_info_for_template,
            "notes_from_service": notes # Pass notes explicitly if provided
        }
        
        html_string = render_template('invoice_template.html', **context)
        pdf_file_content = HTML(string=html_string).write_pdf()
        
        pdf_filename = f"{invoice_number}.pdf"
        # Ensure INVOICE_PDF_PATH directory exists
        invoice_pdf_dir = self.config['INVOICE_PDF_PATH']
        os.makedirs(invoice_pdf_dir, exist_ok=True)
        
        pdf_full_path = os.path.join(invoice_pdf_dir, pdf_filename)
        
        with open(pdf_full_path, 'wb') as f:
            f.write(pdf_file_content)
        
        query_db(
            "UPDATE invoices SET pdf_path = ?, status = ? WHERE id = ?",
            (pdf_full_path, 'issued', invoice_id),
            db_conn=db_conn,
            commit=False # Commit is handled by the calling method
        )
        current_app.logger.info(f"PDF generated and saved for invoice {invoice_number} at {pdf_full_path}")


    def create_invoice_from_order(self, order_id):
        """Creates an invoice for a given order."""
        if not order_id:
            raise ValueError("Order ID is required to create an invoice.")

        db = self._get_db_connection()
        try:
            db.execute("BEGIN")

            order = query_db("SELECT * FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)
            if not order:
                raise ValueError(f"Order with ID {order_id} not found.")

            existing_invoice = query_db("SELECT id, invoice_number FROM invoices WHERE order_id = ?", [order_id], db_conn=db, one=True)
            if existing_invoice:
                current_app.logger.warning(f"Invoice for order {order_id} already exists (ID: {existing_invoice['id']}). Returning existing invoice number: {existing_invoice['invoice_number']}")
                db.commit() # Commit to release lock, even if returning early
                return existing_invoice['id'], existing_invoice['invoice_number']

            user = query_db("SELECT * FROM users WHERE id = ?", [order['user_id']], db_conn=db, one=True)
            if not user:
                raise ValueError(f"User with ID {order['user_id']} not found for order {order_id}.")

            order_items_db = query_db("SELECT * FROM order_items WHERE order_id = ?", [order_id], db_conn=db)
            if not order_items_db:
                raise ValueError(f"No items found for order ID {order_id}.")

            invoice_number = self._generate_invoice_number(db)
            issue_date = datetime.now()
            due_date = issue_date + timedelta(days=self.config.get('INVOICE_DUE_DAYS', 30))
            
            invoice_id = query_db(
                """INSERT INTO invoices (order_id, b2b_user_id, invoice_number, issue_date, due_date, total_amount, currency, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (order_id, user['id'], invoice_number, issue_date.strftime("%Y-%m-%d"), due_date.strftime("%Y-%m-%d"), 
                 order['total_amount'], order['currency'], 'draft', order.get('notes_internal')), # Use internal order notes if available
                db_conn=db,
                commit=False
            )
            
            invoice_items_for_pdf = []
            for item in order_items_db:
                query_db(
                    """INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price, product_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (invoice_id, item['product_name'], item['quantity'], item['unit_price'], item['total_price'], item['product_id']),
                    db_conn=db,
                    commit=False
                )
                invoice_items_for_pdf.append(dict(item)) # Use original item for PDF context

            shipping_details = {
                "line1": order['shipping_address_line1'], "line2": order['shipping_address_line2'],
                "city": order['shipping_city'], "postal_code": order['shipping_postal_code'], "country": order['shipping_country']
            }

            self._create_pdf_and_save(db, invoice_id, invoice_number, user, invoice_items_for_pdf, shipping_details, order.get('notes_internal'))
            
            db.commit()
            current_app.logger.info(f"Successfully created invoice ID {invoice_id} (Number: {invoice_number}) for order ID {order_id}.")
            return invoice_id, invoice_number

        except (ValueError, sqlite3.Error, Exception) as e:
            if db: db.rollback()
            current_app.logger.error(f"Failed to create invoice for order ID {order_id}: {e}", exc_info=True)
            raise

    def create_manual_invoice(self, b2b_user_id, user_currency, line_items_data, notes=None):
        """Creates a manual invoice for a B2B user with provided line items."""
        if not b2b_user_id or not line_items_data:
            raise ValueError("B2B User ID and line items are required for manual invoice.")

        db = self._get_db_connection()
        try:
            db.execute("BEGIN")

            user = query_db("SELECT * FROM users WHERE id = ? AND role = 'b2b_professional'", [b2b_user_id], db_conn=db, one=True)
            if not user:
                raise ValueError(f"B2B Professional User with ID {b2b_user_id} not found.")

            invoice_number = self._generate_invoice_number(db)
            issue_date = datetime.now()
            due_date = issue_date + timedelta(days=self.config.get('INVOICE_DUE_DAYS', 30))
            
            total_amount = 0
            for item_data in line_items_data:
                if not all(k in item_data for k in ('description', 'quantity', 'unit_price')):
                    raise ValueError("Each line item must have description, quantity, and unit_price.")
                item_data['quantity'] = int(item_data['quantity'])
                item_data['unit_price'] = float(item_data['unit_price'])
                total_amount += item_data['quantity'] * item_data['unit_price']

            invoice_id = query_db(
                """INSERT INTO invoices (b2b_user_id, invoice_number, issue_date, due_date, total_amount, currency, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (b2b_user_id, invoice_number, issue_date.strftime("%Y-%m-%d"), due_date.strftime("%Y-%m-%d"), 
                 total_amount, user_currency or user.get('currency', 'EUR'), 'draft', notes),
                db_conn=db,
                commit=False
            )
            
            invoice_items_for_pdf = []
            for item_data in line_items_data:
                item_total = item_data['quantity'] * item_data['unit_price']
                query_db(
                    """INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price)
                       VALUES (?, ?, ?, ?, ?)""",
                    (invoice_id, item_data['description'], item_data['quantity'], item_data['unit_price'], item_total),
                    db_conn=db,
                    commit=False
                )
                # For PDF, ensure all necessary fields are present
                invoice_items_for_pdf.append({
                    'description': item_data['description'],
                    'quantity': item_data['quantity'],
                    'unit_price': item_data['unit_price'],
                    'total_price': item_total
                })
            
            # Manual invoices typically don't have a pre-defined shipping address from an order context
            # It could be fetched from user's primary address if needed, or left blank/handled differently.
            self._create_pdf_and_save(db, invoice_id, invoice_number, user, invoice_items_for_pdf, shipping_address_details=None, notes=notes)
            
            db.commit()
            current_app.logger.info(f"Successfully created manual invoice ID {invoice_id} (Number: {invoice_number}) for B2B user ID {b2b_user_id}.")
            return invoice_id, invoice_number

        except (ValueError, sqlite3.Error, Exception) as e:
            if db: db.rollback()
            current_app.logger.error(f"Failed to create manual invoice for B2B user ID {b2b_user_id}: {e}", exc_info=True)
            raise
