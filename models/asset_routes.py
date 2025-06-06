import os
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, ProductImage, Product, AdminUser

asset_routes_blueprint = Blueprint('asset_routes', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@asset_routes_blueprint.route('/upload_image/<int:product_id>', methods=['POST'])
@login_required
def upload_product_image(product_id):
    """
    Upload an image for a specific product.
    """
    if not isinstance(current_user, AdminUser):
        return jsonify({"error": "Admin access required"}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # To avoid overwriting files with the same name, append product_id and a timestamp
        unique_filename = f"{product_id}_{filename}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)

        # The URL path should be relative to the static folder
        image_url = f'/uploads/{unique_filename}'

        new_image = ProductImage(product_id=product.id, image_url=image_url)
        db.session.add(new_image)
        db.session.commit()
        return jsonify({'success': True, 'image': new_image.to_dict()}), 201

    return jsonify({'error': 'File type not allowed'}), 400


@asset_routes_blueprint.route('/delete_image/<int:image_id>', methods=['DELETE'])
@login_required
def delete_product_image(image_id):
    """
    Delete a product image.
    """
    if not isinstance(current_user, AdminUser):
        return jsonify({"error": "Admin access required"}), 403

    image = ProductImage.query.get(image_id)
    if not image:
        return jsonify({'error': 'Image not found'}), 404

    # Remove the file from the filesystem
    try:
        # Construct absolute path to the file
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], os.path.basename(image.image_url))
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        # Log the error but proceed with DB deletion
        print(f"Error deleting file {filepath}: {e}")

    db.session.delete(image)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Image deleted successfully'})


@asset_routes_blueprint.route('/product_images/<int:product_id>', methods=['GET'])
@login_required
def get_product_images(product_id):
    """
    Get all images for a specific product.
    """
    if not isinstance(current_user, AdminUser):
        return jsonify({"error": "Admin access required"}), 403
        
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    images = [image.to_dict() for image in product.images]
    return jsonify(images)
