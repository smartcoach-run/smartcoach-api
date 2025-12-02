import logging
from services.airtable_service import AirtableService
from core.internal_result import InternalResult

logger = logging.getLogger("SCN_6")

# --------------------------------------------------------------------
#  UTILITAIRES
# --------------------------------------------------------------------


def detect_allure(jour_relatif: int, objectif_normalise: str) -> str:
    """
    Mapping simple :
        - J1 → E
        - J2 → T / I / R (random contrôlé)
        - J3 → ASxx selon distance
    """

    if jour_relatif == 1:
        return "E"

    if jour_relatif == 2:
        # cycle T/I/R déterministe pour éviter le random
        cycle = ["T", "I", "R"]
        return cycle[(jour_relatif - 1) % 3]

    if jour_relatif == 3:
        if objectif_normalise in ["10K", "10 km"]:
            return "AS10"
        if objectif_normalise in ["21K", "21 km", "Semi"]:
            return "AS21"
        if objectif_normalise in ["42K", "42 km", "Marathon"]:
            return "AS42"
        return "AS10"

    return "E"


def find_template(records, phase_label, distance_norm, allure):
    """
    Recherche dans 📘 Séances types :
    - Champ "Phase" = libellé
    - Champ "Objectif" contient la distance normalisée
    - Champ "Catégorie" = allure (E / T / I / R / AS10 / etc.)
    """
    matching = []

    for rec in records:
        f = rec.get("fields", {})

        # PHASE
        if f.get("Phase") != phase_label:
            continue

        # DISTANCE -> champ "Objectif" = multi-select
        obj = f.get("Objectif", [])
        if isinstance(obj, list):
            if distance_norm not in obj:
                continue
        else:
            continue

        # CATÉGORIE
        if f.get("Catégorie") != allure:
            continue

        matching.append(rec)

    if not matching:
        return None

    # Retourne la première correspondance (simple, déterministe)
    return matching[0]


# --------------------------------------------------------------------
#  SCN_6 SIMPLE
# --------------------------------------------------------------------


def run_scn_6(context):
    """
    SCN_6 SIMPLE :
    - Prend les slots construits par SCN_1
    - Détermine type d'allure par slot
    - Sélectionne un template Airtable
    - Renvoie un JSON structuré
    """

    logger.info("SCN_6 → Démarrage (Version SIMPLE)")

    try:
        service = AirtableService()
        table_name = "📘 Séances types"

        logger.info("SCN_6 → Chargement des templates Airtable…")
        all_templates = service.fetch_all(table_name)

        distance = context.objectif_normalise  # ex : "10K"
        phases = context.week_structure.get("weeks", [])
        slots_by_week = context.slots  # issu de SCN_1

        final_output = []

        for week_obj in slots_by_week:
            semaine_num = week_obj["semaine"]
            slot_list = week_obj["slots"]

            # identifier la phase de la semaine
            phase_info = next(
                (p for p in phases if p["semaine"] == semaine_num),
                None
            )
            if not phase_info:
                logger.warning(f"SCN_6 → Pas trouvé phase pour semaine {semaine_num}")
                continue

            phase_label = phase_info["phase"]  # ex : "Prépa générale"

            week_result = {
                "semaine": semaine_num,
                "phase": phase_label,
                "seances": []
            }

            for s in slot_list:
                jour = s["jour"]
                jr = s["jour_relatif"]
                slot_id = s["slot_id"]

                # déterminer l’allure
                allure = detect_allure(jr, distance)

                # récupérer template
                tpl = find_template(
                    all_templates,
                    phase_label=phase_label,
                    distance_norm=distance,
                    allure=allure
                )

                if tpl:
                    f = tpl["fields"]
                    modele = f.get("Modèle", "")
                    categorie = f.get("Catégorie", "")
                    duree = f.get("Durée", "")
                    description = f.get("Description", "")
                else:
                    modele = "Séance non trouvée"
                    categorie = allure
                    duree = None
                    description = "Aucun modèle correspondant dans Airtable."

                week_result["seances"].append({
                    "slot_id": slot_id,
                    "jour": jour,
                    "jour_relatif": jr,
                    "type_allure": allure,
                    "modele": modele,
                    "categorie": categorie,
                    "duree": duree,
                    "description": description
                })

            final_output.append(week_result)

        logger.info("SCN_6 → OK (simple generation)")

        return InternalResult.ok(
            message="SCN_6 terminé avec succès (Version SIMPLE)",
            data={"plan": final_output}
        )

    except Exception as e:
        logger.exception("SCN_6 → ERREUR")
        return InternalResult.error(
            message=f"Erreur dans SCN_6 : {e}",
            source="SCN_6"
        )