"""
validation_service.py
---------------------------------------------------------------------
Validation simple et robuste utilisée par SCN_1.

CONFORME :
- RCTC (aucun champ inventé)
- Manuel SmartCoach
- Story SCN_1

Objectif :
- Vérifier uniquement les formats basiques :
    - email
    - date valide
    - champs obligatoires

ATTENTION :
- Aucune règle métier ici
- Pas de QC avancé
- Pas d’accès Airtable
- Pas de dépendance complexe

SCN_1 décide quoi faire en cas d'erreur.
---------------------------------------------------------------------
"""

import re
from datetime import datetime


class ValidationService:

    # ----------------------------------------------------------
    # EMAIL
    # ----------------------------------------------------------
    EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z0-9]+$")

    def validate_email(self, email: str | None) -> bool:
        """
        Vérifie qu'un email est valide.
        Retourne True si valide, False sinon.
        """
        if not email:
            return False
        return bool(self.EMAIL_REGEX.match(email))

    # ----------------------------------------------------------
    # DATES
    # ----------------------------------------------------------
    def validate_date(self, value: str | None) -> bool:
        """
        Vérifie si une chaîne correspond à une date valide ISO AAAA-MM-JJ.

        Airtable envoie toujours les dates calculées ou saisies en ISO.
        Retourne True si la date est correcte.
        """
        if not value:
            return False
        try:
            datetime.fromisoformat(value)
            return True
        except Exception:
            return False

    # ----------------------------------------------------------
    # PRÉSENCE DES CHAMPS OBLIGATOIRES
    # ----------------------------------------------------------
    REQUIRED_FIELDS = [
        "Prénom",
        "Email",
        "Mode",
        "Niveau_normalisé",
        "Objectif_normalisé",
        "Jours disponibles",
        "date_course",                # RCTC
        "Date début plan (calculée)"  # RCTC
    ]

    def check_required(self, fields: dict) -> list[str]:
        """
        Vérifie la présence des champs obligatoires.
        Retourne une liste d'erreurs.

        Pas de blocage automatique : SCN_1 choisit quoi faire.
        """
        errors = []
        for key in self.REQUIRED_FIELDS:
            if fields.get(key) in (None, "", []):
                errors.append(f"Champ requis manquant : {key}")
        return errors

    # ----------------------------------------------------------
    # VALIDATION GLOBALE (utilisée par SCN_1)
    # ----------------------------------------------------------
    def validate_context(self, ctx: dict) -> list[str]:
        """
        Vérification simple du contexte enrichi SCN_1.
        Retourne une liste d'erreurs.
        Aucun arrêt automatique.
        """
        errors = []

        # Email
        if not self.validate_email(ctx.get("email")):
            errors.append("Email invalide.")

        # date_course
        if not self.validate_date(ctx.get("date_objectif")):
            errors.append("date_objectif n'est pas une date valide.")

        # date_debut_plan
        if not self.validate_date(ctx.get("date_debut_plan")):
            errors.append("date_debut_plan n'est pas une date valide.")

        return errors
