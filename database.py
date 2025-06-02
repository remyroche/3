import sqlite3
import os
import click
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash
import datetime 

# --- Database Initialization and Connection Management ---

def get_db_connection():
    if 'db_conn' not in g or g.db_conn is None:
        try:
            db_path = current_app.config['DATABASE_PATH']
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            g.db_conn = sqlite3.connect(
                db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            g.db_conn.row_factory = sqlite3.Row
            g.db_conn.execute("PRAGMA foreign_keys = ON;")
            current_app.logger.debug(f"Database connection established to {db_path}")
        except sqlite3.Error as e:
            current_app.logger.error(f"Database connection error: {e}")
            raise
        except Exception as e:
            current_app.logger.error(f"An unexpected error occurred while connecting to the database: {e}")
            raise
    return g.db_conn

def close_db_connection(e=None):
    db_conn = g.pop('db_conn', None)
    if db_conn is not None:
        try:
            db_conn.close()
            current_app.logger.debug("Database connection closed.")
        except Exception as e:
            current_app.logger.error(f"Error closing database connection: {e}")

def init_db_schema(db_conn=None):
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
        if db_conn and connection_managed_internally: db_conn.rollback()
        raise
    except FileNotFoundError as e: 
        current_app.logger.error(f"Schema file error: {e}")
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error during schema initialization: {e}")
        if db_conn and connection_managed_internally and hasattr(db_conn, 'rollback'): db_conn.rollback()
        raise

def populate_initial_data(db_conn=None):
    connection_managed_internally = False
    if db_conn is None:
        if not current_app:
            raise RuntimeError("Application context is required to populate initial data.")
        db_conn = get_db_connection()
        connection_managed_internally = True
    
    cursor = db_conn.cursor()
    populated_something = False

    try:
        # Secure initial admin creation:
        # Admin credentials should be set via environment variables for production.
        admin_email_env = current_app.config.get('INITIAL_ADMIN_EMAIL')
        admin_password_env = current_app.config.get('INITIAL_ADMIN_PASSWORD')

        if admin_email_env and admin_password_env:
            cursor.execute("SELECT COUNT(*) FROM users WHERE email = ? AND role = 'admin'", (admin_email_env,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    """INSERT INTO users (email, password_hash, first_name, last_name, role, is_active, is_verified, professional_status) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (admin_email_env, generate_password_hash(admin_password_env), "Admin", "Trüvra", 'admin', True, True, 'approved')
                )
                current_app.logger.info(f"Admin user created from environment variables: {admin_email_env}.")
                populated_something = True
            else:
                current_app.logger.info(f"Admin user {admin_email_env} already exists.")
        else:
            current_app.logger.warning(
                "INITIAL_ADMIN_EMAIL or INITIAL_ADMIN_PASSWORD environment variables not set. "
                "Initial admin user will not be created automatically. "
                "Please create an admin user manually or set these environment variables."
            )
            # Fallback for development if defaults were previously used and admin still exists:
            legacy_admin_email = current_app.config.get('ADMIN_EMAIL', 'admin@maisontruvra.com')
            cursor.execute("SELECT COUNT(*) FROM users WHERE email = ? AND role = 'admin'", (legacy_admin_email,))
            if cursor.fetchone()[0] == 0 and config_by_name.get(os.getenv('FLASK_ENV')) == DevelopmentConfig :
                 current_app.logger.warning(f"Attempting to create admin with ADMIN_EMAIL (legacy dev default). THIS IS INSECURE FOR PRODUCTION.")
                 # This block could be removed entirely to force env var usage.
                 # admin_password_config = current_app.config.get('ADMIN_PASSWORD', 'SecureAdminP@ss1') # Legacy default
                 # cursor.execute(
                 #    """INSERT INTO users (email, password_hash, first_name, last_name, role, is_active, is_verified, professional_status) 
                 #       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                 #    (legacy_admin_email, generate_password_hash(admin_password_config), "Admin", "Trüvra", 'admin', True, True, 'approved')
                 # )
                 # current_app.logger.info(f"Legacy default admin user created: {legacy_admin_email}. CHANGE THIS PASSWORD.")
                 # populated_something = True


        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            initial_categories = [
                ('Truffes Fraîches', 'Découvrez nos truffes fraîches de saison.', None, 'truffes-fraiches', 'CAT-TF'),
                ('Huiles Truffées', 'Huiles d\'olive extra vierge infusées aux arômes de truffe.', None, 'huiles-truffees', 'CAT-HT'),
                ('Sauces Truffées', 'Sauces gourmandes pour sublimer vos plats.', None, 'sauces-truffees', 'CAT-ST'),
                ('Coffrets Cadeaux', 'Des assortiments parfaits pour offrir.', None, 'coffrets-cadeaux', 'CAT-CG'),
                ('Autre', 'Autres délices truffés.', None, 'autre', 'CAT-AUTRE')
            ]
            cursor.executemany(
                "INSERT INTO categories (name, description, parent_id, slug, category_code) VALUES (?, ?, ?, ?, ?)",
                initial_categories
            )
            current_app.logger.info(f"{len(initial_categories)} initial categories populated.")
            populated_something = True

        if populated_something:
            if connection_managed_internally: db_conn.commit()
            current_app.logger.info("Initial data populated where applicable.")
        else:
            current_app.logger.info("No new initial data was populated.")

    except sqlite3.IntegrityError as ie:
        if connection_managed_internally: db_conn.rollback()
        current_app.logger.warning(f"Integrity error during data population (likely data already exists): {ie}")
    except Exception as e:
        if connection_managed_internally: db_conn.rollback()
        current_app.logger.error(f"Error populating initial data: {e}", exc_info=True)
        raise

@click.command('init-db')
@with_appcontext
def init_db_command():
    db_conn = get_db_connection()
    init_db_schema(db_conn)
    click.echo('Initialized the database schema from schema.sql.')
    populate_initial_data(db_conn)
    click.echo('Populated initial data (if applicable).')

def query_db(query, args=(), one=False, commit=False, db_conn=None):
    connection_provided = db_conn is not None
    if not connection_provided:
        db_conn = get_db_connection()
    cursor = None
    try:
        cursor = db_conn.cursor()
        cursor.execute(query, args)
        if commit: 
            if not connection_provided: 
                 db_conn.commit()
            return cursor.lastrowid if "insert" in query.lower() else cursor.rowcount
        rv = cursor.fetchall()
        return (rv[0] if rv else None) if one else rv
    except sqlite3.Error as e:
        current_app.logger.error(f"Database query error: {e} \nQuery: {query} \nArgs: {args}")
        if db_conn and commit and not connection_provided: db_conn.rollback()
        raise 
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred during query_db: {e}")
        if db_conn and commit and not connection_provided: db_conn.rollback()
        raise

def register_db_commands(app):
    app.cli.add_command(init_db_command)
    app.teardown_appcontext(close_db_connection)
    app.logger.info("Database commands registered and teardown context set.")

def record_stock_movement(db_conn, product_id, movement_type, quantity_change=None, weight_change_grams=None,
                          variant_id=None, serialized_item_id=None, reason=None,
                          related_order_id=None, related_user_id=None, notes=None):
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
    args = (
        product_id, variant_id, serialized_item_id, movement_type,
        quantity_change, weight_change_grams, reason,
        related_order_id, related_user_id, notes
    )
    try:
        cursor = db_conn.cursor()
        cursor.execute(sql, args)
        current_app.logger.debug(f"Stock movement prepared for recording (pending commit): {movement_type} for product ID {product_id}")
        return cursor.lastrowid
    except sqlite3.Error as e:
        current_app.logger.error(f"Failed to prepare stock movement record: {e}. Query: {sql}, Args: {args}")
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error preparing stock movement record: {e}")
        raise

def get_product_id_from_code(product_code, db_conn=None):
    if not product_code: return None
    product_row = query_db("SELECT id FROM products WHERE product_code = ?", [product_code], db_conn=db_conn, one=True)
    return product_row['id'] if product_row else None

def get_category_id_from_code(category_code, db_conn=None):
    if not category_code: return None
    category_row = query_db("SELECT id FROM categories WHERE category_code = ?", [category_code], db_conn=db_conn, one=True)
    return category_row['id'] if category_row else None
