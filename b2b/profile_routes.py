from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, B2BUser

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
