# generate_label.py
# Script pour générer les étiquettes des produits Maison Trüvra
# Installation requise : pip install Pillow

from PIL import Image, ImageDraw, ImageFont
import os
# import datetime # Plus nécessaire ici si format_date_french est importé
from utils import format_date_french # Importation de la fonction partagée

# --- Configuration Générale des Étiquettes ---
LABEL_OUTPUT_SUBDIR = "etiquettes" # Sous-dossier pour les étiquettes
# Assurez-vous que arial.ttf est accessible, par exemple dans le même dossier ou via un chemin absolu/relatif correct
# Si vous utilisez un environnement virtuel ou Docker, assurez-vous que la police est incluse.
DEFAULT_FONT_PATH = os.path.join(os.path.dirname(__file__), "arial.ttf")  # Exemple pour rendre le chemin plus robuste
if not os.path.exists(DEFAULT_FONT_PATH):
    # Fallback très basique si arial.ttf n'est pas trouvée au chemin spécifié
    print(f"Attention: Police {DEFAULT_FONT_PATH} non trouvée. Tentative d'utiliser un nom de police système si possible ou défaut Pillow.")
    DEFAULT_FONT_PATH = "arial.ttf" # Laisse Pillow tenter de la trouver dans les chemins système standards

MAISON_TRUVRA_LOGO_PATH = os.path.join(os.path.dirname(__file__), "image_6b84ab.png") # Logo image_6b84ab.png

DEFAULT_FONT_SIZE_TITLE = 24
DEFAULT_FONT_SIZE_TEXT = 16
DEFAULT_FONT_SIZE_SMALL = 12
TEXT_COLOR = (0, 0, 0) # Noir
LABEL_BACKGROUND_COLOR = (255, 255, 255) # Blanc par défaut

POT_LABEL_CONFIG = {
    "Grand 200mL": {
        "avant": {"width": 300, "height": 200, "shape": "rectangle", "logo_area": (10, 10, 100, 50)},
        "arriere": {"width": 300, "height": 200, "shape": "rectangle", "qr_code_area": (200, 130, 290, 190)},
    },
    "Carré 150mL": {
        "avant": {"width": 250, "height": 180, "shape": "rectangle", "logo_area": (10, 10, 90, 45)},
        "arriere": {"width": 250, "height": 180, "shape": "rectangle", "qr_code_area": (160, 110, 230, 170)},
    },
    "Petit 100mL": {
        "avant": {"width": 200, "height": 150, "shape": "rectangle", "logo_area": (5, 5, 75, 35)},
        "arriere": {"width": 200, "height": 150, "shape": "rectangle", "qr_code_area": (130, 90, 190, 140)},
    },
    "Sachet plastique": { 
        "avant": {"width": 350, "height": 250, "shape": "rectangle", "logo_area": (15, 15, 120, 60), "qr_code_area": (250, 170, 340, 240)},
        "arriere": None, 
    },
    "default": { 
        "avant": {"width": 250, "height": 180, "shape": "rectangle", "logo_area": (10, 10, 90, 45)},
        "arriere": {"width": 250, "height": 180, "shape": "rectangle", "qr_code_area": (160, 110, 230, 170)},
    }
}

PRODUCT_CONTENT_CONFIG = {
    "Truffe Noire du Périgord Entière fraîche": {
        "texte_avant_specifique": "L'excellence de la Truffe Noire Fraîche.",
        "image_produit_path": None, 
        "ingredients_specifiques": None 
    },
    "Brisures de Truffe Noire du Périgord": {
        "texte_avant_specifique": "L'intensité des brisures de Melanosporum.",
        "image_produit_path": None, 
        "ingredients_specifiques": "Truffe Noire (Tuber melanosporum), jus de truffe Tuber melanosporum, sel."
    },
    "Huile infusée à la Truffe Noire du Périgord": {
        "texte_avant_specifique": "Subtilement parfumée.",
        "image_produit_path": None, 
        "ingredients_specifiques": "Huile d'olive vierge extra, arôme naturel de truffe noire (Tuber melanosporum)."
    },
    "default": { 
        "texte_avant_specifique": "Un délice Maison Trüvra.",
        "image_produit_path": None,
        "ingredients_specifiques": None
    }
}

def load_font(size, weight="normal"):
    font_path_to_try = DEFAULT_FONT_PATH
    # Tentative de gestion du gras un peu plus simple
    # Pillow peut simuler le gras si la police ne l'a pas en variante explicite, mais le résultat varie.
    # Pour un contrôle fin, des fichiers de police distincts (arialbd.ttf) sont meilleurs.
    # Ici, on se fie principalement au chemin de base et Pillow fera de son mieux.
    # Si DEFAULT_FONT_PATH pointe déjà vers une police bold, weight="bold" ne changera rien.
    try:
        return ImageFont.truetype(font_path_to_try, size)
    except IOError:
        print(f"Attention : Police {font_path_to_try} non trouvée. Utilisation de la police par défaut de Pillow.")
        return ImageFont.load_default()


def draw_text_multiline(draw, text, position, font, max_width, text_color=TEXT_COLOR, spacing=4, align="left"):
    if not text: return position[1]
    lines = []
    words = text.split()
    if not words: return position[1] # Rien à dessiner si le texte est vide ou que des espaces

    current_line = words[0]
    for word in words[1:]:
        test_line = f"{current_line} {word}"
        try:
            bbox = draw.textbbox((0,0), test_line, font=font)
            line_width = bbox[2] - bbox[0]
        except AttributeError: # Fallback pour les anciennes versions de Pillow
            line_width, _ = draw.textsize(test_line, font=font)

        if line_width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)

    y_text = position[1]
    for line in lines:
        x_text = position[0]
        line_actual_width = 0
        line_height = 0
        try:
            bbox_line = draw.textbbox((0,0), line, font=font)
            line_actual_width = bbox_line[2] - bbox_line[0]
            line_height = bbox_line[3] - bbox_line[1] 
        except AttributeError: # Fallback
            line_actual_width, line_height = draw.textsize(line, font=font)
            
        if align == "center":
            x_text = position[0] + (max_width - line_actual_width) / 2
        elif align == "right":
            x_text = position[0] + (max_width - line_actual_width)
        
        draw.text((x_text, y_text), line, font=font, fill=text_color)
        y_text += line_height + spacing
    return y_text


def paste_image_in_area(base_image, image_to_paste_path, area_coords):
    if image_to_paste_path and os.path.exists(image_to_paste_path):
        try:
            img_to_paste = Image.open(image_to_paste_path)
            
            area_width = area_coords[2] - area_coords[0]
            area_height = area_coords[3] - area_coords[1]
            
            img_to_paste.thumbnail((area_width, area_height), Image.Resampling.LANCZOS)
            
            paste_x = area_coords[0] + (area_width - img_to_paste.width) // 2
            paste_y = area_coords[1] + (area_height - img_to_paste.height) // 2
            
            if img_to_paste.mode == 'RGBA':
                base_image.paste(img_to_paste, (paste_x, paste_y), img_to_paste)
            else:
                base_image.paste(img_to_paste, (paste_x, paste_y))
            return True
        except Exception as e_img:
            print(f"Erreur chargement/collage image {image_to_paste_path}: {e_img}")
    else:
        if image_to_paste_path: print(f"Image non trouvée : {image_to_paste_path}")
    return False

def create_product_label(product_data, qr_code_path, base_output_dir):
    try:
        label_output_path = os.path.join(base_output_dir, LABEL_OUTPUT_SUBDIR)
        if not os.path.exists(label_output_path):
            os.makedirs(label_output_path)

        pot_type = product_data.get("pot_selectionne")
        if not pot_type: 
             pot_type = "Sachet plastique" if product_data.get("type_produit_detail") == "frais" else "default"
        
        label_spec_pot = POT_LABEL_CONFIG.get(pot_type, POT_LABEL_CONFIG["default"])
        product_name_key = product_data.get("nom_produit_affiche", "default")
        content_spec_product = PRODUCT_CONTENT_CONFIG.get(product_name_key, PRODUCT_CONTENT_CONFIG["default"])
        num_identification = product_data.get("numero_identification", "N/A")

        font_title = load_font(DEFAULT_FONT_SIZE_TITLE, weight="bold")
        font_text = load_font(DEFAULT_FONT_SIZE_TEXT)
        font_small = load_font(DEFAULT_FONT_SIZE_SMALL)

        spec_avant = label_spec_pot["avant"]
        img_avant = Image.new("RGB", (spec_avant["width"], spec_avant["height"]), LABEL_BACKGROUND_COLOR)
        draw_avant = ImageDraw.Draw(img_avant)
        
        current_y = 15 
        padding_x = 15

        if spec_avant.get("logo_area"):
            if MAISON_TRUVRA_LOGO_PATH and os.path.exists(MAISON_TRUVRA_LOGO_PATH):
                 paste_image_in_area(img_avant, MAISON_TRUVRA_LOGO_PATH, spec_avant["logo_area"])
                 current_y = max(current_y, spec_avant["logo_area"][3] + 10)
            else:
                print(f"Logo non trouvé: {MAISON_TRUVRA_LOGO_PATH}. Il ne sera pas ajouté.")


        nom_produit_affiche = product_data.get("nom_produit_affiche", "Produit Maison Trüvra")
        current_y = draw_text_multiline(draw_avant, nom_produit_affiche, 
                                        (padding_x, current_y), font_title, 
                                        spec_avant["width"] - 2 * padding_x, align="center")
        current_y += 10

        if content_spec_product.get("texte_avant_specifique"):
            current_y = draw_text_multiline(draw_avant, content_spec_product["texte_avant_specifique"],
                                            (padding_x, current_y), font_text, 
                                            spec_avant["width"] - 2 * padding_x, align="center")
            current_y += 10
        
        if content_spec_product.get("image_produit_path"):
            img_prod_area_height = spec_avant["height"] // 3
            img_prod_area_width = spec_avant["width"] - 4 * padding_x 
            img_prod_area_y0 = current_y
            img_prod_area_x0 = (spec_avant["width"] - img_prod_area_width) // 2
            img_prod_area = (img_prod_area_x0, img_prod_area_y0, img_prod_area_x0 + img_prod_area_width, img_prod_area_y0 + img_prod_area_height)
            if paste_image_in_area(img_avant, content_spec_product["image_produit_path"], img_prod_area):
                current_y += img_prod_area_height + 10

        poids_net_str = f"Poids Net : {product_data.get('poids_net_final_g', 'N/A')} g"
        poids_height = 0
        try:
            bbox_poids = draw_avant.textbbox((0,0), poids_net_str, font=font_text)
            poids_height = bbox_poids[3] - bbox_poids[1]
        except AttributeError:
            _, poids_height = draw_avant.textsize(poids_net_str, font=font_text)

        y_poids = spec_avant["height"] - poids_height - 15 
        draw_text_multiline(draw_avant, poids_net_str, (padding_x, y_poids), font_text, spec_avant["width"] - 2 * padding_x, align="center")

        if pot_type == "Sachet plastique" and spec_avant.get("qr_code_area") and qr_code_path and os.path.exists(qr_code_path):
            paste_image_in_area(img_avant, qr_code_path, spec_avant["qr_code_area"])

        path_etiquette_avant = os.path.join(label_output_path, f"ETIQUETTE_AVANT_{num_identification}.png")
        img_avant.save(path_etiquette_avant)
        print(f"Étiquette avant générée : {path_etiquette_avant}")

        path_etiquette_arriere = None
        if label_spec_pot.get("arriere"):
            spec_arriere = label_spec_pot["arriere"]
            img_arriere = Image.new("RGB", (spec_arriere["width"], spec_arriere["height"]), LABEL_BACKGROUND_COLOR)
            draw_arriere = ImageDraw.Draw(img_arriere)
            
            current_y_arr = 10
            
            ingredients_text = product_data.get("ingredients_affichage", "Voir emballage")
            if content_spec_product.get("ingredients_specifiques"):
                ingredients_text = content_spec_product["ingredients_specifiques"]
            current_y_arr = draw_text_multiline(draw_arriere, f"Ingrédients : {ingredients_text}", (10, current_y_arr), font_small, spec_arriere["width"] - 20)
            
            ddm_str = format_date_french(product_data.get("ddm"))
            current_y_arr = draw_text_multiline(draw_arriere, f"DDM : {ddm_str}", (10, current_y_arr), font_small, spec_arriere["width"] - 20) # DDM plus court
            
            current_y_arr = draw_text_multiline(draw_arriere, f"ID : {num_identification}", (10, current_y_arr), font_small, spec_arriere["width"] - 20)
            if product_data.get("numero_lot_manuel"):
                current_y_arr = draw_text_multiline(draw_arriere, f"Lot : {product_data['numero_lot_manuel']}", (10, current_y_arr), font_small, spec_arriere["width"] - 20)
            
            current_y_arr = draw_text_multiline(draw_arriere, "Maison Trüvra - contact@maisontruvra.com", (10, current_y_arr + 5), font_small, spec_arriere["width"] - 20)

            if spec_arriere.get("qr_code_area") and qr_code_path and os.path.exists(qr_code_path):
                paste_image_in_area(img_arriere, qr_code_path, spec_arriere["qr_code_area"])
            else:
                print(f"QR Code non ajouté à l'étiquette arrière (config manquante, chemin invalide ou fichier inexistant)")

            path_etiquette_arriere = os.path.join(label_output_path, f"ETIQUETTE_ARRIERE_{num_identification}.png")
            img_arriere.save(path_etiquette_arriere)
            print(f"Étiquette arrière générée : {path_etiquette_arriere}")

        return path_etiquette_avant, path_etiquette_arriere

    except Exception as e:
        print(f"Erreur majeure lors de la génération des étiquettes : {e}")
        import traceback
        traceback.print_exc()
        return None, None

if __name__ == '__main__':
    print("Test de la génération d'étiquettes...")
    # Le dossier mock_qr_dir sera créé à côté de generate_label.py si utils.py est à la racine
    # ou adaptez le chemin pour sortir les fichiers de test où vous le souhaitez.
    mock_output_base_dir = os.path.join(os.path.dirname(__file__), "output_test_labels")
    
    mock_qr_code_dir = os.path.join(mock_output_base_dir, "qrcodes_production") 
    if not os.path.exists(mock_qr_code_dir):
        os.makedirs(mock_qr_code_dir)
    
    mock_qr_path = os.path.join(mock_qr_code_dir, "QR_MTID-TESTLABEL-001.png")

    if not os.path.exists(mock_qr_path):
        try:
            qr_test_img = Image.new("RGB", (100,100), "grey") 
            draw_qr = ImageDraw.Draw(qr_test_img)
            font_qr_test = load_font(12) if DEFAULT_FONT_PATH else ImageFont.load_default()
            draw_qr.text((10,10), "QR TEST", fill="white", font=font_qr_test)
            qr_test_img.save(mock_qr_path)
            print(f"Faux QR code de test créé : {mock_qr_path}")
        except Exception as e_mock_qr:
            print(f"Erreur création faux QR code: {e_mock_qr}")
            mock_qr_path = None

    if not os.path.exists(MAISON_TRUVRA_LOGO_PATH):
         print(f"ATTENTION: Logo {MAISON_TRUVRA_LOGO_PATH} non trouvé. Le logo ne sera pas inclus sur l'étiquette de test.")
    
    mock_product_data_1 = {
        "nom_produit_affiche": "Brisures de Truffe Noire du Périgord",
        "numero_identification": "MTID-TESTLABEL-001",
        "numero_lot_manuel": "LOT-ETIQ-A",
        "pot_selectionne": "Carré 150mL", 
        "poids_net_final_g": 150,
        "ddm": "2025-12-31",
        "ingredients_affichage": "Tuber melanosporum 80%, jus de truffe Tuber melanosporum, sel de Guérande.",
        "type_produit_detail": "conserve"
    }
    mock_product_data_2 = {
        "nom_produit_affiche": "Truffe Noire du Périgord Entière fraîche",
        "numero_identification": "MTID-TESTLABEL-002",
        "numero_lot_manuel": "LOT-ETIQ-B",
        "pot_selectionne": None, 
        "poids_net_final_g": 30,
        "ddm": "2025-01-15", # DDM doit être une date valide pour le formatage
        "ingredients_affichage": "100% Tuber melanosporum.",
        "type_produit_detail": "frais"
    }
    
    if not os.path.exists(mock_output_base_dir):
        os.makedirs(mock_output_base_dir)

    if mock_qr_path and os.path.exists(mock_qr_path):
        print(f"\nGénération étiquette pour: {mock_product_data_1['nom_produit_affiche']}")
        create_product_label(mock_product_data_1, mock_qr_path, mock_output_base_dir)
        
        mock_qr_path_2 = os.path.join(mock_qr_code_dir, "QR_MTID-TESTLABEL-002.png")
        if not os.path.exists(mock_qr_path_2):
            try:
                qr_test_img_2 = Image.new("RGB", (100,100), "darkblue")
                draw_qr_2 = ImageDraw.Draw(qr_test_img_2)
                font_qr_test_2 = load_font(12) if DEFAULT_FONT_PATH else ImageFont.load_default()
                draw_qr_2.text((10,10), "QR TEST 2", fill="white", font=font_qr_test_2)
                qr_test_img_2.save(mock_qr_path_2)
            except Exception as e_qr2:
                 print(f"Erreur création faux QR code 2: {e_qr2}")
        
        if os.path.exists(mock_qr_path_2):
            print(f"\nGénération étiquette pour: {mock_product_data_2['nom_produit_affiche']}")
            create_product_label(mock_product_data_2, mock_qr_path_2, mock_output_base_dir)
        else:
            print(f"QR code de test 2 ({mock_qr_path_2}) non disponible.")
            
    else:
        print(f"QR code de test ({mock_qr_path}) non disponible, test des étiquettes annulé.")
