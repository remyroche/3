# newsletter/__init__.py
from flask import Blueprint

newsletter_bp = Blueprint('newsletter', __name__, url_prefix='/api/newsletter')

# Import the new B2B and B2C route modules
from . import b2c_routes
from . import b2b_routes
