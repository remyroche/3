import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
from flask import current_app, url_for
import uuid # For potentially more unique filenames if needed

# --- QR Code Generation ---
def generate_qr_code_for_item(item_uid, product_id, product_name):
    """
    Generates a QR code for a given item UID and saves it.
    The QR code will typically encode a URL to the item's digital passport.
    Returns the relative path to the saved QR code image.
    """
    qr_folder = current_app.config['QR_CODE_FOLDER']
    os.makedirs(qr_folder, exist_ok=True)

    # Define the data for the QR code (e.g., URL to the item's passport)
    # Assuming a route like /passport/<item_uid> exists and is publicly accessible or via app
    # For now, let's use a placeholder or a direct item UID encoding.
    # In a real app, this would be a full URL.
    # passport_url = url_for('passport.view_passport', item_uid=item_uid, _external=True) # If passport blueprint exists
    passport_data_or_url = f"{current_app.config.get('APP_BASE_URL', 'https://maisontruvra.com')}/passport/{item_uid}"


    qr_filename = f"qr_{item_uid}.png"
    qr_filepath = os.path.join(qr_folder, qr_filename)

    try:
        img = qrcode.make(passport_data_or_url)
        img.save(qr_filepath)
        current_app.logger.info(f"QR Code generated for item {item_uid} at {qr_filepath}")
        # Return path relative to the ASSET_STORAGE_PATH's 'qr_codes' subfolder
        return os.path.join('qr_codes', qr_filename) 
    except Exception as e:
        current_app.logger.error(f"Failed to generate QR code for {item_uid}: {e}")
        raise # Re-raise to be handled by the caller, possibly rolling back a transaction


# --- Digital Passport Generation (HTML) ---
def generate_item_passport(item_uid, product_id, product_name, batch_number=None, production_date=None, expiry_date=None, additional_info=None):
    """
    Generates an HTML digital passport for a specific item.
    Returns the relative path to the saved HTML file.
    `additional_info` could be a dictionary with more product-specific details.
    """
    passport_folder = current_app.config['PASSPORT_FOLDER']
    os.makedirs(passport_folder, exist_ok=True)
    
    passport_filename = f"passport_{item_uid}.html"
    passport_filepath = os.path.join(passport_folder, passport_filename)

    # Get logo path from config
    logo_path_config = current_app.config.get('MAISON_TRUVRA_LOGO_PATH_PASSPORT', None)
    logo_html_embed = ""
    if logo_path_config and os.path.exists(logo_path_config):
        # For simplicity, just linking to it if served, or could embed as base64.
        # This assumes logo can be served from a static path or similar.
        # For a self-contained HTML, embedding as base64 might be better.
        # For now, this is a placeholder for how logo is included.
        logo_url_path = os.path.join('/static/assets/logos', os.path.basename(logo_path_config)) # Example static path
        # logo_html_embed = f'<img src="{logo_url_path}" alt="Maison Trüvra Logo" style="max-height: 80px; margin-bottom: 20px;">'
        # Correct approach: make logo accessible via a URL or embed. For now, we'll just show text.
        pass


    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-ARIAL">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Passeport Produit - {item_uid}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; padding: 20px; border: 1px solid #eee; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; border-bottom: 1px solid #eee; padding-bottom: 15px; margin-bottom: 20px; }}
            .header h1 {{ margin: 0; color: #333; }}
            .content {{ font-size: 16px; color: #555; }}
            .content p {{ margin: 10px 0; }}
            .content strong {{ color: #000; }}
            .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #aaa; }}
        </style>
    </head>
    <body>
        <div class="header">
            {logo_html_embed if logo_html_embed else '<h2>Maison Trüvra</h2>'}
            <h1>Passeport d'Authenticité</h1>
        </div>
        <div class="content">
            <p><strong>Identifiant Unique (UID):</strong> {item_uid}</p>
            <p><strong>Produit:</strong> {product_name} (ID: {product_id})</p>
            {f'<p><strong>Numéro de Lot:</strong> {batch_number}</p>' if batch_number else ''}
            {f'<p><strong>Date de Production:</strong> {production_date}</p>' if production_date else ''}
            {f'<p><strong>Date d&rsquo;Expiration:</strong> {expiry_date}</p>' if expiry_date else ''}
            <p>Ce produit est un article authentique de Maison Trüvra, fabriqué avec soin et passion.</p>
            """
    if additional_info and isinstance(additional_info, dict):
        html_content += "<h3>Informations Complémentaires:</h3>"
        for key, value in additional_info.items():
            html_content += f"<p><strong>{key.replace('_', ' ').title()}:</strong> {value}</p>"
    
    html_content += """
        </div>
        <div class="footer">
            &copy; {datetime.now().year} Maison Trüvra. Tous droits réservés.
        </div>
    </body>
    </html>
    """

    try:
        with open(passport_filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        current_app.logger.info(f"Passport HTML generated for item {item_uid} at {passport_filepath}")
        # Return path relative to the ASSET_STORAGE_PATH's 'passports' subfolder
        return os.path.join('passports', passport_filename)
    except Exception as e:
        current_app.logger.error(f"Failed to generate passport HTML for {item_uid}: {e}")
        raise


# --- Product Label Generation (PDF or Image) ---
def generate_product_label(product_id, product_name, product_description, product_price, currency, product_sku, item_uid_for_label=None):
    """
    Generates a product label as an image (e.g., PNG).
    If item_uid_for_label is provided, it's included in the label text and filename.
    Returns the relative path to the saved label image.
    """
    label_folder = current_app.config['LABEL_FOLDER']
    os.makedirs(label_folder, exist_ok=True)

    # Use config for font and logo
    default_font_path = current_app.config.get('DEFAULT_FONT_PATH')
    logo_path_config = current_app.config.get('MAISON_TRUVRA_LOGO_PATH_LABEL')

    # Filename generation
    product_id_display = str(product_id) + "_" + product_name.replace(" ", "_").lower()
    if item_uid_for_label:
        label_filename = f"label_item_{item_uid_for_label}.png"
    else:
        label_filename = f"label_product_{product_id_display}.png"
    
    label_filepath = os.path.join(label_folder, label_filename)

    # Label dimensions and appearance (example)
    width, height = 400, 250
    bg_color = (255, 255, 255)
    text_color = (0, 0, 0)
    
    try:
        font_main_size = 18
        font_small_size = 14
        font_main = ImageFont.truetype(default_font_path, font_main_size) if default_font_path and os.path.exists(default_font_path) else ImageFont.load_default()
        font_small = ImageFont.truetype(default_font_path, font_small_size) if default_font_path and os.path.exists(default_font_path) else ImageFont.load_default()

        label_image = Image.new('RGB', (width, height), color=bg_color)
        draw = ImageDraw.Draw(label_image)

        padding = 20
        current_y = padding

        # Logo (optional)
        if logo_path_config and os.path.exists(logo_path_config):
            try:
                logo_img = Image.open(logo_path_config)
                logo_img.thumbnail((width - 2 * padding, 60)) # Max width, max height 60
                label_image.paste(logo_img, ( (width - logo_img.width) // 2, current_y), logo_img if logo_img.mode == 'RGBA' else None)
                current_y += logo_img.height + 10
            except Exception as logo_err:
                current_app.logger.warning(f"Could not load or place logo on label: {logo_err}")
                draw.text((padding, current_y), "Maison Trüvra", font=font_main, fill=text_color) # Fallback text
                current_y += font_main_size + 5


        # Product Name
        draw.text((padding, current_y), product_name, font=font_main, fill=text_color)
        current_y += font_main_size + 10

        # Product Description (shortened)
        short_desc = (product_description[:60] + '...') if product_description and len(product_description) > 60 else product_description
        if short_desc:
            draw.text((padding, current_y), short_desc, font=font_small, fill=text_color)
            current_y += font_small_size + 5

        # Price
        price_text = f"Prix: {product_price:.2f} {currency}"
        draw.text((padding, current_y), price_text, font=font_small, fill=text_color)
        current_y += font_small_size + 10

        # SKU / UID
        if item_uid_for_label:
            id_text = f"UID: {item_uid_for_label}"
        else:
            id_text = f"SKU: {product_sku}"
        draw.text((padding, current_y), id_text, font=font_small, fill=text_color)
        current_y += font_small_size + 5
        
        # Add a simple border
        draw.rectangle([(0,0), (width-1, height-1)], outline=text_color, width=1)

        label_image.save(label_filepath)
        current_app.logger.info(f"Label generated for {'item ' + item_uid_for_label if item_uid_for_label else 'product ' + str(product_id)} at {label_filepath}")
        # Return path relative to the ASSET_STORAGE_PATH's 'labels' subfolder
        return os.path.join('labels', label_filename)
    except Exception as e:
        current_app.logger.error(f"Failed to generate label for {'item ' + item_uid_for_label if item_uid_for_label else 'product ' + str(product_id)}: {e}")
        raise
