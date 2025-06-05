# backend/b2b/__init__.py
from flask import Blueprint

b2b_bp = Blueprint('b2b_bp', __name__, url_prefix='/api/b2b')

# Import routes after blueprint creation to avoid circular imports
from . import routes
