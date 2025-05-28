import os
import uuid
import sqlite3
from flask import Blueprint, request, jsonify, current_app, g
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..database import get_db_connection, query_db, record_stock_movement
from ..services.asset_service import generate_qr_code_for_item, generate_item_passport # generate_product_label might be used too
from ..utils import admin_required, format_datetime_for_display, parse_datetime_from_iso, format_datetime_for_storage

inventory_bp = Blueprint('inventory_bp', __name__, url_prefix='/api/inventory') # Keep /api/inventory prefix


@inventory_bp.route('/serialized/receive', methods=['POST'])
@admin_required # Use centralized admin_required
def receive_serialized_stock():
    data = request.json
    product_id_str = data.get('product_id')
    quantity_received_str = data.get('quantity_received')
    variant_id_str = data.get('variant_id') 
    batch_number = data.get('batch_number')
    production_date_str = data.get('production_date') 
    expiry_date_str = data.get('expiry_date')     
    cost_price_str = data.get('cost_price')          
    notes = data.get('notes', '')

    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not all([product_id_str, quantity_received_str]):
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail', details="Product ID and quantity are required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Product ID and quantity are required"), 400

    try:
        product_id = int(product_id_str)
        quantity_received = int(quantity_received_str)
        if quantity_received <= 0: raise ValueError("Quantity received must be positive.")
        variant_id = int(variant_id_str) if variant_id_str else None
        cost_price = float(cost_price_str) if cost_price_str else None
    except ValueError as ve:
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail', details=f"Invalid data type: {ve}", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Invalid data type: {ve}"), 400

    db = get_db_connection()
    cursor = db.cursor()
    
    product_info = query_db("SELECT sku_prefix, name FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
    if not product_info:
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail', target_type='product', target_id=product_id, details="Product not found.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Product not found"), 404
    
    product_sku_prefix = product_info['sku_prefix']
    product_name_for_assets = product_info['name']

    production_date_db = format_datetime_for_storage(parse_datetime_from_iso(production_date_str)) if production_date_str else None
    expiry_date_db = format_datetime_for_storage(parse_datetime_from_iso(expiry_date_str)) if expiry_date_str else None

    generated_item_uids = []
    generated_assets_metadata = [] 

    try:
        for _ in range(quantity_received):
            item_uid = f"{product_sku_prefix}-{uuid.uuid4().hex[:12].upper()}"
            
            # Ensure asset service functions are called within app context if they rely on current_app
            with current_app.app_context():
                qr_code_relative_path = generate_qr_code_for_item(item_uid, product_id, product_name_for_assets)
                passport_relative_path = generate_item_passport(item_uid, product_id, product_name_for_assets, batch_number, production_date_str, expiry_date_str)
            
            generated_assets_metadata.append({'qr': qr_code_relative_path, 'passport': passport_relative_path})

            cursor.execute(
                """INSERT INTO serialized_inventory_items 
                   (item_uid, product_id, variant_id, batch_number, production_date, expiry_date, cost_price, notes, status, qr_code_url, passport_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", # Removed label_url for now, can be added if needed
                (item_uid, product_id, variant_id, batch_number, production_date_db, expiry_date_db, cost_price, notes, 'available', 
                 qr_code_relative_path, passport_relative_path)
            )
            serialized_item_id = cursor.lastrowid

            record_stock_movement(db, product_id, 'receive_serialized', quantity_change=1, variant_id=variant_id, serialized_item_id=serialized_item_id, reason="Initial stock receipt of serialized item", related_user_id=current_admin_id)
            generated_item_uids.append(item_uid)

        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_success', target_type='product', target_id=product_id, details=f"Received {quantity_received} items. UIDs: {', '.join(generated_item_uids)}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"{quantity_received} serialized items received successfully.", item_uids=generated_item_uids, success=True), 201

    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error receiving serialized stock for product {product_id}: {e}", exc_info=True)
        
        asset_base = current_app.config['ASSET_STORAGE_PATH']
        for asset_paths in generated_assets_metadata:
            if asset_paths.get('qr'): try: os.remove(os.path.join(asset_base, asset_paths['qr'])) 
            except OSError: pass
            if asset_paths.get('passport'): try: os.remove(os.path.join(asset_base, asset_paths['passport']))
            except OSError: pass
        
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail_exception', target_type='product', target_id=product_id, details=f"Failed: {str(e)}. Rolled back. Assets cleaned.", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to receive serialized stock: {str(e)}", success=False), 500

@inventory_bp.route('/stock/adjust', methods=['POST']) # For aggregate stock
@admin_required
def adjust_stock():
    data = request.json
    product_id_str = data.get('product_id')
    variant_id_str = data.get('variant_id')
    adjustment_quantity_str = data.get('quantity_change') # Renamed from form for clarity
    # adjustment_weight_grams_str = data.get('adjustment_weight_grams') # If tracking aggregate weight
    reason = data.get('notes') # 'notes' from form is the reason
    movement_type = data.get('movement_type') # e.g. 'ajustement_manuel', 'perte', 'correction'
    
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not product_id_str or not reason or not movement_type:
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail_missing_fields', details="Product ID, reason, and movement type are required.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Product ID, reason, and movement type are required"), 400
    if adjustment_quantity_str is None: # and adjustment_weight_grams_str is None:
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail_no_adjustment', target_type='product', target_id=product_id_str, details="Adjustment quantity must be provided.", status='failure', ip_address=request.remote_addr)
        return jsonify(message="Adjustment quantity must be provided"), 400

    db = get_db_connection()
    try:
        product_id = int(product_id_str)
        variant_id = int(variant_id_str) if variant_id_str else None
        adjustment_quantity = int(adjustment_quantity_str) if adjustment_quantity_str is not None else 0
        # adjustment_weight_grams = float(adjustment_weight_grams_str) if adjustment_weight_grams_str is not None else 0.0

        # Validate movement_type
        allowed_movement_types = ['ajustement_manuel', 'correction', 'perte', 'retour_non_commande', 'addition', 'creation_lot', 'decouverte_stock', 'retour_client'] # Expanded list
        if movement_type not in allowed_movement_types:
            audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail_invalid_type', target_type='product', target_id=product_id, details=f"Invalid movement type: {movement_type}", status='failure', ip_address=request.remote_addr)
            return jsonify(message=f"Invalid movement type: {movement_type}"),400
        
        # Update aggregate stock
        if variant_id:
            if adjustment_quantity != 0:
                query_db("UPDATE product_weight_options SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", [adjustment_quantity, variant_id], db_conn=db, commit=False)
        else: 
            if adjustment_quantity != 0:
                query_db("UPDATE products SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", [adjustment_quantity, product_id], db_conn=db, commit=False)
            # if adjustment_weight_grams != 0:
            #     query_db("UPDATE products SET aggregate_stock_weight_grams = COALESCE(aggregate_stock_weight_grams, 0) + ? WHERE id = ?", [adjustment_weight_grams, product_id], db_conn=db, commit=False)

        record_stock_movement(db, product_id, movement_type, quantity_change=adjustment_quantity, variant_id=variant_id, reason=reason, related_user_id=current_admin_id, notes=reason)
        
        db.commit()
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_success', target_type='product', target_id=product_id, details=f"Stock for product {product_id} (variant {variant_id}) adjusted by Qty: {adjustment_quantity}. Reason: {reason}", status='success', ip_address=request.remote_addr)
        return jsonify(message="Stock adjusted successfully", success=True), 200

    except ValueError as ve:
        db.rollback()
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail_value_error', target_type='product', target_id=product_id_str, details=f"Invalid data type: {ve}", status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Invalid data type: {ve}", success=False), 400
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error adjusting stock for product {product_id_str}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail_exception', target_type='product', target_id=product_id_str, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to adjust stock", success=False), 500

@inventory_bp.route('/product/<int:product_id>', methods=['GET']) # For admin overview
@admin_required
def get_admin_product_inventory_details(product_id):
    db = get_db_connection()
    variant_id_filter = request.args.get('variant_id', type=int)

    try:
        product_info = query_db("SELECT id, name, type, aggregate_stock_quantity, aggregate_stock_weight_grams FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
        if not product_info:
            return jsonify(message="Product not found"), 404

        inventory_details = dict(product_info)
        
        if product_info['type'] == 'variable_weight':
            options_data = query_db("SELECT id as option_id, weight_grams, sku_suffix, aggregate_stock_quantity FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", [product_id], db_conn=db)
            inventory_details['current_stock_by_variant'] = [dict(opt) for opt in options_data] if options_data else []
            # Sum of variants for total if main product aggregate_stock_quantity is not the source of truth for variants
            inventory_details['calculated_total_variant_stock'] = sum(v.get('aggregate_stock_quantity',0) for v in inventory_details['current_stock_by_variant'])

        # Fetch stock movements
        movements_query = "SELECT * FROM stock_movements WHERE product_id = ?"
        movements_params = [product_id]
        if variant_id_filter:
            movements_query += " AND variant_id = ?"
            movements_params.append(variant_id_filter)
        movements_query += " ORDER BY movement_date DESC LIMIT 100" # Limit for performance
        
        movements_data = query_db(movements_query, movements_params, db_conn=db)
        inventory_details['stock_movements_log'] = [dict(m) for m in movements_data] if movements_data else []
        for m_log in inventory_details['stock_movements_log']:
            m_log['movement_date'] = format_datetime_for_display(m_log['movement_date'])

        return jsonify(inventory_details), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin inventory details for product {product_id}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch inventory details"), 500

@inventory_bp.route('/serialized/items', methods=['GET'])
@admin_required
def get_serialized_items():
    db = get_db_connection()
    product_id_filter = request.args.get('product_id', type=int)
    status_filter = request.args.get('status')
    item_uid_search = request.args.get('item_uid')

    query = """
        SELECT si.*, p.name as product_name, p.sku_prefix, 
               pwo.sku_suffix as variant_sku_suffix, pwo.weight_grams as variant_weight_grams
        FROM serialized_inventory_items si
        JOIN products p ON si.product_id = p.id
        LEFT JOIN product_weight_options pwo ON si.variant_id = pwo.id
    """
    conditions = []
    params = []

    if product_id_filter:
        conditions.append("si.product_id = ?")
        params.append(product_id_filter)
    if status_filter:
        conditions.append("si.status = ?")
        params.append(status_filter)
    if item_uid_search:
        conditions.append("si.item_uid LIKE ?")
        params.append(f"%{item_uid_search}%")
    
    if conditions: query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY si.received_at DESC, si.id DESC LIMIT 100" # Add pagination

    try:
        items_data = query_db(query, params, db_conn=db)
        items = [dict(row) for row in items_data] if items_data else []
        for item in items:
            item['production_date'] = format_datetime_for_display(item['production_date'])
            item['expiry_date'] = format_datetime_for_display(item['expiry_date'])
            item['received_at'] = format_datetime_for_display(item['received_at'])
            item['sold_at'] = format_datetime_for_display(item['sold_at'])
            item['updated_at'] = format_datetime_for_display(item['updated_at'])
            if item.get('qr_code_url'):
                item['qr_code_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item['qr_code_url'], _external=True)
            if item.get('passport_url'):
                item['passport_full_url'] = url_for('admin_api_bp.serve_asset', asset_relative_path=item['passport_url'], _external=True)
        return jsonify(items), 200
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
        if notes: updated_notes_db += f"\n[{format_datetime_for_display(datetime.now(timezone.utc))} by AdminID:{current_admin_id}]: Status changed from {old_status} to {new_status}. Reason: {notes}"
        
        query_db("UPDATE serialized_inventory_items SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE item_uid = ?", [new_status, updated_notes_db.strip(), item_uid], db_conn=db, commit=True)
        
        # Optionally, record an aggregate stock movement if this status change affects availability
        # For example, if 'damaged' makes an 'available' item unavailable.
        # This depends on how aggregate stock is managed alongside serialized stock.
        # record_stock_movement(db, item_info['product_id'], ...)

        audit_logger.log_action(user_id=current_admin_id, action='update_item_status_success', target_type='serialized_item', target_id=item_uid, details=f"Status of {item_uid} from '{old_status}' to '{new_status}'. Notes: {notes}", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Status of item {item_uid} updated to {new_status}.", success=True), 200
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating status for item {item_uid}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='update_item_status_fail_exception', target_type='serialized_item', target_id=item_uid, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to update item status", success=False), 500