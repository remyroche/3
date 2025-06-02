# backend/admin_api/routes.py

import os
import json
import uuid
import sqlite3
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash # Added for admin login
from flask import Blueprint, request, jsonify, current_app, g, url_for, send_from_directory # send_from_directory was missing
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity # Added create_access_token, create_refresh_token

from ..utils import (
    admin_required,
    format_datetime_for_display,
    parse_datetime_from_iso,
    generate_slug,
    allowed_file,
    get_file_extension,
    format_datetime_for_storage,
    generate_static_json_files
)
from ..database import get_db_connection, query_db, record_stock_movement
from . import admin_api_bp

# --- Admin Authentication ---
@admin_api_bp.route('/login', methods=['POST'])
def admin_login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    audit_logger = current_app.audit_log_service

    if not email or not password:
        audit_logger.log_action(action='admin_login_fail', email=email, details="Email and password required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Email and password are required"), 400

    db = get_db_connection()
    try:
        admin_user_data = query_db(
            "SELECT id, email, password_hash, role, is_active, first_name, last_name FROM users WHERE email = ? AND role = 'admin'",
            [email],
            db_conn=db,
            one=True
        )

        if admin_user_data and check_password_hash(admin_user_data['password_hash'], password):
            admin_user = dict(admin_user_data)
            if not admin_user['is_active']:
                audit_logger.log_action(user_id=admin_user['id'], action='admin_login_fail_inactive', target_type='user_admin', target_id=admin_user['id'], details="Admin account is inactive.", status='failure', ip_address=request.remote_addr)
                return jsonify(message="Admin account is inactive. Please contact support."), 403

            identity = admin_user['id']
            additional_claims = {
                "role": admin_user['role'],
                "email": admin_user['email'],
                "is_admin": True, # Explicitly mark as admin
                "first_name": admin_user.get('first_name'),
                "last_name": admin_user.get('last_name')
            }
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            # refresh_token = create_refresh_token(identity=identity) # Optional: implement refresh token logic if needed for admin

            audit_logger.log_action(user_id=admin_user['id'], action='admin_login_success', target_type='user_admin', target_id=admin_user['id'], status='success', ip_address=request.remote_addr)
            
            # Prepare user info to return to frontend (without password hash)
            user_info_to_return = {
                "id": admin_user['id'],
                "email": admin_user['email'],
                "prenom": admin_user.get('first_name'), # Match frontend 'prenom'
                "nom": admin_user.get('last_name'),     # Match frontend 'nom'
                "role": admin_user['role'],
                "is_admin": True
            }
            return jsonify(
                success=True,
                message="Admin login successful!",
                token=access_token,
                # refresh_token=refresh_token, # Uncomment if using refresh tokens
                user=user_info_to_return
            ), 200
        else:
            audit_logger.log_action(action='admin_login_fail_credentials', email=email, details="Invalid admin credentials.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid admin email or password"), 401

    except Exception as e:
        current_app.logger.error(f"Error during admin login for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='admin_login_fail_server_error', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Admin login failed due to a server error"), 500


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
    category_code = data.get('category_code', '').strip().upper() # Ensure uppercase for consistency
    image_file = request.files.get('image_url') 
    
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not name or not category_code:
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail', details="Name and Category Code are required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Name and Category Code are required"), 400

    slug = generate_slug(name)
    db = get_db_connection()
    cursor = db.cursor() 
    image_filename_db = None 

    try:
        if query_db("SELECT id FROM categories WHERE name = ?", [name], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='create_category_fail_name_exists', details=f"Category name '{name}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category name '{name}' already exists"), 409
        if query_db("SELECT id FROM categories WHERE slug = ?", [slug], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='create_category_fail_slug_exists', details=f"Category slug '{slug}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category slug '{slug}' already exists. Try a different name."), 409
        if query_db("SELECT id FROM categories WHERE category_code = ?", [category_code], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='create_category_fail_code_exists', details=f"Category code '{category_code}' already exists.", status='failure', ip_address=request.remote_addr)
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
            "INSERT INTO categories (name, description, parent_id, slug, image_url, category_code, is_active) VALUES (?, ?, ?, ?, ?, ?, TRUE)", # Default is_active to TRUE
            (name, description, parent_id, slug, image_filename_db, category_code)
        )
        category_id = cursor.lastrowid
        db.commit() 
        
        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after category creation: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='create_category', target_type='category', target_id=category_id, details=f"Category '{name}' created.", status='success', ip_address=request.remote_addr)
        created_category = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        return jsonify(message="Category created successfully", category=dict(created_category) if created_category else {}, success=True), 201
    except sqlite3.IntegrityError as e:
        db.rollback()
        current_app.logger.error(f"Category creation integrity error: {e}")
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail_integrity', details=f"Database integrity error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Category name, slug, or code likely already exists (DB integrity)."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error creating category: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='create_category_fail_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to create category due to a server error."), 500


@admin_api_bp.route('/categories', methods=['GET'])
@admin_required
def get_categories():
    db = get_db_connection()
    try:
        # Added is_active to the SELECT
        categories_data = query_db("SELECT id, name, description, parent_id, slug, image_url, category_code, is_active, created_at, updated_at FROM categories ORDER BY name", db_conn=db)
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
        # Added is_active
        category_data = query_db("SELECT *, is_active FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
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
    category_code = data.get('category_code', '').strip().upper() # Ensure uppercase
    is_active_str = data.get('is_active') # Get as string first
    image_file = request.files.get('image_url')
    remove_image = data.get('remove_image') == 'true'

    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    if not name or not category_code: # Category code is now mandatory
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail_missing_fields', target_type='category', target_id=category_id, details="Name and Category Code are required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Name and Category Code are required for update"), 400

    db = get_db_connection()
    cursor = db.cursor() 
    try:
        current_category_row = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if not current_category_row:
            audit_logger.log_action(user_id=current_user_id, action='update_category_fail_not_found', target_type='category', target_id=category_id, details="Category not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Category not found"), 404
        current_category = dict(current_category_row)

        new_slug = generate_slug(name) if name != current_category['name'] else current_category['slug']
        
        # Validations for name, slug, and code conflicts
        if name != current_category['name'] and query_db("SELECT id FROM categories WHERE name = ? AND id != ?", [name, category_id], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='update_category_fail_name_exists', target_type='category', target_id=category_id, details=f"Category name '{name}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Another category with the name '{name}' already exists"), 409
        if new_slug != current_category['slug'] and query_db("SELECT id FROM categories WHERE slug = ? AND id != ?", [new_slug, category_id], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='update_category_fail_slug_exists', target_type='category', target_id=category_id, details=f"Category slug '{new_slug}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Another category with slug '{new_slug}' already exists. Try a different name."), 409
        if category_code != current_category.get('category_code') and query_db("SELECT id FROM categories WHERE category_code = ? AND id != ?", [category_code, category_id], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='update_category_fail_code_exists', target_type='category', target_id=category_id, details=f"Category code '{category_code}' already exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Another category with code '{category_code}' already exists."), 409

        upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
        os.makedirs(upload_folder_categories, exist_ok=True)
        image_filename_to_update_db = current_category['image_url']

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
        if parent_id_str and parent_id_str.strip() and parent_id_str.lower() != 'null': # Check for 'null' string
            try:
                parent_id_to_update = int(parent_id_str)
                if parent_id_to_update == category_id:
                    audit_logger.log_action(user_id=current_user_id, action='update_category_fail_self_parent', target_type='category', target_id=category_id, details="Category cannot be its own parent.", status='failure', ip_address=request.remote_addr)
                    return jsonify(message="Category cannot be its own parent."), 400
            except ValueError:
                audit_logger.log_action(user_id=current_user_id, action='update_category_fail_invalid_parent_id', target_type='category', target_id=category_id, details="Invalid parent ID format.", status='failure', ip_address=request.remote_addr)
                return jsonify(message="Invalid parent ID format."), 400
        
        description_to_update = description if description is not None else current_category['description']
        is_active_to_update = is_active_str.lower() == 'true' if is_active_str is not None else current_category['is_active']


        cursor.execute(
            """UPDATE categories SET 
               name = ?, description = ?, parent_id = ?, slug = ?, image_url = ?, category_code = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (name, description_to_update, parent_id_to_update, new_slug, image_filename_to_update_db, category_code, is_active_to_update, category_id)
        )
        db.commit() 
        
        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after category update: {e_gen}", exc_info=True)
        
        audit_logger.log_action(user_id=current_user_id, action='update_category', target_type='category', target_id=category_id, details=f"Category '{name}' updated.", status='success', ip_address=request.remote_addr)
        updated_category = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        return jsonify(message="Category updated successfully", category=dict(updated_category) if updated_category else {}, success=True), 200
    except sqlite3.IntegrityError as e:
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail_integrity', target_type='category', target_id=category_id, details=f"DB integrity error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Category name, slug, or code likely conflicts with an existing one (DB integrity)."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating category {category_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='update_category_fail_exception', target_type='category', target_id=category_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update category due to a server error."), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() 

    try:
        category_to_delete_row = query_db("SELECT image_url, name FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if not category_to_delete_row:
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail_not_found', target_type='category', target_id=category_id, details="Category not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Category not found"), 404
        category_to_delete = dict(category_to_delete_row)

        products_in_category_row = query_db("SELECT COUNT(*) FROM products WHERE category_id = ?", [category_id], db_conn=db, one=True)
        products_in_category = products_in_category_row[0] if products_in_category_row else 0
        if products_in_category > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail_in_use', target_type='category', target_id=category_id, details=f"Category '{category_to_delete['name']}' in use by {products_in_category} products.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Category '{category_to_delete['name']}' is in use by products. Reassign products first."), 409
        
        if category_to_delete['image_url']:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category_to_delete['image_url'])
            if os.path.exists(full_image_path):
                try: os.remove(full_image_path)
                except OSError as e_rem: current_app.logger.error(f"Error deleting category image {full_image_path}: {e_rem}")
        
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        db.commit() 

        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after category deletion: {e_gen}", exc_info=True)

        if cursor.rowcount > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_category', target_type='category', target_id=category_id, details=f"Category '{category_to_delete['name']}' deleted.", status='success', ip_address=request.remote_addr)
            return jsonify(message=f"Category '{category_to_delete['name']}' deleted successfully"), 200
        else: 
            audit_logger.log_action(user_id=current_user_id, action='delete_category_fail_not_deleted_race', target_type='category', target_id=category_id, details="Category not found during delete op (race condition?).", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Category not found during delete operation"), 404
    except sqlite3.IntegrityError as e: 
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='delete_category_fail_integrity_subcategories', target_type='category', target_id=category_id, details=f"DB integrity error: {e}. Subcategories might exist.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete category due to DB integrity constraints (e.g., subcategories exist)."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error deleting category {category_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='delete_category_fail_exception', target_type='category', target_id=category_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to delete category due to a server error."), 500

# --- Product Management ---
@admin_api_bp.route('/products', methods=['POST'])
@admin_required
def create_product():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor()

    try:
        data = request.form.to_dict() 
        main_image_file = request.files.get('image_url_main') # Changed from 'main_image_url'
        
        name = data.get('name')
        # The form uses 'productCode' for the SKU prefix, map it to sku_prefix
        sku_prefix = data.get('product_code', '').strip().upper() # Use product_code from form, ensure uppercase
        product_type = data.get('type', 'simple') # Default to 'simple' if not provided
        description = data.get('description', '') # Use 'description' from form
        
        # Category ID is directly submitted from select
        category_id_str = data.get('category_id')
        category_id = int(category_id_str) if category_id_str and category_id_str.isdigit() else None

        brand = data.get('brand', "Maison Trüvra") # Default brand
        base_price_str = data.get('price') # Form uses 'price' for base_price
        currency = data.get('currency', 'EUR')
        
        # Map form field 'quantity' to 'aggregate_stock_quantity'
        aggregate_stock_quantity_str = data.get('quantity', '0')
        aggregate_stock_weight_grams_str = data.get('aggregate_stock_weight_grams') # Keep if used
        unit_of_measure = data.get('unit_of_measure')
        
        # Form uses 'productIsActive' and 'productIsFeatured'
        is_active = data.get('is_active', 'true').lower() == 'true' # Default to true
        is_featured = data.get('is_featured', 'false').lower() == 'true' # Default to false
        
        meta_title = data.get('meta_title', name) # Default to product name
        meta_description = data.get('meta_description', description[:160] if description else '') # Default to start of description
        slug = generate_slug(name)

        if not all([name, sku_prefix, product_type, category_id is not None]): # Category is now mandatory
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail_missing_fields', details="Name, SKU Prefix, Type, Category required.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Name, SKU Prefix (Product Code), Type, and Category are required."), 400
        
        if query_db("SELECT id FROM products WHERE sku_prefix = ?", [sku_prefix], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail_sku_exists', details=f"SKU prefix '{sku_prefix}' exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"SKU prefix (Product Code) '{sku_prefix}' already exists."), 409
        if query_db("SELECT id FROM products WHERE slug = ?", [slug], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail_slug_exists', details=f"Product slug '{slug}' exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Product name (slug: '{slug}') already exists. Choose a different name."), 409

        main_image_filename_db = None
        if main_image_file and allowed_file(main_image_file.filename):
            filename = secure_filename(f"product_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(main_image_file.filename)}")
            upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
            os.makedirs(upload_folder_products, exist_ok=True)
            main_image_file.save(os.path.join(upload_folder_products, filename))
            main_image_filename_db = os.path.join('products', filename)

        base_price = float(base_price_str) if base_price_str is not None and base_price_str != '' else None
        aggregate_stock_quantity = int(aggregate_stock_quantity_str) if aggregate_stock_quantity_str is not None and aggregate_stock_quantity_str != '' else 0
        aggregate_stock_weight_grams = float(aggregate_stock_weight_grams_str) if aggregate_stock_weight_grams_str else None

        if product_type == 'simple' and base_price is None:
            audit_logger.log_action(user_id=current_user_id, action='create_product_fail_price_simple', details="Base price required for simple products.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Base price (Price field) is required for simple products."), 400
        
        # product_code is now the sku_prefix for consistency with schema
        # The form sends 'productCode' which is mapped to sku_prefix
        product_code_db_val = sku_prefix # Use the validated sku_prefix as the product_code

        # Main product insert
        cursor.execute(
            """INSERT INTO products (name, description, category_id, product_code, brand, sku_prefix, type, 
                                   base_price, currency, main_image_url, aggregate_stock_quantity, 
                                   aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured, 
                                   meta_title, meta_description, slug)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, description, category_id, product_code_db_val, brand, sku_prefix, product_type, 
             base_price, currency, main_image_filename_db, 
             aggregate_stock_quantity if product_type == 'simple' else 0, 
             aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured, 
             meta_title, meta_description, slug)
        )
        product_id = cursor.lastrowid
        
        # For simple products, if stock quantity is provided, record it.
        if product_type == 'simple' and aggregate_stock_quantity > 0:
             record_stock_movement(db, product_id, 'initial_stock', quantity_change=aggregate_stock_quantity, reason="Initial stock for new simple product", related_user_id=current_user_id)
        
        # Note: Weight options handling is removed from here as it's complex for a simple create form.
        # It's better handled in a separate variant management UI or during product edit.
        # If the product type is 'variable_weight', its aggregate stocks will be 0 initially
        # and updated when variants are added/managed via the inventory section.

        db.commit() 
        
        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after product creation: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='create_product', target_type='product', target_id=product_id, details=f"Product '{name}' (Code: {product_code_db_val}) created.", status='success', ip_address=request.remote_addr)
        
        created_product_data_row = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        response_data = {"message": "Product created successfully", "product_id": product_id, "slug": slug, "success": True}
        if created_product_data_row:
            response_data["product"] = dict(created_product_data_row)
        return jsonify(response_data), 201

    except (sqlite3.IntegrityError, ValueError) as e:
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='create_product_fail_db_value_error', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to create product: {str(e)}", success=False), 400 if isinstance(e, ValueError) else 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Unexpected error creating product: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='create_product_fail_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to create product due to an unexpected server error.", success=False), 500

@admin_api_bp.route('/products', methods=['GET'])
@admin_required # Keep admin_required for the admin version of product listing
def get_products_admin(): # Renamed to avoid conflict if public /products is different
    db = get_db_connection()
    include_variants_param = request.args.get('include_variants', 'false').lower() == 'true'
    try:
        # Added product_code, is_active, is_featured to SELECT
        products_data = query_db(
            """SELECT p.*, c.name as category_name, c.category_code 
               FROM products p LEFT JOIN categories c ON p.category_id = c.id 
               ORDER BY p.name""", db_conn=db
        )
        products = [dict(row) for row in products_data] if products_data else []
        for product in products:
            product['created_at'] = format_datetime_for_display(product['created_at'])
            product['updated_at'] = format_datetime_for_display(product['updated_at'])
            # Frontend expects 'price' to be 'base_price' for display consistency in admin table
            product['price'] = product.get('base_price') 
            # Frontend expects 'quantity' to be 'aggregate_stock_quantity'
            product['quantity'] = product.get('aggregate_stock_quantity')

            if product.get('main_image_url'):
                product['main_image_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=product['main_image_url'], _external=True)
            
            if product['type'] == 'variable_weight' or include_variants_param:
                options_data = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product['id']], db_conn=db)
                product['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
                product['variant_count'] = len(product['weight_options'])
                if product['type'] == 'variable_weight' and product['weight_options']:
                    # Recalculate aggregate stock for variable products based on their variants for admin display
                    product['quantity'] = sum(opt.get('aggregate_stock_quantity', 0) for opt in product['weight_options'])
            
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
        current_app.logger.error(f"Error fetching products for admin: {e}", exc_info=True)
        return jsonify(message="Failed to fetch products for admin"), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['GET'])
@admin_required
def get_product_admin_detail(product_id): # Name is fine as it's specific by ID
    db = get_db_connection()
    try:
        # Added product_code to SELECT
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
                        # Ensure 'serve_passport_public' is correctly defined in your app's URL map
                        # It seems to be in __init__.py, so this should work IF app context is right
                        if asset_row['asset_type'] == 'passport_html' and 'serve_passport_public' in current_app.view_functions:
                             # Passports are public, use the public route from __init__.py
                            passport_filename = os.path.basename(asset_row['file_path'])
                            asset_full_url = url_for('serve_passport_public', filename=passport_filename, _external=True)
                        else:
                             # Other assets (QR, labels) might be admin-only or served differently
                            asset_full_url = url_for('admin_api_bp.serve_asset', asset_relative_path=asset_row['file_path'], _external=True)
                    except Exception as e_asset_url:
                        current_app.logger.warning(f"Could not generate URL for asset {asset_row['file_path']}: {e_asset_url}")
                
                product_assets[f"{asset_type_key}_url"] = asset_full_url
                product_assets[f"{asset_type_key}_file_path"] = asset_row['file_path']
        product['assets'] = product_assets
            
        return jsonify(product), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching product {product_id} for admin: {e}", exc_info=True)
        return jsonify(message="Failed to fetch product details for admin"), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['PUT'])
@admin_required
def update_product(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() 

    try:
        current_product_row = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not current_product_row:
            audit_logger.log_action(user_id=current_user_id, action='update_product_fail_not_found', target_type='product', target_id=product_id, details="Product not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Product not found"), 404
        current_product = dict(current_product_row)

        data = request.form.to_dict()
        main_image_file = request.files.get('image_url_main') # Changed from 'main_image_url'
        remove_main_image = data.get('remove_main_image') == 'true'

        name = data.get('name', current_product['name'])
        new_slug = generate_slug(name) if name != current_product['name'] else current_product['slug']
        
        # Form uses 'productCode' for SKU (product_code in DB)
        new_product_code = data.get('product_code', current_product['product_code']).strip().upper()
        if new_product_code != current_product['product_code'] and query_db("SELECT id FROM products WHERE product_code = ? AND id != ?", [new_product_code, product_id], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='update_product_fail_code_exists', target_type='product', target_id=product_id, details=f"Product Code '{new_product_code}' exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Product Code '{new_product_code}' already exists."), 409
        
        # sku_prefix is also updated if product_code changes, assuming they are linked or the same
        new_sku_prefix = new_product_code 

        if new_slug != current_product['slug'] and query_db("SELECT id FROM products WHERE slug = ? AND id != ?", [new_slug, product_id], db_conn=db, one=True):
            audit_logger.log_action(user_id=current_user_id, action='update_product_fail_slug_exists', target_type='product', target_id=product_id, details=f"Slug '{new_slug}' exists.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Product name (slug: '{new_slug}') already exists."), 409
        
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

        category_id_str = data.get('category_id') # From form select
        category_id_to_update = current_product['category_id']
        if category_id_str and category_id_str.isdigit():
            category_id_to_update = int(category_id_str)
        elif category_id_str == "": # Handle empty string for "no category"
             category_id_to_update = None


        update_payload_product = {
            'name': name, 'slug': new_slug, 
            'product_code': new_product_code, # This is the main SKU
            'sku_prefix': new_sku_prefix,     # Often same as product_code or a base for variants
            'description': data.get('description', current_product['description']), # Form uses 'description'
            'category_id': category_id_to_update,
            'brand': data.get('brand', current_product['brand']),
            'type': data.get('type', current_product['type']),
            'base_price': float(data['price']) if data.get('price') is not None and data.get('price') != '' else current_product['base_price'], # Form uses 'price'
            'currency': data.get('currency', current_product['currency']),
            'main_image_url': main_image_filename_db,
            'aggregate_stock_quantity': int(data.get('quantity', current_product['aggregate_stock_quantity'])), # Form uses 'quantity'
            'aggregate_stock_weight_grams': float(data['aggregate_stock_weight_grams']) if data.get('aggregate_stock_weight_grams') is not None and data.get('aggregate_stock_weight_grams') != '' else current_product['aggregate_stock_weight_grams'],
            'unit_of_measure': data.get('unit_of_measure', current_product['unit_of_measure']),
            'is_active': data.get('is_active', str(current_product['is_active'])).lower() == 'true', # Form uses 'is_active'
            'is_featured': data.get('is_featured', str(current_product['is_featured'])).lower() == 'true', # Form uses 'is_featured'
            'meta_title': data.get('meta_title', current_product['meta_title'] or name),
            'meta_description': data.get('meta_description', current_product['meta_description'] or data.get('description', '')[:160]),
        }
        
        if update_payload_product['type'] == 'simple' and update_payload_product['base_price'] is None:
            audit_logger.log_action(user_id=current_user_id, action='update_product_fail_price_simple', target_type='product', target_id=product_id, details="Base price required for simple product.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Base price (Price field) is required for simple products."), 400
        
        # Removed weight_options handling from here for simplicity in PUT.
        # Assume variants are managed separately via inventory/variant routes.
        # If product type changes, existing variants might need to be cleared or handled.
        # For now, this PUT focuses on the main product entity.

        set_clause_product = ", ".join([f"{key} = ?" for key in update_payload_product.keys()])
        sql_args_product = list(update_payload_product.values())
        sql_args_product.append(product_id)

        cursor.execute(f"UPDATE products SET {set_clause_product}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", tuple(sql_args_product))
        
        # If type changed from variable_weight to simple, consider deleting old variants
        if current_product['type'] == 'variable_weight' and update_payload_product['type'] == 'simple':
            cursor.execute("DELETE FROM product_weight_options WHERE product_id = ?", (product_id,))
            current_app.logger.info(f"Product {product_id} type changed to simple, variants deleted.")
        
        db.commit() 
        
        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after product update: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='update_product', target_type='product', target_id=product_id, details=f"Product '{name}' (Code: {new_product_code}) updated.", status='success', ip_address=request.remote_addr)
        
        # Fetch the fully updated product to return
        updated_product_response = get_product_admin_detail(product_id) # Use the admin detail getter
        return jsonify(message="Product updated successfully", product=updated_product_response.get_json() if updated_product_response else {}, success=True), 200

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
    cursor = db.cursor() 
    try:
        product_to_delete_row = query_db("SELECT name, main_image_url, product_code FROM products WHERE id = ?", [product_id], db_conn=db, one=True) # Changed sku_prefix to product_code
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
        
        db.commit() 

        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after product deletion: {e_gen}", exc_info=True)

        if cursor.rowcount > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_product', target_type='product', target_id=product_id, details=f"Product '{product_to_delete['name']}' (Code: {product_to_delete['product_code']}) deleted.", status='success', ip_address=request.remote_addr)
            return jsonify(message=f"Product '{product_to_delete['name']}' deleted successfully"), 200
        else: 
            audit_logger.log_action(user_id=current_user_id, action='delete_product_fail_not_deleted_race', target_type='product', target_id=product_id, details="Product not found during delete op (race condition?).", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Product not found during delete operation"), 404
    except sqlite3.IntegrityError as e:
        db.rollback()
        audit_logger.log_action(user_id=current_user_id, action='delete_product_fail_integrity_orders', target_type='product', target_id=product_id, details=f"DB integrity error (e.g., in orders): {e}", status='failure', ip_address=request.remote_addr)
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
    role_filter = request.args.get('role')
    status_filter_str = request.args.get('is_active') # Changed from 'status'
    search_term = request.args.get('search')

    query_sql = "SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, professional_status, created_at FROM users"
    conditions = []
    params = []

    if role_filter: conditions.append("role = ?"); params.append(role_filter)
    if status_filter_str is not None: # Check for presence, not just truthiness
        is_active_val = status_filter_str.lower() == 'true'
        conditions.append("is_active = ?")
        params.append(is_active_val)
    if search_term:
        conditions.append("(email LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR company_name LIKE ? OR CAST(id AS TEXT) LIKE ?)") # Added ID search
        term = f"%{search_term}%"
        params.extend([term, term, term, term, term])
    
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
def get_user_admin_detail(user_id): # Name is fine
    db = get_db_connection()
    try:
        user_data = query_db("SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, vat_number, siret_number, professional_status, created_at, updated_at FROM users WHERE id = ?", [user_id], db_conn=db, one=True)
        if not user_data: return jsonify(message="User not found"), 404
        
        user = dict(user_data)
        user['created_at'] = format_datetime_for_display(user['created_at'])
        user['updated_at'] = format_datetime_for_display(user['updated_at'])
        
        orders_data = query_db("SELECT id as order_id, order_date, total_amount, status FROM orders WHERE user_id = ? ORDER BY order_date DESC", [user_id], db_conn=db)
        user['orders'] = [dict(row) for row in orders_data] if orders_data else []
        for order_item in user['orders']: 
            order_item['order_date'] = format_datetime_for_display(order_item['order_date'])
        return jsonify(user), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching details for user {user_id} (admin): {e}", exc_info=True)
        return jsonify(message="Failed to fetch user details (admin)"), 500

@admin_api_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user_admin(user_id): # Renamed to avoid conflict
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() 
    data = request.json

    if not data: return jsonify(message="No data provided"), 400

    allowed_fields = ['first_name', 'last_name', 'role', 'is_active', 'is_verified', 
                      'company_name', 'vat_number', 'siret_number', 'professional_status']
    update_payload = {k: data[k] for k in data if k in allowed_fields}

    if not update_payload: return jsonify(message="No valid fields to update"), 400
    
    # Ensure boolean conversions for is_active and is_verified
    if 'is_active' in update_payload: 
        update_payload['is_active'] = str(update_payload['is_active']).lower() == 'true'
    if 'is_verified' in update_payload: 
        update_payload['is_verified'] = str(update_payload['is_verified']).lower() == 'true'


    set_clause = ", ".join([f"{key} = ?" for key in update_payload.keys()])
    sql_args = list(update_payload.values())
    sql_args.append(user_id)

    try:
        if not query_db("SELECT id FROM users WHERE id = ?", [user_id], db_conn=db, one=True):
             return jsonify(message="User not found"), 404

        cursor.execute(f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", tuple(sql_args))
        db.commit() 
        
        if cursor.rowcount == 0: return jsonify(message="User not found or no changes made"), 404 # Should be caught by above check
        
        audit_logger.log_action(user_id=current_admin_id, action='update_user_admin', target_type='user', target_id=user_id, details=f"User {user_id} updated by admin. Fields: {', '.join(update_payload.keys())}", status='success', ip_address=request.remote_addr)
        return jsonify(message="User updated successfully"), 200
    except sqlite3.Error as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_user_admin_fail_db_error', target_type='user', target_id=user_id, details=f"DB error: {e}", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update user due to DB error"), 500
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_user_admin_fail_exception', target_type='user', target_id=user_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update user"), 500

# --- Order Management ---
@admin_api_bp.route('/orders', methods=['GET'])
@admin_required
def get_orders_admin(): # Renamed to avoid conflict
    db = get_db_connection()
    search_filter = request.args.get('search')
    status_filter = request.args.get('status')
    date_filter_str = request.args.get('date') # Date as string YYYY-MM-DD

    query_sql = """
        SELECT o.id as order_id, o.user_id, o.order_date, o.status, o.total_amount, o.currency,
               u.email as customer_email, (u.first_name || ' ' || u.last_name) as customer_name
        FROM orders o LEFT JOIN users u ON o.user_id = u.id
    """
    conditions = []
    params = []

    if search_filter:
        conditions.append("(CAST(o.id AS TEXT) LIKE ? OR u.email LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ? OR o.payment_transaction_id LIKE ?)")
        term = f"%{search_filter}%"
        params.extend([term, term, term, term, term])
    if status_filter:
        conditions.append("o.status = ?")
        params.append(status_filter)
    if date_filter_str: 
        try:
            # Ensure date_filter_str is a valid date format before using in query
            datetime.strptime(date_filter_str, '%Y-%m-%d') # Validates format
            conditions.append("DATE(o.order_date) = ?") # Compare only the date part
            params.append(date_filter_str)
        except ValueError:
            return jsonify(message="Invalid date format for filter. Use YYYY-MM-DD."), 400


    if conditions: query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY o.order_date DESC"

    try:
        orders_data = query_db(query_sql, params, db_conn=db)
        orders = [dict(row) for row in orders_data] if orders_data else []
        for order in orders:
            order['order_date'] = format_datetime_for_display(order['order_date'])
        return jsonify(orders), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching orders for admin: {e}", exc_info=True)
        return jsonify(message="Failed to fetch orders for admin"), 500

@admin_api_bp.route('/orders/<int:order_id>', methods=['GET'])
@admin_required
def get_order_admin_detail(order_id): # Name is fine
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
        current_app.logger.error(f"Error fetching details for order {order_id} (admin): {e}", exc_info=True)
        return jsonify(message="Failed to fetch order details (admin)"), 500

@admin_api_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@admin_required
def update_order_status_admin(order_id): # Renamed
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() 
    data = request.json
    new_status = data.get('status')
    tracking_number = data.get('tracking_number')
    carrier = data.get('carrier') 

    if not new_status: return jsonify(message="New status not provided"), 400
    allowed_statuses = ['pending_payment', 'paid', 'processing', 'awaiting_shipment', 'shipped', 'delivered', 'completed', 'cancelled', 'refunded', 'on_hold', 'failed'] # Expanded list
    if new_status not in allowed_statuses:
        return jsonify(message=f"Invalid status. Allowed: {', '.join(allowed_statuses)}"), 400

    try:
        order_info_row = query_db("SELECT status FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)
        if not order_info_row: return jsonify(message="Order not found"), 404
        order_info = dict(order_info_row)

        update_fields = {"status": new_status}
        if new_status in ['shipped', 'delivered']: # Only add tracking if relevant
            if tracking_number: update_fields["tracking_number"] = tracking_number
            if carrier: update_fields["shipping_method"] = carrier 
        
        set_clause_parts = [f"{key} = ?" for key in update_fields.keys()]
        set_clause_parts.append("updated_at = CURRENT_TIMESTAMP") 
        
        params = list(update_fields.values())
        params.append(order_id)
        
        cursor.execute(f"UPDATE orders SET {', '.join(set_clause_parts)} WHERE id = ?", tuple(params))
        db.commit() 
        
        audit_logger.log_action(user_id=current_admin_id, action='update_order_status_admin', target_type='order', target_id=order_id, details=f"Order {order_id} status from '{order_info['status']}' to '{new_status}'. Tracking: {tracking_number or 'N/A'}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Order status updated to {new_status}", success=True), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_order_status_admin_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update order status", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>/notes', methods=['POST'])
@admin_required
def add_order_note_admin(order_id): # Renamed
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() 
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
        db.commit() 
        
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note_admin', target_type='order', target_id=order_id, details=f"Added note to order {order_id}: '{note_content[:50]}...'", status='success', ip_address=request.remote_addr)
        return jsonify(message="Note added successfully.", new_note_entry=new_note_entry, success=True), 201
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note_admin_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to add note to order", success=False), 500

# --- Review Management ---
@admin_api_bp.route('/reviews', methods=['GET'])
@admin_required
def get_reviews_admin(): # Renamed
    db = get_db_connection()
    status_filter = request.args.get('status') 
    product_id_filter_str = request.args.get('product_id') # Can be product_code or ID
    user_id_filter_str = request.args.get('user_id') # Can be user_id or email

    query_sql = """
        SELECT r.id, r.product_id, p.name as product_name, p.product_code, r.user_id, u.email as user_email, 
               r.rating, r.comment, r.review_date, r.is_approved
        FROM reviews r JOIN products p ON r.product_id = p.id JOIN users u ON r.user_id = u.id
    """
    conditions = []
    params = []
    if status_filter == 'pending': conditions.append("r.is_approved = FALSE")
    elif status_filter == 'approved': conditions.append("r.is_approved = TRUE")
    
    if product_id_filter_str:
        if product_id_filter_str.isdigit():
            conditions.append("r.product_id = ?")
            params.append(int(product_id_filter_str))
        else: # Assume it's a product name or code
            conditions.append("(p.name LIKE ? OR p.product_code LIKE ?)")
            params.extend([f"%{product_id_filter_str}%", f"%{product_id_filter_str}%"])
            
    if user_id_filter_str:
        if user_id_filter_str.isdigit():
            conditions.append("r.user_id = ?")
            params.append(int(user_id_filter_str))
        else: # Assume it's an email
            conditions.append("u.email LIKE ?")
            params.append(f"%{user_id_filter_str}%")
    
    if conditions: query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY r.review_date DESC"
    
    try:
        reviews_data = query_db(query_sql, params, db_conn=db)
        reviews = [dict(row) for row in reviews_data] if reviews_data else []
        for review in reviews:
            review['review_date'] = format_datetime_for_display(review['review_date'])
        return jsonify(reviews), 200
    except Exception as e: return jsonify(message=f"Failed to fetch reviews (admin): {e}"), 500

@admin_api_bp.route('/reviews/<int:review_id>/approve', methods=['PUT'])
@admin_required
def approve_review_admin(review_id): # Renamed
    return _update_review_approval_admin(review_id, True)

@admin_api_bp.route('/reviews/<int:review_id>/unapprove', methods=['PUT'])
@admin_required
def unapprove_review_admin(review_id): # Renamed
    return _update_review_approval_admin(review_id, False)

def _update_review_approval_admin(review_id, is_approved_status): # Renamed
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() 
    action_verb = "approve" if is_approved_status else "unapprove"
    try:
        if not query_db("SELECT id FROM reviews WHERE id = ?", [review_id], db_conn=db, one=True):
            return jsonify(message="Review not found"), 404
        cursor.execute("UPDATE reviews SET is_approved = ? WHERE id = ?", (is_approved_status, review_id))
        db.commit() 
        audit_logger.log_action(user_id=current_admin_id, action=f'{action_verb}_review_admin', target_type='review', target_id=review_id, details=f"Review {review_id} set to {is_approved_status} by admin.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Review {'approved' if is_approved_status else 'unapproved'} successfully"), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action=f'{action_verb}_review_admin_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to {action_verb} review: {e}"), 500

@admin_api_bp.route('/reviews/<int:review_id>', methods=['DELETE'])
@admin_required
def delete_review_admin(review_id): # Renamed
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() 
    try:
        if not query_db("SELECT id FROM reviews WHERE id = ?", [review_id], db_conn=db, one=True):
            return jsonify(message="Review not found"), 404
        cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        db.commit() 
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin', target_type='review', target_id=review_id, details=f"Review {review_id} deleted by admin.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Review deleted successfully"), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to delete review: {e}"), 500

# --- Settings Management ---
@admin_api_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings_admin(): # Renamed
    db = get_db_connection()
    try:
        settings_data = query_db("SELECT key, value, description FROM settings", db_conn=db)
        settings = {row['key']: {'value': row['value'], 'description': row['description']} for row in settings_data} if settings_data else {}
        return jsonify(settings), 200
    except Exception as e: return jsonify(message=f"Failed to fetch settings (admin): {e}"), 500

@admin_api_bp.route('/settings', methods=['POST'])
@admin_required
def update_settings_admin(): # Renamed
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor() 
    data = request.json
    if not data: return jsonify(message="No settings data provided"), 400
    
    updated_keys = []
    try:
        for key, value_obj in data.items():
            value_to_store = value_obj.get('value') if isinstance(value_obj, dict) else value_obj
            if value_to_store is not None: # Allow empty string for value
                cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (key, str(value_to_store)))
                updated_keys.append(key)
        db.commit() 
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin', target_type='application_settings', details=f"Settings updated by admin: {', '.join(updated_keys)}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Settings updated successfully", updated_settings=updated_keys), 200
    except Exception as e:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update settings: {e}"), 500

# --- Detailed Inventory View (from inventory/routes.py, moved here for admin context) ---
@admin_api_bp.route('/inventory/items/detailed', methods=['GET'])
@admin_required
def get_detailed_inventory_items_admin(): # Renamed
    db = get_db_connection()
    try:
        sql_query = """
            SELECT
                p.name AS product_name,
                p.product_code, -- Added product_code
                pl_fr.name as product_name_fr, -- Added localized names
                pl_en.name as product_name_en,
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
                product_localizations pl_fr ON p.id = pl_fr.product_id AND pl_fr.lang_code = 'fr'
            LEFT JOIN 
                product_localizations pl_en ON p.id = pl_en.product_id AND pl_en.lang_code = 'en'
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
                # Ensure dates are consistently formatted as ISO strings or null
                item['production_date'] = format_datetime_for_storage(item['production_date']) if item.get('production_date') else None
                item['expiry_date'] = format_datetime_for_storage(item['expiry_date']) if item.get('expiry_date') else None
                item['received_at'] = format_datetime_for_storage(item['received_at']) if item.get('received_at') else None
                # Add full URLs for assets if they exist
                if item.get('qr_code_url'):
                    item['qr_code_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item['qr_code_url'], _external=True)
                if item.get('passport_url'):
                    item['passport_full_url'] = url_for('serve_passport_public', filename=os.path.basename(item['passport_url']), _external=True) # Use public route
                if item.get('label_url'):
                    item['label_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item['label_url'], _external=True)
                detailed_items.append(item)
        # The frontend expects a direct array, not nested under 'data' or 'success' for this specific route
        return jsonify(detailed_items), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching detailed inventory items for admin: {e}", exc_info=True)
        # Return an empty array on error to prevent frontend breaking if it expects an array
        return jsonify([]), 500


# --- Asset Serving (Example for uploaded files) ---
@admin_api_bp.route('/assets/<path:asset_relative_path>')
@admin_required 
def serve_asset(asset_relative_path):
    if ".." in asset_relative_path or asset_relative_path.startswith("/"):
        from flask import abort
        return abort(404)

    possible_base_paths_map = {
        'categories': os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories'),
        'products': os.path.join(current_app.config['UPLOAD_FOLDER'], 'products'),
        'professional_documents': current_app.config['PROFESSIONAL_DOCS_UPLOAD_PATH'],
        'qr_codes': current_app.config['QR_CODE_FOLDER'],
        # Passports are served by a public route, but if admin needs direct access:
        # 'passports': current_app.config['PASSPORT_FOLDER'], 
        'labels': current_app.config['LABEL_FOLDER'],
        'invoices': current_app.config['INVOICE_PDF_PATH']
    }
    
    # Determine the base directory from the first part of the asset_relative_path
    path_parts = asset_relative_path.split(os.sep, 1)
    asset_type_folder = path_parts[0]
    filename_in_type_folder = path_parts[1] if len(path_parts) > 1 else None

    if asset_type_folder in possible_base_paths_map and filename_in_type_folder:
        base_path = possible_base_paths_map[asset_type_folder]
        full_path = os.path.join(base_path, filename_in_type_folder)
        
        if os.path.exists(full_path) and os.path.isfile(full_path):
            if os.path.realpath(full_path).startswith(os.path.realpath(base_path)):
                current_app.logger.debug(f"Serving asset: {filename_in_type_folder} from directory: {base_path}")
                return send_from_directory(base_path, filename_in_type_folder)
    
    current_app.logger.warning(f"Admin asset not found or path issue: {asset_relative_path}")
    from flask import abort
    return abort(404)

# --- Regenerate Static JSON Files ---
@admin_api_bp.route('/regenerate-static-json', methods=['POST'])
@admin_required
def regenerate_static_json_endpoint():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        generate_static_json_files() # Call the utility function
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json', status='success', ip_address=request.remote_addr)
        return jsonify(message="Static JSON files (products_details.json, categories_details.json) regenerated successfully.", success=True), 200
    except Exception as e:
        current_app.logger.error(f"Failed to regenerate static JSON files via API: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to regenerate static JSON files: {str(e)}", success=False), 500
```
