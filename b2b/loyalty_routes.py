from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from models import B2BUser
from services.b2b_loyalty_service import get_user_loyalty_info, LoyaltyService

loyalty_blueprint = Blueprint('b2b_loyalty', __name__)

@b2b_bp.route('/loyalty', methods=['GET'])
@jwt_required()
def get_loyalty_status():
    user_id = get_jwt_identity()
    loyalty_service = LoyaltyService()
    # This service should be adapted to fetch loyalty points and history
    # For now, returning mock data.
    mock_data = {
        "total_points": 1250,
        "history": [
            {"date": "2025-05-15", "description": "Order #1055", "points": 500},
            {"date": "2025-04-20", "description": "Order #1043", "points": 750}
        ]
    }
    return jsonify(mock_data)



@loyalty_blueprint.route('/loyalty_program')
@login_required
def loyalty_program():
    """
    Display the loyalty program page for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
    return render_template('pro/programme-fidelite.html')


@loyalty_blueprint.route('/get_loyalty_info')
@login_required
def get_loyalty_points():
    """
    Get the full loyalty info (points, tier, discount) for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
    
    loyalty_info = get_user_loyalty_info(current_user.id)
    if loyalty_info:
        return jsonify(loyalty_info)
    return jsonify({"error": "Could not retrieve loyalty information"}), 500
