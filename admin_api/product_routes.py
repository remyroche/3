# admin_api/product_routes.py
import os
import uuid
import sqlite3
from flask import request, jsonify, current_app, url_for
from flask_jwt_extended import get_jwt_identity
from werkzeug.utils import secure_filename

from . import admin_api_bp
from ..database import get_db_connection, query_db, record_stock_movement
from ..utils import (
    admin_required,
    format_datetime_for_display,
    generate_slug,
    allowed_file,
    get_file_extension,
    generate_static_json_files
)

@admin_api_bp.route('/products', methods=['POST'])
@admin_required
def create_product():
    """Creates a new product."""
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor()

    try:
        data = request.form.to_dict()
        main_image_file = request.files.get('main_image_url')

        name = data.get('name')
        product_code = data.get('product_code', '').strip().upper()
        sku_prefix = data.get('sku_prefix', product_code).strip().upper()
        product_type = data.get('type', 'simple')
        description = data.get('description', '')

        category_id_str = data.get('category_id')
        category_id = int(category_id_str) if category_id_str and category_id_str.isdigit() else None

        brand = data.get('brand', "Maison Trüvra")
        base_price_str = data.get('price')
        currency = data.get('currency', 'EUR')

        aggregate_stock_quantity_str = data.get('quantity', '0')
        aggregate_stock_weight_grams_str = data.get('aggregate_stock_weight_grams')
        unit_of_measure = data.get('unit_of_measure')

        is_active = data.get('is_active', 'true').lower() == 'true'
        is_featured = data.get('is_featured', 'false').lower() == 'true'

        meta_title = data.get('meta_title', name)
        meta_description = data.get('meta_description', description[:160] if description else '')
        slug = generate_slug(name)

        if not all([name, product_code, sku_prefix, product_type, category_id is not None]):
            return jsonify(message="Name, Product Code, SKU Prefix, Type, and Category are required.", success=False), 400

        if query_db("SELECT id FROM products WHERE product_code = ?", [product_code], db_conn=db, one=True):
            return jsonify(message=f"Product Code '{product_code}' already exists.", success=False), 409
        if sku_prefix != product_code and query_db("SELECT id FROM products WHERE sku_prefix = ?", [sku_prefix], db_conn=db, one=True):
             return jsonify(message=f"SKU Prefix '{sku_prefix}' already exists for another product.", success=False), 409
        if query_db("SELECT id FROM products WHERE slug = ?", [slug], db_conn=db, one=True):
            return jsonify(message=f"Product name (slug: '{slug}') already exists.", success=False), 409

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
            return jsonify(message="Base price (Price field) is required for simple products.", success=False), 400

        cursor.execute(
            """INSERT INTO products (name, description, category_id, product_code, brand, sku_prefix, type,
                                   base_price, currency, main_image_url, aggregate_stock_quantity,
                                   aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured,
                                   meta_title, meta_description, slug)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, description, category_id, product_code, brand, sku_prefix, product_type,
             base_price, currency, main_image_filename_db,
             aggregate_stock_quantity if product_type == 'simple' else 0,
             aggregate_stock_weight_grams, unit_of_measure, is_active, is_featured,
             meta_title, meta_description, slug)
        )
        product_id = cursor.lastrowid

        if product_type == 'simple' and aggregate_stock_quantity > 0:
             record_stock_movement(db, product_id, 'initial_stock', quantity_change=aggregate_stock_quantity, reason="Initial stock for new simple product", related_user_id=current_user_id)

        db.commit()

        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after product creation: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='create_product', target_type='product', target_id=product_id, details=f"Product '{name}' (Code: {product_code}) created.", status='success', ip_address=request.remote_addr)

        created_product_data_row = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        response_data = {"message": "Product created successfully", "product_id": product_id, "slug": slug, "success": True}
        if created_product_data_row:
            response_data["product"] = dict(created_product_data_row)
        return jsonify(response_data), 201

    except (sqlite3.IntegrityError, ValueError) as e:
        db.rollback()
        return jsonify(message=f"Failed to create product: {str(e)}", success=False), 400 if isinstance(e, ValueError) else 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error creating product: {e}", exc_info=True)
        return jsonify(message=f"Failed to create product: {str(e)}", success=False), 500


@admin_api_bp.route('/products', methods=['GET'])
@admin_required
def get_products_admin():
    """Retrieves a list of all products for the admin panel."""
    db = get_db_connection()
    include_variants_param = request.args.get('include_variants', 'false').lower() == 'true'
    try:
        products_data = query_db(
            """SELECT p.*, c.name as category_name, c.category_code
               FROM products p LEFT JOIN categories c ON p.category_id = c.id
               ORDER BY p.name""", db_conn=db
        )
        products = [dict(row) for row in products_data] if products_data else []
        for product in products:
            product['created_at'] = format_datetime_for_display(product['created_at'])
            product['updated_at'] = format_datetime_for_display(product['updated_at'])
            product['price'] = product.get('base_price')
            product['quantity'] = product.get('aggregate_stock_quantity')

            if product.get('main_image_url'):
                product['main_image_full_url'] = url_for('serve_public_asset', filepath=product['main_image_url'], _external=True)

            if product['type'] == 'variable_weight' or include_variants_param:
                options_data = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product['id']], db_conn=db)
                product['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
                product['variant_count'] = len(product['weight_options'])
                if product['type'] == 'variable_weight' and product['weight_options']:
                    product['quantity'] = sum(opt.get('aggregate_stock_quantity', 0) for opt in product['weight_options'])

            images_data = query_db("SELECT id, image_url, alt_text, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC", [product['id']], db_conn=db)
            product['additional_images'] = []
            if images_data:
                for img_row in images_data:
                    img_dict = dict(img_row)
                    if img_dict.get('image_url'):
                         img_dict['image_full_url'] = url_for('serve_public_asset', filepath=img_dict['image_url'], _external=True)
                    product['additional_images'].append(img_dict)
        return jsonify(products=products, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching products for admin: {e}", exc_info=True)
        return jsonify(message=f"Failed to fetch products for admin: {str(e)}", success=False), 500


@admin_api_bp.route('/products/<int:product_id>', methods=['GET'])
@admin_required
def get_product_admin_detail(product_id):
    """Retrieves detailed information for a single product."""
    db = get_db_connection()
    try:
        product_data = query_db("SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.id = ?", [product_id], db_conn=db, one=True)
        if not product_data:
            return jsonify(message="Product not found", success=False), 404

        product = dict(product_data)
        product['created_at'] = format_datetime_for_display(product['created_at'])
        product['updated_at'] = format_datetime_for_display(product['updated_at'])
        if product.get('main_image_url'):
            product['main_image_full_url'] = url_for('serve_public_asset', filepath=product['main_image_url'], _external=True)

        if product['type'] == 'variable_weight':
            options_data = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product_id], db_conn=db)
            product['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []

        images_data = query_db("SELECT id, image_url, alt_text, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC", [product_id], db_conn=db)
        product['additional_images'] = []
        if images_data:
            for img_row in images_data:
                img_dict = dict(img_row)
                if img_dict.get('image_url'):
                    img_dict['image_full_url'] = url_for('serve_public_asset', filepath=img_dict['image_url'], _external=True)
                product['additional_images'].append(img_dict)

        assets_data = query_db("SELECT asset_type, file_path FROM generated_assets WHERE related_product_id = ?", [product_id], db_conn=db)
        product_assets = {}
        if assets_data:
            for asset_row in assets_data:
                asset_type_key = asset_row['asset_type'].lower().replace(' ', '_')
                asset_full_url = None
                if asset_row.get('file_path'):
                    try:
                        if asset_row['asset_type'] == 'passport_html':
                            passport_filename = os.path.basename(asset_row['file_path'])
                            asset_full_url = url_for('serve_public_asset', filepath=f"passports/{passport_filename}", _external=True)
                        else:
                            asset_full_url = url_for('admin_api_bp.serve_asset', asset_relative_path=asset_row['file_path'], _external=True)
                    except Exception as e_asset_url:
                        current_app.logger.warning(f"Could not generate URL for asset {asset_row['file_path']}: {e_asset_url}")

                product_assets[f"{asset_type_key}_url"] = asset_full_url
                product_assets[f"{asset_type_key}_file_path"] = asset_row['file_path']
        product['assets'] = product_assets

        return jsonify(product=product, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching product detail (admin) for ID {product_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to fetch product details (admin): {str(e)}", success=False), 500


@admin_api_bp.route('/products/<int:product_id>', methods=['PUT'])
@admin_required
def update_product(product_id):
    """Updates an existing product."""
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor()

    try:
        current_product_row = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not current_product_row:
            return jsonify(message="Product not found", success=False), 404
        current_product = dict(current_product_row)

        data = request.form.to_dict()
        main_image_file = request.files.get('main_image_url')
        remove_main_image = data.get('remove_main_image') == 'true'

        name = data.get('name', current_product['name'])
        new_slug = generate_slug(name) if name != current_product['name'] else current_product['slug']

        new_product_code = data.get('product_code', current_product['product_code']).strip().upper()
        if new_product_code != current_product['product_code'] and query_db("SELECT id FROM products WHERE product_code = ? AND id != ?", [new_product_code, product_id], db_conn=db, one=True):
            return jsonify(message=f"Product Code '{new_product_code}' already exists.", success=False), 409

        new_sku_prefix = data.get('sku_prefix', current_product.get('sku_prefix') or new_product_code).strip().upper()
        if new_sku_prefix != current_product.get('sku_prefix') and query_db("SELECT id FROM products WHERE sku_prefix = ? AND id != ?", [new_sku_prefix, product_id], db_conn=db, one=True):
             return jsonify(message=f"SKU Prefix '{new_sku_prefix}' already exists for another product.", success=False), 409

        if new_slug != current_product['slug'] and query_db("SELECT id FROM products WHERE slug = ? AND id != ?", [new_slug, product_id], db_conn=db, one=True):
            return jsonify(message=f"Product name (slug: '{new_slug}') already exists.", success=False), 409

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

        category_id_str = data.get('category_id')
        category_id_to_update = int(category_id_str) if category_id_str and category_id_str.isdigit() else current_product['category_id']

        update_payload_product = {
            'name': name, 'slug': new_slug, 'product_code': new_product_code, 'sku_prefix': new_sku_prefix,
            'description': data.get('description', current_product['description']),
            'category_id': category_id_to_update,
            'brand': data.get('brand', current_product['brand']),
            'type': data.get('type', current_product['type']),
            'base_price': float(data['price']) if data.get('price') is not None and data.get('price') != '' else current_product['base_price'],
            'currency': data.get('currency', current_product['currency']),
            'main_image_url': main_image_filename_db,
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
        sql_args_product = list(update_payload_product.values()) + [product_id]

        cursor.execute(f"UPDATE products SET {set_clause_product}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", tuple(sql_args_product))

        if current_product['type'] == 'variable_weight' and update_payload_product['type'] == 'simple':
            cursor.execute("DELETE FROM product_weight_options WHERE product_id = ?", (product_id,))

        db.commit()

        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after product update: {e_gen}", exc_info=True)

        audit_logger.log_action(user_id=current_user_id, action='update_product', target_type='product', target_id=product_id, details=f"Product '{name}' (Code: {new_product_code}) updated.", status='success', ip_address=request.remote_addr)

        updated_product_data = query_db("SELECT * FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        return jsonify(message="Product updated successfully", product=dict(updated_product_data) if updated_product_data else {}, success=True), 200

    except (sqlite3.IntegrityError, ValueError) as e:
        db.rollback()
        return jsonify(message=f"Failed to update product: {str(e)}", success=False), 400 if isinstance(e, ValueError) else 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating product ID {product_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to update product: {str(e)}", success=False), 500


@admin_api_bp.route('/products/<int:product_id>', methods=['DELETE'])
@admin_required
def delete_product(product_id):
    """Deletes a product."""
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    db = get_db_connection()
    cursor = db.cursor()
    try:
        product_to_delete_row = query_db("SELECT name, main_image_url, product_code FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not product_to_delete_row:
            return jsonify(message="Product not found", success=False), 404
        product_to_delete = dict(product_to_delete_row)

        # Clean up main image
        if product_to_delete['main_image_url']:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], product_to_delete['main_image_url'])
            if os.path.exists(full_image_path): os.remove(full_image_path)

        # Clean up additional images
        additional_images = query_db("SELECT image_url FROM product_images WHERE product_id = ?", [product_id], db_conn=db)
        if additional_images:
            for img in additional_images:
                full_add_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], img['image_url'])
                if os.path.exists(full_add_image_path): os.remove(full_add_image_path)

        # The database should handle cascading deletes for related tables like product_images, product_weight_options, etc.
        # if the foreign keys are set up with ON DELETE CASCADE. If not, they must be deleted manually here.
        # Example (if cascade is not set):
        # cursor.execute("DELETE FROM product_weight_options WHERE product_id = ?", (product_id,))
        # cursor.execute("DELETE FROM product_images WHERE product_id = ?", (product_id,))

        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        db.commit()

        try:
            generate_static_json_files()
        except Exception as e_gen:
            current_app.logger.error(f"Failed to regenerate static JSON files after product deletion: {e_gen}", exc_info=True)

        if cursor.rowcount > 0:
            audit_logger.log_action(user_id=current_user_id, action='delete_product', target_type='product', target_id=product_id, details=f"Product '{product_to_delete['name']}' deleted.", status='success', ip_address=request.remote_addr)
            return jsonify(message=f"Product '{product_to_delete['name']}' deleted successfully", success=True), 200
        else:
            return jsonify(message="Product not found during delete operation", success=False), 404
    except sqlite3.IntegrityError as e:
        db.rollback()
        # This occurs if other tables (e.g., order_items) still reference this product and ON DELETE is RESTRICT.
        current_app.logger.warning(f"IntegrityError deleting product {product_id}: {e}", exc_info=True)
        return jsonify(message="Cannot delete product. It is referenced in orders or other records.", success=False), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error deleting product ID {product_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to delete product: {str(e)}", success=False), 500
