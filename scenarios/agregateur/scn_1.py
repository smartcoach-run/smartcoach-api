from datetime import date, timedelta, datetime
from typing import List, Dict
from core.internal_result import InternalResult
from core.utils.logger import log_info, log_error
from ics.ics_builder import run_generate_ics
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES
from services.airtable_fields import ATFIELDS, get_field

MODULE_NAME = "SCN_1"

# =========================
# Helpers jours / dates
# =========================

DAY_ORDER = {
    "Lundi": 0,
    "Mardi": 1,
    "Mercredi": 2,
    "Jeudi": 3,
    "Vendredi": 4,
    "Samedi": 5,
    "Dimanche": 6,
}

def find_first_slot_date(start_date: date, dispos: List[str]) -> date:
    """
    Retourne la première date >= start_date correspondant à un jour dispo
    en s'appuyant uniquement sur DAY_ORDER.
    """
    dispo_indexes = {DAY_ORDER[d] for d in dispos}

    for delta in range(0, 8):
        candidate = start_date + timedelta(days=delta)
        if candidate.weekday() in dispo_indexes:
            return candidate

    raise RuntimeError(
        f"No eligible slot found in next 7 days from {start_date}"
    )

def build_training_days(
    jours_disponibles: list[str],
    niveau: str | None = None,
    objectif: str | None = None,
) -> dict:
    """
    Moteur SmartCoach — construction intelligente des jours d'entraînement
    """

    if not jours_disponibles:
        raise ValueError("Aucun jour disponible fourni")

    DAY_ORDER = {
        "Lundi": 0,
        "Mardi": 1,
        "Mercredi": 2,
        "Jeudi": 3,
        "Vendredi": 4,
        "Samedi": 5,
        "Dimanche": 6,
    }

    # Normalisation / tri
    jours_ordonnes = sorted(jours_disponibles, key=lambda d: DAY_ORDER[d])

    # Nombre de séances cible (simple à ce stade)
    nb_seances_cible = len(jours_ordonnes)

    def pick_non_consecutive_days(ordered_days, nb_seances):
        selected = []
        last_idx = None

        for day in ordered_days:
            idx = DAY_ORDER[day]
            if last_idx is None or idx - last_idx > 1:
                selected.append(day)
                last_idx = idx
            if len(selected) == nb_seances:
                break

        return selected

    jours_seances = pick_non_consecutive_days(
        jours_ordonnes,
        nb_seances_cible
    )

    ajustement = False
    message = None

    if len(jours_seances) < nb_seances_cible:
        ajustement = True
        message = (
            "On a ajusté les jours d'entraînement pour éviter "
            "des séances consécutives."
        )

    return {
        "jours_seances": jours_seances,
        "nb_seances": len(jours_seances),
        "ajustement": ajustement,
        "message": message,
    }

def run_scn_1(context) -> InternalResult:
    """
    Wrapper SCN_1
    Input attendu : context.record_id = ID Coureur
    """
    try:
        coureur_id = context.record_id

        result = run_scn_1_slots(coureur_id)

        return InternalResult.ok(
            message="SCN_1 exécuté avec succès",
            source="SCN_1",
            data=result,
        )

    except Exception as e:
        return InternalResult.error(
            message=f"Exception SCN_1 : {e}",
            source="SCN_1",
            data={},
        )

def run_scn_1_slots(coureur_id: str) -> dict:
    """
    SCN_1 – Génération de la structure du plan (slots)
    Source de vérité : table Coureur (Airtable)
    """

    airtable = AirtableService()

    # 1️⃣ Lecture du Coureur
    record = airtable.get_record(ATABLES.COU_TABLE, coureur_id)
    if not record:
        raise RuntimeError(f"Coureur introuvable : {coureur_id}")

    # 2️⃣ Lecture des champs via référentiel ATFIELDS
    date_debut = get_field(record, ATFIELDS.COU_DATE_DEBUT_PLAN)
    date_course = get_field(record, ATFIELDS.COU_DATE_COURSE)

    dispos = get_field(record, ATFIELDS.COU_JOURS_DISPO, [])

    nb_semaines = (
        get_field(record, ATFIELDS.COU_DUREE_PLAN_CALC)
        or get_field(record, ATFIELDS.COU_TEST_DUREE_PLAN)
    )

    # Conversion robuste string → date (Airtable safe)
    if isinstance(date_debut, str):
        date_debut_date = datetime.strptime(
            date_debut[:10], "%Y-%m-%d"
        ).date()
    else:
        date_debut_date = date_debut

    # 🔒 Source de vérité unique pour SCN_1
    date_reference = date_debut_date

    # 2bis️⃣ Construction intelligente des jours (SmartCoach)
    result_jours = build_training_days(
        jours_disponibles=dispos,
        niveau=get_field(record, ATFIELDS.COU_NIVEAU),
        objectif=get_field(record, ATFIELDS.COU_OBJECTIF_NORMALISE),
    )

    # Jours et nb séances VALIDÉS
    dispos = result_jours["jours_seances"]
    sessions_per_week = result_jours["nb_seances"]

    # 2ter️⃣ Persistance des jours validés dans Airtable
    airtable.update_record_by_id(
        ATABLES.COU_TABLE,
        coureur_id,
        {
            ATFIELDS.COU_JOURS_FINAL: dispos,
        },
    )

    # 3️⃣ Garde-fous minimum
    if not date_debut:
        raise RuntimeError("Date de début de plan absente (COU_DATE_DEBUT_PLAN)")

    if not nb_semaines or nb_semaines <= 0:
        raise RuntimeError("Durée du plan invalide (nb_semaines)")

    if not dispos:
        raise RuntimeError("Aucun jour d'entraînement défini (Jours disponibles)")

    if not sessions_per_week or sessions_per_week <= 0:
        raise RuntimeError("Nombre de séances hebdomadaires invalide")

    if len(dispos) < sessions_per_week:
        raise RuntimeError("Nombre de jours < nombre de séances")

    # 4️⃣ Génération du squelette de plan (logique existante)
    plan_squelette = {}

    for week in range(1, nb_semaines + 1):
        week_key = f"S{week}"
        plan_squelette[week_key] = {}

        for day in dispos:
            plan_squelette[week_key][day] = None

    # 4bis️⃣ Calcul de la première date réelle de séance
    first_slot_date = find_first_slot_date(date_debut_date, dispos)
    
    # Début de la semaine S1 (lundi de la date de référence)
    week_1_start = date_debut_date - timedelta(days=date_debut_date.weekday())

    # 5️⃣ Résultat standard SCN_1
    return {
        "nb_semaines": nb_semaines,

        # Début calendaire du plan (semaine S1)
        "date_debut_semaine_1": week_1_start.isoformat(),

        # Première séance réelle
        "date_premier_slot": first_slot_date.isoformat(),

        "date_fin_plan": date_course if date_course else None,
        "jours_optimises": dispos,
        "plan_squelette": plan_squelette,
    }

def normalize_and_order_days(dispos: List[str]) -> List[str]:
    """Normalise et ordonne les jours selon l'ordre semaine."""
    return sorted(dispos, key=lambda d: DAY_ORDER[d])


def get_week_dates(week_start: date) -> Dict[str, date]:
    """Retourne un mapping Jour -> Date pour une semaine donnée."""
    return {
        day: week_start + timedelta(days=offset)
        for day, offset in DAY_ORDER.items()
    }


# =========================
# Airtable persistence (stub)
# =========================

def persist_slot(slot_payload: dict):
    """
    Persistance d'un slot dans Airtable.
    À brancher sur airtable_service.create_record("Slots", payload)
    """
    # Exemple :
    # airtable_service.create_record("Slots", slot_payload)
    pass
