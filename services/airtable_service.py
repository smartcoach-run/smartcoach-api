# services/airtable_service.py

import os
import logging
import requests
from pyairtable import Table
from core.utils.logger import log_info, log_warning, log_error
from services.airtable_tables import ATABLES

# 👉 On utilise UNIQUEMENT ce référentiel (IDs Airtable)
from services.airtable_tables import ATABLES
from core.config import config  # AJOUT

class AirtableService:
    def __init__(self):
        from core.config import config
        
        self.api_key = config.api_key      # ✔ bon nom
        self.base_id = config.base_id      # ✔ bon nom
        self.env = config.env              # facultatif mais utile

        if not self.api_key:
            raise RuntimeError("API KEY is missing")

        if not self.base_id:
            raise RuntimeError(f"BASE_ID is missing for ENV={config.env}")

        self.table = None
        self.table_name = None

    """
    Service Airtable centralisé — lecture simple v1.
    """
    # ----------------------------------------------------
    # Compatibilité SCN_1 + Cache local (FAST)
    # ----------------------------------------------------

    # Cache simple en mémoire (clé = "record:<id>")
    _RECORD_CACHE = {}

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

    # ---------------------------------------------------------
    # Alias standard : list_records()
    # Attendu par SCN_SLOT_RESOLVER / futurs scénarios
    # ---------------------------------------------------------
    def list_records(
        self,
        table_id: str,
        filter_by_formula: str | None = None,
    ) -> list:
        """
        Façade standard pour lister des records Airtable.
        Compatible avec SCN_SLOT_RESOLVER et futurs scénarios.
        """
        if filter_by_formula:
            return self.find_all(table_id, filter_by_formula)
        return self.list_all(table_id)

    def get_session_types(self):
        """
        Retourne tous les records de la table 📘 Séances Types
        """
        self.set_table(ATABLES.SEANCES_TYPES)
        return self.get_all_records()
    
    # ---------------------------------------------------------
    # UPSERT générique (create si non trouvé, update sinon)
    # ---------------------------------------------------------
    def upsert_record(self, table_id: str, key_field: str, key_value: str, fields: dict):
        """
        Upsert générique SmartCoach :
        - Cherche un record où key_field == key_value
        - Update si trouvé
        - Sinon Create
        Retourne le record Airtable final.
        """

        from core.utils.logger import log_info, log_error

        try:
            # 1) Lire table
            temp_table = Table(self.api_key, self.base_id, table_id)

            # 2) Chercher record existant
            formula = f"{{{key_field}}} = '{key_value}'"
            matches = temp_table.all(formula=formula)

            if matches:
                record_id = matches[0]["id"]
                log_info(f"[Airtable UPSERT] Update → {table_id}/{record_id} ({key_field}={key_value})")
                return temp_table.update(record_id, fields)

            # 3) Sinon créer
            fields[key_field] = key_value
            log_info(f"[Airtable UPSERT] Create → {table_id} ({key_field}={key_value})")
            return temp_table.create(fields)

        except Exception as e:
            log_error(f"[Airtable UPSERT] Erreur sur {table_id} : {e}")
            raise
    
    # ---------------------------------------------------------
    #   Lecture d’un record dans une table donnée.
    #    Compatible SCN_1 / RCTC v2025-12.
    #    Utilise un cache mémoire interne pour les accès répétés.
    # ---------------------------------------------------------
    def get_record(self, table_id: str, record_id: str):

        cache_key = f"{table_id}:{record_id}"

        # 1) Retour immédiat si déjà en cache
        if cache_key in self._RECORD_CACHE:
            return self._RECORD_CACHE[cache_key]

        # 2) Sélection dynamique de la table
        self.set_table(table_id)

        try:
            record = self.table.get(record_id)

            # 3) Mise en cache
            self._RECORD_CACHE[cache_key] = record

            return record

        except Exception as e:
            log_error(
                f"[AirtableService] Erreur get_record sur {table_id}/{record_id} : {e}",
                module="AirtableService"
            )
            return None
