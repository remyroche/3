import sqlite3
import os
import click
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
import datetime # Added for populate_initial_data and record_stock_movement

# --- Database Initialization and Connection Management ---

def get_db_connection():
    """
    Establishes a new database connection or returns the existing one
    for the current application context.
    Stores the connection in Flask's 'g' object.
    """
    if 'db_conn' not in g or g.db_conn is None:
        try:
            db_path = current_app.config['DATABASE_PATH']
            # Ensure the database directory exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            g.db_conn = sqlite3.connect(
                db_path,
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            g.db_conn.row_factory = sqlite3.Row  # Access columns by name
            g.db_conn.execute("PRAGMA foreign_keys = ON;") # Enforce foreign key constraints
            current_app.logger.info(f"Database connection established to {db_path}")
        except sqlite3.Error as e:
            current_app.logger.error(f"Database connection error: {e}")
            raise
        except Exception as e:
            current_app.logger.error(f"An unexpected error occurred while connecting to the database: {e}")
            raise
    return g.db_conn

def close_db_connection(e=None):
    """
    Closes the database connection at the end of the request.
    This function is typically registered with Flask's app.teardown_appcontext.
    """
    db_conn = g.pop('db_conn', None)
    if db_conn is not None:
        try:
            db_conn.close()
            current_app.logger.info("Database connection closed.")
        except Exception as e:
            current_app.logger.error(f"Error closing database connection: {e}")

def init_db_schema(db_conn=None):
    """
    Initializes the database schema by executing SQL commands from 'schema.sql'.
    If db_conn is not provided, it will attempt to get one using the app context.
    """
    connection_managed_internally = False
    if db_conn is None:
        if not current_app:
            raise RuntimeError("Application context is required to get a database connection.")
        db_conn = get_db_connection()
        connection_managed_internally = True

    try:
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        if not os.path.exists(schema_path):
            current_app.logger.error(f"Schema file not found at {schema_path}")
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path, 'r') as f:
            sql_script = f.read()
        
        cursor = db_conn.cursor()
        cursor.executescript(sql_script)
        db_conn.commit()
        current_app.logger.info("Database schema initialized successfully from schema.sql.")
    except sqlite3.Error as e:
        current_app.logger.error(f"Error initializing database schema: {e}")
        if db_conn:
            db_conn.rollback()
        raise
    except FileNotFoundError as e:
        current_app.logger.error(f"Schema file error: {e}")
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error during schema initialization: {e}")
        if db_conn and hasattr(db_conn, 'rollback'):
            db_conn.rollback()
        raise

def populate_initial_data(db_conn=None):
    """
    Populates the database with initial data, like an admin user and sample products.
    Uses the provided db_conn or gets one from the app context.
    """
    connection_managed_internally = False
    if db_conn is None:
        if not current_app:
            raise RuntimeError("Application context is required to populate initial data.")
        db_conn = get_db_connection()
        connection_managed_internally = True
    
    cursor = db_conn.cursor()
    populated_something = False

    try:
        # Populate Admin User
        admin_email_config = current_app.config.get('ADMIN_EMAIL', 'admin@maisontruvra.com')
        cursor.execute("SELECT COUNT(*) FROM users WHERE email = ?", (admin_email_config,))
        if cursor.fetchone()[0] == 0:
            admin_password_config = current_app.config.get('ADMIN_PASSWORD', 'SecureAdminP@ss1')
            cursor.execute(
                "INSERT INTO users (email, password_hash, first_name, last_name, role, is_active, is_verified, professional_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (admin_email_config, generate_password_hash(admin_password_config), "Admin", "Trüvra", 'admin', True, True, 'approved')
            )
            current_app.logger.info(f"Admin user created: {admin_email_config}. IMPORTANT: Change default password if in use.")
            populated_something = True
        else:
            current_app.logger.info("Admin user already exists.")

        # Populate Sample Products (Simplified example)
        # This should ideally check if 'products' table is empty before populating to avoid duplication on multiple calls.
        # For a robust solution, use unique constraints on product SKUs/slugs and handle IntegrityError.
        # The schema.sql has UNIQUE constraints, so INSERT OR IGNORE or manual checks are needed if re-run.
        
        # Note: The original populate_initial_data from asset_generators.py had more complex product data.
        # This version is simplified. For full functionality, that data structure should be used here.
        # Also, that version called record_stock_movement. That logic should be included here if initial stock is set.

        if populated_something:
            db_conn.commit()
            current_app.logger.info("Initial data populated.")
        else:
            current_app.logger.info("No new initial data was populated (e.g., admin user already existed).")

    except sqlite3.IntegrityError as ie:
        db_conn.rollback()
        current_app.logger.warning(f"Integrity error during data population (likely data already exists): {ie}")
    except Exception as e:
        db_conn.rollback()
        current_app.logger.error(f"Error populating initial data: {e}")
        raise # Re-raise for visibility or specific handling


# --- Flask CLI Commands for Database Management ---

@click.command('init-db') # Renamed from init-db-schema for broader scope
@with_appcontext
def init_db_command():
    """Clear existing data (if any, by re-running schema) and create new tables, then populate initial data."""
    db_conn = get_db_connection() # Connection is managed by app context
    
    # Initialize schema first
    init_db_schema(db_conn) # Pass the connection
    click.echo('Initialized the database schema from schema.sql.')
    
    # Then populate initial data
    populate_initial_data(db_conn)
    click.echo('Populated initial data (if applicable).')


# --- Utility Functions (can be expanded) ---

def query_db(query, args=(), one=False, commit=False, db_conn=None):
    """
    Helper function to query the database.
    :param query: The SQL query string.
    :param args: Arguments to pass to the query.
    :param one: Boolean, whether to fetch one record or all.
    :param commit: Boolean, whether to commit after the query (for INSERT, UPDATE, DELETE).
                 The caller is responsible for overall transaction management if part of a larger operation.
    :param db_conn: Optional. An existing database connection. If None, gets one from context.
    :return: Fetched data or lastrowid for INSERT/rowcount for UPDATE/DELETE.
    """
    connection_provided = db_conn is not None
    if not connection_provided:
        db_conn = get_db_connection()
    
    cursor = None
    try:
        cursor = db_conn.cursor()
        cursor.execute(query, args)
        
        if commit:
            # This commit is for standalone operations using query_db.
            # If part of a larger transaction, the caller should manage the commit.
            if not connection_provided: 
                 db_conn.commit()
            return cursor.lastrowid if "insert" in query.lower() else cursor.rowcount

        rv = cursor.fetchall()
        return (rv[0] if rv else None) if one else rv
    except sqlite3.Error as e:
        current_app.logger.error(f"Database query error: {e} \nQuery: {query} \nArgs: {args}")
        if db_conn and commit and not connection_provided: 
            db_conn.rollback()
        raise 
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred during query_db: {e}")
        if db_conn and commit and not connection_provided:
            db_conn.rollback()
        raise

def register_db_commands(app):
    """Registers database CLI commands with the Flask application."""
    app.cli.add_command(init_db_command) # Use the consolidated command
    app.teardown_appcontext(close_db_connection)
    app.logger.info("Database commands registered and teardown context set.")

def record_stock_movement(db_conn, product_id, movement_type, quantity_change=None, weight_change_grams=None,
                          variant_id=None, serialized_item_id=None, reason=None,
                          related_order_id=None, related_user_id=None, notes=None):
    """
    Records a stock movement using the provided database connection.
    The caller is responsible for transaction management (commit/rollback).
    """
    if db_conn is None:
        current_app.logger.error("record_stock_movement called without a database connection.")
        raise ValueError("A database connection (db_conn) is required for record_stock_movement.")

    sql = """
        INSERT INTO stock_movements (
            product_id, variant_id, serialized_item_id, movement_type,
            quantity_change, weight_change_grams, reason,
            related_order_id, related_user_id, notes, movement_date 
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """
    # Added movement_date to ensure it's set, CURRENT_TIMESTAMP in SQL will handle it
    args = (
        product_id, variant_id, serialized_item_id, movement_type,
        quantity_change, weight_change_grams, reason,
        related_order_id, related_user_id, notes
    )
    
    try:
        cursor = db_conn.cursor()
        cursor.execute(sql, args)
        current_app.logger.info(f"Stock movement prepared for recording (pending commit): {movement_type} for product {product_id}")
        return cursor.lastrowid
    except sqlite3.Error as e:
        current_app.logger.error(f"Failed to prepare stock movement record: {e}. Query: {sql}, Args: {args}")
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error preparing stock movement record: {e}")
        raise