# backend/admin_api/__init__.py
from flask import Blueprint, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

admin_api_bp = Blueprint('admin_api_bp', __name__, url_prefix='/api/admin')

# This hook will apply the default admin rate limit to all routes in this blueprint.
# Specific routes can have their own more restrictive limits.
@admin_api_bp.before_request
def before_request_hook():
    # It's good practice to ensure the limiter is available on the app context.
    # This assumes the limiter instance is attached as `current_app.limiter` in create_app.
    if hasattr(current_app, 'limiter'):
        limiter = current_app.limiter
        limiter.limit(current_app.config.get('ADMIN_API_RATELIMITS', "200 per hour"))(lambda: True)()
    else:
        current_app.logger.warning("Flask-Limiter instance not found on current_app. Admin API rate limiting may not be active.")


# Import all the route modules to register their routes with the blueprint
from . import auth_routes
from . import dashboard_routes
from . import product_management_routes
from . import user_management_routes
from . import order_management_routes
from . import b2b_management_routes
from . import site_management_routes
from . import asset_routes
