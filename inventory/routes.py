import os
import uuid
import sqlite3
import csv 
from io import StringIO 
from flask import request, jsonify, current_app, g, url_for, Response, send_from_directory, make_response 
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone 

from ..database import get_db_connection, query_db, record_stock_movement, get_product_id_from_code
from ..services.asset_service import (
    generate_qr_code_for_item, 
    generate_item_passport,
    generate_product_label_pdf 
)
from ..utils import admin_required, format_datetime_for_display, parse_datetime_from_iso, format_datetime_for_storage 
from . import inventory_bp 


@inventory_bp.route('/serialized/receive', methods=['POST'])
@admin_required
def receive_serialized_stock():
    data = request.json
    product_code_str = data.get('product_code') # Use product_code
    quantity_received_str = data.get('quantity_received')
    variant_sku_suffix = data.get('variant_sku_suffix') # SKU suffix for variant
    batch_number = data.get('batch_number')
    production_date_iso_str = data.get('production_date') 
    expiry_date_iso_str = data.get('expiry_date')     
    cost_price_str = data.get('cost_price')          
    notes = data.get('notes', '')
    actual_weight_grams_str = data.get('actual_weight_grams') 

    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not all([product_code_str, quantity_received_str]):
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail', details="Product Code and quantity are required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Product Code and quantity are required"), 400

    db = get_db_connection() # Get DB connection early
    product_id = get_product_id_from_code(product_code_str.upper(), db_conn=db)
    if not product_id:
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail', details=f"Product Code '{product_code_str}' not found.", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Product Code '{product_code_str}' not found."), 404
    
    variant_id = None
    if variant_sku_suffix:
        variant_info = query_db("SELECT id FROM product_weight_options WHERE product_id = ? AND sku_suffix = ?", [product_id, variant_sku_suffix.upper()], db_conn=db, one=True)
        if not variant_info:
            audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail', details=f"Variant SKU suffix '{variant_sku_suffix}' not found for product code '{product_code_str}'.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Variant SKU suffix '{variant_sku_suffix}' not found for product code '{product_code_str}'."), 400
        variant_id = variant_info['id']


    try:
        quantity_received = int(quantity_received_str)
        if quantity_received <= 0: raise ValueError("Quantity received must be positive.")
        cost_price = float(cost_price_str) if cost_price_str else None
        actual_weight_grams_item = float(actual_weight_grams_str) if actual_weight_grams_str else None
    except ValueError as ve:
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail', details=f"Invalid data type: {ve}", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Invalid data type: {ve}"), 400

    cursor = db.cursor()
    
    product_info_row = query_db(
        "SELECT p.id, p.name, p.sku_prefix, p.product_code, p.category_id, " 
        "p_lang.name_fr as product_name_fr, p_lang.name_en as product_name_en, " 
        "c_lang.name_fr as category_name_fr, c_lang.name_en as category_name_en, "
        "c_lang.species_fr, c_lang.species_en, c_lang.ingredients_fr, c_lang.ingredients_en " 
        "FROM products p "
        "LEFT JOIN product_localizations p_lang ON p.id = p_lang.product_id " 
        "LEFT JOIN categories cat ON p.category_id = cat.id "
        "LEFT JOIN category_localizations c_lang ON cat.id = c_lang.category_id "
        "WHERE p.id = ?", [product_id], db_conn=db, one=True # Use resolved product_id
    )

    if not product_info_row: # Should not happen if product_id was resolved
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail', target_type='product', target_id=product_id, details="Product details not found after ID resolution.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Product details could not be fetched."), 404
    
    product_info_dict = dict(product_info_row)
    product_sku_prefix = product_info_dict.get('sku_prefix') or product_info_dict['product_code'] # Fallback to product_code if no sku_prefix
    product_name_fr_for_assets = product_info_dict.get('product_name_fr', product_info_dict.get('name', 'Produit Inconnu'))
    product_name_en_for_assets = product_info_dict.get('product_name_en', product_info_dict.get('name', 'Unknown Product'))

    category_id_for_product = product_info_dict.get('category_id')
    category_info_for_passport = {"name_fr": "N/A", "name_en": "N/A", "species_fr": "N/A", "species_en": "N/A", "ingredients_fr": "N/A", "ingredients_en": "N/A"}
    if category_id_for_product:
        cat_details_row = query_db("SELECT name_fr, name_en, species_fr, species_en, ingredients_fr, ingredients_en FROM category_localizations WHERE category_id = ?", [category_id_for_product], db_conn=db, one=True)
        if cat_details_row:
            category_info_for_passport = dict(cat_details_row)
        else: 
            cat_base_name_row = query_db("SELECT name FROM categories WHERE id = ?", [category_id_for_product], db_conn=db, one=True)
            if cat_base_name_row:
                category_info_for_passport['name_fr'] = cat_base_name_row['name']
                category_info_for_passport['name_en'] = cat_base_name_row['name']

    production_date_db = format_datetime_for_storage(parse_datetime_from_iso(production_date_iso_str)) if production_date_iso_str else None
    expiry_date_db = format_datetime_for_storage(parse_datetime_from_iso(expiry_date_iso_str)) if expiry_date_iso_str else None
    
    processing_date_for_label_fr = datetime.now(timezone.utc).strftime('%d/%m/%Y')
    app_base_url = current_app.config.get('APP_BASE_URL', 'http://localhost:8000')

    generated_items_details = []

    try:
        for i in range(quantity_received):
            item_uid = f"{product_sku_prefix}-{uuid.uuid4().hex[:8].upper()}" 
            
            item_specific_data_for_passport = {
                "batch_number": batch_number,
                "production_date": production_date_iso_str, 
                "expiry_date": expiry_date_iso_str,
                "actual_weight_grams": actual_weight_grams_item 
            }
            passport_relative_path = generate_item_passport(
                item_uid, 
                product_info_dict, 
                category_info_for_passport, 
                item_specific_data_for_passport
            )
            if not passport_relative_path:
                raise Exception(f"Failed to generate passport for item {i+1}.")

            passport_url_for_qr = f"{app_base_url}/passport/{item_uid}" # Public facing URL
            qr_code_png_relative_path = generate_qr_code_for_item(item_uid, product_id, product_name_fr_for_assets, product_name_en_for_assets) 
            if not qr_code_png_relative_path:
                 raise Exception(f"Failed to generate passport QR code PNG for item {i+1}.")

            weight_for_label = actual_weight_grams_item
            if not weight_for_label and variant_id:
                variant_data_for_label = query_db("SELECT weight_grams FROM product_weight_options WHERE id = ?", [variant_id], db_conn=db, one=True)
                if variant_data_for_label: weight_for_label = variant_data_for_label['weight_grams']
            
            label_pdf_relative_path = generate_product_label_pdf(
                item_uid=item_uid,
                product_name_fr=product_name_fr_for_assets,
                product_name_en=product_name_en_for_assets,
                weight_grams=weight_for_label,
                processing_date_str=processing_date_for_label_fr,
                passport_url=passport_url_for_qr
            )
            if not label_pdf_relative_path:
                raise Exception(f"Failed to generate PDF label for item {i+1}.")

            cursor.execute(
                """INSERT INTO serialized_inventory_items 
                   (item_uid, product_id, variant_id, batch_number, production_date, expiry_date, 
                    cost_price, notes, status, qr_code_url, passport_url, label_url, actual_weight_grams)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_uid, product_id, variant_id, batch_number, production_date_db, expiry_date_db, 
                 cost_price, notes, 'available', qr_code_png_relative_path, passport_relative_path, label_pdf_relative_path,
                 actual_weight_grams_item)
            )
            serialized_item_id = cursor.lastrowid
            record_stock_movement(db, product_id, 'receive_serialized', quantity_change=1, variant_id=variant_id, serialized_item_id=serialized_item_id, reason="Initial stock receipt of serialized item", related_user_id=current_admin_id)
            
            generated_items_details.append({
                "item_uid": item_uid,
                "product_name": product_name_fr_for_assets, 
                "product_code": product_code_str.upper(),
                "qr_code_path": qr_code_png_relative_path,
                "passport_path": passport_relative_path,
                "label_pdf_path": label_pdf_relative_path
            })

        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_success', target_type='product', target_id=product_id, details=f"Received {quantity_received} items for product code {product_code_str}. UIDs: {', '.join([item['item_uid'] for item in generated_items_details])}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"{quantity_received} serialized items received successfully.", items=generated_items_details, success=True), 201

    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error receiving serialized stock for product code {product_code_str}: {e}", exc_info=True)
        
        asset_base = current_app.config['ASSET_STORAGE_PATH']
        for item_detail in generated_items_details:
            for key in ['qr_code_path', 'passport_path', 'label_pdf_path']:
                if item_detail.get(key):
                    try: os.remove(os.path.join(asset_base, item_detail[key]))
                    except OSError: pass 
            
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail_exception', target_type='product', target_id=product_id, details=f"Failed for product code {product_code_str}: {str(e)}. Rolled back. Assets cleaned if possible.", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to receive serialized stock: {str(e)}", success=False), 500

@inventory_bp.route('/export/serialized_items', methods=['GET'])
@admin_required
def export_serialized_items_csv():
    db = get_db_connection()
    audit_logger = current_app.audit_log_service
    current_admin_id = get_jwt_identity()

    try:
        query_sql = """
            SELECT 
                si.item_uid,
                p.product_code, -- Using product_code
                COALESCE(pl_fr.name, p.name) AS product_name_fr, 
                COALESCE(pl_en.name, p.name) AS product_name_en, 
                pwo.weight_grams AS variant_weight_grams,
                pwo.sku_suffix AS variant_sku_suffix,
                si.status,
                si.batch_number,
                si.production_date,
                si.expiry_date,
                si.received_at,
                si.sold_at,
                si.cost_price,
                si.actual_weight_grams,
                si.notes
            FROM serialized_inventory_items si
            JOIN products p ON si.product_id = p.id
            LEFT JOIN product_localizations pl_fr ON p.id = pl_fr.product_id AND pl_fr.lang_code = 'fr'
            LEFT JOIN product_localizations pl_en ON p.id = pl_en.product_id AND pl_en.lang_code = 'en'
            LEFT JOIN product_weight_options pwo ON si.variant_id = pwo.id
            ORDER BY p.product_code, si.item_uid;
        """
        items_data = query_db(query_sql, db_conn=db)

        if not items_data:
            audit_logger.log_action(user_id=current_admin_id, action='export_serialized_items_csv_nodata', details="No serialized items found to export.", status='success_nodata', ip_address=request.remote_addr)
            return jsonify(message="No serialized items found to export."), 404

        output = StringIO()
        writer = csv.writer(output)
        
        headers = ['Item UID', 'Product Code', 'Product Name (FR)', 'Product Name (EN)', 'Variant Weight (g)', 'Variant SKU Suffix', 'Status', 'Batch Number', 'Production Date', 'Expiry Date', 'Received At', 'Sold At', 'Cost Price', 'Actual Weight (g)', 'Notes']
        writer.writerow(headers)

        for item_row in items_data:
            item = dict(item_row)
            writer.writerow([ item.get('item_uid'), item.get('product_code'), item.get('product_name_fr'), item.get('product_name_en'), item.get('variant_weight_grams'), item.get('variant_sku_suffix'), item.get('status'), item.get('batch_number'), format_datetime_for_display(item.get('production_date'), fmt='%Y-%m-%d'), format_datetime_for_display(item.get('expiry_date'), fmt='%Y-%m-%d'), format_datetime_for_display(item.get('received_at')), format_datetime_for_display(item.get('sold_at')), item.get('cost_price'), item.get('actual_weight_grams'), item.get('notes') ])
        
        output.seek(0)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"maison_truvra_serialized_inventory_{timestamp}.csv"
        audit_logger.log_action(user_id=current_admin_id, action='export_serialized_items_csv_success', details=f"Exported {len(items_data)} items to CSV.", status='success', ip_address=request.remote_addr)
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={filename}"})
    except Exception as e:
        current_app.logger.error(f"Error exporting serialized items to CSV: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='export_serialized_items_csv_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to export serialized items."), 500

@inventory_bp.route('/import/serialized_items', methods=['POST'])
@admin_required
def import_serialized_items_csv():
    db = get_db_connection()
    audit_logger = current_app.audit_log_service
    current_admin_id = get_jwt_identity()

    if 'file' not in request.files:
        audit_logger.log_action(user_id=current_admin_id, action='import_serialized_csv_fail_nofile', details="No file part in request.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="No file part in request."), 400
    
    file = request.files['file']
    if file.filename == '':
        audit_logger.log_action(user_id=current_admin_id, action='import_serialized_csv_fail_no_filename', details="No selected file.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="No selected file."), 400

    if not file.filename.endswith('.csv'):
        audit_logger.log_action(user_id=current_admin_id, action='import_serialized_csv_fail_invalid_format', details="Invalid file format. Only CSV is allowed.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Invalid file format. Only CSV is allowed."), 400

    imported_count = 0
    updated_count = 0
    failed_rows = []
    processed_rows = 0

    try:
        stream = StringIO(file.stream.read().decode("UTF-8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        required_headers = ['Product Code', 'Status'] 
        
        if not all(header in csv_reader.fieldnames for header in required_headers):
            missing = [h for h in required_headers if h not in csv_reader.fieldnames]
            audit_logger.log_action(user_id=current_admin_id, action='import_serialized_csv_fail_missing_headers', details=f"Missing CSV headers: {', '.join(missing)}", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Missing required CSV headers: {', '.join(missing)}. Required: {', '.join(required_headers)}"), 400

        for row_num, row in enumerate(csv_reader, start=1):
            processed_rows += 1
            product_code = row.get('Product Code', '').strip().upper()
            item_uid_csv = row.get('Item UID', '').strip()
            variant_sku_suffix = row.get('Variant SKU Suffix', '').strip().upper()
            status = row.get('Status', 'available').strip()
            batch_number = row.get('Batch Number', '').strip()
            production_date_str = row.get('Production Date', '').strip()
            expiry_date_str = row.get('Expiry Date', '').strip()
            cost_price_str = row.get('Cost Price', '').strip()
            actual_weight_grams_str = row.get('Actual Weight (g)', '').strip()
            notes = row.get('Notes', '').strip()

            if not product_code:
                failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': 'Product Code is missing.'})
                continue

            product_info = query_db("SELECT id, sku_prefix FROM products WHERE product_code = ?", [product_code], db_conn=db, one=True)
            if not product_info:
                failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'product_code': product_code, 'error': 'Product Code not found.'})
                continue
            product_id = product_info['id']
            product_sku_prefix = product_info.get('sku_prefix') or product_code # Fallback

            variant_id = None
            if variant_sku_suffix:
                variant_info = query_db("SELECT id FROM product_weight_options WHERE product_id = ? AND sku_suffix = ?", [product_id, variant_sku_suffix], db_conn=db, one=True)
                if not variant_info:
                    failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'product_code': product_code, 'variant_sku': variant_sku_suffix, 'error': 'Variant SKU Suffix not found for this product.'})
                    continue
                variant_id = variant_info['id']

            try:
                production_date_db = format_datetime_for_storage(parse_datetime_from_iso(production_date_str)) if production_date_str else None
                expiry_date_db = format_datetime_for_storage(parse_datetime_from_iso(expiry_date_str)) if expiry_date_str else None
                cost_price = float(cost_price_str) if cost_price_str else None
                actual_weight_grams = float(actual_weight_grams_str) if actual_weight_grams_str else None
            except ValueError as ve:
                failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': f'Invalid data format: {ve}'})
                continue

            cursor = db.cursor()
            existing_item = None
            if item_uid_csv:
                existing_item = query_db("SELECT id FROM serialized_inventory_items WHERE item_uid = ?", [item_uid_csv], db_conn=db, one=True)

            if existing_item: 
                cursor.execute("""UPDATE serialized_inventory_items SET status = ?, batch_number = ?, production_date = ?, expiry_date = ?, 
                                  cost_price = ?, actual_weight_grams = ?, notes = ?, updated_at = CURRENT_TIMESTAMP, product_id = ?, variant_id = ?
                                  WHERE item_uid = ?""",
                               (status, batch_number, production_date_db, expiry_date_db, cost_price, actual_weight_grams, notes, product_id, variant_id, item_uid_csv))
                updated_count += 1
            else: 
                item_uid_to_insert = item_uid_csv if item_uid_csv else f"{product_sku_prefix}-{uuid.uuid4().hex[:8].upper()}"
                if not item_uid_csv: # If generated, check uniqueness
                    while query_db("SELECT id FROM serialized_inventory_items WHERE item_uid = ?", [item_uid_to_insert], db_conn=db, one=True):
                        item_uid_to_insert = f"{product_sku_prefix}-{uuid.uuid4().hex[:8].upper()}"

                cursor.execute("""INSERT INTO serialized_inventory_items 
                                  (item_uid, product_id, variant_id, status, batch_number, production_date, expiry_date, cost_price, actual_weight_grams, notes)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                               (item_uid_to_insert, product_id, variant_id, status, batch_number, production_date_db, expiry_date_db, cost_price, actual_weight_grams, notes))
                serialized_item_id = cursor.lastrowid
                record_stock_movement(db, product_id, 'import_csv_new', quantity_change=1, variant_id=variant_id, serialized_item_id=serialized_item_id, reason="CSV Import - New Item", related_user_id=current_admin_id)
                imported_count += 1
        
        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='import_serialized_csv_success', details=f"Imported: {imported_count}, Updated: {updated_count}, Failed: {len(failed_rows)} from {processed_rows} rows.", status='success', ip_address=request.remote_addr)
        return jsonify(message="CSV import processed.", imported=imported_count, updated=updated_count, failed_rows=failed_rows, total_processed=processed_rows, success=True), 200

    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error importing serialized items from CSV: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='import_serialized_csv_fail_exception', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to import CSV: {str(e)}"), 500

@inventory_bp.route('/labels/<path:filename>')
@admin_required 
def serve_label_pdf(filename):
    label_dir = os.path.join(current_app.config['ASSET_STORAGE_PATH'], 'labels')
    return send_from_directory(label_dir, filename, as_attachment=False)

@inventory_bp.route('/passports/<path:filename>') 
@admin_required 
def serve_passport_html(filename):
    passport_dir = os.path.join(current_app.config['ASSET_STORAGE_PATH'], 'passports')
    return send_from_directory(passport_dir, filename)


@inventory_bp.route('/stock/adjust', methods=['POST'])
@admin_required
def adjust_stock():
    data = request.json
    product_code_str = data.get('product_code') # Use product_code
    variant_sku_suffix = data.get('variant_sku_suffix') # Use SKU suffix for variant
    adjustment_quantity_str = data.get('quantity_change')
    reason = data.get('notes') 
    movement_type = data.get('movement_type') 
    
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not product_code_str or not reason or not movement_type:
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail_missing_fields', details="Product Code, reason, and movement type are required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Product Code, reason, and movement type are required"), 400
    if adjustment_quantity_str is None: # Can be 0 for some types
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail_no_adjustment', target_type='product', target_id=product_code_str, details="Adjustment quantity must be provided.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Adjustment quantity must be provided"), 400

    db = get_db_connection()
    product_id = get_product_id_from_code(product_code_str.upper(), db_conn=db)
    if not product_id:
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail_invalid_product', target_type='product', target_id=product_code_str, details=f"Product code '{product_code_str}' not found.", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Product code '{product_code_str}' not found."), 404

    variant_id = None
    if variant_sku_suffix:
        variant_info = query_db("SELECT id FROM product_weight_options WHERE product_id = ? AND sku_suffix = ?", [product_id, variant_sku_suffix.upper()], db_conn=db, one=True)
        if not variant_info:
            audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail_invalid_variant', target_type='product', target_id=product_id, details=f"Variant SKU '{variant_sku_suffix}' not found for product.", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Variant SKU '{variant_sku_suffix}' not found for this product."), 400
        variant_id = variant_info['id']
        
    cursor = db.cursor() 
    try:
        adjustment_quantity = int(adjustment_quantity_str) 
        
        allowed_movement_types = ['ajustement_manuel', 'correction', 'perte', 'retour_non_commande', 'addition', 'creation_lot', 'decouverte_stock', 'retour_client']
        if movement_type not in allowed_movement_types:
            audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail_invalid_type', target_type='product', target_id=product_id, details=f"Invalid movement type: {movement_type}", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Invalid movement type: {movement_type}"),400
        
        # Update aggregate stock. This logic assumes non-serialized adjustments.
        # For serialized items, status changes are preferred.
        if variant_id:
            if adjustment_quantity != 0:
                cursor.execute("UPDATE product_weight_options SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", (adjustment_quantity, variant_id))
        else: # Simple product
            if adjustment_quantity != 0:
                cursor.execute("UPDATE products SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", (adjustment_quantity, product_id))

        record_stock_movement(db, product_id, movement_type, quantity_change=adjustment_quantity, variant_id=variant_id, reason=reason, related_user_id=current_admin_id, notes=reason)
        
        db.commit() 
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_success', target_type='product', target_id=product_id, details=f"Stock for product code {product_code_str} (variant SKU {variant_sku_suffix or 'N/A'}) adjusted by Qty: {adjustment_quantity}. Reason: {reason}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Stock adjusted successfully", success=True), 200

    except ValueError as ve:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail_value_error', target_type='product', target_id=product_code_str, details=f"Invalid data type: {ve}", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Invalid data type: {ve}", success=False), 400
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error adjusting stock for product code {product_code_str}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail_exception', target_type='product', target_id=product_code_str, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to adjust stock", success=False), 500

@inventory_bp.route('/product/<string:product_code>', methods=['GET']) # Use product_code
@admin_required
def get_admin_product_inventory_details(product_code):
    db = get_db_connection()
    variant_sku_filter = request.args.get('variant_sku_suffix') # Filter by SKU suffix

    product_id = get_product_id_from_code(product_code.upper(), db_conn=db)
    if not product_id:
        return jsonify(message="Product not found"), 404

    try:
        product_info_row = query_db("SELECT id, name, product_code, type, aggregate_stock_quantity, aggregate_stock_weight_grams FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not product_info_row: # Should be caught by product_id check earlier
            return jsonify(message="Product not found"), 404
        product_info = dict(product_info_row)

        inventory_details = product_info
        variant_id_internal_filter = None
        
        if product_info['type'] == 'variable_weight':
            options_data = query_db("SELECT id as option_id, weight_grams, sku_suffix, aggregate_stock_quantity FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product_id], db_conn=db)
            inventory_details['current_stock_by_variant'] = [dict(opt) for opt in options_data] if options_data else []
            inventory_details['calculated_total_variant_stock'] = sum(v.get('aggregate_stock_quantity',0) for v in inventory_details['current_stock_by_variant'])
            if variant_sku_filter:
                matched_variant = next((v for v in inventory_details['current_stock_by_variant'] if v['sku_suffix'].upper() == variant_sku_filter.upper()), None)
                if matched_variant: variant_id_internal_filter = matched_variant['option_id']


        movements_query = "SELECT * FROM stock_movements WHERE product_id = ?"
        movements_params = [product_id]
        if variant_id_internal_filter: # Filter movements by resolved variant_id
            movements_query += " AND variant_id = ?"
            movements_params.append(variant_id_internal_filter)
        elif variant_sku_filter and not variant_id_internal_filter: # SKU provided but no match found, so no movements for it
             inventory_details['stock_movements_log'] = []
        
        if not (variant_sku_filter and not variant_id_internal_filter): # Only query if we have a valid target or no variant filter
            movements_query += " ORDER BY movement_date DESC LIMIT 100" 
            movements_data = query_db(movements_query, movements_params, db_conn=db)
            inventory_details['stock_movements_log'] = []
            if movements_data:
                for m_log_row in movements_data:
                    m_log_dict = dict(m_log_row)
                    m_log_dict['movement_date'] = format_datetime_for_display(m_log_dict['movement_date'])
                    inventory_details['stock_movements_log'].append(m_log_dict)

        return jsonify(inventory_details), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin inventory details for product code {product_code}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch inventory details"), 500

@inventory_bp.route('/serialized/items', methods=['GET']) # This is the detailed list for admin_view_inventory.html
@admin_required
def get_serialized_items_admin_view(): # Renamed to avoid confusion
    db = get_db_connection()
    product_code_filter = request.args.get('product_code') # Filter by product_code
    status_filter = request.args.get('status')
    item_uid_search = request.args.get('item_uid')

    query_sql = """
        SELECT si.*, p.name as product_name, p.product_code, p.sku_prefix, 
               pwo.sku_suffix as variant_sku_suffix, pwo.weight_grams as variant_weight_grams
        FROM serialized_inventory_items si
        JOIN products p ON si.product_id = p.id
        LEFT JOIN product_weight_options pwo ON si.variant_id = pwo.id
    """
    conditions = []
    params = []

    if product_code_filter:
        product_id_internal = get_product_id_from_code(product_code_filter.upper(), db_conn=db)
        if product_id_internal:
            conditions.append("si.product_id = ?")
            params.append(product_id_internal)
        else: # Product code not found, return empty
            return jsonify([]), 200 
            
    if status_filter:
        conditions.append("si.status = ?")
        params.append(status_filter)
    if item_uid_search:
        conditions.append("si.item_uid LIKE ?")
        params.append(f"%{item_uid_search}%")
    
    if conditions: query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY si.received_at DESC, si.id DESC LIMIT 100"

    try:
        items_data = query_db(query_sql, params, db_conn=db)
        items = [dict(row) for row in items_data] if items_data else []
        for item in items:
            item['production_date'] = format_datetime_for_display(item['production_date'])
            item['expiry_date'] = format_datetime_for_display(item['expiry_date'])
            item['received_at'] = format_datetime_for_display(item['received_at'])
            item['sold_at'] = format_datetime_for_display(item['sold_at'])
            item['updated_at'] = format_datetime_for_display(item['updated_at'])
            if item.get('qr_code_url'):
                try:
                    item['qr_code_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item['qr_code_url'], _external=True)
                except Exception as e_qr_url:
                    current_app.logger.warning(f"Could not generate URL for QR code {item['qr_code_url']}: {e_qr_url}")
                    item['qr_code_full_url'] = None
            if item.get('passport_url'):
                try:
                    passport_filename = os.path.basename(item['passport_url'])
                    item['passport_full_url'] = url_for('serve_passport_public', filename=passport_filename, _external=True)
                except Exception as e_pass_url:
                    current_app.logger.warning(f"Could not generate URL for passport {item['passport_url']}: {e_pass_url}")
                    item['passport_full_url'] = None
            if item.get('label_url'):
                try:
                    item['label_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item['label_url'], _external=True)
                except Exception as e_label_url:
                    current_app.logger.warning(f"Could not generate URL for label {item['label_url']}: {e_label_url}")
                    item['label_full_url'] = None
        return jsonify(items), 200 # Return array directly
    except Exception as e:
        current_app.logger.error(f"Error fetching serialized items: {e}", exc_info=True)
        return jsonify(message="Failed to fetch serialized items"), 500


@inventory_bp.route('/serialized/items/<string:item_uid>/status', methods=['PUT'])
@admin_required
def update_serialized_item_status(item_uid):
    data = request.json
    new_status = data.get('status')
    notes = data.get('notes', '') 

    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not new_status:
        audit_logger.log_action(user_id=current_admin_id, action='update_item_status_fail_no_status', target_type='serialized_item', target_id=item_uid, details="New status required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="New status is required"), 400
    
    allowed_manual_statuses = ['available', 'damaged', 'recalled', 'reserved_internal', 'missing'] 
    if new_status not in allowed_manual_statuses:
        audit_logger.log_action(user_id=current_admin_id, action='update_item_status_fail_invalid_status', target_type='serialized_item', target_id=item_uid, details=f"Invalid status '{new_status}'.", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Invalid status '{new_status}'. Allowed: {', '.join(allowed_manual_statuses)}"), 400

    db = get_db_connection()
    cursor = db.cursor() 
    try:
        item_info_row = query_db("SELECT id, product_id, variant_id, status, notes as current_notes FROM serialized_inventory_items WHERE item_uid = ?", [item_uid], db_conn=db, one=True)
        if not item_info_row:
            audit_logger.log_action(user_id=current_admin_id, action='update_item_status_fail_not_found', target_type='serialized_item', target_id=item_uid, details="Item not found.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Serialized item not found"), 404
        item_info = dict(item_info_row)
        old_status = item_info['status']

        if old_status == new_status:
            return jsonify(message="Item status is already set to this value.", item_status=new_status, success=True), 200

        updated_notes_db = item_info.get('current_notes', '') or ''
        if notes: 
            timestamp_str = format_datetime_for_display(datetime.now(timezone.utc))
            updated_notes_db += f"\n[{timestamp_str} by AdminID:{current_admin_id}]: Status changed from {old_status} to {new_status}. Reason: {notes}"
        
        cursor.execute("UPDATE serialized_inventory_items SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE item_uid = ?", (new_status, updated_notes_db.strip(), item_uid))
        
        # Potentially adjust aggregate stock if moving to/from a countable status like 'available'
        product_id_internal = item_info['product_id']
        variant_id_internal = item_info['variant_id']
        quantity_change_for_aggregate = 0

        if old_status == 'available' and new_status != 'available':
            quantity_change_for_aggregate = -1
        elif old_status != 'available' and new_status == 'available':
            quantity_change_for_aggregate = 1
        
        if quantity_change_for_aggregate != 0:
            if variant_id_internal:
                cursor.execute("UPDATE product_weight_options SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", (quantity_change_for_aggregate, variant_id_internal))
            else: # Simple product
                cursor.execute("UPDATE products SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", (quantity_change_for_aggregate, product_id_internal))
            
            # Record a movement for the aggregate change if it makes sense for your model
            # For now, focusing on the serialized item status change audit.
            # record_stock_movement(db, product_id_internal, f"status_change_aggregate_{new_status}", quantity_change=quantity_change_for_aggregate, variant_id=variant_id_internal, serialized_item_id=item_info['id'], reason=f"Status change of item {item_uid}", related_user_id=current_admin_id)

        db.commit() 
        
        audit_logger.log_action(user_id=current_admin_id, action='update_item_status_success', target_type='serialized_item', target_id=item_uid, details=f"Status of {item_uid} from '{old_status}' to '{new_status}'. Notes: {notes}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Status of item {item_uid} updated to {new_status}.", success=True), 200
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating status for item {item_uid}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='update_item_status_fail_exception', target_type='serialized_item', target_id=item_uid, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update item status", success=False), 500