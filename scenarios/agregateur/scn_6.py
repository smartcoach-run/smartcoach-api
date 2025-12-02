# ================================================================
#  SCN_6 — Génération des séances à partir de la structure SCN_1
#  Version 100% alignée avec Airtable_fields + Airtable_tables
#  Compatible VDOT_reference.csv et 📘 Séances types.csv
# ================================================================

from typing import List, Dict, Any, Optional

from core.internal_result import InternalResult
from core.context import SmartCoachContext
from core.utils.logger import get_logger

from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES
from services.airtable_fields import ATFIELDS

log = get_logger("SCN_6")


# ================================================================
# Helpers Airtable
# ================================================================

def load_vdot_row(vdot_value: int) -> Optional[Dict[str, Any]]:
    """
    Charge la ligne de VDOT correspondant à vdot_value
    depuis la table VDOT_reference.
    """
    service = AirtableService()
    service.set_table(ATABLES.VDOT_REFERENCE)

    formula = f"{{VDOT}} = {vdot_value}"
    records = service.list_records(formula=formula)

    if not records:
        log.warning(f"SCN_6 → aucune ligne VDOT pour valeur={vdot_value}")
        return None

    return records[0].get("fields", {})


def load_templates() -> List[Dict[str, Any]]:
    """
    Charge tous les modèles depuis 📘 Séances types.
    """
    service = AirtableService()
    service.set_table(ATABLES.SEANCES_TYPES)

    records = service.list_records()
    templates = [r.get("fields", {}) for r in records]

    log.info(f"SCN_6 → {len(templates)} séances types chargées.")
    return templates


# ================================================================
# Mapping phase → type logique (Option B)
# ================================================================

def determine_code(slot: Dict[str, Any], phase_label: str, niveau: str, objectif: str) -> str:
    """
    Détermine le code interne (E, T, I, LONG, SP10K...) selon :
      - phase,
      - jour relatif,
      - niveau,
      - distance.
    """
    jr = slot.get("jour_relatif")

    # --- PHASE BASE ---
    if "Base" in phase_label:
        return {1: "E", 2: "TECH", 3: "ELD"}.get(jr, "E")

    # --- PHASE DÉVELOPPEMENT ---
    if "Développement" in phase_label:
        return {1: "T", 2: "I", 3: "LONG"}.get(jr, "E")

    # --- PHASE SPÉCIFIQUE ---
    if "Spécifique" in phase_label or "Spé" in phase_label:
        if "10" in objectif:
            return "SP10K"
        if "21" in objectif:
            return "SP21K"
        if "42" in objectif:
            return "SP42K"
        return "SPGEN"

    # --- PHASE AFFÛTAGE ---
    if "Affûtage" in phase_label:
        return {1: "E_COURT", 2: "RAPPEL", 3: "E_TRES_COURT"}.get(jr, "E")

    return "E"


# ================================================================
# Sélection template
# ================================================================

def match_template(
    templates: List[Dict[str, Any]],
    code: str,
    phase_label: str,
    niveau: str,
    objectif: str,
) -> Optional[Dict[str, Any]]:
    """
    Sélectionne le template correspondant au code + niveau + objectif + phase.
    Champs utilisés (validés dans CSV) :
      - Clé technique
      - Phase cible
      - Distance cible
      - Niveau cible
    """
    candidates = []

    for tpl in templates:
        tpl_code = tpl.get("Clé technique")
        tpl_phase = tpl.get("Phase cible", "Any")
        tpl_dist = tpl.get("Distance cible", "Générique")
        tpl_niveau = tpl.get("Niveau cible", "Tous")

        if tpl_code != code:
            continue

        if tpl_phase not in ("Any", phase_label):
            continue

        if tpl_dist not in ("Générique", objectif):
            continue

        if tpl_niveau not in ("Tous", niveau):
            continue

        candidates.append(tpl)

    if not candidates:
        log.warning(
            f"SCN_6 → Aucun template pour code={code}, phase={phase_label}, "
            f"niveau={niveau}, dist={objectif}"
        )
        return None

    return candidates[0]


# ================================================================
# Construction séance
# ================================================================

def build_session(
    slot: Dict[str, Any],
    tpl: Dict[str, Any],
    vdot: Dict[str, Any],
    phase_label: str,
) -> Dict[str, Any]:
    """
    Assemble la séance finale (sans calcul distance/durée pour V1).
    """
    return {
        "slot_id": slot.get("slot_id"),
        "semaine": slot.get("semaine"),
        "jour": slot.get("jour"),
        "phase": phase_label,
        "type": tpl.get("Label public"),
        "echauffement": tpl.get("Échauffement"),
        "corps": tpl.get("Corps"),
        "retour": tpl.get("Retour au calme"),
        "allures": {
            "E": vdot.get("E_min_km"),
            "M": vdot.get("M_min_km"),
            "T": vdot.get("T_min_km"),
            "I": vdot.get("I_min_km"),
            "R": vdot.get("R_min_km"),
        },
        "distance_km": None,
        "duree_min": None,
    }


# ================================================================
# SCN_6 — Fonction principale
# ================================================================

def run_scn_6(context: SmartCoachContext) -> InternalResult:
    """
    SCN_6 : génère toutes les séances du plan.
    """
    log.info("SCN_6 → Démarrage")

    # --- 1) vérifier slots + phases ---
    slots = context.slots
    phases = context.phases
    if not slots or not phases:
        return InternalResult.make_error(
            "SCN_6 → SCN_1 non exécuté : slots/phases manquants.",
            source="SCN_6",
        )

    record = context.record_raw.get("fields", {})
    niveau = record.get("Niveau_normalisé") or record.get("Niveau_mesuré")
    objectif = record.get("Objectif_normalisé") or record.get("Objectif_distance")

    # --- 2) VDOT ---
    vdot_user = record.get("VDOT_utilisé") or record.get("f_VDOT_ref")
    if isinstance(vdot_user, list):
        vdot_user = vdot_user[0]

    vdot_row = load_vdot_row(int(vdot_user))
    if not vdot_row:
        return InternalResult.make_error(
            f"SCN_6 → impossible de charger VDOT {vdot_user}",
            source="SCN_6",
        )

    # --- 3) Templates ---
    templates = load_templates()
    if not templates:
        return InternalResult.make_error(
            "SCN_6 → aucun modèle de séance disponible.",
            source="SCN_6",
        )

    # Mapping semaine → phase
    phase_by_week = {p["semaine"]: p["phase"] for p in phases}

    all_sessions = []

    # --- 4) Boucle principale ---
    for week_block in slots:
        semaine = week_block["semaine"]
        phase_label = phase_by_week.get(semaine, "Base")

        for s in week_block["slots"]:
            slot = {
                "semaine": semaine,
                "jour": s["jour"],
                "jour_relatif": s["jour_relatif"],
                "slot_id": s["slot_id"],
            }

            # a) déterminer code interne
            code = determine_code(slot, phase_label, niveau, objectif)

            # b) choisir template
            tpl = match_template(templates, code, phase_label, niveau, objectif)
            if not tpl:
                continue

            # c) construire séance
            session = build_session(slot, tpl, vdot_row, phase_label)
            all_sessions.append(session)

    if not all_sessions:
        return InternalResult.make_error(
            "SCN_6 → aucune séance générée.",
            source="SCN_6",
        )

    log.info(f"SCN_6 → Terminé ({len(all_sessions)} séances générées)")

    return InternalResult.make_success(
        message="SCN_6 terminé avec succès",
        data={
            "nb_seances": len(all_sessions),
            "seances": all_sessions,
        },
        context=context,
        source="SCN_6",
    )
