# backend/admin_api/dashboard_routes.py
from flask import jsonify, current_app, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from . import admin_api_bp
from .. import db
from ..models import User, Product, Order, Category, UserRoleEnum, ProfessionalStatusEnum, OrderStatusEnum
from ..utils import admin_required

@admin_api_bp.route('/dashboard/stats', methods=['GET'])
@admin_required
def get_dashboard_stats():
    current_admin_id = get_jwt_identity()
    audit_logger = current_app.audit_log_service
    try:
        total_users = db.session.query(func.count(User.id)).scalar()
        total_products = Product.query.filter_by(is_active=True).count()
        
        pending_order_statuses = [
            OrderStatusEnum.PAID, 
            OrderStatusEnum.PROCESSING, 
            OrderStatusEnum.AWAITING_SHIPMENT,
            OrderStatusEnum.PENDING_PO_REVIEW,
            OrderStatusEnum.ORDER_PENDING_APPROVAL
        ]
        pending_orders = Order.query.filter(Order.status.in_(pending_order_statuses)).count()
        
        total_categories = Category.query.filter_by(is_active=True).count()
        
        pending_b2b_applications = User.query.filter(
            User.role == UserRoleEnum.B2B_PROFESSIONAL,
            User.professional_status == ProfessionalStatusEnum.PENDING_REVIEW
        ).count()
        
        stats = {
            "total_users": total_users,
            "total_products": total_products,
            "pending_orders": pending_orders,
            "total_categories": total_categories,
            "pending_b2b_applications": pending_b2b_applications
        }
        
        audit_logger.log_action(user_id=current_admin_id, action='get_dashboard_stats', status='success', ip_address=request.remote_addr)
        return jsonify(stats=stats, success=True), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching dashboard stats: {e}", exc_info=True)
        audit_logger.log_action(user_id=current_admin_id, action='get_dashboard_stats_fail', details=str(e), status='failure', ip_address=request.remote_addr)
        return jsonify(message="Failed to fetch dashboard statistics", success=False), 500
