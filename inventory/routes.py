# backend/inventory/routes.py
import os
import uuid
import csv
from io import StringIO
from flask import request, jsonify, current_app, url_for, Response, abort as flask_abort, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
from sqlalchemy import func # For func.upper()

# Assuming your Flask app instance has a 'celery' attribute if using Celery
# from your_app import celery_app # Example: from .. import celery_app

from .. import db
from ..models import (
    Product, ProductWeightOption, SerializedInventoryItem, StockMovement, 
    Category, CategoryLocalization, ProductLocalization,
    SerializedInventoryItemStatusEnum, StockMovementTypeEnum # Import Enums
)
from ..services.asset_service import (
    generate_qr_code_for_item,
    generate_item_passport,
    generate_product_label_pdf
)
from ..utils import admin_required, format_datetime_for_display, parse_datetime_from_iso, format_datetime_for_storage
from ..database import record_stock_movement 

from . import inventory_bp

# --- Conceptual Sanitization Helper ---
# In a real application, use a library like bleach for HTML sanitization
# or more specific validation/cleaning based on field type.
def sanitize_input(value, allow_html=False):
    if value is None:
        return None
    value_str = str(value).strip()
    if not allow_html:
        # Basic sanitization: replace < and > to prevent simple HTML injection
        # For robust XSS prevention where HTML is displayed, use a proper library.
        value_str = value_str.replace("<", "&lt;").replace(">", "&gt;")
    # Add other general sanitization if needed (e.g., limit length)
    return value_str

# --- Helper for receive_serialized_stock ---
def _process_single_item_receipt_and_assets(
        db_session, product_info, variant_id, item_index,
        batch_number, production_date_iso_str, expiry_date_iso_str,
        cost_price, notes_for_item, actual_weight_grams_item,
        current_admin_id, category_info_for_passport):
    """
    Processes a single item for stock receipt: generates UID, assets, creates DB object.
    Returns the SerializedInventoryItem object (not yet committed) and asset details.
    Can raise exceptions if asset generation fails.
    """
    product_id = product_info.id
    product_name_for_assets = product_info.name # Default
    product_sku_prefix = product_info.product_code # Using product_code as sku_prefix

    # Fetch localized names for assets
    loc_fr = ProductLocalization.query.filter_by(product_id=product_id, lang_code='fr').first()
    loc_en = ProductLocalization.query.filter_by(product_id=product_id, lang_code='en').first()
    product_name_fr_for_assets = loc_fr.name_fr if loc_fr and loc_fr.name_fr else product_name_for_assets
    product_name_en_for_assets = loc_en.name_en if loc_en and loc_en.name_en else product_name_for_assets

    item_uid = f"{product_sku_prefix}-{uuid.uuid4().hex[:8].upper()}"
    
    item_specific_data_for_passport = {
        "batch_number": batch_number, "production_date": production_date_iso_str,
        "expiry_date": expiry_date_iso_str, "actual_weight_grams": actual_weight_grams_item
    }
    
    # --- Conceptual Asynchronous Asset Generation ---
    # In a real scenario with Celery:
    # passport_task = generate_item_passport_async.delay(item_uid, product_info.to_dict(), category_info_for_passport, item_specific_data_for_passport)
    # qr_task = generate_qr_code_for_item_async.delay(item_uid, product_id, product_name_fr_for_assets, product_name_en_for_assets)
    # label_task = generate_product_label_pdf_async.delay(...)
    # For now, we do it synchronously.
    # -----------------------------------------------

    passport_relative_path = generate_item_passport(item_uid, product_info, category_info_for_passport, item_specific_data_for_passport)
    if not passport_relative_path: raise Exception(f"Failed to generate passport for item {item_index+1}.")

    passport_public_url = url_for('serve_public_asset', filepath=passport_relative_path, _external=True)
    qr_code_png_relative_path = generate_qr_code_for_item(item_uid, product_id, product_name_fr_for_assets, product_name_en_for_assets)
    if not qr_code_png_relative_path: raise Exception(f"Failed to generate QR code PNG for item {item_index+1}.")
    
    weight_for_label = actual_weight_grams_item
    if not weight_for_label and variant_id:
        variant_for_label = ProductWeightOption.query.get(variant_id)
        if variant_for_label: weight_for_label = variant_for_label.weight_grams

    processing_date_for_label_fr = datetime.now(timezone.utc).strftime('%d/%m/%Y')
    label_pdf_relative_path = generate_product_label_pdf(
        item_uid=item_uid, product_name_fr=product_name_fr_for_assets, product_name_en=product_name_en_for_assets,
        weight_grams=weight_for_label, processing_date_str=processing_date_for_label_fr,
        passport_url=passport_public_url
    )
    if not label_pdf_relative_path: raise Exception(f"Failed to generate PDF label for item {item_index+1}.")

    production_date_db = parse_datetime_from_iso(production_date_iso_str) if production_date_iso_str else None
    expiry_date_db = parse_datetime_from_iso(expiry_date_iso_str) if expiry_date_iso_str else None

    new_item = SerializedInventoryItem(
        item_uid=item_uid, product_id=product_id, variant_id=variant_id,
        batch_number=batch_number, production_date=production_date_db, expiry_date=expiry_date_db,
        cost_price=cost_price, notes=notes_for_item, 
        status=SerializedInventoryItemStatusEnum.AVAILABLE, # Use Enum
        qr_code_url=qr_code_png_relative_path, 
        passport_url=passport_relative_path,
        label_url=label_pdf_relative_path, 
        actual_weight_grams=actual_weight_grams_item
    )
    db_session.add(new_item)
    db_session.flush() # To get new_item.id for stock movement

    record_stock_movement(db_session, product_id, StockMovementTypeEnum.RECEIVE_SERIALIZED, # Use Enum
                          quantity_change=1, variant_id=variant_id, serialized_item_id=new_item.id,
                          reason="Initial stock receipt via serialized receive", related_user_id=current_admin_id)
    
    asset_details = {
        "item_uid": item_uid, "product_name": product_name_fr_for_assets, "product_code": product_info.product_code,
        "qr_code_path": qr_code_png_relative_path, "passport_path": passport_relative_path,
        "label_pdf_path": label_pdf_relative_path
    }
    return new_item, asset_details
# --- End Helper ---


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
    notes_for_item = data.get('notes', '') # Notes apply per item if generated in loop
    actual_weight_grams_str = data.get('actual_weight_grams')

    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not all([product_code_str, quantity_received_str]):
        return jsonify(message="Product Code and quantity are required", success=False), 400

    product_info = Product.query.filter(func.upper(Product.product_code) == product_code_str.upper()).first()
    if not product_info:
        return jsonify(message=f"Product Code '{product_code_str}' not found.", success=False), 404
    
    variant_id = None
    if variant_sku_suffix:
        variant_info_model = ProductWeightOption.query.filter_by(product_id=product_info.id, sku_suffix=variant_sku_suffix.upper()).first()
        if not variant_info_model:
            return jsonify(message=f"Variant SKU suffix '{variant_sku_suffix}' not found for product code '{product_code_str}'.", success=False), 400
        variant_id = variant_info_model.id

    try:
        quantity_received = int(quantity_received_str)
        if quantity_received <= 0: raise ValueError("Quantity received must be positive.")
        cost_price = float(cost_price_str) if cost_price_str else None
        actual_weight_grams_item = float(actual_weight_grams_str) if actual_weight_grams_str else None
    except ValueError as ve:
        return jsonify(message=f"Invalid data type: {ve}", success=False), 400

    # Category info for passport (fetch once)
    category_info_for_passport = {"name_fr": "N/A", "name_en": "N/A", "species_fr": "N/A", "species_en": "N/A", "ingredients_fr": "N/A", "ingredients_en": "N/A"}
    if product_info.category_id:
        category = Category.query.get(product_info.category_id)
        if category:
            cat_loc_fr = CategoryLocalization.query.filter_by(category_id=category.id, lang_code='fr').first()
            cat_loc_en = CategoryLocalization.query.filter_by(category_id=category.id, lang_code='en').first()
            category_info_for_passport['name_fr'] = (cat_loc_fr.name_fr if cat_loc_fr and cat_loc_fr.name_fr else category.name)
            category_info_for_passport['name_en'] = (cat_loc_en.name_en if loc_en and loc_en.name_en else category.name)
            # Populate other localized category fields as needed

    generated_items_summary = []
    all_assets_generated_for_cleanup = []

    try:
        for i in range(quantity_received):
            # Pass db.session to the helper if it needs to add to session,
            # or let it return objects to be added here.
            # For now, helper adds to session, main route commits.
            _, asset_details = _process_single_item_receipt_and_assets(
                db.session, product_info, variant_id, i,
                batch_number, production_date_iso_str, expiry_date_iso_str,
                cost_price, notes_for_item, actual_weight_grams_item,
                current_admin_id, category_info_for_passport
            )
            generated_items_summary.append(asset_details)
            all_assets_generated_for_cleanup.extend([
                asset_details['qr_code_path'], 
                asset_details['passport_path'], 
                asset_details['label_pdf_path']
            ])
        
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_success', target_type='product', target_id=product_info.id, details=f"Received {quantity_received} items for {product_code_str}.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"{quantity_received} items received successfully.", items=generated_items_summary, success=True), 201
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during batch stock receipt for {product_code_str}: {e}", exc_info=True)
        # Asset cleanup logic
        asset_base = current_app.config['ASSET_STORAGE_PATH']
        for asset_relative_path in all_assets_generated_for_cleanup:
            if asset_relative_path:
                try: 
                    full_asset_path = os.path.join(asset_base, asset_relative_path)
                    if os.path.exists(full_asset_path):
                        os.remove(full_asset_path)
                except OSError as e_clean:
                     current_app.logger.error(f"Error cleaning up asset {asset_relative_path}: {e_clean}")
        
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail_exception', target_type='product', target_id=product_info.id, details=f"Failed for {product_code_str}: {str(e)}.", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to receive stock: {str(e)}", success=False), 500


@inventory_bp.route('/export/serialized_items', methods=['GET'])
@admin_required
def export_serialized_items_csv():
    # ... (Existing logic, ensure Enums are handled if status is exported as string: item.status.value) ...
    # This function was already quite detailed and mostly fine.
    # Ensure that when fetching data, if you access an Enum field, you use .value for the CSV.
    audit_logger = current_app.audit_log_service
    current_admin_id = get_jwt_identity()
    try:
        items_query = db.session.query(
            SerializedInventoryItem.item_uid, Product.product_code, 
            func.coalesce(ProductLocalization.name_fr, Product.name).label("product_name_fr"),
            func.coalesce(ProductLocalization.name_en, Product.name).label("product_name_en"),
            ProductWeightOption.weight_grams.label('variant_weight_grams'), 
            ProductWeightOption.sku_suffix.label('variant_sku_suffix'),
            SerializedInventoryItem.status, SerializedInventoryItem.batch_number, 
            SerializedInventoryItem.production_date, SerializedInventoryItem.expiry_date, 
            SerializedInventoryItem.received_at, SerializedInventoryItem.sold_at,
            SerializedInventoryItem.cost_price, SerializedInventoryItem.actual_weight_grams, 
            SerializedInventoryItem.notes
        ).join(Product, SerializedInventoryItem.product_id == Product.id)\
         .outerjoin(ProductLocalization, and_(Product.id == ProductLocalization.product_id, ProductLocalization.lang_code == 'fr'))\
         .outerjoin(ProductLocalization.alias('pl_en'), and_(Product.id == ProductLocalization.alias('pl_en').product_id, ProductLocalization.alias('pl_en').lang_code == 'en'))\
         .outerjoin(ProductWeightOption, SerializedInventoryItem.variant_id == ProductWeightOption.id)\
         .order_by(Product.product_code, SerializedInventoryItem.item_uid)

        items_data_tuples = items_query.all()

        if not items_data_tuples:
            return jsonify(message="No serialized items found to export.", success=False), 404

        output = StringIO()
        writer = csv.writer(output)
        headers = ['Item UID', 'Product Code', 'Product Name (FR)', 'Product Name (EN)', 
                   'Variant Weight (g)', 'Variant SKU Suffix', 'Status', 'Batch Number', 
                   'Production Date', 'Expiry Date', 'Received At', 'Sold At', 
                   'Cost Price', 'Actual Weight (g)', 'Notes']
        writer.writerow(headers)

        for item_tuple in items_data_tuples:
            # Convert SQLAlchemy Row to something subscriptable or use getattr
            item_dict = {col.name: getattr(item_tuple, col.name) for col in item_tuple._fields}
            status_value = item_dict.get('status').value if isinstance(item_dict.get('status'), enum.Enum) else item_dict.get('status', '')

            writer.writerow([
                item_dict.get('item_uid', ''), item_dict.get('product_code', ''), 
                item_dict.get('product_name_fr', ''), item_dict.get('product_name_en', ''),
                item_dict.get('variant_weight_grams', ''), item_dict.get('variant_sku_suffix', ''),
                status_value, 
                item_dict.get('batch_number', ''),
                format_datetime_for_display(item_dict.get('production_date'), fmt='%Y-%m-%d') if item_dict.get('production_date') else '',
                format_datetime_for_display(item_dict.get('expiry_date'), fmt='%Y-%m-%d') if item_dict.get('expiry_date') else '',
                format_datetime_for_display(item_dict.get('received_at')) if item_dict.get('received_at') else '',
                format_datetime_for_display(item_dict.get('sold_at')) if item_dict.get('sold_at') else '',
                item_dict.get('cost_price', ''), item_dict.get('actual_weight_grams', ''), 
                item_dict.get('notes', '')
            ])
        
        output.seek(0)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"maison_truvra_serialized_inventory_{timestamp}.csv"
        audit_logger.log_action(user_id=current_admin_id, action='export_serialized_items_csv_success', details=f"Exported {len(items_data_tuples)} items.", status='success', ip_address=request.remote_addr)
        return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={filename}"})
    except Exception as e:
        current_app.logger.error(f"Error exporting CSV: {e}", exc_info=True)
        return jsonify(message="Failed to export serialized items.", success=False), 500


@inventory_bp.route('/import/serialized_items', methods=['POST'])
@admin_required
def import_serialized_items_csv():
    audit_logger = current_app.audit_log_service
    current_admin_id = get_jwt_identity()
    if 'file' not in request.files: return jsonify(message="No file part in request.", success=False), 400
    file = request.files['file']
    if file.filename == '': return jsonify(message="No selected file.", success=False), 400
    if not file.filename.endswith('.csv'): return jsonify(message="Invalid file format. Only CSV.", success=False), 400

    imported_count = 0; updated_count = 0; failed_rows = []; processed_count = 0
    
    # Define expected headers and which ones are strictly required for new items
    # For updates via UID, only UID and fields to update are needed.
    # For new items, Product Code is essential.
    expected_headers = ['Item UID', 'Product Code', 'Variant SKU Suffix', 'Status', 
                        'Batch Number', 'Production Date', 'Expiry Date', 
                        'Cost Price', 'Actual Weight (g)', 'Notes']
    required_for_new = ['Product Code'] # Status defaults if not provided

    try:
        stream = StringIO(file.stream.read().decode("UTF-8-sig"), newline=None) # Use UTF-8-sig for BOM
        reader = csv.DictReader(stream)
        
        # Header validation
        csv_headers = reader.fieldnames
        if not csv_headers:
             return jsonify(message="CSV file is empty or has no headers.", success=False), 400
        
        missing_required_headers = [h for h in required_for_new if h not in csv_headers]
        if any(h not in csv_headers for h in ['Product Code']): # At least Product Code must be there
             return jsonify(message=f"CSV missing essential headers. Required: 'Product Code'. Found: {', '.join(csv_headers)}", success=False), 400


        for row_num, row_dict in enumerate(reader, start=1):
            processed_count += 1
            # Sanitize string inputs from CSV
            product_code = sanitize_input(row_dict.get('Product Code', '')).upper()
            item_uid_csv = sanitize_input(row_dict.get('Item UID', ''))
            variant_sku_csv = sanitize_input(row_dict.get('Variant SKU Suffix', '')).upper()
            status_str = sanitize_input(row_dict.get('Status', 'available'))
            batch_number_csv = sanitize_input(row_dict.get('Batch Number'))
            notes_csv = sanitize_input(row_dict.get('Notes')) # Basic strip, no HTML allowed by default

            # Validate status enum
            try:
                status_enum = SerializedInventoryItemStatusEnum(status_str.lower()) if status_str else SerializedInventoryItemStatusEnum.AVAILABLE
            except ValueError:
                failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': f"Invalid status value: '{status_str}'."})
                continue
            
            if not product_code and not item_uid_csv: # Must have at least one to identify or create
                failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': 'Product Code or Item UID is required.'})
                continue
            
            product = None
            if product_code:
                product = Product.query.filter(func.upper(Product.product_code) == product_code).first()
                if not product:
                    failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': f'Product Code {product_code} not found.'})
                    continue
            
            variant_id_db = None
            if product and variant_sku_csv: # Only look for variant if product exists
                variant = ProductWeightOption.query.filter_by(product_id=product.id, sku_suffix=variant_sku_csv).first()
                if not variant:
                    failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': f'Variant SKU {variant_sku_csv} not found for product {product_code}.'})
                    continue
                variant_id_db = variant.id
            
            # Parse dates and numbers carefully
            production_date_db = parse_datetime_from_iso(sanitize_input(row_dict.get('Production Date')))
            expiry_date_db = parse_datetime_from_iso(sanitize_input(row_dict.get('Expiry Date')))
            cost_price_db = None
            if row_dict.get('Cost Price'):
                try: cost_price_db = float(sanitize_input(row_dict.get('Cost Price')))
                except ValueError: failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': 'Invalid Cost Price format.'}); continue
            actual_weight_db = None
            if row_dict.get('Actual Weight (g)'):
                try: actual_weight_db = float(sanitize_input(row_dict.get('Actual Weight (g)')))
                except ValueError: failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': 'Invalid Actual Weight format.'}); continue

            existing_item = None
            if item_uid_csv:
                existing_item = SerializedInventoryItem.query.filter_by(item_uid=item_uid_csv).first()
            
            if existing_item:
                if product and existing_item.product_id != product.id: # UID exists but product code mismatch
                     failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': f'Item UID {item_uid_csv} exists but Product Code mismatch.'}); continue
                
                existing_item.status = status_enum
                if variant_id_db is not None: existing_item.variant_id = variant_id_db # Allow changing variant if needed
                if batch_number_csv is not None: existing_item.batch_number = batch_number_csv
                if production_date_db is not None: existing_item.production_date = production_date_db
                if expiry_date_db is not None: existing_item.expiry_date = expiry_date_db
                if cost_price_db is not None: existing_item.cost_price = cost_price_db
                if actual_weight_db is not None: existing_item.actual_weight_grams = actual_weight_db
                if notes_csv is not None: existing_item.notes = notes_csv
                existing_item.updated_at = datetime.now(timezone.utc)
                updated_count += 1
            else: # New item
                if not product: # Product code was required for new items
                    failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': 'Product Code required for new item.'}); continue

                uid_to_insert = item_uid_csv if item_uid_csv else f"{product.product_code}-{uuid.uuid4().hex[:8].upper()}"
                # Ensure UID is unique if generated
                while not item_uid_csv and SerializedInventoryItem.query.filter_by(item_uid=uid_to_insert).first():
                    uid_to_insert = f"{product.product_code}-{uuid.uuid4().hex[:8].upper()}"

                new_item = SerializedInventoryItem(
                    item_uid=uid_to_insert, product_id=product.id, variant_id=variant_id_db, 
                    status=status_enum, batch_number=batch_number_csv, 
                    production_date=production_date_db, expiry_date=expiry_date_db,
                    cost_price=cost_price_db, actual_weight_grams=actual_weight_db,
                    notes=notes_csv
                )
                db.session.add(new_item)
                db.session.flush() 
                record_stock_movement(db.session, product.id, StockMovementTypeEnum.IMPORT_CSV_NEW, 1, variant_id_db, new_item.id, "CSV Import", current_admin_id)
                imported_count += 1
        
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='import_serialized_csv_success', details=f"Imported: {imported_count}, Updated: {updated_count}, Failed: {len(failed_rows)} from {processed_count} rows.", status='success', ip_address=request.remote_addr)
        return jsonify(message="CSV import processed.", imported=imported_count, updated=updated_count, failed_rows=failed_rows, total_processed=processed_count, success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error importing CSV: {e}", exc_info=True)
        return jsonify(message=f"Failed to import CSV: {str(e)}", success=False), 500

@inventory_bp.route('/stock/adjust', methods=['POST'])
@admin_required
def adjust_stock():
    # ... (Existing logic, ensure Enums are used for movement_type) ...
    data = request.json
    product_code_str = data.get('product_code')
    variant_sku_suffix = data.get('variant_sku_suffix')
    quantity_change_str = data.get('quantity_change')
    reason = data.get('notes') 
    movement_type_str = data.get('movement_type') # e.g., 'manual_adjustment_in', 'damage_out'

    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not all([product_code_str, reason, movement_type_str]) or quantity_change_str is None:
        return jsonify(message="Product Code, reason, movement type, and quantity change are required.", success=False), 400

    product = Product.query.filter(func.upper(Product.product_code) == product_code_str.upper()).first()
    if not product:
        return jsonify(message=f"Product code '{product_code_str}' not found.", success=False), 404

    variant_id_db = None
    target_stock_entity = product 
    if variant_sku_suffix:
        variant = ProductWeightOption.query.filter_by(product_id=product.id, sku_suffix=variant_sku_suffix.upper()).first()
        if not variant:
            return jsonify(message=f"Variant SKU '{variant_sku_suffix}' not found for product '{product_code_str}'.", success=False), 404
        variant_id_db = variant.id
        target_stock_entity = variant 

    try:
        quantity_change = int(quantity_change_str)
        movement_type_enum = StockMovementTypeEnum(movement_type_str) # Validate against Enum
        
        if quantity_change != 0:
            if target_stock_entity.aggregate_stock_quantity is None: target_stock_entity.aggregate_stock_quantity = 0
            target_stock_entity.aggregate_stock_quantity += quantity_change
            if target_stock_entity.aggregate_stock_quantity < 0:
                raise ValueError("Stock quantity cannot go below zero with this adjustment.")
        
        record_stock_movement(db.session, product.id, movement_type_enum, 
                              quantity_change=quantity_change,
                              variant_id=variant_id_db, reason=reason, 
                              related_user_id=current_admin_id, notes=reason)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_success', target_type='product_stock', target_id=product.id, details=f"Stock for {product_code_str} (var: {variant_sku_suffix or 'N/A'}) adjusted by {quantity_change} via {movement_type_enum.value}. Reason: {reason}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Stock adjusted successfully", success=True), 200
    except ValueError as ve: # Catches int conversion, enum conversion, stock < 0
        db.session.rollback()
        return jsonify(message=f"Invalid data: {ve}", success=False), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adjusting stock for {product_code_str}: {e}", exc_info=True)
        return jsonify(message="Failed to adjust stock", success=False), 500

@inventory_bp.route('/product/<string:product_code>', methods=['GET'])
@admin_required
def get_admin_product_inventory_details(product_code):
    # ... (Existing logic, ensure Enums are handled if status/type is part of to_dict()) ...
    variant_sku_suffix = request.args.get('variant_sku_suffix')
    product = Product.query.filter(func.upper(Product.product_code) == product_code.upper()).first()
    if not product: return jsonify(message="Product not found", success=False), 404

    try:
        details = product.to_dict() 
        
        if product.type == ProductTypeEnum.VARIABLE_WEIGHT: # Use Enum
            options = ProductWeightOption.query.filter_by(product_id=product.id).order_by(ProductWeightOption.weight_grams).all()
            details['current_stock_by_variant'] = [
                {'option_id': opt.id, 'weight_grams': opt.weight_grams, 'price': opt.price, 
                 'sku_suffix': opt.sku_suffix, 'aggregate_stock_quantity': opt.aggregate_stock_quantity} 
                for opt in options
            ]
            details['calculated_total_variant_stock'] = sum(v.get('aggregate_stock_quantity', 0) for v in details['current_stock_by_variant'])
        
        movements_query = StockMovement.query.filter_by(product_id=product.id)
        target_variant_id = None
        if variant_sku_suffix:
            target_variant = ProductWeightOption.query.filter_by(product_id=product.id, sku_suffix=variant_sku_suffix.upper()).first()
            if target_variant:
                target_variant_id = target_variant.id
                movements_query = movements_query.filter_by(variant_id=target_variant_id)
            else: 
                details['stock_movements_log'] = [] # Variant not found, no movements for it
        
        if not (variant_sku_suffix and not target_variant_id): 
            movements_models = movements_query.order_by(StockMovement.movement_date.desc()).limit(100).all()
            details['stock_movements_log'] = [m.to_dict() for m in movements_models] # Assuming to_dict handles Enum.value
        
        return jsonify(details=details, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin inventory details for {product_code}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch inventory details", success=False), 500


@inventory_bp.route('/serialized/items/<string:item_uid>/status', methods=['PUT'])
@admin_required
def update_serialized_item_status(item_uid):
    # ... (Existing logic, ensure Enums are used for new_status and old_status comparison) ...
    data = request.json
    new_status_str = data.get('status')
    notes = sanitize_input(data.get('notes', '')) # Sanitize notes
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not new_status_str: return jsonify(message="New status required", success=False), 400
    
    try:
        new_status_enum = SerializedInventoryItemStatusEnum(new_status_str.lower())
    except ValueError:
        return jsonify(message=f"Invalid status value: '{new_status_str}'.", success=False), 400

    # Define statuses an admin can manually set. Others (like 'sold', 'allocated') are system-set.
    allowed_manual_statuses = [
        SerializedInventoryItemStatusEnum.AVAILABLE, 
        SerializedInventoryItemStatusEnum.DAMAGED, 
        SerializedInventoryItemStatusEnum.RECALLED, 
        SerializedInventoryItemStatusEnum.RESERVED_INTERNAL, 
        SerializedInventoryItemStatusEnum.MISSING
    ]
    if new_status_enum not in allowed_manual_statuses:
        return jsonify(message=f"Invalid status for manual update. Allowed: {', '.join(s.value for s in allowed_manual_statuses)}", success=False), 400

    try:
        item = SerializedInventoryItem.query.filter_by(item_uid=item_uid).first()
        if not item: return jsonify(message="Item not found", success=False), 404
        
        old_status_enum = item.status # This is already an Enum member
        if old_status_enum == new_status_enum:
            return jsonify(message="Status unchanged.", item_status=new_status_enum.value, success=True), 200

        item.status = new_status_enum
        current_item_notes = item.notes or ""
        if notes:
            item.notes = f"{current_item_notes}\n[{format_datetime_for_display(None)} by AdminID:{current_admin_id}]: Status {old_status_enum.value} -> {new_status_enum.value}. Reason: {notes}".strip()
        item.updated_at = datetime.now(timezone.utc)
        
        qty_change_agg = 0
        if old_status_enum == SerializedInventoryItemStatusEnum.AVAILABLE and new_status_enum != SerializedInventoryItemStatusEnum.AVAILABLE: 
            qty_change_agg = -1
        elif old_status_enum != SerializedInventoryItemStatusEnum.AVAILABLE and new_status_enum == SerializedInventoryItemStatusEnum.AVAILABLE: 
            qty_change_agg = 1
        
        if qty_change_agg != 0:
            target_stock_entity = ProductWeightOption.query.get(item.variant_id) if item.variant_id else Product.query.get(item.product_id)
            if target_stock_entity:
                if target_stock_entity.aggregate_stock_quantity is None: target_stock_entity.aggregate_stock_quantity = 0
                target_stock_entity.aggregate_stock_quantity += qty_change_agg
        
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_item_status_success', target_type='serialized_item', target_id=item_uid, details=f"Status of {item_uid} from '{old_status_enum.value}' to '{new_status_enum.value}'. Notes: {notes}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Status of {item_uid} updated to {new_status_enum.value}.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating status for {item_uid}: {e}", exc_info=True)
        return jsonify(message="Failed to update item status", success=False), 500

