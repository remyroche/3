import os
import uuid
import sqlite3 # For explicit error handling
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..database import get_db_connection, query_db, record_stock_movement # record_stock_movement now requires db_conn
from ..services.asset_service import generate_qr_code_for_item, generate_item_passport, generate_product_label
from ..utils import format_datetime_for_storage # If needed for dates, or use isoformat()

inventory_bp = Blueprint('inventory', __name__, url_prefix='/api/inventory')

# Decorator for admin-only access (if not already in a shared utils or directly using admin_required from admin_api)
def admin_required_inventory(fn):
    @jwt_required()
    def wrapper(*args, **kwargs):
        # This assumes the admin_required decorator logic from admin_api.py 
        # would be suitable here, or you might have a shared one.
        # For now, let's assume a similar check.
        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        if claims.get('role') != 'admin':
            return jsonify(message="Administration rights required for inventory management."), 403
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


@inventory_bp.route('/serialized/receive', methods=['POST'])
@admin_required_inventory # Protect this critical endpoint
def receive_serialized_stock():
    data = request.json
    product_id = data.get('product_id')
    quantity_received = data.get('quantity_received')
    variant_id = data.get('variant_id') # Optional, for specific weight options
    batch_number = data.get('batch_number')
    production_date_str = data.get('production_date') # Expect ISO string
    expiry_date_str = data.get('expiry_date')     # Expect ISO string
    cost_price = data.get('cost_price')           # Cost per item
    notes = data.get('notes', '')

    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not all([product_id, quantity_received]):
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail', details="Product ID and quantity are required.", status='failure')
        return jsonify(message="Product ID and quantity are required"), 400

    try:
        quantity_received = int(quantity_received)
        if quantity_received <= 0:
            raise ValueError("Quantity received must be positive.")
        product_id = int(product_id)
        if variant_id: variant_id = int(variant_id)
        if cost_price: cost_price = float(cost_price)
    except ValueError as ve:
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail', details=f"Invalid data type: {ve}", status='failure')
        return jsonify(message=f"Invalid data type: {ve}"), 400

    db = get_db_connection()
    cursor = db.cursor()
    
    # Get product SKU prefix for generating item UIDs and asset names
    product_info = query_db("SELECT sku_prefix, name FROM products WHERE id = ?", [product_id], db_conn=db, one=True)
    if not product_info:
        audit_logger.log_action(user_id=current_admin_id, action='receive_serialized_stock_fail', target_type='product', target_id=product_id, details="Product not found.", status='failure')
        return jsonify(message="Product not found"), 404
    
    product_sku_prefix = product_info['sku_prefix']
    product_name_for_assets = product_info['name']


    # Prepare dates for DB (store as ISO string or let SQLite handle based on schema affinity)
    production_date_db = production_date_str # Assuming stored as TEXT ISO8601
    expiry_date_db = expiry_date_str       # Assuming stored as TEXT ISO8601

    generated_item_uids = []
    generated_assets_metadata = [] # To store paths for potential cleanup on error

    try:
        for i in range(quantity_received):
            item_uid = f"{product_sku_prefix}-{uuid.uuid4().hex[:12].upper()}"
            
            # 1. Generate Assets (QR Code, Passport, Label)
            # These functions should raise exceptions on failure.
            # Paths are relative to ASSET_STORAGE_PATH subfolders
            qr_code_relative_path = generate_qr_code_for_item(item_uid, product_id, product_name_for_assets)
            passport_relative_path = generate_item_passport(item_uid, product_id, product_name_for_assets, batch_number, production_date_str, expiry_date_str)
            # Label might be more generic per product, or specific per item if needed
            # label_relative_path = generate_product_label(product_id, item_uid=item_uid) # If item-specific label
            label_relative_path = None # Or generate a generic one if not item-specific, or skip if not needed here

            generated_assets_metadata.append({
                'qr': qr_code_relative_path, 
                'passport': passport_relative_path,
                # 'label': label_relative_path
            })

            # 2. Insert into serialized_inventory_items
            cursor.execute(
                """INSERT INTO serialized_inventory_items 
                   (item_uid, product_id, variant_id, batch_number, production_date, expiry_date, cost_price, notes, status, qr_code_url, passport_url, label_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_uid, product_id, variant_id, batch_number, production_date_db, expiry_date_db, cost_price, notes, 'available', 
                 qr_code_relative_path, passport_relative_path, label_relative_path)
            )
            serialized_item_id = cursor.lastrowid

            # 3. Record stock movement for this specific item
            record_stock_movement(
                db_conn=db, # Pass the connection
                product_id=product_id,
                variant_id=variant_id,
                serialized_item_id=serialized_item_id,
                movement_type='receive_serialized',
                quantity_change=1, # Each serialized item is one unit
                reason="Initial stock receipt of serialized item",
                related_user_id=current_admin_id
            )
            generated_item_uids.append(item_uid)

        # 4. Update aggregate stock on product/variant (optional, if also tracking aggregate)
        # This depends on your exact stock management strategy.
        # If serialized is the ONLY source of truth for these items, aggregate might not need +qty here.
        # If you do update aggregate, ensure it's done carefully.
        # Example:
        # if variant_id:
        #    cursor.execute("UPDATE product_weight_options SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", [quantity_received, variant_id])
        # else:
        #    cursor.execute("UPDATE products SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", [quantity_received, product_id])


        db.commit() # Commit only if all items processed and assets generated successfully
        
        audit_logger.log_action(
            user_id=current_admin_id,
            action='receive_serialized_stock_success',
            target_type='product',
            target_id=product_id,
            details=f"Received {quantity_received} serialized items. UIDs: {', '.join(generated_item_uids)}",
            status='success'
        )
        return jsonify(message=f"{quantity_received} serialized items received successfully.", item_uids=generated_item_uids), 201

    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error receiving serialized stock for product {product_id}: {e}")
        
        # Attempt to clean up any partially generated assets if an error occurred mid-batch
        # This is best-effort as file operations can also fail.
        asset_base = current_app.config['ASSET_STORAGE_PATH']
        for asset_paths in generated_assets_metadata:
            if asset_paths.get('qr'):
                try: os.remove(os.path.join(asset_base, asset_paths['qr']))
                except OSError: pass
            if asset_paths.get('passport'):
                try: os.remove(os.path.join(asset_base, asset_paths['passport']))
                except OSError: pass
            # if asset_paths.get('label'):
            #     try: os.remove(os.path.join(asset_base, asset_paths['label']))
            #     except OSError: pass
        
        audit_logger.log_action(
            user_id=current_admin_id,
            action='receive_serialized_stock_fail',
            target_type='product',
            target_id=product_id,
            details=f"Failed to receive stock: {str(e)}. Rolled back transaction. Attempted asset cleanup.",
            status='failure'
        )
        return jsonify(message=f"Failed to receive serialized stock: {str(e)}"), 500


@inventory_bp.route('/stock/adjust', methods=['POST'])
@admin_required_inventory
def adjust_stock():
    data = request.json
    product_id = data.get('product_id')
    variant_id = data.get('variant_id') # Optional
    adjustment_quantity = data.get('adjustment_quantity') # Can be positive or negative
    adjustment_weight_grams = data.get('adjustment_weight_grams') # For variable_weight products
    reason = data.get('reason')
    
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not product_id or not reason:
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail', details="Product ID and reason are required.", status='failure')
        return jsonify(message="Product ID and reason are required"), 400
    if adjustment_quantity is None and adjustment_weight_grams is None:
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail', target_type='product', target_id=product_id, details="Adjustment quantity or weight must be provided.", status='failure')
        return jsonify(message="Adjustment quantity or weight must be provided"), 400

    db = get_db_connection()
    try:
        product_id = int(product_id)
        if variant_id: variant_id = int(variant_id)
        if adjustment_quantity is not None: adjustment_quantity = int(adjustment_quantity)
        if adjustment_weight_grams is not None: adjustment_weight_grams = float(adjustment_weight_grams)

        # Determine movement type based on adjustment sign
        movement_type_qty = None
        if adjustment_quantity is not None:
            movement_type_qty = 'adjustment_in' if adjustment_quantity > 0 else 'adjustment_out'
        
        movement_type_weight = None
        if adjustment_weight_grams is not None:
            movement_type_weight = 'adjustment_in_weight' if adjustment_weight_grams > 0 else 'adjustment_out_weight'

        # This route is primarily for aggregate stock. Serialized items have their own status changes.
        # Update aggregate stock
        if variant_id:
            if adjustment_quantity is not None:
                query_db("UPDATE product_weight_options SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?", 
                         [adjustment_quantity, variant_id], db_conn=db, commit=False) # Commit handled below
            # Weight adjustments on variants might be more complex if they also have quantity
        else: # Product-level adjustment
            if adjustment_quantity is not None:
                query_db("UPDATE products SET aggregate_stock_quantity = aggregate_stock_quantity + ? WHERE id = ?",
                         [adjustment_quantity, product_id], db_conn=db, commit=False)
            if adjustment_weight_grams is not None:
                query_db("UPDATE products SET aggregate_stock_weight_grams = COALESCE(aggregate_stock_weight_grams, 0) + ? WHERE id = ?",
                         [adjustment_weight_grams, product_id], db_conn=db, commit=False)

        # Record stock movement
        # For quantity based
        if adjustment_quantity is not None:
            record_stock_movement(
                db_conn=db, # Pass the connection
                product_id=product_id,
                variant_id=variant_id,
                movement_type=movement_type_qty,
                quantity_change=adjustment_quantity,
                reason=reason,
                related_user_id=current_admin_id
            )
        # For weight based
        if adjustment_weight_grams is not None:
             record_stock_movement(
                db_conn=db,
                product_id=product_id,
                variant_id=variant_id, # May or may not apply depending on how weight is tracked
                movement_type=movement_type_weight,
                weight_change_grams=adjustment_weight_grams,
                reason=reason,
                related_user_id=current_admin_id
            )
        
        db.commit()
        audit_logger.log_action(
            user_id=current_admin_id,
            action='adjust_stock_success',
            target_type='product',
            target_id=product_id,
            details=f"Stock adjusted for product {product_id} (variant {variant_id}): Qty by {adjustment_quantity}, Weight by {adjustment_weight_grams}. Reason: {reason}",
            status='success'
        )
        return jsonify(message="Stock adjusted successfully"), 200

    except ValueError as ve:
        db.rollback() # Rollback if type conversion fails
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail', target_type='product', target_id=product_id, details=f"Invalid data type: {ve}", status='failure')
        return jsonify(message=f"Invalid data type: {ve}"), 400
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error adjusting stock for product {product_id}: {e}")
        audit_logger.log_action(user_id=current_admin_id, action='adjust_stock_fail', target_type='product', target_id=product_id, details=str(e), status='failure')
        return jsonify(message="Failed to adjust stock"), 500


@inventory_bp.route('/serialized/items', methods=['GET'])
@admin_required_inventory
def get_serialized_items():
    db = get_db_connection()
    # Add filters: product_id, status, batch_number, etc.
    product_id_filter = request.args.get('product_id', type=int)
    status_filter = request.args.get('status')

    query = """
        SELECT si.*, p.name as product_name, p.sku_prefix, pwo.sku_suffix as variant_sku_suffix
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
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY si.received_at DESC, si.id DESC"
    # Add pagination

    try:
        items_data = query_db(query, params, db_conn=db)
        items = [dict(row) for row in items_data] if items_data else []
        for item in items: # Format dates
            item['production_date'] = format_datetime_for_display(item['production_date'])
            item['expiry_date'] = format_datetime_for_display(item['expiry_date'])
            item['received_at'] = format_datetime_for_display(item['received_at'])
            item['sold_at'] = format_datetime_for_display(item['sold_at'])
            # Construct full asset URLs if needed by admin frontend
            if item.get('qr_code_url'):
                item['qr_code_full_url'] = f"{request.host_url.rstrip('/')}{admin_api_bp.url_prefix}/assets/{item['qr_code_url']}" # Assumes admin_api_bp is imported for url_prefix
            if item.get('passport_url'):
                item['passport_full_url'] = f"{request.host_url.rstrip('/')}{admin_api_bp.url_prefix}/assets/{item['passport_url']}"


        return jsonify(items), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching serialized items: {e}")
        return jsonify(message="Failed to fetch serialized items"), 500

@inventory_bp.route('/serialized/items/<string:item_uid>/status', methods=['PUT'])
@admin_required_inventory
def update_serialized_item_status(item_uid):
    data = request.json
    new_status = data.get('status')
    notes = data.get('notes', '') # Optional notes for status change

    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if not new_status:
        audit_logger.log_action(user_id=current_admin_id, action='update_item_status_fail', target_type='serialized_item', target_id=item_uid, details="New status is required.", status='failure')
        return jsonify(message="New status is required"), 400
    
    # Add validation for allowed statuses: e.g. ['available', 'damaged', 'recalled', 'reserved_internal']
    # 'allocated' and 'sold' are typically handled by order process.
    allowed_manual_statuses = ['available', 'damaged', 'recalled', 'reserved_internal', 'missing'] 
    if new_status not in allowed_manual_statuses:
        audit_logger.log_action(user_id=current_admin_id, action='update_item_status_fail', target_type='serialized_item', target_id=item_uid, details=f"Invalid status '{new_status}'. Allowed: {allowed_manual_statuses}", status='failure')
        return jsonify(message=f"Invalid status '{new_status}'. Allowed for manual update: {', '.join(allowed_manual_statuses)}"), 400

    db = get_db_connection()
    try:
        item_info = query_db("SELECT id, product_id, variant_id, status FROM serialized_inventory_items WHERE item_uid = ?", [item_uid], db_conn=db, one=True)
        if not item_info:
            audit_logger.log_action(user_id=current_admin_id, action='update_item_status_fail', target_type='serialized_item', target_id=item_uid, details="Serialized item not found.", status='failure')
            return jsonify(message="Serialized item not found"), 404

        old_status = item_info['status']
        if old_status == new_status:
            return jsonify(message="Item status is already set to this value.", item_status=new_status), 200 # Or 304 Not Modified

        cursor = db.cursor()
        # Append to notes rather than overwriting, or have a separate field for status change reason
        updated_notes = item_info.get('notes', '') or ''
        if notes:
             updated_notes += f"\nStatus change to {new_status} by admin {current_admin_id} on {datetime.now().isoformat()}: {notes}"
        
        cursor.execute("UPDATE serialized_inventory_items SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE item_uid = ?", 
                       [new_status, updated_notes.strip(), item_uid])
        
        # Record a stock movement for this status change
        # This might be redundant if status itself is the source of truth for serialized items.
        # However, for auditing or if aggregate stock is affected (e.g. 'damaged' removes from 'available aggregate')
        movement_type = f"status_change_{old_status}_to_{new_status}"
        quantity_impact = 0
        if old_status == 'available' and new_status != 'available':
            quantity_impact = -1 # Removed from available stock
        elif old_status != 'available' and new_status == 'available':
            quantity_impact = 1 # Added back to available stock
        
        if quantity_impact != 0:
            # This movement type is more for aggregate tracking if needed.
            # record_stock_movement(
            #     db_conn=db,
            #     product_id=item_info['product_id'],
            #     variant_id=item_info['variant_id'],
            #     serialized_item_id=item_info['id'],
            #     movement_type=movement_type,
            #     quantity_change=quantity_impact, 
            #     reason=f"Status changed by admin: {notes}",
            #     related_user_id=current_admin_id
            # )
            pass # Decide if aggregate stock movement recording is needed here.

        db.commit()
        audit_logger.log_action(
            user_id=current_admin_id,
            action='update_item_status_success',
            target_type='serialized_item',
            target_id=item_uid, # Using item_uid as target_id for log
            details=f"Status of item {item_uid} changed from '{old_status}' to '{new_status}'. Notes: {notes}",
            status='success'
        )
        return jsonify(message=f"Status of item {item_uid} updated to {new_status}."), 200

    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error updating status for item {item_uid}: {e}")
        audit_logger.log_action(user_id=current_admin_id, action='update_item_status_fail', target_type='serialized_item', target_id=item_uid, details=str(e), status='failure')
        return jsonify(message="Failed to update item status"), 500

