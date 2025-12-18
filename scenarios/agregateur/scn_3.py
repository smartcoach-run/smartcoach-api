# =====================================================================
# SCN_3 – Mapping modèles Airtable → Slots (SmartCoach 2025 STABLE)
# =====================================================================

from utils.session_types_utils import map_record_to_session_type

import logging

logger = logging.getLogger("SCN_3")


def run_scn_3(context):
    logger.info("[SCN_3] ▶ Mapping catégories / modèles Airtable")

    records = getattr(context, "models_seance_types", None)

    if not records:
        raise RuntimeError("SCN_3 : aucun modèle 'Séances Types' dans le context. Vérifie SCN_1.")

    # Convertir Airtable → SessionType
    models = [map_record_to_session_type(rec) for rec in records]

    logger.info(f"[SCN_3] {len(models)} modèles Airtable chargés.")

    slots_by_week = context.slots_by_week
    user_mode = context.user_mode

    for week_id, data in slots_by_week.items():
        for slot in data["slots"]:

            target_cat = slot.get("type_allure")
            target_phase = slot.get("phase")
            found = None

            # 1️⃣ Match exact
            for m in models:
                if (
                    m.cat_smartcoach == target_cat
                    and target_phase in m.phase_ids
                    and (not m.mode or user_mode in m.mode)
                ):
                    found = m
                    break

            # 2️⃣ Match partiel (sans phase)
            if not found:
                for m in models:
                    if (
                        m.cat_smartcoach == target_cat
                        and (not m.mode or user_mode in m.mode)
                    ):
                        found = m
                        break

            # 3️⃣ Fallback EF
            if not found and user_mode == "Running":
                for m in models:
                    if m.cat_smartcoach == "EF":
                        found = m
                        break

            # 4️⃣ Rien trouvé
            if not found:
                slot["modele"] = "Séance non trouvée"
                slot["description"] = "Aucun modèle correspondant dans Airtable."
                slot["categorie"] = target_cat
                continue

            # Injecter le modèle trouvé
            slot["modele"] = found.nom
            slot["description"] = found.description
            slot["categorie"] = found.categorie or found.cat_smartcoach
            slot["duree"] = found.duree
            slot["type_allure"] = found.cat_smartcoach

    logger.info("[SCN_3] ✔ Terminé — modèles ajoutés aux sessions.")
    return context
