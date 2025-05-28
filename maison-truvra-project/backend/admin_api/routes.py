import os
import json
import uuid
import sqlite3
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, current_app, send_from_directory, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity

# Import centralized utilities and services
from ..utils import (
    admin_required,
    format_datetime_for_display,
    parse_datetime_from_iso, # Keep if parsing dates from request body
    generate_slug,
    allowed_file,
    get_file_extension
)
from ..database import get_db_connection, query_db # record_stock_movement is not directly used here but in inventory
from ..services.asset_service import generate_qr_code_for_item, generate_item_passport, generate_product_label

# admin_api_bp is defined in admin_api/__init__.py
from . import admin_api_bp

# --- Dashboard ---
@admin_api_bp.route('/dashboard/stats', methods=['GET'])
@admin_required
def get_dashboard_stats():
    db = get_db_connection()
    try:
        total_users = query_db("SELECT COUNT(*) FROM users", db_conn=db, one=True)[0]
        total_products = query_db("SELECT COUNT(*) FROM products", db_conn=db, one=True)[0]
        total_orders = query_db("SELECT COUNT(*) FROM orders", db_conn=db, one=True)[0]
        # Add more stats as needed
        return jsonify({
            "total_users": total_users,
            "total_products": total_products,
            "total_orders": total_orders,
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching dashboard stats: {e}", exc_info=True)
        return jsonify(message="Failed to fetch dashboard statistics"), 500

# --- Category Management ---
@admin_api_bp.route('/categories', methods=['POST'])
@admin_required
def create_category():
    data = request.form.to_dict()
    name = data.get('name')
    description = data.get('description', '')
    parent_id = data.get('parent_id')
    image_file = request.files.get('image_url') # Matches form field name in admin_categories.js
    
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not name:
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details="Name is required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Name is required"), 400

    slug = generate_slug(name)
    db = get_db_connection()
    image_filename_db = None # Path to store in DB, relative to UPLOAD_FOLDER

    try:
        # Check for existing category by name or slug
        existing_category_name = query_db("SELECT id FROM categories WHERE name = ?", [name], db_conn=db, one=True)
        if existing_category_name:
            audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details=f"Category name '{name}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category name '{name}' already exists"), 409
        
        existing_category_slug = query_db("SELECT id FROM categories WHERE slug = ?", [slug], db_conn=db, one=True)
        if existing_category_slug:
            audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details=f"Category slug '{slug}' already exists (from name '{name}').", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category slug '{slug}' already exists. Try a different name."), 409

        if image_file and allowed_file(image_file.filename, current_app.config['ALLOWED_EXTENSIONS']):
            filename = secure_filename(f"category_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
            # Define specific upload subfolder for categories
            upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
            os.makedirs(upload_folder_categories, exist_ok=True)
            image_path_full = os.path.join(upload_folder_categories, filename)
            image_file.save(image_path_full)
            image_filename_db = os.path.join('categories', filename) # Store this relative path

        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO categories (name, description, parent_id, slug, image_url) VALUES (?, ?, ?, ?, ?)",
            (name, description, parent_id if parent_id and parent_id.strip() else None, slug, image_filename_db)
        )
        category_id = cursor.lastrowid
        db.commit()
        
        audit_logger.log_action(
            user_id=current_user_id, 
            action='create_category', 
            target_type='category', 
            target_id=category_id,
            details=f"Category '{name}' created with ID {category_id}.",
            status='success',
            ip_address=request.remote_addr
        )
        return jsonify(message="Category created successfully", category_id=category_id, slug=slug, image_url=image_filename_db), 201
    except sqlite3.IntegrityError as e:
        db.rollback()
        current_app.logger.error(f"Category creation integrity error: {e}")
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details=f"Database integrity error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Category name or slug likely already exists (DB integrity)."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error creating category: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to create category due to a server error."), 500

@admin_api_bp.route('/categories', methods=['GET'])
@admin_required
def get_categories():
    db = get_db_connection()
    try:
        categories_data = query_db("SELECT id, name, description, parent_id, slug, image_url, created_at, updated_at FROM categories ORDER BY name", db_conn=db)
        categories = [dict(row) for row in categories_data] if categories_data else []
        
        for category in categories:
            category['created_at'] = format_datetime_for_display(category['created_at'])
            category['updated_at'] = format_datetime_for_display(category['updated_at'])
            if category.get('image_url'):
                 category['image_full_url'] = url_for('admin_api.serve_asset', asset_relative_path=category['image_url'], _external=True)
        return jsonify(categories), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching categories: {e}", exc_info=True)
        return jsonify(message="Failed to fetch categories"), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['GET'])
@admin_required
def get_category(category_id):
    db = get_db_connection()
    try:
        category_data = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if category_data:
            category = dict(category_data)
            category['created_at'] = format_datetime_for_display(category['created_at'])
            category['updated_at'] = format_datetime_for_display(category['updated_at'])
            if category.get('image_url'):
                 category['image_full_url'] = url_for('admin_api.serve_asset', asset_relative_path=category['image_url'], _external=True)
            return jsonify(category), 200
        return jsonify(message="Category not found"), 404
    except Exception as e:
        current_app.logger.error(f"Error fetching category {category_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch category details"), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['PUT'])
@admin_required
def update_category(category_id):
    data = request.form.to_dict()
    name = data.get('name')
    description = data.get('description')
    parent_id_str = data.get('parent_id')
    image_file = request.files.get('image_url') # Matches form field name
    remove_image = data.get('remove_image') == 'true'

    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not name:
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details="Name is required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Name is required for update"), 400

    db = get_db_connection()
    try:
        current_category = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if not current_category:
            audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details="Category not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Category not found"), 404

        new_slug = generate_slug(name)
        image_filename_to_update_db = current_category['image_url']

        # Check for name/slug conflicts (excluding current category)
        if name != current_category['name']:
            existing_category_name = query_db("SELECT id FROM categories WHERE name = ? AND id != ?", [name, category_id], db_conn=db, one=True)
            if existing_category_name:
                audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details=f"Category name '{name}' already exists.", status='failure', ip_address=request.remote_addr)
                return jsonify(message=f"Another category with the name '{name}' already exists"), 409
        
        if new_slug != current_category['slug']: # Only check slug if name (and thus slug) changed
            existing_category_slug = query_db("SELECT id FROM categories WHERE slug = ? AND id != ?", [new_slug, category_id], db_conn=db, one=True)
            if existing_category_slug:
                audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details=f"Category slug '{new_slug}' already exists.", status='failure', ip_address=request.remote_addr)
                return jsonify(message=f"Another category with the generated slug '{new_slug}' already exists. Try a different name."), 409

        upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
        os.makedirs(upload_folder_categories, exist_ok=True)

        if remove_image and current_category['image_url']:
            full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_category['image_url'])
            if os.path.exists(full_old_image_path):
                try: os.remove(full_old_image_path)
                except OSError as e_rem: current_app.logger.error(f"Error removing old category image {full_old_image_path}: {e_rem}")
            image_filename_to_update_db = None
        elif image_file and allowed_file(image_file.filename, current_app.config['ALLOWED_EXTENSIONS']):
            if current_category['image_url']:
                full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_category['image_url'])
                if os.path.exists(full_old_image_path):
                    try: os.remove(full_old_image_path)
                    except OSError as e_rem_up: current_app.logger.error(f"Error removing old category image for update {full_old_image_path}: {e_rem_up}")
            
            filename = secure_filename(f"category_{new_slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
            image_path_full = os.path.join(upload_folder_categories, filename)
            image_file.save(image_path_full)
            image_filename_to_update_db = os.path.join('categories', filename)

        parent_id_to_update = None
        if parent_id_str and parent_id_str.strip():
            try:
                parent_id_to_update = int(parent_id_str)
                if parent_id_to_update == category_id: # Prevent self-parenting
                    audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details="Category cannot be its own parent.", status='failure', ip_address=request.remote_addr)
                    return jsonify(message="Category cannot be its own parent."), 400
            except ValueError:
                audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details="Invalid parent ID format.", status='failure', ip_address=request.remote_addr)
                return jsonify(message="Invalid parent ID format."), 400
        
        description_to_update = description if description is not None else current_category['description']

        cursor = db.cursor()
        cursor.execute(
            """UPDATE categories SET 
               name = ?, description = ?, parent_id = ?, slug = ?, image_url = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (name, description_to_update, parent_id_to_update, new_slug, image_filename_to_update_db, category_id)
        )
        db.commit()
        
        audit_logger.log_action(
            user_id=current_user_id, 
            action='update_category', 
            target_type='category', 
            target_id=category_id,
            details=f"Category '{name}' updated.",
            status='success',
            ip_address=request.remote_addr
        )
        return jsonify(message="Category updated successfully", slug=new_slug, image_url=image_filename_to_update_db), 200
    except sqlite3.IntegrityError as e:
        db.rollback()
        current_app.logger.error(f"Category update integrity error for ID {category_id}: {e}")
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details=f"Database integrity error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Category name or slug likely conflicts with an existing one (DB integrity)."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating category {category_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update category due to a server error."), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()

    try:
        category_to_delete = query_db("SELECT image_url, name FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if not category_to_delete:
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details="Category not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Category not found"), 404

        products_in_category = query_db("SELECT COUNT(*) FROM products WHERE category_id = ?", [category_id], db_conn=db, one=True)[0]
        if products_in_category > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details=f"Category '{category_to_delete['name']}' is in use by {products_in_category} products.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category '{category_to_delete['name']}' is in use by products and cannot be deleted. Reassign products first."), 409
        
        if category_to_delete['image_url']:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category_to_delete['image_url'])
            if os.path.exists(full_image_path):
                try: os.remove(full_image_path)
                except OSError as e_rem: current_app.logger.error(f"Error deleting category image {full_image_path}: {e_rem}")
        
        cursor = db.cursor()
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        db.commit()

        if cursor.rowcount > 0:
            audit_logger.log_action(
                user_id=current_user_id, 
                action='delete_category', 
                target_type='category', 
                target_id=category_id,
                details=f"Category '{category_to_delete['name']}' (ID: {category_id}) deleted.",
                status='success',
                ip_address=request.remote_addr
            )
            return jsonify(message=f"Category '{category_to_delete['name']}' deleted successfully"), 200
        else:
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details="Category not found during delete operation.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Category not found during delete operation"), 404
    except sqlite3.IntegrityError as e:
        db.rollback()
        current_app.logger.error(f"Integrity error deleting category {category_id}: {e}")
        audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details=f"Database integrity error: {e}. Category might still be in use.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete category due to integrity constraints (e.g. subcategories not handled by SET NULL)."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error deleting category {category_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete category"), 500

# --- Product Management ---
@admin_api_bp.route('/products', methods=['POST'])
@admin_required
def create_product():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()

    try:
        # Data from form (admin_products.js)
        data = request.form.to_dict()
        main_image_file = request.files.get('image_url_main') # Matches admin_products.js form field name
        
        # Map form field names to database column names
        name = data.get('name')
        sku_prefix = data.get('id') # Form 'id' is used as sku_prefix
        product_type = data.get('type', 'simple') # Default if not in form, though schema has it NOT NULL
        description = data.get('long_description', data.get('short_description', ''))
        category_name_from_form = data.get('category') # Form sends category name
        
        # Find category_id from category_name
        category_id = None
        if category_name_from_form:
            category_row = query_db("SELECT id FROM categories WHERE name = ?", [category_name_from_form], db_conn=db, one=True)
            if category_row:
                category_id = category_row['id']
            else:
                current_app.logger.warning(f"Category '{category_name_from_form}' not found for product creation.")
                # Optionally create category or return error
                # For now, allow null category_id if not found or not provided, schema allows NULL
        
        brand = data.get('brand', "Maison Trüvra")
        base_price_str = data.get('base_price')
        currency = data.get('currency', 'EUR')
        
        # 'initial_stock_quantity' from form maps to 'aggregate_stock_quantity' for simple products
        aggregate_stock_quantity_str = data.get('initial_stock_quantity', data.get('aggregate_stock_quantity', '0'))
        
        aggregate_stock_weight_grams_str = data.get('aggregate_stock_weight_grams')
        unit_of_measure = data.get('unit_of_measure')
        is_active = data.get('is_published', 'true').lower() == 'true'
        is_featured = data.get('is_featured', 'false').lower() == 'true'
        meta_title = data.get('meta_title', name) # Default meta_title to product name
        meta_description = data.get('meta_description', data.get('short_description'))
        slug = generate_slug(name)

        # Additional details from form (store in description or dedicated fields if schema supports)
        # species = data.get('species')
        # origin = data.get('origin')
        # seasonality = data.get('seasonality')
        # ideal_uses = data.get('ideal_uses')
        # sensory_desc_form = data.get('sensory_description')
        # pairing_sugg_form = data.get('pairing_suggestions')
        # For now, these are assumed to be part of long_description or need schema changes.

        required_fields_check = {'name': name, 'sku_prefix': sku_prefix, 'type': product_type}
        for field_name_key, field_val in required_fields_check.items():
            if not field_val:
                audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details=f"Missing required field: {field_name_key}", status='failure', ip_address=request.remote_addr)
                return jsonify(message=f"Missing required field: {field_name_key}"), 400
        
        existing_sku = query_db("SELECT id FROM products WHERE sku_prefix = ?", [sku_prefix], db_conn=db, one=True)
        if existing_sku:
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details=f"SKU prefix '{sku_prefix}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"SKU prefix '{sku_prefix}' already exists."), 409

        existing_slug = query_db("SELECT id FROM products WHERE slug = ?", [slug], db_conn=db, one=True)
        if existing_slug:
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details=f"Product name/slug '{slug}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Product name (slug: '{slug}') already exists. Choose a different name."), 409

        main_image_filename_db = None
        if main_image_file and allowed_file(main_image_file.filename, current_app.config['ALLOWED_EXTENSIONS']):
            filename = secure_filename(f"product_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(main_image_file.filename)}")
            upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
            os.makedirs(upload_folder_products, exist_ok=True)
            image_path_full = os.path.join(upload_folder_products, filename)
            main_image_file.save(image_path_full)
            main_image_filename_db = os.path.join('products', filename)

        try:
            base_price = float(base_price_str) if base_price_str is not None and base_price_str != '' else None
            aggregate_stock_quantity = int(aggregate_stock_quantity_str) if aggregate_stock_quantity_str is not None else 0
            aggregate_stock_weight_grams = float(aggregate_stock_weight_grams_str) if aggregate_stock_weight_grams_str else None
        except ValueError as ve:
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details=f"Invalid data type for price or stock: {ve}", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Invalid data type for price or stock: {ve}"), 400

        if product_type == 'simple' and base_price is None:
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details="Base price is required for simple products.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Base price is required for simple products."), 400
        
        weight_options_json_str = data.get('weight_options', '[]') # From admin_products.js, this is a JSON string
        weight_options = json.loads(weight_options_json_str) if weight_options_json_str else []

        if product_type == 'variable_weight' and not unit_of_measure and not weight_options:
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details="Unit of measure and/or weight options are required for variable weight products.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Unit of measure and/or weight options are required for variable weight products."), 400

        cursor = db.cursor()
        sql_insert_product = """
            INSERT INTO products (name, description, category_id, brand, sku_prefix, type, 
                                   base_price, currency, main_image_url, aggregate_stock_quantity, 
                                   aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured, 
                                   meta_title, meta_description, slug)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        product_args = (
            name, description, category_id, brand, sku_prefix, product_type, 
            base_price, currency, main_image_filename_db, aggregate_stock_quantity, 
            aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured, 
            meta_title, meta_description, slug
        )
        cursor.execute(sql_insert_product, product_args)
        product_id = cursor.lastrowid

        if product_type == 'variable_weight' and weight_options:
            try:
                if not isinstance(weight_options, list): raise ValueError("Weight options must be a list.")
                for option in weight_options:
                    if not all(k in option for k in ('weight_grams', 'price', 'sku_suffix', 'initial_stock')):
                        raise ValueError("Missing fields in weight option (weight_grams, price, sku_suffix, initial_stock).")
                    
                    variant_stock = int(option.get('initial_stock', 0))
                    
                    cursor.execute(
                        """INSERT INTO product_weight_options 
                           (product_id, weight_grams, price, sku_suffix, aggregate_stock_quantity, is_active)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (product_id, float(option['weight_grams']), float(option['price']), option['sku_suffix'],
                         variant_stock, option.get('is_active', True))
                    )
                    # Optionally record stock movement for each variant's initial stock
                    if variant_stock > 0:
                        variant_option_id = cursor.lastrowid
                        record_stock_movement(db, product_id, 'initial_stock_variant', quantity_change=variant_stock, variant_id=variant_option_id, reason="Initial stock for new variant")

            except (json.JSONDecodeError, ValueError) as e_opt:
                db.rollback() 
                current_app.logger.error(f"Error processing product weight options: {e_opt}")
                audit_logger.log_action(user_id=current_user_id, action='create_product_fail', target_type='product', target_id=product_id, details=f"Invalid weight options format: {e_opt}", status='failure', ip_address=request.remote_addr)
                return jsonify(message=f"Invalid format for weight options: {e_opt}"), 400
        
        # Record initial stock for simple product if quantity > 0
        if product_type == 'simple' and aggregate_stock_quantity > 0:
            record_stock_movement(db, product_id, 'initial_stock', quantity_change=aggregate_stock_quantity, reason="Initial stock for new simple product")

        db.commit()
        audit_logger.log_action(
            user_id=current_user_id, 
            action='create_product', 
            target_type='product', 
            target_id=product_id,
            details=f"Product '{name}' (SKU: {sku_prefix}) created.",
            status='success',
            ip_address=request.remote_addr
        )
        
        created_product_data = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        response_data = {"message": "Product created successfully", "product_id": product_id, "slug": slug}
        if created_product_data:
            response_data["product"] = dict(created_product_data)
            # Add asset paths if generated synchronously (asset_service.py handles this)
            # For example, if generate_qr_code_for_item, etc., are called here or in a service layer
            # after product creation and paths are returned.
            # This example assumes asset generation might be a separate step or async.
            # If paths are available, they would be added to response_data["product"]["assets"]

        return jsonify(response_data), 201

    except sqlite3.IntegrityError as e:
        db.rollback()
        current_app.logger.error(f"Product creation integrity error: {e}")
        audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details=f"Database integrity error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Product SKU prefix or name (slug) likely already exists."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error creating product: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to create product due to an unexpected error."), 500


@admin_api_bp.route('/products/<int:product_id>', methods=['PUT'])
@admin_required
def update_product(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()

    try:
        current_product_row = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not current_product_row:
            audit_logger.log_action(user_id=current_user_id, action='update_product_fail', target_type='product', target_id=product_id, details="Product not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Product not found"), 404
        current_product = dict(current_product_row)

        data = request.form.to_dict()
        main_image_file = request.files.get('image_url_main') # Matches admin_products.js
        remove_main_image = data.get('remove_main_image') == 'true'

        name = data.get('name', current_product['name'])
        new_slug = generate_slug(name) if data.get('name') and name != current_product['name'] else current_product['slug']
        
        new_sku_prefix = data.get('id', current_product['sku_prefix']) # 'id' from form is sku_prefix
        if new_sku_prefix != current_product['sku_prefix']:
            existing_sku = query_db("SELECT id FROM products WHERE sku_prefix = ? AND id != ?", [new_sku_prefix, product_id], db_conn=db, one=True)
            if existing_sku:
                audit_logger.log_action(user_id=current_user_id, action='update_product_fail', target_type='product', target_id=product_id, details=f"SKU prefix '{new_sku_prefix}' already exists.", status='failure', ip_address=request.remote_addr)
                return jsonify(message=f"SKU prefix '{new_sku_prefix}' already exists."), 409
        
        if new_slug != current_product['slug']: # Check if slug actually changed
            existing_slug = query_db("SELECT id FROM products WHERE slug = ? AND id != ?", [new_slug, product_id], db_conn=db, one=True)
            if existing_slug:
                audit_logger.log_action(user_id=current_user_id, action='update_product_fail', target_type='product', target_id=product_id, details=f"Product name/slug '{new_slug}' already exists.", status='failure', ip_address=request.remote_addr)
                return jsonify(message=f"Product name (slug: '{new_slug}') already exists."), 409
        
        upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
        os.makedirs(upload_folder_products, exist_ok=True)
        main_image_filename_to_update_db = current_product['main_image_url']

        if remove_main_image and current_product['main_image_url']:
            full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_product['main_image_url'])
            if os.path.exists(full_old_image_path):
                try: os.remove(full_old_image_path)
                except OSError as e_rem: current_app.logger.error(f"Error removing old product image {full_old_image_path}: {e_rem}")
            main_image_filename_to_update_db = None
        elif main_image_file and allowed_file(main_image_file.filename, current_app.config['ALLOWED_EXTENSIONS']):
            if current_product['main_image_url']:
                full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_product['main_image_url'])
                if os.path.exists(full_old_image_path):
                    try: os.remove(full_old_image_path)
                    except OSError as e_rem_up: current_app.logger.error(f"Error removing old product image for update {full_old_image_path}: {e_rem_up}")

            filename = secure_filename(f"product_{new_slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(main_image_file.filename)}")
            image_path_full = os.path.join(upload_folder_products, filename)
            main_image_file.save(image_path_full)
            main_image_filename_to_update_db = os.path.join('products', filename)

        # Consolidate all fields for the products table update
        update_payload_product = {
            'name': name,
            'slug': new_slug,
            'sku_prefix': new_sku_prefix,
            'description': data.get('long_description', data.get('short_description', current_product['description'])),
            'category_id': int(data.get('category_id', data.get('category'))) if (data.get('category_id') or data.get('category')) else current_product['category_id'],
            'brand': data.get('brand', current_product['brand']),
            'type': data.get('type', current_product['type']),
            'base_price': float(data['base_price']) if data.get('base_price') is not None and data.get('base_price') != '' else current_product['base_price'],
            'currency': data.get('currency', current_product['currency']),
            'main_image_url': main_image_filename_to_update_db,
            'aggregate_stock_quantity': int(data.get('initial_stock_quantity', data.get('aggregate_stock_quantity'))) if (data.get('initial_stock_quantity') is not None or data.get('aggregate_stock_quantity') is not None) else current_product['aggregate_stock_quantity'],
            'aggregate_stock_weight_grams': float(data['aggregate_stock_weight_grams']) if data.get('aggregate_stock_weight_grams') is not None and data.get('aggregate_stock_weight_grams') != '' else current_product['aggregate_stock_weight_grams'],
            'unit_of_measure': data.get('unit_of_measure', current_product['unit_of_measure']),
            'is_active': data.get('is_published', str(current_product['is_active'])).lower() == 'true',
            'is_featured': data.get('is_featured', str(current_product['is_featured'])).lower() == 'true',
            'meta_title': data.get('meta_title', current_product['meta_title'] or name),
            'meta_description': data.get('meta_description', current_product['meta_description'] or data.get('short_description')),
        }
        
        # Additional fields from admin_products.js form (species, origin etc.) are not in schema.sql's products table directly.
        # If they need to be stored, the schema needs adjustment (e.g., a JSONB column or separate columns).
        # For now, they are ignored for the DB update if not in schema.

        if update_payload_product['type'] == 'simple' and update_payload_product['base_price'] is None:
            audit_logger.log_action(user_id=current_user_id, action='update_product_fail', target_type='product', target_id=product_id, details="Base price is required for simple products.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Base price is required for simple products."), 400
        
        weight_options_json_str = data.get('weight_options', '[]')
        weight_options = json.loads(weight_options_json_str) if weight_options_json_str else []

        if update_payload_product['type'] == 'variable_weight':
            if not update_payload_product['unit_of_measure'] and not weight_options:
                 audit_logger.log_action(user_id=current_user_id, action='update_product_fail', target_type='product', target_id=product_id, details="Unit of measure and options required for variable weight.", status='failure', ip_address=request.remote_addr)
                 return jsonify(message="Unit of measure and weight options are required for variable weight products."), 400
            if weight_options: # If variants are provided, base_price and simple stock should be nullified on main product
                update_payload_product['base_price'] = None
                update_payload_product['aggregate_stock_quantity'] = 0 

        set_clause_product = ", ".join([f"{key} = ?" for key in update_payload_product.keys()])
        sql_args_product = list(update_payload_product.values())
        sql_args_product.append(product_id)

        cursor = db.cursor()
        cursor.execute(f"UPDATE products SET {set_clause_product}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", sql_args_product)

        # Handle product_weight_options: delete existing and re-insert/update based on form data
        if update_payload_product['type'] == 'variable_weight':
            try:
                if not isinstance(weight_options, list): raise ValueError("Weight options must be a list.")
                
                existing_options_rows = query_db("SELECT option_id FROM product_weight_options WHERE product_id = ?", [product_id], db_conn=db)
                existing_option_ids = {row['option_id'] for row in existing_options_rows} if existing_options_rows else set()
                submitted_option_ids = set()

                for option_data in weight_options:
                    if not all(k in option_data for k in ('weight_grams', 'price', 'sku_suffix', 'initial_stock')): # initial_stock from form
                        raise ValueError("Missing fields in weight option.")
                    
                    option_id_form = option_data.get('option_id') # This should be sent from form for existing options
                    variant_stock = int(option_data.get('initial_stock', 0)) # 'initial_stock' from form

                    if option_id_form and int(option_id_form) in existing_option_ids: # Update existing
                        cursor.execute(
                            """UPDATE product_weight_options SET weight_grams = ?, price = ?, sku_suffix = ?, 
                               aggregate_stock_quantity = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                               WHERE option_id = ? AND product_id = ?""",
                            (float(option_data['weight_grams']), float(option_data['price']), option_data['sku_suffix'],
                             variant_stock, option_data.get('is_active', True), int(option_id_form), product_id)
                        )
                        submitted_option_ids.add(int(option_id_form))
                    else: # Insert new
                        cursor.execute(
                            """INSERT INTO product_weight_options 
                               (product_id, weight_grams, price, sku_suffix, aggregate_stock_quantity, is_active)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (product_id, float(option_data['weight_grams']), float(option_data['price']), option_data['sku_suffix'],
                             variant_stock, option_data.get('is_active', True))
                        )
                
                options_to_delete = existing_option_ids - submitted_option_ids
                for opt_id_del in options_to_delete:
                    cursor.execute("DELETE FROM product_weight_options WHERE option_id = ?", (opt_id_del,))

            except (json.JSONDecodeError, ValueError) as e_opt:
                db.rollback()
                current_app.logger.error(f"Error processing product weight options for update: {e_opt}")
                audit_logger.log_action(user_id=current_user_id, action='update_product_fail', target_type='product', target_id=product_id, details=f"Invalid weight options format: {e_opt}", status='failure', ip_address=request.remote_addr)
                return jsonify(message=f"Invalid format for weight options: {e_opt}"), 400
        elif update_payload_product['type'] == 'simple': # If product type changed to simple, clear all variants
            cursor.execute("DELETE FROM product_weight_options WHERE product_id = ?", (product_id,))

        db.commit()
        audit_logger.log_action(
            user_id=current_user_id, 
            action='update_product', 
            target_type='product', 
            target_id=product_id,
            details=f"Product '{update_payload_product['name']}' (SKU: {update_payload_product['sku_prefix']}) updated.",
            status='success',
            ip_address=request.remote_addr
        )
        
        # Re-fetch the product to include any changes and potentially generated asset URLs
        updated_product_full_data = get_product(product_id).get_json() # Call the GET endpoint logic
        return jsonify(message="Product updated successfully", product=updated_product_full_data), 200

    except sqlite3.IntegrityError as e:
        db.rollback()
        current_app.logger.error(f"Product update integrity error for ID {product_id}: {e}")
        audit_logger.log_action(user_id=current_user_id, action='update_product_fail', target_type='product', target_id=product_id, details=f"Database integrity error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Product SKU prefix or name (slug) likely conflicts with an existing one."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating product {product_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='update_product_fail', target_type='product', target_id=product_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update product due to an unexpected error."), 500

# ... (The rest of the routes: DELETE Product, Product Image Management, User Management, Order Management, Review Management, Asset Serving, Settings Management)
# These routes would be updated similarly to use the centralized `admin_required` decorator,
# `current_app.audit_log_service`, `get_db_connection()`, `query_db`,
# and `url_for('admin_api.serve_asset', ...)` for asset URLs.
# For brevity, I am not repeating all of them here but the pattern is established above.

# --- Asset Serving ---
# This route serves files from UPLOAD_FOLDER (for categories, products)
# and ASSET_STORAGE_PATH (for qr_codes, passports, labels, invoices).
# asset_relative_path includes the first-level directory, e.g., "categories/image.jpg"
@admin_api_bp.route('/assets/<path:asset_relative_path>')
@admin_required
def serve_asset(asset_relative_path):
    path_parts = asset_relative_path.split(os.sep, 1)
    top_level_folder = path_parts[0]
    
    upload_dirs = ['categories', 'products', 'professional_documents']
    generated_asset_dirs = ['qr_codes', 'passports', 'labels', 'invoices']

    base_directory_to_serve_from = None

    if top_level_folder in upload_dirs:
        base_directory_to_serve_from = current_app.config['UPLOAD_FOLDER']
        # asset_relative_path is already correct for send_from_directory
    elif top_level_folder in generated_asset_dirs:
        base_directory_to_serve_from = current_app.config['ASSET_STORAGE_PATH']
        # asset_relative_path is already correct for send_from_directory
    else:
        current_app.logger.warning(f"Asset serving attempt for unknown top-level folder: {top_level_folder} in path {asset_relative_path}")
        return jsonify(message="Forbidden: Invalid asset category"), 403

    # Security check: Ensure the final path is within the intended base directory
    # os.path.abspath resolves ".."
    full_file_path = os.path.abspath(os.path.join(base_directory_to_serve_from, asset_relative_path))
    
    # Check if the resolved path is still within the base_directory_to_serve_from
    # os.path.commonpath can be used, or string startswith on abspaths
    if not full_file_path.startswith(os.path.abspath(base_directory_to_serve_from) + os.sep):
        current_app.logger.warning(f"Directory traversal attempt or invalid asset path. Base: {base_directory_to_serve_from}, Relative: {asset_relative_path}, Resolved: {full_file_path}")
        return jsonify(message="Forbidden: Invalid path"), 403

    if not os.path.isfile(full_file_path):
        current_app.logger.warning(f"Asset not found: {full_file_path} (Relative from app root: {asset_relative_path})")
        return jsonify(message="Asset not found"), 404

    # send_from_directory takes the directory and the filename (which can include subpaths from that directory)
    # Here, asset_relative_path is the path relative to base_directory_to_serve_from
    current_app.logger.debug(f"Serving asset: Dir='{base_directory_to_serve_from}', File='{asset_relative_path}'")
    return send_from_directory(base_directory_to_serve_from, asset_relative_path)

# --- User Management (Example continuation) ---
@admin_api_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user_details(user_id): # Renamed from get_user for clarity
    db = get_db_connection()
    try:
        user_data = query_db("SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, vat_number, siret_number, professional_status, created_at, updated_at FROM users WHERE id = ?", [user_id], db_conn=db, one=True)
        if not user_data:
            return jsonify(message="User not found"), 404
        
        user = dict(user_data)
        user['created_at'] = format_datetime_for_display(user['created_at'])
        user['updated_at'] = format_datetime_for_display(user['updated_at'])
        
        # Fetch user's orders (example)
        orders_data = query_db("SELECT id as order_id, order_date, total_amount, status FROM orders WHERE user_id = ? ORDER BY order_date DESC", [user_id], db_conn=db)
        user['orders'] = [dict(row) for row in orders_data] if orders_data else []
        for order in user['orders']:
            order['order_date'] = format_datetime_for_display(order['order_date'])
            
        return jsonify(user), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching details for user {user_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch user details"), 500

# --- Order Management (Example continuation) ---
@admin_api_bp.route('/orders/<int:order_id>', methods=['GET'])
@admin_required
def get_order_details(order_id): # Renamed for clarity
    db = get_db_connection()
    try:
        order_data = query_db(
            """SELECT o.*, u.email as customer_email, 
                      (u.first_name || ' ' || u.last_name) as customer_name 
               FROM orders o 
               JOIN users u ON o.user_id = u.id 
               WHERE o.id = ?""", [order_id], db_conn=db, one=True)
        
        if not order_data:
            return jsonify(message="Order not found"), 404
            
        order = dict(order_data)
        order['order_date'] = format_datetime_for_display(order['order_date'])
        order['created_at'] = format_datetime_for_display(order['created_at'])
        order['updated_at'] = format_datetime_for_display(order['updated_at'])
        
        items_data = query_db(
            """SELECT oi.id as item_id, oi.product_id, oi.product_name, oi.quantity, 
                      oi.price_at_purchase, oi.variant, oi.variant_option_id,
                      p.sku_prefix, si.item_uid as serialized_item_uid
               FROM order_items oi
               LEFT JOIN products p ON oi.product_id = p.id
               LEFT JOIN product_weight_options pwo ON oi.variant_option_id = pwo.option_id
               LEFT JOIN serialized_inventory_items si ON oi.serialized_item_id = si.id
               WHERE oi.order_id = ?""", [order_id], db_conn=db)
        order['items'] = [dict(row) for row in items_data] if items_data else []
        
        # Fetch order notes (if schema has an order_notes table or similar)
        # For now, assuming notes are part of the orders table or a separate simple log
        # Example: If notes are stored in a JSON field or separate table
        # order_notes_data = query_db("SELECT content, admin_user, created_at FROM order_notes WHERE order_id = ? ORDER BY created_at ASC", [order_id], db_conn=db)
        # order['notes'] = [dict(note) for note in order_notes_data] if order_notes_data else []

        return jsonify(order), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching details for order {order_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch order details"), 500

# --- Settings Management ---
@admin_api_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings():
    db = get_db_connection()
    try:
        settings_data = query_db("SELECT key, value, description FROM settings", db_conn=db)
        settings = {row['key']: {'value': row['value'], 'description': row['description']} for row in settings_data} if settings_data else {}
        return jsonify(settings), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching settings: {e}", exc_info=True)
        return jsonify(message="Failed to fetch settings"), 500

@admin_api_bp.route('/settings', methods=['POST'])
@admin_required
def update_settings():
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    data = request.json

    if not data:
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_fail', details="No settings data provided.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="No settings data provided"), 400
    
    updated_keys = []
    try:
        cursor = db.cursor()
        for key, value_obj in data.items(): # Assuming frontend sends {"key": {"value": "...", "description": "..."}} or just {"key":"value"}
            value_to_store = value_obj
            if isinstance(value_obj, dict): # If frontend sends more details
                value_to_store = value_obj.get('value')
                # description_to_store = value_obj.get('description') # Could update description too

            if value_to_store is not None: # Allow clearing a setting by sending null? Or handle differently.
                cursor.execute(
                    "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (key, str(value_to_store)) # Ensure value is stored as text
                )
                updated_keys.append(key)
        db.commit()
        audit_logger.log_action(
            user_id=current_admin_id, 
            action='update_settings', 
            target_type='application_settings',
            details=f"Settings updated: {', '.join(updated_keys)}",
            status='success',
            ip_address=request.remote_addr
        )
        return jsonify(message="Settings updated successfully", updated_settings=updated_keys), 200
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating settings: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update settings"), 500

```

This provides the requested `admin_api/routes.py` file with the integrated changes.
The main structural issues in the backend Python code should now be largely addressed. The next logical step would be to ensure the frontend HTML and JavaScript files correctly reference assets and scripts, and that any redundant frontend JS bundles are removed in favor of the modular scripts.Okay, I will provide the full, updated content for `maison-truvra-project/backend/admin_api/routes.py`.

This version uses the centralized `admin_required` decorator from `backend.utils.py`, ensures consistent use of `current_app.audit_log_service`, `get_db_connection()`, `query_db`, date formatting functions, and `url_for` for generating asset URLs where appropriate. It also includes fixes and refinements to the product and category management logic based on the previous refactoring.


```python
import os
import json
import uuid
import sqlite3 # For specific error handling if needed
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, current_app, send_from_directory, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity

# Import centralized utilities and services
from ..utils import (
    admin_required,
    format_datetime_for_display,
    # parse_datetime_from_iso, # Not directly used in this version of admin_api, but available in utils
    generate_slug,
    allowed_file,
    get_file_extension
)
from ..database import get_db_connection, query_db, record_stock_movement # record_stock_movement for potential direct use
from ..services.asset_service import generate_qr_code_for_item, generate_item_passport, generate_product_label

# admin_api_bp is defined in admin_api/__init__.py
from . import admin_api_bp

# --- Dashboard ---
@admin_api_bp.route('/dashboard/stats', methods=['GET'])
@admin_required
def get_dashboard_stats():
    db = get_db_connection()
    try:
        total_users = query_db("SELECT COUNT(*) FROM users", db_conn=db, one=True)[0]
        total_products = query_db("SELECT COUNT(*) FROM products", db_conn=db, one=True)[0]
        total_orders = query_db("SELECT COUNT(*) FROM orders", db_conn=db, one=True)[0]
        return jsonify({
            "total_users": total_users,
            "total_products": total_products,
            "total_orders": total_orders,
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching dashboard stats: {e}", exc_info=True)
        return jsonify(message="Failed to fetch dashboard statistics"), 500

# --- Category Management ---
@admin_api_bp.route('/categories', methods=['POST'])
@admin_required
def create_category():
    data = request.form.to_dict()
    name = data.get('name')
    description = data.get('description', '')
    parent_id_str = data.get('parent_id')
    image_file = request.files.get('image_url')
    
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not name:
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details="Name is required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Name is required"), 400

    slug = generate_slug(name)
    db = get_db_connection()
    image_filename_db = None

    try:
        existing_category_name = query_db("SELECT id FROM categories WHERE name = ?", [name], db_conn=db, one=True)
        if existing_category_name:
            audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details=f"Category name '{name}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category name '{name}' already exists"), 409
        
        existing_category_slug = query_db("SELECT id FROM categories WHERE slug = ?", [slug], db_conn=db, one=True)
        if existing_category_slug:
            audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details=f"Category slug '{slug}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category slug '{slug}' already exists. Try a different name."), 409

        if image_file and allowed_file(image_file.filename, current_app.config['ALLOWED_EXTENSIONS']):
            filename = secure_filename(f"category_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
            upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
            os.makedirs(upload_folder_categories, exist_ok=True)
            image_path_full = os.path.join(upload_folder_categories, filename)
            image_file.save(image_path_full)
            image_filename_db = os.path.join('categories', filename)

        parent_id = int(parent_id_str) if parent_id_str and parent_id_str.strip() else None

        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO categories (name, description, parent_id, slug, image_url) VALUES (?, ?, ?, ?, ?)",
            (name, description, parent_id, slug, image_filename_db)
        )
        category_id = cursor.lastrowid
        db.commit()
        
        audit_logger.log_action(user_id=current_user_id, action='create_category', target_type='category', target_id=category_id, details=f"Category '{name}' created.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Category created successfully", category_id=category_id, slug=slug, image_url=image_filename_db), 201
    except sqlite3.IntegrityError as e:
        db.rollback()
        current_app.logger.error(f"Category creation integrity error: {e}")
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details=f"Database integrity error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Category name or slug likely already exists."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error creating category: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to create category"), 500

@admin_api_bp.route('/categories', methods=['GET'])
@admin_required
def get_categories():
    db = get_db_connection()
    try:
        categories_data = query_db("SELECT id, name, description, parent_id, slug, image_url, created_at, updated_at FROM categories ORDER BY name", db_conn=db)
        categories = [dict(row) for row in categories_data] if categories_data else []
        
        for category in categories:
            category['created_at'] = format_datetime_for_display(category['created_at'])
            category['updated_at'] = format_datetime_for_display(category['updated_at'])
            if category.get('image_url'):
                 category['image_full_url'] = url_for('admin_api.serve_asset', asset_relative_path=category['image_url'], _external=True)
        return jsonify(categories), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching categories: {e}", exc_info=True)
        return jsonify(message="Failed to fetch categories"), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['GET'])
@admin_required
def get_category_detail(category_id): # Renamed for clarity
    db = get_db_connection()
    try:
        category_data = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if category_data:
            category = dict(category_data)
            category['created_at'] = format_datetime_for_display(category['created_at'])
            category['updated_at'] = format_datetime_for_display(category['updated_at'])
            if category.get('image_url'):
                 category['image_full_url'] = url_for('admin_api.serve_asset', asset_relative_path=category['image_url'], _external=True)
            return jsonify(category), 200
        return jsonify(message="Category not found"), 404
    except Exception as e:
        current_app.logger.error(f"Error fetching category {category_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch category details"), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['PUT'])
@admin_required
def update_category(category_id):
    data = request.form.to_dict()
    name = data.get('name')
    description = data.get('description')
    parent_id_str = data.get('parent_id')
    image_file = request.files.get('image_url')
    remove_image = data.get('remove_image') == 'true'

    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not name:
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details="Name is required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Name is required for update"), 400

    db = get_db_connection()
    try:
        current_category_row = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if not current_category_row:
            audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details="Category not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Category not found"), 404
        current_category = dict(current_category_row)

        new_slug = generate_slug(name)
        image_filename_to_update_db = current_category['image_url']

        if name != current_category['name']:
            existing_category_name = query_db("SELECT id FROM categories WHERE name = ? AND id != ?", [name, category_id], db_conn=db, one=True)
            if existing_category_name:
                audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details=f"Category name '{name}' already exists.", status='failure', ip_address=request.remote_addr)
                return jsonify(message=f"Another category with the name '{name}' already exists"), 409
        
        if new_slug != current_category['slug']:
            existing_category_slug = query_db("SELECT id FROM categories WHERE slug = ? AND id != ?", [new_slug, category_id], db_conn=db, one=True)
            if existing_category_slug:
                audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details=f"Category slug '{new_slug}' already exists.", status='failure', ip_address=request.remote_addr)
                return jsonify(message=f"Another category with the generated slug '{new_slug}' already exists. Try a different name."), 409

        upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
        os.makedirs(upload_folder_categories, exist_ok=True)

        if remove_image and current_category['image_url']:
            full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_category['image_url'])
            if os.path.exists(full_old_image_path):
                try: os.remove(full_old_image_path)
                except OSError as e_rem: current_app.logger.error(f"Error removing old category image {full_old_image_path}: {e_rem}")
            image_filename_to_update_db = None
        elif image_file and allowed_file(image_file.filename, current_app.config['ALLOWED_EXTENSIONS']):
            if current_category['image_url']:
                full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_category['image_url'])
                if os.path.exists(full_old_image_path):
                    try: os.remove(full_old_image_path)
                    except OSError as e_rem_up: current_app.logger.error(f"Error removing old category image for update {full_old_image_path}: {e_rem_up}")
            
            filename = secure_filename(f"category_{new_slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
            image_path_full = os.path.join(upload_folder_categories, filename)
            image_file.save(image_path_full)
            image_filename_to_update_db = os.path.join('categories', filename)

        parent_id_to_update = None
        if parent_id_str and parent_id_str.strip():
            try:
                parent_id_to_update = int(parent_id_str)
                if parent_id_to_update == category_id:
                    audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details="Category cannot be its own parent.", status='failure', ip_address=request.remote_addr)
                    return jsonify(message="Category cannot be its own parent."), 400
            except ValueError:
                audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details="Invalid parent ID format.", status='failure', ip_address=request.remote_addr)
                return jsonify(message="Invalid parent ID format."), 400
        
        description_to_update = description if description is not None else current_category['description']

        cursor = db.cursor()
        cursor.execute(
            """UPDATE categories SET 
               name = ?, description = ?, parent_id = ?, slug = ?, image_url = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (name, description_to_update, parent_id_to_update, new_slug, image_filename_to_update_db, category_id)
        )
        db.commit()
        
        audit_logger.log_action(user_id=current_user_id, action='update_category', target_type='category', target_id=category_id, details=f"Category '{name}' updated.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Category updated successfully", slug=new_slug, image_url=image_filename_to_update_db), 200
    except sqlite3.IntegrityError as e:
        db.rollback()
        current_app.logger.error(f"Category update integrity error for ID {category_id}: {e}")
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details=f"Database integrity error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Category name or slug likely conflicts with an existing one."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating category {category_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update category"), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()

    try:
        category_to_delete = query_db("SELECT image_url, name FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if not category_to_delete:
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details="Category not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Category not found"), 404

        products_in_category = query_db("SELECT COUNT(*) FROM products WHERE category_id = ?", [category_id], db_conn=db, one=True)[0]
        if products_in_category > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details=f"Category '{category_to_delete['name']}' is in use by {products_in_category} products.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category '{category_to_delete['name']}' is in use by products. Reassign products first."), 409
        
        if category_to_delete['image_url']:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category_to_delete['image_url'])
            if os.path.exists(full_image_path):
                try: os.remove(full_image_path)
                except OSError as e_rem: current_app.logger.error(f"Error deleting category image {full_image_path}: {e_rem}")
        
        cursor = db.cursor()
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        db.commit()

        if cursor.rowcount > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_category', target_type='category', target_id=category_id, details=f"Category '{category_to_delete['name']}' deleted.", status='success', ip_address=request.remote_addr)
            return jsonify(message=f"Category '{category_to_delete['name']}' deleted successfully"), 200
        else: # Should be caught by initial check
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details="Category not found during delete op.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Category not found during delete operation"), 404

    except sqlite3.IntegrityError as e: # e.g. if subcategories exist and parent_id is RESTRICT
        db.rollback()
        current_app.logger.error(f"Integrity error deleting category {category_id}: {e}")
        audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details=f"DB integrity error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete category due to DB integrity constraints."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error deleting category {category_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete category"), 500

# --- Product Management ---
@admin_api_bp.route('/products', methods=['POST'])
@admin_required
def create_product():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()

    try:
        data = request.form.to_dict()
        main_image_file = request.files.get('image_url_main') # From admin_products.js form

        # Map form fields to DB columns (ensure names match schema.sql and form)
        name = data.get('name')
        sku_prefix = data.get('id') # Form 'id' is product's SKU prefix
        product_type = data.get('type', 'simple')
        description = data.get('long_description', data.get('short_description', ''))
        
        category_name_from_form = data.get('category') # Form sends category name
        category_id = None
        if category_name_from_form:
            category_row = query_db("SELECT id FROM categories WHERE name = ?", [category_name_from_form], db_conn=db, one=True)
            if category_row: category_id = category_row['id']
            else: current_app.logger.warning(f"Category '{category_name_from_form}' not found during product creation.")

        brand = data.get('brand', "Maison Trüvra")
        base_price_str = data.get('base_price')
        currency = data.get('currency', 'EUR')
        aggregate_stock_quantity_str = data.get('initial_stock_quantity', '0') # For simple products
        
        # Fields for 'variable_weight' products
        aggregate_stock_weight_grams_str = data.get('aggregate_stock_weight_grams')
        unit_of_measure = data.get('unit_of_measure')
        
        is_active = data.get('is_published', 'true').lower() == 'true' # 'is_published' from form
        is_featured = data.get('is_featured', 'false').lower() == 'true'
        meta_title = data.get('meta_title', name)
        meta_description = data.get('meta_description', data.get('short_description', ''))
        slug = generate_slug(name)

        # Validation
        if not all([name, sku_prefix, product_type]):
            return jsonify(message="Name, SKU Prefix (ID from form), and Type are required."), 400
        
        if query_db("SELECT id FROM products WHERE sku_prefix = ?", [sku_prefix], db_conn=db, one=True):
            return jsonify(message=f"SKU prefix '{sku_prefix}' already exists."), 409
        if query_db("SELECT id FROM products WHERE slug = ?", [slug], db_conn=db, one=True):
            return jsonify(message=f"Product name (slug: '{slug}') already exists."), 409

        main_image_filename_db = None
        if main_image_file and allowed_file(main_image_file.filename, current_app.config['ALLOWED_EXTENSIONS']):
            filename = secure_filename(f"product_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(main_image_file.filename)}")
            upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
            os.makedirs(upload_folder_products, exist_ok=True)
            main_image_file.save(os.path.join(upload_folder_products, filename))
            main_image_filename_db = os.path.join('products', filename)

        base_price = float(base_price_str) if base_price_str is not None and base_price_str != '' else None
        aggregate_stock_quantity = int(aggregate_stock_quantity_str) if aggregate_stock_quantity_str is not None else 0
        aggregate_stock_weight_grams = float(aggregate_stock_weight_grams_str) if aggregate_stock_weight_grams_str else None

        if product_type == 'simple' and base_price is None:
            return jsonify(message="Base price is required for simple products."), 400
        
        weight_options_json_str = data.get('weight_options', '[]')
        weight_options = json.loads(weight_options_json_str) if weight_options_json_str else []

        if product_type == 'variable_weight' and not unit_of_measure and not weight_options:
             return jsonify(message="Unit of measure and/or weight options are required for variable weight products."), 400

        cursor = db.cursor()
        cursor.execute(
            """INSERT INTO products (name, description, category_id, brand, sku_prefix, type, 
                                   base_price, currency, main_image_url, aggregate_stock_quantity, 
                                   aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured, 
                                   meta_title, meta_description, slug)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, description, category_id, brand, sku_prefix, product_type, 
             base_price, currency, main_image_filename_db, 
             aggregate_stock_quantity if product_type == 'simple' else 0, # Base product stock is 0 if variants manage stock
             aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured, 
             meta_title, meta_description, slug)
        )
        product_id = cursor.lastrowid

        if product_type == 'variable_weight' and weight_options:
            for option in weight_options:
                if not all(k in option for k in ('weight_grams', 'price', 'sku_suffix', 'initial_stock')):
                    raise ValueError("Missing fields in weight option.")
                variant_stock = int(option.get('initial_stock', 0))
                cursor.execute(
                    """INSERT INTO product_weight_options 
                       (product_id, weight_grams, price, sku_suffix, aggregate_stock_quantity, is_active)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (product_id, float(option['weight_grams']), float(option['price']), option['sku_suffix'],
                     variant_stock, option.get('is_active', True))
                )
                if variant_stock > 0:
                    record_stock_movement(db, product_id, 'initial_stock_variant', quantity_change=variant_stock, variant_id=cursor.lastrowid, reason="Initial stock for new variant")
        elif product_type == 'simple' and aggregate_stock_quantity > 0:
             record_stock_movement(db, product_id, 'initial_stock', quantity_change=aggregate_stock_quantity, reason="Initial stock for new simple product")


        db.commit()
        audit_logger.log_action(user_id=current_user_id, action='create_product', target_type='product', target_id=product_id, details=f"Product '{name}' created.", status='success', ip_address=request.remote_addr)
        
        created_product_data = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        # Here, you might also call asset_service to generate QR/Passport/Label and include their paths in the response
        # For example:
        # asset_paths = asset_service.generate_all_assets_for_product(product_id, ...)
        # created_product_data['assets'] = asset_paths 
        return jsonify(message="Product created successfully", product=dict(created_product_data) if created_product_data else {}, product_id=product_id), 201

    except (sqlite3.IntegrityError, ValueError) as e: # Catch specific errors
        db.rollback()
        current_app.logger.error(f"Product creation error: {e}")
        audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to create product: {str(e)}"), 400 if isinstance(e, ValueError) else 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Unexpected error creating product: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to create product due to an unexpected server error."), 500

@admin_api_bp.route('/products', methods=['GET'])
@admin_required
def get_products():
    db = get_db_connection()
    include_variants_param = request.args.get('include_variants', 'false').lower() == 'true'
    try:
        products_data = query_db(
            """SELECT p.*, c.name as category_name 
               FROM products p LEFT JOIN categories c ON p.category_id = c.id 
               ORDER BY p.name""", db_conn=db
        )
        products = [dict(row) for row in products_data] if products_data else []
        for product in products:
            product['created_at'] = format_datetime_for_display(product['created_at'])
            product['updated_at'] = format_datetime_for_display(product['updated_at'])
            if product.get('main_image_url'):
                product['main_image_full_url'] = url_for('admin_api.serve_asset', asset_relative_path=product['main_image_url'], _external=True)
            
            if product['type'] == 'variable_weight' or include_variants_param:
                options_data = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product['id']], db_conn=db)
                product['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
                product['variant_count'] = len(product['weight_options'])
                if product['weight_options']: # Sum variant stocks for display if product itself has 0
                    product['aggregate_stock_quantity'] = sum(opt.get('aggregate_stock_quantity', 0) for opt in product['weight_options'])
            
            images_data = query_db("SELECT id, image_url, alt_text, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC", [product['id']], db_conn=db)
            product['additional_images'] = [dict(img_row) for img_row in images_data] if images_data else []
            for img_dict in product['additional_images']:
                 img_dict['image_full_url'] = url_for('admin_api.serve_asset', asset_relative_path=img_dict['image_url'], _external=True)
        return jsonify(products), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching products: {e}", exc_info=True)
        return jsonify(message="Failed to fetch products"), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['GET'])
@admin_required
def get_product_detail(product_id): # Renamed for clarity
    db = get_db_connection()
    try:
        product_data = query_db("SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.id = ?", [product_id], db_conn=db, one=True)
        if not product_data:
            return jsonify(message="Product not found"), 404
            
        product = dict(product_data)
        product['created_at'] = format_datetime_for_display(product['created_at'])
        product['updated_at'] = format_datetime_for_display(product['updated_at'])
        if product.get('main_image_url'):
            product['main_image_full_url'] = url_for('admin_api.serve_asset', asset_relative_path=product['main_image_url'], _external=True)

        if product['type'] == 'variable_weight':
            options_data = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product_id], db_conn=db)
            product['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
        
        images_data = query_db("SELECT id, image_url, alt_text, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC", [product_id], db_conn=db)
        product['additional_images'] = [dict(img_row) for img_row in images_data] if images_data else []
        for img_dict in product['additional_images']:
            img_dict['image_full_url'] = url_for('admin_api.serve_asset', asset_relative_path=img_dict['image_url'], _external=True)
        
        assets_data = query_db("SELECT asset_type, file_path FROM generated_assets WHERE related_product_id = ?", [product_id], db_conn=db)
        product_assets = {}
        if assets_data:
            for asset_row in assets_data:
                asset_type = asset_row['asset_type']
                file_path = asset_row['file_path']
                asset_url_key = f"{asset_type}_url" # e.g. qr_code_url
                asset_path_key = f"{asset_type}_file_path" # e.g. qr_code_file_path

                if asset_type == 'passport_html':
                     asset_full_url = url_for('serve_passport_public', filename=os.path.basename(file_path), _external=True) if 'serve_passport_public' in current_app.view_functions else url_for('admin_api.serve_asset', asset_relative_path=file_path, _external=True)
                else:
                    asset_full_url = url_for('admin_api.serve_asset', asset_relative_path=file_path, _external=True)
                
                product_assets[asset_url_key] = asset_full_url
                product_assets[asset_path_key] = file_path # Store relative path for JS if needed
        product['assets'] = product_assets
            
        return jsonify(product), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching product {product_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch product details"), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['PUT'])
@admin_required
def update_product(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()

    try:
        current_product_row = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not current_product_row:
            return jsonify(message="Product not found"), 404
        current_product = dict(current_product_row)

        data = request.form.to_dict()
        main_image_file = request.files.get('image_url_main')
        remove_main_image = data.get('remove_main_image') == 'true'

        name = data.get('name', current_product['name'])
        new_slug = generate_slug(name) if name != current_product['name'] else current_product['slug']
        
        new_sku_prefix = data.get('id', current_product['sku_prefix']) # Form 'id' is sku_prefix
        if new_sku_prefix != current_product['sku_prefix']:
            if query_db("SELECT id FROM products WHERE sku_prefix = ? AND id != ?", [new_sku_prefix, product_id], db_conn=db, one=True):
                return jsonify(message=f"SKU prefix '{new_sku_prefix}' already exists."), 409
        
        if new_slug != current_product['slug']:
            if query_db("SELECT id FROM products WHERE slug = ? AND id != ?", [new_slug, product_id], db_conn=db, one=True):
                return jsonify(message=f"Product name (slug: '{new_slug}') already exists."), 409
        
        upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
        os.makedirs(upload_folder_products, exist_ok=True)
        main_image_filename_db = current_product['main_image_url']

        if remove_main_image and current_product['main_image_url']:
            full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_product['main_image_url'])
            if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            main_image_filename_db = None
        elif main_image_file and allowed_file(main_image_file.filename, current_app.config['ALLOWED_EXTENSIONS']):
            if current_product['main_image_url']:
                full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_product['main_image_url'])
                if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            filename = secure_filename(f"product_{new_slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(main_image_file.filename)}")
            main_image_file.save(os.path.join(upload_folder_products, filename))
            main_image_filename_db = os.path.join('products', filename)

        category_name_from_form = data.get('category')
        category_id_to_update = current_product['category_id']
        if category_name_from_form:
            cat_row = query_db("SELECT id FROM categories WHERE name = ?", [category_name_from_form], db_conn=db, one=True)
            category_id_to_update = cat_row['id'] if cat_row else current_product['category_id']


        update_payload_product = {
            'name': name, 'slug': new_slug, 'sku_prefix': new_sku_prefix,
            'description': data.get('long_description', data.get('short_description', current_product['description'])),
            'category_id': category_id_to_update,
            'brand': data.get('brand', current_product['brand']),
            'type': data.get('type', current_product['type']),
            'base_price': float(data['base_price']) if data.get('base_price') is not None and data.get('base_price') != '' else current_product['base_price'],
            'currency': data.get('currency', current_product['currency']),
            'main_image_url': main_image_filename_db,
            'aggregate_stock_quantity': int(data.get('initial_stock_quantity', data.get('aggregate_stock_quantity', current_product['aggregate_stock_quantity']))),
            'aggregate_stock_weight_grams': float(data['aggregate_stock_weight_grams']) if data.get('aggregate_stock_weight_grams') is not None and data.get('aggregate_stock_weight_grams') != '' else current_product['aggregate_stock_weight_grams'],
            'unit_of_measure': data.get('unit_of_measure', current_product['unit_of_measure']),
            'is_active': data.get('is_published', str(current_product['is_active'])).lower() == 'true',
            'is_featured': data.get('is_featured', str(current_product['is_featured'])).lower() == 'true',
            'meta_title': data.get('meta_title', current_product['meta_title'] or name),
            'meta_description': data.get('meta_description', current_product['meta_description'] or data.get('short_description')),
        }
        
        if update_payload_product['type'] == 'simple' and update_payload_product['base_price'] is None:
            return jsonify(message="Base price is required for simple products."), 400
        
        weight_options_json_str = data.get('weight_options', '[]')
        weight_options = json.loads(weight_options_json_str) if weight_options_json_str else []

        if update_payload_product['type'] == 'variable_weight':
            if not update_payload_product['unit_of_measure'] and not weight_options:
                 return jsonify(message="Unit of measure and weight options are required for variable weight products."), 400
            if weight_options:
                update_payload_product['base_price'] = None
                update_payload_product['aggregate_stock_quantity'] = 0 

        set_clause_product = ", ".join([f"{key} = ?" for key in update_payload_product.keys()])
        sql_args_product = list(update_payload_product.values())
        sql_args_product.append(product_id)

        cursor = db.cursor()
        cursor.execute(f"UPDATE products SET {set_clause_product}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", sql_args_product)

        if update_payload_product['type'] == 'variable_weight':
            existing_options_rows = query_db("SELECT option_id FROM product_weight_options WHERE product_id = ?", [product_id], db_conn=db)
            existing_option_ids = {row['option_id'] for row in existing_options_rows} if existing_options_rows else set()
            submitted_option_ids = set()

            for option_data in weight_options:
                if not all(k in option_data for k in ('weight_grams', 'price', 'sku_suffix', 'initial_stock')):
                    raise ValueError("Missing fields in weight option.")
                option_id_form = option_data.get('option_id')
                variant_stock = int(option_data.get('initial_stock', 0))

                if option_id_form and int(option_id_form) in existing_option_ids:
                    cursor.execute(
                        """UPDATE product_weight_options SET weight_grams = ?, price = ?, sku_suffix = ?, 
                           aggregate_stock_quantity = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                           WHERE option_id = ? AND product_id = ?""",
                        (float(option_data['weight_grams']), float(option_data['price']), option_data['sku_suffix'],
                         variant_stock, option_data.get('is_active', True), int(option_id_form), product_id)
                    )
                    submitted_option_ids.add(int(option_id_form))
                else:
                    cursor.execute(
                        """INSERT INTO product_weight_options 
                           (product_id, weight_grams, price, sku_suffix, aggregate_stock_quantity, is_active)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (product_id, float(option_data['weight_grams']), float(option_data['price']), option_data['sku_suffix'],
                         variant_stock, option_data.get('is_active', True))
                    )
            options_to_delete = existing_option_ids - submitted_option_ids
            for opt_id_del in options_to_delete:
                cursor.execute("DELETE FROM product_weight_options WHERE option_id = ?", (opt_id_del,))
        elif update_payload_product['type'] == 'simple':
            cursor.execute("DELETE FROM product_weight_options WHERE product_id = ?", (product_id,))

        db.commit()
        audit_logger.log_action(user_id=current_user_id, action='update_product', target_type='product', target_id=product_id, details=f"Product '{name}' updated.", status='success', ip_address=request.remote_addr)
        
        updated_product_full_data = get_product_detail(product_id).get_json() # Use the detail getter
        return jsonify(message="Product updated successfully", product=updated_product_full_data), 200

    except (sqlite3.IntegrityError, ValueError) as e:
        db.rollback()
        current_app.logger.error(f"Product update error for ID {product_id}: {e}")
        audit_logger.log_action(user_id=current_user_id, action='update_product_fail', target_type='product', target_id=product_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update product: {str(e)}"), 400 if isinstance(e, ValueError) else 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Unexpected error updating product {product_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='update_product_fail', target_type='product', target_id=product_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update product due to an unexpected server error."), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['DELETE'])
@admin_required
def delete_product(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    try:
        product_to_delete = query_db("SELECT name, main_image_url, sku_prefix FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not product_to_delete:
            return jsonify(message="Product not found"), 404

        # Check for active serialized items (simplified check, schema has RESTRICT)
        # active_serialized_items = query_db("SELECT COUNT(*) FROM serialized_inventory_items WHERE product_id = ? AND status NOT IN ('sold', 'damaged')", [product_id], db_conn=db, one=True)[0]
        # if active_serialized_items > 0:
        #     return jsonify(message=f"Product '{product_to_delete['name']}' has active serialized items."), 409

        if product_to_delete['main_image_url']:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], product_to_delete['main_image_url'])
            if os.path.exists(full_image_path): os.remove(full_image_path)
        
        additional_images = query_db("SELECT image_url FROM product_images WHERE product_id = ?", [product_id], db_conn=db)
        if additional_images:
            for img in additional_images:
                full_add_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], img['image_url'])
                if os.path.exists(full_add_image_path): os.remove(full_add_image_path)
        
        cursor = db.cursor()
        # CASCADE deletes from product_images, product_weight_options, stock_movements, reviews
        # RESTRICT on order_items.product_id, serialized_inventory_items.product_id
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        db.commit()

        if cursor.rowcount > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_product', target_type='product', target_id=product_id, details=f"Product '{product_to_delete['name']}' deleted.", status='success', ip_address=request.remote_addr)
            return jsonify(message=f"Product '{product_to_delete['name']}' deleted successfully"), 200
        else:
            return jsonify(message="Product not found during delete operation"), 404
    except sqlite3.IntegrityError as e:
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='delete_product_fail', target_type='product', target_id=product_id, details=f"DB integrity error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete product due to DB integrity constraints (e.g., in orders)."), 409
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='delete_product_fail', target_type='product', target_id=product_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete product"), 500

# --- Product Image Management ---
@admin_api_bp.route('/products/<int:product_id>/images', methods=['POST'])
@admin_required
def add_product_image(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()

    if 'image' not in request.files:
        return jsonify(message="No image file provided"), 400
    
    image_file = request.files['image']
    alt_text = request.form.get('alt_text', '')
    is_primary = request.form.get('is_primary', 'false').lower() == 'true'

    product = query_db("SELECT slug FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
    if not product: return jsonify(message="Product not found"), 404

    if not allowed_file(image_file.filename, current_app.config['ALLOWED_EXTENSIONS']):
        return jsonify(message="Invalid image file type"), 400

    try:
        filename = secure_filename(f"product_{product['slug']}_img_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
        image_folder_segment = os.path.join('products', 'additional') # Subfolder for additional images
        upload_folder_full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_folder_segment)
        os.makedirs(upload_folder_full_path, exist_ok=True)
        
        image_path_on_disk = os.path.join(upload_folder_full_path, filename)
        image_file.save(image_path_on_disk)
        image_url_to_store_db = os.path.join(image_folder_segment, filename)

        cursor = db.cursor()
        if is_primary:
            cursor.execute("UPDATE product_images SET is_primary = FALSE WHERE product_id = ?", (product_id,))
        
        cursor.execute(
            "INSERT INTO product_images (product_id, image_url, alt_text, is_primary) VALUES (?, ?, ?, ?)",
            (product_id, image_url_to_store_db, alt_text, is_primary)
        )
        image_id = cursor.lastrowid
        db.commit()

        audit_logger.log_action(user_id=current_user_id, action='add_product_image', target_type='product_image', target_id=image_id, details=f"Added image to product ID {product_id}.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Image added successfully", image_id=image_id, image_url=image_url_to_store_db), 201
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='add_product_image_fail', target_type='product', target_id=product_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to add image"), 500

@admin_api_bp.route('/products/<int:product_id>/images/<int:image_id>', methods=['DELETE'])
@admin_required
def delete_product_image(product_id, image_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()

    try:
        image_data = query_db("SELECT image_url FROM product_images WHERE id = ? AND product_id = ?", [image_id, product_id], db_conn=db, one=True)
        if not image_data:
            return jsonify(message="Image not found or does not belong to this product"), 404
        
        full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_data['image_url'])
        if os.path.exists(full_image_path):
            try: os.remove(full_image_path)
            except OSError as e_rem: current_app.logger.error(f"Error deleting product image file {full_image_path}: {e_rem}")

        cursor = db.cursor()
        cursor.execute("DELETE FROM product_images WHERE id = ?", (image_id,))
        db.commit()

        audit_logger.log_action(user_id=current_user_id, action='delete_product_image', target_type='product_image', target_id=image_id, details=f"Deleted image ID {image_id} from product ID {product_id}.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Image deleted successfully"), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='delete_product_image_fail', target_type='product_image', target_id=image_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete image"), 500

# --- User Management ---
@admin_api_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    db = get_db_connection()
    try:
        users_data = query_db("SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, professional_status, created_at FROM users ORDER BY created_at DESC", db_conn=db)
        users = [dict(row) for row in users_data] if users_data else []
        for user in users:
            user['created_at'] = format_datetime_for_display(user['created_at'])
        return jsonify(users), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching users: {e}", exc_info=True)
        return jsonify(message="Failed to fetch users"), 500

@admin_api_bp.route('/users/<int:user_id>', methods=['GET']) # Added to fetch single user details
@admin_required
def get_user_admin_detail(user_id): # Renamed to avoid conflict with potential public user route
    db = get_db_connection()
    try:
        user_data = query_db("SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, vat_number, siret_number, professional_status, created_at, updated_at FROM users WHERE id = ?", [user_id], db_conn=db, one=True)
        if not user_data:
            return jsonify(message="User not found"), 404
        
        user = dict(user_data)
        user['created_at'] = format_datetime_for_display(user['created_at'])
        user['updated_at'] = format_datetime_for_display(user['updated_at'])
        
        orders_data = query_db("SELECT id as order_id, order_date, total_amount, status FROM orders WHERE user_id = ? ORDER BY order_date DESC", [user_id], db_conn=db)
        user['orders'] = [dict(row) for row in orders_data] if orders_data else []
        for order_item in user['orders']: # Ensure order_date is formatted
            order_item['order_date'] = format_datetime_for_display(order_item['order_date'])
            
        return jsonify(user), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching details for user {user_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch user details"), 500


@admin_api_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    data = request.json

    if not data:
        return jsonify(message="No data provided"), 400

    allowed_fields = ['first_name', 'last_name', 'role', 'is_active', 'is_verified', 
                      'company_name', 'vat_number', 'siret_number', 'professional_status']
    update_payload = {k: data[k] for k in data if k in allowed_fields}

    if not update_payload: return jsonify(message="No valid fields to update"), 400
    
    if 'is_active' in update_payload: update_payload['is_active'] = bool(update_payload['is_active'])
    if 'is_verified' in update_payload: update_payload['is_verified'] = bool(update_payload['is_verified'])

    set_clause = ", ".join([f"{key} = ?" for key in update_payload.keys()])
    sql_args = list(update_payload.values())
    sql_args.append(user_id)

    try:
        user_info_before = query_db("SELECT email, role, professional_status FROM users WHERE id = ?", [user_id], db_conn=db, one=True)
        if not user_info_before: return jsonify(message="User not found"), 404

        cursor = db.cursor()
        cursor.execute(f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", sql_args)
        if cursor.rowcount == 0: return jsonify(message="User not found or no changes made"), 404
        db.commit()
        
        # B2B status change notification logic can be added here if needed
        audit_logger.log_action(user_id=current_admin_id, action='update_user', target_type='user', target_id=user_id, details=f"User {user_id} updated. Fields: {', '.join(update_payload.keys())}", status='success', ip_address=request.remote_addr)
        return jsonify(message="User updated successfully"), 200
    except sqlite3.Error as e: # More specific DB error
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_user_fail', target_type='user', target_id=user_id, details=f"DB error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update user due to DB error"), 500
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_user_fail', target_type='user', target_id=user_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update user"), 500

# --- Order Management ---
@admin_api_bp.route('/orders', methods=['GET'])
@admin_required
def get_orders():
    db = get_db_connection()
    try:
        orders_data = query_db(
            """SELECT o.id as order_id, o.user_id, o.order_date, o.status, o.total_amount, o.currency,
                      u.email as customer_email, (u.first_name || ' ' || u.last_name) as customer_name
               FROM orders o
               LEFT JOIN users u ON o.user_id = u.id
               ORDER BY o.order_date DESC""", db_conn=db) # user_id can be NULL for guest orders if schema allows
        orders = [dict(row) for row in orders_data] if orders_data else []
        for order in orders:
            order['order_date'] = format_datetime_for_display(order['order_date'])
        return jsonify(orders), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching orders: {e}", exc_info=True)
        return jsonify(message="Failed to fetch orders"), 500

@admin_api_bp.route('/orders/<int:order_id>', methods=['GET']) # Added to fetch single order details
@admin_required
def get_order_admin_detail(order_id): # Renamed to avoid conflict
    db = get_db_connection()
    try:
        order_data = query_db(
            """SELECT o.*, u.email as customer_email, 
                      (u.first_name || ' ' || u.last_name) as customer_name 
               FROM orders o 
               LEFT JOIN users u ON o.user_id = u.id 
               WHERE o.id = ?""", [order_id], db_conn=db, one=True)
        
        if not order_data: return jsonify(message="Order not found"), 404
            
        order = dict(order_data)
        order['order_date'] = format_datetime_for_display(order['order_date'])
        order['created_at'] = format_datetime_for_display(order['created_at'])
        order['updated_at'] = format_datetime_for_display(order['updated_at'])
        
        items_data = query_db(
            """SELECT oi.id as item_id, oi.product_id, oi.product_name, oi.quantity, 
                      oi.price_at_purchase, oi.total_price, oi.variant, oi.variant_option_id,
                      p.sku_prefix, si.item_uid as serialized_item_uid_actual
               FROM order_items oi
               LEFT JOIN products p ON oi.product_id = p.id
               LEFT JOIN product_weight_options pwo ON oi.variant_option_id = pwo.option_id
               LEFT JOIN serialized_inventory_items si ON oi.serialized_item_id = si.id
               WHERE oi.order_id = ?""", [order_id], db_conn=db)
        order['items'] = [dict(row) for row in items_data] if items_data else []
        
        # Fetch order notes if schema supports (e.g., from orders.notes_internal or a separate table)
        # For now, assuming notes_internal is part of orders table as per schema.sql
        # If notes are in a separate table:
        # order_notes_data = query_db("SELECT content, admin_user_id, created_at FROM order_notes WHERE order_id = ? ORDER BY created_at ASC", [order_id], db_conn=db)
        # order['notes_history'] = [dict(note) for note in order_notes_data] if order_notes_data else []

        return jsonify(order), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching details for order {order_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch order details"), 500


@admin_api_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@admin_required
def update_order_status(order_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    data = request.json
    new_status = data.get('status')
    tracking_number = data.get('tracking_number') # Optional
    carrier = data.get('carrier') # Optional

    if not new_status:
        return jsonify(message="New status not provided"), 400
    
    # Add validation for allowed status values from schema
    allowed_statuses = ['pending_payment', 'paid', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded']
    if new_status not in allowed_statuses:
        return jsonify(message=f"Invalid status value. Allowed: {', '.join(allowed_statuses)}"), 400

    try:
        order_info = query_db("SELECT status, user_id FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)
        if not order_info: return jsonify(message="Order not found"), 404

        cursor = db.cursor()
        # Update status and optionally tracking info
        update_sql = "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP"
        params = [new_status]
        if new_status in ['shipped', 'delivered'] and tracking_number:
            update_sql += ", tracking_number = ?"
            params.append(tracking_number)
        if new_status in ['shipped', 'delivered'] and carrier: # Assuming carrier is stored if status is shipped/delivered
            # Add carrier to schema if not present or handle differently
            # For now, let's assume schema has a 'shipping_method' or similar that can store carrier
            # update_sql += ", shipping_method = ?" 
            # params.append(carrier)
            pass # Modify if carrier needs to be stored

        update_sql += " WHERE id = ?"
        params.append(order_id)
        
        cursor.execute(update_sql, tuple(params))
        db.commit()

        audit_logger.log_action(user_id=current_admin_id, action='update_order_status', target_type='order', target_id=order_id, details=f"Order {order_id} status changed from '{order_info['status']}' to '{new_status}'. Tracking: {tracking_number or 'N/A'}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Order status updated to {new_status}"), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_order_status_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update order status"), 500

@admin_api_bp.route('/orders/<int:order_id>/notes', methods=['POST'])
@admin_required
def add_order_note(order_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    data = request.json
    note_content = data.get('note')

    if not note_content or not note_content.strip():
        return jsonify(message="Note content cannot be empty."), 400

    try:
        order_exists = query_db("SELECT id FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)
        if not order_exists: return jsonify(message="Order not found"), 404

        # Assuming 'notes_internal' is a TEXT field in 'orders' table that can append notes
        # A better approach would be a separate order_notes table.
        # For now, appending to existing notes if any.
        current_notes_row = query_db("SELECT notes_internal FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)
        existing_notes = current_notes_row['notes_internal'] if current_notes_row and current_notes_row['notes_internal'] else ""
        
        timestamp = format_datetime_for_display(None) # Gets current time formatted
        admin_user_info = query_db("SELECT email FROM users WHERE id = ?", [current_admin_id], db_conn=db, one=True)
        admin_identifier = admin_user_info['email'] if admin_user_info else f"AdminID:{current_admin_id}"

        new_note_entry = f"[{timestamp} by {admin_identifier}]: {note_content}"
        updated_notes = f"{existing_notes}\n{new_note_entry}".strip()

        cursor = db.cursor()
        cursor.execute("UPDATE orders SET notes_internal = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (updated_notes, order_id))
        db.commit()
        
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note', target_type='order', target_id=order_id, details=f"Added note to order {order_id}: '{note_content[:50]}...'", status='success', ip_address=request.remote_addr)
        return jsonify(message="Note added successfully.", new_note_entry=new_note_entry), 201
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to add note to order"), 500


# --- Review Management ---
# (Assuming routes are similar to previous version, using centralized admin_required and audit logging)
@admin_api_bp.route('/reviews', methods=['GET'])
@admin_required
def get_reviews():
    db = get_db_connection()
    status_filter = request.args.get('status')
    query_sql = """
        SELECT r.id, r.product_id, p.name as product_name, r.user_id, u.email as user_email, 
               r.rating, r.comment, r.review_date, r.is_approved
        FROM reviews r
        JOIN products p ON r.product_id = p.id
        JOIN users u ON r.user_id = u.id
    """
    params = []
    if status_filter == 'pending': query_sql += " WHERE r.is_approved = FALSE"
    elif status_filter == 'approved': query_sql += " WHERE r.is_approved = TRUE"
    query_sql += " ORDER BY r.review_date DESC"
    try:
        reviews_data = query_db(query_sql, params, db_conn=db)
        reviews = [dict(row) for row in reviews_data] if reviews_data else []
        for review in reviews:
            review['review_date'] = format_datetime_for_display(review['review_date'])
        return jsonify(reviews), 200
    except Exception as e: return jsonify(message=f"Failed to fetch reviews: {e}"), 500

@admin_api_bp.route('/reviews/<int:review_id>/approve', methods=['PUT'])
@admin_required
def approve_review(review_id):
    return _update_review_approval(review_id, True)

@admin_api_bp.route('/reviews/<int:review_id>/unapprove', methods=['PUT'])
@admin_required
def unapprove_review(review_id):
    return _update_review_approval(review_id, False)

def _update_review_approval(review_id, is_approved_status):
    # ... (implementation similar to previous, using audit_logger)
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    action_verb = "approve" if is_approved_status else "unapprove"
    try:
        if not query_db("SELECT id FROM reviews WHERE id = ?", [review_id], db_conn=db, one=True):
            return jsonify(message="Review not found"), 404
        query_db("UPDATE reviews SET is_approved = ? WHERE id = ?", (is_approved_status, review_id), db_conn=db, commit=True)
        audit_logger.log_action(user_id=current_admin_id, action=f'{action_verb}_review', target_type='review', target_id=review_id, details=f"Review {review_id} set to {is_approved_status}.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Review {'approved' if is_approved_status else 'unapproved'} successfully"), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action=f'{action_verb}_review_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to {action_verb} review: {e}"), 500

@admin_api_bp.route('/reviews/<int:review_id>', methods=['DELETE'])
@admin_required
def delete_review(review_id):
    # ... (implementation similar to previous, using audit_logger)
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    try:
        if not query_db("SELECT id FROM reviews WHERE id = ?", [review_id], db_conn=db, one=True):
            return jsonify(message="Review not found"), 404
        query_db("DELETE FROM reviews WHERE id = ?", (review_id,), db_conn=db, commit=True)
        audit_logger.log_action(user_id=current_admin_id, action='delete_review', target_type='review', target_id=review_id, details=f"Review {review_id} deleted.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Review deleted successfully"), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to delete review: {e}"), 500

# --- Asset Serving ---
@admin_api_bp.route('/assets/<path:asset_relative_path>')
@admin_required
def serve_asset(asset_relative_path):
    path_parts = asset_relative_path.split(os.sep, 1)
    top_level_folder = path_parts[0]
    
    upload_dirs = ['categories', 'products', 'professional_documents']
    generated_asset_dirs = ['qr_codes', 'passports', 'labels', 'invoices']
    base_directory_to_serve_from = None

    if top_level_folder in upload_dirs:
        base_directory_to_serve_from = current_app.config['UPLOAD_FOLDER']
    elif top_level_folder in generated_asset_dirs:
        base_directory_to_serve_from = current_app.config['ASSET_STORAGE_PATH']
    else:
        return jsonify(message="Forbidden: Invalid asset category"), 403
    
    full_file_path = os.path.abspath(os.path.join(base_directory_to_serve_from, asset_relative_path))
    
    if not full_file_path.startswith(os.path.abspath(base_directory_to_serve_from) + os.sep):
        return jsonify(message="Forbidden: Invalid path"), 403
    if not os.path.isfile(full_file_path):
        return jsonify(message="Asset not found"), 404
        
    return send_from_directory(base_directory_to_serve_from, asset_relative_path)

# --- Settings Management ---
@admin_api_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings():
    db = get_db_connection()
    try:
        settings_data = query_db("SELECT key, value, description FROM settings", db_conn=db)
        settings = {row['key']: {'value': row['value'], 'description': row['description']} for row in settings_data} if settings_data else {}
        return jsonify(settings), 200
    except Exception as e: return jsonify(message=f"Failed to fetch settings: {e}"), 500

@admin_api_bp.route('/settings', methods=['POST'])
@admin_required
def update_settings():
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    data = request.json
    if not data: return jsonify(message="No settings data provided"), 400
    
    updated_keys = []
    try:
        cursor = db.cursor()
        for key, value_obj in data.items():
            value_to_store = value_obj.get('value') if isinstance(value_obj, dict) else value_obj
            if value_to_store is not None:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (key, str(value_to_store)))
                updated_keys.append(key)
        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_settings', target_type='application_settings', details=f"Settings updated: {', '.join(updated_keys)}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Settings updated successfully", updated_settings=updated_keys), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update settings: {e}"), 500
