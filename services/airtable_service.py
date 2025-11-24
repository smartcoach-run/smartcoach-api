# services/airtable_service.py
# AirtableService v1 — accès lecture Airtable (table Coureurs)

import os
from typing import Optional

from pyairtable import Table
from core.utils.logger import log_info, log_warning, log_error

from core.airtable_refs import ATREFS


class AirtableService:
    """
    Service Airtable centralisé.
    v1 : accès simple en lecture d’un enregistrement.
    """

    def __init__(self):
        self.api_key = os.getenv("AIRTABLE_API_KEY")
        self.base_id = os.getenv("AIRTABLE_BASE_ID")

        if not self.api_key or not self.base_id:
            log_error("Clés Airtable manquantes (API KEY ou BASE ID).", module="AirtableService")
            raise ValueError("Configuration Airtable incomplète.")

        self.table_name = ATABLES.COU_TABLE
        self.table = Table(self.api_key, self.base_id, self.table_name)

        log_info(f"AirtableService → connecté à la table '{self.table_name}'", module="AirtableService")

    # ------------------------------------------------------------------
    # Lecture simple d’un record
    # ------------------------------------------------------------------
    def get_record(self, record_id: str) -> Optional[dict]:
        """
        Récupère un record Airtable en toute sécurité.
        Retourne None si le record n’existe pas ou en cas d’erreur.
        """

        log_info(f"Lecture record Airtable : {record_id}", module="AirtableService")

        try:
            rec = self.table.get(record_id)
            if not rec:
                log_warning(f"Record introuvable : {record_id}", module="AirtableService")
                return None

            log_info(f"Record récupéré", module="AirtableService")
            return rec

        except Exception as e:
            log_error(f"Erreur Airtable lors de la lecture du record : {e}", module="AirtableService")
            return None
