# smartcoach_core/airtable_refs.py
# =====================================================
# Référentiel CENTRALISÉ des noms de tables Airtable
# Source unique de vérité pour tout SmartCoach
# =====================================================
from services.airtable_tables import ATABLES

class ATREFS:
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
