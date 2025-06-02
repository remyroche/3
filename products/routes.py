import sqlite3
from flask import Blueprint, request, jsonify, current_app, g
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt 
from ..database import get_db_connection, query_db 
from ..utils import format_datetime_for_display, generate_slug

products_bp = Blueprint('products_bp', __name__, url_prefix='/api/products')

def get_db():
    if not hasattr(g, 'db_conn') or g.db_conn is None:
        g.db_conn = get_db_connection()
    return g.db_conn

def get_locale():
    return request.headers.get('Accept-Language', 'en').split(',')[0].split('-')[0]

@products_bp.route('/', methods=['GET'])
def get_products():
    """
    Lists products for the public frontend.
    Supports filtering by category slug, search term, featured status, and pagination.
    """
    db = get_db()
    lang = get_locale() # For potential future localized fields

    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int) # Default to 12 for better grid display
        category_slug = request.args.get('category_slug') # Changed from 'category' to be specific
        search_term = request.args.get('search')
        sort_by = request.args.get('sort', 'name_asc')
        featured_str = request.args.get('featured')

        offset = (page - 1) * per_page
        if page < 1 or per_page < 1:
            return jsonify(message='Page and per_page parameters must be positive integers.', success=False), 400

        base_query = """
            SELECT 
                p.id, p.name, p.description, p.slug, p.base_price, p.currency, 
                p.main_image_url, p.type, p.unit_of_measure, p.is_featured,
                p.aggregate_stock_quantity, p.aggregate_stock_weight_grams,
                p.product_code, -- Added for consistency, though slug is primary for public
                c.name as category_name, c.slug as category_slug, c.category_code
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.is_active = TRUE
        """
        count_query = """
            SELECT COUNT(p.id)
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.is_active = TRUE
        """

        conditions = []
        params = []
        count_params = [] # Separate params for count query if they differ

        if category_slug:
            conditions.append("c.slug = ?")
            params.append(category_slug)
            count_params.append(category_slug)
        
        if search_term:
            conditions.append("(LOWER(p.name) LIKE ? OR LOWER(p.description) LIKE ? OR LOWER(p.product_code) LIKE ?)")
            term_like = f"%{search_term.lower()}%"
            params.extend([term_like, term_like, term_like])
            count_params.extend([term_like, term_like, term_like])

        featured = None
        if featured_str:
            if featured_str.lower() == 'true': featured = True
            elif featured_str.lower() == 'false': featured = False
        
        if featured is not None:
            conditions.append("p.is_featured = ?")
            params.append(1 if featured else 0)
            count_params.append(1 if featured else 0)


        if conditions:
            base_query += " AND " + " AND ".join(conditions)
            count_query += " AND " + " AND ".join(conditions)
        
        # Sorting logic
        order_clause = " ORDER BY p.name ASC" # Default
        if sort_by == 'name_desc': order_clause = " ORDER BY p.name DESC"
        elif sort_by == 'price_asc': order_clause = " ORDER BY p.base_price ASC"
        elif sort_by == 'price_desc': order_clause = " ORDER BY p.base_price DESC"
        elif sort_by == 'date_desc': order_clause = " ORDER BY p.created_at DESC"
        base_query += order_clause

        base_query += " LIMIT ? OFFSET ?"
        params.extend([per_page, offset])

        products_data = query_db(base_query, params, db_conn=db)
        total_products_row = query_db(count_query, count_params, db_conn=db, one=True)
        total_products = total_products_row[0] if total_products_row else 0

        products_list = []
        if products_data:
            for row in products_data:
                product_dict = dict(row)
                if product_dict.get('main_image_url'):
                    try:
                        product_dict['main_image_full_url'] = url_for('serve_public_asset', filepath=product_dict['main_image_url'], _external=True)
                    except Exception as e_url:
                        current_app.logger.warning(f"Could not generate public URL for product image {product_dict['main_image_url']}: {e_url}")
                        product_dict['main_image_full_url'] = None # Or a placeholder
                
                if product_dict['type'] == 'variable_weight':
                    options_data = query_db(
                        "SELECT id as option_id, weight_grams, price, sku_suffix, aggregate_stock_quantity FROM product_weight_options WHERE product_id = ? AND is_active = TRUE ORDER BY weight_grams",
                        [product_dict['id']], db_conn=db
                    )
                    product_dict['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
                products_list.append(product_dict)
        
        total_pages = (total_products + per_page - 1) // per_page if total_products > 0 and per_page > 0 else 0
        
        return jsonify({
            "products": products_list,
            "page": page,
            "per_page": per_page,
            "total_products": total_products,
            "total_pages": total_pages,
            "success": True
        }), 200

    except ValueError as ve: # Catch specific errors like invalid page/per_page
        current_app.logger.warning(f"Invalid request parameters for product listing: {ve}")
        return jsonify(message=str(ve), success=False), 400
    except Exception as e:
        current_app.logger.error(f"Error fetching products list: {e}", exc_info=True)
        return jsonify(message="Failed to fetch products", success=False), 500

@products_bp.route('/<string:slug_or_code>', methods=['GET'])
def get_product_detail_by_slug_or_code(slug_or_code):
    """
    Fetches a single product by its slug (preferred) or product_code.
    """
    db = get_db()
    # lang = get_locale() # For future localized fields

    try:
        # Try fetching by slug first
        product_query = """
            SELECT p.*, c.name as category_name, c.slug as category_slug, c.category_code
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.slug = ? AND p.is_active = TRUE
        """
        product_data = query_db(product_query, [slug_or_code], db_conn=db, one=True)

        if not product_data:
            # If not found by slug, try by product_code
            product_query_by_code = """
                SELECT p.*, c.name as category_name, c.slug as category_slug, c.category_code
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.product_code = ? AND p.is_active = TRUE
            """
            product_data = query_db(product_query_by_code, [slug_or_code.upper()], db_conn=db, one=True)

        if not product_data:
            return jsonify(message="Product not found or not active", success=False), 404

        product_details = dict(product_data)
        product_details['created_at'] = format_datetime_for_display(product_details['created_at'])
        product_details['updated_at'] = format_datetime_for_display(product_details['updated_at'])
        if product_details.get('main_image_url'):
            try:
                product_details['main_image_full_url'] = url_for('serve_public_asset', filepath=product_details['main_image_url'], _external=True)
            except Exception as e_url:
                current_app.logger.warning(f"Could not generate public URL for product image {product_details['main_image_url']}: {e_url}")
                product_details['main_image_full_url'] = None


        images_data = query_db(
            "SELECT id, image_url, alt_text, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC",
            [product_details['id']], db_conn=db
        )
        product_details['additional_images'] = []
        if images_data:
            for img_row in images_data:
                img_dict = dict(img_row)
                if img_dict.get('image_url'):
                    try:
                        img_dict['image_full_url'] = url_for('serve_public_asset', filepath=img_dict['image_url'], _external=True)
                    except Exception as e_img_url:
                        current_app.logger.warning(f"Could not generate public URL for additional image {img_dict['image_url']}: {e_img_url}")
                        img_dict['image_full_url'] = None
                product_details['additional_images'].append(img_dict)

        if product_details['type'] == 'variable_weight':
            options_data = query_db(
                "SELECT id as option_id, weight_grams, price, sku_suffix, aggregate_stock_quantity FROM product_weight_options WHERE product_id = ? AND is_active = TRUE ORDER BY weight_grams",
                [product_details['id']], db_conn=db
            )
            product_details['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
        
        reviews_query = """
            SELECT r.id, r.rating, r.comment, r.review_date, u.first_name as user_first_name
            FROM reviews r
            JOIN users u ON r.user_id = u.id
            WHERE r.product_id = ? AND r.is_approved = TRUE
            ORDER BY r.review_date DESC
        """
        reviews_data = query_db(reviews_query, [product_details['id']], db_conn=db)
        product_details['reviews'] = []
        if reviews_data:
            for rev_row in reviews_data:
                review_dict = dict(rev_row)
                review_dict['review_date'] = format_datetime_for_display(review_dict['review_date'])
                product_details['reviews'].append(review_dict)
        
        return jsonify(product=product_details, success=True), 200 # Return as object

    except Exception as e:
        current_app.logger.error(f"Error fetching product detail for {slug_or_code}: {e}", exc_info=True)
        return jsonify(message="Failed to fetch product details", success=False), 500

@products_bp.route('/categories', methods=['GET'])
def get_categories():
    """
    Lists all active categories for the public frontend.
    """
    db = get_db()
    try:
        categories_data = query_db(
            """SELECT c.id, c.name, c.description, c.category_code, c.slug, c.image_url, c.parent_id,
                   (SELECT COUNT(p.id) FROM products p WHERE p.category_id = c.id AND p.is_active = TRUE) as product_count
            FROM categories c 
            WHERE c.is_active = TRUE ORDER BY c.name ASC""", # Ensure only active categories
            db_conn=db
        )
        categories_list = []
        if categories_data:
            for cat_row in categories_data:
                cat_dict = dict(cat_row)
                if cat_dict.get('image_url'):
                    try:
                        cat_dict['image_full_url'] = url_for('serve_public_asset', filepath=cat_dict['image_url'], _external=True)
                    except Exception as e_cat_url:
                        current_app.logger.warning(f"Could not generate public URL for category image {cat_dict['image_url']}: {e_cat_url}")
                        cat_dict['image_full_url'] = None
                categories_list.append(cat_dict)
        
        return jsonify(categories=categories_list, success=True), 200 # Return as object
    except Exception as e:
        current_app.logger.error(f"Error fetching public categories: {e}", exc_info=True)
        return jsonify(message="Failed to fetch categories", success=False), 500

@products_bp.route('/categories/<string:category_slug_or_code>', methods=['GET'])
def get_category_detail(category_slug_or_code):
    """
    Fetches a single category by its slug (preferred) or category_code.
    """
    db = get_db()
    try:
        # Try by slug first
        category_data = query_db(
            "SELECT id, name, description, category_code, slug, image_url, parent_id FROM categories WHERE slug = ? AND is_active = TRUE",
            [category_slug_or_code], db_conn=db, one=True
        )
        if not category_data:
            # Try by category_code if not found by slug
            category_data = query_db(
                "SELECT id, name, description, category_code, slug, image_url, parent_id FROM categories WHERE category_code = ? AND is_active = TRUE",
                [category_slug_or_code.upper()], db_conn=db, one=True
            )

        if category_data:
            category = dict(category_data)
            if category.get('image_url'):
                try:
                    category['image_full_url'] = url_for('serve_public_asset', filepath=category['image_url'], _external=True)
                except Exception as e_cat_detail_url:
                    current_app.logger.warning(f"Could not generate public URL for category image {category['image_url']} in detail view: {e_cat_detail_url}")
                    category['image_full_url'] = None
            return jsonify(category=category, success=True), 200 # Return as object
        else:
            return jsonify(message="Category not found or not active", success=False), 404
    except Exception as e:
        current_app.logger.error(f"Error fetching category {category_slug_or_code}: {e}", exc_info=True)
        return jsonify(message="Failed to retrieve category details", success=False), 500

@products_bp.route('/<int:product_id>/reviews', methods=['POST'])
@jwt_required() 
def submit_review(product_id):
    db = get_db()
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    # user_role = claims.get('role', 'b2c_customer') # Not strictly needed for this action if any logged-in user can review
    audit_logger = current_app.audit_log_service

    data = request.json
    rating = data.get('rating')
    comment = data.get('comment', '')

    if not rating or not isinstance(rating, int) or not (1 <= rating <= 5):
        return jsonify(message="Rating must be an integer between 1 and 5.", success=False), 400

    try:
        product_exists = query_db("SELECT id FROM products WHERE id = ? AND is_active = TRUE", [product_id], db_conn=db, one=True)
        if not product_exists:
            return jsonify(message="Product not found or not active.", success=False), 404

        existing_review = query_db("SELECT id FROM reviews WHERE product_id = ? AND user_id = ?", [product_id, current_user_id], db_conn=db, one=True)
        if existing_review:
            return jsonify(message="You have already reviewed this product.", success=False), 409

        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO reviews (product_id, user_id, rating, comment, is_approved) VALUES (?, ?, ?, ?, ?)",
            (product_id, current_user_id, rating, comment, False) 
        )
        review_id = cursor.lastrowid
        db.commit()

        audit_logger.log_action(
            user_id=current_user_id, action='submit_review', target_type='review', target_id=review_id,
            details=f"User submitted review for product ID {product_id} with rating {rating}.", status='success', ip_address=request.remote_addr
        )
        return jsonify(message="Review submitted successfully. It will be visible after approval.", review_id=review_id, success=True), 201

    except sqlite3.IntegrityError as e:
        db.rollback()
        current_app.logger.error(f"Integrity error submitting review for product {product_id} by user {current_user_id}: {e}", exc_info=True)
        return jsonify(message="Failed to submit review due to a database conflict.", success=False), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error submitting review for product {product_id} by user {current_user_id}: {e}", exc_info=True)
        return jsonify(message="Failed to submit review.", success=False), 500
