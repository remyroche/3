# -*- coding: UTF-8 -*-
"""
This script is DEPRECATED for use within the main application flow.
Its functionality for generating HTML item passports is now primarily handled by:
backend/services/asset_service.py -> generate_item_passport()

That service uses the Flask application's configuration for paths and
can be integrated into transactional processes.

This standalone script may be kept for isolated testing of passport generation
logic if needed, but should not be relied upon for generating assets
that are tracked by the application's database or served through its routes.
"""

import os
import argparse
from datetime import datetime

# Assuming utils.py is in the same directory or accessible via PYTHONPATH
try:
    from utils import format_date_french # This might refer to a top-level utils.py
except ImportError:
    # Fallback or simple implementation if utils.py is not found in this standalone context
    def format_date_french(date_obj):
        if date_obj:
            # Attempt to parse if string, then format
            if isinstance(date_obj, str):
                try:
                    date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
                except ValueError:
                    try: # Try another common format
                        date_obj = datetime.strptime(date_obj, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                         return date_obj # Return as is if parsing fails
            return date_obj.strftime("%d/%m/%Y")
        return ""

# Configuration (originally for standalone use)
OUTPUT_DIR_PASSPORTS = "generated_assets/passports" # Relative to script location
MAISON_TRUVRA_LOGO_PATH_PASSPORT = "static_assets/logos/maison_truvra_passport_logo.png" # Example path

def generate_item_passport_html(item_uid, product_name, product_id,
                                batch_number=None, production_date_str=None, expiry_date_str=None,
                                additional_info_json_str=None, # Expect JSON string for additional info
                                output_dir=OUTPUT_DIR_PASSPORTS,
                                logo_path=MAISON_TRUVRA_LOGO_PATH_PASSPORT):
    """
    Generates an HTML digital passport for a specific item.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f"passport_{item_uid}.html"
    filepath = os.path.join(output_dir, filename)

    # Format dates if provided
    production_date_display = format_date_french(production_date_str) if production_date_str else "N/A"
    expiry_date_display = format_date_french(expiry_date_str) if expiry_date_str else "N/A"
    
    additional_info_html = ""
    if additional_info_json_str:
        try:
            import json
            additional_info = json.loads(additional_info_json_str)
            if isinstance(additional_info, dict):
                additional_info_html += "<h3>Informations Complémentaires:</h3>"
                for key, value in additional_info.items():
                    additional_info_html += f"<p><strong>{key.replace('_', ' ').title()}:</strong> {value}</p>"
        except json.JSONDecodeError:
            print(f"Warning: Could not parse additional_info_json_str: {additional_info_json_str}")
        except Exception as e:
            print(f"Warning: Error processing additional_info: {e}")


    logo_html_embed = ""
    if logo_path and os.path.exists(logo_path):
        # In a real scenario, you might embed as base64 or ensure the logo is served publicly
        # For this standalone script, we'll just note its path or a placeholder
        logo_html_embed = f'<p style="text-align:center;"><img src="{logo_path}" alt="Maison Trüvra Logo" style="max-height: 80px; margin-bottom: 20px;"></p>'
        # Note: This direct file path will only work if the HTML is viewed locally with access to this path.
        # For web serving, the logo path needs to be a URL.
    else:
        logo_html_embed = '<h2 style="text-align:center;">Maison Trüvra</h2>'


    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Passeport Produit - {item_uid}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; padding: 20px; border: 1px solid #eee; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 800px; margin-left: auto; margin-right: auto; }}
            .header {{ text-align: center; border-bottom: 1px solid #eee; padding-bottom: 15px; margin-bottom: 20px; }}
            .header h1 {{ margin: 0; color: #333; }}
            .content {{ font-size: 16px; color: #555; }}
            .content p {{ margin: 10px 0; line-height: 1.6; }}
            .content strong {{ color: #000; }}
            .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #aaa; border-top: 1px solid #eee; padding-top: 15px;}}
        </style>
    </head>
    <body>
        <div class="header">
            {logo_html_embed}
            <h1>Passeport d'Authenticité</h1>
        </div>
        <div class="content">
            <p><strong>Identifiant Unique (UID):</strong> {item_uid}</p>
            <p><strong>Produit:</strong> {product_name} (Référence Produit: {product_id})</p>
            <p><strong>Numéro de Lot:</strong> {batch_number if batch_number else 'N/A'}</p>
            <p><strong>Date de Production:</strong> {production_date_display}</p>
            <p><strong>Date d&rsquo;Expiration / DLUO:</strong> {expiry_date_display}</p>
            <hr>
            <p>Ce produit est un article authentique de Maison Trüvra, sélectionné et préparé avec le plus grand soin pour garantir une qualité exceptionnelle. Chaque détail de sa conception à sa réalisation reflète notre engagement envers l'excellence et la tradition artisanale.</p>
            {additional_info_html}
        </div>
        <div class="footer">
            &copy; {datetime.now().year} Maison Trüvra. Tous droits réservés.
        </div>
    </body>
    </html>
    """

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Passport HTML generated: {filepath}")
        return filepath
    except Exception as e:
        print(f"Error writing passport HTML file {filepath}: {e}")
        return None

if __name__ == "__main__":
    print("--- Item Passport HTML Generator (Standalone - DEPRECATED for app use) ---")
    parser = argparse.ArgumentParser(description="Generate an HTML passport for a specific item.")
    parser.add_argument("--item_uid", required=True, help="Unique Item Identifier")
    parser.add_argument("--product_name", required=True, help="Product Name")
    parser.add_argument("--product_id", required=True, help="Product ID")
    parser.add_argument("--batch", default=None, help="Batch Number")
    parser.add_argument("--prod_date", default=None, help="Production Date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--exp_date", default=None, help="Expiry Date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--extra_json", default=None, help="Additional info as a JSON string (e.g. '{\"Origin\":\"France\", \"Artisan\":\"John Doe\"}')")
    parser.add_argument("--out_dir", default=OUTPUT_DIR_PASSPORTS, help=f"Output directory (default: {OUTPUT_DIR_PASSPORTS})")
    parser.add_argument("--logo", default=MAISON_TRUVRA_LOGO_PATH_PASSPORT, help=f"Path to logo image for passport (default: {MAISON_TRUVRA_LOGO_PATH_PASSPORT})")

    args = parser.parse_args()

    generate_item_passport_html(
        item_uid=args.item_uid,
        product_name=args.product_name,
        product_id=args.product_id,
        batch_number=args.batch,
        production_date_str=args.prod_date,
        expiry_date_str=args.exp_date,
        additional_info_json_str=args.extra_json,
        output_dir=args.out_dir,
        logo_path=args.logo
    )