# backend/newsletter/__init__.py
from flask import Blueprint
newsletter_bp = Blueprint('newsletter_bp', __name__, url_prefix='/api') # Prefix /api
from . import routes

