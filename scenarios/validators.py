# ============================================================
# validators.py — Validations techniques de bas niveau
# SOCLE : utilisé par SCN_0a (Validation & Normalisation)
# ============================================================

from typing import List
from services.airtable_fields import ATFIELDS

# Jours autorisés (SOCLE)
VALID_JOURS = [
    "Lundi", "Mardi", "Mercredi", "Jeudi",
    "Vendredi", "Samedi", "Dimanche"
]

# Modes autorisés (SOCLE simple, pas métier)
VALID_MODES = ["Running", "Vitalité", "Kids", "Hyrox"]


# ============================================================
# VALIDATE REQUIRED FIELDS
# ============================================================
def validate_required_fields(record: dict) -> List[str]:
    """
    Valide la présence des champs indispensables.
    Pure validation technique, aucun métier.
    """
    errors = []
    fields = record.get("fields", {})

    required = [
        ATFIELDS.COU_MODE,
        ATFIELDS.COU_NIVEAU_NORMALISE,
        ATFIELDS.COU_OBJECTIF_NORMALISE,
    ]

    for key in required:
        if key not in fields or fields[key] in (None, "", []):
            errors.append(f"Champ obligatoire manquant: {key}")

    return errors


# ============================================================
# VALIDATE MODE
# ============================================================
def validate_mode(record: dict) -> List[str]:
    """
    Vérifie que le mode est lisible et conforme
    aux valeurs minimales attendues (sans métier).
    """
    errors = []
    fields = record.get("fields", {})

    raw = fields.get(ATFIELDS.COU_MODE)
    if not raw:
        return errors  # handled in required_fields

    mode = str(raw).strip()

    # Normalisation légère (pas métier)
    if "Running" in mode:
        mode_norm = "Running"
    elif "Vital" in mode:
        mode_norm = "Vitalité"
    elif "Kid" in mode:
        mode_norm = "Kids"
    elif "Hyrox" in mode or "DEKA" in mode:
        mode_norm = "Hyrox"
    else:
        mode_norm = mode

    if mode_norm not in VALID_MODES:
        errors.append(f"Mode invalide: {mode}")

    return errors


# ============================================================
# VALIDATE NIVEAU
# ============================================================
def validate_niveau(record: dict) -> List[str]:
    """
    S'assure que le niveau normalisé est présent et cohérent.
    """
    errors = []
    fields = record.get("fields", {})

    raw = fields.get(ATFIELDS.COU_NIVEAU_NORMALISE)
    if not raw:
        return errors  # handled in required_fields

    # Pas de métier, juste un contrôle technique
    niveau = str(raw).strip()
    if niveau == "":
        errors.append("Niveau invalide (vide)")

    return errors


# ============================================================
# VALIDATE OBJECTIF
# ============================================================
def validate_objectif(record: dict) -> List[str]:
    """
    Vérification très simple de l'objectif normalisé.
    (SCN_0c fera la validation métier réelle)
    """
    errors = []
    fields = record.get("fields", {})

    raw = fields.get(ATFIELDS.COU_OBJECTIF_NORMALISE)
    if not raw:
        return errors

    objectif = str(raw).strip()
    if objectif == "":
        errors.append("Objectif invalide (vide)")

    return errors


# ============================================================
# VALIDATE JOURS
# ============================================================
def validate_jours(record: dict) -> List[str]:
    """
    Vérifie que le champ jours est une liste,
    et que tous les jours appartiennent aux 7 jours standard.
    Aucune logique métier ici, seulement syntaxique.
    """
    errors = []
    fields = record.get("fields", {})

    jours_raw = fields.get(ATFIELDS.COU_JOURS_DISPO)
    if jours_raw is None:
        return errors  # pas obligatoire dans SCN_0a

    # Doit être une liste
    if not isinstance(jours_raw, list):
        errors.append("Le champ jours doit être une liste.")
        return errors

    # Doit contenir uniquement des jours valides
    invalid = [j for j in jours_raw if j not in VALID_JOURS]
    if invalid:
        errors.append(f"Jours invalides : {invalid}")

    return errors


# ============================================================
# VALIDATE DATE OBJECTIF (syntaxe uniquement)
# ============================================================
def validate_date_objectif(record: dict) -> List[str]:
    """
    Vérification minimaliste : format non vide.
    Le parsing réel sera fait dans SCN_0a.
    """
    errors = []
    fields = record.get("fields", {})

    raw = fields.get(ATFIELDS.COU_DATE_COURSE)
    if not raw:
        return errors  # pas obligatoire dans tous les cas

    if not isinstance(raw, str):
        errors.append("La date objectif doit être une chaîne.")

    return errors


# ============================================================
# ENTRY POINT — VALIDATE ALL
# ============================================================
def run_all_validations(record: dict) -> List[str]:
    """
    Combine toutes les validations techniques.
    SCN_0a ne doit appeler qu'une seule fonction.
    """
    errors = []
    errors.extend(validate_required_fields(record))
    errors.extend(validate_mode(record))
    errors.extend(validate_niveau(record))
    errors.extend(validate_objectif(record))
    errors.extend(validate_jours(record))
    errors.extend(validate_date_objectif(record))

    return errors
