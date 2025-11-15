# smartcoach_services/log_service.py
# ===============================================================
# Service de log centralisé pour 📋 Suivi génération
# - 1 ligne par record_id (UPSERT sur "Nom du log / Record ID")
# - Pas de lien avec "Scénarios de validation" pour l’instant
# ===============================================================

from smartcoach_core.airtable_refs import ATABLES
from smartcoach_core.airtable_fields import ATFIELDS
from smartcoach_core.config import SMARTCOACH_ENV


def log_event(airtable, record_id, statut, message, environnement=None):
    """
    - Clé fonctionnelle : champ "Nom du log / Record ID"
    - UPDATE si record_id existe
    - Sinon CREATE
    """

    env = (environnement or SMARTCOACH_ENV or "DEV").upper()

    payload = {
        ATFIELDS.SG_LOG_ID: record_id,
        ATFIELDS.SG_STATUT_EXECUTION: statut,
        ATFIELDS.SG_MESSAGE_STATUT: message,
        ATFIELDS.SG_ENVIRONNEMENT: env,
    }

    try:
        # 1) On tente de trouver un log existant
        try:
            existing = airtable.search_by_field(
                ATABLES.SUIVI_GENERATION,
                ATFIELDS.SG_LOG_ID,
                record_id,
            ) or []
        except AttributeError:
            existing = []

        # 2) UPSERT
        if existing:
            log_record_id = existing[0]["id"]
            return airtable.update_record(
                ATABLES.SUIVI_GENERATION,
                log_record_id,
                payload
            )
        else:
            return airtable.create_record(
                ATABLES.SUIVI_GENERATION,
                payload
            )

    except Exception as e:
        print("[LOG ERROR] Impossible d’écrire le log :", e)
        return None

    """
    Écrit / met à jour un log dans la table 📋 Suivi génération.

    - Clé fonctionnelle : champ "Nom du log / Record ID"
    - Si un log existe déjà pour ce record_id → update
    - Sinon → create
    """

    env = environnement or SMARTCOACH_ENV or "DEV"

    # ⚙️ Payload minimal, aligné sur RCTC
    payload = {
        ATFIELDS.SG_LOG_ID: record_id,              # "Nom du log / Record ID"
        ATFIELDS.SG_STATUT_EXECUTION: statut,       # "Statut exécution"
        ATFIELDS.SG_MESSAGE_STATUT: message,        # "Message de statut"
        ATFIELDS.SG_ENVIRONNEMENT: env,             # "Environnement"
    }

    try:
        # 1) On essaie de trouver un log existant pour ce record_id
        try:
            existing = airtable.search_by_field(
                ATABLES.SUIVI_GENERATION,
                ATFIELDS.SG_LOG_ID,
                record_id,
            ) or []
        except AttributeError:
            # Vieille version d'AirtableService sans search_by_field :
            # dans ce cas, on bascule en "create only".
            existing = []

        # 2) UPSERT
        if existing:
            # On prend la première ligne trouvée et on la met à jour
            log_record_id = existing[0]["id"]
            return airtable.update_record(
                ATABLES.SUIVI_GENERATION,
                log_record_id,
                payload
            )
        else:
            # Aucun log existant → création
            return airtable.create_record(
                ATABLES.SUIVI_GENERATION,
                payload
            )

    except Exception as e:
        print(f"[LOG ERROR] Impossible d’écrire le log : {e}")
        return None