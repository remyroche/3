# backend/b2b/auth_routes.py
from flask import request, jsonify, current_app
from flask_jwt_extended import create_access_token
from sqlalchemy import func

from . import b2b_bp
from .. import db
from ..models import User, UserRoleEnum, ProfessionalStatusEnum

@b2b_bp.route('/register', methods=['POST'])
def b2b_register():
    """Handles the registration of a new B2B professional account."""
    data = request.json
    audit_logger = current_app.audit_log_service

    if not all(data.get(k) for k in ['email', 'password', 'company_name', 'siret']):
        return jsonify(message="Email, password, company name, and SIRET are required.", success=False), 400

    if User.query.filter(func.lower(User.email) == data['email'].lower()).first():
        return jsonify(message="Email address already registered.", success=False), 409

    if User.query.filter_by(siret_number=data['siret']).first():
        return jsonify(message="SIRET number already registered.", success=False), 409

    password_error = User.validate_password(data['password'])
    if password_error:
        return jsonify(message=password_error, success=False), 400

    new_user = User(
        email=data['email'].lower(),
        company_name=data['company_name'],
        siret_number=data['siret'],
        phone_number=data.get('phone'),
        role=UserRoleEnum.B2B_PROFESSIONAL,
        professional_status=ProfessionalStatusEnum.PENDING_REVIEW,
        is_active=True,  # Account is active, but status is pending
        is_verified=False # Requires email verification
    )
    new_user.set_password(data['password'])
    new_user.generate_referral_code()

    try:
        db.session.add(new_user)
        db.session.commit()
        audit_logger.log_action(action='b2b_register_success', user_id=new_user.id, status='success')
        # TODO: Trigger email verification and admin notification
        return jsonify(message="Registration successful! Your account is pending admin approval.", success=True), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"B2B registration error for {data['email']}: {e}", exc_info=True)
        return jsonify(message="Could not process registration due to a server error.", success=False), 500


@b2b_bp.route('/login', methods=['POST'])
def b2b_login():
    """Handles B2B user login and returns a JWT."""
    data = request.json
    email = data.get('email', '').lower()
    password = data.get('password')

    if not email or not password:
        return jsonify(message="Email and password are required.", success=False), 400

    user = User.query.filter(func.lower(User.email) == email, User.role == UserRoleEnum.B2B_PROFESSIONAL).first()

    if not user or not user.check_password(password):
        return jsonify(message="Invalid credentials.", success=False), 401

    if user.professional_status != ProfessionalStatusEnum.APPROVED:
        return jsonify(message=f"Your account status is '{user.professional_status.value}'. Please contact support.", success=False), 403

    if not user.is_active:
        return jsonify(message="Your account is inactive.", success=False), 403

    additional_claims = {
        "role": user.role.value,
        "company_name": user.company_name
    }
    access_token = create_access_token(identity=user.id, additional_claims=additional_claims)
    
    return jsonify(success=True, token=access_token, user=user.to_dict())
