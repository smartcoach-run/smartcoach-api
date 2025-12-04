# ======================================================================
#  SCENARIO 3 : Mapping catégories / modèles de séance (Option C)
# ======================================================================

from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES
# ===== IMPORT MAPPING =====
from utils.session_types_utils import map_record_to_session_type



def convert_phase(phase_scn1):
    """
    Convertit la phase issue de SCN_1 vers les phases Airtable.
    Ajustable selon ta logique d'entraînement.
    """
    mapping = {
        "Prépa générale": ["Base1", "Base2"],
        "Spécifique": ["Progression"],
        "Affûtage": ["Affûtage"]
    }
    return mapping.get(phase_scn1, [])


def select_model(models, phases, univers="Running"):
    """
    Sélectionne LE modèle Airtable correspondant à :
    - une phase (Base1/Base2/Progression/Affûtage)
    - un univers (Running)
    - un type d'allure cohérent (mais pas obligatoire pour V1)
    """

    candidates = []

    for m in models:

        # 1) Univers
        univers_list = m.get("univers", [])
        if univers not in univers_list:
            continue

        # 2) Phase
        phase_ids = m.get("phase_ids", [])
        if not any(p in phase_ids for p in phases):
            continue

        candidates.append(m)

    # Pour V1 → premier match
    return candidates[0] if candidates else None



# ======================================================================
#  RUN SCN_3
# ======================================================================

def run_scn_3(context):

    print("[SCN_3] ▶ Mapping catégories / modèles Airtable")

    # -----------------------------------------------------------
    # Charger les modèles Airtable (séances types)
    # -----------------------------------------------------------
    airtable = AirtableService()
    raw_models = airtable.list_all(ATABLES.SEANCES_TYPES)
    models = [map_record_to_session_type(rec) for rec in raw_models]

    # Vérification DEBUG
    print(f"[SCN_3] {len(models)} modèles Airtable chargés.")

    sessions = context.sessions_targets  # sessions issues de SCN_2
    cleaned_sessions = []

    for sess in sessions:
        phase_s1 = sess.get("phase")              # ex: "Prépa générale"
        phases_normalisees = convert_phase(phase_s1)

        # -----------------------------------------------------------
        # Sélection du modèle Airtable (via Option C)
        # -----------------------------------------------------------
        modele = select_model(models, phases_normalisees, univers="Running")

        if modele:
            sess["categorie_seance"] = modele.get("categorie")
            sess["type_seance_cle"] = modele.get("type_allure")
            sess["modele_nom"] = modele.get("nom")
            sess["duree_min"] = modele.get("duree_min")
            sess["description"] = modele.get("description")
        else:
            # Aucun modèle trouvé → on garde des champs vides,
            # mais SCN_6 ne plantera plus : valeurs vides OK.
            sess["categorie_seance"] = ""
            sess["type_seance_cle"] = ""
            sess["modele_nom"] = "Séance non trouvée"
            sess["duree_min"] = None
            sess["description"] = "Aucun modèle compatible dans Airtable."

        cleaned_sessions.append(sess)

    # Mise à jour du contexte
    context.sessions_targets = cleaned_sessions

    print("[SCN_3] ✔ Terminé — modèles ajoutés aux sessions.")

    from core.internal_result import InternalResult

    return InternalResult.make_success(
        data={"sessions_targets": cleaned_sessions},
        source="SCN_3"
    )

