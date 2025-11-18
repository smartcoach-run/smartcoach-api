# smartcoach_services/log_service.py
# ===============================================================
# Service de log centralisé pour 📋 Suivi génération
# ===============================================================

from datetime import datetime
import json

from smartcoach_core.airtable_refs import ATABLES
from smartcoach_core.airtable_fields import ATFIELDS
from smartcoach_core.config import SMARTCOACH_ENV

LOG_SCRIPT_VERSION = "SCN_1_LOG_V1"


# ---------------------------------------------------------------
# 1. Création du LogContext
# ---------------------------------------------------------------

def create_log_context(record_id: str, scenario_id: str, debug: bool = False) -> dict:
    now = datetime.utcnow().isoformat()
    env = (SMARTCOACH_ENV or "DEV").upper()

    return {
        "record_id": record_id,
        "scenario_id": scenario_id,

        "meta": {
            "date_generation": now,
            "env": env,
            "version_script": LOG_SCRIPT_VERSION,
            "debug": bool(debug),
            "started_at": now,
            "ended_at": None,
            "duration_sec": None,
        },

        "input": {},
        "engine": {},

        "output": {
            "plan_genere": False,
            "nom_plan": None,
            "nb_seances": 0,
            "type_plan": None,
            "duree_semaines": None,
            "alertes": [],
        },

        "status": {
            "statut_execution": None,
            "message": None,
            "erreur_code": None,
        },

        "tech": {
            "source": "API",
            "make_route_name": None,
            "cle_diagnostic": None,
            "raw": {},
        },
    }


# ---------------------------------------------------------------
# 2. Mapping LogContext → Airtable
# ---------------------------------------------------------------

def _map_log_context_to_airtable_fields(log: dict) -> dict:

    meta = log.get("meta", {})
    output = log.get("output", {})
    status = log.get("status", {})
    tech = log.get("tech", {})

    alertes = output.get("alertes") or []

    print(">>> VERSION LOG_SERVICE ACTUELLE CHARGÉE")

    fields = {}

    # Identifiant logique du log
    fields[ATFIELDS.SG_LOG_ID] = log.get("record_id")

    # Métadonnées
    fields[ATFIELDS.SG_DATE_GENERATION] = meta.get("date_generation")
    fields[ATFIELDS.SG_ENVIRONNEMENT] = meta.get("env")
    fields[ATFIELDS.SG_DUREE_EXECUTION] = meta.get("duration_sec")
    fields[ATFIELDS.SG_DEBUG_ACTIF] = meta.get("debug")
    fields[ATFIELDS.SG_VERSION_SCRIPT] = meta.get("version_script")

    # Scénario & source
    fields[ATFIELDS.SG_TYPE_SCENARIO] = log.get("scenario_id")
    fields[ATFIELDS.SG_SOURCE] = tech.get("source")

    # Statut
    fields[ATFIELDS.SG_STATUT_EXECUTION] = status.get("statut_execution")
    fields[ATFIELDS.SG_MESSAGE_STATUT] = status.get("message") or status.get("erreur_code")
    fields[ATFIELDS.SG_ERREUR_CODE] = status.get("erreur_code") or "OK"

    # Résultat plan
    fields[ATFIELDS.SG_PLAN_GENERE] = output.get("plan_genere")
    fields[ATFIELDS.SG_NOM_PLAN] = output.get("nom_plan")
    fields[ATFIELDS.SG_NB_SEANCES_GENEREES] = output.get("nb_seances")
    fields[ATFIELDS.SG_TYPE_PLAN] = output.get("type_plan")
    fields[ATFIELDS.SG_DUREE_PLAN_SEMAINES] = output.get("duree_semaines")  

    # Alertes rencontrées
    alertes = output.get("alertes")
    if isinstance(alertes, list):
        alertes = ", ".join(alertes)   # transforme la liste en texte
    if not alertes:
        alertes = "RAS"

    fields[ATFIELDS.SG_ALERTES_RENCONTREES] = alertes

    # Email (géré dans Make)
    fields[ATFIELDS.SG_EMAIL_ENVOYE] = None

    # Infos techniques
    fields[ATFIELDS.SG_MAKE_ROUTE_NAME] = tech.get("source")
    #fields[ATFIELDS.SG_CLE_DIAGNOSTIC] = tech.get("cle_diagnostic")
    fields[ATFIELDS.SG_LIEN_JSON_BRUT] = json.dumps(log, ensure_ascii=False)

    # Nettoyage → on enlève les None
    return {k: v for k, v in fields.items() if v is not None}


# ---------------------------------------------------------------
# 3. UPSERT du log
# ---------------------------------------------------------------

def save_log_context(airtable, log: dict):
    if not log:
        return None

    record_id = log.get("record_id")
    if not record_id:
        print("[LOG] record_id manquant.")
        return None

    fields = _map_log_context_to_airtable_fields(log)

    try:
        formula = f"{{{ATFIELDS.SG_LOG_ID}}} = '{record_id}'"
        existing = airtable.find_records(ATABLES.SUIVI_GENERATION, formula) or []

        if existing:
            log_record_id = existing[0]["id"]
            return airtable.update_record(ATABLES.SUIVI_GENERATION, log_record_id, fields)
        else:
            return airtable.create_record(ATABLES.SUIVI_GENERATION, fields)

    except Exception as e:
        print(f"[LOG ERROR] Impossible d’écrire le log : {e}")
        return None


# ---------------------------------------------------------------
# 4. Compat : ancien style
# ---------------------------------------------------------------

def log_event(airtable, record_id, statut, message, environnement=None):
    env = (environnement or SMARTCOACH_ENV or "DEV").upper()

    log = create_log_context(record_id=record_id, scenario_id="SCN_1", debug=False)
    log["meta"]["env"] = env
    log["status"]["statut_execution"] = statut
    log["status"]["message"] = message

    log["tech"]["cle_diagnostic"] = f"SCN_1 - {record_id}"

    return save_log_context(airtable, log)
