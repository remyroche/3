from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from models import B2BUser
from services.b2b_asset_service import get_user_assets

asset_blueprint = Blueprint('b2b_asset', __name__)

@asset_blueprint.route('/get_assets')
@login_required
def get_assets():
    """
    Get the assets for the current B2B user.
    """
    if not isinstance(current_user, B2BUser):
        return jsonify({"error": "Not a B2B user"}), 403
    assets = get_user_assets(current_user.id)
    return jsonify(assets)
