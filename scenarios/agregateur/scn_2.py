# scenarios/agregateur/scn_2.py

from datetime import date, timedelta
from typing import Dict, Any, List

from core.internal_result import InternalResult
from core.utils.logger import log_info, log_error

# -------------------------------------------------------------------
# Helpers: gestion dates & jours
# -------------------------------------------------------------------

DAYS_MAP = {
    "Lundi": 0,
    "Mardi": 1,
    "Mercredi": 2,
    "Jeudi": 3,
    "Vendredi": 4,
    "Samedi": 5,
    "Dimanche": 6,
}

def _parse_iso(d: str) -> date:
    return date.fromisoformat(d)

def _compute_first_slot_date(date_debut: date, target_day: str) -> date:
    """Retourne la première date >= date_debut correspondant au jour."""
    target_idx = DAYS_MAP[target_day]
    delta = (target_idx - date_debut.weekday()) % 7
    return date_debut + timedelta(days=delta)

# -------------------------------------------------------------------
# Phases dynamiques (P1/P2/P3/P4)
# -------------------------------------------------------------------

def _compute_phase_slices(nb_semaines: int) -> List[str]:
    if nb_semaines <= 0:
        return []

    ratios = [0.30, 0.20, 0.40, 0.10]
    raw = [r * nb_semaines for r in ratios]

    phases_len = [max(1, round(x)) for x in raw]

    diff = sum(phases_len) - nb_semaines
    if diff != 0:
        phases_len[-1] -= diff
        if phases_len[-1] < 1:
            phases_len[-1] = 1

    phases = []
    labels = ["P1", "P2", "P3", "P4"]
    for label, n in zip(labels, phases_len):
        phases.extend([label] * n)

    if len(phases) > nb_semaines:
        phases = phases[:nb_semaines]
    elif len(phases) < nb_semaines:
        phases.extend(["P4"] * (nb_semaines - len(phases)))

    return phases

# -------------------------------------------------------------------
# Pattern intensité hebdo (LIGHT / HARD / LONG)
# -------------------------------------------------------------------

def _build_week_intensity_pattern(nb_sessions: int) -> List[str]:
    if nb_sessions <= 0:
        return []
    if nb_sessions == 1:
        return ["LONG"]
    if nb_sessions == 2:
        return ["LIGHT", "LONG"]
    if nb_sessions == 3:
        return ["LIGHT", "HARD", "LONG"]
    if nb_sessions == 4:
        return ["LIGHT", "HARD", "LIGHT", "LONG"]
    return ["LIGHT", "HARD", "LIGHT", "HARD", "LONG"][:nb_sessions]

# -------------------------------------------------------------------
# Référentiels (placeholder pour la future intégration Airtable)
# -------------------------------------------------------------------

def _load_seances_types() -> List[Dict[str, Any]]:
    return []

def _load_mapping_phase(categorie_smartcoach: str) -> List[Dict[str, Any]]:
    return []

# -------------------------------------------------------------------
# Placeholder : sélection de séance (sera remplacé par Airtable)
# -------------------------------------------------------------------

def _choose_seance_for_slot(seances_types, phase, intensity_tag, jour):
    return None  # volontaire pour tester la structure

# -------------------------------------------------------------------
# SCN_2 principal
# -------------------------------------------------------------------

def run_scn_2(context, data_scn1: Dict[str, Any]) -> InternalResult:
    try:
        log_info("SCN_2 → Démarrage (construction des slots)")

        nb_semaines = int(data_scn1.get("nb_semaines", 0))
        if nb_semaines <= 0:
            return InternalResult.error(
                code="KO_DATA",
                message="nb_semaines invalide dans data_scn1",
                data={"data_scn1": data_scn1},
                source="SCN_2",
            )

        date_debut_plan = _parse_iso(data_scn1["date_debut_plan"])
        date_objectif = _parse_iso(data_scn1.get("date_fin_plan"))
        jours = data_scn1.get("jours_optimises") or data_scn1.get("jours_dispos") or []
        categorie_smartcoach = data_scn1.get("categorie_smartcoach")

        record_id = getattr(context, "record_id", None)
        if not record_id:
            return InternalResult.error(
                message="record_id manquant pour SCN_2",
                source="SCN_2"
            )

        if not jours:
            return InternalResult.error(
                code="KO_DATA",
                message="Aucun jour disponible pour construire les slots",
                data={},
                source="SCN_2",
            )

        phases_by_week = _compute_phase_slices(nb_semaines)
        pattern = _build_week_intensity_pattern(len(jours))

        seances_types = _load_seances_types()
        mapping_phase = _load_mapping_phase(categorie_smartcoach)

        # Pré-calcul du premier jour valide
        first_dates = {
            jour: _compute_first_slot_date(date_debut_plan, jour)
            for jour in jours
        }

        slots = []

        # --------------------------
        # BOUCLE SEMAINE PAR SEMAINE
        # --------------------------
        for week_idx in range(nb_semaines):

            phase = phases_by_week[week_idx]

            # --------------------------
            # BOUCLE JOUR PAR JOUR
            # --------------------------
            for i, jour in enumerate(jours):

                slot_date = first_dates[jour] + timedelta(weeks=week_idx)
                intensity_tag = pattern[i % len(pattern)]

                seance = _choose_seance_for_slot(
                    seances_types=seances_types,
                    phase=phase,
                    intensity_tag=intensity_tag,
                    jour=jour,
                )

                slot_id = f"{record_id}__S{week_idx+1}__{jour}"

                if seance is None:
                    slot = {
                        "semaine": week_idx + 1,
                        "jour_sem": jour,
                        "date_cible": slot_date.isoformat(),
                        "phase": phase,
                        "categorie_moteur": None,
                        "charge_coeff": None,
                        "allure_dominante": None,
                        "type_seance_nom": None,
                        "seance_type_id": None,
                        "status": "planned",
                        "slot_id": slot_id,
                    }
                else:
                    slot = {
                        "semaine": week_idx + 1,
                        "jour_sem": jour,
                        "date_cible": slot_date.isoformat(),
                        "phase": phase,
                        "categorie_moteur": seance.categorie_moteur,
                        "charge_coeff": seance.charge_coeff,
                        "allure_dominante": seance.allure_dominante,
                        "type_seance_nom": seance.nom,
                        "seance_type_id": seance.id,
                        "status": "planned",
                        "slot_id": slot_id,
                    }

                slots.append(slot)

        return InternalResult.ok(
            data={
                "meta": {
                    "nb_semaines": nb_semaines,
                    "date_debut_plan": date_debut_plan.isoformat(),
                    "date_fin_plan": date_objectif.isoformat(),
                },
                "slots": slots,
            },
            message="SCN_2 terminé (slots générés)",
            source="SCN_2",
        )

    except Exception as e:
        log_error(f"[SCN_2] Erreur inattendue : {e}")
        return InternalResult.error(
            message=f"EXCEPTION: {e}",
            data={},
            source="SCN_2",
            context=context
        )


