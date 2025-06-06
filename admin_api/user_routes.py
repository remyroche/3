# backend/admin_api/user_routes.py
# Admin User Management (CRUD)

from flask import request, jsonify, current_app, url_for
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func, or_
from datetime import datetime, timezone

from . import admin_api_bp
from .. import db
from ..models import User, ProfessionalDocument, UserRoleEnum, ProfessionalStatusEnum, B2BPricingTierEnum
from ..utils import admin_required

@admin_api_bp.route('/users', methods=['GET'])
@admin_required
def get_users_admin():
    audit_logger = current_app.audit_log_service
    current_admin_id = get_jwt_identity()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        role_filter = request.args.get('role')
        is_active_filter = request.args.get('is_active')
        professional_status_filter = request.args.get('professional_status')
        search_term = request.args.get('search')

        query = User.query

        if role_filter:
            try: query = query.filter(User.role == UserRoleEnum(role_filter))
            except ValueError: return jsonify(message=f"Invalid role filter: {role_filter}", success=False), 400
        
        if is_active_filter is not None:
            query = query.filter(User.is_active == (is_active_filter.lower() == 'true'))
        
        if professional_status_filter:
            try: query = query.filter(User.professional_status == ProfessionalStatusEnum(professional_status_filter))
            except ValueError: return jsonify(message=f"Invalid professional status filter: {professional_status_filter}", success=False), 400
        
        if search_term:
            term_like = f"%{search_term.lower()}%"
            query = query.filter(
                or_(
                    User.email.ilike(term_like),
                    User.first_name.ilike(term_like),
                    User.last_name.ilike(term_like),
                    User.company_name.ilike(term_like),
                    func.cast(User.id, db.String).ilike(term_like)
                )
            )
        
        paginated_users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        users_data = [u.to_dict() for u in paginated_users.items]
        
        audit_logger.log_action(user_id=current_admin_id, action='admin_get_users_list', status='success', ip_address=request.remote_addr)
        return jsonify({
            "users": users_data,
            "pagination": {
                "current_page": paginated_users.page, "per_page": paginated_users.per_page,
                "total_items": paginated_users.total, "total_pages": paginated_users.pages
            },
            "success": True
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching users for admin: {e}", exc_info=True)
        return jsonify(message="Failed to fetch users.", success=False), 500

@admin_api_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user_admin_detail(user_id):
    """Retrieves detailed information for a single user for the admin panel."""
    user_model = User.query.get_or_404(user_id)
    user_data = user_model.to_dict()

    if user_model.role == UserRoleEnum.B2B_PROFESSIONAL:
        user_data['professional_documents'] = []
        for doc in user_model.professional_documents:
            doc_download_url = None
            if doc.file_path:
                try:
                    # Uses the asset serving route
                    doc_download_url = url_for('admin_api.serve_asset', asset_relative_path=doc.file_path, _external=True)
                except Exception as e_doc_url:
                    current_app.logger.warning(f"Could not generate URL for professional document {doc.file_path}: {e_doc_url}")
            
            user_data['professional_documents'].append({
                "id": doc.id,
                "document_type": doc.document_type,
                "upload_date": doc.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
                "status": doc.status.value if doc.status else None,
                "download_url": doc_download_url,
                "notes": doc.notes
            })
            
    return jsonify(user=user_data, success=True), 200

@admin_api_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user_admin(user_id):
    """Updates a user's details from the admin panel."""
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    data = request.json
    if not data:
        return jsonify(message="No data provided for update.", success=False), 400

    user = User.query.get_or_404(user_id)
    
    # List of fields an admin is allowed to modify
    allowed_fields = [
        'first_name', 'last_name', 'role', 'is_active', 'is_verified',
        'company_name', 'vat_number', 'siret_number', 'professional_status',
        'b2b_tier', 'newsletter_b2c_opt_in', 'newsletter_b2b_opt_in'
    ]
    updated_fields_log = []

    for field in allowed_fields:
        if field in data:
            new_value = data[field]
            current_value = getattr(user, field, None)
            
            # Process value (e.g., convert to Enum or boolean) before comparison
            try:
                if field == 'role' and new_value:
                    new_value_processed = UserRoleEnum(new_value)
                elif field == 'professional_status' and new_value:
                    new_value_processed = ProfessionalStatusEnum(new_value)
                elif field == 'b2b_tier' and new_value:
                    new_value_processed = B2BPricingTierEnum(new_value)
                elif isinstance(current_value, bool):
                    new_value_processed = str(new_value).lower() in ['true', '1', 'yes']
                else:
                    new_value_processed = new_value
            except ValueError as e_enum:
                return jsonify(message=f"Invalid value for {field}: {new_value}. Error: {str(e_enum)}", success=False), 400

            if new_value_processed != current_value:
                setattr(user, field, new_value_processed)
                updated_fields_log.append(field)
    
    if not updated_fields_log:
        return jsonify(message="No changes detected.", success=True), 200

    try:
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        audit_logger.log_action(
            user_id=current_admin_id, 
            action='update_user_admin_success', 
            target_type='user', 
            target_id=user_id, 
            details=f"Fields updated: {', '.join(updated_fields_log)}", 
            status='success', 
            ip_address=request.remote_addr
        )
        return jsonify(message="User updated successfully.", user=user.to_dict(), success=True), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update user {user_id}: {e}", exc_info=True)
        audit_logger.log_action(
            user_id=current_admin_id, 
            action='update_user_admin_fail', 
            target_type='user', 
            target_id=user_id, 
            details=str(e), 
            status='failure', 
            ip_address=request.remote_addr
        )
        return jsonify(message="Failed to update user.", error=str(e), success=False), 500

