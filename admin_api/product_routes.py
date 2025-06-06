# backend/admin_api/product_routes.py
# Admin Product and Category Management

import os
import uuid
import json
from flask import request, jsonify, current_app, url_for
from flask_jwt_extended import get_jwt_identity
from werkzeug.utils import secure_filename
from sqlalchemy import func

from . import admin_api_bp
from .. import db
from ..models import (
    Category, Product, ProductImage, ProductWeightOption,
    ProductLocalization, CategoryLocalization, ProductTypeEnum, PreservationTypeEnum
)
from ..utils import (
    admin_required, generate_slug, allowed_file,
    get_file_extension, generate_static_json_files, sanitize_input
)

# --- Helper Function for Localization ---
def _update_or_create_product_localization(product_id, lang_code, data_dict):
    """Helper to update or create product localization records."""
    loc = ProductLocalization.query.filter_by(product_id=product_id, lang_code=lang_code).first()
    if not loc:
        loc = ProductLocalization(product_id=product_id, lang_code=lang_code)
        db.session.add(loc)
    
    # Assign attributes based on language
    if lang_code == 'fr':
        loc.name_fr = data_dict.get('name', getattr(loc, 'name_fr', None))
        loc.description_fr = data_dict.get('description', getattr(loc, 'description_fr', None))
        loc.long_description_fr = data_dict.get('long_description', getattr(loc, 'long_description_fr', None))
        loc.sensory_evaluation_fr = data_dict.get('sensory_evaluation', getattr(loc, 'sensory_evaluation_fr', None))
        loc.food_pairings_fr = data_dict.get('food_pairings', getattr(loc, 'food_pairings_fr', None))
        loc.species_fr = data_dict.get('species', getattr(loc, 'species_fr', None))
        loc.meta_title_fr = data_dict.get('meta_title', getattr(loc, 'meta_title_fr', None)) 
        loc.meta_description_fr = data_dict.get('meta_description', getattr(loc, 'meta_description_fr', None))
    elif lang_code == 'en':
        loc.name_en = data_dict.get('name_en', getattr(loc, 'name_en', None))
        loc.description_en = data_dict.get('description_en', getattr(loc, 'description_en', None))
        loc.long_description_en = data_dict.get('long_description_en', getattr(loc, 'long_description_en', None))
        loc.sensory_evaluation_en = data_dict.get('sensory_evaluation_en', getattr(loc, 'sensory_evaluation_en', None))
        loc.food_pairings_en = data_dict.get('food_pairings_en', getattr(loc, 'food_pairings_en', None))
        loc.species_en = data_dict.get('species_en', getattr(loc, 'species_en', None))
        loc.meta_title_en = data_dict.get('meta_title_en', getattr(loc, 'meta_title_en', None))
        loc.meta_description_en = data_dict.get('meta_description_en', getattr(loc, 'meta_description_en', None))
    return loc

# --- Category Management Routes ---
@admin_api_bp.route('/categories', methods=['POST'])
@admin_required
def create_category():
    data = request.form.to_dict()
    image_file = request.files.get('image_file')
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    name = sanitize_input(data.get('name'))
    category_code = sanitize_input(data.get('category_code', '')).strip().upper()

    if not name or not category_code:
        return jsonify(message="Name and Category Code are required", success=False), 400

    if Category.query.filter(func.lower(Category.name) == name.lower()).first():
        return jsonify(message="Category name already exists.", success=False), 409
    if Category.query.filter(func.upper(Category.category_code) == category_code).first():
        return jsonify(message="Category code already exists.", success=False), 409

    slug = generate_slug(name)
    if Category.query.filter_by(slug=slug).first():
        return jsonify(message=f"Category slug '{slug}' already exists. Try a different name.", success=False), 409

    image_filename_db = None
    if image_file and allowed_file(image_file.filename):
        filename = secure_filename(f"category_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
        upload_folder_cats = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
        os.makedirs(upload_folder_cats, exist_ok=True)
        image_path_full = os.path.join(upload_folder_cats, filename)
        image_file.save(image_path_full)
        image_filename_db = os.path.join('categories', filename).replace(os.sep, '/')

    parent_id = data.get('parent_id')
    parent_id = int(parent_id) if parent_id and parent_id.isdigit() else None

    new_category = Category(
        name=name,
        description=sanitize_input(data.get('description')),
        parent_id=parent_id,
        slug=slug,
        image_url=image_filename_db,
        category_code=category_code,
        is_active=str(data.get('is_active')).lower() == 'true'
    )

    try:
        db.session.add(new_category)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='create_category_success', target_type='category', target_id=new_category.id, details=f"Category '{name}' created.", status='success')
        generate_static_json_files()
        return jsonify(message="Category created successfully", category=new_category.to_dict(), success=True), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating category: {e}", exc_info=True)
        return jsonify(message=f"Failed to create category: {str(e)}", success=False), 500

@admin_api_bp.route('/categories', methods=['GET'])
@admin_required
def get_categories():
    try:
        categories_models = Category.query.order_by(Category.name).all()
        categories_data = []
        for cat_model in categories_models:
            cat_dict = cat_model.to_dict()
            if cat_model.image_url:
                try:
                    cat_dict['image_full_url'] = url_for('serve_public_asset', filepath=cat_model.image_url, _external=True)
                except Exception as e:
                    current_app.logger.warning(f"Could not generate URL for category image {cat_model.image_url}: {e}")
            categories_data.append(cat_dict)
        return jsonify(categories=categories_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching categories for admin: {e}", exc_info=True)
        return jsonify(message=f"Failed to fetch categories: {str(e)}", success=False), 500

@admin_api_bp.route('/categories/<int:category_id>', methods=['GET'])
@admin_required
def get_category_detail(category_id):
    category_model = Category.query.get_or_404(category_id)
    cat_dict = category_model.to_dict()
    if category_model.image_url:
        try:
            cat_dict['image_full_url'] = url_for('serve_public_asset', filepath=category_model.image_url, _external=True)
        except Exception as e:
            current_app.logger.warning(f"Could not generate URL for category image {category_model.image_url}: {e}")
    return jsonify(category=cat_dict, success=True), 200

@admin_api_bp.route('/categories/<int:category_id>', methods=['PUT'])
@admin_required
def update_category(category_id):
    category = Category.query.get_or_404(category_id)
    data = request.form.to_dict()
    image_file = request.files.get('image_file')
    remove_image = data.get('remove_image') == 'true'
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    name = sanitize_input(data.get('name', category.name))
    category_code = sanitize_input(data.get('category_code', category.category_code)).strip().upper()

    if not name or not category_code:
        return jsonify(message="Name and Category Code are required.", success=False), 400

    # Uniqueness checks
    if name != category.name and Category.query.filter(func.lower(Category.name) == name.lower(), Category.id != category_id).first():
        return jsonify(message="Category name already exists.", success=False), 409
    if category_code != category.category_code and Category.query.filter(func.upper(Category.category_code) == category_code, Category.id != category_id).first():
        return jsonify(message="Category code already exists.", success=False), 409

    new_slug = generate_slug(name)
    if new_slug != category.slug and Category.query.filter_by(slug=new_slug, id!=category_id).first():
        return jsonify(message=f"Category name (slug: '{new_slug}') already exists.", success=False), 409

    # Image handling
    if remove_image and category.image_url:
        old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category.image_url)
        if os.path.exists(old_image_path): os.remove(old_image_path)
        category.image_url = None
    elif image_file and allowed_file(image_file.filename):
        if category.image_url:
            old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category.image_url)
            if os.path.exists(old_image_path): os.remove(old_image_path)
        
        filename = secure_filename(f"category_{new_slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(image_file.filename)}")
        upload_folder_cats = os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
        os.makedirs(upload_folder_cats, exist_ok=True)
        image_file.save(os.path.join(upload_folder_cats, filename))
        category.image_url = os.path.join('categories', filename).replace(os.sep, '/')

    # Update fields
    category.name = name
    category.slug = new_slug
    category.category_code = category_code
    category.description = sanitize_input(data.get('description', category.description))
    parent_id = data.get('parent_id')
    category.parent_id = int(parent_id) if parent_id and parent_id.isdigit() else None
    category.is_active = str(data.get('is_active')).lower() == 'true'

    try:
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='update_category_success', target_type='category', target_id=category_id, details=f"Category '{name}' updated.", status='success')
        generate_static_json_files()
        return jsonify(message="Category updated successfully.", category=category.to_dict(), success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating category {category_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to update category: {str(e)}", success=False), 500


@admin_api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    if category.products.first():
        return jsonify(message=f"Cannot delete category '{category.name}' because it contains products.", success=False), 409
    if category.children.first():
        return jsonify(message=f"Cannot delete category '{category.name}' because it has sub-categories.", success=False), 409

    category_name_log = category.name
    if category.image_url:
        image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], category.image_url)
        if os.path.exists(image_path):
            os.remove(image_path)

    try:
        db.session.delete(category)
        db.session.commit()
        audit_logger.log_action(user_id=current_admin_id, action='delete_category_success', target_type='category', target_id=category_id, details=f"Category '{category_name_log}' deleted.", status='success')
        generate_static_json_files()
        return jsonify(message=f"Category '{category_name_log}' deleted successfully.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting category {category_id}: {e}", exc_info=True)
        return jsonify(message=f"Failed to delete category: {str(e)}", success=False), 500

# --- Product Management Routes ---
@admin_api_bp.route('/products', methods=['GET'])
@admin_required
def get_products_admin():
    include_variants = request.args.get('include_variants', 'false').lower() == 'true'
    try:
        products_models = Product.query.order_by(Product.name).all()
        products_data = []
        for p_model in products_models:
            product_dict = p_model.to_dict()
            if p_model.main_image_url:
                try: product_dict['main_image_full_url'] = url_for('serve_public_asset', filepath=p_model.main_image_url, _external=True)
                except Exception as e: current_app.logger.warning(f"URL gen error for main image {p_model.main_image_url}: {e}")
            
            if include_variants and p_model.type == ProductTypeEnum.VARIABLE_WEIGHT:
                product_dict['weight_options'] = [opt.to_dict() for opt in p_model.weight_options]
                product_dict['variant_count'] = len(product_dict['weight_options'])
            
            products_data.append(product_dict)
        return jsonify(products=products_data, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin products list: {e}", exc_info=True)
        return jsonify(message="Failed to fetch products list.", success=False), 500

@admin_api_bp.route('/products', methods=['POST'])
@admin_required
def create_product_admin():
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    data = request.form.to_dict()
    main_image_file = request.files.get('main_image_file')

    if not data.get('name') or not data.get('product_code') or not data.get('category_id'):
        return jsonify(message="Name (FR), Product Code, and Category are required.", success=False), 400

    if Product.query.filter(func.upper(Product.product_code) == data['product_code'].upper()).first():
        return jsonify(message=f"Product Code '{data['product_code']}' already exists.", success=False), 409
    
    slug = generate_slug(data['name'])
    if Product.query.filter_by(slug=slug).first():
        return jsonify(message=f"A product with a similar name (slug: '{slug}') already exists.", success=False), 409
        
    try:
        main_image_db_path = None
        if main_image_file and allowed_file(main_image_file.filename):
            filename = secure_filename(f"product_{slug}_{uuid.uuid4().hex[:8]}.{get_file_extension(main_image_file.filename)}")
            upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'products')
            os.makedirs(upload_folder, exist_ok=True)
            main_image_file.save(os.path.join(upload_folder, filename))
            main_image_db_path = os.path.join('products', filename).replace(os.sep, '/')

        new_product = Product(
            name=sanitize_input(data['name']),
            product_code=sanitize_input(data['product_code']).upper(),
            slug=slug,
            category_id=int(data['category_id']),
            type=ProductTypeEnum(data.get('type', 'simple')),
            base_price=float(data['price']) if data.get('price') else None,
            is_active=str(data.get('is_active', 'true')).lower() == 'true',
            is_featured=str(data.get('is_featured', 'false')).lower() == 'true',
            main_image_url=main_image_db_path
            # ... add other fields from form ...
        )
        db.session.add(new_product)
        db.session.flush()

        loc_data_fr = { 'name': new_product.name, 'description': data.get('description'), 'long_description': data.get('long_description') }
        _update_or_create_product_localization(new_product.id, 'fr', loc_data_fr)
        
        loc_data_en = { 'name_en': data.get('name_en'), 'description_en': data.get('description_en'), 'long_description_en': data.get('long_description_en') }
        if any(loc_data_en.values()):
            _update_or_create_product_localization(new_product.id, 'en', loc_data_en)

        db.session.commit()
        generate_static_json_files()
        audit_logger.log_action(user_id=current_user_id, action='create_product_admin_success', target_type='product', target_id=new_product.id, details=f"Product '{new_product.name}' created.", status='success')
        return jsonify(message="Product created successfully", product=new_product.to_dict(), success=True), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating product: {e}", exc_info=True)
        return jsonify(message="Server error while creating product.", error=str(e), success=False), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['PUT'])
@admin_required
def update_product_admin(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.form.to_dict()
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    # Update logic from the monolithic routes.py should be adapted here.
    # This involves updating product fields, handling image uploads/deletions,
    # and updating localizations.

    try:
        # Example: Updating a simple field
        product.name = sanitize_input(data.get('name', product.name))
        # ... update all other fields from 'data' similar to create_product_admin ...
        
        db.session.commit()
        generate_static_json_files()
        audit_logger.log_action(user_id=current_admin_id, action='update_product_admin_success', target_type='product', target_id=product_id, details=f"Product '{product.name}' updated.", status='success')
        return jsonify(message="Product updated successfully", product=product.to_dict(), success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating product {product_id}: {e}", exc_info=True)
        return jsonify(message="Server error while updating product.", error=str(e), success=False), 500
    
@admin_api_bp.route('/products/<int:product_id>/options', methods=['PUT'])
@admin_required
def update_product_options_admin(product_id):
    product = Product.query.get_or_404(product_id)
    if product.type != ProductTypeEnum.VARIABLE_WEIGHT:
        return jsonify(message="Options can only be managed for 'variable_weight' products.", success=False), 400

    data = request.json
    options_data = data.get('options', [])
    
    existing_option_ids_from_payload = {opt.get('option_id') for opt in options_data if opt.get('option_id')}

    try:
        # Delete options not present in the payload
        for existing_opt in list(product.weight_options):
            if existing_opt.id not in existing_option_ids_from_payload:
                db.session.delete(existing_opt)

        for opt_data in options_data:
            weight = float(opt_data.get('weight_grams'))
            price = float(opt_data.get('price'))
            sku_suffix = sanitize_input(opt_data.get('sku_suffix', '')).strip().upper()
            option_id = opt_data.get('option_id')

            if not all([weight, price, sku_suffix]):
                raise ValueError("Weight, price, and SKU suffix are required for each option.")

            if option_id: # Update existing
                option = ProductWeightOption.query.get(option_id)
                if option and option.product_id == product_id:
                    option.weight_grams = weight
                    option.price = price
                    option.sku_suffix = sku_suffix
            else: # Create new
                new_option = ProductWeightOption(
                    product_id=product_id,
                    weight_grams=weight,
                    price=price,
                    sku_suffix=sku_suffix
                )
                db.session.add(new_option)

        db.session.commit()
        return jsonify(message="Product weight options updated successfully.", success=True), 200
    except ValueError as ve:
        db.session.rollback()
        return jsonify(message=str(ve), success=False), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update product options for product ID {product_id}: {e}", exc_info=True)
        return jsonify(message="Failed to update product options due to a server error.", success=False), 500

@admin_api_bp.route('/products/<int:product_id>', methods=['DELETE'])
@admin_required
def delete_product_admin(product_id):
    product = Product.query.get_or_404(product_id)
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service

    # Check for related orders before deleting
    if product.order_items.first():
        return jsonify(message="Cannot delete product as it is part of existing orders.", success=False), 409
    
    # Collect all image paths to delete from the filesystem
    image_paths_to_delete = []
    if product.main_image_url:
        image_paths_to_delete.append(os.path.join(current_app.config['UPLOAD_FOLDER'], product.main_image_url))
    
    for img in product.images:
        if img.image_url:
            image_paths_to_delete.append(os.path.join(current_app.config['UPLOAD_FOLDER'], img.image_url))

    product_name_for_log = product.name

    try:
        # The database relationships are set up with cascade="all, delete-orphan",
        # so deleting the product will automatically delete related ProductImage,
        # ProductWeightOption, and ProductLocalization records.
        db.session.delete(product)
        db.session.commit()

        # After successful DB deletion, delete the physical files
        for path in image_paths_to_delete:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError as e:
                current_app.logger.error(f"Error deleting product image file {path}: {e}", exc_info=True)
        
        audit_logger.log_action(user_id=current_admin_id, action='delete_product_success', target_type='product', target_id=product_id, details=f"Product '{product_name_for_log}' and its assets deleted.", status='success')
        
        generate_static_json_files()
        
        return jsonify(message=f"Product '{product_name_for_log}' deleted successfully.", success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting product {product_id}: {e}", exc_info=True)
        return jsonify(message="Server error while deleting product.", error=str(e), success=False), 500
