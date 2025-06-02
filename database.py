# backend/database.py
import os
import click
from flask import current_app
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

# Import the db instance and models from your application structure
# This assumes db is initialized in backend/__init__.py and models are in backend/models.py
from . import db # Or from .models import db if you define it there
from .models import User, Category, Product # Import other models as needed

# The old get_db_connection, close_db_connection, query_db, init_db_schema
# are no longer needed when using Flask-SQLAlchemy as it manages connections and sessions.

def populate_initial_data_sqlalchemy():
    """Populates the database with initial data using SQLAlchemy models."""
    if not current_app:
        print("Error: Application context is not available. Cannot populate data.")
        return

    with current_app.app_context():
        # --- Admin User ---
        admin_email = current_app.config.get('INITIAL_ADMIN_EMAIL')
        admin_password = current_app.config.get('INITIAL_ADMIN_PASSWORD')

        if admin_email and admin_password:
            if not User.query.filter_by(email=admin_email, role='admin').first():
                admin = User(
                    email=admin_email,
                    first_name="Admin",
                    last_name="Trüvra",
                    role='admin',
                    is_active=True,
                    is_verified=True, # Admins are typically pre-verified
                    professional_status='approved' # If admin can also be a B2B user
                )
                admin.set_password(admin_password) # Use the method from the User model
                db.session.add(admin)
                current_app.logger.info(f"Admin user '{admin_email}' created via SQLAlchemy.")
            else:
                current_app.logger.info(f"Admin user '{admin_email}' already exists.")
        else:
            current_app.logger.warning(
                "INITIAL_ADMIN_EMAIL or INITIAL_ADMIN_PASSWORD not set in config. "
                "Initial admin user will not be created automatically."
            )

        # --- Categories ---
        if Category.query.count() == 0:
            initial_categories_data = [
                {'name': 'Truffes Fraîches', 'description': 'Découvrez nos truffes fraîches de saison.', 'category_code': 'CAT-TF', 'slug': 'truffes-fraiches', 'is_active': True},
                {'name': 'Huiles Truffées', 'description': 'Huiles d\'olive extra vierge infusées aux arômes de truffe.', 'category_code': 'CAT-HT', 'slug': 'huiles-truffees', 'is_active': True},
                {'name': 'Sauces Truffées', 'description': 'Sauces gourmandes pour sublimer vos plats.', 'category_code': 'CAT-ST', 'slug': 'sauces-truffees', 'is_active': True},
                {'name': 'Coffrets Cadeaux', 'description': 'Des assortiments parfaits pour offrir.', 'category_code': 'CAT-CG', 'slug': 'coffrets-cadeaux', 'is_active': True},
                {'name': 'Autre', 'description': 'Autres délices truffés.', 'category_code': 'CAT-AUTRE', 'slug': 'autre', 'is_active': True}
            ]
            for cat_data in initial_categories_data:
                category = Category(**cat_data) # Unpack dictionary into model constructor
                db.session.add(category)
            current_app.logger.info(f"{len(initial_categories_data)} initial categories populated via SQLAlchemy.")
        else:
            current_app.logger.info("Categories table already has data. Skipping initial population.")
        
        # --- Example Product (Optional) ---
        # if Product.query.count() == 0:
        #     cat_tf = Category.query.filter_by(slug='truffes-fraiches').first()
        #     if cat_tf:
        #         example_product = Product(
        #             name="Truffe Noire d'Hiver (Exemple)",
        #             description="Une truffe noire d'hiver exceptionnelle.",
        #             category_id=cat_tf.id,
        #             product_code="PROD-TNH-EX01",
        #             sku_prefix="TNHEX", # Example
        #             type='simple', # or 'variable_weight'
        #             base_price=150.00,
        #             currency='EUR',
        #             is_active=True,
        #             slug='truffe-noire-hiver-exemple',
        #             aggregate_stock_quantity=10 
        #         )
        #         db.session.add(example_product)
        #         current_app.logger.info("Example product added.")

        try:
            db.session.commit()
            current_app.logger.info("Initial data (if any) committed successfully via SQLAlchemy.")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing initial data: {e}", exc_info=True)
            raise

@click.command('seed-db')
@with_appcontext
def seed_db_command():
    """Seeds the database with initial data using SQLAlchemy models."""
    populate_initial_data_sqlalchemy()
    click.echo('Database seeded with initial data (SQLAlchemy).')

def register_db_commands(app):
    """Registers database-related CLI commands."""
    app.cli.add_command(seed_db_command)
    # The 'init-db' command is now effectively handled by Flask-Migrate's `flask db upgrade`
    # You might remove the old init_db_command or adapt it if needed for very specific first-time setup
    # not covered by migrations (though migrations should handle schema creation).
    app.logger.info("SQLAlchemy DB seed command registered.")


# --- Utility functions that were in database.py, now adapted or to be replaced ---

def record_stock_movement(
    db_session, product_id, movement_type, quantity_change=None, weight_change_grams=None,
    variant_id=None, serialized_item_id=None, reason=None,
    related_order_id=None, related_user_id=None, notes=None
):
    """
    Records a stock movement using SQLAlchemy session.
    Note: The db_session should be passed in, typically from the route handler.
    The calling function is responsible for db.session.commit().
    """
    from .models import StockMovement # Local import to avoid circular dependency at module level

    if not db_session:
        current_app.logger.error("record_stock_movement called without a SQLAlchemy db session.")
        raise ValueError("A SQLAlchemy db session is required for record_stock_movement.")

    movement = StockMovement(
        product_id=product_id,
        variant_id=variant_id,
        serialized_item_id=serialized_item_id,
        movement_type=movement_type,
        quantity_change=quantity_change,
        weight_change_grams=weight_change_grams,
        reason=reason,
        related_order_id=related_order_id,
        related_user_id=related_user_id,
        notes=notes
        # movement_date is defaulted in the model
    )
    db_session.add(movement)
    current_app.logger.debug(f"Stock movement object created for recording: {movement_type} for product ID {product_id}")
    # The calling function should commit the session.
    return movement # Returning the object might be useful

def get_product_id_from_code(product_code, db_session=None):
    """Fetches product ID using product_code with SQLAlchemy."""
    from .models import Product # Local import
    if not product_code: return None
    
    # If db_session is not provided, this implies it's called outside a request context
    # or where db.session is not readily available. This is less ideal.
    # For calls within request handlers, db.session should be used directly.
    if db_session:
        product = db_session.query(Product.id).filter_by(product_code=product_code.upper()).first()
    else: # Fallback, assumes app context is available for db.session
        product = Product.query.with_entities(Product.id).filter_by(product_code=product_code.upper()).first()
        
    return product.id if product else None

def get_category_id_from_code(category_code, db_session=None):
    """Fetches category ID using category_code with SQLAlchemy."""
    from .models import Category # Local import
    if not category_code: return None

    if db_session:
        category = db_session.query(Category.id).filter_by(category_code=category_code.upper()).first()
    else:
        category = Category.query.with_entities(Category.id).filter_by(category_code=category_code.upper()).first()
        
    return category.id if category else None
