# utils.py
import datetime
import os

def format_date_french(date_iso_str, fmt="%d/%m/%Y"):
    """
    Formate une date ISO (AAAA-MM-JJ) en format français (JJ/MM/AAAA).
    Retourne 'N/A' si la date est invalide, vide ou None.
    """
    if not date_iso_str:
        return "N/A"
    try:
        # Tente de parser avec ou sans informations d'heure/timezone
        if 'T' in date_iso_str:
            # Prend uniquement la partie date si l'heure est présente
            date_part = date_iso_str.split('T')[0]
            dt_obj = datetime.date.fromisoformat(date_part)
        else:
            dt_obj = datetime.date.fromisoformat(date_iso_str)
        return dt_obj.strftime(fmt)
    except (ValueError, TypeError):
        # Si le parsing échoue, retourne la chaîne originale ou 'N/A' si elle est vide après split
        return date_iso_str if date_iso_str else "N/A"


