# services/airtable_service.py

import os
from pyairtable import Table
from core.utils.logger import log_info, log_warning, log_error

# 👉 On utilise UNIQUEMENT ce référentiel (IDs Airtable)
from services.airtable_tables import ATABLES


class AirtableService:
    """
    Service Airtable centralisé — lecture simple v1.
    """

    def __init__(self):
        # 🔐 Variables d’environnement (OK)
        self.api_key = os.getenv("AIRTABLE_API_KEY")
        self.base_id = os.getenv("AIRTABLE_BASE_ID")

        if not self.api_key or not self.base_id:
            log_error("Clés Airtable manquantes (API KEY ou BASE ID).",
                      module="AirtableService")
            raise ValueError("Configuration Airtable incomplète.")

        # 👟 Table par défaut : Coureurs
        self.table_name = ATABLES.COU_TABLE  # ← ID de la table Coureurs
        self.table = Table(self.api_key, self.base_id, self.table_name)

        log_info(f"AirtableService → connecté à la table '{self.table_name}'",
                 module="AirtableService")
    # -------------------------------
    # Lecture simple d’un record
    # -------------------------------
    def get(self, record_id: str):
        log_info(f"Lecture record Airtable : {record_id}", module="AirtableService")
        try:
            return self.table.get(record_id)
        except Exception as e:
            log_error(f"Erreur Airtable lors de la lecture du record : {e}",
                      module="AirtableService")
            return None

    # -------------------------------
    # Compatibilité SCN_1 : get_record()
    # -------------------------------
    def get_record(self, record_id: str):
        """
        Alias pour compatibilité avec SCN_1.
        """
        return self.get(record_id)

 
