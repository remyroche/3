import sqlite3
from flask import Blueprint, request, jsonify, current_app, g
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt # For review submission
from ..database import get_db_connection, query_db # query_db uses get_db_connection
from ..utils import format_datetime_for_display, generate_slug # Assuming generate_slug is in utils

# This is the more comprehensive blueprint that will be kept.
# The older, simpler one will be removed.
products_bp = Blueprint('products', __name__, url_prefix='/api/products')

# Helper to get DB connection (consistent with other modules)
def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'db_conn') or g.db_conn is None:
        g.db_conn = get_db_connection() # Uses the main get_db_connection
    return g.db_conn

# Helper for language (can be expanded)
def get_locale():
    # Example: Get language from request headers or a session/cookie
    # For now, defaults to 'en', can be 'fr'
    return request.headers.get('Accept-Language', 'en').split(',')[0].split('-')[0]


@products_bp.route('/', methods=['GET'])
def get_products_list():
    db = get_db()
    lang = get_locale() # For potential future localized fields

    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        category_slug = request.args.get('category')
        search_term = request.args.get('search')
        sort_by = request.args.get('sort', 'name_asc') # e.g., name_asc, name_desc, price_asc, price_desc, date_desc

        offset = (page - 1) * per_page

        base_query = """
            SELECT 
                p.id, p.name, p.description, p.slug, p.base_price, p.currency, 
                p.main_image_url, p.type, p.unit_of_measure, p.is_featured,
                p.aggregate_stock_quantity, p.aggregate_stock_weight_grams,
                c.name as category_name, c.slug as category_slug
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

        if category_slug:
            conditions.append("c.slug = ?")
            params.append(category_slug)
        
        if search_term:
            # Basic search on name and description. Can be expanded.
            conditions.append("(LOWER(p.name) LIKE ? OR LOWER(p.description) LIKE ?)")
            params.extend([f"%{search_term.lower()}%", f"%{search_term.lower()}%"])

        if conditions:
            base_query += " AND " + " AND ".join(conditions)
            count_query += " AND " + " AND ".join(conditions)
        
        # Sorting logic
        if sort_by == 'name_asc':
            base_query += " ORDER BY p.name ASC"
        elif sort_by == 'name_desc':
            base_query += " ORDER BY p.name DESC"
        elif sort_by == 'price_asc':
            base_query += " ORDER BY p.base_price ASC"
        elif sort_by == 'price_desc':
            base_query += " ORDER BY p.base_price DESC"
        elif sort_by == 'date_desc': # Newest first
            base_query += " ORDER BY p.created_at DESC"
        else: # Default sort
            base_query += " ORDER BY p.name ASC"

        base_query += " LIMIT ? OFFSET ?"
        params.extend([per_page, offset])

        products_data = query_db(base_query, params, db_conn=db)
        total_products_row = query_db(count_query, params[:-2], db_conn=db, one=True) # Exclude limit/offset params for count
        total_products = total_products_row[0] if total_products_row else 0

        products_list = []
        if products_data:
            for row in products_data:
                product_dict = dict(row)
                if product_dict.get('main_image_url'):
                    # Assuming assets are served from a public endpoint or a specific asset serving route
                    # This might need adjustment based on how frontend constructs URLs
                    # For now, let's assume a generic asset path if served by Flask, or direct if CDN
                    # If using the admin asset server (now protected), this URL won't work for public.
                    # A separate public asset server or direct web server serving is better.
                    # Placeholder for public URL construction:
                    product_dict['main_image_full_url'] = f"/assets/{product_dict['main_image_url']}" # Example
                
                # Fetch active weight options for variable products
                if product_dict['type'] == 'variable_weight':
                    options_data = query_db(
                        "SELECT id, weight_grams, price, sku_suffix, aggregate_stock_quantity FROM product_weight_options WHERE product_id = ? AND is_active = TRUE ORDER BY weight_grams",
                        [product_dict['id']], db_conn=db
                    )
                    product_dict['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
                products_list.append(product_dict)
        
        return jsonify({
            "products": products_list,
            "page": page,
            "per_page": per_page,
            "total_products": total_products,
            "total_pages": (total_products + per_page - 1) // per_page if total_products > 0 else 0
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching products list: {e}")
        return jsonify(message="Failed to fetch products"), 500


@products_bp.route('/<string:slug>', methods=['GET'])
def get_product_detail(slug):
    db = get_db()
    lang = get_locale()

    try:
        product_query = """
            SELECT p.*, c.name as category_name, c.slug as category_slug
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.slug = ? AND p.is_active = TRUE
        """
        product_data = query_db(product_query, [slug], db_conn=db, one=True)

        if not product_data:
            return jsonify(message="Product not found or not active"), 404

        product_details = dict(product_data)
        product_details['created_at'] = format_datetime_for_display(product_details['created_at'])
        product_details['updated_at'] = format_datetime_for_display(product_details['updated_at'])
        if product_details.get('main_image_url'):
            product_details['main_image_full_url'] = f"/assets/{product_details['main_image_url']}" # Example

        # Fetch additional images
        images_data = query_db(
            "SELECT id, image_url, alt_text, is_primary FROM product_images WHERE product_id = ? ORDER BY is_primary DESC, id ASC",
            [product_details['id']], db_conn=db
        )
        product_details['additional_images'] = []
        if images_data:
            for img_row in images_data:
                img_dict = dict(img_row)
                img_dict['image_full_url'] = f"/assets/{img_dict['image_url']}" # Example
                product_details['additional_images'].append(img_dict)

        # Fetch active weight options if variable_weight
        if product_details['type'] == 'variable_weight':
            options_data = query_db(
                "SELECT id, weight_grams, price, sku_suffix, aggregate_stock_quantity FROM product_weight_options WHERE product_id = ? AND is_active = TRUE ORDER BY weight_grams",
                [product_details['id']], db_conn=db
            )
            product_details['weight_options'] = [dict(opt_row) for opt_row in options_data] if options_data else []
        
        # Fetch approved reviews
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
        
        return jsonify(product_details), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching product detail for slug {slug}: {e}")
        return jsonify(message="Failed to fetch product details"), 500


@products_bp.route('/<int:product_id>/reviews', methods=['POST'])
@jwt_required() # User must be logged in to post a review
def submit_review(product_id):
    db = get_db()
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    user_role = claims.get('role', 'b2c_customer') # Default to b2c if role not in token
    audit_logger = current_app.audit_log_service # Use app-initialized service

    data = request.json
    rating = data.get('rating')
    comment = data.get('comment', '')

    if not rating or not isinstance(rating, int) or not (1 <= rating <= 5):
        audit_logger.log_action(
            user_id=current_user_id,
            action='submit_review_fail',
            target_type='product',
            target_id=product_id,
            details="Invalid rating provided.",
            status='failure'
        )
        return jsonify(message="Rating must be an integer between 1 and 5."), 400

    try:
        # Check if product exists and is active
        product_exists = query_db("SELECT id FROM products WHERE id = ? AND is_active = TRUE", [product_id], db_conn=db, one=True)
        if not product_exists:
            audit_logger.log_action(
                user_id=current_user_id,
                action='submit_review_fail',
                target_type='product',
                target_id=product_id,
                details="Product not found or not active for review.",
                status='failure'
            )
            return jsonify(message="Product not found or not active."), 404

        # Optional: Check if user has purchased this product (more complex, requires order history check)
        # For now, allow any logged-in user to review.

        # Check if user already reviewed this product
        existing_review = query_db("SELECT id FROM reviews WHERE product_id = ? AND user_id = ?", [product_id, current_user_id], db_conn=db, one=True)
        if existing_review:
            audit_logger.log_action(
                user_id=current_user_id,
                action='submit_review_fail',
                target_type='product',
                target_id=product_id,
                details="User has already reviewed this product.",
                status='failure'
            )
            return jsonify(message="You have already reviewed this product."), 409

        cursor = db.cursor()
        # Reviews are not approved by default, admin needs to approve them
        cursor.execute(
            "INSERT INTO reviews (product_id, user_id, rating, comment, is_approved) VALUES (?, ?, ?, ?, ?)",
            (product_id, current_user_id, rating, comment, False) 
        )
        review_id = cursor.lastrowid
        db.commit()

        audit_logger.log_action(
            user_id=current_user_id,
            action='submit_review',
            target_type='review',
            target_id=review_id,
            details=f"User submitted review for product ID {product_id} with rating {rating}.",
            status='success'
        )
        return jsonify(message="Review submitted successfully. It will be visible after approval.", review_id=review_id), 201

    except sqlite3.IntegrityError as e: # Should be rare if product/user checks are done
        db.rollback()
        current_app.logger.error(f"Integrity error submitting review for product {product_id} by user {current_user_id}: {e}")
        audit_logger.log_action(
            user_id=current_user_id,
            action='submit_review_fail',
            target_type='product',
            target_id=product_id,
            details=f"Database integrity error: {e}",
            status='failure'
        )
        return jsonify(message="Failed to submit review due to a database conflict."), 409
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error submitting review for product {product_id} by user {current_user_id}: {e}")
        audit_logger.log_action(
            user_id=current_user_id,
            action='submit_review_fail',
            target_type='product',
            target_id=product_id,
            details=str(e),
            status='failure'
        )
        return jsonify(message="Failed to submit review."), 500


@products_bp.route('/categories', methods=['GET'])
def get_public_categories():
    db = get_db()
    try:
        # Fetch only top-level categories or all, depending on desired display
        # This example fetches all active categories
        categories_data = query_db(
            "SELECT id, name, slug, description, image_url, parent_id FROM categories ORDER BY name", # Assuming active categories are handled by admin
            db_conn=db
        )
        categories_list = []
        if categories_data:
            for cat_row in categories_data:
                cat_dict = dict(cat_row)
                if cat_dict.get('image_url'):
                    cat_dict['image_full_url'] = f"/assets/{cat_dict['image_url']}" # Example public asset URL
                categories_list.append(cat_dict)
        
        return jsonify(categories_list), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching public categories: {e}")
        return jsonify(message="Failed to fetch categories"), 500

# Add other public product-related utility endpoints if needed, e.g.,
# - Featured products
# - Related products
# - Search suggestions
