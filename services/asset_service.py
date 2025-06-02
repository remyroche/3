# backend/services/asset_service.py
import os
import qrcode
from PIL import Image as PILImage # Renamed to avoid conflict with ReportLab's Image
from PIL import ImageDraw, ImageFont
from flask import current_app, url_for # url_for might be problematic if used without app context for external URLs
from reportlab.lib.pagesizes import letter, A7 # A7 is small, good for labels
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as ReportLabImage, KeepInFrame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.colors import HexColor
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from datetime import datetime
import uuid

# --- QR Code Generation (shared utility) ---
def generate_qr_image(data, size=50*mm):
    """
    Generates a QR code image object using reportlab.graphics.barcode.qr.
    Returns a Drawing object containing the QR code.
    """
    qr_code = qr.QrCodeWidget(data)
    qr_code.barWidth = size
    qr_code.barHeight = size
    qr_code.qrVersion = None # Auto-detect version
    
    d = Drawing(size, size, transform=[size/qr_code.barWidth, 0, 0, size/qr_code.barHeight, 0, 0])
    d.add(qr_code)
    return d

# --- QR Code File Generation (for passport link in DB) ---
def generate_qr_code_for_item(item_uid, product_id, product_name_fr, product_name_en):
    """
    Generates a QR code image file for a given item UID, linking to its passport.
    Saves it as a PNG file.
    Returns the relative path to the saved QR code image.
    """
    qr_folder = current_app.config['QR_CODE_FOLDER']
    os.makedirs(qr_folder, exist_ok=True)

    app_base_url = current_app.config.get('APP_BASE_URL', 'https://maisontruvra.com')
    passport_url = f"{app_base_url}/passport/{item_uid}"

    qr_filename = f"qr_passport_{item_uid}.png"
    qr_filepath = os.path.join(qr_folder, qr_filename)

    try:
        # Using the qrcode library for simple PNG generation for this specific use case
        img = qrcode.make(passport_url)
        img.save(qr_filepath)
        current_app.logger.info(f"Passport QR Code PNG generated for item {item_uid} at {qr_filepath}, URL: {passport_url}")
        return os.path.join('qr_codes', qr_filename)
    except Exception as e:
        current_app.logger.error(f"Failed to generate QR code PNG for {item_uid}: {e}")
        raise

# --- Digital Passport Generation (HTML - Bilingual) ---
def generate_item_passport(item_uid, product_info, category_info, item_specific_data):
    """
    Generates a bilingual HTML digital passport for a specific item.
    Returns the relative path to the saved HTML file.

    Args:
        item_uid (str): Unique identifier for the item.
        product_info (dict): Dictionary containing product details (e.g., name_fr, name_en, category_id).
        category_info (dict): Dictionary containing category details (e.g., name_fr, name_en, species_fr/en, ingredients_fr/en).
                               This data should be fetched by the calling route.
        item_specific_data (dict): Dictionary with item-specifics (e.g., batch_number, production_date, expiry_date, actual_weight_grams).
    """
    passport_folder = current_app.config['PASSPORT_FOLDER']
    os.makedirs(passport_folder, exist_ok=True)
    
    passport_filename = f"passport_{item_uid}.html"
    passport_filepath = os.path.join(passport_folder, passport_filename)

    # Extract data, providing fallbacks
    product_name_fr = product_info.get('name_fr', product_info.get('name', 'Produit Inconnu'))
    product_name_en = product_info.get('name_en', product_info.get('name', 'Unknown Product'))
    
    category_name_fr = category_info.get('name_fr', category_info.get('name', 'Catégorie Inconnue'))
    category_name_en = category_info.get('name_en', category_info.get('name', 'Unknown Category'))
    species_fr = category_info.get('species_fr', category_info.get('species', 'N/A'))
    species_en = category_info.get('species_en', category_info.get('species', 'N/A'))
    ingredients_fr = category_info.get('ingredients_fr', category_info.get('ingredients_notes_fr', category_info.get('ingredients', 'N/A')))
    ingredients_en = category_info.get('ingredients_en', category_info.get('ingredients_notes_en', category_info.get('ingredients', 'N/A')))
    # Add more fields from category_info as needed, e.g., main_ingredients, fresh_vs_preserved etc.

    batch_number = item_specific_data.get('batch_number', 'N/A')
    production_date_str = item_specific_data.get('production_date') # Expects ISO string
    expiry_date_str = item_specific_data.get('expiry_date') # Expects ISO string
    actual_weight_grams = item_specific_data.get('actual_weight_grams')

    # Format dates for display
    from ..utils import format_datetime_for_display # Assuming utils.py is in parent directory
    production_date_display_fr = format_datetime_for_display(production_date_str, fmt='%d/%m/%Y') if production_date_str else 'N/A'
    production_date_display_en = format_datetime_for_display(production_date_str, fmt='%Y-%m-%d') if production_date_str else 'N/A'
    expiry_date_display_fr = format_datetime_for_display(expiry_date_str, fmt='%d/%m/%Y') if expiry_date_str else 'N/A'
    expiry_date_display_en = format_datetime_for_display(expiry_date_str, fmt='%Y-%m-%d') if expiry_date_str else 'N/A'
    
    processing_date_fr = format_datetime_for_display(datetime.now(), fmt='%d/%m/%Y')
    processing_date_en = format_datetime_for_display(datetime.now(), fmt='%Y-%m-%d')


    logo_path_config = current_app.config.get('MAISON_TRUVRA_LOGO_PATH_PASSPORT')
    logo_html_embed = ""
    if logo_path_config:
        # Try to create a relative path if the logo is within the static assets served by Flask
        # This is a common pattern but might need adjustment based on actual static file setup
        try:
            static_folder_name = current_app.static_url_path.strip('/') if current_app.static_url_path else 'static'
            # Construct a path relative to where the HTML file will be, assuming it's served from a path that can access static assets
            # This is tricky without knowing the exact serving setup. A full URL is safer if the logo is hosted.
            # For now, let's assume a simplified relative path or placeholder
            logo_filename = os.path.basename(logo_path_config)
            # This relative path assumes the passport HTML and logo are served in a way that this path resolves.
            # Example: if passports are in /assets/generated_assets/passports/ and logo in /static/assets/logos/
            # The relative path would be something like ../../../static/assets/logos/logo.png
            # For robustness, a full URL to the logo might be better if it's hosted.
            # For demonstration, we'll use a placeholder if direct relative path is complex.
            # logo_html_embed = f'<img src="../../static_assets/logos/{logo_filename}" alt="Maison Trüvra Logo" style="max-height: 80px; margin-bottom: 20px;">'
            # Using a placeholder image for simplicity in this example as relative paths can be tricky
            logo_html_embed = f'<img src="https://placehold.co/200x80/7D6A4F/F5EEDE?text=Maison+Trüvra" alt="Maison Trüvra Logo" style="max-height: 80px; margin-bottom: 20px;">'

        except Exception as e:
            current_app.logger.warning(f"Could not form logo path for passport: {e}")


    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Passeport Produit / Product Passport - {item_uid}</title>
        <style>
            body {{ font-family: 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0; background-color: #f9f9f9; color: #333; }}
            .container {{ max-width: 800px; margin: 20px auto; background-color: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; border-bottom: 2px solid #eee; padding-bottom: 20px; margin-bottom: 25px; }}
            .header img {{ max-height: 70px; margin-bottom: 15px; }}
            .header h1 {{ margin: 0; color: #2c3e50; font-size: 24px; font-weight: 600; }}
            .section {{ margin-bottom: 25px; padding-bottom: 20px; border-bottom: 1px dashed #ddd; }}
            .section:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
            .section h2 {{ font-size: 20px; color: #34495e; margin-top: 0; margin-bottom: 15px; border-left: 4px solid #D4AF37; padding-left: 10px; }}
            .content p {{ margin: 8px 0; line-height: 1.6; }}
            .content strong {{ color: #2c3e50; font-weight: 600; min-width: 180px; display: inline-block; }}
            .bilingual-section {{ margin-top: 15px; }}
            .lang-fr {{ }}
            .lang-en {{ margin-top: 10px; color: #555; }}
            .lang-en strong {{ min-width: 160px; }}
            .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #95a5a6; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                {logo_html_embed if logo_html_embed else '<h2>Maison Trüvra</h2>'}
                <h1>Passeport d'Authenticité / Certificate of Authenticity</h1>
            </div>

            <div class="section">
                <h2>Identification de l'Article / Item Identification</h2>
                <div class="content">
                    <p><strong>Identifiant Unique (UID) :</strong> {item_uid}</p>
                    <p><strong>Numéro de Lot / Batch Number :</strong> {batch_number}</p>
                    <p><strong>Date de Traitement / Processing Date :</strong> {processing_date_fr} / {processing_date_en}</p>
                    {f'<p><strong>Poids Net / Net Weight :</strong> {actual_weight_grams}g</p>' if actual_weight_grams else ''}
                </div>
            </div>

            <div class="section">
                <h2>Détails du Produit / Product Details</h2>
                <div class="content bilingual-section">
                    <div class="lang-fr">
                        <p><strong>Produit :</strong> {product_name_fr}</p>
                        <p><strong>Catégorie :</strong> {category_name_fr}</p>
                        <p><strong>Espèce / Origine :</strong> {species_fr}</p>
                        <p><strong>Ingrédients Principaux :</strong> {ingredients_fr}</p>
                        <p><strong>Date de Production :</strong> {production_date_display_fr}</p>
                        <p><strong>Date d'Expiration :</strong> {expiry_date_display_fr}</p>
                    </div>
                    <hr style="margin: 10px 0; border-color: #eee;">
                    <div class="lang-en">
                        <p><strong>Product :</strong> {product_name_en}</p>
                        <p><strong>Category :</strong> {category_name_en}</p>
                        <p><strong>Species / Origin :</strong> {species_en}</p>
                        <p><strong>Main Ingredients :</strong> {ingredients_en}</p>
                        <p><strong>Production Date :</strong> {production_date_display_en}</p>
                        <p><strong>Expiry Date :</strong> {expiry_date_display_en}</p>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2>Traçabilité et Qualité / Traceability and Quality</h2>
                <div class="content bilingual-section">
                    <div class="lang-fr">
                        <p>Ce produit est un article authentique de Maison Trüvra, cultivé et récolté avec le plus grand soin pour garantir une qualité et une fraîcheur exceptionnelles. Notre engagement envers des pratiques durables et une traçabilité complète assure une expérience gustative inégalée.</p>
                    </div>
                    <hr style="margin: 10px 0; border-color: #eee;">
                    <div class="lang-en">
                        <p>This product is an authentic Maison Trüvra item, cultivated and harvested with the utmost care to ensure exceptional quality and freshness. Our commitment to sustainable practices and complete traceability guarantees an unparalleled taste experience.</p>
                    </div>
                </div>
            </div>

            <div class="footer">
                &copy; {datetime.now().year} Maison Trüvra. Tous droits réservés / All rights reserved.
                <p>URL: maisontruvra.com/passport/{item_uid}</p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        with open(passport_filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        current_app.logger.info(f"Bilingual Passport HTML generated for item {item_uid} at {passport_filepath}")
        return os.path.join('passports', passport_filename)
    except Exception as e:
        current_app.logger.error(f"Failed to generate bilingual passport HTML for {item_uid}: {e}")
        raise

# --- Product Label Generation (PDF) ---
def generate_product_label_pdf(item_uid, product_name_fr, product_name_en, weight_grams, processing_date_str, passport_url):
    """
    Generates a product label as a PDF file using ReportLab.
    Includes product name, weight, processing date, logo, and a QR code for the passport.
    Returns the relative path to the saved PDF label.
    """
    label_folder = current_app.config['LABEL_FOLDER']
    os.makedirs(label_folder, exist_ok=True)

    # Filename: productname_today'sdate_productUID.pdf (name part might be tricky with special chars)
    # For simplicity, backend will generate a UID-based name, frontend can rename on download.
    pdf_filename = f"label_pdf_{item_uid}.pdf"
    pdf_filepath = os.path.join(label_folder, pdf_filename)
    
    # Paths from config
    default_font_path = current_app.config.get('DEFAULT_FONT_PATH') # Ensure this font supports French characters
    logo_path_config = current_app.config.get('MAISON_TRUVRA_LOGO_PATH_LABEL') # For PDF label

    # Styles
    styles = getSampleStyleSheet()
    style_normal = styles['Normal']
    style_normal.fontName = 'Helvetica' if not default_font_path else os.path.splitext(os.path.basename(default_font_path))[0]
    style_normal.fontSize = 8 # Small font for labels
    style_normal.leading = 10

    style_title = ParagraphStyle('TitleStyle', parent=style_normal, fontSize=10, leading=12, fontName=style_normal.fontName + '-Bold')

    # Document setup (A7 is small: 74 x 105 mm)
    doc = SimpleDocTemplate(pdf_filepath, pagesize=A7,
                            leftMargin=5*mm, rightMargin=5*mm,
                            topMargin=5*mm, bottomMargin=5*mm)
    story = []

    # 1. Logo
    if logo_path_config and os.path.exists(logo_path_config):
        try:
            logo = ReportLabImage(logo_path_config, width=30*mm, height=10*mm) # Adjust size as needed
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 2*mm))
        except Exception as e:
            current_app.logger.warning(f"Could not load logo for PDF label: {e}")
            story.append(Paragraph("Maison Trüvra", style_title)) # Fallback text
            story.append(Spacer(1, 2*mm))
    else:
        story.append(Paragraph("Maison Trüvra", style_title))
        story.append(Spacer(1, 2*mm))

    # 2. Product Name (French, as primary for label)
    story.append(Paragraph(product_name_fr, style_title))
    story.append(Spacer(1, 1*mm))

    # 3. Weight
    if weight_grams:
        story.append(Paragraph(f"Poids Net / Net Weight: {weight_grams}g", style_normal))
        story.append(Spacer(1, 1*mm))

    # 4. Date of Processing
    story.append(Paragraph(f"Date de Traitement: {processing_date_str}", style_normal)) # Expects formatted date string
    story.append(Spacer(1, 1*mm))
    
    # 5. Item UID (small)
    story.append(Paragraph(f"UID: {item_uid}", ParagraphStyle('UIDStyle', parent=style_normal, fontSize=6)))
    story.append(Spacer(1, 3*mm))

    # 6. QR Code to Passport URL
    qr_code_drawing = generate_qr_image(passport_url, size=20*mm) # QR code size on label
    qr_code_drawing.hAlign = 'CENTER'
    story.append(qr_code_drawing)
    story.append(Spacer(1,1*mm))
    story.append(Paragraph("Scannez pour le passeport du produit", ParagraphStyle('QRTextStyle', parent=style_normal, fontSize=6, alignment=1))) # Alignment 1 = TA_CENTER

    try:
        doc.build(story)
        current_app.logger.info(f"PDF Label generated for item {item_uid} at {pdf_filepath}")
        return os.path.join('labels', pdf_filename) # Relative path for storage/linking
    except Exception as e:
        current_app.logger.error(f"Failed to generate PDF label for {item_uid}: {e}")
        raise
