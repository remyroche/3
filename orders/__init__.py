# backend/orders/__init__.py
from flask import Blueprint

orders_bp = Blueprint('orders_bp', __name__, url_prefix='/api/orders')

# Import the refactored route modules to register their routes with the blueprint
from . import public_routes
from . import b2c_routes
