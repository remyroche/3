# backend/b2b/referral_routes.py
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from . import b2b_bp
from ..models import User

@b2b_bp.route('/referral', methods=['GET'])
@jwt_required()
def get_referral_info():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)

    # Ensure user has a referral code
    if not user.referral_code:
        user.generate_referral_code()
        db.session.commit()

    referred_users = User.query.filter_by(referred_by_id=user_id).all()
    
    history = [{
        "date": referred.created_at.strftime('%Y-%m-%d'),
        "referred_email": referred.email,
        "status": "completed" if referred.orders.first() else "pending"
    } for referred in referred_users]

    return jsonify({
        "referral_code": user.referral_code,
        "referrals": history
    })
