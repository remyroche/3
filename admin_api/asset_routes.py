# admin_api/asset_routes.py
import os
from flask import current_app, send_from_directory, abort as flask_abort
from . import admin_api_bp
from ..utils import admin_required

@admin_api_bp.route('/assets/<path:asset_relative_path>')
@admin_required
def serve_asset(asset_relative_path):
    """
    Securely serves files from designated admin-accessible directories.
    Prevents directory traversal attacks.
    """
    if ".." in asset_relative_path or asset_relative_path.startswith("/"):
        current_app.logger.warning(f"Directory traversal attempt for admin asset: {asset_relative_path}")
        return flask_abort(404)

    asset_type_map = {
        'qr_codes': current_app.config['QR_CODE_FOLDER'],
        'labels': current_app.config['LABEL_FOLDER'],
        'invoices': current_app.config['INVOICE_PDF_PATH'],
        'professional_documents': current_app.config['PROFESSIONAL_DOCS_UPLOAD_PATH'],
        'products': os.path.join(current_app.config['UPLOAD_FOLDER'], 'products'),
        'categories': os.path.join(current_app.config['UPLOAD_FOLDER'], 'categories')
    }

    try:
        path_parts = asset_relative_path.split(os.sep, 1)
        asset_type_key = path_parts[0]
        filename_in_type_folder = path_parts[1] if len(path_parts) > 1 else None

        if asset_type_key in asset_type_map and filename_in_type_folder:
            base_path_abs = asset_type_map[asset_type_key]

            if not base_path_abs:
                current_app.logger.error(f"Asset base path for type '{asset_type_key}' is not configured.")
                return flask_abort(404)

            full_path = os.path.normpath(os.path.join(base_path_abs, filename_in_type_folder))

            if not os.path.abspath(full_path).startswith(os.path.abspath(base_path_abs)):
                current_app.logger.error(f"Security violation: Attempt to access file outside designated admin asset directory. Requested: {full_path}, Base: {base_path_abs}")
                return flask_abort(404)

            if os.path.exists(full_path) and os.path.isfile(full_path):
                return send_from_directory(base_path_abs, filename_in_type_folder)

        current_app.logger.warning(f"Admin asset not found or path not recognized: {asset_relative_path}")
        return flask_abort(404)
    except Exception as e:
        current_app.logger.error(f"Error serving admin asset '{asset_relative_path}': {e}", exc_info=True)
        return flask_abort(500)
