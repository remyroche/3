# backend/services/asset_service.py
import os
import qrcode
from PIL import Image as PILImage 
from PIL import ImageDraw, ImageFont
from flask import current_app, url_for
from reportlab.lib.pagesizes import A7 
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as ReportLabImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.graphics.barcode import qr as reportlab_qr # aliased to avoid conflict
from reportlab.graphics.shapes import Drawing
from datetime import datetime
import uuid

# Import models for type hinting and accessing localized data
from ..models import Product, Category, ProductLocalization, CategoryLocalization 
from ..utils import format_datetime_for_display # Assuming this is in backend/utils.py

# --- QR Code Generation (for ReportLab PDF embedding) ---
def generate_qr_image_for_reportlab(data_string, size=20*mm): # Renamed for clarity
    """
    Generates a QR code as a ReportLab Drawing object.
    """
    qr_code_widget = reportlab_qr.QrCodeWidget(data_string)
    # Calculate bounds and transform for desired size
    bounds = qr_code_widget.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    
    # Handle cases where width or height might be zero if data_string is empty
    if width == 0 or height == 0:
        current_app.logger.warning(f"Cannot generate ReportLab QR code for empty or invalid data: {data_string}")
        # Return an empty drawing or a placeholder
        return Drawing(size, size)

    # Scale transformation
    sx = size / width
    sy = size / height
    
    drawing = Drawing(size, size, transform=[sx, 0, 0, sy, -bounds[0]*sx, -bounds[1]*sy])
    drawing.add(qr_code_widget)
    return drawing

# --- QR Code File Generation (PNG for passport link in DB/HTML) ---
def generate_qr_code_for_item(item_uid, product_id, product_name_fr, product_name_en): # product_id, names for context/logging
    """
    Generates a QR code image file (PNG) for a given item UID, linking to its public passport URL.
    Saves it and returns the relative path (from ASSET_STORAGE_PATH).
    """
    qr_folder_abs = current_app.config['QR_CODE_FOLDER'] # Absolute path from config
    os.makedirs(qr_folder_abs, exist_ok=True)

    # Use APP_BASE_URL_FRONTEND for public-facing URLs
    frontend_base_url = current_app.config.get('APP_BASE_URL_FRONTEND', current_app.config.get('APP_BASE_URL', 'http://localhost:8000'))
    passport_public_url = f"{frontend_base_url}/passport/{item_uid}" # This is the URL the QR code will contain

    qr_filename = f"qr_passport_{item_uid}.png"
    qr_filepath_full = os.path.join(qr_folder_abs, qr_filename)

    try:
        img = qrcode.make(passport_public_url)
        img.save(qr_filepath_full)
        current_app.logger.info(f"Passport QR Code PNG generated for item {item_uid} at {qr_filepath_full}, URL: {passport_public_url}")
        
        # Return path relative to ASSET_STORAGE_PATH for DB storage
        base_asset_path = current_app.config['ASSET_STORAGE_PATH']
        relative_path = os.path.relpath(qr_filepath_full, base_asset_path).replace(os.sep, '/')
        return relative_path # e.g., 'qr_codes/qr_passport_XYZ.png'
    except Exception as e:
        current_app.logger.error(f"Failed to generate QR code PNG for {item_uid}: {e}", exc_info=True)
        raise # Re-raise to be handled by the caller

# --- Digital Passport Generation (HTML - Bilingual) ---
def generate_item_passport(item_uid, product_model, category_model, item_specific_data):
    """
    Generates a bilingual HTML digital passport for a specific item.
    Args:
        product_model (Product): SQLAlchemy Product model instance.
        category_model (Category): SQLAlchemy Category model instance.
    Returns the relative path (from ASSET_STORAGE_PATH) to the saved HTML file.
    """
    passport_folder_abs = current_app.config['PASSPORT_FOLDER'] # Absolute path
    os.makedirs(passport_folder_abs, exist_ok=True)
    
    passport_filename = f"passport_{item_uid}.html"
    passport_filepath_full = os.path.join(passport_folder_abs, passport_filename)

    # Extract and localize data from models
    # Product Data
    prod_loc_fr = product_model.localizations.filter_by(lang_code='fr').first()
    prod_loc_en = product_model.localizations.filter_by(lang_code='en').first()

    product_name_fr = prod_loc_fr.name_fr if prod_loc_fr and prod_loc_fr.name_fr else product_model.name
    product_name_en = prod_loc_en.name_en if prod_loc_en and prod_loc_en.name_en else product_model.name
    # Add other localized product fields as needed, e.g., description
    # product_description_fr = prod_loc_fr.description_fr if prod_loc_fr and prod_loc_fr.description_fr else product_model.description
    # product_description_en = prod_loc_en.description_en if prod_loc_en and prod_loc_en.description_en else product_model.description


    # Category Data
    category_name_fr = "N/A"; category_name_en = "N/A"
    species_fr = "N/A"; species_en = "N/A"
    ingredients_fr = "N/A"; ingredients_en = "N/A"
    if category_model:
        cat_loc_fr = category_model.localizations.filter_by(lang_code='fr').first()
        cat_loc_en = category_model.localizations.filter_by(lang_code='en').first()
        category_name_fr = cat_loc_fr.name_fr if cat_loc_fr and cat_loc_fr.name_fr else category_model.name
        category_name_en = cat_loc_en.name_en if cat_loc_en and cat_loc_en.name_en else category_model.name
        species_fr = cat_loc_fr.species_fr if cat_loc_fr and cat_loc_fr.species_fr else (category_model.description or "N/A") # Example fallback
        species_en = cat_loc_en.species_en if cat_loc_en and cat_loc_en.species_en else (category_model.description or "N/A")
        ingredients_fr = cat_loc_fr.main_ingredients_fr if cat_loc_fr and cat_loc_fr.main_ingredients_fr else "N/A"
        ingredients_en = cat_loc_en.main_ingredients_en if cat_loc_en and cat_loc_en.main_ingredients_en else "N/A"


    batch_number = item_specific_data.get('batch_number', 'N/A')
    production_date_iso = item_specific_data.get('production_date') 
    expiry_date_iso = item_specific_data.get('expiry_date') 
    actual_weight_grams = item_specific_data.get('actual_weight_grams')

    production_date_display_fr = format_datetime_for_display(production_date_iso, fmt='%d/%m/%Y') if production_date_iso else 'N/A'
    production_date_display_en = format_datetime_for_display(production_date_iso, fmt='%Y-%m-%d') if production_date_iso else 'N/A'
    expiry_date_display_fr = format_datetime_for_display(expiry_date_iso, fmt='%d/%m/%Y') if expiry_date_iso else 'N/A'
    expiry_date_display_en = format_datetime_for_display(expiry_date_iso, fmt='%Y-%m-%d') if expiry_date_iso else 'N/A'
    
    processing_date_fr = format_datetime_for_display(datetime.now(timezone.utc), fmt='%d/%m/%Y')
    processing_date_en = format_datetime_for_display(datetime.now(timezone.utc), fmt='%Y-%m-%d')

    logo_public_url = current_app.config.get('PASSPORT_LOGO_PUBLIC_URL', 'https://placehold.co/200x80/7D6A4F/F5EEDE?text=Maison+Trüvra+Logo')
    logo_html_embed = f'<img src="{logo_public_url}" alt="Maison Trüvra Logo" style="max-height: 70px; margin-bottom: 15px;">'

    # Using f-string for HTML content (ensure all variables are properly escaped if they could contain HTML special chars from untrusted sources)
    # For data coming from your DB, it's usually fine, but be mindful.
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Passeport Produit / Product Passport - {item_uid}</title>
        <style>
            body {{ font-family: 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 20px; background-color: #f9f9f9; color: #333; }}
            .container {{ max-width: 800px; margin: 0 auto; background-color: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; border-bottom: 2px solid #eee; padding-bottom: 20px; margin-bottom: 25px; }}
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
                {logo_html_embed}
                <h1>Passeport d'Authenticité / Certificate of Authenticity</h1>
            </div>

            <div class="section">
                <h2>Identification de l'Article / Item Identification</h2>
                <div class="content">
                    <p><strong>Identifiant Unique (UID):</strong> {item_uid}</p>
                    <p><strong>Numéro de Lot / Batch Number:</strong> {batch_number}</p>
                    <p><strong>Date de Traitement / Processing Date:</strong> {processing_date_fr} / {processing_date_en}</p>
                    {f'<p><strong>Poids Net / Net Weight:</strong> {actual_weight_grams}g</p>' if actual_weight_grams is not None else ''}
                </div>
            </div>

            <div class="section">
                <h2>Détails du Produit / Product Details</h2>
                <div class="content bilingual-section">
                    <div class="lang-fr">
                        <p><strong>Produit:</strong> {product_name_fr}</p>
                        <p><strong>Catégorie:</strong> {category_name_fr}</p>
                        <p><strong>Espèce / Origine:</strong> {species_fr}</p>
                        <p><strong>Ingrédients Principaux:</strong> {ingredients_fr}</p>
                        <p><strong>Date de Production:</strong> {production_date_display_fr}</p>
                        <p><strong>Date d'Expiration:</strong> {expiry_date_display_fr}</p>
                    </div>
                    <hr style="margin: 10px 0; border-color: #eee;">
                    <div class="lang-en">
                        <p><strong>Product:</strong> {product_name_en}</p>
                        <p><strong>Category:</strong> {category_name_en}</p>
                        <p><strong>Species / Origin:</strong> {species_en}</p>
                        <p><strong>Main Ingredients:</strong> {ingredients_en}</p>
                        <p><strong>Production Date:</strong> {production_date_display_en}</p>
                        <p><strong>Expiry Date:</strong> {expiry_date_display_en}</p>
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
                <p>URL: {current_app.config.get('APP_BASE_URL_FRONTEND', 'https://maisontruvra.com')}/passport/{item_uid}</p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        with open(passport_filepath_full, 'w', encoding='utf-8') as f:
            f.write(html_content)
        current_app.logger.info(f"Bilingual Passport HTML generated for item {item_uid} at {passport_filepath_full}")
        base_asset_path = current_app.config['ASSET_STORAGE_PATH']
        return os.path.relpath(passport_filepath_full, base_asset_path).replace(os.sep, '/')
    except Exception as e:
        current_app.logger.error(f"Failed to generate bilingual passport HTML for {item_uid}: {e}", exc_info=True)
        raise

# --- Product Label Generation (PDF) ---
def generate_product_label_pdf(item_uid, product_name_fr, product_name_en, weight_grams, processing_date_str, passport_url_for_qr):
    """
    Generates a product label as a PDF file using ReportLab.
    Args:
        passport_url_for_qr (str): The public URL to the item's passport, for the QR code.
    Returns the relative path (from ASSET_STORAGE_PATH) to the saved PDF label.
    """
    label_folder_abs = current_app.config['LABEL_FOLDER'] # Absolute path
    os.makedirs(label_folder_abs, exist_ok=True)
    pdf_filename = f"label_pdf_{item_uid}.pdf"
    pdf_filepath_full = os.path.join(label_folder_abs, pdf_filename)
    
    default_font_path = current_app.config.get('DEFAULT_FONT_PATH')
    logo_path_config = current_app.config.get('MAISON_TRUVRA_LOGO_PATH_LABEL')

    styles = getSampleStyleSheet()
    # Attempt to register custom font if path is provided
    # Note: Font registration with ReportLab can be tricky and might need specific setup.
    # This is a basic attempt. For production, ensure fonts are correctly installed or embedded.
    base_font_name = 'Helvetica'
    if default_font_path and os.path.exists(default_font_path):
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            font_name_registered = os.path.splitext(os.path.basename(default_font_path))[0]
            pdfmetrics.registerFont(TTFont(font_name_registered, default_font_path))
            base_font_name = font_name_registered
            current_app.logger.info(f"Registered font '{base_font_name}' for PDF labels from {default_font_path}")
        except Exception as e_font:
            current_app.logger.warning(f"Could not register custom font {default_font_path} for PDF: {e_font}. Falling back to Helvetica.")
            base_font_name = 'Helvetica'


    style_normal = ParagraphStyle('Normal_Label', parent=styles['Normal'], fontName=base_font_name, fontSize=7, leading=9)
    style_title = ParagraphStyle('Title_Label', parent=style_normal, fontSize=9, fontName=base_font_name + ('-Bold' if base_font_name == 'Helvetica' else ''), leading=11) # Bold for Helvetica
    style_small = ParagraphStyle('Small_Label', parent=style_normal, fontSize=5, leading=6)
    style_qr_text = ParagraphStyle('QR_Text_Label', parent=style_small, alignment=1) # Centered

    doc = SimpleDocTemplate(pdf_filepath_full, pagesize=A7, leftMargin=4*mm, rightMargin=4*mm, topMargin=4*mm, bottomMargin=4*mm)
    story = []

    if logo_path_config and os.path.exists(logo_path_config):
        try:
            logo = ReportLabImage(logo_path_config, width=25*mm, height=8*mm) 
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 1.5*mm))
        except Exception as e_logo:
            current_app.logger.warning(f"Could not load logo for PDF label {logo_path_config}: {e_logo}")
            story.append(Paragraph("Maison Trüvra", style_title))
            story.append(Spacer(1, 1.5*mm))
    else:
        story.append(Paragraph("Maison Trüvra", style_title))
        story.append(Spacer(1, 1.5*mm))

    story.append(Paragraph(product_name_fr, style_title)) # Primary name in French
    if product_name_en and product_name_en.lower() != product_name_fr.lower():
        story.append(Paragraph(f"<i>({product_name_en})</i>", style_normal)) # English name smaller/italic
    story.append(Spacer(1, 1*mm))

    if weight_grams is not None:
        story.append(Paragraph(f"Poids Net / Net Wt: {weight_grams:.1f}g", style_normal)) # Format weight
        story.append(Spacer(1, 1*mm))

    story.append(Paragraph(f"Traité le / Processed: {processing_date_str}", style_normal))
    story.append(Spacer(1, 1*mm))
    
    story.append(Paragraph(f"UID: {item_uid}", style_small))
    story.append(Spacer(1, 2*mm))

    qr_code_drawing = generate_qr_image_for_reportlab(passport_url_for_qr, size=18*mm) # Smaller QR for label
    qr_code_drawing.hAlign = 'CENTER'
    story.append(qr_code_drawing)
    story.append(Spacer(1, 0.5*mm))
    story.append(Paragraph("Scannez pour authenticité / Scan for authenticity", style_qr_text))

    try:
        doc.build(story)
        current_app.logger.info(f"PDF Label generated for item {item_uid} at {pdf_filepath_full}")
        base_asset_path = current_app.config['ASSET_STORAGE_PATH']
        return os.path.relpath(pdf_filepath_full, base_asset_path).replace(os.sep, '/')
    except Exception as e:
        current_app.logger.error(f"Failed to generate PDF label for {item_uid}: {e}", exc_info=True)
        raise
