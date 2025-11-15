# smartcoach_core/airtable_refs.py
# =====================================================
# Référentiel CENTRALISÉ des noms de tables Airtable
# Source unique de vérité pour tout SmartCoach
# =====================================================

class ATABLES:
    """
    Référentiel unique des tables Airtable utilisées dans SmartCoach.
    Toute modification de nom de table se fait ici.
    """

    SCENARIOS_VALIDATION = "🎛 Scénarios de validation"

    # 🔢 Référentiels
    REF_JOURS = "⚖️ Référence Jours"
    REF_VDOT = "VDOT_reference"
    REF_NIVEAUX = "📘 Référentiel Niveaux"
    REF_CATEGORIES_SEANCES = "🎛️ Référentiel Catégories Séances"

    # 👟 Données principales
    COUREURS = "👟 Coureurs"
    SEANCES = "🏋️ Séances"
    SEANCES_TYPES = "📘 Séances Types"

    # 📬 Automatisations & Messages
    MESSAGES_HEBDO = "✉️ Messages Hebdo"

    # 📊 Suivi & Logs
    SUIVI_GENERATION = "📋 Suivi génération"

    # 💬 Communication & Contenu
    CONSEILS_COACH = "💭 Conseils du Coach"

    # 🗃️ Archivage
    ARCHIVES = "🗃️ Archives"

# smartcoach_core/airtable_refs.py

class ASCENARIOS:
    SCN_1 = "reclHUzZQq0tooSUM"   # <-- mets ici le vrai recordID de la table “Scénarios de validation”

def list_all_tables():
    """
    Retourne la liste complète des tables définies.
    Utile pour validation, diagnostic ou logs.
    """
    return [
        value for name, value in ATABLES.__dict__.items()
        if not name.startswith("__") and not callable(value)
    ]
