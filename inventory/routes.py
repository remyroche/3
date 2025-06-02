import os
import uuid
import sqlite3
import csv 
from io import StringIO 
from flask import request, jsonify, current_app, g, url_for, Response, send_from_directory, make_response, abort as flask_abort 
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
    product_code_str = data.get('product_code') 
    quantity_received_str = data.get('quantity_received')
    variant_sku_suffix = data.get('variant_sku_suffix') 
    batch_number = data.get('batch_number')
    production_date_iso_str = data.get('production_date') 
    expiry_date_iso_str = data.get('expiry_date')     
    cost_price_str = data.get('cost_price')          
    notes = data.get('notes', '')
    actual_weight_grams_str = data.get('actual_weight_grams') 

    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not all([product_code_str, quantity_received_str]):
        return jsonify(message="Product Code and quantity are required", success=False), 400

    db = get_db_connection()
    # Fetch product details including product_code which now serves as the SKU base
    product_row = query_db("SELECT id, name, product_code, category_id FROM products WHERE product_code = ?", [product_code_str.upper()], db_conn=db, one=True)
    if not product_row:
        return jsonify(message=f"Product Code '{product_code_str}' not found.", success=False), 404
    
    product_id = product_row['id']
    # Use product_code from DB as the definitive prefix for UIDs
    product_code_for_uid_prefix = product_row['product_code'] 
    product_name_for_assets = product_row['name'] 
    category_id_for_product = product_row.get('category_id')
    
    product_loc_fr = query_db("SELECT name_fr FROM product_localizations WHERE product_id = ? AND lang_code = 'fr'", [product_id], db_conn=db, one=True)
    product_loc_en = query_db("SELECT name_en FROM product_localizations WHERE product_id = ? AND lang_code = 'en'", [product_id], db_conn=db, one=True)
    product_name_fr_for_assets = product_loc_fr['name_fr'] if product_loc_fr else product_name_for_assets
    product_name_en_for_assets = product_loc_en['name_en'] if product_loc_en else product_name_for_assets

    variant_id = None
    if variant_sku_suffix:
        variant_info = query_db("SELECT id FROM product_weight_options WHERE product_id = ? AND sku_suffix = ?", [product_id, variant_sku_suffix.upper()], db_conn=db, one=True)
        if not variant_info:
            return jsonify(message=f"Variant SKU suffix '{variant_sku_suffix}' not found for product code '{product_code_str}'.", success=False), 400
        variant_id = variant_info['id']

    try:
        quantity_received = int(quantity_received_str)
        if quantity_received <= 0: raise ValueError("Quantity received must be positive.")
        cost_price = float(cost_price_str) if cost_price_str else None
        actual_weight_grams_item = float(actual_weight_grams_str) if actual_weight_grams_str else None
    except ValueError as ve:
        return jsonify(message=f"Invalid data type: {ve}", success=False), 400

    cursor = db.cursor()
    
    category_info_for_passport = {"name_fr": "N/A", "name_en": "N/A", "species_fr": "N/A", "species_en": "N/A", "ingredients_fr": "N/A", "ingredients_en": "N/A"}
    if category_id_for_product:
        cat_details_row = query_db("SELECT cl.name_fr, cl.name_en, cl.species_fr, cl.species_en, cl.ingredients_fr, cl.ingredients_en FROM category_localizations cl WHERE cl.category_id = ? UNION ALL SELECT c.name, c.name, NULL, NULL, NULL, NULL FROM categories c WHERE c.id = ? AND NOT EXISTS (SELECT 1 FROM category_localizations cl2 WHERE cl2.category_id = c.id) LIMIT 1", [category_id_for_product, category_id_for_product], db_conn=db, one=True)
        if cat_details_row: category_info_for_passport = dict(cat_details_row)

    production_date_db = format_datetime_for_storage(parse_datetime_from_iso(production_date_iso_str)) if production_date_iso_str else None
    expiry_date_db = format_datetime_for_storage(parse_datetime_from_iso(expiry_date_iso_str)) if expiry_date_iso_str else None
    processing_date_for_label_fr = datetime.now(timezone.utc).strftime('%d/%m/%Y')
    app_base_url = current_app.config.get('APP_BASE_URL', 'http://localhost:8000')

    generated_items_details = []
    try:
        for i in range(quantity_received):
            # Generate item_uid using product_code from DB
            item_uid = f"{product_code_for_uid_prefix}-{uuid.uuid4().hex[:8].upper()}" 
            
            item_specific_data_for_passport = {"batch_number": batch_number, "production_date": production_date_iso_str, "expiry_date": expiry_date_iso_str, "actual_weight_grams": actual_weight_grams_item}
            passport_relative_path = generate_item_passport(item_uid, product_row, category_info_for_passport, item_specific_data_for_passport)
            if not passport_relative_path: raise Exception(f"Failed to generate passport for item {i+1}.")

            passport_public_url = url_for('serve_public_asset', filepath=f"passports/{os.path.basename(passport_relative_path)}", _external=True)
            qr_code_png_relative_path = generate_qr_code_for_item(item_uid, product_id, product_name_fr_for_assets, product_name_en_for_assets)
            if not qr_code_png_relative_path: raise Exception(f"Failed to generate passport QR code PNG for item {i+1}.")

            weight_for_label = actual_weight_grams_item
            if not weight_for_label and variant_id:
                variant_data_for_label = query_db("SELECT weight_grams FROM product_weight_options WHERE id = ?", [variant_id], db_conn=db, one=True)
                if variant_data_for_label: weight_for_label = variant_data_for_label['weight_grams']
            
            label_pdf_relative_path = generate_product_label_pdf(item_uid=item_uid, product_name_fr=product_name_fr_for_assets, product_name_en=product_name_en_for_assets, weight_grams=weight_for_label, processing_date_str=processing_date_for_label_fr, passport_url=passport_public_url)
            if not label_pdf_relative_path: raise Exception(f"Failed to generate PDF label for item {i+1}.")

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
            record_stock_movement(db, product_id, 'receive_serialized', quantity_change=1, variant_id=variant_id, serialized_item_id=serialized_item_id, reason="Initial stock receipt", related_user_id=current_admin_id)
            
            generated_items_details.append({"item_uid": item_uid, "product_name": product_name_fr_for_assets, "product_code": product_code_str.upper(), "qr_code_path": qr_code_png_relative_path, "passport_path": passport_relative_path, "label_pdf_path": label_pdf_relative_path})
        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_success', target_type='product', target_id=product_id, details=f"Received {quantity_received} items for {product_code_str}.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"{quantity_received} items received.", items=generated_items_details, success=True), 201
    except Exception as e:
        db.rollback(); current_app.logger.error(f"Error receiving stock for {product_code_str}: {e}", exc_info=True)
        asset_base = current_app.config['ASSET_STORAGE_PATH']
        for item_detail in generated_items_details:
            for key in ['qr_code_path', 'passport_path', 'label_pdf_path']:
                if item_detail.get(key):
                    try: os.remove(os.path.join(asset_base, item_detail[key]))
                    except OSError: pass 
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail_exception', target_type='product', target_id=product_id, details=f"Failed for {product_code_str}: {str(e)}.", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to receive stock: {str(e)}", success=False), 500

@inventory_bp.route('/export/serialized_items', methods=['GET'])
@admin_required
def export_serialized_items_csv():
    db = get_db_connection(); audit_logger = current_app.audit_log_service; current_admin_id = get_jwt_identity()
    try:
        query_sql = """
            SELECT si.item_uid, p.product_code, COALESCE(pl_fr.name, p.name) AS product_name_fr, 
                   COALESCE(pl_en.name, p.name) AS product_name_en, pwo.weight_grams AS variant_weight_grams,
                   pwo.sku_suffix AS variant_sku_suffix, si.status, si.batch_number, si.production_date,
                   si.expiry_date, si.received_at, si.sold_at, si.cost_price, si.actual_weight_grams, si.notes
            FROM serialized_inventory_items si JOIN products p ON si.product_id = p.id
            LEFT JOIN product_localizations pl_fr ON p.id = pl_fr.product_id AND pl_fr.lang_code = 'fr'
            LEFT JOIN product_localizations pl_en ON p.id = pl_en.product_id AND pl_en.lang_code = 'en'
            LEFT JOIN product_weight_options pwo ON si.variant_id = pwo.id
            ORDER BY p.product_code, si.item_uid;
        """
        items_data = query_db(query_sql, db_conn=db)
        if not items_data:
            return jsonify(message="No serialized items found to export.", success=False), 404
        output = StringIO(); writer = csv.writer(output)
        headers = ['Item UID', 'Product Code', 'Product Name (FR)', 'Product Name (EN)', 'Variant Weight (g)', 'Variant SKU Suffix', 'Status', 'Batch Number', 'Production Date', 'Expiry Date', 'Received At', 'Sold At', 'Cost Price', 'Actual Weight (g)', 'Notes']
        writer.writerow(headers)
        for item_row in items_data:
            item = dict(item_row)
            # Ensure all keys are present, defaulting to empty string if not
            writer.writerow([
                item.get('item_uid', ''), item.get('product_code', ''), item.get('product_name_fr', ''), 
                item.get('product_name_en', ''), item.get('variant_weight_grams', ''), item.get('variant_sku_suffix', ''),
                item.get('status', ''), item.get('batch_number', ''),
                format_datetime_for_display(item.get('production_date'), fmt='%Y-%m-%d') if item.get('production_date') else '',
                format_datetime_for_display(item.get('expiry_date'), fmt='%Y-%m-%d') if item.get('expiry_date') else '',
                format_datetime_for_display(item.get('received_at')) if item.get('received_at') else '',
                format_datetime_for_display(item.get('sold_at')) if item.get('sold_at') else '',
                item.get('cost_price', ''), item.get('actual_weight_grams', ''), item.get('notes', '')
            ])
        output.seek(0); timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"maison_truvra_serialized_inventory_{timestamp}.csv"
        audit_logger.log_action(user_id=current_admin_id, action='export_serialized_items_csv_success', details=f"Exported {len(items_data)} items.", status='success', ip_address=request.remote_addr)
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={filename}"})
    except Exception as e:
        current_app.logger.error(f"Error exporting CSV: {e}", exc_info=True)
        return jsonify(message="Failed to export serialized items.", success=False), 500

@inventory_bp.route('/import/serialized_items', methods=['POST'])
@admin_required
def import_serialized_items_csv():
    db = get_db_connection(); audit_logger = current_app.audit_log_service; current_admin_id = get_jwt_identity()
    if 'file' not in request.files: return jsonify(message="No file part in request.", success=False), 400
    file = request.files['file']
    if file.filename == '': return jsonify(message="No selected file.", success=False), 400
    if not file.filename.endswith('.csv'): return jsonify(message="Invalid file format. Only CSV.", success=False), 400

    imported = 0; updated = 0; failed = []; processed = 0
    try:
        stream = StringIO(file.stream.read().decode("UTF-8"), newline=None)
        reader = csv.DictReader(stream)
        headers = ['Product Code', 'Status'] 
        if not all(h in reader.fieldnames for h in headers):
            return jsonify(message=f"Missing CSV headers: {', '.join(h for h in headers if h not in reader.fieldnames)}", success=False), 400

        for row_num, row_dict in enumerate(reader, start=1):
            processed += 1; product_code = row_dict.get('Product Code', '').strip().upper()
            uid = row_dict.get('Item UID', '').strip(); variant_sku = row_dict.get('Variant SKU Suffix', '').strip().upper()
            status = row_dict.get('Status', 'available').strip()
            batch_number = row_dict.get('Batch Number', '').strip()
            prod_date_str = row_dict.get('Production Date', '').strip()
            exp_date_str = row_dict.get('Expiry Date', '').strip()
            cost_str = row_dict.get('Cost Price', '').strip()
            actual_weight_str = row_dict.get('Actual Weight (g)', '').strip()
            notes_csv = row_dict.get('Notes', '').strip()

            if not product_code: failed.append({'row': row_num, 'uid': uid, 'error': 'Product Code missing.'}); continue
            
            # Use product_code directly for product lookup
            prod_info = query_db("SELECT id FROM products WHERE product_code = ?", [product_code], db_conn=db, one=True)
            if not prod_info: failed.append({'row': row_num, 'uid': uid, 'error': 'Product Code not found.'}); continue
            prod_id = prod_info['id']

            var_id = None
            if variant_sku:
                var_info = query_db("SELECT id FROM product_weight_options WHERE product_id = ? AND sku_suffix = ?", [prod_id, variant_sku], db_conn=db, one=True)
                if not var_info: failed.append({'row': row_num, 'uid': uid, 'error': 'Variant SKU not found.'}); continue
                var_id = var_info['id']
            
            try:
                prod_date = format_datetime_for_storage(parse_datetime_from_iso(prod_date_str)) if prod_date_str else None
                exp_date = format_datetime_for_storage(parse_datetime_from_iso(exp_date_str)) if exp_date_str else None
                cost = float(cost_str) if cost_str else None
                actual_weight = float(actual_weight_str) if actual_weight_str else None
            except ValueError as ve_format:
                failed.append({'row': row_num, 'uid': uid, 'error': f'Invalid data format: {ve_format}'}); continue

            cursor = db.cursor()
            existing = query_db("SELECT id FROM serialized_inventory_items WHERE item_uid = ?", [uid], db_conn=db, one=True) if uid else None
            if existing:
                cursor.execute("UPDATE serialized_inventory_items SET status=?, batch_number=?, production_date=?, expiry_date=?, cost_price=?, actual_weight_grams=?, notes=?, product_id=?, variant_id=?, updated_at=CURRENT_TIMESTAMP WHERE item_uid=?",
                               (status, batch_number, prod_date, exp_date, cost, actual_weight, notes_csv, prod_id, var_id, uid))
                updated += 1
            else:
                # Use product_code (which is the new sku_prefix) for UID generation
                uid_to_insert = uid if uid else f"{product_code}-{uuid.uuid4().hex[:8].upper()}"
                while query_db("SELECT id FROM serialized_inventory_items WHERE item_uid = ?", [uid_to_insert], db_conn=db, one=True):
                    uid_to_insert = f"{product_code}-{uuid.uuid4().hex[:8].upper()}"
                cursor.execute("INSERT INTO serialized_inventory_items (item_uid, product_id, variant_id, status, batch_number, production_date, expiry_date, cost_price, actual_weight_grams, notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (uid_to_insert, prod_id, var_id, status, batch_number, prod_date, exp_date, cost, actual_weight, notes_csv))
                ser_id = cursor.lastrowid
                record_stock_movement(db, prod_id, 'import_csv_new', 1, var_id, ser_id, "CSV Import", current_admin_id)
                imported += 1
        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='import_serialized_csv_success', details=f"Imported: {imported}, Updated: {updated}, Failed: {len(failed)} from {processed} rows.", status='success', ip_address=request.remote_addr)
        return jsonify(message="CSV import processed.", imported=imported, updated=updated, failed_rows=failed, total_processed=processed, success=True), 200
    except Exception as e:
        db.rollback(); current_app.logger.error(f"Error importing CSV: {e}", exc_info=True)
        return jsonify(message=f"Failed to import CSV: {str(e)}", success=False), 500

@inventory_bp.route('/stock/adjust', methods=['POST'])
@admin_required
def adjust_stock():
    data = request.json; product_code_str = data.get('product_code'); variant_sku = data.get('variant_sku_suffix')
    qty_change_str = data.get('quantity_change'); reason = data.get('notes'); mov_type = data.get('movement_type')
    admin_id = get_jwt_identity(); audit = current_app.audit_log_service; db = get_db_connection()

    if not all([product_code_str, reason, mov_type]) or qty_change_str is None:
        return jsonify(message="Product Code, reason, movement type, and quantity change required", success=False), 400
    
    prod_id = get_product_id_from_code(product_code_str.upper(), db_conn=db)
    if not prod_id: return jsonify(message=f"Product code '{product_code_str}' not found.", success=False), 404
    
    var_id = None
    if variant_sku:
        var_info = query_db("SELECT id FROM product_weight_options WHERE product_id = ? AND sku_suffix = ?", [prod_id, variant_sku.upper()], db_conn=db, one=True)
        if not var_info: return jsonify(message=f"Variant SKU '{variant_sku}' not found.", success=False), 400
        var_id = var_info['id']
        
    cursor = db.cursor()
    try:
        qty_change = int(qty_change_str)
        allowed_mov = ['ajustement_manuel', 'correction', 'perte', 'retour_non_commande', 'addition', 'creation_lot', 'decouverte_stock', 'retour_client']
        if mov_type not in allowed_mov: return jsonify(message=f"Invalid movement type: {mov_type}", success=False), 400
        
        if qty_change != 0:
            if var_id: cursor.execute("UPDATE product_weight_options SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", (qty_change, var_id))
            else: cursor.execute("UPDATE products SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", (qty_change, prod_id))
        
        record_stock_movement(db, prod_id, mov_type, qty_change, var_id, reason=reason, related_user_id=admin_id, notes=reason)
        db.commit()
        audit.log_action(user_id=admin_id, action='adjust_stock_success', target_type='product', target_id=prod_id, details=f"Stock for {product_code_str} (var: {variant_sku or 'N/A'}) adjusted by {qty_change}. Reason: {reason}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Stock adjusted successfully", success=True), 200
    except ValueError as ve:
        db.rollback(); return jsonify(message=f"Invalid data: {ve}", success=False), 400
    except Exception as e:
        db.rollback(); current_app.logger.error(f"Error adjusting stock for {product_code_str}: {e}", exc_info=True)
        return jsonify(message="Failed to adjust stock", success=False), 500

@inventory_bp.route('/product/<string:product_code>', methods=['GET'])
@admin_required
def get_admin_product_inventory_details(product_code):
    db = get_db_connection(); variant_sku = request.args.get('variant_sku_suffix')
    prod_id = get_product_id_from_code(product_code.upper(), db_conn=db)
    if not prod_id: return jsonify(message="Product not found", success=False), 404

    try:
        prod_info = query_db("SELECT * FROM products WHERE id = ?", [prod_id], db_conn=db, one=True)
        if not prod_info: return jsonify(message="Product not found", success=False), 404
        details = dict(prod_info); var_id_filter = None
        
        if details['type'] == 'variable_weight':
            options = query_db("SELECT *, id as option_id FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [prod_id], db_conn=db)
            details['current_stock_by_variant'] = [dict(o) for o in options] if options else []
            details['calculated_total_variant_stock'] = sum(v.get('aggregate_stock_quantity',0) for v in details['current_stock_by_variant'])
            if variant_sku:
                match_var = next((v for v in details['current_stock_by_variant'] if v['sku_suffix'].upper() == variant_sku.upper()), None)
                if match_var: var_id_filter = match_var['option_id']
        
        mov_query = "SELECT * FROM stock_movements WHERE product_id = ?"
        mov_params = [prod_id]
        if var_id_filter: mov_query += " AND variant_id = ?"; mov_params.append(var_id_filter)
        elif variant_sku and not var_id_filter: details['stock_movements_log'] = []
        
        if not (variant_sku and not var_id_filter):
            mov_query += " ORDER BY movement_date DESC LIMIT 100"
            movements = query_db(mov_query, mov_params, db_conn=db)
            details['stock_movements_log'] = []
            if movements:
                for m in movements:
                    m_dict = dict(m); m_dict['movement_date'] = format_datetime_for_display(m_dict['movement_date'])
                    details['stock_movements_log'].append(m_dict)
        return jsonify(details=details, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin inventory details for {product_code}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch inventory details", success=False), 500

@inventory_bp.route('/serialized/items/<string:item_uid>/status', methods=['PUT'])
@admin_required
def update_serialized_item_status(item_uid):
    data = request.json; new_status = data.get('status'); notes = data.get('notes', '')
    admin_id = get_jwt_identity(); audit = current_app.audit_log_service; db = get_db_connection()

    if not new_status: return jsonify(message="New status required", success=False), 400
    allowed = ['available', 'damaged', 'recalled', 'reserved_internal', 'missing']
    if new_status not in allowed: return jsonify(message=f"Invalid status. Allowed: {', '.join(allowed)}", success=False), 400

    cursor = db.cursor()
    try:
        item_info = query_db("SELECT id, product_id, variant_id, status, notes as current_notes FROM serialized_inventory_items WHERE item_uid = ?", [item_uid], db_conn=db, one=True)
        if not item_info: return jsonify(message="Item not found", success=False), 404
        item = dict(item_info); old_status = item['status']
        if old_status == new_status: return jsonify(message="Status unchanged.", item_status=new_status, success=True), 200

        updated_notes = item.get('current_notes', '') or ''
        if notes: updated_notes += f"\n[{format_datetime_for_display(None)} by AdminID:{admin_id}]: Status {old_status} -> {new_status}. Reason: {notes}"
        
        cursor.execute("UPDATE serialized_inventory_items SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE item_uid = ?", (new_status, updated_notes.strip(), item_uid))
        
        qty_change_agg = 0
        if old_status == 'available' and new_status != 'available': qty_change_agg = -1
        elif old_status != 'available' and new_status == 'available': qty_change_agg = 1
        
        if qty_change_agg != 0:
            if item['variant_id']: cursor.execute("UPDATE product_weight_options SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", (qty_change_agg, item['variant_id']))
            else: cursor.execute("UPDATE products SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", (qty_change_agg, item['product_id']))
        db.commit()
        audit.log_action(user_id=admin_id, action='update_item_status_success', target_type='serialized_item', target_id=item_uid, details=f"Status of {item_uid} from '{old_status}' to '{new_status}'. Notes: {notes}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Status of {item_uid} updated to {new_status}.", success=True), 200
    except Exception as e:
        db.rollback(); current_app.logger.error(f"Error updating status for {item_uid}: {e}", exc_info=True)
        return jsonify(message="Failed to update item status", success=False), 500
