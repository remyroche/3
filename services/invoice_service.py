import os
import sqlite3
from datetime import datetime, timedelta
from flask import current_app, render_template
from weasyprint import HTML, CSS
from ..database import get_db_connection, query_db



class InvoiceService:
    """Service class for handling invoice generation and management."""

    def __init__(self):
        self.db = get_db_connection()
        self.config = current_app.config

    def _generate_invoice_number(self):
        """Generates a new, unique invoice number."""
        try:
            last_invoice = query_db(
                "SELECT invoice_number FROM invoices ORDER BY id DESC LIMIT 1",
                db_conn=self.db,
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
            # Fallback to a timestamp-based unique number if sequence fails
            return f"INV-ERR-{int(datetime.now().timestamp())}"

    def create_invoice_from_order(self, order_id):
        """Creates an invoice for a given order."""
        if not order_id:
            raise ValueError("Order ID is required to create an invoice.")

        try:
            # Begin a transaction
            self.db.execute("BEGIN")

            # 1. Fetch Order and related data
            order = query_db("SELECT * FROM orders WHERE id = ?", [order_id], db_conn=self.db, one=True)
            if not order:
                raise ValueError(f"Order with ID {order_id} not found.")

            # Check if an invoice already exists for this order
            existing_invoice = query_db("SELECT id FROM invoices WHERE order_id = ?", [order_id], db_conn=self.db, one=True)
            if existing_invoice:
                current_app.logger.warning(f"Invoice for order {order_id} already exists (ID: {existing_invoice['id']}).")
                # Depending on business logic, you might return the existing invoice ID or raise an error
                return existing_invoice['id']

            user = query_db("SELECT * FROM users WHERE id = ?", [order['user_id']], db_conn=self.db, one=True)
            order_items = query_db("SELECT * FROM order_items WHERE order_id = ?", [order_id], db_conn=self.db)

            # 2. Create Invoice record in DB
            invoice_number = self._generate_invoice_number()
            issue_date = datetime.now()
            due_date = issue_date + timedelta(days=30) # Example: due in 30 days
            
            invoice_id = query_db(
                """INSERT INTO invoices (order_id, b2b_user_id, invoice_number, issue_date, due_date, total_amount, currency, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (order_id, user['id'], invoice_number, issue_date.strftime("%Y-%m-%d"), due_date.strftime("%Y-%m-%d"), order['total_amount'], order['currency'], 'draft'),
                db_conn=self.db,
                commit=False # Commit will happen at the end
            )
            
            # 3. Create Invoice Items
            for item in order_items:
                query_db(
                    """INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price, product_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (invoice_id, item['product_name'], item['quantity'], item['unit_price'], item['total_price'], item['product_id']),
                    db_conn=self.db,
                    commit=False
                )

            # 4. Generate PDF
            company_info = self.config.get('DEFAULT_COMPANY_INFO', {})
            # Ensure the logo path is an absolute file path or a data URI for WeasyPrint
            logo_path = company_info.get('logo_path')
            if logo_path and os.path.exists(logo_path):
                 company_info['logo_path'] = f'file://{os.path.abspath(logo_path)}'


            # Prepare context for the template
            context = {
                "invoice": query_db("SELECT * FROM invoices WHERE id = ?", [invoice_id], db_conn=self.db, one=True),
                "invoice_items": query_db("SELECT * FROM invoice_items WHERE invoice_id = ?", [invoice_id], db_conn=self.db),
                "user": user,
                "shipping_address": {
                    "line1": order['shipping_address_line1'], "line2": order['shipping_address_line2'],
                    "city": order['shipping_city'], "postal_code": order['shipping_postal_code'], "country": order['shipping_country']
                },
                "company": company_info
            }
            
            # Render HTML from template
            html_string = render_template('invoice_template.html', **context)
            
            # Generate PDF
            pdf_file = HTML(string=html_string).write_pdf()
            
            # 5. Save PDF and update DB
            pdf_filename = f"{invoice_number}.pdf"
            pdf_path = os.path.join(self.config['INVOICE_PDF_PATH'], pdf_filename)
            
            with open(pdf_path, 'wb') as f:
                f.write(pdf_file)
            
            query_db(
                "UPDATE invoices SET pdf_path = ?, status = ? WHERE id = ?",
                (pdf_path, 'issued', invoice_id),
                db_conn=self.db,
                commit=False
            )
            
            # 6. Commit transaction
            self.db.commit()
            current_app.logger.info(f"Successfully created invoice ID {invoice_id} for order ID {order_id}.")
            
            return invoice_id

        except (ValueError, sqlite3.Error, Exception) as e:
            if self.db:
                self.db.rollback() # Rollback on any error
            current_app.logger.error(f"Failed to create invoice for order ID {order_id}: {e}", exc_info=True)
            raise # Re-raise the exception to be handled by the route

