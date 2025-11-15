"""
scn_1.py
---------------------------------------------------------------------
Scénario SCN_1 : Génération du plan d'entraînement.

Ce scénario :
- Récupère le coureur dans Airtable
- Met en forme le contexte
- Enregistre un log dans 📋 Suivi génération
- Retourne un dictionnaire propre

ATTENTION :
Aucun champ n'est inventé.
Tout est conforme au RCTC (référentiel des champs techniques côté Airtable).
---------------------------------------------------------------------
"""

from datetime import datetime


def scenario_1(ctx):
    """
    Exécution du scénario SCN_1.
    ctx contient :
    - record_id
    - airtable (instance AirtableService)
    - fields (données du coureur)
    - debug
    """

    print("\n--- [SCN_1] DÉMARRAGE SCÉNARIO 1 ---")

    record_id = ctx.get("record_id")
    airtable = ctx.get("airtable")
    fields = ctx.get("fields", {})

    if ctx.get("debug"):
        print("[SCN_1] Contexte initial chargé.")
        print("[SCN_1] Champs coureur disponibles :", list(fields.keys()))

    # ----------------------------------------------------------
    # 1. Préparation du contexte enrichi
    #   (Strictement en respectant le RCTC)
    # ----------------------------------------------------------
    print("[SCN_1] Préparation du contexte enrichi…")

    enriched = {
        "record_id": record_id,

        # Champs exacts du RCTC
        "prenom": fields.get("Prénom"),
        "email": fields.get("Email") or "",  # renommé récemment → parfait

        # IMPORTANT
        # Mode_normalisé n’existe plus → Mode (champ réel Airtable)
        "mode": fields.get("Mode"),

        # Niveau_normalisé existe → OK
        "niveau": fields.get("Niveau_normalisé"),

        # Les deux existent : Objectif_normalisé prioritaire
        "objectif": fields.get("Objectif_normalisé") or fields.get("Objectif"),

        # Jours disponibles (ARRAY côté Airtable)
        "jours_dispo": fields.get("Jours disponibles") or [],

        # BON CHAMP selon RCTC
        "date_objectif": fields.get("date_course"),

        # DOIT RESTER (clé Airtable servant à config)
        "cle_niveau_reference": fields.get("Clé niveau référence"),

        # Champs calculés côté Airtable (ne pas recalculer ici)
        "date_debut_plan": fields.get("Date début plan (calculée)"),
    }

    if ctx.get("debug"):
        print("[SCN_1] Contexte enrichi :", enriched)

    # ----------------------------------------------------------
    # 2. Log Airtable dans 📋 Suivi génération
    # ----------------------------------------------------------
    print("[SCN_1] Log dans 📋 Suivi génération…")

    log_fields = {
        "Scénario": "SCN_1",            # EXACT selon RCTC
        "Record": record_id,            # NOM EXACT RCTC
        "Statut": "OK",                 # Pour l’instant succès
        "Horodatage": datetime.now().isoformat(timespec="seconds"),
        "Données scénario": str(enriched)  # Simple dump string
    }

    try:
        airtable.create_record("📋 Suivi génération", log_fields)
        print("[SCN_1] Log → OK")
    except Exception as e:
        print("[SCN_1] ⚠️ Erreur lors du log →", e)

    # ----------------------------------------------------------
    # 3. Retour API
    # ----------------------------------------------------------
    return {
        "scenario": "SCN_1",
        "status": "success",
        "record_id": record_id,
        "data": enriched
    }