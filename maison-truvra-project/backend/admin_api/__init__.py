# backend/admin_api/__init__.py
from flask import Blueprint

admin_api_bp = Blueprint('admin_api_bp', __name__, url_prefix='/api/admin')

from . import routes # Import routes for this blueprint
