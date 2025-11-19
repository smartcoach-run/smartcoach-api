# smartcoach_scenarios/scn_1.py
# ===============================================================
# SCN-1 : scénario de génération de plan à partir d’un coureur.
#
# V0 baseline :
#   - ne génère pas encore le plan ni les séances
#   - ne touche pas encore Airtable
#   - se contente d'ajouter un message dans le contexte
#
# FUTUR :
#   - chargement coureur Airtable
#   - contrôles RG-xx
#   - génération plan + séances via generation_service
#   - logs détaillés via log_service
# ===============================================================

from smartcoach_core.context import SmartCoachContext


def run_scn_1(context: SmartCoachContext) -> SmartCoachContext:
    """
    Exécution du scénario SCN-1 (version squelette).
    """

    # Ici on se contente de tracer un message.
    # Plus tard, on branchera :
    #   - airtable_service pour charger le coureur
    #   - rules_service pour appliquer les règles
    #   - generation_service pour produire plan + séances
    context.add_message("SCN-1 exécuté (squelette).")

    return context
