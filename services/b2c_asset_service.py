# services/b2c_asset_service.py
import os
import qrcode
from flask import current_app, url_for
from reportlab.lib.pagesizes import A7
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as ReportLabImage
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.barcode import qr as reportlab_qr
from reportlab.graphics.shapes import Drawing
from datetime import datetime

class B2CAssetService:
    @staticmethod
    def generate_qr_code_for_item(item_uid, product_name):
        """
        Generates a QR code PNG file that links to the item's public passport URL.

        Returns:
            str: The relative path to the saved QR code image.
        """
        qr_folder_abs = current_app.config['QR_CODE_FOLDER']
        os.makedirs(qr_folder_abs, exist_ok=True)

        frontend_base_url = current_app.config.get('APP_BASE_URL_FRONTEND', 'http://localhost:8000')
        passport_public_url = f"{frontend_base_url}/passport/{item_uid}"

        qr_filename = f"qr_passport_{item_uid}.png"
        qr_filepath_full = os.path.join(qr_folder_abs, qr_filename)

        img = qrcode.make(passport_public_url)
        img.save(qr_filepath_full)
        current_app.logger.info(f"Passport QR Code generated for item {item_uid}")

        base_asset_path = current_app.config['ASSET_STORAGE_PATH']
        return os.path.relpath(qr_filepath_full, base_asset_path).replace(os.sep, '/')

    @staticmethod
    def generate_item_passport_html(item_uid, product_info, item_specifics):
        """
        Generates a bilingual HTML digital passport for a specific item.

        Returns:
            str: The relative path to the saved HTML file.
        """
        passport_folder_abs = current_app.config['PASSPORT_FOLDER']
        os.makedirs(passport_folder_abs, exist_ok=True)
        passport_filename = f"passport_{item_uid}.html"
        passport_filepath_full = os.path.join(passport_folder_abs, passport_filename)

        # Simplified HTML generation logic for brevity
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Product Passport {item_uid}</title></head>
        <body>
            <h1>Passport for {product_info.get('name')}</h1>
            <p><strong>UID:</strong> {item_uid}</p>
            <p><strong>Batch:</strong> {item_specifics.get('batch_number', 'N/A')}</p>
            <p><strong>Production Date:</strong> {item_specifics.get('production_date', 'N/A')}</p>
        </body>
        </html>
        """
        with open(passport_filepath_full, 'w', encoding='utf-8') as f:
            f.write(html_content)

        base_asset_path = current_app.config['ASSET_STORAGE_PATH']
        return os.path.relpath(passport_filepath_full, base_asset_path).replace(os.sep, '/')


    @staticmethod
    def generate_product_label_pdf(item_uid, product_name, weight_grams, processing_date_str, passport_url):
        """
        Generates a product label as a PDF file using ReportLab.

        Returns:
            str: The relative path to the saved PDF label.
        """
        label_folder_abs = current_app.config['LABEL_FOLDER']
        os.makedirs(label_folder_abs, exist_ok=True)
        pdf_filename = f"label_pdf_{item_uid}.pdf"
        pdf_filepath_full = os.path.join(label_folder_abs, pdf_filename)

        doc = SimpleDocTemplate(pdf_filepath_full, pagesize=A7, leftMargin=4*mm, rightMargin=4*mm, topMargin=4*mm, bottomMargin=4*mm)
        styles = getSampleStyleSheet()
        story = []

        # Simplified PDF generation logic for brevity
        story.append(Paragraph(product_name, styles['Title']))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(f"Net Weight: {weight_grams}g", styles['Normal']))
        story.append(Paragraph(f"Processed: {processing_date_str}", styles['Normal']))
        story.append(Paragraph(f"UID: {item_uid}", styles['Code']))
        story.append(Spacer(1, 4*mm))
        
        qr_code = reportlab_qr.QrCodeWidget(passport_url)
        bounds = qr_code.getBounds()
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        drawing = Drawing(20*mm, 20*mm, transform=[20*mm/width, 0, 0, 20*mm/height, 0, 0])
        drawing.add(qr_code)
        story.append(drawing)
        
        doc.build(story)
        
        base_asset_path = current_app.config['ASSET_STORAGE_PATH']
        return os.path.relpath(pdf_filepath_full, base_asset_path).replace(os.sep, '/')
