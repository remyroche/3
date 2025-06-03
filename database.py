# backend/database.py
import os
import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import func # Import func for SQL functions like upper

# Import the db instance and models from your application structure
from . import db 
from .models import User, Category, Product, StockMovement # Import other models as needed

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
            if not User.query.filter_by(email=admin_email, role='admin').first(): # Assuming UserRoleEnum.ADMIN if using enums
                admin = User(
                    email=admin_email,
                    first_name="Admin",
                    last_name="Trüvra",
                    role='admin', # Or UserRoleEnum.ADMIN
                    is_active=True,
                    is_verified=True,
                    professional_status='approved' # Or ProfessionalStatusEnum.APPROVED
                )
                admin.set_password(admin_password)
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
                category = Category(**cat_data)
                db.session.add(category)
            current_app.logger.info(f"{len(initial_categories_data)} initial categories populated via SQLAlchemy.")
        else:
            current_app.logger.info("Categories table already has data. Skipping initial population.")
        
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
    app.logger.info("SQLAlchemy DB seed command registered.")

def record_stock_movement(
    db_session, product_id, movement_type, quantity_change=None, weight_change_grams=None,
    variant_id=None, serialized_item_id=None, reason=None,
    related_order_id=None, related_user_id=None, notes=None
):
    """
    Records a stock movement using SQLAlchemy session.
    The calling function is responsible for db_session.commit().
    """
    from .models import StockMovement # Local import to avoid circular dependency at module level

    if not db_session:
        current_app.logger.error("record_stock_movement called without a SQLAlchemy db session.")
        raise ValueError("A SQLAlchemy db session is required for record_stock_movement.")

    movement = StockMovement(
        product_id=product_id,
        variant_id=variant_id,
        serialized_item_id=serialized_item_id,
        movement_type=movement_type, # Assumes movement_type is an Enum member if models are updated
        quantity_change=quantity_change,
        weight_change_grams=weight_change_grams,
        reason=reason,
        related_order_id=related_order_id,
        related_user_id=related_user_id,
        notes=notes
    )
    db_session.add(movement)
    current_app.logger.debug(f"Stock movement object created for recording: {movement_type} for product ID {product_id}")
    return movement

def get_product_id_from_code(product_code, db_session=None):
    """Fetches product ID using product_code with SQLAlchemy (case-insensitive)."""
    from .models import Product 
    if not product_code: return None
    
    session_to_use = db_session or db.session
    product = session_to_use.query(Product.id).filter(func.upper(Product.product_code) == product_code.upper()).first()
    return product.id if product else None

def get_category_id_from_code(category_code, db_session=None):
    """Fetches category ID using category_code with SQLAlchemy (case-insensitive)."""
    from .models import Category 
    if not category_code: return None

    session_to_use = db_session or db.session
    # Apply case-insensitive comparison
    category = session_to_use.query(Category.id).filter(func.upper(Category.category_code) == category_code.upper()).first()
    return category.id if category else None
