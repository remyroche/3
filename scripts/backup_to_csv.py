# /scripts/backup_to_csv.py
import os
import csv
from datetime import datetime, timezone
from sqlalchemy import create_engine, inspect as sqlalchemy_inspect
from sqlalchemy.orm import sessionmaker
import logging

# Configure logging for the script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration (Adjust these as needed or load from environment/config file) ---
# Ensure this matches your Flask app's DATABASE_URL for the target environment
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'dev_maison_truvra_orm.sqlite3'))
BACKUP_DIR_BASE = os.environ.get('CSV_BACKUP_DIR', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'csv_backups'))
TABLES_TO_BACKUP = [ # Add all tables you want to back up
    'users', 'categories', 'products', 'product_weight_options', 
    'serialized_inventory_items', 'stock_movements', 'orders', 'order_items',
    'reviews', 'carts', 'cart_items', 'professional_documents',
    'invoices', 'invoice_items', 'audit_log', 'newsletter_subscriptions',
    'settings', 'product_localizations', 'category_localizations', 'generated_assets'
]
# --- End Configuration ---

def get_db_session(db_url):
    """Creates and returns a new SQLAlchemy session."""
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def backup_table_to_csv(session, table_name, backup_filepath):
    """Backs up a single table to a CSV file."""
    try:
        # Using SQLAlchemy's reflection to get table metadata
        inspector = sqlalchemy_inspect(session.bind)
        if not inspector.has_table(table_name):
            logging.warning(f"Table '{table_name}' not found in database. Skipping.")
            return False

        # Get columns for the header
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        
        # Fetch all data from the table
        # For very large tables, consider chunking or server-side cursors if supported by DB
        result_proxy = session.execute(f"SELECT * FROM {table_name}") # Use raw SQL for simplicity here
        
        with open(backup_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(columns) # Write header
            for row in result_proxy:
                csv_writer.writerow(row)
        logging.info(f"Successfully backed up table '{table_name}' to '{backup_filepath}'")
        return True
    except Exception as e:
        logging.error(f"Error backing up table '{table_name}': {e}", exc_info=True)
        return False

def main():
    logging.info("Starting daily CSV backup process...")
    
    session = get_db_session(DATABASE_URL)
    if not session:
        logging.error("Failed to create database session. Aborting backup.")
        return

    try:
        today_date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        backup_dir_today = os.path.join(BACKUP_DIR_BASE, today_date_str)
        os.makedirs(backup_dir_today, exist_ok=True)
        logging.info(f"Backup directory for today: {backup_dir_today}")

        all_successful = True
        for table_name in TABLES_TO_BACKUP:
            csv_filename = f"{table_name}_backup_{today_date_str}.csv"
            backup_filepath = os.path.join(backup_dir_today, csv_filename)
            if not backup_table_to_csv(session, table_name, backup_filepath):
                all_successful = False
        
        if all_successful:
            logging.info("All specified tables backed up successfully to CSV.")
        else:
            logging.warning("Some tables failed to back up. Check logs for details.")

    except Exception as e:
        logging.error(f"An critical error occurred during the CSV backup process: {e}", exc_info=True)
    finally:
        if session:
            session.close()
            logging.info("Database session closed.")

if __name__ == "__main__":
    # This script can be run directly or scheduled.
    # Example: python -m scripts.backup_to_csv (if scripts is a package)
    # or python scripts/backup_to_csv.py
    main()
