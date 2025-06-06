# services/b2b/b2b_asset_service.py
import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

from ..models import ProfessionalDocument
from ..utils import allowed_file, get_file_extension

class B2BAssetService:
    @staticmethod
    def store_professional_document(user_id, file_storage, document_type):
        """
        Saves a professional document upload and creates a corresponding database record.
        
        Args:
            user_id (int): The ID of the B2B user uploading the document.
            file_storage (FileStorage): The file object from the request.
            document_type (str): The type of document (e.g., 'kbis', 'vat_certificate').

        Returns:
            ProfessionalDocument: The newly created ProfessionalDocument object.
        
        Raises:
            ValueError: If the file type is not allowed.
        """
        if not (file_storage and file_storage.filename and allowed_file(file_storage.filename, 'ALLOWED_DOCUMENT_EXTENSIONS')):
            raise ValueError("Invalid file type. Allowed types are specified in the configuration.")

        upload_folder = current_app.config['PROFESSIONAL_DOCS_UPLOAD_PATH']
        os.makedirs(upload_folder, exist_ok=True)

        safe_doc_type = "".join(c for c in document_type if c.isalnum() or c in ('-', '_')).rstrip()
        filename_base = secure_filename(f"user_{user_id}_{safe_doc_type}_{uuid.uuid4().hex[:8]}")
        extension = get_file_extension(file_storage.filename)
        filename = f"{filename_base}.{extension}"
        
        file_path_full = os.path.join(upload_folder, filename)
        file_storage.save(file_path_full)
        
        # Path to store in DB is relative to the designated assets root
        # This makes it easier to serve later without exposing full system paths.
        db_file_path = os.path.join('professional_documents', filename).replace(os.sep, '/')

        new_doc = ProfessionalDocument(
            user_id=user_id,
            document_type=document_type,
            file_path=db_file_path
        )
        return new_doc
