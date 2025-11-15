# scn_1.py
from datetime import datetime
from smartcoach_services.log_service import log_generation   # on délègue le log propre
from smartcoach_core.airtable_fields import ATFIELDS


def scenario_1(ctx):
    print("\n--- [SCN_1] DÉMARRAGE SCÉNARIO 1 ---")

    record_id = ctx.get("record_id")
    airtable = ctx.get("airtable")
    fields = ctx.get("fields", {})
    debug = ctx.get("debug", False)

    if debug:
        print("[SCN_1] Contexte initial chargé.")
        print("[SCN_1] Champs coureur disponibles :", list(fields.keys()))

    # ----------------------------------------------------------
    # 1. Contexte enrichi — conforme RCTC
    # ----------------------------------------------------------
    enriched = {
        "record_id": record_id,
        "prenom": fields.get("Prénom"),
        "email": fields.get("Email") or "",
        "mode": fields.get("Mode"),
        "niveau": fields.get("Niveau_normalisé"),
        "objectif": fields.get("Objectif_normalisé") or fields.get("Objectif"),
        "jours_dispo": fields.get("Jours disponibles") or [],
        "date_objectif": fields.get("date_course"),
        "cle_niveau_reference": fields.get("Clé niveau référence"),
        "date_debut_plan": fields.get("Date début plan (calculée)"),
    }

    if debug:
        print("[SCN_1] Contexte enrichi :", enriched)

    # ----------------------------------------------------------
    # 2. LOG CORRECT selon Airtable (via log_service)
    # ----------------------------------------------------------
    print("[SCN_1] Log dans 📋 Suivi génération…")

    log_generation(
        airtable=airtable,
        record_id=record_id,
        scenario="SCN_1",
        status="START",
        message="Scénario 1 – Contexte chargé"
    )

    # ----------------------------------------------------------
    # 3. Retour API
    # ----------------------------------------------------------
    return {
        "scenario": "SCN_1",
        "status": "success",
        "record_id": record_id,
        "data": enriched
    }