# newsletter/b2c_routes.py

from flask import request, jsonify, current_app
import sqlite3
from . import newsletter_bp
from ..database import get_db_connection

@newsletter_bp.route('/subscribe', methods=['POST'])
def subscribe_newsletter():
    """Handles B2C newsletter subscription."""
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify(message="Email is required", success=False), 400

    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Using INSERT OR IGNORE to prevent errors on duplicate entries
        cursor.execute(
            "INSERT OR IGNORE INTO newsletter_subscribers (email, type, is_active) VALUES (?, 'B2C', TRUE)",
            (email,)
        )
        db.commit()

        if cursor.rowcount > 0:
            message = "Subscription successful"
            status_code = 201
            current_app.logger.info(f"New B2C newsletter subscription: {email}")
        else:
            message = "Email is already subscribed"
            status_code = 200

        return jsonify(message=message, success=True), status_code

    except sqlite3.IntegrityError:
        # This case is less likely with INSERT OR IGNORE but kept for safety
        db.rollback()
        return jsonify(message="Email is already subscribed", success=True), 200
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error during B2C newsletter subscription for {email}: {e}", exc_info=True)
        return jsonify(message="Subscription failed due to a server error", success=False), 500

