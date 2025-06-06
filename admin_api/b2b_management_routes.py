from services.b2b_referral_service import award_branding_referral_credit, check_and_award_purchase_referrals


from flask import jsonify
from . import admin_api_bp
from ..utils import admin_required

@admin_api_bp.route('/b2b/quotes', methods=['GET'])
@admin_required
def get_b2b_quotes():
    """
    Placeholder route to get B2B quote requests.
    """
    # Add logic here to query QuoteRequest models and return them.
    return jsonify(message="B2B quote management endpoint.", success=True)

# Add other B2B management routes here as your application grows.

@b2b_management_blueprint.route('/b2b_user/<int:user_id>/details', methods=['GET'])
@login_required
def get_b2b_user_details(user_id):
    """
    Gets a comprehensive overview of a B2B user for the admin panel.
    """
    user = User.query.get_or_404(user_id)
    if not user.b2b_profile:
        return jsonify({'error': 'Not a B2B user'}), 404

    # Recalculate level to ensure data is fresh
    level, annual_spend = b2b_partnership_service.update_user_partnership_level(user.id)

    referees = [
        {'id': ref.id, 'email': ref.email, 'company_name': ref.b2b_profile.company_name if ref.b2b_profile else 'N/A'}
        for ref in user.referrals
    ]

    details = {
        'user_info': user.to_dict(),
        'annual_spend': annual_spend,
        'partnership_level': level.value,
        'referral_info': {
            'code': user.referral_code,
            'credit_balance': user.referral_credit_balance,
            'referee_count': len(referees),
            'referees': referees
        }
    }
    return jsonify(details)

@b2b_management_blueprint.route('/recalculate_all_levels', methods=['POST'])
@login_required
def recalculate_all_levels():
    """
    Admin-triggered job to recalculate partnership levels for all B2B users.
    """
    b2b_users = B2BUser.query.all()
    count = 0
    for b2b_user in b2b_users:
        b2b_partnership_service.update_user_partnership_level(b2b_user.user_id)
        count += 1
    return jsonify({'success': True, 'message': f'{count} B2B user levels recalculated.'})


@b2b_management_blueprint.route('/b2b_user/<int:user_id>/approve_branding_partner', methods=['POST'])
@login_required
def approve_branding_partner(user_id):
    """
    Approves a B2B user for the restaurant branding incentive and triggers the referral credit.
    """
    b2b_user = B2BUser.query.filter_by(user_id=user_id).first_or_404()
    
    if b2b_user.is_restaurant_branding_partner:
        return jsonify({'error': 'User is already a branding partner'}), 400

    b2b_user.is_restaurant_branding_partner = True
    
    # Award credit to the referrer
    award_branding_referral_credit(b2b_user.id)
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Branding partner approved and referral credit awarded.'})


@b2b_management_blueprint.route('/trigger_referral_check', methods=['POST'])
@login_required
def trigger_referral_check():
    """
    Manually triggers the job to check for and award purchase-based referral credits.
    """
    result = check_and_award_purchase_referrals()
    return jsonify(result)
