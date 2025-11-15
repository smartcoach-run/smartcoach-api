"""
airtable_service.py
---------------------------------------------------------------------
Service d’accès à Airtable utilisé par SmartCoach.

CONFORME :
- RCTC
- Manuel SmartCoach
- Story SCN_1
- Tables Airtable : Coureurs, Scénarios_validation, Logs

Ce module fournit :
- get_record(table, record_id)
- update_record(table, record_id, fields)
- find_records(table, formula)
- create_record(table, fields)

Il ne crée aucun champ, n’en invente aucun,
et se limite strictement aux opérations nécessaires pour SCN_1.
---------------------------------------------------------------------
"""

import requests


class AirtableService:

    def __init__(self, api_key: str, base_id: str):
        """
        Initialise la connexion Airtable.

        PARAMÈTRES
        ----------
        api_key : str
            Clé API Airtable (ex : 'skxxxxxxxx')
        base_id : str
            ID de la base Airtable (ex : 'appXXXXXXXX')
        """
        self.api_key = api_key
        self.base_id = base_id

        if not self.api_key:
            raise ValueError("Clé API Airtable manquante")
        if not self.base_id:
            raise ValueError("ID de base Airtable manquant")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_record(self, table: str, record_id: str):
        url = f"https://api.airtable.com/v0/{self.base_id}/{table}/{record_id}"
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Erreur GET {table}/{record_id} : {response.text}")
        return response.json()

    def update_record(self, table: str, record_id: str, fields: dict):
        url = f"https://api.airtable.com/v0/{self.base_id}/{table}/{record_id}"
        payload = {"fields": fields}
        response = requests.patch(url, json=payload, headers=self.headers)
        if response.status_code not in (200, 201):
            raise Exception(f"Erreur UPDATE {table}/{record_id} : {response.text}")
        return response.json()

    def create_record(self, table: str, fields: dict):
        url = f"https://api.airtable.com/v0/{self.base_id}/{table}"
        payload = {"fields": fields}
        response = requests.post(url, json=payload, headers=self.headers)
        if response.status_code not in (200, 201):
            raise Exception(f"Erreur CREATE {table} : {response.text}")
        return response.json()

    def find_records(self, table: str, formula: str):
        url = f"https://api.airtable.com/v0/{self.base_id}/{table}"
        params = {"filterByFormula": formula}
        response = requests.get(url, headers=self.headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Erreur FIND {table} : {response.text}")
        return response.json().get("records", [])