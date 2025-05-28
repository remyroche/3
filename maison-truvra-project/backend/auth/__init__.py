# backend/auth/__init__.py
from flask import Blueprint

# Création du Blueprint pour l'authentification
# Le préfixe URL '/api/auth' sera appliqué à toutes les routes définies dans ce Blueprint
auth_bp = Blueprint('auth_bp', __name__, url_prefix='/api/auth')

# Importer les routes après la création du Blueprint pour éviter les importations circulaires
from . import routes
