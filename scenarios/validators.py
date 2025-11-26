# scenarios/validators.py

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pyairtable import Table

from services.airtable_fields import ATFIELDS
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES
from core.utils.logger import log_info, log_warning, log_error


@dataclass
class Step2Result:
    """
    Résultat standardisé de l'étape 2 pour SCN_1 (mode Running).

    Structure JSON (Option A – compacte & Make-friendly) :

    {
      "status": "ok" | "error" | "warning",
      "blocking": true | false,
      "errors": [
        { "code": "ERR_JOURS_MIN", "message": "...", "field": "jours" }
      ],
      "warnings": [
        { "code": "WARN_REF_JOURS_MISSING", "message": "...", "field": "Nb_jours_min" }
      ],
      "data": {
        "mode": "Running",
        "niveau": "Reprise",
        "objectif": "10K",
        "jours_user": 2,
        "jours_min": 3,
        "jours_max": 5,
        "jours_final": 3,
        "ajustement_necessaire": true,
        "jours_proposes": ["Mardi", "Jeudi", "Dimanche"],
        "commentaire_coach": "On garde un rythme doux et régulier 🙂"
      }
    }
    """
    status: str = "ok"
    blocking: bool = False
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, code: str, message: str, field: Optional[str] = None) -> None:
        self.errors.append(
            {
                "code": code,
                "message": message,
                "field": field,
            }
        )
        self.status = "error"

    def add_warning(self, code: str, message: str, field: Optional[str] = None) -> None:
        self.warnings.append(
            {
                "code": code,
                "message": message,
                "field": field,
            }
        )
        if self.status == "ok":
            self.status = "warning"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "blocking": self.blocking,
            "errors": self.errors,
            "warnings": self.warnings,
            "data": self.data,
        }


def _safe_get_int(value: Any) -> Optional[int]:
    """Convertit proprement en int ou renvoie None."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _fetch_ref_jours(
    mode: Optional[str],
    niveau_norm: Optional[str],
    objectif_norm: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    Va chercher la ligne correspondante dans la table ⚖️ Référence Jours
    en fonction du triplet (Mode, Niveau_normalisé, Objectif_normalisé).

    Retourne le dict `fields` du record trouvé ou None.
    """
    if not mode or not niveau_norm or not objectif_norm:
        log_warning(
            "REF_JOURS → clés incomplètes (mode/niveau/objectif manquants), impossible de chercher une référence.",
            module="SCN_1",
        )
        return None

    try:
        service = AirtableService()
    except Exception as e:
        log_error(f"REF_JOURS → impossible d'initialiser AirtableService : {e}", module="SCN_1")
        return None

    table = Table(service.api_key, service.base_id, ATABLES.REF_JOURS)

    # AND({Mode}='Running',{Niveau}='Reprise',{Objectif}='10K')
    formula = (
        "AND("
        f"{{{ATFIELDS.RJ_MODE}}}='{mode}',"
        f"{{{ATFIELDS.RJ_NIVEAU}}}='{niveau_norm}',"
        f"{{{ATFIELDS.RJ_OBJECTIF}}}='{objectif_norm}'"
        ")"
    )

    log_info(f"REF_JOURS → recherche avec formula={formula}", module="SCN_1")

    try:
        records = table.all(formula=formula, max_records=2)
    except Exception as e:
        log_error(f"REF_JOURS → erreur lors de la requête Airtable : {e}", module="SCN_1")
        return None

    if not records:
        log_warning(
            f"REF_JOURS → aucune ligne trouvée pour mode={mode}, niveau={niveau_norm}, objectif={objectif_norm}",
            module="SCN_1",
        )
        return None

    if len(records) > 1:
        log_warning(
            f"REF_JOURS → plusieurs lignes trouvées pour mode={mode}, niveau={niveau_norm}, objectif={objectif_norm}. "
            "On utilise la première.",
            module="SCN_1",
        )

    return records[0].get("fields", {})


def validate_running_step2(record: Dict[str, Any]) -> Step2Result:
    """
    Étape 2 – Validations & cohérences pour le mode Running.

    🔹 Objectif :
    - Valider le nombre de jours disponibles.
    - Charger les bornes min/max et jours proposés depuis ⚖️ REF_JOURS
      en fonction de (Mode, Niveau_normalisé, Objectif_normalisé).
    - Appliquer les règles SmartCoach : ajustement automatique, jamais de punition.
    - Retourner une structure compacte Make-ready.
    """
    step2 = Step2Result()
    fields = record.get("fields", {})

    # 1) Lecture des champs de base (table Coureurs)
    mode = fields.get(ATFIELDS.COU_MODE)
    niveau = fields.get(ATFIELDS.COU_NIVEAU_NORMALISE)
    objectif = fields.get(ATFIELDS.COU_OBJECTIF_NORMALISE)

    jours_dispo_raw = fields.get(ATFIELDS.COU_JOURS_DISPO)

    # Fillout renvoie une liste de jours (["Vendredi", "Dimanche"])
    if isinstance(jours_dispo_raw, list):
        jours_dispo = len(jours_dispo_raw)
    else:
        jours_dispo = _safe_get_int(jours_dispo_raw)

    log_info(
        f"SCN_1/Step2 → mode={mode}, niveau={niveau}, objectif={objectif}, "
        f"jours_dispo_raw={jours_dispo_raw}, jours_dispo={jours_dispo}",
        module="SCN_1",
    )

    # Mode ≠ Running → aucune validation spécifique
    if mode and str(mode).lower() != "running":
        step2.data = {
            "mode": mode,
            "niveau": niveau,
            "objectif": objectif,
            "jours_user": jours_dispo_raw,
            "message": "Mode non Running : validations spécifiques désactivées.",
        }
        return step2

    # 2) Jours disponibles : cas invalide (vraiment)
    if jours_dispo is None or jours_dispo <= 0:
        msg = "Nombre de jours disponibles invalide ou non renseigné."
        log_warning(f"SCN_1/Step2 → {msg}", module="SCN_1")
        step2.add_error(
            code="ERR_JOURS_INVALIDES",
            message=msg,
            field=ATFIELDS.COU_JOURS_DISPO,
        )
        step2.blocking = True
        step2.data = {
            "mode": mode,
            "niveau": niveau,
            "objectif": objectif,
            "jours_user": jours_dispo_raw,
        }
        return step2

    # 3) Chargement de la référence REF_JOURS
    ref_fields = _fetch_ref_jours(mode, niveau, objectif)

    if not ref_fields:
        # On ne bloque pas, mais on signale : la config REF_JOURS n'est pas prête.
        msg = "Impossible de récupérer les valeurs de référence dans REF_JOURS."
        log_warning(f"SCN_1/Step2 → {msg}", module="SCN_1")
        step2.add_warning(
            code="WARN_REF_JOURS_MISSING",
            message=msg,
            field="REF_JOURS",
        )
        step2.data = {
            "mode": mode,
            "niveau": niveau,
            "objectif": objectif,
            "jours_user": jours_dispo,
            "jours_min": None,
            "jours_max": None,
            "jours_final": jours_dispo,
            "ajustement_necessaire": False,
            "jours_proposes": None,
            "commentaire_coach": None,
        }
        return step2

    # Extraction des valeurs de référence
    jours_min = _safe_get_int(ref_fields.get(ATFIELDS.RJ_NB_JOURS_MIN))
    jours_max = _safe_get_int(ref_fields.get(ATFIELDS.RJ_NB_JOURS_MAX))
    jours_proposes = ref_fields.get(ATFIELDS.RJ_JOURS_PROPOSES)
    commentaire_coach = ref_fields.get(ATFIELDS.RJ_COMMENTAIRE_COACH)

    if jours_min is None or jours_max is None:
        msg = "REF_JOURS présent mais Nb_jours_min / Nb_jours_max manquants ou invalides."
        log_warning(f"SCN_1/Step2 → {msg}", module="SCN_1")
        step2.add_warning(
            code="WARN_REF_JOURS_INCOMPLETE",
            message=msg,
            field=f"{ATFIELDS.RJ_NB_JOURS_MIN}/{ATFIELDS.RJ_NB_JOURS_MAX}",
        )
        step2.data = {
            "mode": mode,
            "niveau": niveau,
            "objectif": objectif,
            "jours_user": jours_dispo,
            "jours_min": jours_min,
            "jours_max": jours_max,
            "jours_final": jours_dispo,
            "ajustement_necessaire": False,
            "jours_proposes": jours_proposes,
            "commentaire_coach": commentaire_coach,
        }
        return step2

    # 4) Application des règles SmartCoach (ajustement doux, jamais punitif)
    ajustement_necessaire = False
    jours_final = jours_dispo

    if jours_dispo < jours_min:
        msg = (
            f"Tu avais choisi {jours_dispo} jour(s). "
            f"On t'accompagne sur {jours_min} jour(s) par semaine pour installer la routine 🌿"
        )
        step2.add_warning(
            code="WARN_JOURS_SOUS_MIN",
            message=msg,
            field=ATFIELDS.COU_JOURS_DISPO,
        )
        ajustement_necessaire = True
        jours_final = jours_min

    elif jours_dispo > jours_max:
        msg = (
            f"{jours_dispo} jours, c'est un rythme soutenu. "
            f"On adapte à {jours_max} jour(s) pour que ce soit confortable et régulier 👍"
        )
        step2.add_warning(
            code="WARN_JOURS_SUR_MAX",
            message=msg,
            field=ATFIELDS.COU_JOURS_DISPO,
        )
        ajustement_necessaire = True
        jours_final = jours_max

    # 5) Données Make-ready
    step2.data = {
        "mode": mode,
        "niveau": niveau,
        "objectif": objectif,
        "jours_user": jours_dispo,
        "jours_min": jours_min,
        "jours_max": jours_max,
        "jours_final": jours_final,
        "ajustement_necessaire": ajustement_necessaire,
        "jours_proposes": jours_proposes,
        "commentaire_coach": commentaire_coach,
    }

    return step2

# -------------------------------------------------------------------
# Étape 3 – Sélection des jours & phases (mode Running)
# -------------------------------------------------------------------

DAYS_ORDER = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _normalize_days_list(value: Any) -> List[str]:
    """Normalise un champ Airtable en liste de jours (toujours une liste de str)."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _compute_phases_for_objectif(objectif: Optional[str]) -> List[Dict[str, Any]]:
    """
    Renvoie une liste de phases en fonction de l'objectif normalisé.

    Par simplicité (v1 SOCLE) :
    - 5K  : 2 / 2 / 1
    - 10K : 3 / 3 / 1
    - Semi: 4 / 4 / 1
    - Marathon: 5 / 6 / 2
    - défaut: 3 / 3 / 1
    """
    obj = (objectif or "").lower()

    if "5" in obj and "k" in obj:
        base, constr, aff = 2, 2, 1
    elif "10" in obj and "k" in obj:
        base, constr, aff = 3, 3, 1
    elif "semi" in obj or "21" in obj:
        base, constr, aff = 4, 4, 1
    elif "marathon" in obj or "42" in obj:
        base, constr, aff = 5, 6, 2
    else:
        base, constr, aff = 3, 3, 1

    return [
        {"id": 1, "nom": "Base", "semaines": base},
        {"id": 2, "nom": "Construction", "semaines": constr},
        {"id": 3, "nom": "Affûtage", "semaines": aff},
    ]

def build_step3_running(record: Dict[str, Any], step2_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Étape 3 – Sélection des jours & phases pour le mode Running.
    Sortie alignée avec ce que Step4 attend.
    """

    fields = record.get("fields", {})

    # -------------------------------
    # 1) Extraction des jours user
    # -------------------------------
    jours_user_raw = fields.get(ATFIELDS.COU_JOURS_DISPO)
    user_days = _normalize_days_list(jours_user_raw)

    # -------------------------------
    # 2) Nombre de jours final ciblé
    # -------------------------------
    jours_final = step2_data.get("jours_final") or step2_data.get("jours_user")
    if not isinstance(jours_final, int) or jours_final <= 0:
        jours_final = len(user_days) if user_days else 2

    # -------------------------------
    # 3) Jours proposés par REF_JOURS
    # -------------------------------
    jours_proposes_raw = step2_data.get("jours_proposes") or []
    proposed_days = _normalize_days_list(jours_proposes_raw)

    # -------------------------------
    # 4) Construction des jours retenus (ordonnés)
    # -------------------------------
    chosen: List[str] = []

    # priorité user
    for d in DAYS_ORDER:
        if d in user_days and d not in chosen:
            chosen.append(d)

    # compléter avec jours proposés
    if len(chosen) < jours_final:
        missing = jours_final - len(chosen)
        for d in DAYS_ORDER:
            if d in proposed_days and d not in chosen:
                chosen.append(d)
                missing -= 1
                if missing == 0:
                    break

    # fallback
    if len(chosen) < jours_final:
        for d in user_days + proposed_days:
            if len(chosen) >= jours_final:
                break
            if d not in chosen:
                chosen.append(d)

    # réduire si trop
    if len(chosen) > jours_final:
        ordered = [d for d in DAYS_ORDER if d in chosen]
        chosen = ordered[:jours_final] if len(ordered) >= jours_final else chosen[:jours_final]

    days_added = [d for d in chosen if d not in user_days]

    # -------------------------------
    # 5) Phases complètes pour Step4
    # -------------------------------
    objectif = step2_data.get("objectif")
    phases = _compute_phases_for_objectif(objectif)

    # Nombre total de semaines = somme des semaines de chaque phase
    total_weeks = sum(ph.get("semaines", 0) for ph in phases)

    # -------------------------------
    # LOG
    # -------------------------------
    log_info(
        f"SCN_1/Step3 → user_days={user_days}, chosen={chosen}, days_added={days_added}",
        module="SCN_1",
    )

    # -------------------------------
    # 6) STRUCTURE DE SORTIE STANDARDISÉE
    # (CE QUE STEP4 ATTEND VRAIMENT)
    # -------------------------------
    return {
        "status": "ok",

        # NOTE : nom officiel attendu par Step4
        "jours_retenus": chosen,

        # Required by Step4
        "jours_final": jours_final,
        "plan_distance": objectif,
        "plan_nb_semaines": total_weeks,

        # phases au bon format
        "phases": phases
    }
