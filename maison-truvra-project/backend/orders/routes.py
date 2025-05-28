# backend/orders/routes.py
from flask import Blueprint, request, jsonify, current_app, g
from ..database import get_db, record_stock_movement
from ..utils import is_valid_email
from ..auth.routes import admin_required # Assuming you might need admin_required for some order ops later
import jwt # For decoding token if user_id comes from token

orders_bp = Blueprint('orders_bp', __name__, url_prefix='/api/orders')

@orders_bp.route('/checkout', methods=['POST'])
def checkout():
    data = request.get_json()
    current_app.logger.info(f"Données de checkout reçues : {data}")

    customer_email = data.get('customerEmail')
    shipping_address_data = data.get('shippingAddress') 
    cart_items = data.get('cartItems')
    
    # Determine user_id: from payload if explicitly sent, or from JWT if available
    user_id = data.get('userId', None)
    if not user_id and hasattr(g, 'current_user_id') and g.current_user_id:
        user_id = g.current_user_id
    elif not user_id and request.headers.get('Authorization'): # Fallback: check token directly if g not set
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
                user_id = payload.get('user_id')
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                user_id = None # Token invalid or expired, proceed as guest or require login

    # --- Validations d'entrée ---
    if not customer_email or not is_valid_email(customer_email):
        return jsonify({"success": False, "message": "Adresse e-mail du client invalide ou manquante."}), 400
    if not shipping_address_data or not all(k in shipping_address_data for k in ['address', 'zipcode', 'city', 'country', 'firstname', 'lastname']):
        return jsonify({"success": False, "message": "Adresse de livraison incomplète."}), 400
    if not cart_items or not isinstance(cart_items, list) or len(cart_items) == 0:
        return jsonify({"success": False, "message": "Panier vide ou invalide."}), 400

    shipping_address_full = (
        f"{shipping_address_data.get('firstname', '')} {shipping_address_data.get('lastname', '')}\n"
        f"{shipping_address_data['address']}\n"
        f"{shipping_address_data.get('apartment', '')}\n"
        f"{shipping_address_data['zipcode']} {shipping_address_data['city']}\n"
        f"{shipping_address_data['country']}"
    ).replace('\n\n','\n').strip()

    db = None # Initialize db to None
    try:
        db = get_db()
        cursor = db.cursor()
        
        total_amount_calculated = 0
        validated_items_for_order = []

        for item_from_cart in cart_items:
            product_id_cart = item_from_cart.get('id')
            quantity_ordered = int(item_from_cart.get('quantity', 0))
            price_from_cart = float(item_from_cart.get('price', 0))
            variant_option_id_cart = item_from_cart.get('variant_option_id', None) 
            
            if quantity_ordered <= 0:
                raise ValueError(f"Quantité invalide pour {item_from_cart.get('name')}.")

            actual_price_db = 0
            current_stock_db = 0

            if variant_option_id_cart:
                cursor.execute("SELECT price, stock_quantity FROM product_weight_options WHERE option_id = ? AND product_id = ?", 
                               (variant_option_id_cart, product_id_cart))
                variant_info = cursor.fetchone()
                if not variant_info:
                    raise ValueError(f"Option de produit {item_from_cart.get('name')} (Variante ID: {variant_option_id_cart}) non trouvée.")
                actual_price_db = variant_info['price']
                current_stock_db = variant_info['stock_quantity']
            else: 
                cursor.execute("SELECT base_price, stock_quantity FROM products WHERE id = ?", (product_id_cart,))
                product_info = cursor.fetchone()
                if not product_info:
                    raise ValueError(f"Produit {item_from_cart.get('name')} (ID: {product_id_cart}) non trouvé.")
                if product_info['base_price'] is None and not variant_option_id_cart:
                     raise ValueError(f"Configuration de prix incorrecte pour le produit {product_id_cart}. variant_option_id manquant.")
                actual_price_db = product_info['base_price']
                current_stock_db = product_info['stock_quantity']
            
            if abs(actual_price_db - price_from_cart) > 0.01: # Price check tolerance
                current_app.logger.warning(
                    f"Discordance de prix pour {product_id_cart} (Variante: {variant_option_id_cart}). "
                    f"Client: {price_from_cart}, DB: {actual_price_db}. Utilisation du prix DB."
                )
            
            if current_stock_db < quantity_ordered:
                raise ValueError(f"Stock insuffisant pour {item_from_cart.get('name')}. Demandé: {quantity_ordered}, Disponible: {current_stock_db}")

            total_amount_calculated += actual_price_db * quantity_ordered
            validated_items_for_order.append({
                "product_id": product_id_cart,
                "product_name": item_from_cart.get('name'),
                "quantity": quantity_ordered,
                "price_at_purchase": actual_price_db,
                "variant": item_from_cart.get('variant'),
                "variant_option_id": variant_option_id_cart
            })
        
        payment_successful = True # Placeholder for actual payment integration
        if not payment_successful:
            if db: db.rollback()
            return jsonify({"success": False, "message": "Le paiement a échoué."}), 400

        customer_name_for_order = f"{shipping_address_data.get('firstname', '')} {shipping_address_data.get('lastname', '')}".strip()
        cursor.execute(
            "INSERT INTO orders (user_id, customer_email, customer_name, shipping_address, total_amount, status) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, customer_email, customer_name_for_order, shipping_address_full, total_amount_calculated, 'Paid')
        )
        order_id = cursor.lastrowid
        current_app.logger.info(f"Commande #{order_id} créée pour {customer_email}.")

        for item in validated_items_for_order:
            cursor.execute(
                '''INSERT INTO order_items (order_id, product_id, product_name, quantity, price_at_purchase, variant, variant_option_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (order_id, item['product_id'], item['product_name'], item['quantity'], 
                 item['price_at_purchase'], item['variant'], item['variant_option_id'])
            )
            record_stock_movement(cursor, item['product_id'], -item['quantity'], 'vente', 
                                  variant_option_id=item['variant_option_id'], order_id=order_id, 
                                  notes=f"Vente pour commande #{order_id}")
        
        db.commit()
        
        return jsonify({
            "success": True, 
            "message": "Commande passée avec succès !",
            "orderId": f"TRUVRA{order_id:05d}",
            "totalAmount": round(total_amount_calculated, 2)
        }), 201

    except ValueError as ve:
        if db: db.rollback()
        current_app.logger.warning(f"Erreur de validation lors du checkout : {ve}")
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        if db: db.rollback()
        current_app.logger.error(f"Erreur de checkout : {e}", exc_info=True)
        return jsonify({"success": False, "message": "Une erreur interne est survenue lors de la création de la commande."}), 500
    finally:
        if db: db.close()

@orders_bp.route('/history', methods=['GET'])
def get_order_history():
    # This route should be protected, e.g., by requiring a valid user token
    user_id = None
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"success": False, "message": "Authentification requise."}), 401

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
        user_id = payload.get('user_id')
        if not user_id:
            return jsonify({"success": False, "message": "Token invalide (user_id manquant)."}), 401
    except jwt.ExpiredSignatureError:
        return jsonify({"success": False, "message": "Token expiré."}), 401
    except jwt.InvalidTokenError:
        return jsonify({"success": False, "message": "Token invalide."}), 401

    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT order_id, total_amount, order_date, status FROM orders WHERE user_id = ? ORDER BY order_date DESC",
            (user_id,)
        )
        orders = [dict(row) for row in cursor.fetchall()]
        return jsonify({"success": True, "orders": orders}), 200
    except Exception as e:
        current_app.logger.error(f"Erreur lors de la récupération de l'historique des commandes pour l'utilisateur {user_id}: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Erreur serveur lors de la récupération de l'historique."}), 500
    finally:
        if db: db.close()
