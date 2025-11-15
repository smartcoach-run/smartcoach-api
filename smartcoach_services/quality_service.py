# smartcoach_services/quality_service.py

from datetime import datetime


class QualityService:
    """
    Service de contrôle qualité (QC)
    Vérifie que les champs essentiels sont présents et correctement formatés.
    """

    @staticmethod
    def run(ctx):
        errors = []

        # --- 1) Email ---
        email = ctx.get("email")
        if not email or "@" not in email:
            errors.append("email invalide.")

        # --- 2) Prénom ---
        prenom = ctx.get("prenom")
        if not prenom or not isinstance(prenom, str):
            errors.append("Prénom manquant ou invalide.")

        # --- 3) Mode ---
        mode = ctx.get("mode")
        if not mode:
            errors.append("Champ requis manquant : mode")

        # --- 4) Objectif ---
        objectif = ctx.get("objectif")
        if not objectif:
            errors.append("Champ requis manquant : objectif")

        # --- 5) Date objectif / date_course ---
        date_objectif = ctx.get("date_objectif")
        if date_objectif:
            try:
                QualityService._parse_date(date_objectif)
            except Exception:
                errors.append("date_objectif n'est pas une date valide.")
        else:
            errors.append("date_objectif manquante.")

        # --- 6) Date début plan (calculée) ---
        date_debut_plan = ctx.get("date_debut_plan")
        if date_debut_plan:
            try:
                QualityService._parse_date(date_debut_plan)
            except Exception:
                errors.append("date_debut_plan n'est pas une date valide.")
        else:
            errors.append("date_debut_plan manquante.")

        return errors

    # --------------------------------------------------------------
    # 🔧 Parse LATEX DATES → gère : ISO, US, FR, format Airtable
    # --------------------------------------------------------------
    @staticmethod
    def _parse_date(value):
        """
        Supporte différents formats de dates Airtable.
        """
        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            # Airtable format typical: '2025-11-22T00:00:00.000Z'
            try:
                return datetime.fromisoformat(value.replace("Z", ""))
            except Exception:
                pass

            # FR format: "22/11/2025"
            try:
                return datetime.strptime(value, "%d/%m/%Y")
            except Exception:
                pass

            # US format: "2025-11-22"
            try:
                return datetime.strptime(value, "%Y-%m-%d")
            except Exception:
                pass

        raise ValueError("Invalid date format")