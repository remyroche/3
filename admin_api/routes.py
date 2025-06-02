# backend/admin_api/routes.py

import os
import json
import uuid
import sqlite3
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash 
from flask import Blueprint, request, jsonify, current_app, g, url_for, send_from_directory, abort as flask_abort
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt 

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
from ..services.invoice_service import InvoiceService
from . import admin_api_bp


# Helper to check for admin role from JWT claims
def is_admin_user():
    claims = get_jwt()
    return claims.get('role') == 'admin'

@admin_api_bp.route('/users/professionals', methods=['GET'])
@jwt_required()
def get_professional_users_list():
    if not is_admin_user():
        return jsonify(message="Forbidden: Admin access required."), 403
    db = get_db_connection()
    try:
        professionals = query_db(
            "SELECT id, email, first_name, last_name, company_name, professional_status FROM users WHERE role = 'b2b_professional' ORDER BY company_name, last_name, first_name",
            db_conn=db
        )
        return jsonify([dict(row) for row in professionals] if professionals else []), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching professional users for admin: {e}")
        return jsonify(message="Failed to fetch professional users."), 500

@admin_api_bp.route('/invoices/create', methods=['POST'])
@jwt_required()
def admin_create_manual_invoice():
    if not is_admin_user():
        return jsonify(message="Forbidden: Admin access required."), 403
    data = request.json
    b2b_user_id = data.get('b2b_user_id')
    line_items_data = data.get('line_items')
    notes = data.get('notes')
    currency = data.get('currency', 'EUR') 
    if not b2b_user_id or not line_items_data or not isinstance(line_items_data, list) or len(line_items_data) == 0:
        return jsonify(message="Missing required fields: b2b_user_id and at least one line_item."), 400
    for item_data in line_items_data:
        if not all(k in item_data for k in ('description', 'quantity', 'unit_price')):
            return jsonify(message="Each line item must have description, quantity, and unit_price."), 400
        try:
            int(item_data['quantity']); float(item_data['unit_price'])
        except ValueError:
            return jsonify(message="Invalid quantity or unit_price in line items. Must be numbers."), 400
    try:
        invoice_service = InvoiceService()
        invoice_id, invoice_number = invoice_service.create_manual_invoice(b2b_user_id=b2b_user_id, user_currency=currency, line_items_data=line_items_data, notes=notes)
        return jsonify(success=True, message="Manual invoice created successfully.", invoice_id=invoice_id, invoice_number=invoice_number), 201
    except ValueError as ve: 
        current_app.logger.warning(f"Validation error creating manual invoice: {ve}")
        return jsonify(message=str(ve)), 400 
    except Exception as e:
        current_app.logger.error(f"Admin API error creating manual invoice: {e}", exc_info=True)
        return jsonify(message=f"An internal error occurred: {str(e)}"), 500

@admin_api_bp.route('/login', methods=['POST'])
def admin_login():
    data = request.json; email = data.get('email'); password = data.get('password')
    audit_logger = current_app.audit_log_service
    if not email or not password:
        return jsonify(message="Email and password are required", success=False), 400
    db = get_db_connection()
    try:
        admin_user_data = query_db("SELECT id, email, password_hash, role, is_active, first_name, last_name FROM users WHERE email = ? AND role = 'admin'", [email], db_conn=db, one=True)
        if admin_user_data and check_password_hash(admin_user_data['password_hash'], password):
            admin_user = dict(admin_user_data)
            if not admin_user['is_active']:
                return jsonify(message="Admin account is inactive. Please contact support.", success=False), 403
            identity = admin_user['id']
            additional_claims = {"role": admin_user['role'], "email": admin_user['email'], "is_admin": True, "first_name": admin_user.get('first_name'), "last_name": admin_user.get('last_name')}
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            user_info_to_return = {"id": admin_user['id'], "email": admin_user['email'], "prenom": admin_user.get('first_name'), "nom": admin_user.get('last_name'), "role": admin_user['role'], "is_admin": True}
            return jsonify(success=True, message="Admin login successful!", token=access_token, user=user_info_to_return), 200
        else:
            return jsonify(message="Invalid admin email or password", success=False), 401
    except Exception as e:
        current_app.logger.error(f"Error during admin login for {email}: {e}", exc_info=True)
        return jsonify(message="Admin login failed due to a server error", success=False), 500

@admin_api_bp.route('/dashboard/stats', methods=['GET'])
@admin_required
def get_dashboard_stats():
    db = get_db_connection(); audit_logger = current_app.audit_log_service; current_admin_id = get_jwt_identity()
    try:
        total_users_row = query_db("SELECT COUNT(*) as count FROM users", db_conn=db, one=True)
        total_products_row = query_db("SELECT COUNT(*) as count FROM products WHERE is_active = TRUE", db_conn=db, one=True)
        pending_order_statuses = ('paid', 'processing', 'awaiting_shipment') 
        status_placeholders = ','.join(['?'] * len(pending_order_statuses))
        pending_orders_row = query_db(f"SELECT COUNT(*) as count FROM orders WHERE status IN ({status_placeholders})", pending_order_statuses, db_conn=db, one=True)
        total_categories_row = query_db("SELECT COUNT(*) as count FROM categories WHERE is_active = TRUE", db_conn=db, one=True)
        pending_b2b_applications_row = query_db("SELECT COUNT(*) as count FROM users WHERE role = 'b2b_professional' AND professional_status = 'pending'", db_conn=db, one=True)
        stats = {"total_users": total_users_row['count'] if total_users_row else 0, "total_products": total_products_row['count'] if total_products_row else 0, "pending_orders": pending_orders_row['count'] if pending_orders_row else 0, "total_categories": total_categories_row['count'] if total_categories_row else 0, "pending_b2b_applications": pending_b2b_applications_row['count'] if pending_b2b_applications_row else 0, "success": True}
        audit_logger.log_action(user_id=current_admin_id, action='get_dashboard_stats', status='success', ip_address=request.remote_addr)
        return jsonify(stats), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching dashboard stats: {e}", exc_info=True)
        return jsonify(message="Failed to fetch dashboard statistics", success=False), 500

@admin_api_bp.route('/categories', methods=['POST'])
@admin_required
def create_category():
    data = request.form.to_dict(); name = data.get('name'); description = data.get('description', ''); parent_id_str = data.get('parent_id')
    category_code = data.get('category_code', '').strip().upper(); image_file = request.files.get('image_url'); is_active = data.get('is_active', 'true').lower() == 'true'
    current_user_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    if not name or not category_code:
        return jsonify(message="Name and Category Code are required", success=False), 400
    slug = generate_slug(name); db = get_db_connection(); cursor = db.cursor(); image_filename_db = None 
    try:
        if query_db("SELECT id FROM categories WHERE name = ?", [name], db_conn=db, one=True): return jsonify(message=f"Category name '{name}' already exists", success=False), 409
        if query_db("SELECT id FROM categories WHERE slug = ?", [slug], db_conn=db, one=True): return jsonify(message=f"Category slug '{slug}' already exists. Try a different name.", success=False), 409
        if query_db("SELECT id FROM categories WHERE category_code = ?", [category_code], db_conn=db, one=True): return jsonify(message=f"Category code '{category_code}' already exists.", success=False), 409
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(f"category_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
            upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories'); os.makedirs(upload_folder_categories, exist_ok=True)
            image_file.save(os.path.join(upload_folder_categories, filename)); image_filename_db = os.path.join('categories', filename) 
        parent_id = int(parent_id_str) if parent_id_str and parent_id_str.strip() and parent_id_str.lower() != 'null' else None
        cursor.execute("INSERT INTO categories (name, description, parent_id, slug, image_url, category_code, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)", (name, description, parent_id, slug, image_filename_db, category_code, is_active))
        category_id = cursor.lastrowid; db.commit() 
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='create_category', target_type='category', target_id=category_id, details=f"Category '{name}' created.", status='success', ip_address=request.remote_addr)
        created_category = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        return jsonify(message="Category created successfully", category=dict(created_category) if created_category else {}, success=True), 201
    except sqlite3.IntegrityError: db.rollback(); return jsonify(message="Category name, slug, or code likely already exists (DB integrity).", success=False), 409
    except Exception as e: db.rollback(); return jsonify(message=f"Failed to create category: {str(e)}", success=False), 500

@admin_api_bp.route('/categories', methods=['GET'])
@admin_required
def get_categories():
    db = get_db_connection()
    try:
        categories_data = query_db("SELECT id, name, description, parent_id, slug, image_url, category_code, is_active, created_at, updated_at FROM categories ORDER BY name", db_conn=db)
        categories = [dict(row) for row in categories_data] if categories_data else []
        for category in categories:
            category['created_at'] = format_datetime_for_display(category['created_at']); category['updated_at'] = format_datetime_for_display(category['updated_at'])
            if category.get('image_url'): category['image_full_url'] = url_for('serve_public_asset', filepath=category['image_url'], _external=True)
        return jsonify(categories=categories, success=True), 200
    except Exception as e: return jsonify(message=f"Failed to fetch categories: {str(e)}", success=False), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['GET'])
@admin_required
def get_category_detail(category_id):
    db = get_db_connection()
    try:
        category_data = query_db("SELECT *, is_active FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if category_data:
            category = dict(category_data); category['created_at'] = format_datetime_for_display(category['created_at']); category['updated_at'] = format_datetime_for_display(category['updated_at'])
            if category.get('image_url'): category['image_full_url'] = url_for('serve_public_asset', filepath=category['image_url'], _external=True)
            return jsonify(category=category, success=True), 200
        return jsonify(message="Category not found", success=False), 404
    except Exception as e: return jsonify(message=f"Failed to fetch category details: {str(e)}", success=False), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['PUT'])
@admin_required
def update_category(category_id):
    data = request.form.to_dict(); name = data.get('name'); description = data.get('description'); parent_id_str = data.get('parent_id')
    category_code = data.get('category_code', '').strip().upper(); is_active_str = data.get('is_active'); image_file = request.files.get('image_url'); remove_image = data.get('remove_image') == 'true'
    current_user_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    if not name or not category_code: return jsonify(message="Name and Category Code are required for update", success=False), 400
    db = get_db_connection(); cursor = db.cursor() 
    try:
        current_category_row = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if not current_category_row: return jsonify(message="Category not found", success=False), 404
        current_category = dict(current_category_row)
        new_slug = generate_slug(name) if name != current_category['name'] else current_category['slug']
        if name != current_category['name'] and query_db("SELECT id FROM categories WHERE name = ? AND id != ?", [name, category_id], db_conn=db, one=True): return jsonify(message=f"Another category with the name '{name}' already exists", success=False), 409
        if new_slug != current_category['slug'] and query_db("SELECT id FROM categories WHERE slug = ? AND id != ?", [new_slug, category_id], db_conn=db, one=True): return jsonify(message=f"Another category with slug '{new_slug}' already exists. Try a different name.", success=False), 409
        if category_code != current_category.get('category_code') and query_db("SELECT id FROM categories WHERE category_code = ? AND id != ?", [category_code, category_id], db_conn=db, one=True): return jsonify(message=f"Another category with code '{category_code}' already exists.", success=False), 409
        upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories'); os.makedirs(upload_folder_categories, exist_ok=True)
        image_filename_to_update_db = current_category['image_url']
        if remove_image and current_category['image_url']:
            full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_category['image_url'])
            if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            image_filename_to_update_db = None
        elif image_file and allowed_file(image_file.filename):
            if current_category['image_url']:
                full_old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_category['image_url'])
                if os.path.exists(full_old_image_path): os.remove(full_old_image_path)
            filename = secure_filename(f"category_{new_slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
            image_file.save(os.path.join(upload_folder_categories, filename)); image_filename_to_update_db = os.path.join('categories', filename)
        parent_id_to_update = None
        if parent_id_str and parent_id_str.strip() and parent_id_str.lower() != 'null':
            try: parent_id_to_update = int(parent_id_str)
            except ValueError: return jsonify(message="Invalid parent ID format.", success=False), 400
            if parent_id_to_update == category_id: return jsonify(message="Category cannot be its own parent.", success=False), 400
        description_to_update = description if description is not None else current_category['description']
        is_active_to_update = is_active_str.lower() == 'true' if is_active_str is not None else current_category['is_active']
        cursor.execute("UPDATE categories SET name = ?, description = ?, parent_id = ?, slug = ?, image_url = ?, category_code = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (name, description_to_update, parent_id_to_update, new_slug, image_filename_to_update_db, category_code, is_active_to_update, category_id))
        db.commit() 
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='update_category', target_type='category', target_id=category_id, details=f"Category '{name}' updated.", status='success', ip_address=request.remote_addr)
        updated_category = query_db("SELECT * FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        return jsonify(message="Category updated successfully", category=dict(updated_category) if updated_category else {}, success=True), 200
    except sqlite3.IntegrityError: db.rollback(); return jsonify(message="Category name, slug, or code likely conflicts (DB integrity).", success=False), 409
    except Exception as e: db.rollback(); return jsonify(message=f"Failed to update category: {str(e)}", success=False), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    current_user_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor() 
    try:
        category_to_delete_row = query_db("SELECT image_url, name FROM categories WHERE id = ?", [category_id], db_conn=db, one=True)
        if not category_to_delete_row: return jsonify(message="Category not found", success=False), 404
        category_to_delete = dict(category_to_delete_row)
        products_in_category_row = query_db("SELECT COUNT(*) FROM products WHERE category_id = ?", [category_id], db_conn=db, one=True)
        if products_in_category_row and products_in_category_row[0] > 0: return jsonify(message=f"Category '{category_to_delete['name']}' in use. Reassign products first.", success=False), 409
        if category_to_delete['image_url']:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category_to_delete['image_url'])
            if os.path.exists(full_image_path): os.remove(full_image_path)
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,)); db.commit() 
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)
        if cursor.rowcount > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_category', target_type='category', target_id=category_id, details=f"Category '{category_to_delete['name']}' deleted.", status='success', ip_address=request.remote_addr)
            return jsonify(message=f"Category '{category_to_delete['name']}' deleted successfully", success=True), 200
        else: return jsonify(message="Category not found during delete operation", success=False), 404
    except sqlite3.IntegrityError: db.rollback(); return jsonify(message="Failed to delete category (DB integrity constraints).", success=False), 409
    except Exception as e: db.rollback(); return jsonify(message=f"Failed to delete category: {str(e)}", success=False), 500

# --- Product Management ---
@admin_api_bp.route('/products', methods=['POST'])
@admin_required
def create_product():
    current_user_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor()
    try:
        data = request.form.to_dict(); main_image_file = request.files.get('main_image_url')
        name = data.get('name'); product_code = data.get('product_code', '').strip().upper() # product_code is the main SKU
        product_type = data.get('type', 'simple'); description = data.get('description', '')
        category_id_str = data.get('category_id'); category_id = int(category_id_str) if category_id_str and category_id_str.isdigit() else None
        brand = data.get('brand', "Maison Trüvra"); base_price_str = data.get('price'); currency = data.get('currency', 'EUR')
        aggregate_stock_quantity_str = data.get('quantity', '0'); aggregate_stock_weight_grams_str = data.get('aggregate_stock_weight_grams')
        unit_of_measure = data.get('unit_of_measure'); is_active = data.get('is_active', 'true').lower() == 'true'
        is_featured = data.get('is_featured', 'false').lower() == 'true'; meta_title = data.get('meta_title', name)
        meta_description = data.get('meta_description', description[:160] if description else ''); slug = generate_slug(name)

        if not all([name, product_code, product_type, category_id is not None]):
            return jsonify(message="Name, Product Code, Type, and Category are required.", success=False), 400
        if query_db("SELECT id FROM products WHERE product_code = ?", [product_code], db_conn=db, one=True):
            return jsonify(message=f"Product Code '{product_code}' already exists.", success=False), 409
        if query_db("SELECT id FROM products WHERE slug = ?", [slug], db_conn=db, one=True):
            return jsonify(message=f"Product name (slug: '{slug}') already exists.", success=False), 409

        main_image_filename_db = None
        if main_image_file and allowed_file(main_image_file.filename):
            filename = secure_filename(f"product_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(main_image_file.filename)}")
            upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products'); os.makedirs(upload_folder_products, exist_ok=True)
            main_image_file.save(os.path.join(upload_folder_products, filename)); main_image_filename_db = os.path.join('products', filename)

        base_price = float(base_price_str) if base_price_str is not None and base_price_str != '' else None
        aggregate_stock_quantity = int(aggregate_stock_quantity_str) if aggregate_stock_quantity_str is not None and aggregate_stock_quantity_str != '' else 0
        aggregate_stock_weight_grams = float(aggregate_stock_weight_grams_str) if aggregate_stock_weight_grams_str else None

        if product_type == 'simple' and base_price is None:
            return jsonify(message="Base price (Price field) is required for simple products.", success=False), 400
        
        cursor.execute(
            """INSERT INTO products (name, description, category_id, product_code, brand, type, 
                                   base_price, currency, main_image_url, aggregate_stock_quantity, 
                                   aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured, 
                                   meta_title, meta_description, slug)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", # Removed sku_prefix placeholder
            (name, description, category_id, product_code, brand, product_type, # product_code used
             base_price, currency, main_image_filename_db, 
             aggregate_stock_quantity if product_type == 'simple' else 0, 
             aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured, 
             meta_title, meta_description, slug)
        )
        product_id = cursor.lastrowid
        if product_type == 'simple' and aggregate_stock_quantity > 0:
             record_stock_movement(db, product_id, 'initial_stock', quantity_change=aggregate_stock_quantity, reason="Initial stock for new simple product", related_user_id=current_user_id)
        db.commit() 
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='create_product', target_type='product', target_id=product_id, details=f"Product '{name}' (Code: {product_code}) created.", status='success', ip_address=request.remote_addr)
        created_product_data_row = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        response_data = {"message": "Product created successfully", "product_id": product_id, "slug": slug, "success": True}
        if created_product_data_row: response_data["product"] = dict(created_product_data_row)
        return jsonify(response_data), 201
    except (sqlite3.IntegrityError, ValueError) as e: db.rollback(); return jsonify(message=f"Failed to create product: {str(e)}", success=False), 400 if isinstance(e, ValueError) else 409
    except Exception as e: db.rollback(); return jsonify(message=f"Failed to create product: {str(e)}", success=False), 500

@admin_api_bp.route('/products', methods=['GET'])
@admin_required
def get_products_admin():
    db = get_db_connection(); include_variants_param = request.args.get('include_variants', 'false').lower() == 'true'
    try:
        products_data = query_db("SELECT p.*, c.name as category_name, c.category_code FROM products p LEFT JOIN categories c ON p.category_id = c.id ORDER BY p.name", db_conn=db)
        products = [dict(row) for row in products_data] if products_data else []
        for product in products:
            product['created_at'] = format_datetime_for_display(product['created_at']); product['updated_at'] = format_datetime_for_display(product['updated_at'])
            product['price'] = product.get('base_price'); product['quantity'] = product.get('aggregate_stock_quantity')
            if product.get('main_image_url'): product['main_image_full_url'] = url_for('serve_public_asset', filepath=product['main_image_url'], _external=True)
            if product['type'] == 'variable_weight' or include_variants_param:
                options_data = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product['id']], db_conn=db)
                product['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
                product['variant_count'] = len(product['weight_options'])
                if product['type'] == 'variable_weight' and product['weight_options']: product['quantity'] = sum(opt.get('aggregate_stock_quantity', 0) for opt in product['weight_options'])
            images_data = query_db("SELECT id, image_url, alt_text, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC", [product['id']], db_conn=db)
            product['additional_images'] = []
            if images_data:
                for img_row in images_data:
                    img_dict = dict(img_row)
                    if img_dict.get('image_url'): img_dict['image_full_url'] = url_for('serve_public_asset', filepath=img_dict['image_url'], _external=True)
                    product['additional_images'].append(img_dict)
        return jsonify(products=products, success=True), 200
    except Exception as e: return jsonify(message=f"Failed to fetch products for admin: {str(e)}", success=False), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['GET'])
@admin_required
def get_product_admin_detail(product_id):
    db = get_db_connection()
    try:
        product_data = query_db("SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.id = ?", [product_id], db_conn=db, one=True)
        if not product_data: return jsonify(message="Product not found", success=False), 404
        product = dict(product_data); product['created_at'] = format_datetime_for_display(product['created_at']); product['updated_at'] = format_datetime_for_display(product['updated_at'])
        if product.get('main_image_url'): product['main_image_full_url'] = url_for('serve_public_asset', filepath=product['main_image_url'], _external=True)
        if product['type'] == 'variable_weight':
            options_data = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product_id], db_conn=db)
            product['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
        images_data = query_db("SELECT id, image_url, alt_text, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC", [product_id], db_conn=db)
        product['additional_images'] = []
        if images_data:
            for img_row in images_data:
                img_dict = dict(img_row)
                if img_dict.get('image_url'): img_dict['image_full_url'] = url_for('serve_public_asset', filepath=img_dict['image_url'], _external=True)
                product['additional_images'].append(img_dict)
        assets_data = query_db("SELECT asset_type, file_path FROM generated_assets WHERE related_product_id = ?", [product_id], db_conn=db)
        product_assets = {}
        if assets_data:
            for asset_row in assets_data:
                asset_type_key = asset_row['asset_type'].lower().replace(' ', '_'); asset_full_url = None
                if asset_row.get('file_path'):
                    try:
                        if asset_row['asset_type'] == 'passport_html': asset_full_url = url_for('serve_public_asset', filepath=f"passports/{os.path.basename(asset_row['file_path'])}", _external=True)
                        else: asset_full_url = url_for('admin_api_bp.serve_asset', asset_relative_path=asset_row['file_path'], _external=True)
                    except Exception as e_asset_url: current_app.logger.warning(f"Could not generate URL for asset {asset_row['file_path']}: {e_asset_url}")
                product_assets[f"{asset_type_key}_url"] = asset_full_url; product_assets[f"{asset_type_key}_file_path"] = asset_row['file_path']
        product['assets'] = product_assets
        return jsonify(product=product, success=True), 200
    except Exception as e: return jsonify(message=f"Failed to fetch product details (admin): {str(e)}", success=False), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['PUT'])
@admin_required
def update_product(product_id):
    current_user_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor() 
    try:
        current_product_row = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not current_product_row: return jsonify(message="Product not found", success=False), 404
        current_product = dict(current_product_row)
        data = request.form.to_dict(); main_image_file = request.files.get('main_image_url'); remove_main_image = data.get('remove_main_image') == 'true'
        name = data.get('name', current_product['name']); new_slug = generate_slug(name) if name != current_product['name'] else current_product['slug']
        new_product_code = data.get('product_code', current_product['product_code']).strip().upper()
        if new_product_code != current_product['product_code'] and query_db("SELECT id FROM products WHERE product_code = ? AND id != ?", [new_product_code, product_id], db_conn=db, one=True):
            return jsonify(message=f"Product Code '{new_product_code}' already exists.", success=False), 409
        if new_slug != current_product['slug'] and query_db("SELECT id FROM products WHERE slug = ? AND id != ?", [new_slug, product_id], db_conn=db, one=True):
            return jsonify(message=f"Product name (slug: '{new_slug}') already exists.", success=False), 409
        upload_folder_products = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products'); os.makedirs(upload_folder_products, exist_ok=True)
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
            main_image_file.save(os.path.join(upload_folder_products, filename)); main_image_filename_db = os.path.join('products', filename)
        category_id_str = data.get('category_id'); category_id_to_update = current_product['category_id']
        if category_id_str: category_id_to_update = int(category_id_str) if category_id_str.isdigit() else None
        
        update_payload_product = {
            'name': name, 'slug': new_slug, 'product_code': new_product_code,
            'description': data.get('description', current_product['description']), 'category_id': category_id_to_update,
            'brand': data.get('brand', current_product['brand']), 'type': data.get('type', current_product['type']),
            'base_price': float(data['price']) if data.get('price') is not None and data.get('price') != '' else current_product['base_price'],
            'currency': data.get('currency', current_product['currency']), 'main_image_url': main_image_filename_db,
            'aggregate_stock_quantity': int(data.get('quantity', current_product['aggregate_stock_quantity'])),
            'aggregate_stock_weight_grams': float(data['aggregate_stock_weight_grams']) if data.get('aggregate_stock_weight_grams') is not None and data.get('aggregate_stock_weight_grams') != '' else current_product['aggregate_stock_weight_grams'],
            'unit_of_measure': data.get('unit_of_measure', current_product['unit_of_measure']),
            'is_active': data.get('is_active', str(current_product['is_active'])).lower() == 'true',
            'is_featured': data.get('is_featured', str(current_product['is_featured'])).lower() == 'true',
            'meta_title': data.get('meta_title', current_product['meta_title'] or name),
            'meta_description': data.get('meta_description', current_product['meta_description'] or data.get('description', '')[:160]),
        }
        if update_payload_product['type'] == 'simple' and update_payload_product['base_price'] is None:
            return jsonify(message="Base price (Price field) is required for simple products.", success=False), 400
        
        set_clause_product = ", ".join([f"{key} = ?" for key in update_payload_product.keys()])
        sql_args_product = list(update_payload_product.values()); sql_args_product.append(product_id)
        cursor.execute(f"UPDATE products SET {set_clause_product}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", tuple(sql_args_product))
        if current_product['type'] == 'variable_weight' and update_payload_product['type'] == 'simple':
            cursor.execute("DELETE FROM product_weight_options WHERE product_id = ?", (product_id,))
        db.commit() 
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='update_product', target_type='product', target_id=product_id, details=f"Product '{name}' (Code: {new_product_code}) updated.", status='success', ip_address=request.remote_addr)
        updated_product_data = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        return jsonify(message="Product updated successfully", product=dict(updated_product_data) if updated_product_data else {}, success=True), 200
    except (sqlite3.IntegrityError, ValueError) as e: db.rollback(); return jsonify(message=f"Failed to update product: {str(e)}", success=False), 400 if isinstance(e, ValueError) else 409
    except Exception as e: db.rollback(); return jsonify(message=f"Failed to update product: {str(e)}", success=False), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['DELETE'])
@admin_required
def delete_product(product_id):
    current_user_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor() 
    try:
        product_to_delete_row = query_db("SELECT name, main_image_url, product_code FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not product_to_delete_row: return jsonify(message="Product not found", success=False), 404
        product_to_delete = dict(product_to_delete_row)
        if product_to_delete['main_image_url']:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], product_to_delete['main_image_url'])
            if os.path.exists(full_image_path): os.remove(full_image_path)
        additional_images = query_db("SELECT image_url FROM product_images WHERE product_id = ?", [product_id], db_conn=db)
        if additional_images:
            for img in additional_images:
                full_add_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], img['image_url'])
                if os.path.exists(full_add_image_path): os.remove(full_add_image_path)
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,)); db.commit() 
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)
        if cursor.rowcount > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_product', target_type='product', target_id=product_id, details=f"Product '{product_to_delete['name']}' deleted.", status='success', ip_address=request.remote_addr)
            return jsonify(message=f"Product '{product_to_delete['name']}' deleted successfully", success=True), 200
        else: return jsonify(message="Product not found during delete operation", success=False), 404
    except sqlite3.IntegrityError: db.rollback(); return jsonify(message="Failed to delete product (DB integrity constraints).", success=False), 409
    except Exception as e: db.rollback(); return jsonify(message=f"Failed to delete product: {str(e)}", success=False), 500

# --- User Management ---
@admin_api_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    db = get_db_connection(); role_filter = request.args.get('role'); status_filter_str = request.args.get('is_active'); search_term = request.args.get('search')
    query_sql = "SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, professional_status, created_at FROM users"
    conditions = []; params = []
    if role_filter: conditions.append("role = ?"); params.append(role_filter)
    if status_filter_str is not None: is_active_val = status_filter_str.lower() == 'true'; conditions.append("is_active = ?"); params.append(is_active_val)
    if search_term:
        conditions.append("(email LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR company_name LIKE ? OR CAST(id AS TEXT) LIKE ?)")
        term = f"%{search_term}%"; params.extend([term, term, term, term, term])
    if conditions: query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY created_at DESC"
    try:
        users_data = query_db(query_sql, params, db_conn=db); users = [dict(row) for row in users_data] if users_data else []
        for user in users: user['created_at'] = format_datetime_for_display(user['created_at'])
        return jsonify(users=users, success=True), 200
    except Exception as e: return jsonify(message=f"Failed to fetch users: {str(e)}", success=False), 500

@admin_api_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user_admin_detail(user_id):
    db = get_db_connection()
    try:
        user_data = query_db("SELECT id, email, first_name, last_name, role, is_active, is_verified, company_name, vat_number, siret_number, professional_status, created_at, updated_at FROM users WHERE id = ?", [user_id], db_conn=db, one=True)
        if not user_data: return jsonify(message="User not found", success=False), 404
        user = dict(user_data); user['created_at'] = format_datetime_for_display(user['created_at']); user['updated_at'] = format_datetime_for_display(user['updated_at'])
        orders_data = query_db("SELECT id as order_id, order_date, total_amount, status FROM orders WHERE user_id = ? ORDER BY order_date DESC", [user_id], db_conn=db)
        user['orders'] = [dict(row) for row in orders_data] if orders_data else []
        for order_item in user['orders']: order_item['order_date'] = format_datetime_for_display(order_item['order_date'])
        return jsonify(user=user, success=True), 200
    except Exception as e: return jsonify(message=f"Failed to fetch user details (admin): {str(e)}", success=False), 500

@admin_api_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user_admin(user_id):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor(); data = request.json
    if not data: return jsonify(message="No data provided", success=False), 400
    allowed_fields = ['first_name', 'last_name', 'role', 'is_active', 'is_verified', 'company_name', 'vat_number', 'siret_number', 'professional_status']
    update_payload = {k: data[k] for k in data if k in allowed_fields}
    if not update_payload: return jsonify(message="No valid fields to update", success=False), 400
    if 'is_active' in update_payload: update_payload['is_active'] = str(update_payload['is_active']).lower() == 'true'
    if 'is_verified' in update_payload: update_payload['is_verified'] = str(update_payload['is_verified']).lower() == 'true'
    set_clause = ", ".join([f"{key} = ?" for key in update_payload.keys()]); sql_args = list(update_payload.values()); sql_args.append(user_id)
    try:
        if not query_db("SELECT id FROM users WHERE id = ?", [user_id], db_conn=db, one=True): return jsonify(message="User not found", success=False), 404
        cursor.execute(f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", tuple(sql_args)); db.commit() 
        if cursor.rowcount == 0: return jsonify(message="User not found or no changes made", success=False), 404
        audit_logger.log_action(user_id=current_admin_id, action='update_user_admin', target_type='user', target_id=user_id, details=f"User {user_id} updated. Fields: {', '.join(update_payload.keys())}", status='success', ip_address=request.remote_addr)
        return jsonify(message="User updated successfully", success=True), 200
    except sqlite3.Error as e: db.rollback(); return jsonify(message="Failed to update user due to DB error", success=False), 500
    except Exception as e: db.rollback(); return jsonify(message=f"Failed to update user: {str(e)}", success=False), 500

# --- Order Management ---
@admin_api_bp.route('/orders', methods=['GET'])
@admin_required
def get_orders_admin():
    db = get_db_connection(); search_filter = request.args.get('search'); status_filter = request.args.get('status'); date_filter_str = request.args.get('date')
    query_sql = "SELECT o.id as order_id, o.user_id, o.order_date, o.status, o.total_amount, o.currency, u.email as customer_email, (u.first_name || ' ' || u.last_name) as customer_name FROM orders o LEFT JOIN users u ON o.user_id = u.id"
    conditions = []; params = []
    if search_filter: conditions.append("(CAST(o.id AS TEXT) LIKE ? OR u.email LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ? OR o.payment_transaction_id LIKE ?)"); term = f"%{search_filter}%"; params.extend([term, term, term, term, term])
    if status_filter: conditions.append("o.status = ?"); params.append(status_filter)
    if date_filter_str: 
        try: datetime.strptime(date_filter_str, '%Y-%m-%d'); conditions.append("DATE(o.order_date) = ?"); params.append(date_filter_str)
        except ValueError: return jsonify(message="Invalid date format. Use YYYY-MM-DD.", success=False), 400
    if conditions: query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY o.order_date DESC"
    try:
        orders_data = query_db(query_sql, params, db_conn=db); orders = [dict(row) for row in orders_data] if orders_data else []
        for order in orders: order['order_date'] = format_datetime_for_display(order['order_date'])
        return jsonify(orders=orders, success=True), 200
    except Exception as e: return jsonify(message=f"Failed to fetch orders: {str(e)}", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>', methods=['GET'])
@admin_required
def get_order_admin_detail(order_id):
    db = get_db_connection()
    try:
        order_data_row = query_db("SELECT o.*, u.email as customer_email, (u.first_name || ' ' || u.last_name) as customer_name FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.id = ?", [order_id], db_conn=db, one=True)
        if not order_data_row: return jsonify(message="Order not found", success=False), 404
        order = dict(order_data_row)
        for dt_field in ['order_date', 'created_at', 'updated_at']: order[dt_field] = format_datetime_for_display(order[dt_field])
        items_data = query_db("SELECT oi.*, p.main_image_url as product_image_url FROM order_items oi LEFT JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?", [order_id], db_conn=db)
        order['items'] = []
        if items_data:
            for item_row in items_data:
                item_dict = dict(item_row)
                if item_dict.get('product_image_url'): item_dict['product_image_full_url'] = url_for('serve_public_asset', filepath=item_dict['product_image_url'], _external=True)
                order['items'].append(item_dict)
        return jsonify(order=order, success=True), 200
    except Exception as e: return jsonify(message=f"Failed to fetch order details: {str(e)}", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@admin_required
def update_order_status_admin(order_id):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor(); data = request.json
    new_status = data.get('status'); tracking_number = data.get('tracking_number'); carrier = data.get('carrier')
    if not new_status: return jsonify(message="New status not provided", success=False), 400
    allowed = ['pending_payment', 'paid', 'processing', 'awaiting_shipment', 'shipped', 'delivered', 'completed', 'cancelled', 'refunded', 'on_hold', 'failed']
    if new_status not in allowed: return jsonify(message=f"Invalid status. Allowed: {', '.join(allowed)}", success=False), 400
    try:
        order_info = query_db("SELECT status FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)
        if not order_info: return jsonify(message="Order not found", success=False), 404
        updates = {"status": new_status}; old_status = order_info['status']
        if new_status in ['shipped', 'delivered']:
            if tracking_number: updates["tracking_number"] = tracking_number
            if carrier: updates["shipping_method"] = carrier
        set_parts = [f"{k} = ?" for k in updates] + ["updated_at = CURRENT_TIMESTAMP"]
        params = list(updates.values()) + [order_id]
        cursor.execute(f"UPDATE orders SET {', '.join(set_parts)} WHERE id = ?", tuple(params)); db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_order_status_admin', target_type='order', target_id=order_id, details=f"Order {order_id} status from '{old_status}' to '{new_status}'. Tracking: {tracking_number or 'N/A'}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Order status updated to {new_status}", success=True), 200
    except Exception as e:
        db.rollback(); audit_logger.log_action(user_id=current_admin_id, action='update_order_status_admin_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update order status: {str(e)}", success=False), 500

@admin_api_bp.route('/orders/<int:order_id>/notes', methods=['POST'])
@admin_required
def add_order_note_admin(order_id):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor(); data = request.json
    note_content = data.get('note')
    if not note_content or not note_content.strip(): return jsonify(message="Note content cannot be empty.", success=False), 400
    try:
        if not query_db("SELECT id FROM orders WHERE id = ?", [order_id], db_conn=db, one=True): return jsonify(message="Order not found", success=False), 404
        current_notes = query_db("SELECT notes_internal FROM orders WHERE id = ?", [order_id], db_conn=db, one=True)['notes_internal'] or ""
        admin_info = query_db("SELECT email FROM users WHERE id = ?", [current_admin_id], db_conn=db, one=True)
        admin_id_str = admin_info['email'] if admin_info else f"AdminID:{current_admin_id}"
        new_entry = f"[{format_datetime_for_display(None)} by {admin_id_str}]: {note_content}"
        updated_notes = f"{current_notes}\n{new_entry}".strip()
        cursor.execute("UPDATE orders SET notes_internal = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (updated_notes, order_id)); db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='add_order_note_admin', target_type='order', target_id=order_id, details=f"Added note: '{note_content[:50]}...'", status='success', ip_address=request.remote_addr)
        return jsonify(message="Note added successfully.", new_note_entry=new_entry, success=True), 201
    except Exception as e:
        db.rollback(); audit_logger.log_action(user_id=current_admin_id, action='add_order_note_admin_fail', target_type='order', target_id=order_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to add note: {str(e)}", success=False), 500

# --- Review Management ---
@admin_api_bp.route('/reviews', methods=['GET'])
@admin_required
def get_reviews_admin():
    db = get_db_connection(); status_filter = request.args.get('status') 
    product_filter = request.args.get('product_id'); user_filter = request.args.get('user_id')
    query = "SELECT r.*, p.name as product_name, p.product_code, u.email as user_email FROM reviews r JOIN products p ON r.product_id = p.id JOIN users u ON r.user_id = u.id"
    conditions = []; params = []
    if status_filter == 'pending': conditions.append("r.is_approved = FALSE")
    elif status_filter == 'approved': conditions.append("r.is_approved = TRUE")
    if product_filter:
        if product_filter.isdigit(): conditions.append("r.product_id = ?"); params.append(int(product_filter))
        else: conditions.append("(p.name LIKE ? OR p.product_code LIKE ?)"); params.extend([f"%{product_filter}%", f"%{product_filter}%"])
    if user_filter:
        if user_filter.isdigit(): conditions.append("r.user_id = ?"); params.append(int(user_filter))
        else: conditions.append("u.email LIKE ?"); params.append(f"%{user_filter}%")
    if conditions: query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY r.review_date DESC"
    try:
        reviews_data = query_db(query, params, db_conn=db)
        reviews = [dict(r) for r in reviews_data] if reviews_data else []
        for rev in reviews: rev['review_date'] = format_datetime_for_display(rev['review_date'])
        return jsonify(reviews=reviews, success=True), 200
    except Exception as e: return jsonify(message=f"Failed to fetch reviews: {str(e)}", success=False), 500

@admin_api_bp.route('/reviews/<int:review_id>/approve', methods=['PUT'])
@admin_required
def approve_review_admin(review_id): return _update_review_approval_admin(review_id, True)

@admin_api_bp.route('/reviews/<int:review_id>/unapprove', methods=['PUT'])
@admin_required
def unapprove_review_admin(review_id): return _update_review_approval_admin(review_id, False)

def _update_review_approval_admin(review_id, is_approved_status):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor(); action = "approve" if is_approved_status else "unapprove"
    try:
        if not query_db("SELECT id FROM reviews WHERE id = ?", [review_id], db_conn=db, one=True): return jsonify(message="Review not found", success=False), 404
        cursor.execute("UPDATE reviews SET is_approved = ? WHERE id = ?", (is_approved_status, review_id)); db.commit()
        audit_logger.log_action(user_id=current_admin_id, action=f'{action}_review_admin', target_type='review', target_id=review_id, details=f"Review {review_id} set to {is_approved_status}.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Review {'approved' if is_approved_status else 'unapproved'} successfully", success=True), 200
    except Exception as e:
        db.rollback(); audit_logger.log_action(user_id=current_admin_id, action=f'{action}_review_admin_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to {action} review: {str(e)}", success=False), 500

@admin_api_bp.route('/reviews/<int:review_id>', methods=['DELETE'])
@admin_required
def delete_review_admin(review_id):
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor()
    try:
        if not query_db("SELECT id FROM reviews WHERE id = ?", [review_id], db_conn=db, one=True): return jsonify(message="Review not found", success=False), 404
        cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,)); db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin', target_type='review', target_id=review_id, details=f"Review {review_id} deleted.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Review deleted successfully", success=True), 200
    except Exception as e:
        db.rollback(); audit_logger.log_action(user_id=current_admin_id, action='delete_review_admin_fail', target_type='review', target_id=review_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to delete review: {str(e)}", success=False), 500

# --- Settings Management ---
@admin_api_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings_admin():
    db = get_db_connection()
    try:
        settings_data = query_db("SELECT key, value, description FROM settings", db_conn=db)
        settings = {row['key']: {'value': row['value'], 'description': row['description']} for row in settings_data} if settings_data else {}
        return jsonify(settings=settings, success=True), 200
    except Exception as e: return jsonify(message=f"Failed to fetch settings: {str(e)}", success=False), 500

@admin_api_bp.route('/settings', methods=['POST'])
@admin_required
def update_settings_admin():
    current_admin_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    db = get_db_connection(); cursor = db.cursor(); data = request.json
    if not data: return jsonify(message="No settings data provided", success=False), 400
    updated_keys = []
    try:
        for key, value_obj in data.items():
            value = value_obj.get('value') if isinstance(value_obj, dict) else value_obj
            if value is not None:
                cursor.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (key, str(value)))
                updated_keys.append(key)
        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin', target_type='application_settings', details=f"Settings updated: {', '.join(updated_keys)}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Settings updated successfully", updated_settings=updated_keys, success=True), 200
    except Exception as e:
        db.rollback(); audit_logger.log_action(user_id=current_admin_id, action='update_settings_admin_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to update settings: {str(e)}", success=False), 500

# --- Detailed Inventory View ---
@admin_api_bp.route('/inventory/items/detailed', methods=['GET'])
@admin_required
def get_detailed_inventory_items_admin():
    db = get_db_connection()
    try:
        sql_query = """
            SELECT p.name AS product_name, p.product_code,
                   pl_fr.name as product_name_fr, pl_en.name as product_name_en,
                   CASE WHEN pwo.id IS NOT NULL THEN p.name || ' - ' || pwo.weight_grams || 'g (' || pwo.sku_suffix || ')' ELSE NULL END AS variant_name,
                   sii.* FROM serialized_inventory_items sii
            JOIN products p ON sii.product_id = p.id
            LEFT JOIN product_localizations pl_fr ON p.id = pl_fr.product_id AND pl_fr.lang_code = 'fr'
            LEFT JOIN product_localizations pl_en ON p.id = pl_en.product_id AND pl_en.lang_code = 'en'
            LEFT JOIN product_weight_options pwo ON sii.variant_id = pwo.id
            ORDER BY p.name, sii.item_uid;
        """
        items_data = query_db(sql_query, db_conn=db)
        detailed_items = []
        if items_data:
            for row in items_data:
                item = dict(row)
                for dt_field in ['production_date', 'expiry_date', 'received_at', 'sold_at', 'updated_at']:
                    item[dt_field] = format_datetime_for_storage(item[dt_field]) if item.get(dt_field) else None
                if item.get('qr_code_url'): item['qr_code_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item['qr_code_url'], _external=True)
                if item.get('passport_url'): item['passport_full_url'] = url_for('serve_public_asset', filepath=f"passports/{os.path.basename(item['passport_url'])}", _external=True)
                if item.get('label_url'): item['label_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item['label_url'], _external=True)
                detailed_items.append(item)
        return jsonify(detailed_items), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching detailed inventory items for admin: {e}", exc_info=True)
        return jsonify([]), 500

# --- Admin Asset Serving ---
@admin_api_bp.route('/assets/<path:asset_relative_path>')
@admin_required 
def serve_asset(asset_relative_path):
    if ".." in asset_relative_path or asset_relative_path.startswith("/"):
        current_app.logger.warning(f"Directory traversal attempt for admin asset: {asset_relative_path}")
        return flask_abort(404)
    asset_type_map = {
        'qr_codes': current_app.config['QR_CODE_FOLDER'], 'labels': current_app.config['LABEL_FOLDER'],
        'invoices': current_app.config['INVOICE_PDF_PATH'], 'professional_documents': current_app.config['PROFESSIONAL_DOCS_UPLOAD_PATH'],
        'products': os.path.join(current_app.config['UPLOAD_FOLDER'], 'products'), # Added for product images
        'categories': os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories') # Added for category images
    }
    path_parts = asset_relative_path.split(os.sep, 1); asset_type_key = path_parts[0]; filename_in_type_folder = path_parts[1] if len(path_parts) > 1 else None
    if asset_type_key in asset_type_map and filename_in_type_folder:
        base_path = asset_type_map[asset_type_key]; full_path = os.path.join(base_path, filename_in_type_folder)
        if not os.path.realpath(full_path).startswith(os.path.realpath(base_path)):
            current_app.logger.error(f"Security violation: Attempt to access file outside designated admin asset directory. Requested: {full_path}, Base: {base_path}")
            return flask_abort(404)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            current_app.logger.debug(f"Serving admin asset: {filename_in_type_folder} from directory: {base_path}")
            return send_from_directory(base_path, filename_in_type_folder)
    current_app.logger.warning(f"Admin asset not found or path not recognized: {asset_relative_path}")
    return flask_abort(404)

# --- Regenerate Static JSON Files ---
@admin_api_bp.route('/regenerate-static-json', methods=['POST'])
@admin_required
def regenerate_static_json_endpoint():
    current_user_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    try:
        generate_static_json_files(); audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json', status='success', ip_address=request.remote_addr)
        return jsonify(message="Static JSON files regenerated successfully.", success=True), 200
    except Exception as e:
        current_app.logger.error(f"Failed to regenerate static JSON files via API: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to regenerate static JSON files: {str(e)}", success=False), 500
