# services/airtable_service.py

import os
from pyairtable import Table
from core.airtable_refs import ATREFS

class AirtableService:
    """Service Airtable centralisé – lecture simple v1."""

    def __init__(self):
        self.api_key = os.getenv("AIRTABLE_API_KEY")
        self.base_id = ATREFS.BASE_ID

        if not self.api_key or not self.base_id:
            raise ValueError("Clés Airtable manquantes (API KEY ou BASE ID).")

        # Table par défaut : Coureurs
        from services.airtable_tables import ATABLES
        self.table = Table(self.api_key, self.base_id, ATABLES.COUR)

    def get(self, record_id: str):
        return self.table.get(record_id)

    def find(self, formula: str):
        return self.table.first(formula=formula)
