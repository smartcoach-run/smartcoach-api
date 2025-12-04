# ======================================================================
# SCN_2 : Génération des cibles par semaine / par séance (version expert)
# - S'appuie sur les résultats de SCN_1
# - Utilise (si dispo) les infos de 📘 Référentiel Niveaux déposées dans le contexte
# ======================================================================

from typing import Any, Dict, List, Optional

from core.internal_result import InternalResult
from core.context import SmartCoachContext as Context
from core.utils.logger import get_logger

log = get_logger(__name__)


# ----------------------------------------------------------------------
# Helpers pour extraire les infos du contexte
# ----------------------------------------------------------------------

def _get_record_fields(context: Context) -> Dict[str, Any]:
    """
    Récupère les fields Airtable bruts depuis record_raw.
    """
    record_raw = context.record_raw or {}
    if isinstance(record_raw, dict):
        return record_raw.get("fields", {})
    return {}


def _extract_vdot_info(context: Context) -> Dict[str, Optional[float]]:
    """
    Essaie de récupérer un VDOT de départ et un VDOT cible/utilisé
    à partir du contexte + record_raw.
    """
    fields = _get_record_fields(context)

    def _first(name: str) -> Optional[float]:
        v = fields.get(name)
        if isinstance(v, list) and v:
            v = v[0]
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    # Priorités :
    #  - d'abord ce que le socle aurait éventuellement déjà mis dans le contexte
    #  - sinon les champs du record Airtable
    vdot_initial = (
        context.get("vdot_initial")
        or _first("VDOT_initial")
        or _first("VDOT_moyen_LK")
        or _first("f_VDOT_ref")
    )
    vdot_target = (
        context.get("vdot_target")
        or _first("VDOT_utilisé")
        or _first("VDOT_cible")
        or vdot_initial
    )

    return {
        "initial": vdot_initial,
        "target": vdot_target,
    }


def _get_ref_niveau_constraints(context: Context) -> Dict[str, Any]:
    """
    Récupère les contraintes issues de 📘 Référentiel Niveaux,
    si elles ont été déposées dans le contexte (par ex via SCN_0c).

    Attendu dans context["ref_niveau"] (ou équivalent) quelque chose comme :
    {
        "Progression autorisée (%)": 80,
        "Volume min (km)": 20,
        "Volume max (km)": 45,
        "Message Coach": "..."
    }

    Si rien n'est dispo, on met des valeurs par défaut "safe".
    """
    ref_niveau = context.get("ref_niveau") or context.get("ref_niveau_data") or {}

    # Noms possibles des champs selon ta config
    prog_pct = (
        ref_niveau.get("Progression autorisée (%)")
        or ref_niveau.get("progression_autorisee_pct")
        or 100
    )
    vol_min = (
        ref_niveau.get("Volume min (km)")
        or ref_niveau.get("Volume_min_km")
        or 0
    )
    vol_max = (
        ref_niveau.get("Volume max (km)")
        or ref_niveau.get("Volume_max_km")
        or vol_min
    )

    try:
        prog_pct = float(prog_pct)
    except (TypeError, ValueError):
        prog_pct = 100.0

    try:
        vol_min = float(vol_min)
    except (TypeError, ValueError):
        vol_min = 0.0

    try:
        vol_max = float(vol_max)
    except (TypeError, ValueError):
        vol_max = vol_min
    if vol_max < vol_min:
        vol_max = vol_min

    return {
        "progression_pct": prog_pct,   # 0–100
        "volume_min": vol_min,         # km / semaine
        "volume_max": vol_max,         # km / semaine
        "raw": ref_niveau,
    }


# ----------------------------------------------------------------------
# Courbe de progression sur les semaines (0 → 1)
# ----------------------------------------------------------------------

def _build_progression_curve(
    phases_meta: List[Dict[str, Any]],
    nb_semaines: int,
) -> Dict[int, float]:
    """
    Construit un dict {semaine: pct_plan} entre 0 et 1
    à partir de step3["phases"] :
    [
      {
        "distance": "10K",
        "phase_cle": "Prépa générale",
        "ordre_phase": 1,
        "semaine_debut": 1,
        "semaine_fin": 5,
        "pct_debut": 0,
        "pct_fin": 0.55
      },
      ...
    ]
    """
    progression: Dict[int, float] = {}

    if not phases_meta:
        # fallback linéaire simple si on n'a pas de meta phases
        for w in range(1, nb_semaines + 1):
            progression[w] = (w - 1) / max(nb_semaines - 1, 1)
        return progression

    for phase in phases_meta:
        try:
            s_deb = int(phase.get("semaine_debut", 1))
            s_fin = int(phase.get("semaine_fin", nb_semaines))
            pct_deb = float(phase.get("pct_debut", 0.0))
            pct_fin = float(phase.get("pct_fin", 1.0))
        except (TypeError, ValueError):
            continue

        if s_deb > nb_semaines:
            continue
        s_fin = min(s_fin, nb_semaines)

        if s_fin <= s_deb:
            # phase sur 1 semaine : tout le monde à pct_deb
            progression[s_deb] = pct_deb
            continue

        span = s_fin - s_deb
        for w in range(s_deb, s_fin + 1):
            alpha = (w - s_deb) / span
            pct = pct_deb + alpha * (pct_fin - pct_deb)
            progression[w] = pct

    # Normalisation éventuelle (si jamais les pct ne couvrent pas 0→1)
    if progression:
        min_p = min(progression.values())
        max_p = max(progression.values())
        if max_p > min_p:
            for w in progression:
                progression[w] = (progression[w] - min_p) / (max_p - min_p)
        else:
            # tout égal => tout le monde à 0.5
            for w in progression:
                progression[w] = 0.5
    else:
        # sécurité : linéaire
        for w in range(1, nb_semaines + 1):
            progression[w] = (w - 1) / max(nb_semaines - 1, 1)

    return progression


# ----------------------------------------------------------------------
# Répartition du volume dans la semaine
# ----------------------------------------------------------------------

def _slot_weights(nb_seances: int) -> List[float]:
    """
    Retourne une répartition de charge par séance dans la semaine.
    Exemple pour 3 séances : EF / Quali / SL => [0.25, 0.30, 0.45]
    La somme fait toujours 1.
    """
    if nb_seances <= 0:
        return []

    if nb_seances == 1:
        return [1.0]
    if nb_seances == 2:
        return [0.45, 0.55]
    if nb_seances == 3:
        return [0.25, 0.30, 0.45]

    # Pour 4+ : on garde simple et on uniformise
    base = 1.0 / nb_seances
    return [base] * nb_seances


# ----------------------------------------------------------------------
# Fonction principale : SCN_2
# ----------------------------------------------------------------------

def run_scn_2(context: Context) -> InternalResult:
    """
    SCN_2 : à partir du travail de SCN_1, on génère :
      - une cible VDOT par semaine
      - un volume cible min / max par semaine
      - une répartition du volume par slot (Sx-Jy)

    Pré-requis (normalement remplis par SCN_1) :
      - context["plan_nb_semaines"]
      - context["slots"] : liste {semaine, slots: [{jour, jour_relatif, slot_id}, ...]}
      - context["phases"] : liste {semaine, phase, phase_index, slots: [...]}
      - context["step3"]["phases"] : meta-phases avec pct_debut / pct_fin
    """
    log.info("SCN_2 ▶ génération des cibles par semaine / séance (expert)")

    # ------------------------------------------------------------------
    # 0) Récup données nécessaires du contexte
    # ------------------------------------------------------------------
    record_norm: Dict[str, Any] = context.get("record_norm", {}) or {}
    step3: Dict[str, Any] = context.get("step3", {}) or {}

    # nb semaines
    nb_semaines = (
        context.get("plan_nb_semaines")
        or record_norm.get("duree_plan_calc")
        or record_norm.get("Durée_plan_calculée_sem")
    )
    try:
        nb_semaines = int(nb_semaines)
    except (TypeError, ValueError):
        nb_semaines = 0

    slots: List[Dict[str, Any]] = context.get("slots") or []
    phases_by_week: List[Dict[str, Any]] = context.get("phases") or []
    phases_meta: List[Dict[str, Any]] = step3.get("phases") or []

    if nb_semaines <= 0 or not slots:
        return InternalResult.make_error(
            message="SCN_2 : données structurelles manquantes (nb_semaines / slots).",
            data={
                "plan_nb_semaines": nb_semaines,
                "slots": slots,
                "phases": phases_by_week,
            },
            context=context,
            source="SCN_2",
        )

    # ------------------------------------------------------------------
    # 1) Progression globale 0→1 sur les semaines
    # ------------------------------------------------------------------
    progression_curve = _build_progression_curve(phases_meta, nb_semaines)

    # ------------------------------------------------------------------
    # 2) VDOT initial / cible + contraintes niveau
    # ------------------------------------------------------------------
    vdot_info = _extract_vdot_info(context)
    ref_niveau_constraints = _get_ref_niveau_constraints(context)

    vdot_initial = vdot_info.get("initial")
    vdot_target = vdot_info.get("target") or vdot_initial

    if vdot_initial is None:
        # On continue quand même mais on marquera vdot_cible=None
        log.warning("SCN_2 : VDOT initial introuvable, les cibles VDOT seront nulles.")

    if vdot_target is None:
        vdot_target = vdot_initial

    progression_pct_autorisee = ref_niveau_constraints["progression_pct"]  # 0–100
    progression_factor = max(0.0, min(progression_pct_autorisee / 100.0, 1.0))

    vol_min_ref = ref_niveau_constraints["volume_min"]
    vol_max_ref = ref_niveau_constraints["volume_max"]

    # ------------------------------------------------------------------
    # 3) Cibles par semaine
    # ------------------------------------------------------------------
    weeks_targets: List[Dict[str, Any]] = []
    # Debug compatible avec dict S1 → slots
    sample_key = next(iter(slots), None)
    log.info(f"[SCN_2] DEBUG slots type={type(slots)}, first_week={sample_key}")


    for semaine in range(1, nb_semaines + 1):
        pct_plan = progression_curve.get(semaine, 0.0)

        # Progression "effective" limitée par Progression autorisée (%)
        eff_pct = pct_plan * progression_factor

        if vdot_initial is not None and vdot_target is not None:
            vdot_semaine = vdot_initial + (vdot_target - vdot_initial) * eff_pct
        else:
            vdot_semaine = None

        # Volume : on part du principe que vol_min / vol_max réf correspondent
        # à la zone "haute" du plan, et on applique un facteur 0.4 → 1.0
        # (c'est volontairement simple, tu pourras ajuster la formule).
        volume_factor = 0.4 + 0.6 * pct_plan  # 40% au début → 100% à la fin
        volume_min_semaine = vol_min_ref * volume_factor
        volume_max_semaine = vol_max_ref * volume_factor

        # On récupère la phase courante (si dispo dans context["phases"])
        phase_info = next(
            (p for p in phases_by_week if p.get("semaine") == semaine),
            {},
        )
        phase_name = phase_info.get("phase")
        phase_index = phase_info.get("phase_index")

        weeks_targets.append(
            {
                "semaine": semaine,
                "phase": phase_name,
                "phase_index": phase_index,
                "pct_plan": pct_plan,
                "pct_plan_effectif": eff_pct,
                "vdot_cible": vdot_semaine,
                "volume_min_km": volume_min_semaine,
                "volume_max_km": volume_max_semaine,
            }
        )

    # ------------------------------------------------------------------
    # 4) Cibles par séance (slot) à partir des cibles hebdo
    # ------------------------------------------------------------------
    sessions_targets: List[Dict[str, Any]] = []

    # Construction d'un dict {semaine: week_target}
    week_target_by_num = {w["semaine"]: w for w in weeks_targets}

    # Adaptation au format dict : {"S1": {...}, "S2": {...}, ...}
    for week_key, week_block in slots.items():

        # Convertir la clé "S4" → 4
        try:
            semaine = int(week_key.replace("S", ""))
        except Exception:
            continue

        week_slots = week_block.get("slots", [])

        target_week = week_target_by_num.get(semaine)
        if not target_week:
            continue

        nb_seances = len(week_slots)
        if nb_seances <= 0:
            continue

        weights = _slot_weights(nb_seances)

        vol_min = target_week["volume_min_km"]
        vol_max = target_week["volume_max_km"]
        vdot_cible = target_week["vdot_cible"]
        phase_name = target_week["phase"]
        phase_index = target_week["phase_index"]

        for idx, slot in enumerate(week_slots):
            poids = weights[idx] if idx < len(weights) else 1.0 / nb_seances

            sessions_targets.append(
                {
                    "slot_id": slot.get("slot_id"),
                    "semaine": semaine,
                    "jour": slot.get("jour"),
                    "jour_relatif": slot.get("jour_relatif"),
                    "phase": phase_name,
                    "phase_index": phase_index,
                    "poids_semaine": poids,
                    "vdot_cible": vdot_cible,
                    "volume_min_km": vol_min * poids if vol_min is not None else None,
                    "volume_max_km": vol_max * poids if vol_max is not None else None,
                    "categorie_seance": None,
                    "type_seance_cle": None,
                }
            )

    # ------------------------------------------------------------------
    # 5) Update contexte + retour
    # ------------------------------------------------------------------
    context.update(
        {
            "weeks_targets": weeks_targets,
            "sessions_targets": sessions_targets,
            "vdot_planning": {
                "vdot_initial": vdot_initial,
                "vdot_target": vdot_target,
                "progression_pct_autorisee": progression_pct_autorisee,
            },
            "ref_niveau_constraints": ref_niveau_constraints,
        }
    )

    data = {
        "plan_nb_semaines": nb_semaines,
        "weeks_targets": weeks_targets,
        "sessions_targets": sessions_targets,
    }

    return InternalResult.ok(
        data=data,
        message="SCN_2 terminé avec succès (version expert)",
        context=context,
        source="SCN_2",
    )