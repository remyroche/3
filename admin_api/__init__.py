# backend/admin_api/__init__.py
from flask import Blueprint

# Define the main blueprint for the entire admin API.
# All other route files in this module will attach their routes to this blueprint.
admin_api_bp = Blueprint('admin_api', __name__, url_prefix='/api/admin')

# Import all the route modules to register their routes with the admin_api_bp.
# This pattern keeps the code modular and organized.
from . import auth_routes
from . import user_routes
from . import product_routes
from . import order_routes
from . import inventory_routes # Assuming inventory is managed under admin
from . import dashboard_routes
from . import b2b_management_routes
from . import site_management_routes
from . import asset_routes
