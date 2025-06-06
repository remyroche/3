# backend/b2b/profile_routes.py
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from . import b2b_bp
from .. import db
from ..models import User

profile_blueprint = Blueprint('b2b_profile', __name__)

@profile_blueprint.route('/profile')
@login_required
def profile():
    """
    Display the profile page for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
    return render_template('pro/profile.html', user=current_user)



@b2b_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_b2b_profile():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())

@b2b_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_b2b_profile():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    data = request.json

    user.company_name = data.get('company_name', user.company_name)
    user.phone_number = data.get('phone_number', user.phone_number)
    user.address_line1 = data.get('address', {}).get('street', user.address_line1)
    user.city = data.get('address', {}).get('city', user.city)
    user.postal_code = data.get('address', {}).get('postal_code', user.postal_code)
    
    db.session.commit()
    return jsonify(message="Profile updated successfully.", success=True, user=user.to_dict())
    
@profile_blueprint.route('/dashboard_info')
@login_required
def b2b_dashboard_info():
    """
    Provides a consolidated JSON object with all info needed for the B2B dashboard.
    """
    if not isinstance(current_user.b2b_profile, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
    
    dashboard_info = get_user_dashboard_info(current_user.id)
    if dashboard_info:
        return jsonify(dashboard_info)
    
    return jsonify({"error": "Could not retrieve dashboard information"}), 500



@profile_blueprint.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    """
    Update the profile for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
    
    data = request.form
    user = B2BUser.query.get(current_user.id)
    
    user.company_name = data.get('company_name', user.company_name)
    user.contact_name = data.get('contact_name', user.contact_name)
    user.email = data.get('email', user.email)
    user.phone_number = data.get('phone_number', user.phone_number)
    user.address = data.get('address', user.address)
    user.siret_number = data.get('siret_number', user.siret_number)
    
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('b2b_profile.profile'))
