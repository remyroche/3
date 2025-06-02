# contraste/admin_api/routes.py

import os
import json
import uuid
import sqlite3
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, current_app, g, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity # send_from_directory is already imported if needed by serve_asset

from ..utils import (
    admin_required,
    format_datetime_for_display,
    parse_datetime_from_iso,
    generate_slug,
    allowed_file,
    get_file_extension,
    format_datetime_for_storage,
    generate_static_json_files # <-- IMPORT THE NEW FUNCTION
)
from ..database import get_db_connection, query_db, record_stock_movement
from . import admin_api_bp

# --- Dashboard ---
@admin_api_bp.route('/dashboard/stats', methods=['GET'])
@admin_required
def get_dashboard_stats():
    db = get_db_connection()
    try:
        total_users = query_db("SELECT COUNT(*) FROM users", db_conn=db, one=True)[0]
        total_products = query_db("SELECT COUNT(*) FROM products WHERE is_active = TRUE", db_conn=db, one=True)[0]
        total_orders = query_db("SELECT COUNT(*) FROM orders WHERE status NOT IN ('cancelled', 'pending_payment')", db_conn=db, one=True)[0]
        pending_b2b_applications = query_db("SELECT COUNT(*) FROM users WHERE role = 'b2b_professional' AND professional_status = 'pending'", db_conn=db, one=True)[0]
        
        return jsonify({
            "total_users": total_users,
            "total_products": total_products,
            "total_orders": total_orders,
            "pending_b2b_applications": pending_b2b_applications
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
    category_code = data.get('category_code', '').strip()
    image_file = request.files.get('image_url') 
    
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not name or not category_code:
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details="Name is required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Name is required"), 400

    slug = generate_slug(name)
    db = get_db_connection()
    cursor = db.cursor() # Get cursor for transaction
    image_filename_db = None 

    try:
        # Check for existing name or slug
        if query_db("SELECT id FROM categories WHERE name = ?", [name], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details=f"Category name '{name}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category name '{name}' already exists"), 409
        if query_db("SELECT id FROM categories WHERE slug = ?", [slug], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details=f"Category slug '{slug}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category slug '{slug}' already exists. Try a different name."), 409
        if category_code and query_db("SELECT id FROM categories WHERE category_code = ?", [category_code], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details=f"Category code '{category_code}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category code '{category_code}' already exists."), 409

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(f"category_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
            upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
            os.makedirs(upload_folder_categories, exist_ok=True)
            image_path_full = os.path.join(upload_folder_categories, filename)
            image_file.save(image_path_full)
            image_filename_db = os.path.join('categories', filename) 

        parent_id = int(parent_id_str) if parent_id_str and parent_id_str.strip() else None

        cursor.execute(
            "INSERT INTO categories (name, description, parent_id, slug, image_url, category_code) VALUES (?, ?, ?, ?, ?, ?)",
            (name, description, parent_id, slug, image_filename_db, category_code)
        )
        category_id = cursor.lastrowid
        db.commit() # Commit transaction
        
        # --- CALL GENERATOR FUNCTION ---
        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after category creation: {e_gen}", exc_info=True)
        # -----------------------------

        audit_logger.log_action(user_id=current_user_id, action='create_category', target_type='category', target_id=category_id, details=f"Category '{name}' created.", status='success', ip_address=request.remote_addr)
        created_category = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        return jsonify(message="Category created successfully", category=dict(created_category) if created_category else {}, success=True), 201
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
        categories_data = query_db("SELECT id, name, description, parent_id, slug, image_url, category_code, created_at, updated_at FROM categories ORDER BY name", db_conn=db)
        categories = [dict(row) for row in categories_data] if categories_data else []
        
        for category in categories:
            category['created_at'] = format_datetime_for_display(category['created_at'])
            category['updated_at'] = format_datetime_for_display(category['updated_at'])
            if category.get('image_url'):
                 category['image_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=category['image_url'], _external=True)
        return jsonify(categories), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching categories: {e}", exc_info=True)
        return jsonify(message="Failed to fetch categories"), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['GET'])
@admin_required
def get_category_detail(category_id):
    db = get_db_connection()
    try:
        category_data = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if category_data:
            category = dict(category_data)
            category['created_at'] = format_datetime_for_display(category['created_at'])
            category['updated_at'] = format_datetime_for_display(category['updated_at'])
            if category.get('image_url'):
                 category['image_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=category['image_url'], _external=True)
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
    category_code = data.get('category_code', '').strip()
    image_file = request.files.get('image_url')
    remove_image = data.get('remove_image') == 'true'

    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    if not name:
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details="Name is required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Name is required for update"), 400

    db = get_db_connection()
    cursor = db.cursor() # Get cursor for transaction
    try:
        current_category_row = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if not current_category_row:
            audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details="Category not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Category not found"), 404
        current_category = dict(current_category_row)

        new_slug = generate_slug(name)
        new_category_code = category_code if category_code else current_category.get('category_code')
        image_filename_to_update_db = current_category['image_url']

        # Validations for name and slug conflicts
        if name != current_category['name'] and query_db("SELECT id FROM categories WHERE name = ? AND id != ?", [name, category_id], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details=f"Category name '{name}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Another category with the name '{name}' already exists"), 409
        if new_slug != current_category['slug'] and query_db("SELECT id FROM categories WHERE slug = ? AND id != ?", [new_slug, category_id], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details=f"Category slug '{new_slug}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Another category with slug '{new_slug}' already exists. Try a different name."), 409
        if new_category_code and new_category_code != current_category.get('category_code') and query_db("SELECT id FROM categories WHERE category_code = ? AND id != ?", [new_category_code, category_id], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details=f"Category code '{new_category_code}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Another category with code '{new_category_code}' already exists."), 409

        upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
        os.makedirs(upload_folder_categories, exist_ok=True)

        if remove_image and current_category['image_url']:
            full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_category['image_url'])
            if os.path.exists(full_old_image_path):
                try: os.remove(full_old_image_path)
                except OSError as e_rem: current_app.logger.error(f"Error removing old category image {full_old_image_path}: {e_rem}")
            image_filename_to_update_db = None
        elif image_file and allowed_file(image_file.filename):
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

        cursor.execute(
            """UPDATE categories SET 
               name = ?, description = ?, parent_id = ?, slug = ?, image_url = ?, category_code = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (name, description_to_update, parent_id_to_update, new_slug, image_filename_to_update_db, new_category_code, category_id)
        )
        db.commit() # Commit transaction
        
        # --- CALL GENERATOR FUNCTION ---
        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after category update: {e_gen}", exc_info=True)
        # -----------------------------
        
        audit_logger.log_action(user_id=current_user_id, action='update_category', target_type='category', target_id=category_id, details=f"Category '{name}' updated.", status='success', ip_address=request.remote_addr)
        updated_category = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        return jsonify(message="Category updated successfully", category=dict(updated_category) if updated_category else {}, success=True), 200
    except sqlite3.IntegrityError as e:
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail', target_type='category', target_id=category_id, details=f"DB integrity error: {e}", status='failure', ip_address=request.remote_addr)
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
    cursor = db.cursor() # Get cursor for transaction

    try:
        category_to_delete_row = query_db("SELECT image_url, name FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if not category_to_delete_row:
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details="Category not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Category not found"), 404
        category_to_delete = dict(category_to_delete_row)

        products_in_category_row = query_db("SELECT COUNT(*) FROM products WHERE category_id = ?", [category_id], db_conn=db, one=True)
        products_in_category = products_in_category_row[0] if products_in_category_row else 0
        if products_in_category > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details=f"Category '{category_to_delete['name']}' in use by {products_in_category} products.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category '{category_to_delete['name']}' is in use by products. Reassign products first."), 409
        
        if category_to_delete['image_url']:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category_to_delete['image_url'])
            if os.path.exists(full_image_path):
                try: os.remove(full_image_path)
                except OSError as e_rem: current_app.logger.error(f"Error deleting category image {full_image_path}: {e_rem}")
        
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        db.commit() # Commit transaction

        # --- CALL GENERATOR FUNCTION ---
        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after category deletion: {e_gen}", exc_info=True)
        # -----------------------------

        if cursor.rowcount > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_category', target_type='category', target_id=category_id, details=f"Category '{category_to_delete['name']}' deleted.", status='success', ip_address=request.remote_addr)
            return jsonify(message=f"Category '{category_to_delete['name']}' deleted successfully"), 200
        else: 
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details="Category not found during delete op (race condition?).", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Category not found during delete operation"), 404
    except sqlite3.IntegrityError as e: 
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details=f"DB integrity error: {e}. Subcategories might exist.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete category due to DB integrity constraints (e.g., subcategories exist)."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error deleting category {category_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='delete_category_fail', target_type='category', target_id=category_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete category due to a server error."), 500

# --- Product Management ---
@admin_api_bp.route('/products', methods=['POST'])
@admin_required
def create_product():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() # Get cursor for transaction

    try:
        data = request.form.to_dict() 
        main_image_file = request.files.get('image_url_main')
        
        name = data.get('name')
        sku_prefix = data.get('id') 
        product_type = data.get('type', 'simple')
        description = data.get('long_description', data.get('short_description', ''))
        
        category_name_from_form = data.get('category')
        category_id = None
        if category_name_from_form:
            category_row = query_db("SELECT id FROM categories WHERE name = ?", [category_name_from_form], db_conn=db, one=True) # Uses g.db_conn
            if category_row: category_id = category_row['id']
            else: current_app.logger.warning(f"Category '{category_name_from_form}' not found during product creation.")

        # ... (rest of the variable assignments and initial validations for name, sku_prefix, product_type) ...
        brand = data.get('brand', "Maison Trüvra")
        base_price_str = data.get('base_price')
        currency = data.get('currency', 'EUR')
        aggregate_stock_quantity_str = data.get('initial_stock_quantity', '0')
        aggregate_stock_weight_grams_str = data.get('aggregate_stock_weight_grams')
        unit_of_measure = data.get('unit_of_measure')
        is_active = data.get('is_published', 'true').lower() == 'true'
        is_featured = data.get('is_featured', 'false').lower() == 'true'
        meta_title = data.get('meta_title', name)
        meta_description = data.get('meta_description', data.get('short_description', ''))
        slug = generate_slug(name)

        if not all([name, sku_prefix, product_type]):
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details="Name, SKU Prefix, Type required.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Name, SKU Prefix (ID from form), and Type are required."), 400
        
        if query_db("SELECT id FROM products WHERE sku_prefix = ?", [sku_prefix], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details=f"SKU prefix '{sku_prefix}' exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"SKU prefix '{sku_prefix}' already exists."), 409
        if query_db("SELECT id FROM products WHERE slug = ?", [slug], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details=f"Product slug '{slug}' exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Product name (slug: '{slug}') already exists. Choose a different name."), 409

        main_image_filename_db = None
        if main_image_file and allowed_file(main_image_file.filename):
            filename = secure_filename(f"product_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(main_image_file.filename)}")
            upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
            os.makedirs(upload_folder_products, exist_ok=True)
            main_image_file.save(os.path.join(upload_folder_products, filename))
            main_image_filename_db = os.path.join('products', filename)

        base_price = float(base_price_str) if base_price_str is not None and base_price_str != '' else None
        aggregate_stock_quantity = int(aggregate_stock_quantity_str) if aggregate_stock_quantity_str is not None else 0
        aggregate_stock_weight_grams = float(aggregate_stock_weight_grams_str) if aggregate_stock_weight_grams_str else None

        if product_type == 'simple' and base_price is None:
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details="Base price required for simple products.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Base price is required for simple products."), 400
        
        weight_options_json_str = data.get('weight_options_json', '[]')
        weight_options = json.loads(weight_options_json_str) if weight_options_json_str else []
        if not isinstance(weight_options, list): raise ValueError("Weight options must be a list.")

        if product_type == 'variable_weight' and not unit_of_measure and not weight_options:
             audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details="Unit/options required for variable weight.", status='failure', ip_address=request.remote_addr)
             return jsonify(message="Unit of measure and/or weight options are required for variable weight products."), 400

        # Main product insert
        cursor.execute(
            """INSERT INTO products (name, description, category_id, brand, sku_prefix, type, 
                                   base_price, currency, main_image_url, aggregate_stock_quantity, 
                                   aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured, 
                                   meta_title, meta_description, slug)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, description, category_id, brand, sku_prefix, product_type, 
             base_price, currency, main_image_filename_db, 
             aggregate_stock_quantity if product_type == 'simple' else 0, 
             aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured, 
             meta_title, meta_description, slug)
        )
        product_id = cursor.lastrowid

        # Product weight options and stock movements
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
                variant_db_id = cursor.lastrowid
                if variant_stock > 0:
                    # Pass db connection to record_stock_movement, it should use the existing transaction
                    record_stock_movement(db, product_id, 'initial_stock_variant', quantity_change=variant_stock, variant_id=variant_db_id, reason="Initial stock for new variant", related_user_id=current_user_id)
        elif product_type == 'simple' and aggregate_stock_quantity > 0:
             record_stock_movement(db, product_id, 'initial_stock', quantity_change=aggregate_stock_quantity, reason="Initial stock for new simple product", related_user_id=current_user_id)

        db.commit() # Commit transaction
        
        # --- CALL GENERATOR FUNCTION ---
        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after product creation: {e_gen}", exc_info=True)
        # -----------------------------

        audit_logger.log_action(user_id=current_user_id, action='create_product', target_type='product', target_id=product_id, details=f"Product '{name}' created.", status='success', ip_address=request.remote_addr)
        
        created_product_data_row = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        response_data = {"message": "Product created successfully", "product_id": product_id, "slug": slug, "success": True}
        if created_product_data_row:
            response_data["product"] = dict(created_product_data_row)
        return jsonify(response_data), 201

    except (sqlite3.IntegrityError, ValueError) as e:
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to create product: {str(e)}", success=False), 400 if isinstance(e, ValueError) else 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Unexpected error creating product: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='create_product_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to create product due to an unexpected server error.", success=False), 500

@admin_api_bp.route('/products', methods=['GET'])
# @admin_required # Temporarily removed for public access to products list
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
                product['main_image_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=product['main_image_url'], _external=True)
            
            if product['type'] == 'variable_weight' or include_variants_param:
                options_data = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product['id']], db_conn=db)
                product['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
                product['variant_count'] = len(product['weight_options'])
                if product['type'] == 'variable_weight' and product['weight_options']:
                    product['aggregate_stock_quantity'] = sum(opt.get('aggregate_stock_quantity', 0) for opt in product['weight_options'])
            
            images_data = query_db("SELECT id, image_url, alt_text, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC", [product['id']], db_conn=db)
            product['additional_images'] = []
            if images_data:
                for img_row in images_data:
                    img_dict = dict(img_row)
                    if img_dict.get('image_url'):
                        img_dict['image_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=img_dict['image_url'], _external=True)
                    product['additional_images'].append(img_dict)
        return jsonify(products), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching products: {e}", exc_info=True)
        return jsonify(message="Failed to fetch products"), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['GET'])
@admin_required
def get_product_admin_detail(product_id):
    db = get_db_connection()
    try:
        product_data = query_db("SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.id = ?", [product_id], db_conn=db, one=True)
        if not product_data:
            return jsonify(message="Product not found"), 404
            
        product = dict(product_data)
        product['created_at'] = format_datetime_for_display(product['created_at'])
        product['updated_at'] = format_datetime_for_display(product['updated_at'])
        if product.get('main_image_url'):
            product['main_image_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=product['main_image_url'], _external=True)

        if product['type'] == 'variable_weight':
            options_data = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product_id], db_conn=db)
            product['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
        
        images_data = query_db("SELECT id, image_url, alt_text, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC", [product_id], db_conn=db)
        product['additional_images'] = []
        if images_data:
            for img_row in images_data:
                img_dict = dict(img_row)
                if img_dict.get('image_url'):
                    img_dict['image_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=img_dict['image_url'], _external=True)
                product['additional_images'].append(img_dict)
        
        assets_data = query_db("SELECT asset_type, file_path FROM generated_assets WHERE related_product_id = ?", [product_id], db_conn=db)
        product_assets = {}
        if assets_data:
            for asset_row in assets_data:
                asset_type_key = asset_row['asset_type'].lower().replace(' ', '_')
                asset_full_url = None
                if asset_row.get('file_path'):
                    try:
                        if asset_row['asset_type'] == 'passport_html' and 'serve_passport_public' in current_app.view_functions:
                            asset_full_url = url_for('serve_passport_public', filename=os.path.basename(asset_row['file_path']), _external=True)
                        else:
                            asset_full_url = url_for('admin_api_bp.serve_asset', asset_relative_path=asset_row['file_path'], _external=True)
                    except Exception as e_asset_url:
                        current_app.logger.warning(f"Could not generate URL for asset {asset_row['file_path']}: {e_asset_url}")
                
                product_assets[f"{asset_type_key}_url"] = asset_full_url
                product_assets[f"{asset_type_key}_file_path"] = asset_row['file_path']
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
    cursor = db.cursor() # Get cursor for transaction

    try:
        current_product_row = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not current_product_row:
            audit_logger.log_action(user_id=current_user_id, action='update_product_fail_not_found', target_type='product', target_id=product_id, details="Product not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Product not found"), 404
        current_product = dict(current_product_row)

        data = request.form.to_dict()
        main_image_file = request.files.get('image_url_main')
        remove_main_image = data.get('remove_main_image') == 'true'

        name = data.get('name', current_product['name'])
        new_slug = generate_slug(name) if name != current_product['name'] else current_product['slug']
        
        new_sku_prefix = data.get('id', current_product['sku_prefix'])
        if new_sku_prefix != current_product['sku_prefix'] and query_db("SELECT id FROM products WHERE sku_prefix = ? AND id != ?", [new_sku_prefix, product_id], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='update_product_fail_sku_exists', target_type='product', target_id=product_id, details=f"SKU '{new_sku_prefix}' exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"SKU prefix '{new_sku_prefix}' already exists."), 409
        
        if new_slug != current_product['slug'] and query_db("SELECT id FROM products WHERE slug = ? AND id != ?", [new_slug, product_id], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='update_product_fail_slug_exists', target_type='product', target_id=product_id, details=f"Slug '{new_slug}' exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Product name (slug: '{new_slug}') already exists."), 409
        
        # ... (image handling logic - same as before, ensure it's correct) ...
        upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
        os.makedirs(upload_folder_products, exist_ok=True)
        main_image_filename_db = current_product['main_image_url']

        if remove_main_image and current_product['main_image_url']:
            full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_product['main_image_url'])
            if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            main_image_filename_db = None
        elif main_image_file and allowed_file(main_image_file.filename):
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
            audit_logger.log_action(user_id=current_user_id, action='update_product_fail_base_price_simple', target_type='product', target_id=product_id, details="Base price required for simple product.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Base price is required for simple products."), 400
        
        weight_options_json_str = data.get('weight_options_json', '[]')
        weight_options = json.loads(weight_options_json_str) if weight_options_json_str else []
        if not isinstance(weight_options, list): raise ValueError("Weight options must be a list.")

        if update_payload_product['type'] == 'variable_weight':
            if not update_payload_product['unit_of_measure'] and not weight_options:
                 audit_logger.log_action(user_id=current_user_id, action='update_product_fail_variable_config', target_type='product', target_id=product_id, details="Unit/options required for variable weight.", status='failure', ip_address=request.remote_addr)
                 return jsonify(message="Unit of measure and weight options are required for variable weight products."), 400
            if weight_options:
                update_payload_product['base_price'] = None
                update_payload_product['aggregate_stock_quantity'] = 0 

        set_clause_product = ", ".join([f"{key} = ?" for key in update_payload_product.keys()])
        sql_args_product = list(update_payload_product.values())
        sql_args_product.append(product_id)

        cursor.execute(f"UPDATE products SET {set_clause_product}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", sql_args_product)

        # Handle weight options update (within the same transaction)
        if update_payload_product['type'] == 'variable_weight':
            existing_options_rows = query_db("SELECT id as option_id FROM product_weight_options WHERE product_id = ?", [product_id], db_conn=db)
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
                           WHERE id = ? AND product_id = ?""",
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
                cursor.execute("DELETE FROM product_weight_options WHERE id = ?", (opt_id_del,))
        elif update_payload_product['type'] == 'simple': # If changed to simple, remove all variants
            cursor.execute("DELETE FROM product_weight_options WHERE product_id = ?", (product_id,))

        db.commit() # Commit transaction
        
        # --- CALL GENERATOR FUNCTION ---
        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after product update: {e_gen}", exc_info=True)
        # -----------------------------

        audit_logger.log_action(user_id=current_user_id, action='update_product', target_type='product', target_id=product_id, details=f"Product '{name}' updated.", status='success', ip_address=request.remote_addr)
        
        updated_product_response = get_product_admin_detail(product_id)
        return jsonify(message="Product updated successfully", product=updated_product_response.get_json().get('product') if updated_product_response else {}, success=True), 200

    except (sqlite3.IntegrityError, ValueError) as e:
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='update_product_fail_db_value_error', target_type='product', target_id=product_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update product: {str(e)}", success=False), 400 if isinstance(e, ValueError) else 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Unexpected error updating product {product_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='update_product_fail_exception', target_type='product', target_id=product_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update product due to an unexpected server error.", success=False), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['DELETE'])
@admin_required
def delete_product(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() # Get cursor for transaction
    try:
        product_to_delete_row = query_db("SELECT name, main_image_url, sku_prefix FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not product_to_delete_row:
            audit_logger.log_action(user_id=current_user_id, action='delete_product_fail_not_found', target_type='product', target_id=product_id, details="Product not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Product not found"), 404
        product_to_delete = dict(product_to_delete_row)

        if product_to_delete['main_image_url']:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], product_to_delete['main_image_url'])
            if os.path.exists(full_image_path): os.remove(full_image_path)
        
        additional_images = query_db("SELECT image_url FROM product_images WHERE product_id = ?", [product_id], db_conn=db)
        if additional_images:
            for img in additional_images:
                full_add_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], img['image_url'])
                if os.path.exists(full_add_image_path): os.remove(full_add_image_path)
        
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        # Related deletions (product_images, product_weight_options, etc.) should be handled by ON DELETE CASCADE in schema.
        # Check for RESTRICT constraints (e.g., if product is in an order_item).
        
        db.commit() # Commit transaction

        # --- CALL GENERATOR FUNCTION ---
        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after product deletion: {e_gen}", exc_info=True)
        # -----------------------------

        if cursor.rowcount > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_product', target_type='product', target_id=product_id, details=f"Product '{product_to_delete['name']}' deleted.", status='success', ip_address=request.remote_addr)
            return jsonify(message=f"Product '{product_to_delete['name']}' deleted successfully"), 200
        else: 
            audit_logger.log_action(user_id=current_user_id, action='delete_product_fail_not_deleted', target_type='product', target_id=product_id, details="Product not found during delete op (race condition?).", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Product not found during delete operation"), 404
    except sqlite3.IntegrityError as e:
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='delete_product_fail_integrity', target_type='product', target_id=product_id, details=f"DB integrity error (e.g., in orders): {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete product due to DB integrity constraints (e.g., product is in existing orders)."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error deleting product {product_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='delete_product_fail_exception', target_type='product', target_id=product_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete product"), 500

# --- User Management ---
@admin_api_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    db = get_db_connection()
    # ... (filtering logic remains the same) ...
    role_filter = request.args.get('role')
    status_filter = request.args.get('status') 
    search_term = request.args.get('search')

    query_sql = "SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, professional_status, created_at FROM users"
    conditions = []
    params = []

    if role_filter: conditions.append("role = ?"); params.append(role_filter)
    if status_filter:
        if status_filter == 'active': conditions.append("is_active = TRUE")
        elif status_filter == 'inactive': conditions.append("is_active = FALSE")
    if search_term:
        conditions.append("(email LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR company_name LIKE ?)")
        term = f"%{search_term}%"
        params.extend([term, term, term, term])
    
    if conditions: query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY created_at DESC"

    try:
        users_data = query_db(query_sql, params, db_conn=db)
        users = [dict(row) for row in users_data] if users_data else []
        for user in users:
            user['created_at'] = format_datetime_for_display(user['created_at'])
        return jsonify(users), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching users: {e}", exc_info=True)
        return jsonify(message="Failed to fetch users"), 500

@admin_api_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user_admin_detail(user_id):
    db = get_db_connection()
    try:
        user_data = query_db("SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, vat_number, siret_number, professional_status, created_at, updated_at FROM users WHERE id = ?", [user_id], db_conn=db, one=True)
        if not user_data: return jsonify(message="User not found"), 404
        
        user = dict(user_data)
        user['created_at'] = format_datetime_for_display(user['created_at'])
        user['updated_at'] = format_datetime_for_display(user['updated_at'])
        
        orders_data = query_db("SELECT id as order_id, order_date, total_amount, status FROM orders WHERE user_id = ? ORDER BY order_date DESC", [user_id], db_conn=db)
        user['orders'] = [dict(row) for row in orders_data] if orders_data else []
        for order_item in user['orders']: # Corrected variable name
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
    cursor = db.cursor() # Get cursor for transaction
    data = request.json

    if not data: return jsonify(message="No data provided"), 400

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
        if not query_db("SELECT id FROM users WHERE id = ?", [user_id], db_conn=db, one=True):
             return jsonify(message="User not found"), 404

        cursor.execute(f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", tuple(sql_args))
        db.commit() # Commit transaction
        
        if cursor.rowcount == 0: return jsonify(message="User not found or no changes made"), 404
        
        audit_logger.log_action(user_id=current_admin_id, action='update_user', target_type='user', target_id=user_id, details=f"User {user_id} updated. Fields: {', '.join(update_payload.keys())}", status='success', ip_address=request.remote_addr)
        return jsonify(message="User updated successfully"), 200
    except sqlite3.Error as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_user_fail_db_error', target_type='user', target_id=user_id, details=f"DB error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update user due to DB error"), 500
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_user_fail_exception', target_type='user', target_id=user_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update user"), 500

# --- Order Management ---
@admin_api_bp.route('/orders', methods=['GET'])
@admin_required
def get_orders():
    db = get_db_connection()
    search_filter = request.args.get('search')
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')

    query_sql = """
        SELECT o.id as order_id, o.user_id, o.order_date, o.status, o.total_amount, o.currency,
               u.email as customer_email, (u.first_name || ' ' || u.last_name) as customer_name
        FROM orders o LEFT JOIN users u ON o.user_id = u.id
    """
    conditions = []
    params = []

    if search_filter:
        conditions.append("(CAST(o.id AS TEXT) LIKE ? OR u.email LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ?)") # Cast o.id to TEXT for LIKE
        term = f"%{search_filter}%"
        params.extend([term, term, term, term])
    if status_filter:
        conditions.append("o.status = ?")
        params.append(status_filter)
    if date_filter: 
        conditions.append("DATE(o.order_date) = ?")
        params.append(date_filter)

    if conditions: query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY o.order_date DESC"

    try:
        orders_data = query_db(query_sql, params, db_conn=db)
        orders = [dict(row) for row in orders_data] if orders_data else []
        for order in orders:
            order['order_date'] = format_datetime_for_display(order['order_date'])
        return jsonify(orders), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching orders: {e}", exc_info=True)
        return jsonify(message="Failed to fetch orders"), 500

@admin_api_bp.route('/orders/<int:order_id>', methods=['GET'])
@admin_required
def get_order_admin_detail(order_id):
    db = get_db_connection()
    try:
        order_data_row = query_db(
            """SELECT o.*, u.email as customer_email, 
                      (u.first_name || ' ' || u.last_name) as customer_name 
               FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.id = ?""", 
            [order_id], db_conn=db, one=True
        )
        if not order_data_row: return jsonify(message="Order not found"), 404
            
        order = dict(order_data_row)
        order['order_date'] = format_datetime_for_display(order['order_date'])
        order['created_at'] = format_datetime_for_display(order['created_at'])
        order['updated_at'] = format_datetime_for_display(order['updated_at'])
        
        items_data = query_db(
            """SELECT oi.id as item_id, oi.product_id, oi.product_name, oi.quantity, 
                      oi.unit_price, oi.total_price, oi.variant_description, oi.variant_id,
                      p.main_image_url as product_image_url
               FROM order_items oi
               LEFT JOIN products p ON oi.product_id = p.id
               WHERE oi.order_id = ?""", [order_id], db_conn=db)
        order['items'] = []
        if items_data:
            for item_row in items_data:
                item_dict = dict(item_row)
                if item_dict.get('product_image_url'):
                    try:
                        item_dict['product_image_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item_dict['product_image_url'], _external=True)
                    except Exception as e_img_url:
                        current_app.logger.warning(f"Could not generate URL for order item image {item_dict['product_image_url']}: {e_img_url}")
                        item_dict['product_image_full_url'] = None
                order['items'].append(item_dict)
        
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
    cursor = db.cursor() # Get cursor for transaction
    data = request.json
    new_status = data.get('status')
    tracking_number = data.get('tracking_number')
    carrier = data.get('carrier') # Assuming schema has 'carrier' field in 'orders'

    if not new_status: return jsonify(message="New status not provided"), 400
    allowed_statuses = ['pending_payment', 'paid', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded']
    if new_status not in allowed_statuses:
        return jsonify(message=f"Invalid status. Allowed: {', '.join(allowed_statuses)}"), 400

    try:
        order_info_row = query_db("SELECT status FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)
        if not order_info_row: return jsonify(message="Order not found"), 404
        order_info = dict(order_info_row)

        update_fields = {"status": new_status}
        if new_status in ['shipped', 'delivered']:
            if tracking_number: update_fields["tracking_number"] = tracking_number
            if carrier: update_fields["shipping_method"] = carrier # Assuming schema field is shipping_method
        
        set_clause_parts = [f"{key} = ?" for key in update_fields.keys()]
        set_clause_parts.append("updated_at = CURRENT_TIMESTAMP") # Always update timestamp
        
        params = list(update_fields.values())
        params.append(order_id)
        
        cursor.execute(f"UPDATE orders SET {', '.join(set_clause_parts)} WHERE id = ?", tuple(params))
        db.commit() # Commit transaction
        
        audit_logger.log_action(user_id=current_admin_id, action='update_order_status', target_type='order', target_id=order_id, details=f"Order {order_id} status from '{order_info['status']}' to '{new_status}'. Tracking: {tracking_number or 'N/A'}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Order status updated to {new_status}", success=True), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_order_status_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update order status", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>/notes', methods=['POST'])
@admin_required
def add_order_note(order_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() # Get cursor for transaction
    data = request.json
    note_content = data.get('note')

    if not note_content or not note_content.strip():
        return jsonify(message="Note content cannot be empty."), 400

    try:
        if not query_db("SELECT id FROM orders WHERE id = ?", [order_id], db_conn=db, one=True):
            return jsonify(message="Order not found"), 404

        current_notes_row = query_db("SELECT notes_internal FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)
        existing_notes = current_notes_row['notes_internal'] if current_notes_row and current_notes_row['notes_internal'] else ""
        
        timestamp_str = format_datetime_for_display(None) 
        admin_user_info_row = query_db("SELECT email FROM users WHERE id = ?", [current_admin_id], db_conn=db, one=True)
        admin_identifier = admin_user_info_row['email'] if admin_user_info_row else f"AdminID:{current_admin_id}"
        new_note_entry = f"[{timestamp_str} by {admin_identifier}]: {note_content}"
        updated_notes = f"{existing_notes}\n{new_note_entry}".strip()

        cursor.execute("UPDATE orders SET notes_internal = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (updated_notes, order_id))
        db.commit() # Commit transaction
        
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note', target_type='order', target_id=order_id, details=f"Added note to order {order_id}: '{note_content[:50]}...'", status='success', ip_address=request.remote_addr)
        return jsonify(message="Note added successfully.", new_note_entry=new_note_entry, success=True), 201
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to add note to order", success=False), 500

# --- Review Management ---
@admin_api_bp.route('/reviews', methods=['GET'])
@admin_required
def get_reviews():
    db = get_db_connection()
    # ... (filtering logic remains the same) ...
    status_filter = request.args.get('status') 
    product_id_filter = request.args.get('product_id', type=int)
    user_id_filter = request.args.get('user_id', type=int)

    query_sql = """
        SELECT r.id, r.product_id, p.name as product_name, r.user_id, u.email as user_email, 
               r.rating, r.comment, r.review_date, r.is_approved
        FROM reviews r JOIN products p ON r.product_id = p.id JOIN users u ON r.user_id = u.id
    """
    conditions = []
    params = []
    if status_filter == 'pending': conditions.append("r.is_approved = FALSE")
    elif status_filter == 'approved': conditions.append("r.is_approved = TRUE")
    if product_id_filter: conditions.append("r.product_id = ?"); params.append(product_id_filter)
    if user_id_filter: conditions.append("r.user_id = ?"); params.append(user_id_filter)
    
    if conditions: query_sql += " WHERE " + " AND ".join(conditions)
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
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() # Get cursor for transaction
    action_verb = "approve" if is_approved_status else "unapprove"
    try:
        if not query_db("SELECT id FROM reviews WHERE id = ?", [review_id], db_conn=db, one=True):
            return jsonify(message="Review not found"), 404
        cursor.execute("UPDATE reviews SET is_approved = ? WHERE id = ?", (is_approved_status, review_id))
        db.commit() # Commit transaction
        audit_logger.log_action(user_id=current_admin_id, action=f'{action_verb}_review', target_type='review', target_id=review_id, details=f"Review {review_id} set to {is_approved_status}.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Review {'approved' if is_approved_status else 'unapproved'} successfully"), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action=f'{action_verb}_review_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to {action_verb} review: {e}"), 500

@admin_api_bp.route('/reviews/<int:review_id>', methods=['DELETE'])
@admin_required
def delete_review(review_id):
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() # Get cursor for transaction
    try:
        if not query_db("SELECT id FROM reviews WHERE id = ?", [review_id], db_conn=db, one=True):
            return jsonify(message="Review not found"), 404
        cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        db.commit() # Commit transaction
        audit_logger.log_action(user_id=current_admin_id, action='delete_review', target_type='review', target_id=review_id, details=f"Review {review_id} deleted.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Review deleted successfully"), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to delete review: {e}"), 500

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
    cursor = db.cursor() # Get cursor for transaction
    data = request.json
    if not data: return jsonify(message="No settings data provided"), 400
    
    updated_keys = []
    try:
        for key, value_obj in data.items():
            value_to_store = value_obj.get('value') if isinstance(value_obj, dict) else value_obj
            if value_to_store is not None:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (key, str(value_to_store)))
                updated_keys.append(key)
        db.commit() # Commit transaction
        audit_logger.log_action(user_id=current_admin_id, action='update_settings', target_type='application_settings', details=f"Settings updated: {', '.join(updated_keys)}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Settings updated successfully", updated_settings=updated_keys), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update settings: {e}"), 500

# --- Detailed Inventory View ---
@admin_api_bp.route('/inventory/items/detailed', methods=['GET'])
@admin_required
def get_detailed_inventory_items():
    db = get_db_connection()
    try:
        sql_query = """
            SELECT
                p.name AS product_name,
                CASE
                    WHEN pwo.id IS NOT NULL THEN p.name || ' - ' || pwo.weight_grams || 'g (' || pwo.sku_suffix || ')'
                    ELSE NULL
                END AS variant_name,
                sii.item_uid,
                sii.status,
                sii.batch_number,
                sii.production_date,
                sii.expiry_date,
                sii.received_at,
                sii.actual_weight_grams,
                sii.cost_price,
                sii.purchase_price,
                sii.notes AS item_notes,
                sii.qr_code_url,
                sii.passport_url,
                sii.label_url,
                sii.id as serialized_item_db_id,
                p.id as product_db_id,
                pwo.id as variant_db_id
            FROM
                serialized_inventory_items sii
            JOIN
                products p ON sii.product_id = p.id
            LEFT JOIN
                product_weight_options pwo ON sii.variant_id = pwo.id
            ORDER BY
                p.name, sii.item_uid;
        """
        items_data = query_db(sql_query, db_conn=db)
        
        detailed_items = []
        if items_data:
            for row in items_data:
                item = dict(row)
                item['production_date'] = format_datetime_for_storage(item['production_date']) # Frontend expects ISO string
                item['expiry_date'] = format_datetime_for_storage(item['expiry_date'])
                item['received_at'] = format_datetime_for_storage(item['received_at'])
                detailed_items.append(item)
        return jsonify(success=True, data=detailed_items), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching detailed inventory items: {e}", exc_info=True)
        return jsonify(success=False, message="Failed to fetch detailed inventory items"), 500

# --- Asset Serving (Example for uploaded files) ---
@admin_api_bp.route('/assets/<path:asset_relative_path>')
@admin_required # Or staff_or_admin_required if staff need access
def serve_asset(asset_relative_path):
    # asset_relative_path could be 'categories/image.jpg' or 'products/image.jpg' or 'professional_documents/doc.pdf'
    # It could also be 'qr_codes/qr_item.png', 'passports/passport_item.html', 'labels/label_item.png'
    
    # Determine base folder based on the first part of the path or a more robust mapping
    # For simplicity, assuming UPLOAD_FOLDER for user uploads and ASSET_STORAGE_PATH for generated.
    
    # Security: Prevent directory traversal
    if ".." in asset_relative_path or asset_relative_path.startswith("/"):
        from flask import abort
        return abort(404)

    # Try UPLOAD_FOLDER first (e.g., for category images, product images)
    # Then try ASSET_STORAGE_PATH (e.g., for QR codes, passports, labels, invoices)
    
    possible_base_paths = [
        current_app.config['UPLOAD_FOLDER'], 
        current_app.config['ASSET_STORAGE_PATH']
    ]
    
    found_path = None
    for base_path in possible_base_paths:
        full_path = os.path.join(base_path, asset_relative_path)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            # Further check: ensure the path is truly within the intended base directory
            # to prevent attacks if asset_relative_path somehow manipulates the path.
            # os.path.commonprefix can be used, or os.path.realpath
            if os.path.realpath(full_path).startswith(os.path.realpath(base_path)):
                found_path = full_path
                directory_to_serve_from = base_path
                filename_to_serve = asset_relative_path
                break
    
    if found_path:
        current_app.logger.debug(f"Serving asset: {filename_to_serve} from directory: {directory_to_serve_from}")
        return send_from_directory(directory_to_serve_from, filename_to_serve)
    else:
        current_app.logger.warning(f"Asset not found: {asset_relative_path} in configured asset/upload paths.")
        from flask import abort
        return abort(404)