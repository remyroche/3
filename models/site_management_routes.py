from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Review, SiteConfiguration, AdminUser
from models.enums import ReviewStatus

site_management_blueprint = Blueprint('site_management_routes', __name__)

# --- Review Management ---

@site_management_blueprint.route('/reviews', methods=['GET'])
@login_required
def get_reviews():
    """
    Get a list of all product reviews.
    """
    if not isinstance(current_user, AdminUser):
        return jsonify({"error": "Admin access required"}), 403
        
    reviews = Review.query.all()
    return jsonify([review.to_dict() for review in reviews])

@site_management_blueprint.route('/review/<int:review_id>/approve', methods=['PUT'])
@login_required
def approve_review(review_id):
    """
    Approve a product review.
    """
    if not isinstance(current_user, AdminUser):
        return jsonify({"error": "Admin access required"}), 403
        
    review = Review.query.get(review_id)
    if not review:
        return jsonify({'error': 'Review not found'}), 404
    
    review.status = ReviewStatus.APPROVED
    db.session.commit()
    return jsonify({'success': True, 'review': review.to_dict()})

@site_management_blueprint.route('/review/<int:review_id>/reject', methods=['PUT'])
@login_required
def reject_review(review_id):
    """
    Reject a product review.
    """
    if not isinstance(current_user, AdminUser):
        return jsonify({"error": "Admin access required"}), 403
        
    review = Review.query.get(review_id)
    if not review:
        return jsonify({'error': 'Review not found'}), 404
        
    review.status = ReviewStatus.REJECTED
    db.session.commit()
    return jsonify({'success': True, 'review': review.to_dict()})

@site_management_blueprint.route('/review/<int:review_id>', methods=['DELETE'])
@login_required
def delete_review(review_id):
    """
    Delete a product review.
    """
    if not isinstance(current_user, AdminUser):
        return jsonify({"error": "Admin access required"}), 403
        
    review = Review.query.get(review_id)
    if not review:
        return jsonify({'error': 'Review not found'}), 404
        
    db.session.delete(review)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Review deleted'})

# --- Site Settings Management ---

@site_management_blueprint.route('/settings', methods=['GET'])
@login_required
def get_settings():
    """
    Get all site configuration settings.
    """
    if not isinstance(current_user, AdminUser):
        return jsonify({"error": "Admin access required"}), 403

    settings = SiteConfiguration.query.all()
    return jsonify({setting.key: setting.value for setting in settings})

@site_management_blueprint.route('/settings', methods=['POST'])
@login_required
def update_settings():
    """
    Update site configuration settings.
    Expects a JSON object with key-value pairs.
    """
    if not isinstance(current_user, AdminUser):
        return jsonify({"error": "Admin access required"}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    for key, value in data.items():
        setting = SiteConfiguration.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value)
        else:
            new_setting = SiteConfiguration(key=key, value=str(value))
            db.session.add(new_setting)
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Settings updated successfully'})
