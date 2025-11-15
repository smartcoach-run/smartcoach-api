"""
log_service.py
---------------------------------------------------------------------
Service de journalisation SmartCoach.

CONFORME :
- RCTC
- Manuel d’implémentation SmartCoach
- Story SCN_1
- Table Airtable : Logs

Ce module fournit deux fonctions :
- log_event        → pour tracer les étapes standard
- log_scn1_execution → pour tracer l'exécution du scénario SCN_1

AUCUNE invention de champs :
Les champs utilisés correspondent à la table Logs d’Airtable :
- Type_evenement
- Message
- Scenario
- Niveau
- Coureur_record_id
- Payload
---------------------------------------------------------------------
"""

from smartcoach_services.airtable_service import AirtableService

# Options de debug / environnement
try:
    from smartcoach_core.config import SMARTCOACH_ENV, SMARTCOACH_DEBUG
except ImportError:
    # Valeurs par défaut en local si smartcoach_core n'est pas dispo
    SMARTCOACH_ENV = "local"
    SMARTCOACH_DEBUG = True


class LogService:

    def __init__(self, airtable: AirtableService):
        """
        Service de logging.

        PARAMÈTRES
        ----------
        airtable : AirtableService
            Instance Airtable déjà initialisée dans main.py
        """
        self.airtable = airtable
        self.table_name = "Logs"   # conforme Airtable (tu l'utilises déjà)

    # ------------------------------------------------------------------
    # LOG ÉVÉNEMENT GÉNÉRIQUE
    # ------------------------------------------------------------------
    def log_event(self, type_event: str, message: str, payload: dict | None = None,
                  scenario: str | None = None, niveau: str | None = None,
                  coureur_id: str | None = None):
        """
        Log d’un événement générique.

        PARAMÈTRES
        ----------
        type_event : str
            Exemples : "INFO", "DEBUG", "SCENARIO", "ERREUR"
        message : str
            Description courte
        payload : dict | None
            Informations supplémentaires (sérialisées en JSON)
        scenario : str | None
            Ex : "SCN_1"
        niveau : str | None
            Niveau d’importance ou de contexte
        coureur_id : str | None
            record_id du coureur concerné (si applicable)
        """

        record_fields = {
            "Type_evenement": type_event,
            "Message": message,
            "Scenario": scenario,
            "Niveau": niveau,
            "Coureur_record_id": coureur_id,
            "Payload": str(payload) if payload else None,
            "Horodatage": datetime.utcnow().isoformat()  # champ standard quand il existe
        }

        # Nettoyage – Airtable n’aime pas les champs None
        record_fields = {k: v for k, v in record_fields.items() if v is not None}

        self.airtable.create_record(self.table_name, record_fields)

    # ------------------------------------------------------------------
    # LOG SCN_1
    # ------------------------------------------------------------------
    def log_scn1_execution(self, step: str, message: str, coureur_id: str | None = None,
                           payload: dict | None = None):
        """
        Log spécialisé pour SCN_1.

        PARAMÈTRES
        ----------
        step : str
            Étape du scénario (ex : "Chargement_coureur", "Validation", "Fin")
        message : str
            Description
        coureur_id : str | None
            record_id du coureur en cours
        payload : dict | None
            Données utiles
        """

        record_fields = {
            "Type_evenement": f"SCN1_{step}",
            "Message": message,
            "Scenario": "SCN_1",
            "Coureur_record_id": coureur_id,
            "Payload": str(payload) if payload else None,
            "Horodatage": datetime.utcnow().isoformat()
        }

        record_fields = {k: v for k, v in record_fields.items() if v is not None}

        self.airtable.create_record(self.table_name, record_fields)