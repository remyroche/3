# backend/admin_api/routes.py
import os
import uuid
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from flask import request, jsonify, current_app, url_for, send_from_directory, abort as flask_abort
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import func, or_ # For OR conditions in SQLAlchemy queries

from .. import db # Import SQLAlchemy instance
from ..models import ( # Import all necessary models
    User, Category, Product, ProductImage, ProductWeightOption,
    Order, OrderItem, Review, Setting, SerializedInventoryItem,
    StockMovement, Invoice, InvoiceItem, ProfessionalDocument,
    ProductLocalization, CategoryLocalization, GeneratedAsset
)
from ..utils import (
    admin_required, format_datetime_for_display, parse_datetime_from_iso,
    generate_slug, allowed_file, get_file_extension, format_datetime_for_storage,
    generate_static_json_files # This function will also need to use SQLAlchemy models
)
from ..services.invoice_service import InvoiceService # Ensure this service is SQLAlchemy-aware

from . import admin_api_bp

# Helper to check for admin role from JWT claims (remains the same)
def is_admin_user():
    claims = get_jwt()
    return claims.get('role') == 'admin'

@admin_api_bp.route('/users/professionals', methods=['GET'])
@admin_required # Replaced jwt_required() with admin_required for role check
def get_professional_users_list():
    # if not is_admin_user(): # Redundant if @admin_required is effective
    #     return jsonify(message="Forbidden: Admin access required."), 403
    try:
        professionals = User.query.filter_by(role='b2b_professional')\
                                  .order_by(User.company_name, User.last_name, User.first_name).all()
        professionals_data = [{
            "id": user.id, "email": user.email, "first_name": user.first_name,
            "last_name": user.last_name, "company_name": user.company_name,
            "professional_status": user.professional_status
        } for user in professionals]
        return jsonify(professionals_data), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching professional users for admin: {e}", exc_info=True)
        return jsonify(message="Failed to fetch professional users.", success=False), 500

@admin_api_bp.route('/invoices/create', methods=['POST'])
@admin_required
def admin_create_manual_invoice():
    data = request.json
    # ... (validation as before) ...
    b2b_user_id = data.get('b2b_user_id')
    line_items_data = data.get('line_items')
    notes = data.get('notes')
    currency = data.get('currency', 'EUR')
    if not b2b_user_id or not line_items_data or not isinstance(line_items_data, list) or len(line_items_data) == 0:
        return jsonify(message="Missing required fields: b2b_user_id and at least one line_item.", success=False), 400

    try:
        invoice_service = InvoiceService() # Ensure InvoiceService uses db.session
        invoice_id, invoice_number = invoice_service.create_manual_invoice(
            b2b_user_id=b2b_user_id, 
            user_currency=currency, 
            line_items_data=line_items_data, 
            notes=notes
        )
        # pdf_full_url generation logic (remains similar, ensure InvoiceService saves path)
        pdf_full_url = None
        if invoice_id:
            invoice = Invoice.query.get(invoice_id)
            if invoice and invoice.pdf_path:
                 pdf_full_url = url_for('admin_api_bp.serve_asset', asset_relative_path=invoice.pdf_path, _external=True)

        return jsonify(success=True, message="Manual invoice created successfully.", invoice_id=invoice_id, invoice_number=invoice_number, pdf_url=pdf_full_url), 201
    except ValueError as ve: 
        return jsonify(message=str(ve), success=False), 400 
    except Exception as e:
        current_app.logger.error(f"Admin API error creating manual invoice: {e}", exc_info=True)
        return jsonify(message=f"An internal error occurred: {str(e)}", success=False), 500

@admin_api_bp.route('/login', methods=['POST'])
def admin_login():
    data = request.json; email = data.get('email'); password = data.get('password')
    audit_logger = current_app.audit_log_service
    if not email or not password:
        return jsonify(message="Email and password are required", success=False), 400
    
    try:
        admin_user = User.query.filter_by(email=email, role='admin').first()
        if admin_user and admin_user.check_password(password):
            if not admin_user.is_active:
                return jsonify(message="Admin account is inactive. Please contact support.", success=False), 403
            
            identity = admin_user.id
            additional_claims = {
                "role": admin_user.role, "email": admin_user.email, "is_admin": True,
                "first_name": admin_user.first_name, "last_name": admin_user.last_name
            }
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            user_info_to_return = {
                "id": admin_user.id, "email": admin_user.email, "prenom": admin_user.first_name,
                "nom": admin_user.last_name, "role": admin_user.role, "is_admin": True
            }
            audit_logger.log_action(user_id=admin_user.id, action='admin_login_success', target_type='user_admin', target_id=admin_user.id, status='success', ip_address=request.remote_addr)
            return jsonify(success=True, message="Admin login successful!", token=access_token, user=user_info_to_return), 200
        else:
            audit_logger.log_action(action='admin_login_fail_credentials', email=email, details="Invalid admin credentials.", status='failure', ip_address=request.remote_addr)
            return jsonify(message="Invalid admin email or password", success=False), 401
    except Exception as e:
        current_app.logger.error(f"Error during admin login for {email}: {e}", exc_info=True)
        audit_logger.log_action(action='admin_login_fail_server_error', email=email, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Admin login failed due to a server error", success=False), 500

@admin_api_bp.route('/dashboard/stats', methods=['GET'])
@admin_required
def get_dashboard_stats():
    audit_logger = current_app.audit_log_service
    current_admin_id = get_jwt_identity()
    try:
        total_users = db.session.query(func.count(User.id)).scalar()
        total_products = Product.query.filter_by(is_active=True).count()
        pending_order_statuses = ('paid', 'processing', 'awaiting_shipment')
        pending_orders = Order.query.filter(Order.status.in_(pending_order_statuses)).count()
        total_categories = Category.query.filter_by(is_active=True).count()
        pending_b2b_applications = User.query.filter_by(role='b2b_professional', professional_status='pending').count()
        
        stats = {
            "total_users": total_users, "total_products": total_products,
            "pending_orders": pending_orders, "total_categories": total_categories,
            "pending_b2b_applications": pending_b2b_applications, "success": True
        }
        audit_logger.log_action(user_id=current_admin_id, action='get_dashboard_stats', status='success', ip_address=request.remote_addr)
        return jsonify(stats=stats), 200 # Return as object with 'stats' key
    except Exception as e:
        current_app.logger.error(f"Error fetching dashboard stats: {e}", exc_info=True)
        return jsonify(message="Failed to fetch dashboard statistics", success=False), 500

# --- Category Management ---
@admin_api_bp.route('/categories', methods=['POST'])
@admin_required
def create_category():
    data = request.form.to_dict(); name = data.get('name'); description = data.get('description', ''); 
    parent_id_str = data.get('parent_id'); category_code = data.get('category_code', '').strip().upper();
    image_file = request.files.get('image_url'); is_active = data.get('is_active', 'true').lower() == 'true'
    current_user_id = get_jwt_identity(); audit_logger = current_app.audit_log_service

    if not name or not category_code:
        return jsonify(message="Name and Category Code are required", success=False), 400
    slug = generate_slug(name)
    image_filename_db = None

    try:
        if Category.query.filter_by(name=name).first(): return jsonify(message=f"Category name '{name}' already exists", success=False), 409
        if Category.query.filter_by(slug=slug).first(): return jsonify(message=f"Category slug '{slug}' already exists.", success=False), 409
        if Category.query.filter_by(category_code=category_code).first(): return jsonify(message=f"Category code '{category_code}' already exists.", success=False), 409

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(f"category_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
            upload_folder_categories = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories'); os.makedirs(upload_folder_categories, exist_ok=True)
            image_file.save(os.path.join(upload_folder_categories, filename)); image_filename_db = os.path.join('categories', filename)
        
        parent_id = int(parent_id_str) if parent_id_str and parent_id_str.strip() and parent_id_str.lower() != 'null' else None
        
        new_category = Category(name=name, description=description, parent_id=parent_id, slug=slug, 
                                image_url=image_filename_db, category_code=category_code, is_active=is_active)
        db.session.add(new_category)
        db.session.commit()
        
        try: generate_static_json_files() # This needs to be SQLAlchemy aware
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)
        
        audit_logger.log_action(user_id=current_user_id, action='create_category', target_type='category', target_id=new_category.id, details=f"Category '{name}' created.", status='success', ip_address=request.remote_addr)
        return jsonify(message="Category created successfully", category=new_category.to_dict() if hasattr(new_category, 'to_dict') else {'id': new_category.id, 'name': new_category.name}, success=True), 201 # Add a to_dict() method to your models
    except Exception as e: # Catch broader SQLAlchemy exceptions
        db.session.rollback()
        return jsonify(message=f"Failed to create category: {str(e)}", success=False), 500

@admin_api_bp.route('/categories', methods=['GET'])
@admin_required
def get_categories():
    try:
        categories_models = Category.query.order_by(Category.name).all()
        categories_data = []
        for cat in categories_models:
            cat_dict = {
                "id": cat.id, "name": cat.name, "description": cat.description, "parent_id": cat.parent_id,
                "slug": cat.slug, "image_url": cat.image_url, "category_code": cat.category_code,
                "is_active": cat.is_active, 
                "created_at": format_datetime_for_display(cat.created_at),
                "updated_at": format_datetime_for_display(cat.updated_at),
                "product_count": cat.products.filter_by(is_active=True).count(), # Example of relationship usage
                "image_full_url": None
            }
            if cat.image_url:
                cat_dict['image_full_url'] = url_for('serve_public_asset', filepath=cat.image_url, _external=True)
            categories_data.append(cat_dict)
        return jsonify(categories=categories_data, success=True), 200
    except Exception as e:
        return jsonify(message=f"Failed to fetch categories: {str(e)}", success=False), 500

# ... Other routes (GET category detail, PUT category, DELETE category) need similar SQLAlchemy conversion ...
# ... Product Management routes (POST, GET all, GET detail, PUT, DELETE) ...
# ... User Management routes ...
# ... Order Management routes ...
# ... Review Management routes ...
# ... Settings Management routes ...
# ... Detailed Inventory View ...
# ... Admin Asset Serving (serve_asset - this one might not need DB changes if it's just file system) ...
# ... Regenerate Static JSON (generate_static_json_files needs to use SQLAlchemy models) ...

# Example for DELETE category
@admin_api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    current_user_id = get_jwt_identity(); audit_logger = current_app.audit_log_service
    try:
        category_to_delete = Category.query.get(category_id)
        if not category_to_delete:
            return jsonify(message="Category not found", success=False), 404
        
        if category_to_delete.products.count() > 0: # Check relationship
            return jsonify(message=f"Category '{category_to_delete.name}' in use. Reassign products first.", success=False), 409
        
        # Image deletion logic remains similar
        if category_to_delete.image_url:
            full_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category_to_delete.image_url)
            if os.path.exists(full_image_path): os.remove(full_image_path)
            
        db.session.delete(category_to_delete)
        db.session.commit()
        
        try: generate_static_json_files()
        except Exception as e_gen: current_app.logger.error(f"Failed to regenerate static JSON files: {e_gen}", exc_info=True)
            
        audit_logger.log_action(user_id=current_user_id, action='delete_category', target_type='category', target_id=category_id, details=f"Category '{category_to_delete.name}' deleted.", status='success', ip_address=request.remote_addr)
        return jsonify(message=f"Category '{category_to_delete.name}' deleted successfully", success=True), 200
    except Exception as e: # Catch broader SQLAlchemy exceptions
        db.session.rollback()
        return jsonify(message=f"Failed to delete category: {str(e)}", success=False), 500

# --- Product Management (Example: GET all products) ---
@admin_api_bp.route('/products', methods=['GET'])
@admin_required
def get_products_admin():
    include_variants_param = request.args.get('include_variants', 'false').lower() == 'true'
    try:
        products_query = Product.query.outerjoin(Category).order_by(Product.name)
        products_models = products_query.all()
        products_data = []
        for p in products_models:
            p_dict = {
                "id": p.id, "name": p.name, "product_code": p.product_code, "sku_prefix": p.sku_prefix,
                "type": p.type, "base_price": p.base_price, "is_active": p.is_active,
                "category_name": p.category.name if p.category else None,
                "category_code": p.category.category_code if p.category else None,
                "main_image_full_url": url_for('serve_public_asset', filepath=p.main_image_url, _external=True) if p.main_image_url else None,
                "aggregate_stock_quantity": p.aggregate_stock_quantity,
                "created_at": format_datetime_for_display(p.created_at),
                "updated_at": format_datetime_for_display(p.updated_at),
                "price": p.base_price, # Alias for frontend
                "quantity": p.aggregate_stock_quantity # Alias for frontend
            }
            if p.type == 'variable_weight' or include_variants_param:
                options = p.weight_options.filter_by(is_active=True).order_by(ProductWeightOption.weight_grams).all()
                p_dict['weight_options'] = [{'option_id': opt.id, 'weight_grams': opt.weight_grams, 'price': opt.price, 'sku_suffix': opt.sku_suffix, 'aggregate_stock_quantity': opt.aggregate_stock_quantity} for opt in options]
                p_dict['variant_count'] = len(p_dict['weight_options'])
                if p.type == 'variable_weight' and p_dict['weight_options']:
                    p_dict['quantity'] = sum(opt.get('aggregate_stock_quantity', 0) for opt in p_dict['weight_options'])
            
            # Add additional images logic if needed
            p_dict['additional_images'] = [{'id': img.id, 'image_url': img.image_url, 'image_full_url': url_for('serve_public_asset', filepath=img.image_url, _external=True) if img.image_url else None, 'is_primary': img.is_primary} for img in p.images]

            products_data.append(p_dict)
        return jsonify(products=products_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin products: {e}", exc_info=True)
        return jsonify(message=f"Failed to fetch products for admin: {str(e)}", success=False), 500

# --- Admin Asset Serving (serve_asset - this one might not need DB changes if it's just file system) ---
# This route remains mostly the same as it deals with file system paths.
@admin_api_bp.route('/assets/<path:asset_relative_path>')
@admin_required 
def serve_asset(asset_relative_path):
    # ... (existing logic for serving assets, ensure paths in config are correct) ...
    # This function was already well-structured for file serving.
    if ".." in asset_relative_path or asset_relative_path.startswith("/"):
        current_app.logger.warning(f"Directory traversal attempt for admin asset: {asset_relative_path}")
        return flask_abort(404)
    asset_type_map = {
        'qr_codes': current_app.config['QR_CODE_FOLDER'], 'labels': current_app.config['LABEL_FOLDER'],
        'invoices': current_app.config['INVOICE_PDF_PATH'], 'professional_documents': current_app.config['PROFESSIONAL_DOCS_UPLOAD_PATH'],
        'products': os.path.join(current_app.config['UPLOAD_FOLDER'], 'products'),
        'categories': os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
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
        generate_static_json_files() # This function in utils.py needs to be SQLAlchemy aware
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json', status='success', ip_address=request.remote_addr)
        return jsonify(message="Static JSON files regenerated successfully.", success=True), 200
    except Exception as e:
        current_app.logger.error(f"Failed to regenerate static JSON files via API: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='regenerate_static_json_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message=f"Failed to regenerate static JSON files: {str(e)}", success=False), 500
