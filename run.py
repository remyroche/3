import os
from flask import Flask, render_template, session, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from config import Config
from database import db
from models import User, B2BUser
from auth.routes import auth_blueprint
from products.routes import product_blueprint
from orders.routes import order_blueprint
from newsletter.b2c_routes import b2c_newsletter_blueprint
from newsletter.b2b_routes import b2b_newsletter_blueprint
from admin_api.routes import admin_api_blueprint
from inventory.routes import inventory_blueprint

# B2B Blueprints
from b2b.profile_routes import profile_blueprint
from b2b.invoice_routes import invoice_blueprint
from b2b.loyalty_routes import loyalty_blueprint
from b2b.asset_routes import asset_blueprint
from b2b.order_routes import order_blueprint


def create_app():
    app = Flask(__name__,
                static_folder='website/dist',
                static_url_path='',
                template_folder='website/dist')
    app.config.from_object(Config)

    db.init_app(app)
    migrate = Migrate(app, db)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        if session.get('user_type') == 'b2b':
            return B2BUser.query.get(int(user_id))
        return User.query.get(int(user_id))

    @app.before_request
    def before_request():
        g.user = current_user

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(product_blueprint)
    app.register_blueprint(order_blueprint)
    app.register_blueprint(b2c_newsletter_blueprint)
    app.register_blueprint(b2b_newsletter_blueprint)
    app.register_blueprint(admin_api_blueprint, url_prefix='/admin/api')
    app.register_blueprint(inventory_blueprint, url_prefix='/inventory')

    # Register B2B blueprints
    app.register_blueprint(profile_blueprint, url_prefix='/pro')
    app.register_blueprint(invoice_blueprint, url_prefix='/pro')
    app.register_blueprint(loyalty_blueprint, url_prefix='/pro')
    app.register_blueprint(asset_blueprint, url_prefix='/pro')
    app.register_blueprint(order_blueprint, url_prefix='/pro')


    # Serve Svelte app
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        # Let Flask routing handle API and other specific routes
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return app.send_static_file(path)
        # For client-side routing, serve the main index.html
        return app.send_static_file('index.html')

    return app, db

app, db = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
