# smartcoach_scenarios/scn_1.py
# ===============================================================
# SCN_1 : scénario de génération de plan à partir d’un coureur.
#
# V1 : ne génère pas encore le plan ni les séances,
#      mais prépare le contexte et enrichit le LogContext.
# ===============================================================

from datetime import datetime

from smartcoach_services.log_service import log_event  # compat si besoin
from smartcoach_core.airtable_fields import ATFIELDS, get_field


def scenario_1(ctx: dict):
    print("\n--- [SCN_1] DÉMARRAGE SCÉNARIO 1 ---")

    record_id = ctx.get("record_id")
    airtable = ctx.get("airtable")
    coureur = ctx.get("coureur") or {}
    fields = ctx.get("fields", {})
    debug = ctx.get("debug", False)
    log = ctx.get("log")

    if debug:
        print("[SCN_1] Contexte initial chargé.")
        print("[SCN_1] Champs coureur disponibles :", list(fields.keys()))

    # ----------------------------------------------------------
    # 1. Contexte enrichi — conforme RCTC / Coureurs
    # ----------------------------------------------------------
    prenom = get_field(coureur, ATFIELDS.COU_PRENOM)
    email = get_field(coureur, ATFIELDS.COU_EMAIL) or ""
    mode = get_field(coureur, ATFIELDS.COU_MODE)
    niveau = get_field(coureur, ATFIELDS.COU_NIVEAU_NORMALISE)
    objectif_norm = get_field(coureur, ATFIELDS.COU_OBJECTIF_NORMALISE)
    jours_dispo = get_field(coureur, ATFIELDS.COU_JOURS_DISPO) or []
    date_objectif = get_field(coureur, ATFIELDS.COU_DATE_COURSE)
    cle_niveau_ref = get_field(coureur, ATFIELDS.COU_CLE_NIVEAU_REF)
    date_debut_plan = get_field(coureur, ATFIELDS.COU_DATE_DEBUT_PLAN)
    duree_plan_sem = get_field(coureur, ATFIELDS.COU_DUREE_PLAN_CALC)

    enriched = {
        "record_id": record_id,
        "prenom": prenom,
        "email": email,
        "mode": mode,
        "niveau": niveau,
        "objectif": objectif_norm or fields.get("Objectif"),
        "jours_dispo": jours_dispo,
        "date_objectif": date_objectif,
        "cle_niveau_reference": cle_niveau_ref,
        "date_debut_plan": date_debut_plan,
        "duree_plan_semaines": duree_plan_sem,
    }

    # On remet aussi ces éléments dans ctx pour les futurs services (generation_service, etc.)
    ctx.update({
        "mode": enriched["mode"],
        "niveau": enriched["niveau"],
        "objectif": enriched["objectif"],
        "jours_dispo": enriched["jours_dispo"],
        "date_objectif": enriched["date_objectif"],
        "date_debut_plan": enriched["date_debut_plan"],
        "nb_semaines_plan": enriched["duree_plan_semaines"],
    })

    if debug:
        print("[SCN_1] Contexte enrichi :", enriched)

    # ----------------------------------------------------------
    # 2. Injection dans le LogContext
    # ----------------------------------------------------------
    if log is not None:
        # Données d'entrée
        log["input"].update(enriched)

        # Type de plan & durée
        log["output"]["type_plan"] = enriched["objectif"]
        log["output"]["duree_semaines"] = enriched.get("duree_plan_semaines")

        # Étape de process
        process = log.setdefault("process", {})
        steps = process.setdefault("steps", [])
        steps.append("SCN_1 : contexte coureur enrichi")

        # Source déjà initialisée dans create_log_context
        log["tech"]["source"] = log["tech"].get("source") or "API"

    # ----------------------------------------------------------
    # 3. (Plus tard) appel à generation_service.generate_plan / generate_sessions
    # ----------------------------------------------------------
    # Pour l’instant, SCN_1 se contente de préparer le contexte + log.
    # La génération du plan et des séances sera branchée ici dans une étape suivante.

    # ----------------------------------------------------------
    # 4. Retour API
    # ----------------------------------------------------------
    return {
        "scenario": "SCN_1",
        "status": "success",
        "record_id": record_id,
        "data": enriched,
    }
