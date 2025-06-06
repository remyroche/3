# backend/models/base.py
# Contains the shared SQLAlchemy instance to avoid circular imports.

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
