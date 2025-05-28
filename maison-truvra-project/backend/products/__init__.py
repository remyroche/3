# backend/products/__init__.py
from flask import Blueprint

products_bp = Blueprint('products_bp', __name__, url_prefix='/api/products')

from . import routes 
