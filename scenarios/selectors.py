# scenarios/selectors.py
# ============================================================
# Sélecteurs communs aux scénarios SmartCoach :
#  - normalisation des jours
#  - construction Step3 Running (jours retenus + repos)
#  - Step4 structure brute Running
#  - Step5 phases + progression
#  - Step6 sélection modèles
# ============================================================

from typing import List, Dict, Any, Optional
from itertools import combinations

from services.airtable_fields import ATFIELDS
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES
from scenarios.validators import _compute_phases_for_objectif
from core.utils.logger import log_info

# === PATCH anti-warnings (2025-12) ===
# Ces variables sont héritées d'un ancien moteur v0.2/v0.3.
# Elles n'ont plus de rôle actif mais certaines fonctions les référencent encore.
# On les définit ici pour éviter les warnings Pylance sans casser la rétrocompatibilité.

semaine_type = None
jours_proposes = None
chosen = None
days_added = None
total_weeks = None
phases = None
objectif = None

# ------------------------------------------------------------
# Ordre canonique simple
# ------------------------------------------------------------
DAYS_ORDER = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
ORDER_MAP = {d: i for i, d in enumerate(DAYS_ORDER)}


# ------------------------------------------------------------
# Normalisation : transforme [" dimanche ", "mardi"] → ["Dimanche", "Mardi"]
# ------------------------------------------------------------
def _normalize_days_list(raw_days: Any) -> List[str]:
    if not raw_days:
        return []
    normalized = []
    for d in raw_days:
        if not isinstance(d, str):
            continue
        d_clean = d.strip().capitalize()
        for ref in DAYS_ORDER:
            if d_clean.lower() == ref.lower():
                normalized.append(ref)
                break
    return normalized


# ------------------------------------------------------------
# LOGIQUE D'OPTIMISATION DES JOURS AVEC REPOS (STEP3)
# ------------------------------------------------------------
def _optimize_days_with_rest(  
    user_days: List[str],
    proposed_days: List[str],
    jours_final: int,
) -> List[str]:
    """
    Version SOCLE v4
    - hard rule zéro consécutif (si possible)
    - exception Dimanche → Lundi (considéré non-consécutif)
    - priorité user_days
    - priorité proposed_days (Airtable)
    - pool minimal + optimisation early-stop
    """
    log_info("🔥 _optimize_days_with_rest → VERSION SOCLE V4 ACTIVÉE", module="DEBUG")
    # Pool : union user + proposed
    pool = list(dict.fromkeys(
        sorted(set(user_days) | set(proposed_days), key=lambda d: ORDER_MAP[d])
    ))

    # On complète TOUJOURS jusqu'à avoir toute la semaine disponible
    for d in DAYS_ORDER:
        if d not in pool:
            pool.append(d)

    # ---------------------------
    # Fonction consécutif SOCLE
    # ---------------------------
    def count_consecutive(ordered: List[str]) -> int:
        consec = 0
        for i in range(len(ordered) - 1):
            d1, d2 = ordered[i], ordered[i+1]

            # Exception SOCLE
            if d1 == "Dimanche" and d2 == "Lundi":
                continue

            # Cas normal
            if ORDER_MAP[d2] - ORDER_MAP[d1] == 1:
                consec += 1

        return consec

    # ---------------------------
    # HARD RULE : zéro consécutif
    # ---------------------------
    non_consec = []
    combos = combinations(pool, jours_final)

    for combo in combos:
        ordered = sorted(combo, key=lambda d: ORDER_MAP[d])
        if count_consecutive(ordered) == 0:
            non_consec.append(ordered)

    if non_consec:
        # 1) privilégier ceux qui respectent tous les jours user
        for c in non_consec:
            if set(user_days).issubset(c):
                return c

        # 2) sinon premier stable
        return non_consec[0]

    # ---------------------------
    # Sinon scoring SOCLE
    # ---------------------------
    def score(combo: List[str]):
        combo_s = set(combo)
        ordered = sorted(combo, key=lambda d: ORDER_MAP[d])

        consec = count_consecutive(ordered)
        missing_user = len(set(user_days) - combo_s)
        missing_prop = len(set(proposed_days) - combo_s)
        extra = len([d for d in ordered if d not in user_days and d not in proposed_days])
        start_idx = ORDER_MAP[ordered[0]]

        return (
            consec * 100,
            missing_user * 50,
            missing_prop * 30,
            extra * 10,
            start_idx,
        )

    best = None
    best_score = None

    for combo in combinations(pool, jours_final):
        s = score(combo)
        if best_score is None or s < best_score:
            best_score = s
            best = list(combo)

    # Log de contrôle
    log_info(
    f"DEBUG Step3 → pool={pool}",
    module="SCN_1",)

    return sorted(best, key=lambda d: ORDER_MAP[d])

# ------------------------------------------------------------
# STEP3 – Sélection des jours Running finalisés
# ------------------------------------------------------------
# ⚠️ DEPRECATED — NE PLUS UTILISER
# Cette version historique de Step3 ne doit plus être appelée.
# Le Step3 canonique est dans builders.py (SCN_1).
def build_step3_running(record: Dict[str, Any], step2_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Étape 3 – Sélection des jours & phases pour le mode Running.

    Objectifs SOCLE :
    - Ne JAMAIS retirer un jour saisi par l'utilisateur.
    - Compléter avec les jours_proposés (REF_JOURS) puis le reste de la semaine si besoin.
    - Minimiser les jours consécutifs (repos prioritaire).
    - Produire une structure propre et stable pour Step4.
    """

    fields = record.get("fields", {})

    # 1) JOURS UTILISATEUR (normalisés)
    jours_user_raw = fields.get(ATFIELDS.COU_JOURS_DISPO)
    user_days = _normalize_days_list(jours_user_raw)

    # 2) NOMBRE FINAL DE JOURS
    #    - Base : jours_final de Step2 (ou jours_user)
    #    - Contrainte SOCLE : JAMAIS moins que le nombre de jours saisis.
    jours_final_step2 = step2_data.get("jours_final") or step2_data.get("jours_user")
    if not isinstance(jours_final_step2, int) or jours_final_step2 <= 0:
        jours_final_step2 = len(user_days) if user_days else 2

    nb_user_days = len(user_days)
    if nb_user_days > 0 and jours_final_step2 < nb_user_days:
        # On ne punit pas : on ajuste vers le haut pour garder tous les jours saisis.
        log_info(
            f"STEP3 → ajustement jours_final de {jours_final_step2} à {nb_user_days} "
            f"pour conserver tous les jours utilisateur.",
            module="SCN_1",
        )
        jours_final = nb_user_days
    else:
        jours_final = jours_final_step2

    # 3) JOURS PROPOSÉS (REF_JOURS)
    jours_proposes_raw = step2_data.get("jours_proposes") or []
    proposed_days = _normalize_days_list(jours_proposes_raw)

    # --------------------------------------------
    # 4) NB DE JOURS CIBLE = modèle (semaine-type)
    # --------------------------------------------
    meta = semaine_type.get("meta", {}) if semaine_type else {}
    nb_jours_modele: int | None = meta.get("nb_jours")
    if not nb_jours_modele:
        nb_jours_modele = len(jours_proposes) or len(user_days)

    # --------------------------------------------
    # 5) OPTIMISATION : on repart de zéro
    #    -> on se base sur :
    #       - les jours utilisateur
    #       - les jours proposés par le modèle
    #       - nb_jours_modele (ex. 3 pour 10K Reprise)
    # --------------------------------------------
    chosen_days, debug = _optimize_days_with_rest(
        user_days=user_days,
        jours_proposes=jours_proposes,
        nb_jours_min=nb_jours_modele,
        nb_jours_max=nb_jours_modele,
        strict_candidates=True,
    )

    # Jours ajoutés par rapport à la saisie
    jours_supplementaires = [j for j in chosen_days if j not in user_days]

    # Drain de sécurité : si pour une raison quelconque on obtient 0 jour,
    # on retombe sur les jours utilisateur.
    if not chosen_days:
        chosen_days = list(user_days)
        jours_supplementaires = []


    # 6) LOG CONTRÔLE
    log_info(
        f"SCN_1/Step3 → user_days={user_days}, jours_final={jours_final}, "
        f"chosen={chosen}, days_added={days_added}, total_weeks={total_weeks}",
        module="SCN_1",
    )
    log_info(
        f"DEBUG Step3 → user_days={user_days}, jours_final={jours_final}",
        module="SCN_1",
    )
    log_info(
        f"DEBUG Step3 → proposed_days={proposed_days}",
        module="SCN_1",
    )

    # 7) SORTIE STANDARDISÉE POUR STEP4
    # 0) PRIORITÉ : si Step2 (SCN_0b) a déjà calculé les jours → on les réutilise
    jours_retenus_step2 = step2_data.get("jours_retenus")
    # PATCH : si SCN_0b a produit des jours optimisés, on les récupère
    scn0b_output = step2_data.get("jours_result", {})
    jours_optimises = scn0b_output.get("jours_valides")

    if jours_optimises:
        chosen_days = _normalize_days_list(jours_optimises)
    else:
        chosen_days = _normalize_days_list(jours_retenus_step2)

    if jours_retenus_step2:
        chosen_days = _normalize_days_list(jours_retenus_step2)

        log_info(
            f"STEP3 → override : jours_retenus provenant de Step2 = {chosen_days}",
            module="SCN_1",
        )

        # On renvoie directement la sortie standard Step3
        return {
            "status": "ok",
            "user_days": chosen_days,                # car rang1 déjà géré par SCN_0b
            "jours_final": len(chosen_days),
            "jours_retenus": chosen_days,
            "days_added": [],                        # SCN_0b les a déjà ajoutés
            "jours_proposes": step2_data.get("jours_proposes", []),
            "phases": phases,
            "plan_distance": objectif,
            "plan_nb_semaines": total_weeks,
        }

# ------------------------------------------------------------
# STEP4 – Construction brute des semaines Running
# ------------------------------------------------------------
def build_step4_running(
    distance: str,
    nb_semaines: int,
    jours_retenus: List[str],
) -> Dict[str, Any]:
    """
    Étape 4 – Construction du squelette hebdomadaire Running.

    Objectifs SOCLE :
    - Construire une structure de semaines propre, déterministe et simple.
    - Associer à chaque jour un jour_relatif stable (1..N selon l'ordre canonique).
    - Ne PAS modifier l'ordre logique des jours transmis par Step3.
    """

    # 1) Normalisation + tri canonique
    normalized_days = _normalize_days_list(jours_retenus)
    ordered_days = sorted(normalized_days, key=lambda d: ORDER_MAP[d])

    # 2) jours_relatifs : mapping jour → index relatif dans la semaine
    jours_relatifs = {j: i + 1 for i, j in enumerate(ordered_days)}

    log_info(
        f"STEP4 → jours_retenus={ordered_days}, jours_relatifs={jours_relatifs}, "
        f"nb_semaines={nb_semaines}, distance={distance}",
        module="SCN_1",
    )

    # 3) Construction des semaines
    weeks: List[Dict[str, Any]] = []
    for w in range(1, nb_semaines + 1):
        slots = [
            {
                "jour": j,
                "jour_relatif": jours_relatifs[j],
            }
            for j in ordered_days
        ]

        weeks.append(
            {
                "semaine": w,
                "phase": None,         # rempli en Step5
                "phase_index": None,   # rempli en Step5
                "slots": slots,
            }
        )

    # 4) Payload Step4
    return {
        "status": "ok",
        "plan_distance": distance,
        "plan_nb_semaines": nb_semaines,
        "jours_retenus": ordered_days,
        "jours_relatifs": jours_relatifs,
        "weeks": weeks,
    }

# ------------------------------------------------------------
# STEP5 – Application des phases + progression
# ------------------------------------------------------------
def apply_phases_and_progression(weeks: List[Dict[str, Any]], phases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    expanded = []
    for ph in phases:
        expanded += [ph["nom"]] * ph["semaines"]

    total = len(weeks)
    min_load = 0.30
    max_load = 0.85
    load_step = (max_load - min_load) / max(total-1, 1)

    def compute_load(i): return round(min_load + i * load_step, 3)

    enriched = []
    for i, w in enumerate(weeks):

        phase_name = expanded[i] if i < len(expanded) else None

        # index dans la phase
        phase_index = None
        if phase_name:
            offset = 0
            for ph in phases:
                if ph["nom"] == phase_name:
                    break
                offset += ph["semaines"]
            phase_index = i - offset + 1

        enriched.append({
            **w,
            "phase": phase_name,
            "phase_index": phase_index,
            "charge_pct": compute_load(i),
        })

    return enriched


# ------------------------------------------------------------
# STEP6 – Récupération & attribution des modèles de séances
# ------------------------------------------------------------
def fetch_seances_types() -> list:
    service = AirtableService()
    records = service.list_all(ATABLES.SEANCES_TYPES)
    log_info(f"STEP6 → {len(records)} séances types chargées", module="SCN_1")
    return records


def select_model_for_slot(slot: dict, week_phase: str, vdot: int, seances_types: list):
    candidates = []
    for rec in seances_types:
        f = rec["fields"]

        # Phase
        if f.get("Phase cible") != week_phase:
            continue

        # VDOT
        v_min = f.get("VDOT_min")
        v_max = f.get("VDOT_max")
        if (v_min is not None and vdot < v_min) or (v_max is not None and vdot > v_max):
            continue

        candidates.append(f)

    return candidates[0] if candidates else None


def apply_models_to_weeks(weeks: list, vdot: Optional[int] = None):

    if vdot is None:
        vdot = 38  # fallback

    seances_types = fetch_seances_types()

    enriched = []
    for w in weeks:
        new_slots = []
        for slot in w.get("slots", []):
            slot["model"] = select_model_for_slot(
                slot=slot,
                week_phase=w["phase"],
                vdot=vdot,
                seances_types=seances_types,
            )
            new_slots.append(slot)

        enriched.append({**w, "slots": new_slots})

    return enriched