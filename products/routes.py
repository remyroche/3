# backend/products/routes.py
from flask import Blueprint, request, jsonify, current_app, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, or_

from .. import db
from ..models import Product, Category, ProductImage, ProductWeightOption, Review, User
from ..utils import format_datetime_for_display, generate_slug

products_bp = Blueprint('products_bp', __name__, url_prefix='/api/products')

def get_locale():
    # Basic language negotiation, can be enhanced
    return request.headers.get('Accept-Language', 'en').split(',')[0].split('-')[0]

@products_bp.route('/', methods=['GET'])
def get_products():
    lang = get_locale() # For future localized fields from ProductLocalization

    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        category_slug = request.args.get('category_slug')
        search_term = request.args.get('search')
        sort_by = request.args.get('sort', 'name_asc') # e.g., name_asc, name_desc, price_asc, price_desc, date_desc
        featured_str = request.args.get('featured')

        if page < 1 or per_page < 1:
            return jsonify(message='Page and per_page parameters must be positive integers.', success=False), 400

        query = Product.query.join(Category, Product.category_id == Category.id)\
                             .filter(Product.is_active == True, Category.is_active == True) # Also filter by active category

        if category_slug:
            query = query.filter(Category.slug == category_slug)
        
        if search_term:
            term_like = f"%{search_term.lower()}%"
            query = query.filter(
                or_(
                    func.lower(Product.name).like(term_like),
                    func.lower(Product.description).like(term_like),
                    func.lower(Product.product_code).like(term_like)
                    # Add ProductLocalization search here if implementing
                )
            )
        
        featured = None
        if featured_str:
            if featured_str.lower() == 'true': featured = True
            elif featured_str.lower() == 'false': featured = False
        if featured is not None:
            query = query.filter(Product.is_featured == featured)

        # Sorting logic
        if sort_by == 'name_desc': query = query.order_by(Product.name.desc())
        elif sort_by == 'price_asc': query = query.order_by(Product.base_price.asc()) # Assumes simple products or a representative price
        elif sort_by == 'price_desc': query = query.order_by(Product.base_price.desc())
        elif sort_by == 'date_desc': query = query.order_by(Product.created_at.desc())
        else: query = query.order_by(Product.name.asc()) # Default: name_asc

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        products_models = pagination.items
        total_products = pagination.total
        total_pages = pagination.pages

        products_list = []
        for p_model in products_models:
            product_dict = {
                'id': p_model.id, 'name': p_model.name, 'description': p_model.description,
                'slug': p_model.slug, 'base_price': p_model.base_price, 'currency': p_model.currency,
                'main_image_url': p_model.main_image_url, 'type': p_model.type,
                'unit_of_measure': p_model.unit_of_measure, 'is_featured': p_model.is_featured,
                'aggregate_stock_quantity': p_model.aggregate_stock_quantity,
                'aggregate_stock_weight_grams': p_model.aggregate_stock_weight_grams,
                'product_code': p_model.product_code,
                'category_name': p_model.category.name if p_model.category else None,
                'category_slug': p_model.category.slug if p_model.category else None,
                'category_code': p_model.category.category_code if p_model.category else None,
                'main_image_full_url': None
            }
            if p_model.main_image_url:
                try:
                    product_dict['main_image_full_url'] = url_for('serve_public_asset', filepath=p_model.main_image_url, _external=True)
                except Exception as e_url:
                    current_app.logger.warning(f"Could not generate URL for product image {p_model.main_image_url}: {e_url}")
            
            if p_model.type == 'variable_weight':
                options = ProductWeightOption.query.filter_by(product_id=p_model.id, is_active=True).order_by(ProductWeightOption.weight_grams).all()
                product_dict['weight_options'] = [
                    {'option_id': opt.id, 'weight_grams': opt.weight_grams, 'price': opt.price, 
                     'sku_suffix': opt.sku_suffix, 'aggregate_stock_quantity': opt.aggregate_stock_quantity} 
                    for opt in options
                ]
            products_list.append(product_dict)
        
        return jsonify({
            "products": products_list, "page": page, "per_page": per_page,
            "total_products": total_products, "total_pages": total_pages, "success": True
        }), 200

    except ValueError as ve:
        current_app.logger.warning(f"Invalid request parameters for product listing: {ve}")
        return jsonify(message=str(ve), success=False), 400
    except Exception as e:
        current_app.logger.error(f"Error fetching products list: {e}", exc_info=True)
        return jsonify(message="Failed to fetch products", success=False), 500

@products_bp.route('/<string:slug_or_code>', methods=['GET'])
def get_product_detail_by_slug_or_code(slug_or_code):
    # Try fetching by slug first
    product_model = Product.query.filter(Product.is_active == True)\
                                 .filter(Product.slug == slug_or_code).first()
    if not product_model:
        # If not found by slug, try by product_code
        product_model = Product.query.filter(Product.is_active == True)\
                                     .filter(func.upper(Product.product_code) == slug_or_code.upper()).first()

    if not product_model:
        return jsonify(message="Product not found or not active", success=False), 404

    try:
        product_details = {
            'id': product_model.id, 'name': product_model.name, 'description': product_model.description,
            'slug': product_model.slug, 'base_price': product_model.base_price, 'currency': product_model.currency,
            'main_image_url': product_model.main_image_url, 'type': product_model.type,
            'unit_of_measure': product_model.unit_of_measure, 'is_featured': product_model.is_featured,
            'aggregate_stock_quantity': product_model.aggregate_stock_quantity,
            'aggregate_stock_weight_grams': product_model.aggregate_stock_weight_grams,
            'product_code': product_model.product_code,
            'category_name': product_model.category.name if product_model.category else None,
            'category_slug': product_model.category.slug if product_model.category else None,
            'category_code': product_model.category.category_code if product_model.category else None,
            'created_at': format_datetime_for_display(product_model.created_at),
            'updated_at': format_datetime_for_display(product_model.updated_at),
            'main_image_full_url': None,
            'additional_images': [],
            'weight_options': [],
            'reviews': []
        }

        if product_model.main_image_url:
            try:
                product_details['main_image_full_url'] = url_for('serve_public_asset', filepath=product_model.main_image_url, _external=True)
            except Exception as e_url:
                current_app.logger.warning(f"Could not generate URL for product image {product_model.main_image_url}: {e_url}")

        for img_model in product_model.images.order_by(ProductImage.is_primary.desc(), ProductImage.id.asc()).all():
            img_dict = {'id': img_model.id, 'image_url': img_model.image_url, 'alt_text': img_model.alt_text, 'is_primary': img_model.is_primary, 'image_full_url': None}
            if img_model.image_url:
                try:
                    img_dict['image_full_url'] = url_for('serve_public_asset', filepath=img_model.image_url, _external=True)
                except Exception as e_img_url:
                    current_app.logger.warning(f"Could not generate URL for additional image {img_model.image_url}: {e_img_url}")
            product_details['additional_images'].append(img_dict)

        if product_model.type == 'variable_weight':
            options = product_model.weight_options.filter_by(is_active=True).order_by(ProductWeightOption.weight_grams).all()
            product_details['weight_options'] = [
                {'option_id': opt.id, 'weight_grams': opt.weight_grams, 'price': opt.price, 
                 'sku_suffix': opt.sku_suffix, 'aggregate_stock_quantity': opt.aggregate_stock_quantity}
                for opt in options
            ]
        
        reviews_models = product_model.reviews.join(User).filter(Review.is_approved == True)\
                                            .order_by(Review.review_date.desc()).all()
        for rev_model in reviews_models:
            product_details['reviews'].append({
                'id': rev_model.id, 'rating': rev_model.rating, 'comment': rev_model.comment,
                'review_date': format_datetime_for_display(rev_model.review_date),
                'user_first_name': rev_model.user.first_name if rev_model.user else "Anonymous"
            })
        
        return jsonify(product=product_details, success=True), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching product detail for {slug_or_code}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch product details", success=False), 500

@products_bp.route('/categories', methods=['GET'])
def get_categories():
    try:
        categories_models = Category.query.filter_by(is_active=True).order_by(Category.name.asc()).all()
        categories_list = []
        for cat_model in categories_models:
            cat_dict = {
                'id': cat_model.id, 'name': cat_model.name, 'description': cat_model.description,
                'category_code': cat_model.category_code, 'slug': cat_model.slug,
                'image_url': cat_model.image_url, 'parent_id': cat_model.parent_id,
                'product_count': cat_model.products.filter_by(is_active=True).count(), # Efficiently count active products
                'image_full_url': None
            }
            if cat_model.image_url:
                try:
                    cat_dict['image_full_url'] = url_for('serve_public_asset', filepath=cat_model.image_url, _external=True)
                except Exception as e_cat_url:
                    current_app.logger.warning(f"Could not generate URL for category image {cat_model.image_url}: {e_cat_url}")
            categories_list.append(cat_dict)
        
        return jsonify(categories=categories_list, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching public categories: {e}", exc_info=True)
        return jsonify(message="Failed to fetch categories", success=False), 500

@products_bp.route('/categories/<string:category_slug_or_code>', methods=['GET'])
def get_category_detail(category_slug_or_code):
    category_model = Category.query.filter(Category.is_active == True)\
                                   .filter(Category.slug == category_slug_or_code).first()
    if not category_model:
        category_model = Category.query.filter(Category.is_active == True)\
                                       .filter(func.upper(Category.category_code) == category_slug_or_code.upper()).first()

    if not category_model:
        return jsonify(message="Category not found or not active", success=False), 404
    
    try:
        category_details = {
            'id': category_model.id, 'name': category_model.name, 'description': category_model.description,
            'category_code': category_model.category_code, 'slug': category_model.slug,
            'image_url': category_model.image_url, 'parent_id': category_model.parent_id,
            'image_full_url': None
        }
        if category_model.image_url:
            try:
                category_details['image_full_url'] = url_for('serve_public_asset', filepath=category_model.image_url, _external=True)
            except Exception as e_cat_detail_url:
                 current_app.logger.warning(f"Could not generate URL for category image {category_model.image_url}: {e_cat_detail_url}")
        return jsonify(category=category_details, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching category {category_slug_or_code}: {e}", exc_info=True)
        return jsonify(message="Failed to retrieve category details", success=False), 500

@products_bp.route('/<int:product_id>/reviews', methods=['POST'])
@jwt_required()
def submit_review(product_id):
    current_user_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service # Assuming audit_logger is available

    data = request.json
    rating = data.get('rating')
    comment = data.get('comment', '')

    if not rating or not isinstance(rating, int) or not (1 <= rating <= 5):
        return jsonify(message="Rating must be an integer between 1 and 5.", success=False), 400

    try:
        product = Product.query.filter_by(id=product_id, is_active=True).first()
        if not product:
            return jsonify(message="Product not found or not active.", success=False), 404

        existing_review = Review.query.filter_by(product_id=product_id, user_id=current_user_id).first()
        if existing_review:
            return jsonify(message="You have already reviewed this product.", success=False), 409

        new_review = Review(
            product_id=product_id,
            user_id=current_user_id,
            rating=rating,
            comment=comment,
            is_approved=False # Reviews typically require approval
        )
        db.session.add(new_review)
        db.session.commit()

        audit_logger.log_action(
            user_id=current_user_id, action='submit_review', target_type='review', target_id=new_review.id,
            details=f"User submitted review for product ID {product_id} with rating {rating}.", status='success', ip_address=request.remote_addr
        )
        return jsonify(message="Review submitted successfully. It will be visible after approval.", review_id=new_review.id, success=True), 201

    except Exception as e: # Catch broader exceptions
        db.session.rollback()
        current_app.logger.error(f"Error submitting review for product {product_id} by user {current_user_id}: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_user_id, action='submit_review_fail', target_type='product', target_id=product_id, details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to submit review.", success=False), 500
