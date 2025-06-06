from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from models import B2BUser
from services.b2b_loyalty_service import get_loyalty_points_for_user

loyalty_blueprint = Blueprint('b2b_loyalty', __name__)

@loyalty_blueprint.route('/loyalty_program')
@login_required
def loyalty_program():
    """
    Display the loyalty program page for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
    return render_template('pro/programme-fidelite.html')


@loyalty_blueprint.route('/get_loyalty_points')
@login_required
def get_loyalty_points():
    """
    Get the loyalty points for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
    points = get_loyalty_points_for_user(current_user.id)
    return jsonify({"points": points})
