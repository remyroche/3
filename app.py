from flask import Flask, request, jsonify
from flask_cors import CORS

# Create the Flask application instance
app = Flask(__name__)

# Configure CORS:
# Allow requests from your frontend (http://127.0.0.1:5500)
# to any route starting with /api/
CORS(app, resources={r"/api/*": {"origins": "http://127.0.0.1:5500"}})

# Example: Load configuration from a config.py file if you have one
# app.config.from_object('config.Config')

# Dummy product data (moved to module level for broader access)
dummy_products_list = [
    {
        "id": 1, "name": "Truffe Noire Classique (Dummy)", "price": None, "base_price": None,
        "short_description": "Une truffe noire exquise, parfaite pour vos plats gastronomiques.",
        "long_description": "<p>Découvrez l'arôme intense et la saveur terreuse unique de notre Truffe Noire Classique. Soigneusement sélectionnée pour sa qualité supérieure, elle transformera vos plats les plus simples en créations culinaires mémorables.</p><p>Idéale pour les risottos, les pâtes, les œufs brouillés ou simplement râpée sur une viande grillée.</p>",
        "image_url_main": "images/placeholder-truffle-1.jpg",
        "image_urls_thumb": ["images/placeholder-truffle-1.jpg", "images/placeholder-truffle-thumb-2.jpg", "images/placeholder-truffle-thumb-3.jpg"],
        "category": "Fresh Truffles", "stock_quantity": 5, # Overall stock if no variants
        "species": "Tuber melanosporum",
        "ideal_uses": "Pâtes, risottos, œufs, viandes", "pairing_suggestions": "Vins rouges corsés, Champagne brut",
        "weight_options": [
            {"option_id": 101, "product_id": 1, "weight_grams": 20, "price": 60.00, "stock_quantity": 3},
            {"option_id": 102, "product_id": 1, "weight_grams": 50, "price": 120.50, "stock_quantity": 2},
            {"option_id": 103, "product_id": 1, "weight_grams": 100, "price": 220.00, "stock_quantity": 0}
        ]
    },
    {
        "id": 2, "name": "Huile d'Olive à la Truffe Blanche (Dummy)", "price": 35.00, "base_price": 35.00,
        "short_description": "Huile d'olive extra vierge infusée à l'arôme délicat de la truffe blanche.",
        "long_description": "<p>Notre huile d'olive extra vierge est délicatement infusée avec l'arôme envoûtant de la truffe blanche d'Alba. Quelques gouttes suffisent pour sublimer vos salades, carpaccios, ou pour apporter une touche finale luxueuse à vos plats.</p>",
        "image_url_main": "images/placeholder-truffle-oil.jpg", "image_urls_thumb": ["images/placeholder-truffle-oil.jpg"], "category": "Truffle Oils", "stock_quantity": 15,
        "species": "Infusion Tuber magnatum pico",
        "ideal_uses": "Salades, pâtes, risottos, finition", "pairing_suggestions": "Plats délicats, légumes grillés", "weight_options": []
    }
]

# Example route
@app.route('/')
def hello_world():
    return 'Hello, Maison Trüvra!'

# Placeholder for Admin Login API endpoint
@app.route('/api/admin/login', methods=['POST', 'OPTIONS']) # Add OPTIONS
def admin_login():
    if request.method == 'OPTIONS':
        # Flask-CORS should handle this, but explicitly returning OK can be a fallback
        return jsonify({'message': 'OPTIONS request successful'}), 200
    if request.method == 'POST':
        # Your actual login logic will go here
        # For now, let's assume a successful dummy login
        # data = request.get_json()
        # username = data.get('username')
        # password = data.get('password')
        return jsonify({'success': True, 'message': 'Admin login successful (dummy)', 'token': 'dummy_jwt_token'}), 200

# Placeholder for fetching products API endpoint
@app.route('/api/products', methods=['GET', 'OPTIONS']) # Add OPTIONS for preflight
def get_products():
    if request.method == 'OPTIONS':
        # Flask-CORS should handle this for defined routes.
        return jsonify({'message': 'OPTIONS request successful'}), 200
    if request.method == 'GET':
        # Replace with logic to fetch actual products from your database
        return jsonify({
            "success": True,
            "products": dummy_products_list
        }), 200

# Endpoint to fetch a single product by ID
@app.route('/api/products/<int:product_id>', methods=['GET', 'OPTIONS'])
def get_product_detail(product_id):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OPTIONS request successful'}), 200
    if request.method == 'GET':
        product = next((p for p in dummy_products_list if p["id"] == product_id), None)
        if product:
            return jsonify(product), 200 # Return the product object directly
        else:
            return jsonify({"success": False, "message": "Produit non trouvé"}), 404

# This part is for running with `python app.py` directly.
# `flask run` (used by your npm start script) handles this differently.
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)