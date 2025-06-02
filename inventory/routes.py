# backend/inventory/routes.py
import os
import uuid
import csv
from io import StringIO
from flask import request, jsonify, current_app, url_for, Response, abort as flask_abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone

from .. import db
from ..models import Product, ProductWeightOption, SerializedInventoryItem, StockMovement, Category, CategoryLocalization, ProductLocalization
from ..services.asset_service import (
    generate_qr_code_for_item,
    generate_item_passport,
    generate_product_label_pdf
)
from ..utils import admin_required, format_datetime_for_display, parse_datetime_from_iso, format_datetime_for_storage
from ..database import record_stock_movement # Keep this if it's complex and adapt it for SQLAlchemy session

from . import inventory_bp

@inventory_bp.route('/serialized/receive', methods=['POST'])
@admin_required
def receive_serialized_stock():
    data = request.json
    product_code_str = data.get('product_code')
    quantity_received_str = data.get('quantity_received')
    variant_sku_suffix = data.get('variant_sku_suffix')
    # ... (other fields as before) ...
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

    product_info = Product.query.filter(func.upper(Product.product_code) == product_code_str.upper()).first()
    if not product_info:
        return jsonify(message=f"Product Code '{product_code_str}' not found.", success=False), 404
    
    product_id = product_info.id
    product_name_for_assets = product_info.name
    product_sku_prefix = product_info.sku_prefix or product_info.product_code # Fallback to product_code

    # Fetch localized names for assets
    loc_fr = ProductLocalization.query.filter_by(product_id=product_id, lang_code='fr').first()
    loc_en = ProductLocalization.query.filter_by(product_id=product_id, lang_code='en').first()
    product_name_fr_for_assets = loc_fr.name_fr if loc_fr and loc_fr.name_fr else product_name_for_assets
    product_name_en_for_assets = loc_en.name_en if loc_en and loc_en.name_en else product_name_for_assets


    variant_id = None
    if variant_sku_suffix:
        variant_info = ProductWeightOption.query.filter_by(product_id=product_id, sku_suffix=variant_sku_suffix.upper()).first()
        if not variant_info:
            return jsonify(message=f"Variant SKU suffix '{variant_sku_suffix}' not found for product code '{product_code_str}'.", success=False), 400
        variant_id = variant_info.id

    try:
        quantity_received = int(quantity_received_str)
        if quantity_received <= 0: raise ValueError("Quantity received must be positive.")
        cost_price = float(cost_price_str) if cost_price_str else None
        actual_weight_grams_item = float(actual_weight_grams_str) if actual_weight_grams_str else None
    except ValueError as ve:
        return jsonify(message=f"Invalid data type: {ve}", success=False), 400

    # Category info for passport
    category_info_for_passport = {"name_fr": "N/A", "name_en": "N/A", "species_fr": "N/A", "species_en": "N/A", "ingredients_fr": "N/A", "ingredients_en": "N/A"}
    if product_info.category_id:
        category = Category.query.get(product_info.category_id)
        if category:
            cat_loc_fr = CategoryLocalization.query.filter_by(category_id=category.id, lang_code='fr').first()
            cat_loc_en = CategoryLocalization.query.filter_by(category_id=category.id, lang_code='en').first()
            category_info_for_passport['name_fr'] = (cat_loc_fr.name_fr if cat_loc_fr and cat_loc_fr.name_fr else category.name)
            category_info_for_passport['name_en'] = (cat_loc_en.name_en if cat_loc_en and cat_loc_en.name_en else category.name)
            # ... populate other localized category fields ...

    production_date_db = parse_datetime_from_iso(production_date_iso_str) if production_date_iso_str else None
    expiry_date_db = parse_datetime_from_iso(expiry_date_iso_str) if expiry_date_iso_str else None
    processing_date_for_label_fr = datetime.now(timezone.utc).strftime('%d/%m/%Y')
    
    generated_items_details = []
    try:
        for _ in range(quantity_received):
            item_uid = f"{product_sku_prefix}-{uuid.uuid4().hex[:8].upper()}"
            
            # Asset generation (paths are relative to ASSET_STORAGE_PATH subfolders)
            item_specific_data_for_passport = {
                "batch_number": batch_number, "production_date": production_date_iso_str,
                "expiry_date": expiry_date_iso_str, "actual_weight_grams": actual_weight_grams_item
            }
            # Pass product_info (SQLAlchemy model instance) to asset service
            passport_relative_path = generate_item_passport(item_uid, product_info, category_info_for_passport, item_specific_data_for_passport)
            if not passport_relative_path: raise Exception(f"Failed to generate passport.")

            passport_public_url = url_for('serve_public_asset', filepath=passport_relative_path, _external=True)
            qr_code_png_relative_path = generate_qr_code_for_item(item_uid, product_id, product_name_fr_for_assets, product_name_en_for_assets)
            if not qr_code_png_relative_path: raise Exception(f"Failed to generate QR code PNG.")
            
            weight_for_label = actual_weight_grams_item
            if not weight_for_label and variant_id:
                variant_for_label = ProductWeightOption.query.get(variant_id)
                if variant_for_label: weight_for_label = variant_for_label.weight_grams

            label_pdf_relative_path = generate_product_label_pdf(
                item_uid=item_uid, product_name_fr=product_name_fr_for_assets, product_name_en=product_name_en_for_assets,
                weight_grams=weight_for_label, processing_date_str=processing_date_for_label_fr,
                passport_url=passport_public_url
            )
            if not label_pdf_relative_path: raise Exception(f"Failed to generate PDF label.")

            new_item = SerializedInventoryItem(
                item_uid=item_uid, product_id=product_id, variant_id=variant_id,
                batch_number=batch_number, production_date=production_date_db, expiry_date=expiry_date_db,
                cost_price=cost_price, notes=notes, status='available',
                qr_code_url=qr_code_png_relative_path, passport_url=passport_relative_path,
                label_url=label_pdf_relative_path, actual_weight_grams=actual_weight_grams_item
            )
            db.session.add(new_item)
            db.session.flush() # To get new_item.id for stock movement

            record_stock_movement(db.session, product_id, 'receive_serialized', quantity_change=1,
                                  variant_id=variant_id, serialized_item_id=new_item.id,
                                  reason="Initial stock receipt", related_user_id=current_admin_id)
            
            generated_items_details.append({
                "item_uid": item_uid, "product_name": product_name_fr_for_assets, "product_code": product_code_str.upper(),
                "qr_code_path": qr_code_png_relative_path, "passport_path": passport_relative_path,
                "label_pdf_path": label_pdf_relative_path
            })
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_success', target_type='product', target_id=product_id, details=f"Received {quantity_received} items for {product_code_str}.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"{quantity_received} items received.", items=generated_items_details, success=True), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error receiving stock for {product_code_str}: {e}", exc_info=True)
        # Asset cleanup logic remains similar
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
    audit_logger = current_app.audit_log_service
    current_admin_id = get_jwt_identity()
    try:
        items_query = db.session.query(
            SerializedInventoryItem.item_uid,
            Product.product_code,
            ProductLocalization.name_fr.label('product_name_fr'), # Requires joining ProductLocalization
            ProductLocalization.name_en.label('product_name_en'), # Requires joining ProductLocalization
            ProductWeightOption.weight_grams.label('variant_weight_grams'),
            ProductWeightOption.sku_suffix.label('variant_sku_suffix'),
            SerializedInventoryItem.status,
            SerializedInventoryItem.batch_number,
            SerializedInventoryItem.production_date,
            SerializedInventoryItem.expiry_date,
            SerializedInventoryItem.received_at,
            SerializedInventoryItem.sold_at,
            SerializedInventoryItem.cost_price,
            SerializedInventoryItem.actual_weight_grams,
            SerializedInventoryItem.notes
        ).join(Product, SerializedInventoryItem.product_id == Product.id)\
         .outerjoin(ProductLocalization, (Product.id == ProductLocalization.product_id) & (ProductLocalization.lang_code == 'fr'))\
         .outerjoin(ProductLocalization.alias(), (Product.id == ProductLocalization.alias().product_id) & (ProductLocalization.alias().lang_code == 'en'))\
         .outerjoin(ProductWeightOption, SerializedInventoryItem.variant_id == ProductWeightOption.id)\
         .order_by(Product.product_code, SerializedInventoryItem.item_uid)
        
        # The above joins for localization might need adjustment based on how you want to handle missing localizations.
        # A simpler approach for names if localizations are not always present:
        # Product.name.label('product_name_default') and then select COALESCE(pl_fr.name, p.name) in Python or SQL.
        # For simplicity here, I'll assume the joins work or you'd handle name fetching differently.
        # A more direct way if you have product_name on Product model:
        items_query_simpler = db.session.query(
            SerializedInventoryItem.item_uid, Product.product_code, Product.name.label("product_name"),
            ProductWeightOption.weight_grams.label('variant_weight_grams'), ProductWeightOption.sku_suffix.label('variant_sku_suffix'),
            SerializedInventoryItem.status, SerializedInventoryItem.batch_number, SerializedInventoryItem.production_date,
            SerializedInventoryItem.expiry_date, SerializedInventoryItem.received_at, SerializedInventoryItem.sold_at,
            SerializedInventoryItem.cost_price, SerializedInventoryItem.actual_weight_grams, SerializedInventoryItem.notes
        ).join(Product, SerializedInventoryItem.product_id == Product.id)\
         .outerjoin(ProductWeightOption, SerializedInventoryItem.variant_id == ProductWeightOption.id)\
         .order_by(Product.product_code, SerializedInventoryItem.item_uid)

        items_data = items_query_simpler.all()

        if not items_data:
            return jsonify(message="No serialized items found to export.", success=False), 404

        output = StringIO()
        writer = csv.writer(output)
        # Adjust headers if using the simpler query
        headers = ['Item UID', 'Product Code', 'Product Name', 'Variant Weight (g)', 'Variant SKU Suffix', 
                   'Status', 'Batch Number', 'Production Date', 'Expiry Date', 'Received At', 
                   'Sold At', 'Cost Price', 'Actual Weight (g)', 'Notes']
        writer.writerow(headers)

        for item_tuple in items_data:
            # Convert SQLAlchemy Row to something subscriptable or use getattr
            item_dict = {col.name: getattr(item_tuple, col.name) for col in item_tuple._fields}
            writer.writerow([
                item_dict.get('item_uid', ''), item_dict.get('product_code', ''), item_dict.get('product_name', ''),
                item_dict.get('variant_weight_grams', ''), item_dict.get('variant_sku_suffix', ''),
                item_dict.get('status', ''), item_dict.get('batch_number', ''),
                format_datetime_for_display(item_dict.get('production_date'), fmt='%Y-%m-%d') if item_dict.get('production_date') else '',
                format_datetime_for_display(item_dict.get('expiry_date'), fmt='%Y-%m-%d') if item_dict.get('expiry_date') else '',
                format_datetime_for_display(item_dict.get('received_at')) if item_dict.get('received_at') else '',
                format_datetime_for_display(item_dict.get('sold_at')) if item_dict.get('sold_at') else '',
                item_dict.get('cost_price', ''), item_dict.get('actual_weight_grams', ''), item_dict.get('notes', '')
            ])
        
        output.seek(0)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"maison_truvra_serialized_inventory_{timestamp}.csv"
        audit_logger.log_action(user_id=current_admin_id, action='export_serialized_items_csv_success', details=f"Exported {len(items_data)} items.", status='success', ip_address=request.remote_addr)
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
    # ... (file validation as before) ...

    imported_count = 0; updated_count = 0; failed_rows = []; processed_count = 0
    try:
        stream = StringIO(file.stream.read().decode("UTF-8"), newline=None)
        reader = csv.DictReader(stream)
        # ... (header validation as before) ...

        for row_num, row_dict in enumerate(reader, start=1):
            processed_count += 1
            product_code = row_dict.get('Product Code', '').strip().upper()
            item_uid_csv = row_dict.get('Item UID', '').strip()
            variant_sku_csv = row_dict.get('Variant SKU Suffix', '').strip().upper()
            status_csv = row_dict.get('Status', 'available').strip()
            # ... (parse other fields from row_dict) ...
            
            if not product_code:
                failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': 'Product Code missing.'})
                continue
            
            product = Product.query.filter(func.upper(Product.product_code) == product_code).first()
            if not product:
                failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': f'Product Code {product_code} not found.'})
                continue
            
            variant_id_db = None
            if variant_sku_csv:
                variant = ProductWeightOption.query.filter_by(product_id=product.id, sku_suffix=variant_sku_csv).first()
                if not variant:
                    failed_rows.append({'row': row_num, 'uid': item_uid_csv, 'error': f'Variant SKU {variant_sku_csv} not found for product {product_code}.'})
                    continue
                variant_id_db = variant.id
            
            # ... (parse dates, numbers from row_dict with error handling) ...
            production_date_db = parse_datetime_from_iso(row_dict.get('Production Date')) if row_dict.get('Production Date') else None
            expiry_date_db = parse_datetime_from_iso(row_dict.get('Expiry Date')) if row_dict.get('Expiry Date') else None


            existing_item = SerializedInventoryItem.query.filter_by(item_uid=item_uid_csv).first() if item_uid_csv else None
            
            if existing_item:
                existing_item.status = status_csv
                existing_item.product_id = product.id # Ensure product_id is correct if UID was reused
                existing_item.variant_id = variant_id_db
                # ... (update other fields for existing_item) ...
                existing_item.updated_at = datetime.now(timezone.utc)
                updated_count += 1
            else:
                uid_to_insert = item_uid_csv if item_uid_csv else f"{product.sku_prefix or product.product_code}-{uuid.uuid4().hex[:8].upper()}"
                # Ensure UID is unique if generated
                while not item_uid_csv and SerializedInventoryItem.query.filter_by(item_uid=uid_to_insert).first():
                    uid_to_insert = f"{product.sku_prefix or product.product_code}-{uuid.uuid4().hex[:8].upper()}"

                new_item = SerializedInventoryItem(
                    item_uid=uid_to_insert, product_id=product.id, variant_id=variant_id_db, status=status_csv,
                    # ... (set other fields for new_item) ...
                    batch_number=row_dict.get('Batch Number'), production_date=production_date_db, expiry_date=expiry_date_db,
                    cost_price=float(row_dict['Cost Price']) if row_dict.get('Cost Price') else None,
                    actual_weight_grams=float(row_dict['Actual Weight (g)']) if row_dict.get('Actual Weight (g)') else None,
                    notes=row_dict.get('Notes')
                )
                db.session.add(new_item)
                db.session.flush() # To get new_item.id
                record_stock_movement(db.session, product.id, 'import_csv_new', 1, variant_id_db, new_item.id, "CSV Import", current_admin_id)
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
    data = request.json
    product_code_str = data.get('product_code')
    variant_sku_suffix = data.get('variant_sku_suffix')
    quantity_change_str = data.get('quantity_change') # This is for aggregate stock
    reason = data.get('notes') # Assuming 'notes' field from form is the reason
    movement_type = data.get('movement_type') # e.g., 'manual_adjustment_in', 'damage_out'

    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not all([product_code_str, reason, movement_type]) or quantity_change_str is None:
        return jsonify(message="Product Code, reason, movement type, and quantity change are required.", success=False), 400

    product = Product.query.filter(func.upper(Product.product_code) == product_code_str.upper()).first()
    if not product:
        return jsonify(message=f"Product code '{product_code_str}' not found.", success=False), 404

    variant_id_db = None
    target_stock_entity = product # Default to product for stock update
    if variant_sku_suffix:
        variant = ProductWeightOption.query.filter_by(product_id=product.id, sku_suffix=variant_sku_suffix.upper()).first()
        if not variant:
            return jsonify(message=f"Variant SKU '{variant_sku_suffix}' not found for product '{product_code_str}'.", success=False), 404
        variant_id_db = variant.id
        target_stock_entity = variant # Update variant's stock

    try:
        quantity_change = int(quantity_change_str)
        # Define allowed movement types for aggregate adjustments
        allowed_aggregate_movements = ['ajustement_manuel', 'correction', 'perte', 'retour_non_commande', 'addition', 'creation_lot', 'decouverte_stock', 'retour_client']
        if movement_type not in allowed_aggregate_movements:
            return jsonify(message=f"Invalid movement type for aggregate stock: {movement_type}", success=False), 400
        
        if quantity_change != 0:
            if target_stock_entity.aggregate_stock_quantity is None: target_stock_entity.aggregate_stock_quantity = 0
            target_stock_entity.aggregate_stock_quantity += quantity_change
            if target_stock_entity.aggregate_stock_quantity < 0:
                # Decide policy: prevent going negative or allow and flag? For now, prevent.
                raise ValueError("Stock quantity cannot go below zero with this adjustment.")
        
        record_stock_movement(db.session, product.id, movement_type, quantity_change=quantity_change,
                              variant_id=variant_id_db, reason=reason, related_user_id=current_admin_id, notes=reason)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_success', target_type='product_stock', target_id=product.id, details=f"Stock for {product_code_str} (var: {variant_sku_suffix or 'N/A'}) adjusted by {quantity_change}. Reason: {reason}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Stock adjusted successfully", success=True), 200
    except ValueError as ve:
        db.session.rollback()
        return jsonify(message=f"Invalid data: {ve}", success=False), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adjusting stock for {product_code_str}: {e}", exc_info=True)
        return jsonify(message="Failed to adjust stock", success=False), 500

@inventory_bp.route('/product/<string:product_code>', methods=['GET'])
@admin_required
def get_admin_product_inventory_details(product_code):
    variant_sku_suffix = request.args.get('variant_sku_suffix')
    product = Product.query.filter(func.upper(Product.product_code) == product_code.upper()).first()
    if not product: return jsonify(message="Product not found", success=False), 404

    try:
        details = product.to_dict() # Assuming a to_dict method in your model for basic fields
        
        # Fetch variants if applicable
        if product.type == 'variable_weight':
            options = ProductWeightOption.query.filter_by(product_id=product.id).order_by(ProductWeightOption.weight_grams).all()
            details['current_stock_by_variant'] = [
                {'option_id': opt.id, 'weight_grams': opt.weight_grams, 'price': opt.price, 'sku_suffix': opt.sku_suffix, 
                 'aggregate_stock_quantity': opt.aggregate_stock_quantity} for opt in options
            ]
            details['calculated_total_variant_stock'] = sum(v.get('aggregate_stock_quantity', 0) for v in details['current_stock_by_variant'])
        
        # Fetch stock movements
        movements_query = StockMovement.query.filter_by(product_id=product.id)
        if variant_sku_suffix:
            target_variant = ProductWeightOption.query.filter_by(product_id=product.id, sku_suffix=variant_sku_suffix.upper()).first()
            if target_variant:
                movements_query = movements_query.filter_by(variant_id=target_variant.id)
            else: # Variant SKU provided but not found, return no movements for it
                details['stock_movements_log'] = []
        
        if not (variant_sku_suffix and not target_variant): # Only query if not a "variant not found" case
            movements_models = movements_query.order_by(StockMovement.movement_date.desc()).limit(100).all()
            details['stock_movements_log'] = [
                {**m.to_dict(), 'movement_date': format_datetime_for_display(m.movement_date)} # Assuming to_dict in StockMovement
                for m in movements_models
            ]
        
        return jsonify(details=details, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin inventory details for {product_code}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch inventory details", success=False), 500

@inventory_bp.route('/serialized/items/<string:item_uid>/status', methods=['PUT'])
@admin_required
def update_serialized_item_status(item_uid):
    data = request.json
    new_status = data.get('status')
    notes = data.get('notes', '')
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not new_status: return jsonify(message="New status required", success=False), 400
    allowed_statuses = ['available', 'damaged', 'recalled', 'reserved_internal', 'missing'] # 'allocated', 'sold' are usually system-set
    if new_status not in allowed_statuses:
        return jsonify(message=f"Invalid status. Allowed for manual update: {', '.join(allowed_statuses)}", success=False), 400

    try:
        item = SerializedInventoryItem.query.filter_by(item_uid=item_uid).first()
        if not item: return jsonify(message="Item not found", success=False), 404
        
        old_status = item.status
        if old_status == new_status:
            return jsonify(message="Status unchanged.", item_status=new_status, success=True), 200

        item.status = new_status
        current_item_notes = item.notes or ""
        if notes:
            item.notes = f"{current_item_notes}\n[{format_datetime_for_display(None)} by AdminID:{current_admin_id}]: Status {old_status} -> {new_status}. Reason: {notes}".strip()
        item.updated_at = datetime.now(timezone.utc)
        
        # Adjust aggregate stock if status changes to/from 'available'
        qty_change_agg = 0
        if old_status == 'available' and new_status != 'available': qty_change_agg = -1
        elif old_status != 'available' and new_status == 'available': qty_change_agg = 1
        
        if qty_change_agg != 0:
            target_stock_entity = None
            if item.variant_id:
                target_stock_entity = ProductWeightOption.query.get(item.variant_id)
            else: # Simple product
                target_stock_entity = Product.query.get(item.product_id)
            
            if target_stock_entity:
                if target_stock_entity.aggregate_stock_quantity is None: target_stock_entity.aggregate_stock_quantity = 0
                target_stock_entity.aggregate_stock_quantity += qty_change_agg
                # Add logic to prevent stock going negative if needed, or handle it
        
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_item_status_success', target_type='serialized_item', target_id=item_uid, details=f"Status of {item_uid} from '{old_status}' to '{new_status}'. Notes: {notes}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Status of {item_uid} updated to {new_status}.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating status for {item_uid}: {e}", exc_info=True)
        return jsonify(message="Failed to update item status", success=False), 500
