# backend/newsletter/__init__.py
from flask import Blueprint

# If the url_prefix in routes.py is '/api', then this prefix should be '/api' as well,
# or the routes within newsletter_bp will be relative to this.
# Given the route change to '/api/subscribe-newsletter', it's cleaner if the blueprint's prefix is just '/api'.
# OR, keep this as '/api/newsletter' and the route in routes.py as just '/subscribe'.
# For consistency with the original script.js, let's adjust here.
newsletter_bp = Blueprint('newsletter_bp', __name__, url_prefix='/api') # Adjusted to /api

from . import routes
