# backend/inventory/__init__.py
from flask import Blueprint

inventory_bp = Blueprint('inventory_bp', __name__, url_prefix='/api/inventory')

from . import routes
