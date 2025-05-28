# backend/orders/__init__.py
from flask import Blueprint

orders_bp = Blueprint('orders_bp', __name__, url_prefix='/api/orders')

from . import routes
