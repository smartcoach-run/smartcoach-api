# services/airtable_service.py

import os
import logging
import requests
from pyairtable import Table
from core.utils.logger import log_info, log_warning, log_error
from services.airtable_tables import ATABLES

# 👉 On utilise UNIQUEMENT ce référentiel (IDs Airtable)
from services.airtable_tables import ATABLES


class AirtableService:
    """
    Service Airtable centralisé — lecture simple v1.
    """
    # ----------------------------------------------------
    # Compatibilité SCN_1 + Cache local (FAST)
    # ----------------------------------------------------

    # Cache simple en mémoire (clé = "record:<id>")
    _RECORD_CACHE = {}

    def get_record(self, record_id: str):
        """
        Lecture rapide d'un record Airtable :
        - 1ère lecture → API Airtable
        - lectures suivantes → cache mémoire (0 ms)

        100% compatible SCN_1.
        """
        cache_key = f"record:{record_id}"

        # Accès correct à l’attribut de classe
        if cache_key in self._RECORD_CACHE:
            return self._RECORD_CACHE[cache_key]

        # Lecture réelle Airtable
        record = self.get(record_id)

        # Mise en cache
        self._RECORD_CACHE[cache_key] = record

        return record
 
    def iterate_records(self):
        """Retourne tous les enregistrements de la table avec pagination."""
        if not self.table_id:
            raise ValueError("La table Airtable n'est pas définie. Appelle set_table() d'abord.")

        all_records = []
        params = {}

        while True:
            url = f"{self.API_URL}/{self.base_id}/{self.table_id}"
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()

            all_records.extend(data.get("records", []))

            offset = data.get("offset")
            if not offset:
                break

            params["offset"] = offset

        return all_records


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
        self.table = Table(self.api_key, self.base_id, ATABLES.COU_TABLE)

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

    # ---------------------------------------------------------
    # Changer de table dynamiquement
    # ---------------------------------------------------------
    def set_table(self, table_id: str):
        """
        Change dynamiquement la table active.
        """
        self.table_name = table_id
        self.table = Table(self.api_key, self.base_id, self.table_name)
        log_info(
            f"AirtableService → connecté à la table '{self.table_name}'",
            module="AirtableService"
        )

    # ---------------------------------------------------------
    # Lecture de TOUS les records d’une table (pyairtable)
    # ---------------------------------------------------------
    def list_all(self, table_id: str) -> list:
        """
        Retourne tous les enregistrements d'une table Airtable.
        Compatible pyairtable, pagination interne automatique.
        """
        temp_table = Table(self.api_key, self.base_id, table_id)

        try:
            records = temp_table.all()
            log_info(
                f"AirtableService → {len(records)} records lus depuis '{table_id}'",
                module="AirtableService"
            )
            return records
        except Exception as e:
            log_error(
                f"Erreur Airtable list_all() sur '{table_id}' : {e}",
                module="AirtableService"
            )
            return []

    # ---------------------------------------------------------
    # Lecture avec filtre Formula
    # ---------------------------------------------------------
    def find_all(self, table_id: str, formula: str) -> list:
        """
        Retourne tous les enregistrements correspondant à une formule Airtable.
        """
        temp_table = Table(self.api_key, self.base_id, table_id)

        try:
            records = temp_table.all(formula=formula)
            log_info(
                f"AirtableService → {len(records)} records filtrés depuis '{table_id}'",
                module="AirtableService"
            )
            return records
        except Exception as e:
            log_error(
                f"Erreur Airtable find_all() sur '{table_id}' : {e}",
                module="AirtableService"
            )
            return []

    # ---------------------------------------------------------
    # Alias simple pour compat SCN_6 : fetch_all(table_id)
    # ---------------------------------------------------------
    def fetch_all(self, table_id: str) -> list:
        """
        Alias de list_all() pour compatibilité avec SCN_6.
        """
        return self.list_all(table_id)

    def get_session_types(self):
        """
        Retourne tous les records de la table 📘 Séances Types
        """
        self.set_table(ATABLES.SEANCES_TYPES)
        return self.get_all_records()
