# backend/inventory/routes.py
from flask import Blueprint, request, jsonify, current_app
from ..database import get_db, record_stock_movement # Importation relative

inventory_bp = Blueprint('inventory_bp', __name__, url_prefix='/api/inventory')

@inventory_bp.route('/add', methods=['POST']) # Sera /api/inventory/add
def add_inventory_stock():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity') # Doit être positif pour une addition
    variant_option_id = data.get('variant_option_id', None) 
    # Types de mouvement pour une addition : 'addition' (générique), 'creation_lot', 'retour_client'
    movement_type = data.get('movement_type', 'addition') 
    notes = data.get('notes', '')

    if not product_id or not isinstance(quantity, int) or quantity <= 0:
        return jsonify({"success": False, "message": "ID produit et quantité positive valides requis."}), 400
    
    allowed_addition_types = ['addition', 'creation_lot', 'retour_client', 'ajustement_manuel']
    if movement_type not in allowed_addition_types:
        return jsonify({"success": False, "message": f"Type de mouvement '{movement_type}' invalide pour une addition de stock. Types autorisés: {', '.join(allowed_addition_types)}"}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        record_stock_movement(cursor, product_id, quantity, movement_type, 
                              variant_option_id=variant_option_id, notes=notes)
        db.commit()
        current_app.logger.info(f"Stock ajouté pour produit {product_id}, qté {quantity}, type {movement_type}")
        return jsonify({"success": True, "message": f"{quantity} unité(s) de {product_id} ajoutée(s) à l'inventaire."}), 200
    except ValueError as ve:
        db.rollback()
        current_app.logger.warning(f"Erreur de validation lors de l'ajout à l'inventaire : {ve}")
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Erreur d'ajout à l'inventaire : {e}", exc_info=True)
        return jsonify({"success": False, "message": "Erreur interne lors de la mise à jour de l'inventaire."}), 500
    finally:
        if db:
            db.close()

@inventory_bp.route('/product/<string:product_id>', methods=['GET']) # Sera /api/inventory/product/<product_id>
def get_product_inventory_details(product_id):
    db = None
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT id, name, stock_quantity, base_price FROM products WHERE id = ?", (product_id,))
        product_info = cursor.fetchone()

        if not product_info:
            return jsonify({"success": False, "message": "Produit non trouvé"}), 404

        inventory_details = {
            "product_id": product_info["id"], 
            "name": product_info["name"]
        }

        if product_info["base_price"] is None: # Produit avec options de poids
            cursor.execute("SELECT option_id, weight_grams, stock_quantity FROM product_weight_options WHERE product_id = ? ORDER BY weight_grams", (product_id,))
            options = cursor.fetchall()
            inventory_details["current_stock_by_variant"] = [dict(opt) for opt in options]
            inventory_details["current_total_stock"] = sum(opt["stock_quantity"] for opt in options)
        else: # Produit simple
            inventory_details["current_stock"] = product_info["stock_quantity"]

        # Mouvements d'ajout (quantity_change > 0)
        cursor.execute("""
            SELECT movement_id, variant_option_id, quantity_change, movement_type, 
                   strftime('%Y-%m-%d %H:%M:%S', movement_date) as movement_date, notes 
            FROM inventory_movements 
            WHERE product_id = ? AND quantity_change > 0 
            ORDER BY movement_date DESC
        """, (product_id,))
        additions = [dict(row) for row in cursor.fetchall()]
        inventory_details["additions_log"] = additions
        inventory_details["total_added_since_beginning"] = sum(a['quantity_change'] for a in additions)

        # Mouvements de soustraction (quantity_change < 0)
        cursor.execute("""
            SELECT movement_id, variant_option_id, quantity_change, movement_type, 
                   strftime('%Y-%m-%d %H:%M:%S', movement_date) as movement_date, order_id, notes 
            FROM inventory_movements 
            WHERE product_id = ? AND quantity_change < 0
            ORDER BY movement_date DESC
        """, (product_id,))
        subtractions = [dict(row) for row in cursor.fetchall()]
        inventory_details["subtractions_log"] = subtractions
        inventory_details["total_subtracted_since_beginning"] = sum(abs(s['quantity_change']) for s in subtractions)
            
        return jsonify(inventory_details)
    except Exception as e:
        current_app.logger.error(f"Erreur lors de la récupération des détails d'inventaire pour {product_id}: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Erreur serveur lors de la récupération des détails d'inventaire."}), 500
    finally:
        if db:
            db.close()
